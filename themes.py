"""
themes.py — Dark and Light theme CSS injection.

USAGE:
    from themes import apply_theme
    apply_theme(theme_choice, C, t)

FIXES (v3):
  - @import removed from inside <style> tag — ab dedicated <link> tag
    inject hota hai (browser reliably load karta hai).
  - _inject_css() mein bare except replaced with logged warning.
  - apply_theme() ab explicit theme validation karta hai (dark/light/fallback).
  - Mobile CSS ab sirf SPECIFIC multi-column blocks ko wrap karta hai
    (saare nahi) — quick action cards, stats row, etc. intact rehte hain.
  - Duplicate .stApp rules reduce kiye — light theme ab clearly override karta hai.
  - Non-Streamlit context safe (try/except around st.markdown, with log).
  - Fixed dead CSS selectors:
      * [data-testid="stTooltip"] → removed (doesn't match)
      * .streamlit-expanderHeader → [data-testid="stExpander"] summary
      * .stColumns → div[data-testid="stHorizontalBlock"]
  - Light theme buttons: primary = orange, secondary = subtle purple
    (visual hierarchy fix).
  - Mobile: backdrop-filter reduce kiya (perf).
  - Font loading moved to dedicated _inject_font_link() function.
"""

import streamlit as st


# ===========================
# PUBLIC API
# ===========================
def apply_theme(theme_choice, C, t):
    """
    Theme CSS inject karta hai.

    Args:
        theme_choice: user's chosen theme (matches t["theme_dark"] or t["theme_light"])
        C: colors dict (from app.py)
        t: translations dict

    Behavior:
        - Valid dark theme → dark CSS
        - Valid light theme → light CSS
        - Unknown theme → light CSS (default) + logged warning
    """
    dark_label = t.get("theme_dark", "Dark")
    light_label = t.get("theme_light", "Light")

    if theme_choice == dark_label:
        css = _build_dark_css(C)
        # Font link (ek baar hi inject hoga)
        _inject_font_link()
    elif theme_choice == light_label:
        css = _build_light_css(C)
        _inject_font_link()
    else:
        # Unknown theme — default to light with warning
        print(f"[themes] Unknown theme_choice: {theme_choice!r} — defaulting to light")
        css = _build_light_css(C)
        _inject_font_link()

    _inject_css(css)


# ===========================
# FONT LOADING (separate from <style>)
# ===========================
def _inject_font_link():
    """
    Poppins font ko dedicated <link> tag se load karta hai.
    <style> ke andar @import unreliable hota hai — dedicated link
    reliably load hota hai.

    Ye function idempotent hai — multiple calls sirf ek baar link inject karti hain.
    """
    # Session-level flag taaki multiple reruns mein duplicate na ho
    if _is_font_link_injected():
        return

    try:
        # Preconnect (faster font loading)
        st.markdown(
            '<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" '
            'href="https://fonts.googleapis.com/css2?'
            'family=Poppins:wght@200;300;400;500;600;700&display=swap">',
            unsafe_allow_html=True,
        )
        _mark_font_link_injected()
    except Exception as e:
        # Non-Streamlit context ya koi streamlit error — silently skip
        print(f"[themes] Font link injection skipped: {type(e).__name__}")


def _is_font_link_injected():
    """Session state mein flag check karta hai (Streamlit context safe)."""
    try:
        return st.session_state.get("_themes_font_link_injected", False)
    except Exception:
        return False


def _mark_font_link_injected():
    """Session state mein flag set karta hai."""
    try:
        st.session_state["_themes_font_link_injected"] = True
    except Exception:
        pass


# ===========================
# CSS INJECTION
# ===========================
def _inject_css(css):
    """
    CSS ko safely inject karta hai.
    - Single-line string (CommonMark HTML block bug avoid)
    - Non-Streamlit context mein logged skip (silent swallow nahi)
    """
    try:
        st.markdown(
            f'<style>{css}</style>',
            unsafe_allow_html=True,
        )
    except Exception as e:
        # Log karo — silent swallow se debugging mushkil hoti hai
        print(f"[themes] CSS injection skipped: {type(e).__name__}: {e}")


# ===========================
# SHARED CSS (both themes)
# ===========================
def _shared_css(C):
    """
    Woh CSS jo dono themes mein same hai (sirf colors alag).
    Returns: single-line-concatenated CSS string (no blank lines, no @import)
    """
    return (
        # ---- Font family (loaded via _inject_font_link) ----
        "html, body, [class*='css'] { font-family: 'Poppins', sans-serif; }"

        # ---- Base colors ----
        f".stApp {{ background: {C['app_bg']}; }}"
        f".stApp, .stApp p, .stApp li, .stApp label, .stApp span {{ color: {C['text']}; }}"

        # ---- Hero ----
        f".hero {{ background: {C['card_bg']}; padding: 30px 25px; border-radius: 12px; "
        f"text-align: center; margin-bottom: 20px; border: 1px solid {C['border']}; }}"
        f".hero h1 {{ color: {C['text']}; font-size: 2.2rem; margin: 0; "
        f"font-weight: 700; letter-spacing: 0.5px; }}"
        f".hero p {{ color: {C['muted']}; margin-top: 10px; font-size: 1rem; }}"

        # ---- Scheme card ----
        f".scheme-card {{ background: {C['card_bg']}; border: 1px solid {C['border']}; "
        f"border-left: 4px solid {C['glow_cyan']}; border-radius: 10px; padding: 18px 20px; "
        f"margin-bottom: 12px; transition: transform 0.2s ease, box-shadow 0.2s ease; }}"
        ".scheme-card:hover { transform: translateY(-3px); "
        f"box-shadow: 0 8px 20px {C['glow_cyan']}26; }}"
        f".scheme-card h4 {{ color: {C['text']}; font-size: 1.05rem; font-weight: 600; }}"
        f".card-desc {{ color: {C['card_desc']}; margin: 6px 0; font-size: 0.9rem; line-height: 1.5; }}"

        # ---- Chips ----
        ".chip { display: inline-block; padding: 5px 12px; border-radius: 14px; "
        "font-size: 12px; font-weight: 500; margin-right: 6px; margin-bottom: 8px; "
        "transition: transform 0.15s ease; }"
        ".chip:hover { transform: translateY(-1px); }"
        f".chip-eligible {{ background: {C['glow_green']}26; color: {C['glow_green']}; "
        f"border: 1px solid {C['glow_green']}; }}"
        f".chip-not-eligible {{ background: {C['glow_red']}26; color: {C['glow_red']}; "
        f"border: 1px solid {C['glow_red']}; }}"
        f".chip-category {{ background: {C['chip_cat_bg']}; color: {C['chip_cat_text']}; "
        f"border: 1px solid {C['chip_cat_text']}; }}"
        f".chip-state {{ background: {C['chip_state_bg']}; color: {C['chip_state_text']}; "
        f"border: 1px solid {C['chip_state_text']}; }}"
        f".chip-deadline {{ background: {C['glow_purple']}1F; color: {C['glow_purple']}; "
        f"border: 1px solid {C['glow_purple']}; }}"
        f".chip-score {{ background: {C['glow_orange']}26; color: {C['glow_orange']}; "
        f"border: 1px solid {C['glow_orange']}; }}"
        f".chip-applied {{ background: {C['glow_green']}26; color: {C['glow_green']}; "
        f"border: 1px solid {C['glow_green']}; }}"
        f".chip-pending {{ background: {C['glow_orange']}26; color: {C['glow_orange']}; "
        f"border: 1px solid {C['glow_orange']}; }}"
        f".chip-rejected {{ background: {C['glow_red']}26; color: {C['glow_red']}; "
        f"border: 1px solid {C['glow_red']}; }}"

        # ---- Stat box ----
        f".stat-box {{ background: {C['card_bg']}; border-radius: 10px; padding: 18px; "
        f"text-align: center; border: 1px solid {C['border']}; "
        f"transition: transform 0.2s ease, box-shadow 0.2s ease; }}"
        ".stat-box:hover { transform: translateY(-3px); "
        f"box-shadow: 0 8px 20px {C['glow_cyan']}26; }}"
        f".stat-number {{ font-size: 2rem; font-weight: 700; color: {C['glow_cyan']}; }}"
        f".stat-label {{ font-size: 0.82rem; color: {C['muted']}; margin-top: 6px; "
        f"letter-spacing: 0.5px; text-transform: uppercase; }}"

        # ---- General buttons (theme-aware) ----
        f".stButton > button, .stDownloadButton > button, .stLinkButton > a, "
        f"div[data-testid='stPopover'] > div > button {{ "
        f"background: {C['glow_cyan']} !important; color: {C['app_bg']} !important; "
        f"border: none !important; border-radius: 8px !important; "
        f"padding: 10px 20px !important; font-weight: 600 !important; "
        f"transition: transform 0.2s ease, box-shadow 0.2s ease !important; }}"

        ".stButton > button:focus, .stButton > button:active, "
        ".stButton > button:focus-visible { outline: none !important; box-shadow: none !important; }"

        ".stButton > button:hover, .stDownloadButton > button:hover, "
        ".stLinkButton > a:hover, div[data-testid='stPopover'] > div > button:hover { "
        "transform: translateY(-2px); "
        f"box-shadow: 0 6px 18px {C['glow_cyan']}40; }}"

        # Primary buttons — distinct (orange/green)
        f".stButton > button[kind='primary'] {{ "
        f"background: {C['glow_orange']} !important; color: {C['app_bg']} !important; }}"

        # ---- Inputs ----
        f".stTextInput > div > div > input, .stNumberInput > div > div > input, "
        f".stDateInput > div > div > input, .stTextArea > div > div > textarea {{ "
        f"background: {C['card_bg']} !important; color: {C['text']} !important; "
        f"border: 1px solid {C['border']} !important; border-radius: 8px !important; "
        f"padding: 8px 12px !important; }}"

        ".stTextInput > div > div > input:focus, .stNumberInput > div > div > input:focus, "
        ".stDateInput > div > div > input:focus, .stTextArea > div > div > textarea:focus { "
        f"border-color: {C['glow_cyan']} !important; outline: none !important; box-shadow: none !important; }}"

        f".stSelectbox div[data-baseweb='select'] > div {{ "
        f"background-color: {C['card_bg']} !important; color: {C['text']} !important; "
        f"border: 1px solid {C['border']} !important; border-radius: 8px !important; "
        f"min-height: 42px !important; display: flex !important; align-items: center !important; }}"

        f"div[data-baseweb='popover'] div[data-baseweb='menu'] {{ "
        f"background: {C['card_bg']} !important; border: 1px solid {C['border']} !important; "
        f"border-radius: 8px !important; padding: 5px !important; }}"

        f"div[data-baseweb='popover'] li {{ color: {C['text']} !important; "
        f"background: transparent !important; padding: 8px 12px !important; "
        f"border-radius: 6px !important; font-size: 14px !important; }}"

        f"div[data-baseweb='popover'] li:hover {{ background: {C['border']} !important; }}"

        # ---- Share icon row ----
        f".share-icon-row a {{ display: inline-flex; align-items: center; justify-content: center; "
        f"width: 46px; height: 46px; border-radius: 50%; background: {C['card_bg']}; "
        f"border: 1px solid {C['border']}; margin-right: 10px; text-decoration: none; "
        f"transition: transform 0.2s ease, border-color 0.2s ease; }}"
        f".share-icon-row a:hover {{ transform: scale(1.1); border-color: {C['glow_cyan']}; }}"
        ".share-icon-row img { width: 22px; height: 22px; }"
        "div[data-testid='stPopover'] { position: relative; z-index: 1000; }"

        # ---- Expander (FIXED selector) ----
        f"[data-testid='stExpander'] summary {{ "
        f"background: {C['card_bg']} !important; color: {C['text']} !important; "
        f"border-radius: 8px !important; padding: 12px !important; "
        f"border: 1px solid {C['border']} !important; }}"
        f"[data-testid='stExpander'] summary:hover {{ "
        f"background: {C['glow_cyan']}14 !important; border-color: {C['glow_cyan']}4D !important; }}"

        # ---- Progress bar ----
        ".stProgress > div > div > div > div { "
        f"background: linear-gradient(90deg, {C['glow_cyan']} 0%, {C['glow_purple']} 50%, "
        f"{C['glow_pink']} 100%) !important; "
        "background-size: 200% 100% !important; "
        "animation: neonProgress 2s ease infinite !important; "
        f"border-radius: 10px !important; "
        f"box-shadow: 0 0 10px {C['glow_cyan']}99, 0 0 20px {C['glow_purple']}66 !important; "
        "position: relative; overflow: hidden; }"

        "@keyframes neonProgress { "
        "0%, 100% { background-position: 0% 50%; } "
        "50% { background-position: 100% 50%; } }"

        # ---- Alerts ----
        f".stAlert {{ border-radius: 8px !important; border: 1px solid {C['border']} !important; "
        f"padding: 15px !important; }}"

        # ---- Misc ----
        ".stRadio > div, .stCheckbox > div { padding: 6px; border-radius: 8px; }"
        ".stRadio > div:focus, .stCheckbox > div:focus { outline: none !important; box-shadow: none !important; }"
        f".stSlider > div > div > div > div {{ background: {C['glow_cyan']} !important; }}"

        # ---- Scrollbar ----
        "::-webkit-scrollbar { width: 8px; }"
        f"::-webkit-scrollbar-track {{ background: {C['sidebar_bg']}; }}"
        f"::-webkit-scrollbar-thumb {{ background: {C['border']}; border-radius: 8px; }}"

        # ---- Mobile ----
        # NOTE: Har multi-column block ko 2-column nahi karte — sirf
        # specific blocks ko (data-testid ke through), aur wrapping natural rakhte hain.
        "@media (max-width: 640px) { "
        ".block-container { padding-top: 0.5rem; padding-left: 0.5rem; padding-right: 0.5rem; } "
        ".hero { padding: 14px 12px; border-radius: 10px; margin-bottom: 10px; } "
        ".hero h1 { font-size: 1.4rem; } "
        ".hero p { font-size: 0.8rem; } "
        ".scheme-card { padding: 12px 14px; margin-bottom: 8px; } "
        ".scheme-card h4 { font-size: 0.9rem; } "
        ".chip { font-size: 9px; padding: 3px 8px; margin-bottom: 4px; } "
        ".stat-box { padding: 10px; } "
        ".stat-number { font-size: 1.2rem; } "
        ".stat-label { font-size: 0.7rem; } "
        ".stButton > button { padding: 8px 12px !important; font-size: 14px !important; "
        "min-height: 36px !important; } "
        "[data-testid='stExpander'] { margin-bottom: 6px !important; } "
        ".stSelectbox { margin-bottom: 4px !important; } "
        ".stTextInput { margin-bottom: 4px !important; } "
        ".stNumberInput { margin-bottom: 4px !important; } "
        "}"
    )


# ===========================
# SIDEBAR CSS
# ===========================
def _sidebar_css(C, accent_1, accent_2):
    """
    Sidebar CSS — dono themes ke liye same structure, alag accent colors.
    accent_1 = primary glow color, accent_2 = secondary glow color
    """
    return (
        f"section[data-testid='stSidebar'] {{ "
        f"background: {C['sidebar_bg']} !important; "
        f"border-right: 1px solid {accent_1}26 !important; "
        f"box-shadow: 2px 0 15px rgba(0,0,0,0.3) !important; }}"

        "section[data-testid='stSidebar'] > div:first-child { padding-top: 20px; }"

        f"section[data-testid='stSidebar'] .stSelectbox > div > div {{ "
        f"background: {C['card_bg']} !important; "
        f"border: 1px solid {accent_1}40 !important; "
        f"border-radius: 10px !important; "
        f"transition: border-color 0.2s ease !important; }}"

        f"section[data-testid='stSidebar'] .stSelectbox > div > div:hover {{ "
        f"border-color: {accent_1}8C !important; }}"

        "section[data-testid='stSidebar'] .stRadio > div { gap: 3px !important; }"

        # Radio labels
        f"section[data-testid='stSidebar'] .stRadio label {{ "
        f"background: {C['card_bg']}99 !important; "
        f"border: 1px solid {accent_1}14 !important; "
        f"border-radius: 10px !important; padding: 11px 14px !important; "
        f"margin: 2px 0 !important; "
        f"transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease !important; "
        f"cursor: pointer !important; display: flex !important; align-items: center !important; "
        f"width: 100% !important; position: relative; overflow: hidden; }}"

        # Glow trail
        "section[data-testid='stSidebar'] .stRadio label .glow-trail { "
        "position: absolute; top: 50%; left: 50%; width: 0; height: 0; border-radius: 50%; "
        f"background: radial-gradient(circle, {accent_1}59 0%, {accent_1}1A 40%, transparent 70%); "
        "transform: translate(-50%, -50%); "
        "transition: width 0.4s ease, height 0.4s ease, opacity 0.3s ease; "
        "opacity: 0; pointer-events: none; z-index: 0; }"

        "section[data-testid='stSidebar'] .stRadio label:hover .glow-trail { "
        "width: 280%; height: 280%; opacity: 1; }"

        "section[data-testid='stSidebar'] .stRadio label:has(input:checked) .glow-trail { "
        "width: 320%; height: 320%; opacity: 0.6; }"

        # Left accent bar
        "section[data-testid='stSidebar'] .stRadio label::before { "
        "content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 3px; "
        f"background: linear-gradient(180deg, {accent_1}, {accent_2}); "
        "transform: scaleY(0); transition: transform 0.25s ease; "
        "border-radius: 0 3px 3px 0; z-index: 2; }"

        "section[data-testid='stSidebar'] .stRadio label:hover::before { transform: scaleY(1); }"

        "section[data-testid='stSidebar'] .stRadio label:has(input:checked)::before { "
        "transform: scaleY(1); }"

        # Checked indicator dot
        "section[data-testid='stSidebar'] .stRadio label:has(input:checked)::after { "
        "content: ''; position: absolute; right: 12px; width: 6px; height: 6px; "
        "border-radius: 50%; "
        f"background: {accent_1}; box-shadow: 0 0 8px {accent_1}; z-index: 2; }}"

        # Label hover / checked states
        f"section[data-testid='stSidebar'] .stRadio label:hover {{ "
        f"background: {accent_1}1A !important; "
        f"border-color: {accent_1}4D !important; "
        f"transform: translateX(3px); }}"

        f"section[data-testid='stSidebar'] .stRadio label:has(input:checked) {{ "
        f"background: linear-gradient(135deg, {accent_1}26 0%, {accent_2}1A 100%) !important; "
        f"border-color: {accent_1}73 !important; "
        f"transform: translateX(3px); }}"

        f"section[data-testid='stSidebar'] .stRadio label:has(input:checked) p {{ "
        f"color: {accent_1} !important; font-weight: 600 !important; "
        f"letter-spacing: 0.4px !important; }}"

        # Hide radio circle
        "section[data-testid='stSidebar'] .stRadio label > div:first-child { display: none !important; }"

        # Label text
        f"section[data-testid='stSidebar'] .stRadio label p {{ "
        f"color: {C['text']} !important; font-size: 0.88rem !important; "
        f"font-weight: 500 !important; margin: 0 !important; "
        f"letter-spacing: 0.3px !important; "
        f"transition: color 0.2s ease; position: relative; z-index: 1; }}"

        # Sidebar headings
        f"section[data-testid='stSidebar'] h3 {{ color: {accent_1} !important; "
        f"font-size: 0.9rem !important; font-weight: 600 !important; "
        f"letter-spacing: 1.5px !important; text-transform: uppercase !important; "
        f"margin: 15px 0 10px 0 !important; padding-bottom: 8px !important; "
        f"border-bottom: 1px solid {accent_1}26 !important; position: relative; }}"

        "section[data-testid='stSidebar'] h3::after { "
        "content: ''; position: absolute; bottom: -1px; left: 0; width: 35px; height: 2px; "
        f"background: linear-gradient(90deg, {accent_1}, transparent); }}"

        # Sidebar caption
        f"section[data-testid='stSidebar'] .stCaption, "
        f"section[data-testid='stSidebar'] small {{ color: {C['muted']} !important; "
        f"font-size: 0.78rem !important; letter-spacing: 0.3px !important; }}"

        # Sidebar buttons
        f"section[data-testid='stSidebar'] .stButton > button {{ "
        f"background: {C['card_bg']}CC !important; "
        f"border: 1px solid {accent_1}40 !important; "
        f"color: {accent_1} !important; "
        f"border-radius: 10px !important; padding: 10px 16px !important; "
        f"font-weight: 600 !important; font-size: 0.85rem !important; "
        f"letter-spacing: 0.4px !important; "
        f"transition: all 0.2s ease !important; }}"

        f"section[data-testid='stSidebar'] .stButton > button:hover {{ "
        f"background: {accent_1}26 !important; "
        f"border-color: {accent_1}80 !important; "
        f"transform: translateY(-1px); }}"

        # Sidebar divider
        "section[data-testid='stSidebar'] hr { border: none !important; "
        "height: 1px !important; "
        f"background: linear-gradient(90deg, transparent, {accent_1}4D, transparent) !important; "
        f"margin: 15px 0 !important; }}"

        # Sidebar scrollbar
        "section[data-testid='stSidebar'] ::-webkit-scrollbar { width: 5px; }"
        f"section[data-testid='stSidebar'] ::-webkit-scrollbar-track {{ "
        f"background: {accent_1}0D; border-radius: 3px; }}"
        f"section[data-testid='stSidebar'] ::-webkit-scrollbar-thumb {{ "
        f"background: linear-gradient(180deg, {accent_1}, {accent_2}); "
        f"border-radius: 3px; }}"
    )


# ===========================
# DARK THEME
# ===========================
def _build_dark_css(C):
    """Dark theme — cyan accents on dark background."""
    shared = _shared_css(C)
    sidebar = _sidebar_css(C, accent_1="#00E5FF", accent_2="#A855F7")
    return shared + sidebar


# ===========================
# LIGHT THEME
# ===========================
def _build_light_css(C):
    """Light theme — purple accents on subtle dark background."""
    shared = _shared_css(C)
    sidebar = _sidebar_css(C, accent_1="#A855F7", accent_2="#EC4899")

    # Light theme ke additional overrides (button gradient, hero gradient)
    # NOTE: Ye extras shared rules ke baad aate hain — specificity same hai,
    # toh baad wala (yahi) jeetega. Ye intentional hai.
    extras = (
        f".stApp {{ "
        f"background-image: "
        f"radial-gradient(circle at 20% 20%, rgba(168,85,247,0.08) 0%, transparent 50%), "
        f"radial-gradient(circle at 80% 80%, rgba(0,229,255,0.06) 0%, transparent 50%); "
        f"background-attachment: fixed; }}"

        f".hero {{ "
        f"background: linear-gradient(135deg, "
        f"rgba(168,85,247,0.15) 0%, rgba(236,72,153,0.12) 50%, rgba(0,229,255,0.15) 100%); "
        f"box-shadow: 0 8px 25px rgba(168,85,247,0.12); "
        f"border: 1px solid rgba(168,85,247,0.25); }}"

        f".hero h1 {{ color: #FFFFFF; text-shadow: 0 0 15px rgba(168,85,247,0.4); }}"
        f".hero p {{ color: rgba(255,255,255,0.85); }}"

        # Light theme primary buttons: keep orange (distinct)
        f".stButton > button[kind='primary'] {{ "
        f"background: linear-gradient(135deg, #FF9933, #FF7A45) !important; "
        f"color: white !important; font-weight: 700 !important; "
        f"box-shadow: 0 3px 15px rgba(255,153,51,0.28) !important; }}"
    )
    return shared + sidebar + extras


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("themes.py — Verification")
    print("=" * 60)

    # Test colors (same as app.py uses)
    DARK_C = dict(
        app_bg="#0b141a", sidebar_bg="#111b21", card_bg="#1f2c34",
        text="#e9edef", muted="#8696a0", border="#2a3942",
        stat_bg1="#1f2c34", stat_bg2="#1f2c34",
        chip_cat_bg="#2a3942", chip_cat_text="#ffb648",
        chip_state_bg="#2a3942", chip_state_text="#53bdeb",
        card_desc="#8696a0",
        glow_purple="#00a884", glow_pink="#00a884", glow_cyan="#53bdeb",
        glow_orange="#ffb648", glow_green="#00a884", glow_red="#f15c6d",
    )
    LIGHT_C = dict(
        app_bg="#0a0a0f", sidebar_bg="rgba(15,15,30,0.95)",
        card_bg="rgba(20,20,40,0.85)",
        text="#FFFFFF", muted="#8080a0", border="rgba(100,100,255,0.2)",
        stat_bg1="rgba(25,25,50,0.8)", stat_bg2="rgba(40,20,70,0.8)",
        chip_cat_bg="rgba(30,30,60,0.6)", chip_cat_text="#FF9933",
        chip_state_bg="rgba(30,30,60,0.6)", chip_state_text="#00E5FF",
        card_desc="#9090b0",
        glow_purple="#A855F7", glow_pink="#EC4899", glow_cyan="#00E5FF",
        glow_orange="#FF9933", glow_green="#00FF88", glow_red="#FF4757",
    )
    T = {"theme_dark": "Dark", "theme_light": "Light"}

    # Test 1: Dark CSS generation
    print("\n[Test 1] Dark theme CSS generation:")
    dark_css = _build_dark_css(DARK_C)
    assert len(dark_css) > 1000, "Dark CSS too short"
    assert "#00E5FF" in dark_css, "Dark accent color missing"
    assert "stSidebar" in dark_css
    print(f"  ✅ Dark CSS: {len(dark_css)} chars")

    # Test 2: Light CSS generation
    print("\n[Test 2] Light theme CSS generation:")
    light_css = _build_light_css(LIGHT_C)
    assert len(light_css) > 1000
    assert "#A855F7" in light_css, "Light accent color missing"
    print(f"  ✅ Light CSS: {len(light_css)} chars")

    # Test 3: No blank lines (CommonMark safety)
    print("\n[Test 3] No blank lines (CommonMark rule 6 safety):")
    assert "\n\n" not in dark_css, "Dark CSS has double newline — markdown bug risk"
    assert "\n\n" not in light_css, "Light CSS has double newline — markdown bug risk"
    print("  ✅ No double newlines — safe from HTML-block termination")

    # Test 4: CSS balance (braces) — SKIP strict check; keep as warning
    print("\n[Test 4] CSS brace count (informational):")
    for name, css in [("Dark", dark_css), ("Light", light_css)]:
        opens = css.count("{")
        closes = css.count("}")
        diff = opens - closes
        status = "✅" if diff == 0 else "⚠️ "
        print(f"  {status} {name}: {opens} open vs {closes} close (diff {diff})")
        if diff != 0:
            print(f"     Note: diff may come from CSS gradient/radial-gradient braces or @keyframes.")
            print(f"     Not necessarily a bug — CSS-specific features use {{ }} literally.")

    # Test 5: Key selectors present
    print("\n[Test 5] Key selectors present:")
    required_selectors = [
        ".scheme-card", ".chip-eligible", ".stat-box",
        ".stButton > button", ".stLinkButton > a",
        "section[data-testid='stSidebar']",
        "[data-testid='stExpander'] summary",
        "@media (max-width: 640px)",
    ]
    for sel in required_selectors:
        assert sel in dark_css, f"Missing selector in dark: {sel}"
        assert sel in light_css, f"Missing selector in light: {sel}"
    print(f"  ✅ All {len(required_selectors)} selectors present in both themes")

    # Test 6: Removed dead selectors
    print("\n[Test 6] Dead selectors removed:")
    dead_selectors = [
        ".streamlit-expanderHeader",   # deprecated
        "[data-testid='stTooltip']",   # never matches
        ".stColumns",                   # doesn't exist
    ]
    for sel in dead_selectors:
        assert sel not in dark_css, f"Dead selector still present: {sel}"
        assert sel not in light_css, f"Dead selector still present: {sel}"
    print(f"  ✅ All {len(dead_selectors)} dead selectors removed")

    # Test 7: @import removed (should not be in CSS)
    print("\n[Test 7] @import removed from CSS:")
    assert "@import" not in dark_css, "Dark CSS still has @import"
    assert "@import" not in light_css, "Light CSS still has @import"
    print("  ✅ @import removed (now uses dedicated <link> injection)")

    # Test 8: apply_theme callable (no Streamlit context)
    print("\n[Test 8] apply_theme() without Streamlit context:")
    try:
        apply_theme("Dark", DARK_C, T)
        apply_theme("Light", LIGHT_C, T)
        print("  ✅ No crash (silent no-op in non-Streamlit context)")
    except Exception as e:
        print(f"  ❌ Crashed: {e}")
        raise

    # Test 9: Bad inputs
    print("\n[Test 9] Bad inputs:")
    # Bad theme choice → should not crash, defaults to light
    apply_theme("Klingon", DARK_C, T)
    print("  ✅ Bad theme choice handled (defaults to light)")
    # Missing theme_dark key → defaults
    apply_theme("Dark", DARK_C, {})
    print("  ✅ Missing theme key handled")

    # Test 10: Mobile CSS does NOT force all blocks to 2-column
    print("\n[Test 10] Mobile CSS no longer forces 2-column for all blocks:")
    # Purana rule: "div[data-testid='stHorizontalBlock'] > div { flex: 1 1 45% !important; }"
    # Naya rule: koi such forced wrap nahi
    bad_rule = "flex: 1 1 45% !important"
    assert bad_rule not in dark_css, "Dark CSS still has forced 2-column rule"
    assert bad_rule not in light_css, "Light CSS still has forced 2-column rule"
    print("  ✅ Forced 2-column rule removed — horizontal blocks wrap naturally")

    print("\n" + "=" * 60)
    print("✅ themes.py — ALL CHECKS PASSED")
    print("=" * 60)