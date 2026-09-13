"""
app.py — Main entry point for Sarkari Scheme Finder.

Multi-mode Streamlit app with 13 sidebar modes.

FIXES (v5):
  - CRITICAL: `submitted` transient boolean bug fixed — search params ab
    st.session_state mein persist hote hain, results reliably render hote hain.
  - CRITICAL: NameErrors fixed (`only_eligible`, `sort_choice_form`,
    `sort_choice_nl`, `gender`, `occupation`, `state`, `category_type`) —
    saare values ab st.session_state se read hoti hain.
  - Checkbox/selectbox widget keys added — state persist karta hai.
  - Atomic JSON writes (profile, applications, notifications).
  - Corrupt JSON quarantine (silent swallow nahi).
  - Query param cleanup improved.
  - `get_deadline_status` invalid dates ke liye (None, None, None) — chip hide.
  - `_render_scraping_tab(df)` unused param removed.
  - set_page_config() FIRST (Streamlit requirement).
"""

import base64
import html
import json
import os
import tempfile
import urllib.parse
from datetime import datetime, date

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from matcher import load_schemes, match_schemes, get_all_states, get_all_categories
from nl_search import search_schemes, build_vocabulary, get_suggestions
from translations import get_text
from themes import apply_theme
from admin_panel import render_admin_panel
import history as history_module
import favorites as favorites_module
import reminders as reminders_module
import faq as faq_module
import doc_checklist
import pdf_export
import voice_assistant
import simple_explain
from csc_locator import get_csc_centers, find_nearest_csc
from dashboard import render_dashboard

try:
    from mobile_config import (
        is_mobile, get_items_per_page, get_search_results_count, apply_mobile_css,
    )
except ImportError:
    def is_mobile(): return False
    def get_items_per_page(): return 10
    def get_search_results_count(): return 8
    def apply_mobile_css(): pass


# ===========================
# CONFIG
# ===========================
LOGO_PATH = os.path.join("assets", "logo.png")

try:
    APP_URL = st.secrets.get(
        "APP_URL",
        os.environ.get("APP_URL", "https://sarkari-scheme.streamlit.app"),
    )
except Exception:
    APP_URL = os.environ.get("APP_URL", "https://sarkari-scheme.streamlit.app")


def get_logo_base64():
    if os.path.exists(LOGO_PATH):
        try:
            with open(LOGO_PATH, "rb") as f:
                return base64.b64encode(f.read()).decode()
        except Exception:
            return None
    return None


LOGO_B64 = get_logo_base64()


# ===========================
# PAGE CONFIG — MUST BE FIRST
# ===========================
st.set_page_config(
    page_title="Sarkari Scheme",
    page_icon=LOGO_PATH if LOGO_B64 else "🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

IS_MOBILE = is_mobile()
apply_mobile_css()


# ===========================
# SAFE HELPERS
# ===========================
def safe_str(value, default=""):
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def is_valid_url(value):
    if not value:
        return False
    value = str(value).strip()
    if not value or value.lower() == "none":
        return False
    return value.startswith("http://") or value.startswith("https://")


def calculate_eligible_score(r):
    if not isinstance(r, dict):
        return 0
    checks = r.get("checks")
    if not checks:
        return 100 if r.get("eligible") else 0
    passed = sum(1 for c in checks if isinstance(c, dict) and c.get("passed"))
    total = len(checks)
    if total == 0:
        return 100 if r.get("eligible") else 0
    return int((passed / total) * 100)


def get_deadline_status(deadline):
    """Invalid/missing → (None, None, None). Chip hide ho jaayega."""
    if not deadline:
        return None, None, None
    try:
        deadline_date = datetime.strptime(str(deadline), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None, None, None
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


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _atomic_json_write(path, data):
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".json_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        _safe_remove(tmp_path)
        raise


def _quarantine_json(path):
    try:
        if not os.path.exists(path):
            return
        corrupt = path + ".corrupt"
        if os.path.exists(corrupt):
            corrupt = f"{path}.{int(datetime.now().timestamp())}.corrupt"
        os.replace(path, corrupt)
    except OSError:
        pass


def _load_json_safe(path, default_factory):
    if not os.path.exists(path):
        return default_factory()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        expected_type = type(default_factory())
        if not isinstance(data, expected_type):
            return default_factory()
        return data
    except (json.JSONDecodeError, OSError):
        _quarantine_json(path)
        return default_factory()


# ===========================
# USER PROFILE / APPLICATIONS / NOTIFICATIONS
# ===========================
PROFILE_FILE = "data/user_profile.json"
APPLICATIONS_FILE = "data/applications.json"
NOTIFICATIONS_FILE = "data/notification_settings.json"


def load_user_profile():
    return _load_json_safe(PROFILE_FILE, dict)


def save_user_profile(profile):
    try:
        if not isinstance(profile, dict):
            return
        _atomic_json_write(PROFILE_FILE, profile)
    except Exception as e:
        print(f"[app.py] save_user_profile failed: {e}")


def load_applications():
    return _load_json_safe(APPLICATIONS_FILE, dict)


def save_application(scheme_name, status):
    if not scheme_name:
        return
    apps = load_applications()
    apps[str(scheme_name)] = str(status)
    try:
        _atomic_json_write(APPLICATIONS_FILE, apps)
    except Exception as e:
        print(f"[app.py] save_application failed: {e}")


def load_notification_settings():
    default = {"email_alerts": False, "sms_alerts": False, "reminder_days": 7}
    data = _load_json_safe(NOTIFICATIONS_FILE, dict)
    if not data:
        return default
    for k, v in default.items():
        data.setdefault(k, v)
    return data


def save_notification_settings(settings):
    try:
        if not isinstance(settings, dict):
            return
        _atomic_json_write(NOTIFICATIONS_FILE, settings)
    except Exception as e:
        print(f"[app.py] save_notification_settings failed: {e}")


# ===========================
# SESSION STATE INIT
# ===========================
_defaults = {
    "lang_choice": "English",
    "theme_choice": "Dark",
    "_lang_widget": "English",
    "_theme_widget": "Dark",
    "font_size": 16,
    "search_params": {},
    "form_submitted": False,
    "high_contrast": False,
}
for _k, _v in _defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ===========================
# QUERY PARAM CONSUMPTION
# ===========================
def _consume_query_params():
    try:
        qp = st.query_params
    except Exception:
        return
    try:
        qa_mode = qp.get("qa_mode", None)
        if qa_mode:
            st.session_state.qa_navigate_to = qa_mode
            try:
                del st.query_params["qa_mode"]
            except Exception:
                try:
                    st.query_params.clear()
                except Exception:
                    pass
    except Exception:
        pass
    try:
        voice_query = qp.get("voice_query", None)
        if voice_query:
            st.session_state.voice_query_from_url = voice_query
            try:
                del st.query_params["voice_query"]
            except Exception:
                pass
    except Exception:
        pass


_consume_query_params()

_should_scroll_this_run = st.session_state.pop("scroll_to_results", False)


# ===========================
# CALLBACKS
# ===========================
def on_mode_change():
    st.session_state.scroll_to_results = True


def on_language_change():
    new_val = st.session_state.get("_lang_widget", None)
    if new_val is not None:
        st.session_state.lang_choice = new_val


def on_theme_change():
    new_val = st.session_state.get("_theme_widget", None)
    if new_val is not None:
        st.session_state.theme_choice = new_val


# ===========================
# SIDEBAR HELPERS
# ===========================
def _render_settings_sidebar(t, clean_states):
    st.markdown(f"### {t['settings_title']}")
    st.markdown(f"#### {t['settings_my_profile']}")

    profile = load_user_profile()
    profile_age = st.number_input(
        t["age"], value=int(profile.get("age", 25) or 25),
        min_value=0, max_value=100, key="settings_profile_age",
    )

    state_options = [t["all"]] + clean_states
    saved_state = profile.get("state", t["all"])
    state_index = state_options.index(saved_state) if saved_state in state_options else 0
    profile_state = st.selectbox(
        t["state"], state_options, index=state_index, key="settings_profile_state",
    )

    profile_income = st.number_input(
        t["income"], value=int(profile.get("income", 200000) or 200000),
        min_value=0, step=10000, key="settings_profile_income",
    )

    if st.button(t["settings_save_profile"], use_container_width=True,
                 key="settings_save_profile_btn"):
        save_user_profile({
            "age": profile_age,
            "state": profile_state,
            "income": profile_income,
        })
        st.success(t["settings_profile_saved"])

    st.markdown(f"#### {t['settings_notifications']}")
    notif_settings = load_notification_settings()
    email_alerts = st.checkbox(
        t["settings_email_alerts"],
        value=notif_settings.get("email_alerts", False),
        key="settings_email_alerts",
    )
    sms_alerts = st.checkbox(
        t["settings_sms_alerts"],
        value=notif_settings.get("sms_alerts", False),
        key="settings_sms_alerts",
    )
    reminder_days = st.slider(
        t["settings_reminder_days"], min_value=1, max_value=30,
        value=notif_settings.get("reminder_days", 7),
        key="settings_reminder_days",
    )
    if st.button(t["settings_save_settings"], use_container_width=True,
                 key="settings_save_settings_btn"):
        save_notification_settings({
            "email_alerts": email_alerts,
            "sms_alerts": sms_alerts,
            "reminder_days": reminder_days,
        })
        st.success(t["settings_settings_saved"])

    st.markdown(f"#### {t['settings_accessibility']}")
    font_size = st.slider(
        t["settings_font_size"], min_value=12, max_value=24,
        value=st.session_state.font_size, key="settings_font_size",
    )
    if font_size != st.session_state.font_size:
        st.session_state.font_size = font_size
        st.markdown(
            f"<style>.stApp, .stApp p, .stApp li, .stApp span "
            f"{{ font-size: {font_size}px !important; }}</style>",
            unsafe_allow_html=True,
        )

    high_contrast = st.checkbox(
        t["settings_high_contrast"],
        value=st.session_state.high_contrast,
        key="high_contrast_checkbox",
    )
    st.session_state.high_contrast = high_contrast
    if high_contrast:
        st.markdown(
            "<style>.stApp { filter: contrast(1.2); }</style>",
            unsafe_allow_html=True,
        )

    st.markdown(f"#### {t['settings_data_management']}")
    if st.button(t["settings_clear_data"], use_container_width=True,
                 key="settings_clear_data_btn"):
        for f in ["data/favorites.json", "data/search_history.json",
                  "data/reminders.json", "data/history.json"]:
            _safe_remove(f)
        st.success(t["settings_data_cleared"])


def _render_share_app_sidebar(t):
    share_text = t["app_share_message"]
    if st.button(t["share_app_btn"], use_container_width=True, key="share_app_btn"):
        encoded_share = urllib.parse.quote(share_text)
        encoded_app_url = urllib.parse.quote(APP_URL)
        st.markdown(
            '<div style="text-align:center; margin-top:5px;">'
            f'<a href="https://wa.me/?text={encoded_share}%20{encoded_app_url}" '
            'target="_blank" style="display:inline-block; padding:8px 16px; '
            'background:#25D366; color:white; border-radius:20px; '
            'text-decoration:none; font-size:14px; margin:3px;">'
            '<img src="https://cdn.simpleicons.org/whatsapp/white" width="16" '
            'style="vertical-align:middle;"> WhatsApp</a>'
            f'<a href="https://t.me/share/url?url={encoded_app_url}&text={encoded_share}" '
            'target="_blank" style="display:inline-block; padding:8px 16px; '
            'background:#26A5E4; color:white; border-radius:20px; '
            'text-decoration:none; font-size:14px; margin:3px;">'
            '<img src="https://cdn.simpleicons.org/telegram/white" width="16" '
            'style="vertical-align:middle;"> Telegram</a>'
            '</div>',
            unsafe_allow_html=True,
        )


# ===========================
# SIDEBAR — BRANDING
# ===========================
with st.sidebar:
    if LOGO_B64:
        st.markdown(
            '<div style="text-align:center;padding:18px 12px;margin-bottom:15px;'
            'background:linear-gradient(135deg,rgba(0,229,255,0.08),rgba(168,85,247,0.05));'
            'border-radius:15px;border:1px solid rgba(0,229,255,0.2);'
            'box-shadow:0 0 25px rgba(0,229,255,0.1),inset 0 0 20px rgba(0,229,255,0.03);">'
            f'<img src="data:image/png;base64,{LOGO_B64}" width="50" '
            'style="margin-bottom:10px;filter:drop-shadow(0 0 15px rgba(0,229,255,0.8));">'
            '<div style="font-family:Orbitron,sans-serif;font-size:1rem;font-weight:800;'
            'letter-spacing:2px;background:linear-gradient(135deg,#00E5FF,#A855F7);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;margin:0;">SARKARI SCHEME</div>'
            '<p style="color:#6B7A8F;font-size:0.7rem;margin:6px 0 0 0;'
            'letter-spacing:1.5px;text-transform:uppercase;">Find Your Scheme</p>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="text-align:center;padding:18px 12px;margin-bottom:15px;'
            'background:linear-gradient(135deg,rgba(0,229,255,0.08),rgba(168,85,247,0.05));'
            'border-radius:15px;border:1px solid rgba(0,229,255,0.2);'
            'box-shadow:0 0 25px rgba(0,229,255,0.1);">'
            '<div style="font-size:2rem;margin-bottom:8px;">🏛️</div>'
            '<div style="font-family:Orbitron,sans-serif;font-size:1rem;font-weight:800;'
            'letter-spacing:2px;background:linear-gradient(135deg,#00E5FF,#A855F7);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;margin:0;">SARKARI SCHEME</div>'
            '<p style="color:#6B7A8F;font-size:0.7rem;margin:6px 0 0 0;'
            'letter-spacing:1.5px;text-transform:uppercase;">Find Your Scheme</p>'
            '</div>',
            unsafe_allow_html=True,
        )


# ===========================
# LANGUAGE & THEME SWITCH
# ===========================
with st.sidebar:
    st.selectbox(
        "Language / भाषा",
        ["English", "हिंदी"],
        key="_lang_widget",
        on_change=on_language_change,
    )
    lang_choice = st.session_state.lang_choice
    t = get_text(lang_choice)

    st.radio(
        t["theme_label"],
        [t["theme_dark"], t["theme_light"]],
        horizontal=True,
        key="_theme_widget",
        on_change=on_theme_change,
    )
    theme_choice = st.session_state.theme_choice


# ===========================
# COLORS
# ===========================
is_simple_dark = (theme_choice == t["theme_dark"])

if is_simple_dark:
    C = {
        "app_bg": "#0b141a", "sidebar_bg": "#111b21", "card_bg": "#1f2c34",
        "text": "#e9edef", "muted": "#8696a0", "border": "#2a3942",
        "stat_bg1": "#1f2c34", "stat_bg2": "#1f2c34",
        "chip_cat_bg": "#2a3942", "chip_cat_text": "#ffb648",
        "chip_state_bg": "#2a3942", "chip_state_text": "#53bdeb",
        "card_desc": "#8696a0",
        "glow_purple": "#00a884", "glow_pink": "#00a884", "glow_cyan": "#53bdeb",
        "glow_orange": "#ffb648", "glow_green": "#00a884", "glow_red": "#f15c6d",
    }
else:
    C = {
        "app_bg": "#0a0a0f", "sidebar_bg": "rgba(15, 15, 30, 0.95)",
        "card_bg": "rgba(20, 20, 40, 0.85)",
        "text": "#FFFFFF", "muted": "#8080a0",
        "border": "rgba(100, 100, 255, 0.2)",
        "stat_bg1": "rgba(25, 25, 50, 0.8)", "stat_bg2": "rgba(40, 20, 70, 0.8)",
        "chip_cat_bg": "rgba(30, 30, 60, 0.6)", "chip_cat_text": "#FF9933",
        "chip_state_bg": "rgba(30, 30, 60, 0.6)", "chip_state_text": "#00E5FF",
        "card_desc": "#9090b0",
        "glow_purple": "#A855F7", "glow_pink": "#EC4899", "glow_cyan": "#00E5FF",
        "glow_orange": "#FF9933", "glow_green": "#00FF88", "glow_red": "#FF4757",
    }

apply_theme(theme_choice, C, t)


# ===========================
# GLOW TRAIL (inject once)
# ===========================
if "glow_trail_injected" not in st.session_state:
    try:
        glow_trail_js = (
            "<script>(function() {"
            "  const injectGlowTrail = () => {"
            "    const sidebar = document.querySelector('section[data-testid=\"stSidebar\"]');"
            "    if (!sidebar) { setTimeout(injectGlowTrail, 500); return; }"
            "    const labels = sidebar.querySelectorAll('.stRadio label');"
            "    labels.forEach(label => {"
            "      if (!label.querySelector('.glow-trail')) {"
            "        const glow = document.createElement('span');"
            "        glow.className = 'glow-trail';"
            "        label.style.position = 'relative';"
            "        label.insertBefore(glow, label.firstChild);"
            "      }"
            "    });"
            "  };"
            "  injectGlowTrail();"
            "  setTimeout(injectGlowTrail, 1000);"
            "})();</script>"
        )
        components.html(glow_trail_js, height=0)
        st.session_state.glow_trail_injected = True
    except Exception:
        pass


# ===========================
# AUTO-SCRAPING (once per session)
# ===========================
if "auto_scraping_checked" not in st.session_state:
    st.session_state.auto_scraping_checked = True
    try:
        from web_scraper import setup_scheduled_scraping
        setup_scheduled_scraping()
    except Exception as e:
        print(f"[app.py] Auto-scraping setup failed: {type(e).__name__}: {e}")


# ===========================
# CSC VARIABLES
# ===========================
csc_state = t["all"]
csc_search = ""


# ===========================
# SIDEBAR — MODE SELECTION + FORMS
# ===========================
with st.sidebar:
    saved_profile = load_user_profile()
    if saved_profile:
        st.caption(
            f"👤 Saved Profile: Age {saved_profile.get('age', '-')}, "
            f"Income ₹{saved_profile.get('income', '-')}, "
            f"State {saved_profile.get('state', '-')}"
        )
    if IS_MOBILE:
        st.caption("📱 Mobile Mode ON")
    st.divider()

    df = load_schemes()
    all_states = get_all_states(df)
    clean_states = [s for s in all_states if s and s != "All"]
    all_categories = [t["all"]] + get_all_categories(df)

    if st.session_state.get("qa_navigate_to"):
        target_mode = st.session_state.qa_navigate_to
        mode_options = [
            t["mode_form"], t["mode_nl"], t["mode_favorites"], t["mode_reminders"],
            t["mode_history"], t["mode_faq"], t["mode_csc"], t["mode_dashboard"],
            t["mode_settings"], t["mode_notifications"], t["mode_admin"],
            t["mode_assistant"], t["mode_voice_assistant"],
        ]
        if target_mode in mode_options:
            st.session_state["_search_mode_widget"] = target_mode
            st.session_state.scroll_to_results = True
        st.session_state.qa_navigate_to = None

    search_mode = st.radio(
        t["mode_label"],
        [
            t["mode_form"], t["mode_nl"], t["mode_favorites"], t["mode_reminders"],
            t["mode_history"], t["mode_faq"], t["mode_csc"], t["mode_dashboard"],
            t["mode_settings"], t["mode_notifications"], t["mode_admin"],
            t["mode_assistant"], t["mode_voice_assistant"],
        ],
        horizontal=False,
        key="_search_mode_widget",
        on_change=on_mode_change,
    )

    st.divider()

    if search_mode == t["mode_form"]:
        if "sidebar_form_initialized" not in st.session_state:
            profile = load_user_profile()
            st.session_state.sidebar_age = int(profile.get("age", 25) or 25)
            st.session_state.sidebar_income = int(profile.get("income", 200000) or 200000)
            st.session_state.sidebar_state = profile.get("state", "All")
            st.session_state.sidebar_form_initialized = True

        age = st.slider(
            t["age"], min_value=0, max_value=100,
            value=st.session_state.get("sidebar_age", 25),
            key="form_age_slider",
        )
        gender = st.selectbox(
            t["gender"], [t["all"], "Male", "Female"],
            key="form_gender_select",
        )
        occupation = st.selectbox(
            t["occupation"],
            [t["all"], "Student", "Farmer", "Self-employed/Small business",
             "Unorganised worker", "Entrepreneur", "Senior citizen", "Unemployed youth"],
            key="form_occupation_select",
        )
        annual_income = st.number_input(
            t["income"], min_value=0,
            value=st.session_state.get("sidebar_income", 200000),
            step=10000, key="form_income_input",
        )
        social_category = st.selectbox(
            t["category"], [t["all"], "General", "SC", "ST", "OBC", "Minority"],
            key="form_category_select",
        )

        state_display = [t["all"]] + clean_states
        saved_state = st.session_state.get("sidebar_state", "All")
        state_index = state_display.index(saved_state) if saved_state in state_display else 0
        state = st.selectbox(
            t["state"], state_display, index=state_index,
            key="form_state_select",
        )

        category_type = st.selectbox(
            t["scheme_category"], all_categories,
            key="form_category_type_select",
        )

        only_eligible = st.checkbox(
            t["only_eligible"], value=False,
            key="form_only_eligible_checkbox",
        )
        sort_choice_form = st.selectbox(
            t["sort_label"],
            [t["sort_default_form"], t["sort_name"], t["sort_category"], t["sort_state"]],
            key="form_sort_select",
        )

        if st.button(t["search_btn"], use_container_width=True, type="primary",
                     key="form_search_btn"):
            save_user_profile({
                "age": age,
                "income": annual_income,
                "state": state,
            })
            st.session_state.search_params = {
                "age": age,
                "gender": gender,
                "occupation": occupation,
                "annual_income": annual_income,
                "social_category": social_category,
                "state": state,
                "category_type": category_type,
                "only_eligible": only_eligible,
                "sort_choice": sort_choice_form,
            }
            st.session_state.sidebar_age = age
            st.session_state.sidebar_income = annual_income
            st.session_state.sidebar_state = state
            st.session_state.form_submitted = True
            st.session_state.scroll_to_results = True
            st.rerun()

    elif search_mode == t["mode_nl"]:
        sort_choice_nl = st.selectbox(
            t["sort_label"],
            [t["sort_default_nl"], t["sort_name"], t["sort_category"], t["sort_state"]],
            key="nl_sort_select",
        )
        st.session_state.nl_sort_choice = sort_choice_nl

    elif search_mode == t["mode_csc"]:
        try:
            csc_df = get_csc_centers()
            csc_states_list = csc_df["State"].dropna().unique().tolist()
        except Exception:
            csc_states_list = []
        csc_state = st.selectbox(
            t["csc_state_label"], [t["all"]] + csc_states_list,
            key="csc_state_select",
        )
        csc_search = st.text_input(
            t["csc_search_label"],
            placeholder=t["csc_search_placeholder"],
            key="csc_search_input",
        )

    elif search_mode == t["mode_settings"]:
        _render_settings_sidebar(t, clean_states)

    st.divider()
    _render_share_app_sidebar(t)


# ===========================
# SCHEME CARD (FRAGMENT)
# ===========================
@st.fragment
def render_scheme_card(r, t, key_prefix, lang_choice):
    if not isinstance(r, dict):
        return

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
        if status_text:
            extra_badge += (
                f'<span class="chip chip-deadline">📅 {html.escape(status_text)}</span>'
            )

    if "eligible" in r:
        score = calculate_eligible_score(r)
        extra_badge += f'<span class="chip chip-score">🎯 {score}% Match</span>'
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
        f'<p class="card-desc"><b>{html.escape(t["what_is"])}:</b> '
        f'{html.escape(description)}</p>'
        f'<p class="card-desc"><b>{html.escape(t["benefit"])}:</b> '
        f'{html.escape(benefits)}</p>'
        f'</div>'
    )
    st.markdown(card_html, unsafe_allow_html=True)

    widget_key = f"{scheme_name}_{abs(hash((scheme_name, category_type, apply_link)))}"

    col1, col2, col3, col4 = st.columns([1, 2, 2, 1])

    with col1:
        star_icon = "⭐" if is_fav else "☆"
        if st.button(
            star_icon,
            key=f"{key_prefix}_fav_{widget_key}",
            help=t["fav_remove_tooltip"] if is_fav else t["fav_add_tooltip"],
        ):
            favorites_module.toggle_favorite(scheme_name)
            st.toast(
                t["fav_added_toast"] if not is_fav else t["fav_removed_toast"]
            )
            st.rerun(scope="fragment")

    with col2:
        if is_valid_url(apply_link):
            st.link_button(t["app_official_site"], apply_link, use_container_width=True)
        else:
            st.button(
                t["app_official_site"], disabled=True,
                use_container_width=True,
                key=f"{key_prefix}_nolink_{widget_key}",
                help="No valid link available",
            )

    with col3:
        form_link = safe_str(r.get("form_link")) or apply_link
        if is_valid_url(form_link):
            st.link_button(t["app_apply_here"], form_link, use_container_width=True)
        else:
            st.button(
                t["app_apply_here"], disabled=True,
                use_container_width=True,
                key=f"{key_prefix}_noform_{widget_key}",
                help="No valid link available",
            )

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
            idx = status_options.index(current_status) if current_status in status_options else 0
            selected_status = st.selectbox(
                t["app_status_update"],
                status_options,
                index=idx,
                key=f"{key_prefix}_status_{widget_key}",
            )
        with col2:
            if st.button(
                t["app_status_save"],
                key=f"{key_prefix}_save_status_{widget_key}",
            ):
                save_application(scheme_name, selected_status)
                st.toast(t["app_status_updated_toast"])
                st.rerun(scope="fragment")

    if r.get("checks"):
        with st.expander(t["eligibility_breakdown"]):
            for c in r["checks"]:
                icon = "✔" if c.get("passed") else "✘"
                st.write(f"{icon} {html.escape(safe_str(c.get('label')))}")

    with st.expander(t["documents_required_label"]):
        try:
            docs = doc_checklist.get_documents(
                scheme_name, category_type, lang=lang_choice
            )
            for d in docs:
                st.write(f"• {html.escape(safe_str(d))}")
            st.caption(t["documents_disclaimer"])
        except Exception as e:
            st.caption(f"Could not load documents: {safe_str(e)[:80]}")

    with st.expander(t["reminder_label"]):
        existing = reminders_module.get_reminder(scheme_name)
        default_date = None
        if existing and existing.get("date"):
            try:
                default_date = datetime.strptime(existing["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                default_date = None

        reminder_date = st.date_input(
            t["set_reminder_label"],
            value=default_date,
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
            if st.button(
                t["save_reminder_btn"],
                key=f"{key_prefix}_save_rem_{widget_key}",
            ):
                if reminder_date:
                    reminders_module.set_reminder(
                        scheme_name, reminder_date.isoformat(), reminder_note
                    )
                    st.toast(t["reminder_saved_toast"])
                    st.rerun(scope="fragment")
                else:
                    st.warning(t["reminder_date_warning"])
        with rcol2:
            if existing and st.button(
                t["remove_reminder_btn"],
                key=f"{key_prefix}_rm_rem_{widget_key}",
            ):
                reminders_module.remove_reminder(scheme_name)
                st.toast(t["reminder_removed_toast"])
                st.rerun(scope="fragment")

    with st.expander(t["explain_simply_label"]):
        explain_state_key = f"{key_prefix}_explain_{widget_key}"
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button(
                t["explain_simply_btn"],
                key=f"{key_prefix}_explain_btn_{widget_key}",
                use_container_width=True,
                type="primary",
            ):
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
                        score=r.get("score", 0),
                    )
                    st.session_state[explain_state_key] = simple_text
                    progress_text.empty()
                    st.success(t["explain_success"])
                except Exception as e:
                    progress_text.empty()
                    st.error(f"{t['explain_error']} {safe_str(e)[:120]}")
        with col2:
            if st.button(
                t["listen_btn"],
                key=f"{key_prefix}_listen_{widget_key}",
                use_container_width=True,
            ):
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
                        "score": r.get("score", 0),
                    }
                    voice_assistant.read_scheme_details(scheme_data, lang_choice)
                except Exception as e:
                    st.error(f"Could not play audio: {safe_str(e)[:80]}")

        if explain_state_key in st.session_state:
            st.markdown("---")
            st.markdown(f"### {t['explain_simple_title']}")
            st.markdown(
                '<div style="background: rgba(255,255,255,0.05); padding: 15px; '
                'border-radius: 10px; border-left: 4px solid #FF9933;">'
                f'{st.session_state[explain_state_key]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("---")

    st.write("")


# ===========================
# SORT HELPER
# ===========================
def sort_results(results, sort_choice, t):
    if not results:
        return []
    try:
        if sort_choice == t["sort_name"]:
            return sorted(results, key=lambda r: safe_str(r.get("scheme_name", "")).lower())
        if sort_choice == t["sort_category"]:
            return sorted(results, key=lambda r: safe_str(r.get("category_type", "")).lower())
        if sort_choice == t["sort_state"]:
            return sorted(results, key=lambda r: safe_str(r.get("applicable_state", "")).lower())
    except Exception:
        pass
    return results


# ===========================
# HERO BANNER
# ===========================
def _render_hero():
    hero_icon = (
        f'<img src="data:image/png;base64,{LOGO_B64}" width="80" '
        f'style="vertical-align:middle; margin-right:18px; '
        f'filter: drop-shadow(0 0 25px rgba(0,229,255,0.9));">'
        if LOGO_B64 else "🏛️"
    )

    hero_html = (
        '<div style="position:relative;'
        'background:linear-gradient(135deg,rgba(0,229,255,0.15) 0%,'
        'rgba(168,85,247,0.15) 35%,rgba(236,72,153,0.12) 65%,'
        'rgba(255,153,51,0.15) 100%);'
        'background-size:300% 300%;animation:gradientShift 10s ease infinite;'
        'border-radius:25px;padding:50px 35px;margin-bottom:25px;'
        'border:1px solid rgba(0,229,255,0.3);backdrop-filter:blur(15px);'
        'box-shadow:0 10px 50px rgba(0,229,255,0.15),'
        '0 0 80px rgba(168,85,247,0.1),inset 0 0 40px rgba(255,255,255,0.05);'
        'text-align:center;overflow:hidden;">'
        '<div style="position:absolute;top:-50%;left:-50%;width:200%;height:200%;'
        'background:linear-gradient(45deg,transparent,rgba(255,255,255,0.08),transparent);'
        'animation:shimmer 4s ease-in-out infinite;pointer-events:none;"></div>'
        '<div style="display:flex;align-items:center;justify-content:center;'
        'flex-wrap:wrap;gap:15px;margin-bottom:15px;position:relative;z-index:2;">'
        f'{hero_icon}'
        '<h1 style="color:#FFFFFF;font-family:Orbitron,sans-serif;font-size:3rem;'
        'font-weight:800;letter-spacing:3px;margin:0;'
        'text-shadow:0 0 20px rgba(0,229,255,0.6),0 0 40px rgba(168,85,247,0.5),'
        '0 0 80px rgba(236,72,153,0.3);">'
        f'{html.escape(t["title"])}</h1>'
        '</div>'
        '<p style="color:#B0B0D0;font-size:1.2rem;margin:10px 0 0 0;'
        'letter-spacing:1.5px;position:relative;z-index:2;'
        'text-shadow:0 0 10px rgba(0,229,255,0.3);">'
        f'{html.escape(t["subtitle"])}</p>'
        '<div style="display:flex;justify-content:center;flex-wrap:wrap;gap:10px;'
        'margin-top:25px;position:relative;z-index:2;">'
        '<span style="background:linear-gradient(135deg,rgba(0,229,255,0.2),'
        'rgba(0,229,255,0.05));color:#00E5FF;padding:8px 18px;border-radius:25px;'
        'font-size:0.85rem;font-weight:600;border:1px solid rgba(0,229,255,0.5);'
        'box-shadow:0 0 15px rgba(0,229,255,0.2);letter-spacing:0.5px;">'
        '🎯 Smart Matching</span>'
        '<span style="background:linear-gradient(135deg,rgba(168,85,247,0.2),'
        'rgba(168,85,247,0.05));color:#A855F7;padding:8px 18px;border-radius:25px;'
        'font-size:0.85rem;font-weight:600;border:1px solid rgba(168,85,247,0.5);'
        'box-shadow:0 0 15px rgba(168,85,247,0.2);letter-spacing:0.5px;">'
        '🌐 Multi-Language</span>'
        '<span style="background:linear-gradient(135deg,rgba(255,153,51,0.2),'
        'rgba(255,153,51,0.05));color:#FF9933;padding:8px 18px;border-radius:25px;'
        'font-size:0.85rem;font-weight:600;border:1px solid rgba(255,153,51,0.5);'
        'box-shadow:0 0 15px rgba(255,153,51,0.2);letter-spacing:0.5px;">'
        '🤖 AI Assistant</span>'
        '<span style="background:linear-gradient(135deg,rgba(0,255,136,0.2),'
        'rgba(0,255,136,0.05));color:#00FF88;padding:8px 18px;border-radius:25px;'
        'font-size:0.85rem;font-weight:600;border:1px solid rgba(0,255,136,0.5);'
        'box-shadow:0 0 15px rgba(0,255,136,0.2);letter-spacing:0.5px;">'
        '⚡ Real-time Updates</span>'
        '</div>'
        '</div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)


st.markdown(
    "<style>"
    "@keyframes gradientShift {"
    "0%, 100% { background-position: 0% 50%; }"
    "50% { background-position: 100% 50%; }"
    "}"
    "@keyframes shimmer {"
    "0% { transform: translateX(-100%) rotate(45deg); }"
    "100% { transform: translateX(100%) rotate(45deg); }"
    "}"
    "</style>",
    unsafe_allow_html=True,
)

_render_hero()


# ===========================
# DISCLAIMER
# ===========================
st.markdown(
    '<div style="background:linear-gradient(135deg,rgba(255,153,51,0.1),'
    'rgba(255,153,51,0.05));border-left:4px solid #FF9933;border-radius:10px;'
    'padding:15px 20px;margin-bottom:25px;box-shadow:0 0 20px rgba(255,153,51,0.1);">'
    '<p style="color:#FFB648;margin:0;font-size:0.9rem;letter-spacing:0.3px;">'
    f'⚠️ {html.escape(t["disclaimer"])}</p>'
    '</div>',
    unsafe_allow_html=True,
)


# ===========================
# QUICK ACTION CARDS
# ===========================
def _render_quick_actions():
    if search_mode in [
        t["mode_dashboard"], t["mode_admin"],
        t["mode_settings"], t["mode_notifications"],
    ]:
        return

    st.markdown(f"### {t.get('quick_actions_title', 'Quick Actions')}")
    st.caption(t.get("quick_actions_caption", "Choose what you need"))

    st.markdown(
        "<style>"
        ".qa-clickable-wrapper { position: relative; width: 100%;"
        "  border-radius: 15px; overflow: hidden; cursor: pointer; }"
        ".qa-clickable-wrapper iframe { position: absolute !important;"
        "  top: 0 !important; left: 0 !important;"
        "  width: 100% !important; height: 100% !important;"
        "  border: none !important; opacity: 0 !important;"
        "  z-index: 10 !important; cursor: pointer !important; }"
        ".qa-clickable-wrapper > div:not(:last-child) { pointer-events: none; }"
        "@keyframes cardClickCyan {"
        "  0%   { transform: scale(1);    box-shadow: 0 0 15px rgba(0,229,255,0.1); }"
        "  50%  { transform: scale(0.94); box-shadow: 0 0 50px rgba(0,229,255,0.9), 0 0 80px rgba(0,229,255,0.5); }"
        "  100% { transform: scale(1);    box-shadow: 0 0 15px rgba(0,229,255,0.1); } }"
        "@keyframes cardClickPurple {"
        "  0%   { transform: scale(1);    box-shadow: 0 0 15px rgba(168,85,247,0.1); }"
        "  50%  { transform: scale(0.94); box-shadow: 0 0 50px rgba(168,85,247,0.9), 0 0 80px rgba(168,85,247,0.5); }"
        "  100% { transform: scale(1);    box-shadow: 0 0 15px rgba(168,85,247,0.1); } }"
        "@keyframes cardClickGreen {"
        "  0%   { transform: scale(1);    box-shadow: 0 0 15px rgba(0,255,136,0.1); }"
        "  50%  { transform: scale(0.94); box-shadow: 0 0 50px rgba(0,255,136,0.9), 0 0 80px rgba(0,255,136,0.5); }"
        "  100% { transform: scale(1);    box-shadow: 0 0 15px rgba(0,255,136,0.1); } }"
        ".qa-clickable-wrapper:active .qa-card-visual { transform: scale(0.96); transition: transform 0.1s ease; }"
        ".qa-clickable-wrapper.clicked-find .qa-card-visual { animation: cardClickCyan 0.5s cubic-bezier(0.4, 0, 0.2, 1); }"
        ".qa-clickable-wrapper.clicked-search .qa-card-visual { animation: cardClickPurple 0.5s cubic-bezier(0.4, 0, 0.2, 1); }"
        ".qa-clickable-wrapper.clicked-ai .qa-card-visual { animation: cardClickGreen 0.5s cubic-bezier(0.4, 0, 0.2, 1); }"
        ".qa-card-visual { border-radius: 15px; padding: 20px; text-align: center;"
        "  transition: transform 0.25s ease, box-shadow 0.25s ease; }"
        ".qa-clickable-wrapper:hover .qa-card-visual { transform: translateY(-4px) scale(1.02); }"
        "</style>",
        unsafe_allow_html=True,
    )

    qa_col1, qa_col2, qa_col3 = st.columns(3)

    def _qa_card_html(card_id, icon, title, desc, color_rgb):
        return (
            f'<div class="qa-clickable-wrapper" id="{card_id}">'
            f'<div class="qa-card-visual" style="background:linear-gradient(135deg,'
            f'rgba({color_rgb},0.1),rgba({color_rgb},0.02));border:1px solid '
            f'rgba({color_rgb},0.3);box-shadow:0 0 15px rgba({color_rgb},0.1);">'
            f'<div style="font-size:2.5rem;margin-bottom:10px;">{icon}</div>'
            f'<h4 style="color:rgb({color_rgb});margin:0 0 5px 0;'
            f'font-family:\'Orbitron\',sans-serif;">{html.escape(title)}</h4>'
            f'<p style="color:#8696A0;font-size:0.85rem;margin:0;">'
            f'{html.escape(desc)}</p>'
            f'</div></div>'
        )

    def _qa_card_button_js(card_id, mode, click_class):
        safe_mode = "".join(ch for ch in str(mode) if ch.isalnum() or ch == "_")
        return (
            "<style>html, body { margin:0; padding:0; width:100%; height:100%; overflow:hidden; }"
            "button { width: 100%; height: 100%; background: transparent;"
            "border: none; cursor: pointer; padding: 0; margin: 0; }</style>"
            "<button onclick=\"(function(){"
            "try {"
            f"var parentDoc = window.parent.document;"
            f"var card = parentDoc.getElementById('{card_id}');"
            f"if (card) {{ card.classList.add('{click_class}'); }}"
            "setTimeout(function() {"
            "var url = new URL(window.parent.location.href);"
            f"url.searchParams.set('qa_mode', '{safe_mode}');"
            "window.parent.location.href = url.toString();"
            "}, 450);"
            "} catch(e) { console.log('click err', e); }"
            "})()\"></button>"
        )

    with qa_col1:
        st.markdown(
            _qa_card_html(
                "qa-card-find", "🎯",
                t.get("qa_find_schemes_title", "Find Schemes"),
                t.get("qa_find_schemes_desc", "Search schemes by eligibility"),
                "0,229,255",
            ),
            unsafe_allow_html=True,
        )
        components.html(
            _qa_card_button_js("qa-card-find", "form", "clicked-find"),
            height=140,
        )

    with qa_col2:
        st.markdown(
            _qa_card_html(
                "qa-card-search", "🔍",
                t.get("qa_smart_search_title", "Smart Search"),
                t.get("qa_smart_search_desc", "Search in your own words"),
                "168,85,247",
            ),
            unsafe_allow_html=True,
        )
        components.html(
            _qa_card_button_js("qa-card-search", "nl", "clicked-search"),
            height=140,
        )

    with qa_col3:
        st.markdown(
            _qa_card_html(
                "qa-card-ai", "🤖",
                t.get("qa_ai_assistant_title", "AI Assistant"),
                t.get("qa_ai_assistant_desc", "Chat directly with AI"),
                "0,255,136",
            ),
            unsafe_allow_html=True,
        )
        components.html(
            _qa_card_button_js("qa-card-ai", "assistant", "clicked-ai"),
            height=140,
        )

    st.write("")
    st.divider()


# ===========================
# NOTIFICATIONS
# ===========================
def show_notifications():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['notif_title']}")

    all_reminders = reminders_module.load_reminders()
    if all_reminders:
        st.markdown(f"#### {t['notif_reminders']}")
        for scheme_name, info in all_reminders.items():
            days = reminders_module.days_remaining(info.get("date", ""))
            if days is None:
                continue
            if days < 0:
                st.error(f"❌ **{scheme_name}** - {t['notif_deadline_expired']} {info['date']}")
            elif days <= 7:
                st.warning(
                    f"⚠️ **{scheme_name}** - "
                    f"{t['notif_due_in_days'].format(days=days)} ({info['date']})"
                )
            else:
                st.info(
                    f"📅 **{scheme_name}** - "
                    f"{t['notif_due_in_days'].format(days=days)} ({info['date']})"
                )
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
                if days_left is not None and status_text and days_left <= 7:
                    st.warning(f"⚠️ **{safe_str(row['scheme_name'])}** - {status_text}")


# ===========================
# MODE RENDERERS
# ===========================
_render_quick_actions()

df = load_schemes()


def _render_eligibility_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)

    # If results already exist in session, show them
    if st.session_state.get("form_submitted", False):
        results = st.session_state.get("form_results", [])
        eligible_count = st.session_state.get("form_eligible_count", 0)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                f"<div class='stat-box'><div class='stat-number'>{len(results)}</div>"
                f"<div class='stat-label'>{t['total_shown']}</div></div>",
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown(
                f"<div class='stat-box'><div class='stat-number'>{eligible_count}</div>"
                f"<div class='stat-label'>{t['eligible_label']}</div></div>",
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                f"<div class='stat-box'><div class='stat-number'>"
                f"{len(results) - eligible_count}</div>"
                f"<div class='stat-label'>{t['not_eligible_label']}</div></div>",
                unsafe_allow_html=True,
            )

        st.write("")
        col_clear1, col_clear2 = st.columns([1, 5])
        with col_clear1:
            if st.button(t["clear_results_btn"], use_container_width=True,
                         key="clear_form_results_btn"):
                st.session_state.form_results = []
                st.session_state.form_eligible_count = 0
                st.session_state.form_submitted = False
                st.session_state.search_params = {}
                st.rerun()

        if results:
            try:
                pdf_bytes = pdf_export.build_pdf(
                    results, profile=st.session_state.get("form_profile")
                )
                st.download_button(
                    t["pdf_download_btn"],
                    data=pdf_bytes,
                    file_name="sarkari_scheme_report.pdf",
                    mime="application/pdf",
                    key="form_pdf_download",
                )
            except Exception as e:
                st.warning(f"Could not build PDF: {safe_str(e)[:80]}")

            st.write("")
            items_per_page = get_items_per_page()
            total_results = len(results)

            if IS_MOBILE and total_results > items_per_page:
                for r in results[:items_per_page]:
                    render_scheme_card(r, t, "form", lang_choice)

                if "show_more_form" not in st.session_state:
                    st.session_state.show_more_form = False

                if st.session_state.show_more_form:
                    for r in results[items_per_page:]:
                        render_scheme_card(r, t, "form", lang_choice)
                else:
                    if st.button(t["load_more_btn"], use_container_width=True,
                                 key="form_load_more_btn"):
                        st.session_state.show_more_form = True
                        st.rerun()
            else:
                for r in results:
                    render_scheme_card(r, t, "form", lang_choice)
        else:
            st.info(t["no_results"])

    else:
        # No submission yet — just show hint
        st.info(t["hint"])


# ===========================
# FORM SUBMISSION HANDLER (runs once after sidebar button click)
# ===========================
def _handle_form_submission():
    """Agar form_submitted=True hai lekin results nahi hain, to compute karo."""
    if not st.session_state.get("form_submitted", False):
        return
    if st.session_state.get("form_results"):
        return  # Already computed

    params = st.session_state.get("search_params", {})
    if not params:
        return

    with st.spinner(t["searching_spinner"]):
        gender_val = "All" if params.get("gender") == t["all"] else params.get("gender", "All")
        category_val = "All" if params.get("social_category") == t["all"] else params.get("social_category", "All")
        occupation_val = "All" if params.get("occupation") == t["all"] else params.get("occupation", "All")
        state_val = "All" if params.get("state") == t["all"] else params.get("state", "All")
        scheme_cat_val = "All" if params.get("category_type") == t["all"] else params.get("category_type", "All")

        try:
            results = match_schemes(
                df,
                age=params.get("age", 25),
                annual_income=params.get("annual_income", 0),
                gender=gender_val,
                social_category=category_val,
                occupation=occupation_val,
                state=state_val,
                category_type=scheme_cat_val,
                only_eligible=params.get("only_eligible", False),
            )
            results = sort_results(results, params.get("sort_choice", t["sort_default_form"]), t)
            eligible_count = sum(1 for r in results if r.get("eligible"))
        except Exception as e:
            st.error(f"Search error: {safe_str(e)[:150]}")
            results = []
            eligible_count = 0

        try:
            history_module.save_entry({
                "mode": "form",
                "age": params.get("age", 25),
                "state": state_val,
                "total": len(results),
                "eligible": eligible_count,
            })
        except Exception:
            pass

        st.session_state.form_results = results
        st.session_state.form_eligible_count = eligible_count
        st.session_state.form_profile = {
            "Age": params.get("age", 25),
            "Gender": gender_val,
            "Annual Income": params.get("annual_income", 0),
            "State": state_val,
            "Category": category_val,
        }


_handle_form_submission()


def _render_nl_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)

    def _select_suggestion(term):
        st.session_state.nl_query = term

    if st.session_state.get("voice_query_from_url"):
        st.session_state.nl_query = st.session_state.voice_query_from_url
        st.session_state.voice_query_from_url = None

    query = st.text_input(
        t["mode_nl"],
        placeholder=t["nl_placeholder"],
        label_visibility="collapsed",
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

    nl_submitted = st.button(t["nl_search_btn"], type="primary", key="nl_search_btn")
    st.caption(t["nl_note"])
    st.write("")

    sort_choice_nl = st.session_state.get("nl_sort_choice", t["sort_default_nl"])

    if query.strip():
        with st.spinner("🔍 Searching..."):
            top_n = get_search_results_count()
            results = search_schemes(df, query, top_n=top_n)
            results = sort_results(results, sort_choice_nl, t)

        if nl_submitted:
            try:
                history_module.save_entry({
                    "mode": "nl", "query": query.strip(), "total": len(results),
                })
            except Exception:
                pass

        if results:
            st.success(f"{len(results)} {t['nl_matches_found']}")
            try:
                pdf_bytes = pdf_export.build_pdf(
                    results, profile={"Search Query": query.strip()}
                )
                st.download_button(
                    t["pdf_download_btn"], data=pdf_bytes,
                    file_name="sarkari_scheme_report.pdf",
                    mime="application/pdf",
                    key="nl_pdf_download",
                )
            except Exception as e:
                st.warning(f"Could not build PDF: {safe_str(e)[:80]}")

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
                    if st.button(t["load_more_btn"], use_container_width=True,
                                 key="nl_load_more_btn"):
                        st.session_state.show_more_nl = True
                        st.rerun()
            else:
                for r in results:
                    render_scheme_card(r, t, "nl", lang_choice)
        else:
            st.info(t["nl_no_results"])
    else:
        st.info(t["nl_hint"])


def _render_favorites_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['favorites_title']}")
    fav_names = favorites_module.load_favorites()

    if not fav_names:
        st.info(t["favorites_empty"])
        return

    fav_rows = df[df["scheme_name"].isin(fav_names)].sort_values("scheme_name")
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


def _render_reminders_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['reminders_title']}")
    st.caption(t["reminders_disclaimer"])

    all_reminders = reminders_module.load_reminders()
    if not all_reminders:
        st.info(t["reminders_empty"])
        return

    for scheme_name, info in sorted(
        all_reminders.items(), key=lambda kv: kv[1].get("date", "")
    ):
        days = reminders_module.days_remaining(info.get("date", ""))
        if days is None:
            continue

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

        note_html = (
            f'<p class="card-desc">{html.escape(info["note"])}</p>'
            if info.get("note") else ""
        )

        reminder_html = (
            '<div class="scheme-card">'
            f'<span class="chip" style="background-color:rgba(255,71,87,0.2); '
            f'color:{status_color}; border:1px solid {status_color};">'
            f'{html.escape(status_text)}</span>'
            f'<h4 style="margin:8px 0 4px 0;">{html.escape(scheme_name)}</h4>'
            f'<p class="card-desc"><b>{html.escape(t["set_reminder_label"])}:</b> '
            f'{html.escape(info["date"])}</p>'
            f'{note_html}</div>'
        )
        st.markdown(reminder_html, unsafe_allow_html=True)

        if st.button(
            t["remove_reminder_btn"],
            key=f"rem_list_remove_{scheme_name}",
        ):
            reminders_module.remove_reminder(scheme_name)
            st.toast(t["reminder_removed_toast"])
            st.rerun()
        st.write("")


def _render_history_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['history_title']}")
    entries = history_module.load_history()

    if not entries:
        st.info(t["history_empty"])
        return

    if st.button(t["history_clear_btn"], key="clear_history_btn"):
        history_module.clear_history()
        st.toast("🗑️ History Cleared")
        st.rerun()

    st.write("")
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("mode") == "form":
            summary = t["history_form_summary"].format(
                age=entry.get("age", "-"),
                state=entry.get("state", "-"),
                eligible=entry.get("eligible", 0),
                total=entry.get("total", 0),
            )
        else:
            summary = t["history_nl_summary"].format(
                query=entry.get("query", ""),
                total=entry.get("total", 0),
            )

        st.markdown(
            f'<div class="scheme-card"><p style="color:{C["muted"]}; '
            f'font-size:12px; margin:0 0 6px 0;">'
            f'{html.escape(entry.get("timestamp", ""))}</p>'
            f'<p style="margin:0;" class="card-desc">{html.escape(summary)}</p>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_faq_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['faq_title']}")
    try:
        for question, answer in faq_module.get_faqs(lang_choice):
            with st.expander(question):
                st.write(answer)
    except Exception as e:
        st.error(f"Could not load FAQs: {safe_str(e)[:120]}")


def _render_csc_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.markdown(f"### {t['csc_title']}")
    st.caption(
        "🗺️ Currently showing CSC centers in **Bhopal** only. "
        "Apna area ya pincode daaliye, hum aapke sabse nazdeek CSC center dhoondhenge."
    )

    st.markdown("#### 📍 Find Nearest CSC Center in Bhopal")
    st.caption(
        "Apna area, colony, ya pincode daaliye "
        "(e.g. 'MP Nagar', '462011', 'Kolar Road')."
    )

    col_addr, col_btn = st.columns([4, 1])
    with col_addr:
        user_address = st.text_input(
            "Address / Area / Pincode (Bhopal)",
            placeholder="e.g. 'MP Nagar' or '462011' or 'Kolar Road'",
            key="csc_user_address_input",
            label_visibility="collapsed",
        )
    with col_btn:
        search_nearby = st.button(
            "🔍 Search", use_container_width=True, type="primary",
            key="csc_nearby_btn",
        )

    if search_nearby and user_address and user_address.strip():
        with st.spinner("🔍 Aapke aas-paas ke CSC centers dhoondh rahe hain..."):
            try:
                user_lat, user_lon, nearest_df, source = find_nearest_csc(
                    user_address, max_results=10
                )
            except Exception as e:
                st.error(f"Error: {safe_str(e)[:120]}")
                user_lat, user_lon, nearest_df = None, None, pd.DataFrame()

        if user_lat is not None and not nearest_df.empty:
            st.success(f"✅ Aapke aas-paas ke {len(nearest_df)} CSC centers mile!")
            st.caption(
                f"📍 Aapki location: ({user_lat:.4f}, {user_lon:.4f}) — "
                f"matched via **{html.escape(source)}**"
            )
            for _, row in nearest_df.iterrows():
                distance_val = row.get("Distance (km)", None)
                distance_text = (
                    f"{distance_val:.1f} km" if distance_val is not None
                    else "Distance N/A"
                )
                gmaps_link = (
                    f"https://www.google.com/maps/dir/?api=1&destination="
                    f"{row['Latitude']},{row['Longitude']}"
                )
                st.markdown(
                    '<div class="scheme-card">'
                    '<span class="chip chip-state" '
                    'style="background:rgba(0,229,255,0.15); color:#00E5FF; '
                    'border:1px solid #00E5FF;">'
                    f'📍 {html.escape(distance_text)}</span>'
                    f'<h4 style="margin:8px 0 4px 0;">'
                    f'{html.escape(safe_str(row.get("Name")))}</h4>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_address_label"])}:'
                    f'</b> {html.escape(safe_str(row.get("Address")))}</p>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_district_label"])}:'
                    f'</b> {html.escape(safe_str(row.get("District")))}, '
                    f'{html.escape(safe_str(row.get("State")))}</p>'
                    f'<p class="card-desc"><b>{html.escape(t["csc_phone_label"])}:</b> '
                    f'{html.escape(safe_str(row.get("Phone")))}</p>'
                    f'<p class="card-desc">'
                    f'<a href="{gmaps_link}" target="_blank" '
                    f'style="color:#00E5FF;">🗺️ Get Directions on Google Maps</a></p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.warning(
                "⚠️ Aapka address locate nahi kar paye. "
                "Kripya pincode ke saath try karein "
                "(jaise '462011' ya 'MP Nagar, Bhopal')."
            )
    elif search_nearby and not user_address.strip():
        st.info("Kripya pehle apna area ya pincode daalein.")

    st.divider()
    st.markdown("#### 🗺️ All CSC Centers in Bhopal")
    csc_df = get_csc_centers()
    st.write(f"**{len(csc_df)}** CSC centers found in Bhopal")
    st.write("")

    if len(csc_df) > 0:
        for _, row in csc_df.iterrows():
            gmaps_link = (
                f"https://www.google.com/maps/search/?api=1&query="
                f"{row['Latitude']},{row['Longitude']}"
            )
            st.markdown(
                '<div class="scheme-card">'
                f'<h4 style="margin:0 0 4px 0;">'
                f'{html.escape(safe_str(row["Name"]))}</h4>'
                f'<p class="card-desc"><b>{html.escape(t["csc_address_label"])}:'
                f'</b> {html.escape(safe_str(row["Address"]))}</p>'
                f'<p class="card-desc"><b>{html.escape(t["csc_district_label"])}:'
                f'</b> {html.escape(safe_str(row["District"]))}</p>'
                f'<p class="card-desc"><b>{html.escape(t["csc_phone_label"])}:</b> '
                f'{html.escape(safe_str(row["Phone"]))}</p>'
                f'<p class="card-desc">'
                f'<a href="{gmaps_link}" target="_blank" '
                f'style="color:#00E5FF;">🗺️ View on Google Maps</a></p>'
                '</div>',
                unsafe_allow_html=True,
            )
    else:
        st.info("No CSC centers found.")


def _render_dashboard_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)

    def get_urgent_schemes(df_local, days_threshold=30):
        urgent = []
        if df_local is None or df_local.empty:
            return urgent
        for _, row in df_local.iterrows():
            deadline = row.get("deadline")
            if not deadline or pd.isna(deadline):
                continue
            days_left, status_text, color = get_deadline_status(deadline)
            if days_left is not None and days_left <= days_threshold and status_text:
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

    render_dashboard(df, get_urgent_schemes, C, is_light=not is_simple_dark)


def _render_admin_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    render_admin_panel()


def _render_assistant_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    from ai_chatbot import render_ai_assistant
    render_ai_assistant(
        render_scheme_card=render_scheme_card,
        sort_results=sort_results,
        t=t,
    )


def _render_voice_assistant_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    try:
        voice_assistant.render_voice_assistant(
            df=df, t=t, lang_choice=lang_choice,
            search_schemes_fn=search_schemes,
            sort_results_fn=sort_results,
            render_scheme_card_fn=render_scheme_card,
            history_module=history_module,
        )
    except Exception as e:
        st.error(f"⚠️ Voice Assistant error: {safe_str(e)[:150]}")
        with st.expander("Debug info"):
            st.exception(e)


def _render_settings_mode():
    st.markdown('<div class="mode-content-anchor"></div>', unsafe_allow_html=True)
    st.info(t["settings_use_sidebar"])


# ===========================
# MODE ROUTER
# ===========================
try:
    _MODE_ROUTER = {
        t["mode_dashboard"]: _render_dashboard_mode,
        t["mode_notifications"]: show_notifications,
        t["mode_admin"]: _render_admin_mode,
        t["mode_assistant"]: _render_assistant_mode,
        t["mode_voice_assistant"]: _render_voice_assistant_mode,
        t["mode_settings"]: _render_settings_mode,
        t["mode_form"]: _render_eligibility_mode,
        t["mode_nl"]: _render_nl_mode,
        t["mode_favorites"]: _render_favorites_mode,
        t["mode_reminders"]: _render_reminders_mode,
        t["mode_history"]: _render_history_mode,
        t["mode_faq"]: _render_faq_mode,
        t["mode_csc"]: _render_csc_mode,
    }
    handler = _MODE_ROUTER.get(search_mode)
    if handler is not None:
        handler()
    else:
        st.warning(f"⚠️ Unknown mode: {search_mode}")
except Exception as e:
    st.error(f"⚠️ Mode error: {safe_str(e)[:150]}")
    with st.expander("Debug info"):
        st.exception(e)


# ===========================
# SCROLL TRIGGER
# ===========================
if _should_scroll_this_run:
    try:
        components.html(
            "<script>"
            "(function() {"
            "  function doScroll() {"
            "    try {"
            "      var parentDoc = window.parent.document;"
            "      var parentWin = window.parent;"
            "      var anchor = parentDoc.querySelector('.mode-content-anchor');"
            "      if (anchor) {"
            "        anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });"
            "        setTimeout(function() {"
            "          try { parentWin.scrollBy({ top: -220, behavior: 'smooth' }); } catch(e) {}"
            "        }, 100);"
            "        return true;"
            "      }"
            "      var statBox = parentDoc.querySelector('.stat-box');"
            "      if (statBox) {"
            "        statBox.scrollIntoView({ behavior: 'smooth', block: 'start' });"
            "        return true;"
            "      }"
            "      var mainContainer = parentDoc.querySelector('.main')"
            "                       || parentDoc.querySelector('section.main');"
            "      if (mainContainer) {"
            "        mainContainer.scrollTo({ top: mainContainer.scrollHeight, behavior: 'smooth' });"
            "        return true;"
            "      }"
            "    } catch(e) { console.log('[scroll] Error:', e); }"
            "    return false;"
            "  }"
            "  setTimeout(doScroll, 300);"
            "  setTimeout(doScroll, 700);"
            "  setTimeout(doScroll, 1200);"
            "  setTimeout(doScroll, 2000);"
            "})();</script>",
            height=0,
        )
    except Exception:
        pass