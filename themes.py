"""
Themes Module
- Contains all CSS for Dark and Light themes
- OPTIMIZED for performance (no heavy backdrop-filters, minimal animations)
- Glow Trail on sidebar (hover + active)
- Usage: from themes import apply_theme
- This file only handles CSS - no logic, no features
"""

import streamlit as st
import textwrap


def apply_theme(theme_choice, C, t):
    """Apply theme CSS based on user's choice."""
    is_simple_dark = (theme_choice == t["theme_dark"])
    
    if is_simple_dark:
        _apply_dark_theme(C)
    else:
        _apply_light_theme(C)


def _apply_dark_theme(C):
    """Apply dark theme CSS - Optimized for performance."""
    st.markdown(
        textwrap.dedent(f"""\
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@200;300;400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}
        .stApp {{ background: {C['app_bg']}; }}
        .stApp, .stApp p, .stApp li, .stApp label, .stApp span {{ color: {C['text']}; }}

        /* ===========================
           HERO - No animations
           =========================== */
        .hero {{
            background: {C['card_bg']};
            padding: 30px 25px;
            border-radius: 12px;
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid {C['border']};
        }}
        .hero h1 {{ color: {C['text']}; font-size: 2.2rem; margin: 0; font-weight: 700; letter-spacing: 0.5px; }}
        .hero p {{ color: {C['muted']}; margin-top: 10px; font-size: 1rem; }}

        /* ===========================
           SCHEME CARD - Simple hover
           =========================== */
        .scheme-card {{
            background: {C['card_bg']};
            border: 1px solid {C['border']};
            border-left: 4px solid {C['glow_cyan']};
            border-radius: 10px;
            padding: 18px 20px;
            margin-bottom: 12px;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .scheme-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0, 229, 255, 0.15);
        }}
        .scheme-card h4 {{ color: {C['text']}; font-size: 1.05rem; font-weight: 600; }}

        .card-desc {{ color: {C['card_desc']}; margin: 6px 0; font-size: 0.9rem; line-height: 1.5; }}

        /* ===========================
           CHIPS - No animations
           =========================== */
        .chip {{
            display: inline-block; padding: 5px 12px; border-radius: 14px;
            font-size: 12px; font-weight: 500; margin-right: 6px; margin-bottom: 8px;
            transition: transform 0.15s ease;
        }}
        .chip:hover {{ transform: translateY(-1px); }}
        .chip-eligible {{ background: rgba(0,168,132,0.15); color: {C['glow_green']}; border: 1px solid {C['glow_green']}; }}
        .chip-not-eligible {{ background: rgba(241,92,109,0.15); color: {C['glow_red']}; border: 1px solid {C['glow_red']}; }}
        .chip-category {{ background: {C['chip_cat_bg']}; color: {C['chip_cat_text']}; border: 1px solid {C['chip_cat_text']}; }}
        .chip-state {{ background: {C['chip_state_bg']}; color: {C['chip_state_text']}; border: 1px solid {C['chip_state_text']}; }}
        .chip-deadline {{ background: rgba(0,168,132,0.12); color: {C['glow_purple']}; border: 1px solid {C['glow_purple']}; }}
        .chip-score {{ background: rgba(255,182,72,0.15); color: {C['glow_orange']}; border: 1px solid {C['glow_orange']}; }}
        .chip-applied {{ background: rgba(0,168,132,0.15); color: {C['glow_green']}; border: 1px solid {C['glow_green']}; }}
        .chip-pending {{ background: rgba(255,182,72,0.15); color: {C['glow_orange']}; border: 1px solid {C['glow_orange']}; }}
        .chip-rejected {{ background: rgba(241,92,109,0.15); color: {C['glow_red']}; border: 1px solid {C['glow_red']}; }}

        /* ===========================
           STAT BOX - Simple hover
           =========================== */
        .stat-box {{
            background: {C['card_bg']};
            border-radius: 10px;
            padding: 18px;
            text-align: center;
            border: 1px solid {C['border']};
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}
        .stat-box:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0, 229, 255, 0.15);
        }}
        .stat-number {{ font-size: 2rem; font-weight: 700; color: {C['glow_cyan']}; }}
        .stat-label {{ font-size: 0.82rem; color: {C['muted']}; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase; }}

        /* ===========================
           OPTIMIZED SIDEBAR - No heavy backdrop-filter
           =========================== */
        section[data-testid="stSidebar"] {{
            background: #0F141E !important;
            border-right: 1px solid rgba(0, 229, 255, 0.15) !important;
            box-shadow: 2px 0 15px rgba(0, 0, 0, 0.3) !important;
        }}

        section[data-testid="stSidebar"] > div:first-child {{
            padding-top: 20px;
        }}

        section[data-testid="stSidebar"] .stSelectbox > div > div {{
            background: rgba(20, 30, 50, 0.8) !important;
            border: 1px solid rgba(0, 229, 255, 0.25) !important;
            border-radius: 10px !important;
            transition: border-color 0.2s ease !important;
        }}

        section[data-testid="stSidebar"] .stSelectbox > div > div:hover {{
            border-color: rgba(0, 229, 255, 0.55) !important;
        }}

        section[data-testid="stSidebar"] .stRadio > div {{ gap: 3px !important; }}

        section[data-testid="stSidebar"] .stRadio label {{
            background: rgba(20, 30, 50, 0.6) !important;
            border: 1px solid rgba(0, 229, 255, 0.08) !important;
            border-radius: 10px !important;
            padding: 11px 14px !important;
            margin: 2px 0 !important;
            transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease !important;
            cursor: pointer !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            position: relative;
            overflow: hidden;
        }}

        section[data-testid="stSidebar"] .stRadio label .glow-trail {{
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: radial-gradient(
                circle,
                rgba(0, 229, 255, 0.35) 0%,
                rgba(0, 229, 255, 0.1) 40%,
                transparent 70%
            );
            transform: translate(-50%, -50%);
            transition: width 0.4s ease, height 0.4s ease, opacity 0.3s ease;
            opacity: 0;
            pointer-events: none;
            z-index: 0;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover .glow-trail {{
            width: 280%;
            height: 280%;
            opacity: 1;
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) .glow-trail {{
            width: 320%;
            height: 320%;
            opacity: 0.6;
            background: radial-gradient(
                circle,
                rgba(0, 229, 255, 0.3) 0%,
                rgba(168, 85, 247, 0.15) 40%,
                transparent 70%
            );
        }}

        section[data-testid="stSidebar"] .stRadio label::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #00E5FF, #A855F7);
            transform: scaleY(0);
            transition: transform 0.25s ease;
            border-radius: 0 3px 3px 0;
            z-index: 2;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover::before {{
            transform: scaleY(1);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked)::before {{
            transform: scaleY(1);
            background: linear-gradient(180deg, #00E5FF, #A855F7, #EC4899);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked)::after {{
            content: '';
            position: absolute;
            right: 12px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #00E5FF;
            box-shadow: 0 0 8px #00E5FF;
            z-index: 2;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover {{
            background: rgba(0, 229, 255, 0.1) !important;
            border-color: rgba(0, 229, 255, 0.3) !important;
            transform: translateX(3px);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) {{
            background: linear-gradient(135deg, 
                rgba(0, 229, 255, 0.15) 0%, 
                rgba(168, 85, 247, 0.1) 100%) !important;
            border-color: rgba(0, 229, 255, 0.45) !important;
            transform: translateX(3px);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) p {{
            color: #00E5FF !important;
            font-weight: 600 !important;
            letter-spacing: 0.4px !important;
        }}

        section[data-testid="stSidebar"] .stRadio label > div:first-child {{
            display: none !important;
        }}

        section[data-testid="stSidebar"] .stRadio label p {{
            color: #B8C5D6 !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            margin: 0 !important;
            letter-spacing: 0.3px !important;
            transition: color 0.2s ease;
            position: relative;
            z-index: 1;
        }}

        section[data-testid="stSidebar"] h3 {{
            color: #00E5FF !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            letter-spacing: 1.5px !important;
            text-transform: uppercase !important;
            margin: 15px 0 10px 0 !important;
            padding-bottom: 8px !important;
            border-bottom: 1px solid rgba(0, 229, 255, 0.15) !important;
            position: relative;
        }}

        section[data-testid="stSidebar"] h3::after {{
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 35px;
            height: 2px;
            background: linear-gradient(90deg, #00E5FF, transparent);
        }}

        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] small {{
            color: #6B7A8F !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.3px !important;
        }}

        section[data-testid="stSidebar"] .stButton > button {{
            background: rgba(20, 30, 50, 0.8) !important;
            border: 1px solid rgba(0, 229, 255, 0.25) !important;
            color: #00E5FF !important;
            border-radius: 10px !important;
            padding: 10px 16px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            letter-spacing: 0.4px !important;
            transition: all 0.2s ease !important;
        }}

        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(0, 229, 255, 0.15) !important;
            border-color: rgba(0, 229, 255, 0.5) !important;
            transform: translateY(-1px);
        }}

        section[data-testid="stSidebar"] hr {{
            border: none !important;
            height: 1px !important;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(0, 229, 255, 0.3), 
                transparent) !important;
            margin: 15px 0 !important;
        }}

        section[data-testid="stSidebar"] ::-webkit-scrollbar {{
            width: 5px;
        }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-track {{
            background: rgba(0, 229, 255, 0.05);
            border-radius: 3px;
        }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, #00E5FF, #A855F7);
            border-radius: 3px;
        }}

        /* ===========================
           GENERAL BUTTONS - Simple
           =========================== */
        .stButton > button, .stDownloadButton > button, .stLinkButton > a,
        div[data-testid="stPopover"] > div > button {{
            background: {C['glow_cyan']} !important; 
            color: #0b141a !important;
            border: none !important; 
            border-radius: 8px !important;
            padding: 10px 20px !important; 
            font-weight: 600 !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }}
        .stButton > button:focus, .stButton > button:active, .stButton > button:focus-visible {{ outline: none !important; box-shadow: none !important; }}
        .stButton > button:hover, .stDownloadButton > button:hover,
        .stLinkButton > a:hover, div[data-testid="stPopover"] > div > button:hover {{ 
            transform: translateY(-2px);
            box-shadow: 0 6px 18px rgba(0, 229, 255, 0.25);
        }}
        .stButton > button[kind="primary"] {{ 
            background: {C['glow_green']} !important; 
            color: #0b141a !important; 
        }}

        /* ===========================
           INPUTS - Simple
           =========================== */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stDateInput > div > div > input,
        .stTextArea > div > div > textarea {{
            background: {C['card_bg']} !important; 
            color: {C['text']} !important;
            border: 1px solid {C['border']} !important; 
            border-radius: 8px !important;
            padding: 8px 12px !important;
            transition: border-color 0.2s ease !important;
        }}
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stDateInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {{
            border-color: {C['glow_cyan']} !important; 
            outline: none !important; 
            box-shadow: none !important;
        }}
        .stSelectbox div[data-baseweb="select"] > div {{
            background-color: {C['card_bg']} !important; 
            color: {C['text']} !important;
            border: 1px solid {C['border']} !important; 
            border-radius: 8px !important;
            min-height: 42px !important; 
            display: flex !important; 
            align-items: center !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="menu"] {{
            background: {C['card_bg']} !important; 
            border: 1px solid {C['border']} !important;
            border-radius: 8px !important; 
            padding: 5px !important;
        }}
        div[data-baseweb="popover"] li {{
            color: {C['text']} !important; 
            background: transparent !important;
            padding: 8px 12px !important; 
            border-radius: 6px !important; 
            font-size: 14px !important;
        }}
        div[data-baseweb="popover"] li:hover {{ background: {C['border']} !important; }}

        /* ===========================
           SHARE ICONS - Simple
           =========================== */
        .share-icon-row a {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 46px; height: 46px; border-radius: 50%;
            background: {C['card_bg']}; 
            border: 1px solid {C['border']};
            margin-right: 10px; text-decoration: none;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .share-icon-row a:hover {{
            transform: scale(1.1);
            border-color: {C['glow_cyan']};
        }}
        .share-icon-row img {{ width: 22px; height: 22px; }}
        div[data-testid="stPopover"] {{ position: relative; z-index: 1000; }}

        /* ===========================
           EXPANDER - Simple
           =========================== */
        .streamlit-expanderHeader {{
            background: {C['card_bg']} !important; 
            color: {C['text']} !important;
            border-radius: 8px !important; 
            padding: 12px !important;
            border: 1px solid {C['border']} !important;
            transition: background 0.2s ease, border-color 0.2s ease !important;
        }}
        .streamlit-expanderHeader:hover {{
            background: rgba(0, 229, 255, 0.08) !important;
            border-color: rgba(0, 229, 255, 0.3) !important;
        }}

        /* ===========================
           MODERN NEON PROGRESS BAR
           =========================== */
        .stProgress > div > div > div > div {{
            background: linear-gradient(90deg, 
                #00E5FF 0%, 
                #A855F7 50%, 
                #EC4899 100%) !important;
            background-size: 200% 100% !important;
            animation: neonProgress 2s ease infinite !important;
            border-radius: 10px !important;
            box-shadow: 
                0 0 10px rgba(0, 229, 255, 0.6),
                0 0 20px rgba(168, 85, 247, 0.4) !important;
            position: relative;
            overflow: hidden;
        }}

        .stProgress > div > div > div > div::after {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(255, 255, 255, 0.4), 
                transparent);
            animation: shimmerProgress 2s ease-in-out infinite;
        }}

        @keyframes neonProgress {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}

        @keyframes shimmerProgress {{
            0% {{ left: -100%; }}
            100% {{ left: 100%; }}
        }}

        .stAlert {{ 
            border-radius: 8px !important; 
            border: 1px solid {C['border']} !important; 
            padding: 15px !important; 
        }}
        .stRadio > div, .stCheckbox > div {{ padding: 6px; border-radius: 8px; }}
        .stRadio > div:focus, .stCheckbox > div:focus {{ outline: none !important; box-shadow: none !important; }}
        .stSlider > div > div > div > div {{ background: {C['glow_cyan']} !important; }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: {C['sidebar_bg']}; }}
        ::-webkit-scrollbar-thumb {{ background: {C['border']}; border-radius: 8px; }}

        @media (max-width: 640px) {{
            .block-container {{ padding-top: 0.5rem; padding-left: 0.5rem; padding-right: 0.5rem; }}
            .hero {{ padding: 14px 12px; border-radius: 10px; margin-bottom: 10px; }}
            .hero h1 {{ font-size: 1.4rem; }}
            .hero p {{ font-size: 0.8rem; }}
            .scheme-card {{ padding: 12px 14px; margin-bottom: 8px; }}
            .scheme-card h4 {{ font-size: 0.9rem; }}
            .chip {{ font-size: 9px; padding: 3px 8px; margin-bottom: 4px; }}
            .stat-box {{ padding: 10px; }}
            .stat-number {{ font-size: 1.2rem; }}
            .stat-label {{ font-size: 0.7rem; }}
            .stButton > button {{ padding: 8px 12px !important; font-size: 14px !important; min-height: 36px !important; }}
            div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 4px !important; }}
            div[data-testid="stHorizontalBlock"] > div {{ flex: 1 1 45% !important; min-width: 0 !important; }}
            .stColumns {{ gap: 4px !important; }}
            .stExpander {{ margin-bottom: 6px !important; }}
            .stSelectbox {{ margin-bottom: 4px !important; }}
            .stTextInput {{ margin-bottom: 4px !important; }}
            .stNumberInput {{ margin-bottom: 4px !important; }}
        }}

        [data-testid="stTooltip"] {{
            background: {C['card_bg']} !important; 
            color: {C['text']} !important;
            border-radius: 8px !important; 
            padding: 8px 12px !important;
            border: 1px solid {C['border']} !important;
        }}
        </style>
        """),
        unsafe_allow_html=True,
    )


def _apply_light_theme(C):
    """Apply light theme CSS - Optimized for performance."""
    st.markdown(
        textwrap.dedent(f"""\
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@200;300;400;500;600;700&display=swap');

        html, body, [class*="css"] {{ font-family: 'Poppins', sans-serif; }}

        /* ===========================
           OPTIMIZED LIGHT BACKGROUND - No animations
           =========================== */
        .stApp {{
            background: #0a0a0f;
            background-image: 
                radial-gradient(circle at 20% 20%, rgba(168, 85, 247, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 80%, rgba(0, 229, 255, 0.06) 0%, transparent 50%);
            background-attachment: fixed;
        }}

        .stApp, .stApp p, .stApp li, .stApp label, .stApp span {{ color: {C['text']}; }}

        /* ===========================
           HERO - No animation
           =========================== */
        .hero {{
            background: linear-gradient(135deg, 
                rgba(168, 85, 247, 0.15) 0%, 
                rgba(236, 72, 153, 0.12) 50%, 
                rgba(0, 229, 255, 0.15) 100%);
            padding: 35px 30px;
            border-radius: 20px;
            text-align: center;
            margin-bottom: 25px;
            box-shadow: 0 8px 25px rgba(168, 85, 247, 0.12);
            position: relative;
            border: 1px solid rgba(168, 85, 247, 0.25);
        }}

        .hero h1 {{
            color: #FFFFFF;
            font-size: 2.5rem;
            margin: 0;
            font-weight: 700;
            letter-spacing: 2px;
            text-shadow: 0 0 15px rgba(168, 85, 247, 0.4);
        }}

        .hero p {{
            color: rgba(255, 255, 255, 0.85);
            margin-top: 10px;
            font-size: 1.05rem;
            letter-spacing: 0.5px;
        }}

        /* ===========================
           SCHEME CARD - Simple hover
           =========================== */
        .scheme-card {{
            background: rgba(25, 25, 45, 0.85);
            border: 1px solid {C['border']};
            border-radius: 15px;
            padding: 22px 25px;
            margin-bottom: 15px;
            border-left: 5px solid {C['glow_purple']};
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            position: relative;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}

        .scheme-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(168, 85, 247, 0.18);
            border-color: rgba(0, 229, 255, 0.35);
            border-left-color: {C['glow_cyan']};
        }}

        .scheme-card h4 {{
            color: {C['text']};
            font-size: 1.1rem;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}

        .card-desc {{ color: {C['card_desc']}; margin: 6px 0; font-size: 0.9rem; line-height: 1.5; }}

        /* ===========================
           CHIPS - No animations
           =========================== */
        .chip {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 500;
            margin-right: 6px;
            margin-bottom: 8px;
            letter-spacing: 0.3px;
            transition: transform 0.15s ease;
        }}

        .chip:hover {{
            transform: translateY(-1px);
        }}

        .chip-eligible {{ background: rgba(0, 255, 136, 0.12); color: #00FF88; border: 1px solid rgba(0, 255, 136, 0.4); }}
        .chip-not-eligible {{ background: rgba(255, 71, 87, 0.12); color: #FF4757; border: 1px solid rgba(255, 71, 87, 0.4); }}
        .chip-category {{ background: rgba(255, 153, 51, 0.12); color: {C['chip_cat_text']}; border: 1px solid rgba(255, 153, 51, 0.4); }}
        .chip-state {{ background: rgba(0, 229, 255, 0.12); color: {C['chip_state_text']}; border: 1px solid rgba(0, 229, 255, 0.4); }}
        .chip-deadline {{ background: rgba(168, 85, 247, 0.12); color: #A855F7; border: 1px solid rgba(168, 85, 247, 0.4); }}
        .chip-score {{ background: rgba(255, 153, 51, 0.12); color: #FF9933; border: 1px solid rgba(255, 153, 51, 0.4); }}
        .chip-applied {{ background: rgba(0, 255, 136, 0.12); color: #00FF88; border: 1px solid rgba(0, 255, 136, 0.4); }}
        .chip-pending {{ background: rgba(255, 153, 51, 0.12); color: #FF9933; border: 1px solid rgba(255, 153, 51, 0.4); }}
        .chip-rejected {{ background: rgba(255, 71, 87, 0.12); color: #FF4757; border: 1px solid rgba(255, 71, 87, 0.4); }}

        /* ===========================
           STAT BOX - Simple hover
           =========================== */
        .stat-box {{
            background: rgba(25, 25, 45, 0.85);
            border-radius: 15px;
            padding: 22px;
            text-align: center;
            border: 1px solid {C['border']};
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }}

        .stat-box:hover {{
            transform: translateY(-3px);
            box-shadow: 0 10px 25px rgba(168, 85, 247, 0.18);
            border-color: rgba(168, 85, 247, 0.4);
        }}

        .stat-number {{
            font-size: 2.2rem;
            font-weight: 700;
            color: {C['glow_orange']};
            text-shadow: 0 0 12px rgba(255, 153, 51, 0.35);
        }}

        .stat-label {{
            font-size: 0.85rem;
            color: {C['muted']};
            margin-top: 6px;
            letter-spacing: 1.2px;
            text-transform: uppercase;
        }}

        /* ===========================
           OPTIMIZED SIDEBAR - No heavy backdrop-filter
           =========================== */
        section[data-testid="stSidebar"] {{
            background: #0F0A19 !important;
            border-right: 1px solid rgba(168, 85, 247, 0.2) !important;
            box-shadow: 2px 0 15px rgba(0, 0, 0, 0.3) !important;
            position: relative;
        }}

        section[data-testid="stSidebar"]::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at 20% 10%, rgba(168, 85, 247, 0.05) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}

        section[data-testid="stSidebar"] > div:first-child {{
            padding-top: 20px;
            position: relative;
            z-index: 1;
        }}

        section[data-testid="stSidebar"] .stSelectbox > div > div {{
            background: rgba(25, 18, 40, 0.8) !important;
            border: 1px solid rgba(168, 85, 247, 0.25) !important;
            border-radius: 10px !important;
            transition: border-color 0.2s ease !important;
        }}

        section[data-testid="stSidebar"] .stSelectbox > div > div:hover {{
            border-color: rgba(168, 85, 247, 0.55) !important;
        }}

        section[data-testid="stSidebar"] .stRadio > div {{ gap: 3px !important; }}

        section[data-testid="stSidebar"] .stRadio label {{
            background: rgba(20, 15, 35, 0.6) !important;
            border: 1px solid rgba(168, 85, 247, 0.08) !important;
            border-radius: 10px !important;
            padding: 11px 14px !important;
            margin: 2px 0 !important;
            transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease !important;
            cursor: pointer !important;
            display: flex !important;
            align-items: center !important;
            width: 100% !important;
            position: relative;
            overflow: hidden;
        }}

        section[data-testid="stSidebar"] .stRadio label .glow-trail {{
            position: absolute;
            top: 50%;
            left: 50%;
            width: 0;
            height: 0;
            border-radius: 50%;
            background: radial-gradient(
                circle,
                rgba(168, 85, 247, 0.35) 0%,
                rgba(168, 85, 247, 0.1) 40%,
                transparent 70%
            );
            transform: translate(-50%, -50%);
            transition: width 0.4s ease, height 0.4s ease, opacity 0.3s ease;
            opacity: 0;
            pointer-events: none;
            z-index: 0;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover .glow-trail {{
            width: 280%;
            height: 280%;
            opacity: 1;
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) .glow-trail {{
            width: 320%;
            height: 320%;
            opacity: 0.6;
            background: radial-gradient(
                circle,
                rgba(168, 85, 247, 0.3) 0%,
                rgba(236, 72, 153, 0.15) 40%,
                transparent 70%
            );
        }}

        section[data-testid="stSidebar"] .stRadio label::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
            background: linear-gradient(180deg, #A855F7, #EC4899);
            transform: scaleY(0);
            transition: transform 0.25s ease;
            border-radius: 0 3px 3px 0;
            z-index: 2;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover::before {{
            transform: scaleY(1);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked)::before {{
            transform: scaleY(1);
            background: linear-gradient(180deg, #A855F7, #EC4899);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked)::after {{
            content: '';
            position: absolute;
            right: 12px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: #A855F7;
            box-shadow: 0 0 8px #A855F7;
            z-index: 2;
        }}

        section[data-testid="stSidebar"] .stRadio label:hover {{
            background: rgba(168, 85, 247, 0.1) !important;
            border-color: rgba(168, 85, 247, 0.3) !important;
            transform: translateX(3px);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) {{
            background: linear-gradient(135deg, 
                rgba(168, 85, 247, 0.15) 0%, 
                rgba(236, 72, 153, 0.1) 100%) !important;
            border-color: rgba(168, 85, 247, 0.45) !important;
            transform: translateX(3px);
        }}

        section[data-testid="stSidebar"] .stRadio label:has(input:checked) p {{
            color: #A855F7 !important;
            font-weight: 600 !important;
            letter-spacing: 0.4px !important;
        }}

        section[data-testid="stSidebar"] .stRadio label > div:first-child {{
            display: none !important;
        }}

        section[data-testid="stSidebar"] .stRadio label p {{
            color: #B8B5C6 !important;
            font-size: 0.88rem !important;
            font-weight: 500 !important;
            margin: 0 !important;
            letter-spacing: 0.3px !important;
            transition: color 0.2s ease;
            position: relative;
            z-index: 1;
        }}

        section[data-testid="stSidebar"] h3 {{
            color: #A855F7 !important;
            font-size: 0.9rem !important;
            font-weight: 600 !important;
            letter-spacing: 1.5px !important;
            text-transform: uppercase !important;
            margin: 15px 0 10px 0 !important;
            padding-bottom: 8px !important;
            border-bottom: 1px solid rgba(168, 85, 247, 0.15) !important;
            position: relative;
        }}

        section[data-testid="stSidebar"] h3::after {{
            content: '';
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 35px;
            height: 2px;
            background: linear-gradient(90deg, #A855F7, transparent);
        }}

        section[data-testid="stSidebar"] .stCaption,
        section[data-testid="stSidebar"] small {{
            color: #7A7089 !important;
            font-size: 0.78rem !important;
            letter-spacing: 0.3px !important;
        }}

        section[data-testid="stSidebar"] .stButton > button {{
            background: rgba(25, 18, 40, 0.8) !important;
            border: 1px solid rgba(168, 85, 247, 0.25) !important;
            color: #A855F7 !important;
            border-radius: 10px !important;
            padding: 10px 16px !important;
            font-weight: 600 !important;
            font-size: 0.85rem !important;
            letter-spacing: 0.4px !important;
            transition: all 0.2s ease !important;
        }}

        section[data-testid="stSidebar"] .stButton > button:hover {{
            background: rgba(168, 85, 247, 0.15) !important;
            border-color: rgba(168, 85, 247, 0.5) !important;
            transform: translateY(-1px);
        }}

        section[data-testid="stSidebar"] hr {{
            border: none !important;
            height: 1px !important;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(168, 85, 247, 0.3), 
                transparent) !important;
            margin: 15px 0 !important;
        }}

        section[data-testid="stSidebar"] ::-webkit-scrollbar {{
            width: 5px;
        }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-track {{
            background: rgba(168, 85, 247, 0.05);
            border-radius: 3px;
        }}
        section[data-testid="stSidebar"] ::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, #A855F7, #EC4899);
            border-radius: 3px;
        }}

        /* ===========================
           GENERAL BUTTONS - Simple
           =========================== */
        .stButton > button, .stDownloadButton > button, .stLinkButton > a,
        div[data-testid="stPopover"] > div > button {{
            background: linear-gradient(135deg, 
                rgba(168, 85, 247, 0.85), 
                rgba(236, 72, 153, 0.75)) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 10px 22px !important;
            font-weight: 600 !important;
            letter-spacing: 0.5px !important;
            box-shadow: 0 3px 10px rgba(168, 85, 247, 0.2) !important;
            transition: transform 0.2s ease, box-shadow 0.2s ease !important;
        }}

        .stButton > button:focus, .stButton > button:active, .stButton > button:focus-visible {{ outline: none !important; box-shadow: none !important; }}

        .stButton > button:hover, .stDownloadButton > button:hover,
        .stLinkButton > a:hover, div[data-testid="stPopover"] > div > button:hover {{
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 18px rgba(168, 85, 247, 0.28) !important;
        }}

        .stButton > button[kind="primary"] {{
            background: linear-gradient(135deg, #FF9933, #FF7A45) !important;
            color: white !important;
            font-weight: 700 !important;
            box-shadow: 0 3px 15px rgba(255, 153, 51, 0.28) !important;
        }}

        /* ===========================
           INPUTS - Simple
           =========================== */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stDateInput > div > div > input,
        .stTextArea > div > div > textarea {{
            background: rgba(20, 15, 35, 0.9) !important;
            color: white !important;
            border: 1px solid rgba(168, 85, 247, 0.25) !important;
            border-radius: 10px !important;
            padding: 8px 12px !important;
            transition: border-color 0.2s ease !important;
        }}

        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus,
        .stDateInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {{
            border-color: rgba(0, 229, 255, 0.55) !important;
            box-shadow: none !important;
            outline: none !important;
        }}

        .stSelectbox div[data-baseweb="select"] > div {{
            background-color: rgba(20, 15, 35, 0.9) !important;
            color: white !important;
            border: 1px solid rgba(168, 85, 247, 0.25) !important;
            border-radius: 10px !important;
            min-height: 42px !important;
            display: flex !important;
            align-items: center !important;
        }}

        div[data-baseweb="popover"] div[data-baseweb="menu"] {{
            background: rgba(20, 15, 35, 0.98) !important;
            border: 1px solid rgba(168, 85, 247, 0.3) !important;
            border-radius: 10px !important;
            padding: 5px !important;
        }}

        div[data-baseweb="popover"] li {{
            color: white !important;
            background: transparent !important;
            padding: 8px 12px !important;
            border-radius: 6px !important;
            font-size: 14px !important;
        }}

        div[data-baseweb="popover"] li:hover {{ background: rgba(168, 85, 247, 0.15) !important; }}

        /* ===========================
           SHARE ICONS - Simple
           =========================== */
        .share-icon-row a {{
            display: inline-flex; align-items: center; justify-content: center;
            width: 46px; height: 46px; border-radius: 50%;
            background: rgba(25, 18, 40, 0.9);
            border: 1px solid rgba(168, 85, 247, 0.3);
            margin-right: 10px; text-decoration: none;
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .share-icon-row a:hover {{
            transform: scale(1.1);
            border-color: rgba(0, 229, 255, 0.5);
        }}

        .share-icon-row img {{ width: 22px; height: 22px; }}
        div[data-testid="stPopover"] {{ position: relative; z-index: 1000; }}

        /* ===========================
           EXPANDER - Simple
           =========================== */
        .streamlit-expanderHeader {{
            background: rgba(25, 18, 40, 0.7) !important;
            color: white !important;
            border-radius: 10px !important;
            padding: 12px !important;
            border: 1px solid rgba(168, 85, 247, 0.2) !important;
            transition: background 0.2s ease, border-color 0.2s ease !important;
        }}

        .streamlit-expanderHeader:hover {{
            background: rgba(168, 85, 247, 0.12) !important;
            border-color: rgba(168, 85, 247, 0.35) !important;
        }}

        /* ===========================
           MODERN NEON PROGRESS BAR
           =========================== */
        .stProgress > div > div > div > div {{
            background: linear-gradient(90deg, 
                #A855F7 0%, 
                #EC4899 50%, 
                #FF9933 100%) !important;
            background-size: 200% 100% !important;
            animation: neonProgress 2s ease infinite !important;
            border-radius: 10px !important;
            box-shadow: 
                0 0 10px rgba(168, 85, 247, 0.5),
                0 0 20px rgba(236, 72, 153, 0.3) !important;
            position: relative;
            overflow: hidden;
        }}

        .stProgress > div > div > div > div::after {{
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, 
                transparent, 
                rgba(255, 255, 255, 0.4), 
                transparent);
            animation: shimmerProgress 2s ease-in-out infinite;
        }}

        @keyframes neonProgress {{
            0%, 100% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
        }}

        @keyframes shimmerProgress {{
            0% {{ left: -100%; }}
            100% {{ left: 100%; }}
        }}

        .stAlert {{
            border-radius: 12px !important;
            border: 1px solid rgba(0, 229, 255, 0.3) !important;
            padding: 15px !important;
        }}

        .stRadio > div, .stCheckbox > div {{ padding: 6px; border-radius: 8px; }}
        .stRadio > div:focus, .stCheckbox > div:focus {{ outline: none !important; box-shadow: none !important; }}
        .stSlider > div > div > div > div {{ background: linear-gradient(90deg, #A855F7, #00E5FF) !important; }}

        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: rgba(15, 15, 30, 0.5); border-radius: 10px; }}
        ::-webkit-scrollbar-thumb {{
            background: linear-gradient(135deg, #A855F7, #EC4899);
            border-radius: 10px;
        }}

        @media (max-width: 640px) {{
            .block-container {{ padding-top: 0.5rem; padding-left: 0.5rem; padding-right: 0.5rem; }}
            .hero {{ padding: 14px 12px; border-radius: 10px; margin-bottom: 10px; }}
            .hero h1 {{ font-size: 1.4rem; }}
            .hero p {{ font-size: 0.8rem; }}
            .scheme-card {{ padding: 12px 14px; margin-bottom: 8px; }}
            .scheme-card h4 {{ font-size: 0.9rem; }}
            .chip {{ font-size: 9px; padding: 3px 8px; margin-bottom: 4px; }}
            .stat-box {{ padding: 10px; }}
            .stat-number {{ font-size: 1.2rem; }}
            .stat-label {{ font-size: 0.7rem; }}
            .stButton > button {{ padding: 8px 12px !important; font-size: 14px !important; min-height: 36px !important; }}
            div[data-testid="stHorizontalBlock"] {{ flex-wrap: wrap !important; gap: 4px !important; }}
            div[data-testid="stHorizontalBlock"] > div {{ flex: 1 1 45% !important; min-width: 0 !important; }}
            .stColumns {{ gap: 4px !important; }}
            .stExpander {{ margin-bottom: 6px !important; }}
        }}

        [data-testid="stTooltip"] {{
            background: rgba(25, 18, 40, 0.95) !important;
            color: white !important;
            border-radius: 8px !important;
            padding: 8px 12px !important;
            border: 1px solid rgba(168, 85, 247, 0.3) !important;
        }}
        </style>
        """),
        unsafe_allow_html=True,
    )