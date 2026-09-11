import streamlit as st
import streamlit.components.v1 as components
import base64
import os
import html
import textwrap
import urllib.parse
import pandas as pd
from matcher import load_schemes, match_schemes, get_all_states, get_all_categories
from nl_search import search_schemes, build_vocabulary, get_suggestions
from translations import get_text
from web_scraper import run_web_scraper, render_web_scraper_ui, setup_scheduled_scraping
from admin_panel import render_admin_panel, check_admin, login_admin
import history as history_module
import favorites as favorites_module
import pdf_export
import doc_checklist
import reminders as reminders_module
import faq
from datetime import datetime, date
from csc_locator import get_csc_centers, find_nearest_csc
import json
import plotly.express as px
import voice_assistant
import simple_explain

# ✅ THEMES MODULE IMPORT
from themes import apply_theme

# ✅ DASHBOARD MODULE IMPORT
from dashboard import render_dashboard

# ===========================
# MOBILE OPTIMIZATION
# ===========================
try:
    from mobile_config import is_mobile, get_items_per_page, get_search_results_count, apply_mobile_css
except ImportError:
    def is_mobile():
        return False
    def get_items_per_page():
        return 10
    def get_search_results_count():
        return 8
    def apply_mobile_css():
        pass

LOGO_PATH = os.path.join("assets", "logo.png")

def get_logo_base64():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

LOGO_B64 = get_logo_base64()

st.set_page_config(
    page_title="Sarkari Scheme",
    page_icon=LOGO_PATH if LOGO_B64 else "🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ===========================
# MOBILE DETECTION
# ===========================
IS_MOBILE = is_mobile()
apply_mobile_css()

# ===========================
# APP CONFIG
# ===========================
try:
    APP_URL = st.secrets.get("APP_URL", os.environ.get("APP_URL", "https://sarkari-scheme.streamlit.app"))
except Exception:
    APP_URL = os.environ.get("APP_URL", "https://sarkari-scheme.streamlit.app")

# ✅ FIX #1: Initialize ALL session state keys EARLY (before any callback fires)
if "lang_choice" not in st.session_state:
    st.session_state.lang_choice = "English"
if "theme_choice" not in st.session_state:
    st.session_state.theme_choice = "Dark"
if "_lang_widget" not in st.session_state:
    st.session_state._lang_widget = st.session_state.lang_choice
if "_theme_widget" not in st.session_state:
    st.session_state._theme_widget = st.session_state.theme_choice

# ✅ FIX #2: Initialize `submitted` at module level to prevent NameError
submitted = False

# ===========================
# SMALL SAFETY HELPERS
# ===========================
def safe_str(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)

def is_valid_url(value):
    if not value:
        return False
    value = str(value).strip()
    if not value or value.lower() == "none":
        return False
    return value.startswith("http://") or value.startswith("https://")

# ===========================
# USER PROFILE SAVE
# ===========================
def load_user_profile():
    if os.path.exists("data/user_profile.json"):
        with open("data/user_profile.json", "r") as f:
            return json.load(f)
    return {}

def save_user_profile(profile):
    os.makedirs("data", exist_ok=True)
    with open("data/user_profile.json", "w") as f:
        json.dump(profile, f, indent=2)

def calculate_eligible_score(r):
    if not r.get("checks"):
        return 100 if r.get("eligible") else 0
    passed = sum(1 for c in r["checks"] if c["passed"])
    total = len(r["checks"])
    if total == 0:
        return 100 if r.get("eligible") else 0
    return int((passed / total) * 100)

def get_deadline_status(deadline):
    if not deadline:
        return None, "No deadline", "#808080"
    try:
        deadline_date = datetime.strptime(str(deadline), "%Y-%m-%d").date()
        today = date.today()
        days_left = (deadline_date - today).days
        if days_left < 0:
            return days_left, "Expired", "#FF4757"
        elif days_left == 0:
            return 0, "Due today", "#FF4757"
        elif days_left <= 7:
            return days_left, f"{days_left} days left", "#FF9933"
        elif days_left <= 30:
            return days_left, f"{days_left} days left", "#00E5FF"
        else:
            return days_left, f"{days_left} days left", "#00FF88"
    except (ValueError, TypeError):
        return None, "Invalid date", "#808080"

# ===========================
# PULSE DASHBOARD FUNCTION
# ===========================
def get_urgent_schemes(df, days_threshold=30):
    urgent = []
    for _, row in df.iterrows():
        deadline = row.get("deadline")
        if not deadline or pd.isna(deadline):
            continue

        days_left, status_text, color = get_deadline_status(deadline)
        if days_left is not None and days_left <= days_threshold:
            urgent.append({
                "scheme_name": safe_str(row["scheme_name"]),
                "category_type": safe_str(row["category_type"]),
                "applicable_state": safe_str(row["applicable_state"]),
                "deadline": deadline,
                "days_left": days_left,
                "status_text": status_text,
                "color": color,
                "apply_link": safe_str(row["apply_link"]),
            })

    urgent.sort(key=lambda x: x["days_left"])
    return urgent

def load_applications():
    if os.path.exists("data/applications.json"):
        with open("data/applications.json", "r") as f:
            return json.load(f)
    return {}

def save_application(scheme_name, status):
    apps = load_applications()
    apps[scheme_name] = status
    os.makedirs("data", exist_ok=True)
    with open("data/applications.json", "w") as f:
        json.dump(apps, f, indent=2)

def load_notification_settings():
    if os.path.exists("data/notification_settings.json"):
        with open("data/notification_settings.json", "r") as f:
            return json.load(f)
    return {"email_alerts": False, "sms_alerts": False, "reminder_days": 7}

def save_notification_settings(settings):
    os.makedirs("data", exist_ok=True)
    with open("data/notification_settings.json", "w") as f:
        json.dump(settings, f, indent=2)

# ===========================
# MODERN SIDEBAR BRANDING
# ===========================
with st.sidebar:
    if LOGO_B64:
        brand_html = (
            '<div style="text-align:center;padding:18px 12px;margin-bottom:15px;'
            'background:linear-gradient(135deg,rgba(0,229,255,0.08),rgba(168,85,247,0.05));'
            'border-radius:15px;border:1px solid rgba(0,229,255,0.2);'
            'box-shadow:0 0 25px rgba(0,229,255,0.1),inset 0 0 20px rgba(0,229,255,0.03);'
            'backdrop-filter:blur(10px);">'
            f'<img src="data:image/png;base64,{LOGO_B64}" width="50" '
            'style="margin-bottom:10px;filter:drop-shadow(0 0 15px rgba(0,229,255,0.8));">'
            '<div style="font-family:Orbitron,sans-serif;font-size:1rem;font-weight:800;'
            'letter-spacing:2px;background:linear-gradient(135deg,#00E5FF,#A855F7);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;margin:0;">SARKARI SCHEME</div>'
            '<p style="color:#6B7A8F;font-size:0.7rem;margin:6px 0 0 0;'
            'letter-spacing:1.5px;text-transform:uppercase;">Find Your Scheme</p>'
            '</div>'
        )
    else:
        brand_html = (
            '<div style="text-align:center;padding:18px 12px;margin-bottom:15px;'
            'background:linear-gradient(135deg,rgba(0,229,255,0.08),rgba(168,85,247,0.05));'
            'border-radius:15px;border:1px solid rgba(0,229,255,0.2);'
            'box-shadow:0 0 25px rgba(0,229,255,0.1),inset 0 0 20px rgba(0,229,255,0.03);'
            'backdrop-filter:blur(10px);">'
            '<div style="font-size:2rem;margin-bottom:8px;'
            'filter:drop-shadow(0 0 15px rgba(0,229,255,0.8));">🏛️</div>'
            '<div style="font-family:Orbitron,sans-serif;font-size:1rem;font-weight:800;'
            'letter-spacing:2px;background:linear-gradient(135deg,#00E5FF,#A855F7);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;margin:0;">SARKARI SCHEME</div>'
            '<p style="color:#6B7A8F;font-size:0.7rem;margin:6px 0 0 0;'
            'letter-spacing:1.5px;text-transform:uppercase;">Find Your Scheme</p>'
            '</div>'
        )
    st.markdown(brand_html, unsafe_allow_html=True)

# ===========================
# THEME & LANGUAGE (FAST SWITCHING)
# ===========================
# ✅ Note: Session state already initialized at top of file
# ✅ Note: No duplicate initialization here

def on_language_change():
    # ✅ SAFE: prevent AttributeError
    new_val = st.session_state.get("_lang_widget", None)
    if new_val is not None:
        st.session_state.lang_choice = new_val
    st.rerun()

def on_theme_change():
    # ✅ SAFE: prevent AttributeError
    new_val = st.session_state.get("_theme_widget", None)
    if new_val is not None:
        st.session_state.theme_choice = new_val
    st.rerun()

with st.sidebar:
    # ✅ FIX #3: Removed `index=` to prevent double rerun
    st.selectbox(
        "Language / भाषा",
        ["English", "हिंदी"],
        key="_lang_widget",
        on_change=on_language_change
    )
    
    lang_choice = st.session_state.lang_choice
    t = get_text(lang_choice)
    
    st.radio(
        t["theme_label"],
        [t["theme_dark"], t["theme_light"]],
        horizontal=True,
        key="_theme_widget",
        on_change=on_theme_change
    )
    
    theme_choice = st.session_state.theme_choice

# ===========================
# COLORS (C)
# ===========================
is_simple_dark = (theme_choice == t["theme_dark"])

if is_simple_dark:
    C = dict(
        app_bg="#0b141a", sidebar_bg="#111b21", card_bg="#1f2c34",
        text="#e9edef", muted="#8696a0", border="#2a3942",
        stat_bg1="#1f2c34", stat_bg2="#1f2c34",
        chip_cat_bg="#2a3942", chip_cat_text="#ffb648",
        chip_state_bg="#2a3942", chip_state_text="#53bdeb",
        card_desc="#8696a0",
        glow_purple="#00a884", glow_pink="#00a884", glow_cyan="#53bdeb",
        glow_orange="#ffb648", glow_green="#00a884", glow_red="#f15c6d",
    )
else:
    C = dict(
        app_bg="#0a0a0f", sidebar_bg="rgba(15, 15, 30, 0.95)", card_bg="rgba(20, 20, 40, 0.85)",
        text="#FFFFFF", muted="#8080a0", border="rgba(100, 100, 255, 0.2)",
        stat_bg1="rgba(25, 25, 50, 0.8)", stat_bg2="rgba(40, 20, 70, 0.8)",
        chip_cat_bg="rgba(30, 30, 60, 0.6)", chip_cat_text="#FF9933",
        chip_state_bg="rgba(30, 30, 60, 0.6)", chip_state_text="#00E5FF",
        card_desc="#9090b0",
        glow_purple="#A855F7", glow_pink="#EC4899", glow_cyan="#00E5FF",
        glow_orange="#FF9933", glow_green="#00FF88", glow_red="#FF4757",
    )

# ===========================
# ✅ APPLY THEME
# ===========================
apply_theme(theme_choice, C, t)

# ===========================
# ✅ GLOW TRAIL (Only Once)
# ===========================
if "glow_trail_injected" not in st.session_state:
    try:
        glow_trail_js = """
        <script>
        (function() {
            const injectGlowTrail = () => {
                const sidebar = document.querySelector('section[data-testid="stSidebar"]');
                if (!sidebar) {
                    setTimeout(injectGlowTrail, 500);
                    return;
                }
                const labels = sidebar.querySelectorAll('.stRadio label');
                labels.forEach(label => {
                    if (!label.querySelector('.glow-trail')) {
                        const glow = document.createElement('span');
                        glow.className = 'glow-trail';
                        label.style.position = 'relative';
                        label.insertBefore(glow, label.firstChild);
                    }
                });
            };
            injectGlowTrail();
            setTimeout(injectGlowTrail, 1000);
        })();
        </script>
        """
        components.html(glow_trail_js, height=0)
        st.session_state.glow_trail_injected = True
    except Exception:
        pass

# ===========================
# ✅ AUTO-SCRAPING (Only Once)
# ===========================
if "auto_scraping_checked" not in st.session_state:
    try:
        setup_scheduled_scraping()
        st.session_state.auto_scraping_checked = True
    except Exception:
        st.session_state.auto_scraping_checked = True

# ===========================
# INITIALIZE CSC VARIABLES
# ===========================
csc_state = t["all"]
csc_search = ""

# ===========================
# SAVED PROFILE LOAD (SIDEBAR)
# ===========================
with st.sidebar:
    saved_profile = load_user_profile()
    if saved_profile:
        st.sidebar.caption(f"👤 Saved Profile: Age {saved_profile.get('age', '-')}, Income ₹{saved_profile.get('income', '-')}, State {saved_profile.get('state', '-')}")

    if IS_MOBILE:
        st.sidebar.caption("📱 Mobile Mode ON")

    st.divider()

    df = load_schemes()
    all_states = get_all_states(df)
    clean_states = [s for s in all_states if s and s != "All"]
    all_categories = [t["all"]] + get_all_categories(df)

    search_mode = st.radio(
        t["mode_label"],
        [
            t["mode_form"], 
            t["mode_nl"], 
            t["mode_favorites"], 
            t["mode_reminders"],
            t["mode_history"], 
            t["mode_faq"], 
            t["mode_csc"], 
            t["mode_dashboard"],
            t["mode_settings"],
            t["mode_notifications"],
            t["mode_admin"],
            t["mode_assistant"],
            t["mode_voice_assistant"],
        ],
        horizontal=False,
    )
    st.divider()

    if search_mode == t["mode_form"]:
        profile = load_user_profile()

        if "age" not in st.session_state:
            st.session_state.age = profile.get("age", 25)
        if "annual_income" not in st.session_state:
            st.session_state.annual_income = profile.get("income", 200000)
        if "state" not in st.session_state:
            st.session_state.state = profile.get("state", "All")

        age = st.slider(t["age"], min_value=0, max_value=100, value=st.session_state.age)
        gender = st.selectbox(t["gender"], [t["all"], "Male", "Female"])
        occupation = st.selectbox(
            t["occupation"],
            [t["all"], "Student", "Farmer", "Self-employed/Small business",
             "Unorganised worker", "Entrepreneur", "Senior citizen", "Unemployed youth"]
        )
        annual_income = st.number_input(t["income"], min_value=0, value=st.session_state.annual_income, step=10000)
        social_category = st.selectbox(t["category"], [t["all"], "General", "SC", "ST", "OBC", "Minority"])

        st.session_state.gender = gender
        st.session_state.occupation = occupation
        st.session_state.social_category = social_category

        state_display = [t["all"]] + clean_states

        if "state" in st.session_state and st.session_state.state in state_display:
            state_index = state_display.index(st.session_state.state)
        else:
            state_index = 0
        state = st.selectbox(t["state"], state_display, index=state_index)

        category_type = st.selectbox(t["scheme_category"], all_categories)
        st.session_state.category_type = category_type
        only_eligible = st.checkbox(t["only_eligible"], value=False)

        sort_choice_form = st.selectbox(
            t["sort_label"],
            [t["sort_default_form"], t["sort_name"], t["sort_category"], t["sort_state"]],
        )

        if st.button(t["search_btn"], use_container_width=True, type="primary"):
            save_user_profile({
                "age": age,
                "income": annual_income,
                "state": state,
            })

            st.session_state.age = age
            st.session_state.annual_income = annual_income
            st.session_state.state = state

            submitted = True
        # ✅ FIX: Removed `else: submitted = False` — already initialized at top

    elif search_mode == t["mode_nl"]:
        sort_choice_nl = st.selectbox(
            t["sort_label"],
            [t["sort_default_nl"], t["sort_name"], t["sort_category"], t["sort_state"]],
        )

    elif search_mode == t["mode_csc"]:
        csc_state = st.selectbox(t["csc_state_label"], [t["all"]] + get_csc_centers()["State"].unique().tolist())
        csc_search = st.text_input(t["csc_search_label"], placeholder=t["csc_search_placeholder"])

    elif search_mode == t["mode_settings"]:
        st.markdown(f"### {t['settings_title']}")

        st.markdown(f"#### {t['settings_my_profile']}")
        profile = load_user_profile()

        profile_age = st.number_input(t["age"], value=profile.get("age", 25), min_value=0, max_value=100)

        state_options = [t["all"]] + clean_states
        saved_state = profile.get("state", t["all"])
        state_index = state_options.index(saved_state) if saved_state in state_options else 0
        profile_state = st.selectbox(t["state"], state_options, index=state_index)

        profile_income = st.number_input(t["income"], value=profile.get("income", 200000), min_value=0, step=10000)

        if st.button(t["settings_save_profile"], use_container_width=True):
            save_user_profile({
                "age": profile_age,
                "state": profile_state,
                "income": profile_income,
            })
            st.success(t["settings_profile_saved"])

        st.markdown(f"#### {t['settings_notifications']}")
        notif_settings = load_notification_settings()
        email_alerts = st.checkbox(t["settings_email_alerts"], value=notif_settings.get("email_alerts", False))
        sms_alerts = st.checkbox(t["settings_sms_alerts"], value=notif_settings.get("sms_alerts", False))
        reminder_days = st.slider(t["settings_reminder_days"], min_value=1, max_value=30, value=notif_settings.get("reminder_days", 7))

        if st.button(t["settings_save_settings"], use_container_width=True):
            save_notification_settings({
                "email_alerts": email_alerts,
                "sms_alerts": sms_alerts,
                "reminder_days": reminder_days,
            })
            st.success(t["settings_settings_saved"])

        st.markdown(f"#### {t['settings_accessibility']}")
        font_size = st.slider(t["settings_font_size"], min_value=12, max_value=24, value=16)

        if st.button(t["settings_apply_font"], use_container_width=True):
            st.markdown(
                f"<style>.stApp, .stApp p, .stApp li, .stApp span {{ font-size: {font_size}px !important; }}</style>",
                unsafe_allow_html=True,
            )

        if "high_contrast" not in st.session_state:
            st.session_state.high_contrast = False
        high_contrast = st.checkbox(t["settings_high_contrast"], value=st.session_state.high_contrast, key="high_contrast")
        if high_contrast:
            st.markdown("<style>.stApp { filter: contrast(1.2); }</style>", unsafe_allow_html=True)

        st.markdown(f"#### {t['settings_data_management']}")
        if st.button(t["settings_clear_data"], use_container_width=True):
            if os.path.exists("data/favorites.json"):
                os.remove("data/favorites.json")
            if os.path.exists("data/history.json"):
                os.remove("data/history.json")
            if os.path.exists("data/reminders.json"):
                os.remove("data/reminders.json")
            st.success(t["settings_data_cleared"])

    st.divider()
    share_text = t["app_share_message"]
    if st.button(t["share_app_btn"], use_container_width=True):
        encoded_share = urllib.parse.quote(share_text)
        encoded_app_url = urllib.parse.quote(APP_URL)
        st.markdown(f"""
        <div style="text-align:center; margin-top:5px;">
            <a href="https://wa.me/?text={encoded_share}%20{encoded_app_url}" target="_blank" 
               style="display:inline-block; padding:8px 16px; background:#25D366; color:white; 
                      border-radius:20px; text-decoration:none; font-size:14px; margin:3px;">
                <img src="https://cdn.simpleicons.org/whatsapp/white" width="16" style="vertical-align:middle;"> WhatsApp
            </a>
            <a href="https://t.me/share/url?url={encoded_app_url}&text={encoded_share}" 
               target="_blank" style="display:inline-block; padding:8px 16px; background:#26A5E4; color:white;
                      border-radius:20px; text-decoration:none; font-size:14px; margin:3px;">
                <img src="https://cdn.simpleicons.org/telegram/white" width="16" style="vertical-align:middle;"> Telegram
            </a>
        </div>
        """, unsafe_allow_html=True)

# ===========================
# NOTIFICATION CENTER
# ===========================
def show_notifications():
    st.markdown(f"### {t['notif_title']}")

    all_reminders = reminders_module.load_reminders()
    if all_reminders:
        st.markdown(f"#### {t['notif_reminders']}")
        for scheme_name, info in all_reminders.items():
            days = reminders_module.days_remaining(info["date"])
            if days < 0:
                st.error(f"❌ **{scheme_name}** - {t['notif_deadline_expired']} {info['date']}")
            elif days <= 7:
                st.warning(f"⚠️ **{scheme_name}** - {t['notif_due_in_days'].format(days=days)} ({info['date']})")
            else:
                st.info(f"📅 **{scheme_name}** - {t['notif_due_in_days'].format(days=days)} ({info['date']})")
    else:
        st.info(t["notif_no_reminders"])

    fav_names = favorites_module.load_favorites()
    if fav_names:
        notif_df = load_schemes()
        fav_schemes = notif_df[notif_df["scheme_name"].isin(fav_names)]
        st.markdown(f"#### {t['notif_favorites_deadlines']}")
        for _, row in fav_schemes.iterrows():
            if row.get("deadline") and pd.notna(row.get("deadline")):
                days_left, status_text, color = get_deadline_status(row["deadline"])
                if days_left is not None and days_left <= 7:
                    st.warning(f"⚠️ **{safe_str(row['scheme_name'])}** - {status_text}")

# ===========================
# RENDER SCHEME CARD FUNCTION
# ===========================
@st.fragment
def render_scheme_card(r, t, key_prefix, lang_choice):
    apps = load_applications()

    scheme_name = safe_str(r.get("scheme_name"))
    category_type = safe_str(r.get("category_type"))
    applicable_state = safe_str(r.get("applicable_state"))
    description = safe_str(r.get("description"))
    benefits = safe_str(r.get("benefits"))
    apply_link = safe_str(r.get("apply_link"))

    is_fav = favorites_module.is_favorite(scheme_name)

    extra_badge = ""
    card_class = ""

    if r.get("deadline") and pd.notna(r.get("deadline")):
        days_left, status_text, color = get_deadline_status(r["deadline"])
        deadline_text = f'<span class="chip chip-deadline">📅 {html.escape(status_text)}</span>'
        extra_badge += deadline_text

    if "eligible" in r:
        score = calculate_eligible_score(r)
        score_text = f'<span class="chip chip-score">🎯 {score}% Match</span>'
        extra_badge += score_text

        card_class = "eligible" if r["eligible"] else "not-eligible"
        badge_class = "chip-eligible" if r["eligible"] else "chip-not-eligible"
        badge_text = t["eligible_badge"] if r["eligible"] else t["not_eligible_badge"]
        extra_badge += f'<span class="chip {badge_class}">{html.escape(badge_text)}</span>'
    elif "score" in r:
        match_pct = int(r["score"] * 100)
        extra_badge += f'<span class="chip chip-score">{match_pct}% match</span>'

    if scheme_name in apps:
        status = apps[scheme_name]
        if status == "Applied":
            extra_badge += f'<span class="chip chip-applied">{t["chip_applied"]}</span>'
        elif status == "Pending":
            extra_badge += f'<span class="chip chip-pending">{t["chip_pending"]}</span>'
        elif status == "Rejected":
            extra_badge += f'<span class="chip chip-rejected">{t["chip_rejected"]}</span>'

    card_html = (
        f'<div class="scheme-card {card_class}">'
        f'{extra_badge}'
        f'<span class="chip chip-category">{html.escape(category_type)}</span>'
        f'<span class="chip chip-state">{html.escape(applicable_state)}</span>'
        f'<h4 style="margin:8px 0 4px 0;">{html.escape(scheme_name)}</h4>'
        f'<p class="card-desc"><b>{html.escape(t["what_is"])}:</b> {html.escape(description)}</p>'
        f'<p class="card-desc"><b>{html.escape(t["benefit"])}:</b> {html.escape(benefits)}</p>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

    widget_key = f"{scheme_name}_{abs(hash((scheme_name, category_type, apply_link)))}"

    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
    with col1:
        star_icon = "⭐" if is_fav else "☆"
        if st.button(star_icon, key=f"{key_prefix}_fav_{widget_key}",
                     help=t["fav_remove_tooltip"] if is_fav else t["fav_add_tooltip"]):
            favorites_module.toggle_favorite(scheme_name)
            st.toast(t["fav_added_toast"] if not is_fav else t["fav_removed_toast"])
            st.rerun(scope="fragment")

    with col2:
        if is_valid_url(apply_link):
            st.link_button(t["app_official_site"], apply_link, use_container_width=True)
        else:
            st.button(t["app_official_site"], disabled=True, use_container_width=True,
                       key=f"{key_prefix}_nolink_{widget_key}", help="No valid link available")

    with col3:
        form_link = safe_str(r.get("form_link")) or apply_link
        if is_valid_url(form_link):
            st.link_button(t["app_apply_here"], form_link, use_container_width=True)
        else:
            st.button(t["app_apply_here"], disabled=True, use_container_width=True,
                       key=f"{key_prefix}_noform_{widget_key}", help="No valid link available")

    with col4:
        with st.popover(t["share_label"], icon=":material/share:", use_container_width=True):
            message = f"{scheme_name} - {benefits}. Apply: {apply_link}"
            encoded_message = urllib.parse.quote(message)
            encoded_url = urllib.parse.quote(apply_link)
            encoded_title = urllib.parse.quote(scheme_name)

            wa_link = f"https://wa.me/?text={encoded_message}"
            tg_link = f"https://t.me/share/url?url={encoded_url}&text={encoded_title}"
            tw_link = f"https://twitter.com/intent/tweet?text={encoded_message}"
            fb_link = f"https://www.facebook.com/sharer/sharer.php?u={encoded_url}"
            mail_link = f"mailto:?subject={encoded_title}&body={encoded_message}"

            icons_html = (
                '<div class="share-icon-row">'
                f'<a href="{wa_link}" target="_blank" title="WhatsApp">'
                '<img src="https://cdn.simpleicons.org/whatsapp/25D366"></a>'
                f'<a href="{tg_link}" target="_blank" title="Telegram">'
                '<img src="https://cdn.simpleicons.org/telegram/26A5E4"></a>'
                f'<a href="{tw_link}" target="_blank" title="Twitter / X">'
                '<img src="https://cdn.simpleicons.org/x/000000"></a>'
                f'<a href="{fb_link}" target="_blank" title="Facebook">'
                '<img src="https://cdn.simpleicons.org/facebook/1877F2"></a>'
                f'<a href="{mail_link}" target="_blank" title="Email">'
                '<img src="https://cdn.simpleicons.org/gmail/EA4335"></a>'
                '</div>'
            )
            st.markdown(icons_html, unsafe_allow_html=True)

            if st.button(t["app_copy_link"], key=f"copy_btn_{widget_key}"):
                st.code(apply_link, language=None)
                st.toast("✅ Official Site Link: " + apply_link)

    with st.expander(t["app_status_label"]):
        current_status = apps.get(scheme_name, "Not Applied")
        status_options = ["Not Applied", "Applied", "Pending", "Rejected"]

        col1, col2 = st.columns([2, 1])
        with col1:
            selected_status = st.selectbox(
                t["app_status_update"], status_options,
                index=status_options.index(current_status) if current_status in status_options else 0,
                key=f"{key_prefix}_status_{widget_key}"
            )
        with col2:
            if st.button(t["app_status_save"], key=f"{key_prefix}_save_status_{widget_key}"):
                save_application(scheme_name, selected_status)
                st.toast(t["app_status_updated_toast"])
                st.rerun(scope="fragment")

    if r.get("checks"):
        with st.expander(t["eligibility_breakdown"]):
            for c in r["checks"]:
                icon = "✔" if c["passed"] else "✘"
                st.write(f"{icon} {html.escape(safe_str(c.get('label')))}")

    with st.expander(t["documents_required_label"]):
        docs = doc_checklist.get_documents(scheme_name, category_type, lang=lang_choice)
        for d in docs:
            st.write(f"• {html.escape(safe_str(d))}")
        st.caption(t["documents_disclaimer"])

    with st.expander(t["reminder_label"]):
        existing = reminders_module.get_reminder(scheme_name)
        default_date = None
        if existing:
            try:
                default_date = datetime.strptime(existing["date"], "%Y-%m-%d").date() if existing and existing.get("date") else None
            except (ValueError, KeyError):
                default_date = None

        reminder_date = st.date_input(
            t["set_reminder_label"], value=default_date,
            key=f"{key_prefix}_date_{widget_key}",
        )
        reminder_note = st.text_input(
            label=t["reminder_note_placeholder"],
            placeholder=t["reminder_note_placeholder"],
            value=existing["note"] if existing else "",
            key=f"{key_prefix}_note_{widget_key}",
            label_visibility="collapsed",
        )
        rcol1, rcol2 = st.columns(2)
        with rcol1:
            if st.button(t["save_reminder_btn"], key=f"{key_prefix}_save_rem_{widget_key}"):
                if reminder_date:
                    reminders_module.set_reminder(scheme_name, reminder_date.isoformat(), reminder_note)
                    st.toast(t["reminder_saved_toast"])
                    st.rerun(scope="fragment")
                else:
                    st.warning(t["reminder_date_warning"])
        with rcol2:
            if existing and st.button(t["remove_reminder_btn"], key=f"{key_prefix}_rm_rem_{widget_key}"):
                reminders_module.remove_reminder(scheme_name)
                st.toast(t["reminder_removed_toast"])
                st.rerun(scope="fragment")

    with st.expander(t["explain_simply_label"]):
        explain_state_key = f"{key_prefix}_explain_{widget_key}"
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button(t["explain_simply_btn"], 
                         key=f"{key_prefix}_explain_btn_{widget_key}", 
                         use_container_width=True,
                         type="primary"):
                progress_text = st.empty()
                progress_text.info(t["explain_generating"])
                
                try:
                    simple_text = simple_explain.explain_scheme(
                        scheme_name=scheme_name,
                        description=description,
                        benefits=benefits,
                        lang_choice=lang_choice,
                        category_type=category_type,
                        applicable_state=applicable_state,
                        apply_link=apply_link,
                        deadline=r.get("deadline", ""),
                        eligible=r.get("eligible", False),
                        score=r.get("score", 0)
                    )
                    st.session_state[explain_state_key] = simple_text
                    progress_text.empty()
                    st.success(t["explain_success"])
                except Exception as e:
                    progress_text.empty()
                    st.error(f"{t['explain_error']} {e}")
        
        with col2:
            if st.button(t["listen_btn"], 
                         key=f"{key_prefix}_listen_{widget_key}", 
                         use_container_width=True):
                try:
                    scheme_data = {
                        "scheme_name": scheme_name,
                        "category_type": category_type,
                        "applicable_state": applicable_state,
                        "description": description,
                        "benefits": benefits,
                        "apply_link": apply_link,
                        "deadline": r.get("deadline", ""),
                        "eligible": r.get("eligible", False),
                        "score": r.get("score", 0)
                    }
                    voice_assistant.read_scheme_details(scheme_data, lang_choice)
                except Exception as e:
                    st.error(f"Could not play audio: {e}")
        
        if explain_state_key in st.session_state:
            st.markdown("---")
            st.markdown(f"### {t['explain_simple_title']}")
            st.markdown(f'<div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 10px; border-left: 4px solid #FF9933;">{st.session_state[explain_state_key]}</div>', unsafe_allow_html=True)
            st.markdown("---")

    st.write("")


def sort_results(results, sort_choice, t):
    if sort_choice == t["sort_name"]:
        return sorted(results, key=lambda r: safe_str(r["scheme_name"]).lower())
    if sort_choice == t["sort_category"]:
        return sorted(results, key=lambda r: safe_str(r["category_type"]).lower())
    if sort_choice == t["sort_state"]:
        return sorted(results, key=lambda r: safe_str(r["applicable_state"]).lower())
    return results

# ===========================
# MAIN AREA — MODERN HERO
# ===========================
hero_icon = (
    f'<img src="data:image/png;base64,{LOGO_B64}" width="80" '
    f'style="vertical-align:middle; margin-right:18px; filter: drop-shadow(0 0 25px rgba(0,229,255,0.9));">'
    if LOGO_B64 else "🏛️"
)

hero_html = (
    '<div style="position:relative;background:linear-gradient(135deg,rgba(0,229,255,0.15) 0%,rgba(168,85,247,0.15) 35%,rgba(236,72,153,0.12) 65%,rgba(255,153,51,0.15) 100%);background-size:300% 300%;animation:gradientShift 10s ease infinite;border-radius:25px;padding:50px 35px;margin-bottom:25px;border:1px solid rgba(0,229,255,0.3);backdrop-filter:blur(15px);box-shadow:0 10px 50px rgba(0,229,255,0.15),0 0 80px rgba(168,85,247,0.1),inset 0 0 40px rgba(255,255,255,0.05);text-align:center;overflow:hidden;">'
    '<div style="position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:linear-gradient(45deg,transparent,rgba(255,255,255,0.08),transparent);animation:shimmer 4s ease-in-out infinite;pointer-events:none;"></div>'
    '<div style="display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:15px;margin-bottom:15px;position:relative;z-index:2;">'
    f'{hero_icon}'
    f'<h1 style="color:#FFFFFF;font-family:Orbitron,sans-serif;font-size:3rem;font-weight:800;letter-spacing:3px;margin:0;text-shadow:0 0 20px rgba(0,229,255,0.6),0 0 40px rgba(168,85,247,0.5),0 0 80px rgba(236,72,153,0.3);">{html.escape(t["title"])}</h1>'
    '</div>'
    f'<p style="color:#B0B0D0;font-size:1.2rem;margin:10px 0 0 0;letter-spacing:1.5px;position:relative;z-index:2;text-shadow:0 0 10px rgba(0,229,255,0.3);">{html.escape(t["subtitle"])}</p>'
    '<div style="display:flex;justify-content:center;flex-wrap:wrap;gap:10px;margin-top:25px;position:relative;z-index:2;">'
    '<span style="background:linear-gradient(135deg,rgba(0,229,255,0.2),rgba(0,229,255,0.05));color:#00E5FF;padding:8px 18px;border-radius:25px;font-size:0.85rem;font-weight:600;border:1px solid rgba(0,229,255,0.5);box-shadow:0 0 15px rgba(0,229,255,0.2);letter-spacing:0.5px;">🎯 Smart Matching</span>'
    '<span style="background:linear-gradient(135deg,rgba(168,85,247,0.2),rgba(168,85,247,0.05));color:#A855F7;padding:8px 18px;border-radius:25px;font-size:0.85rem;font-weight:600;border:1px solid rgba(168,85,247,0.5);box-shadow:0 0 15px rgba(168,85,247,0.2);letter-spacing:0.5px;">🌐 Multi-Language</span>'
    '<span style="background:linear-gradient(135deg,rgba(255,153,51,0.2),rgba(255,153,51,0.05));color:#FF9933;padding:8px 18px;border-radius:25px;font-size:0.85rem;font-weight:600;border:1px solid rgba(255,153,51,0.5);box-shadow:0 0 15px rgba(255,153,51,0.2);letter-spacing:0.5px;">🤖 AI Assistant</span>'
    '<span style="background:linear-gradient(135deg,rgba(0,255,136,0.2),rgba(0,255,136,0.05));color:#00FF88;padding:8px 18px;border-radius:25px;font-size:0.85rem;font-weight:600;border:1px solid rgba(0,255,136,0.5);box-shadow:0 0 15px rgba(0,255,136,0.2);letter-spacing:0.5px;">⚡ Real-time Updates</span>'
    '</div>'
    '</div>'
)

st.markdown(hero_html, unsafe_allow_html=True)

st.markdown("""
<style>
@keyframes gradientShift {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
@keyframes shimmer {
    0% { transform: translateX(-100%) rotate(45deg); }
    100% { transform: translateX(100%) rotate(45deg); }
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    f'<div style="background:linear-gradient(135deg,rgba(255,153,51,0.1),rgba(255,153,51,0.05));border-left:4px solid #FF9933;border-radius:10px;padding:15px 20px;margin-bottom:25px;box-shadow:0 0 20px rgba(255,153,51,0.1);">'
    f'<p style="color:#FFB648;margin:0;font-size:0.9rem;letter-spacing:0.3px;">⚠️ {html.escape(t["disclaimer"])}</p>'
    '</div>',
    unsafe_allow_html=True
)

# ===========================
# QUICK ACTION CARDS (TRANSLATED)
# ===========================
if search_mode not in [t["mode_dashboard"], t["mode_admin"], t["mode_settings"], t["mode_notifications"]]:
    st.markdown(f"### {t.get('quick_actions_title', 'Quick Actions')}")
    st.caption(t.get('quick_actions_caption', 'Choose what you need'))
    
    qa_col1, qa_col2, qa_col3 = st.columns(3)
    
    with qa_col1:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(0,229,255,0.1),rgba(0,229,255,0.02));border:1px solid rgba(0,229,255,0.3);border-radius:15px;padding:20px;text-align:center;box-shadow:0 0 15px rgba(0,229,255,0.1);">
            <div style="font-size:2.5rem;margin-bottom:10px;">🎯</div>
            <h4 style="color:#00E5FF;margin:0 0 5px 0;font-family:'Orbitron',sans-serif;">{t.get('qa_find_schemes_title', 'Find Schemes')}</h4>
            <p style="color:#8696A0;font-size:0.85rem;margin:0;">{t.get('qa_find_schemes_desc', 'Search schemes by eligibility')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with qa_col2:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(168,85,247,0.1),rgba(168,85,247,0.02));border:1px solid rgba(168,85,247,0.3);border-radius:15px;padding:20px;text-align:center;box-shadow:0 0 15px rgba(168,85,247,0.1);">
            <div style="font-size:2.5rem;margin-bottom:10px;">🔍</div>
            <h4 style="color:#A855F7;margin:0 0 5px 0;font-family:'Orbitron',sans-serif;">{t.get('qa_smart_search_title', 'Smart Search')}</h4>
            <p style="color:#8696A0;font-size:0.85rem;margin:0;">{t.get('qa_smart_search_desc', 'Search in your own words')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with qa_col3:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,rgba(0,255,136,0.1),rgba(0,255,136,0.02));border:1px solid rgba(0,255,136,0.3);border-radius:15px;padding:20px;text-align:center;box-shadow:0 0 15px rgba(0,255,136,0.1);">
            <div style="font-size:2.5rem;margin-bottom:10px;">🤖</div>
            <h4 style="color:#00FF88;margin:0 0 5px 0;font-family:'Orbitron',sans-serif;">{t.get('qa_ai_assistant_title', 'AI Assistant')}</h4>
            <p style="color:#8696A0;font-size:0.85rem;margin:0;">{t.get('qa_ai_assistant_desc', 'Chat directly with AI')}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.write("")
    st.divider()

# ===========================
# DASHBOARD
# ===========================
if search_mode == t["mode_dashboard"]:
    render_dashboard(df, get_urgent_schemes, C)

# ===========================
# NOTIFICATION CENTER
# ===========================
elif search_mode == t["mode_notifications"]:
    show_notifications()

# ===========================
# ADMIN PANEL
# ===========================
elif search_mode == t["mode_admin"]:
    render_admin_panel()

# ===========================
# AI ASSISTANT
# ===========================
elif search_mode == t["mode_assistant"]:
    from ai_chatbot import render_ai_assistant
    render_ai_assistant(
        render_scheme_card=render_scheme_card,
        sort_results=sort_results,
        t=t
    )

# ===========================
# VOICE ASSISTANT
# ===========================
elif search_mode == t["mode_voice_assistant"]:
    # ✅ FIX: Wrap in try/except for safety
    try:
        voice_assistant.render_voice_assistant(
            df=df,
            t=t,
            lang_choice=lang_choice,
            search_schemes_fn=search_schemes,
            sort_results_fn=sort_results,
            render_scheme_card_fn=render_scheme_card,
            history_module=history_module,
        )
    except Exception as e:
        st.error(f"⚠️ Voice Assistant error: {e}")
        with st.expander("Debug info"):
            st.exception(e)

# ===========================
# SETTINGS INFO (handled in sidebar)
# ===========================
elif search_mode == t["mode_settings"]:
    st.info(t["settings_use_sidebar"])

# ===========================
# MODE 1: ELIGIBILITY CHECK
# ===========================
elif search_mode == t["mode_form"]:
    if "form_results" in st.session_state and st.session_state.get("form_submitted", False):
        results = st.session_state.form_results
        eligible_count = st.session_state.form_eligible_count

        if "last_search" in st.session_state:
            last_search = st.session_state.last_search
            current_search = {
                "age": st.session_state.age, "gender": st.session_state.gender, "occupation": st.session_state.occupation,
                "annual_income": st.session_state.annual_income, "social_category": st.session_state.social_category,
                "state": st.session_state.state, "category_type": st.session_state.category_type, "only_eligible": only_eligible
            }
            if last_search != current_search:
                st.session_state.form_results = []
                st.session_state.form_eligible_count = 0
                st.session_state.form_submitted = False
                st.session_state.last_search = current_search

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"<div class='stat-box'><div class='stat-number'>{len(results)}</div>"
                        f"<div class='stat-label'>{t['total_shown']}</div></div>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"<div class='stat-box'><div class='stat-number'>{eligible_count}</div>"
                        f"<div class='stat-label'>{t['eligible_label']}</div></div>", unsafe_allow_html=True)
        with col3:
            st.markdown(f"<div class='stat-box'><div class='stat-number'>{len(results) - eligible_count}</div>"
                        f"<div class='stat-label'>{t['not_eligible_label']}</div></div>", unsafe_allow_html=True)

        st.write("")

        col_clear1, col_clear2 = st.columns([1, 5])
        with col_clear1:
            if st.button(t["clear_results_btn"], use_container_width=True):
                st.session_state.form_results = []
                st.session_state.form_eligible_count = 0
                st.session_state.form_submitted = False
                st.session_state.last_search = {}
                st.rerun()

        if results:
            pdf_bytes = pdf_export.build_pdf(results, profile=st.session_state.form_profile)
            st.download_button(
                t["pdf_download_btn"], data=pdf_bytes,
                file_name="sarkari_scheme_report.pdf", mime="application/pdf",
            )
            st.write("")

            items_per_page = get_items_per_page()
            total_results = len(results)
            start_idx = 0
            
            if IS_MOBILE and total_results > items_per_page:
                for r in results[start_idx:start_idx + items_per_page]:
                    render_scheme_card(r, t, "form", lang_choice)
                
                if "show_more_form" not in st.session_state:
                    st.session_state.show_more_form = False
                
                if st.session_state.show_more_form:
                    for r in results[items_per_page:]:
                        render_scheme_card(r, t, "form", lang_choice)
                else:
                    if st.button(t["load_more_btn"], use_container_width=True):
                        st.session_state.show_more_form = True
                        st.rerun()
            else:
                for r in results:
                    render_scheme_card(r, t, "form", lang_choice)
        else:
            st.info(t["no_results"])

    elif submitted:
        with st.spinner(t["searching_spinner"]):
            gender_val = "All" if gender == t["all"] else gender
            category_val = "All" if social_category == t["all"] else social_category
            occupation_val = "All" if occupation == t["all"] else occupation
            state_val = "All" if state == t["all"] else state
            scheme_cat_val = "All" if st.session_state.category_type == t["all"] else st.session_state.category_type

            results = match_schemes(
                df, age=age, annual_income=annual_income, gender=gender_val,
                social_category=category_val, occupation=occupation_val,
                state=state_val, category_type=scheme_cat_val, only_eligible=only_eligible,
            )
            results = sort_results(results, sort_choice_form, t)

            eligible_count = sum(1 for r in results if r["eligible"])

            history_module.save_entry({
                "mode": "form", "age": age, "state": state_val,
                "total": len(results), "eligible": eligible_count,
            })

            st.session_state.form_results = results
            st.session_state.form_eligible_count = eligible_count
            st.session_state.form_profile = {
                "Age": age, "Gender": gender_val, "Annual Income": annual_income,
                "State": state_val, "Category": category_val,
            }
            st.session_state.form_submitted = True
            st.session_state.last_search = {
                "age": age, "gender": gender, "occupation": occupation,
                "annual_income": annual_income, "social_category": social_category,
                "state": state, "category_type": st.session_state.category_type, "only_eligible": only_eligible
            }

            st.rerun()

    else:
        st.info(t["hint"])

# ===========================
# MODE 2: SEARCH SCHEMES (NL)
# ===========================
elif search_mode == t["mode_nl"]:
    def _select_suggestion(term):
        st.session_state.nl_query = term

    input_col = st.columns([1])[0]
    with input_col:
        query = st.text_input(
            t["mode_nl"], placeholder=t["nl_placeholder"], label_visibility="collapsed",
            key="nl_query",
        )

    vocab = build_vocabulary(df)
    suggestions = get_suggestions(vocab, query, max_n=6)

    if suggestions:
        st.caption(t["suggestions_label"])
        chip_cols = st.columns(len(suggestions))
        for i, s in enumerate(suggestions):
            with chip_cols[i]:
                st.button(
                    s, key=f"sugg_{s}", use_container_width=True,
                    on_click=_select_suggestion, args=(s,),
                )

    nl_submitted = st.button(t["nl_search_btn"], type="primary")

    st.caption(t["nl_note"])
    st.write("")

    if query.strip():
        with st.spinner("🔍 Searching..."):
            top_n = get_search_results_count()
            results = search_schemes(df, query, top_n=top_n)
            results = sort_results(results, sort_choice_nl, t)

        if nl_submitted:
            history_module.save_entry({
                "mode": "nl", "query": query.strip(), "total": len(results),
            })

        if results:
            st.success(f"{len(results)} {t['nl_matches_found']}")

            pdf_bytes = pdf_export.build_pdf(results, profile={"Search Query": query.strip()})
            st.download_button(
                t["pdf_download_btn"], data=pdf_bytes,
                file_name="sarkari_scheme_report.pdf", mime="application/pdf",
            )
            st.write("")

            items_per_page = get_items_per_page()
            if IS_MOBILE and len(results) > items_per_page:
                for r in results[:items_per_page]:
                    render_scheme_card(r, t, "nl", lang_choice)
                if "show_more_nl" not in st.session_state:
                    st.session_state.show_more_nl = False
                if st.session_state.show_more_nl:
                    for r in results[items_per_page:]:
                        render_scheme_card(r, t, "nl", lang_choice)
                else:
                    if st.button(t["load_more_btn"], use_container_width=True):
                        st.session_state.show_more_nl = True
                        st.rerun()
            else:
                for r in results:
                    render_scheme_card(r, t, "nl", lang_choice)
        else:
            st.info(t["nl_no_results"])
    else:
        st.info(t["nl_hint"])

# ===========================
# MODE 3: FAVORITES
# ===========================
elif search_mode == t["mode_favorites"]:
    st.markdown(f"### {t['favorites_title']}")

    fav_names = favorites_module.load_favorites()

    if not fav_names:
        st.info(t["favorites_empty"])
    else:
        fav_rows = df[df["scheme_name"].isin(fav_names)]
        fav_rows = fav_rows.sort_values("scheme_name")

        for _, row in fav_rows.iterrows():
            r = {
                "scheme_name": row["scheme_name"],
                "category_type": row["category_type"],
                "applicable_state": row["applicable_state"],
                "description": row["description"],
                "benefits": row["benefits"],
                "apply_link": row["apply_link"],
                "deadline": row.get("deadline", None),
                "form_link": row.get("form_link", None),
            }
            render_scheme_card(r, t, key_prefix="fav", lang_choice=lang_choice)

# ===========================
# MODE 4: REMINDERS
# ===========================
elif search_mode == t["mode_reminders"]:
    st.markdown(f"### {t['reminders_title']}")
    st.caption(t["reminders_disclaimer"])

    all_reminders = reminders_module.load_reminders()

    if not all_reminders:
        st.info(t["reminders_empty"])
    else:
        sorted_items = sorted(all_reminders.items(), key=lambda kv: kv[1]["date"])

        for scheme_name, info in sorted_items:
            days = reminders_module.days_remaining(info["date"])

            if days < 0:
                status_text = t["reminder_overdue"]
                status_color = "#FF4757"
            elif days == 0:
                status_text = t["reminder_today"]
                status_color = "#FF4757"
            elif days <= 7:
                status_text = t["reminder_due_soon"].format(days=days)
                status_color = "#FF9933"
            else:
                status_text = t["reminder_upcoming"].format(days=days)
                status_color = "#00FF88"

            note_html = f'<p class="card-desc">{html.escape(info["note"])}</p>' if info.get("note") else ""

            reminder_html = (
                '<div class="scheme-card">'
                f'<span class="chip" style="background-color:rgba(255,71,87,0.2); color:{status_color}; border:1px solid {status_color};">{html.escape(status_text)}</span>'
                f'<h4 style="margin:8px 0 4px 0;">{html.escape(scheme_name)}</h4>'
                f'<p class="card-desc"><b>{html.escape(t["set_reminder_label"])}:</b> {html.escape(info["date"])}</p>'
                f'{note_html}'
                '</div>'
            )
            st.markdown(reminder_html, unsafe_allow_html=True)

            if st.button(t["remove_reminder_btn"], key=f"rem_list_remove_{scheme_name}"):
                reminders_module.remove_reminder(scheme_name)
                st.toast(t["reminder_removed_toast"])
                st.rerun()
            st.write("")

# ===========================
# MODE 5: SEARCH HISTORY
# ===========================
elif search_mode == t["mode_history"]:
    st.markdown(f"### {t['history_title']}")

    entries = history_module.load_history()

    if not entries:
        st.info(t["history_empty"])
    else:
        if st.button(t["history_clear_btn"]):
            history_module.clear_history()
            st.toast("🗑️ History Cleared")
            st.rerun()

        st.write("")

        for entry in entries:
            if entry.get("mode") == "form":
                summary = t["history_form_summary"].format(
                    age=entry.get("age", "-"), state=entry.get("state", "-"),
                    eligible=entry.get("eligible", 0), total=entry.get("total", 0),
                )
            else:
                summary = t["history_nl_summary"].format(
                    query=entry.get("query", ""), total=entry.get("total", 0),
                )

            st.markdown(
                f'<div class="scheme-card">'
                f'<p style="color:{C["muted"]}; font-size:12px; margin:0 0 6px 0;">'
                f'{html.escape(entry.get("timestamp", ""))}</p>'
                f'<p style="margin:0;" class="card-desc">{html.escape(summary)}</p>'
                f'</div>',
                unsafe_allow_html=True,
            )

# ===========================
# MODE 6: FAQ
# ===========================
elif search_mode == t["mode_faq"]:
    st.markdown(f"### {t['faq_title']}")

    for question, answer in faq.get_faqs(lang_choice):
        with st.expander(question):
            st.write(answer)

# ===========================
# MODE 7: CSC LOCATOR (Bhopal-Specific)
# ===========================
elif search_mode == t["mode_csc"]:
    st.markdown(f"### {t['csc_title']}")
    st.caption("🗺️ Currently showing CSC centers in **Bhopal** only. Apna area ya pincode daaliye, hum aapke sabse nazdeek CSC center dhoondhenge.")

    # ✅ Address-based Search (Bhopal Only)
    st.markdown("#### 📍 Find Nearest CSC Center in Bhopal")
    st.caption("Apna area, colony, ya pincode daaliye (e.g. 'MP Nagar', '462011', 'Kolar Road').")
    
    col_addr, col_btn = st.columns([4, 1])
    with col_addr:
        user_address = st.text_input(
            "Address / Area / Pincode (Bhopal)",
            placeholder="e.g. 'MP Nagar' or '462011' or 'Kolar Road'",
            key="csc_user_address_input",
            label_visibility="collapsed"
        )
    with col_btn:
        search_nearby = st.button("🔍 Search", use_container_width=True, type="primary", key="csc_nearby_btn")
    
    if search_nearby and user_address and user_address.strip():
        with st.spinner("🔍 Aapke aas-paas ke CSC centers dhoondh rahe hain..."):
            try:
                user_lat, user_lon, nearest_df, source = find_nearest_csc(user_address, max_results=10)
            except Exception as e:
                st.error(f"Error: {e}")
                user_lat, user_lon, nearest_df = None, None, pd.DataFrame()
        
        if user_lat is not None and not nearest_df.empty:
            st.success(f"✅ Aapke aas-paas ke {len(nearest_df)} CSC centers mile!")
            st.caption(f"📍 Aapki location: ({user_lat:.4f}, {user_lon:.4f}) — matched via **{source}**")
            
            for _, row in nearest_df.iterrows():
                distance_val = row.get("Distance (km)", None)
                distance_text = f"{distance_val:.1f} km" if distance_val is not None else "Distance N/A"
                
                # Google Maps link for directions
                gmaps_link = f"https://www.google.com/maps/dir/?api=1&destination={row['Latitude']},{row['Longitude']}"
                
                st.markdown(
                    f'<div class="scheme-card">'
                    f'<span class="chip chip-state" style="background:rgba(0,229,255,0.15); color:#00E5FF; border:1px solid #00E5FF;">📍 {html.escape(distance_text)}</span>'
                    f'<h4 style="margin:8px 0 4px 0;">{html.escape(safe_str(row.get("Name")))}</h4>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_address_label"])}:</b> {html.escape(safe_str(row.get("Address")))}</p>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_district_label"])}:</b> {html.escape(safe_str(row.get("District")))}, {html.escape(safe_str(row.get("State")))}</p>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_phone_label"])}:</b> {html.escape(safe_str(row.get("Phone")))}</p>'
                    f'<p class="card-desc"><a href="{gmaps_link}" target="_blank" style="color:#00E5FF;">🗺️ Get Directions on Google Maps</a></p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
        else:
            st.warning(
                "⚠️ Aapka address locate nahi kar paye. Kripya pincode ke saath try karein "
                "(jaise '462011' ya 'MP Nagar, Bhopal')."
            )
    elif search_nearby and not user_address.strip():
        st.info("Kripya pehle apna area ya pincode daalein.")
    
    st.divider()
    
    # ✅ Browse All Bhopal Centers
    st.markdown("#### 🗺️ All CSC Centers in Bhopal")
    
    csc_df = get_csc_centers()
    st.write(f"**{len(csc_df)}** CSC centers found in Bhopal")
    st.write("")

    if len(csc_df) > 0:
        for _, row in csc_df.iterrows():
            gmaps_link = f"https://www.google.com/maps/search/?api=1&query={row['Latitude']},{row['Longitude']}"
            
            st.markdown(
                f'<div class="scheme-card">'
                f'<h4 style="margin:0 0 4px 0;">{html.escape(safe_str(row["Name"]))}</h4>'
                f'<p class="card-desc"><b>{html.escape(t["csc_address_label"])}:</b> {html.escape(safe_str(row["Address"]))}</p>'
                f'<p class="card-desc"><b>{html.escape(t["csc_district_label"])}:</b> {html.escape(safe_str(row["District"]))}</p>'
                f'<p class="card-desc"><b>{html.escape(t["csc_phone_label"])}:</b> {html.escape(safe_str(row["Phone"]))}</p>'
                f'<p class="card-desc"><a href="{gmaps_link}" target="_blank" style="color:#00E5FF;">🗺️ View on Google Maps</a></p>'
                f'</div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No CSC centers found.")

# ===========================
# FALLBACK: Unknown mode
# ===========================
else:
    st.warning(f"⚠️ Unknown mode: {search_mode}")