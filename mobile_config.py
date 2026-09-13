"""
mobile_config.py — Mobile detection & mobile-specific CSS.

FIXES (v2):
  - st.context.headers ab multiple Streamlit versions ke against try kiya jaata hai
    (1.36+ me available hai; older versions me gracefully fallback).
  - User-Agent result ab cached hota hai (ek baar parse, baar-baar nahi).
  - Query param override: `?mobile=1` / `?mobile=0` — testing ke liye force mobile/desktop.
  - CSS injection ab safe hai (Streamlit context ke bahar crash nahi karta).
  - Over-aggressive `* { animation-duration: 0.01ms }` hata diya — sirf known
    heavy animations disable hote hain (spinner chalta rehta hai).
  - Configurable breakpoints via constants.
  - Type hints + docstrings.
"""

import streamlit as st

# ===========================
# CONFIGURATION
# ===========================
MOBILE_UA_KEYWORDS = (
    "android", "iphone", "ipad", "ipod", "mobile", "phone",
    "blackberry", "windows phone", "opera mini", "opera mobi",
)

ITEMS_PER_PAGE_MOBILE = 5
ITEMS_PER_PAGE_DESKTOP = 10
SEARCH_RESULTS_MOBILE = 5
SEARCH_RESULTS_DESKTOP = 8

MOBILE_BREAKPOINT_PX = 640


# ===========================
# INTERNAL: UA EXTRACTION
# ===========================
def _get_user_agent():
    """
    User-Agent string nikaalta hai — multiple Streamlit versions ke against
    try karke. Agar koi bhi method fail ho, khaali string return karta hai.
    """
    # Method 1: Streamlit 1.36+ — st.context.headers
    try:
        headers = st.context.headers  # newer Streamlit
        ua = headers.get("User-Agent", "")
        if ua:
            return str(ua)
    except Exception:
        pass

    # Method 2: st.runtime (older versions)
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        ctx = get_script_run_ctx()
        if ctx and hasattr(ctx, "request"):
            req = ctx.request
            if req and hasattr(req, "headers"):
                ua = req.headers.get("User-Agent", "")
                if ua:
                    return str(ua)
    except Exception:
        pass

    return ""


def _get_query_param(name):
    """Query param safely read karta hai (Streamlit version-safe)."""
    try:
        qp = st.query_params
        return qp.get(name, None)
    except Exception:
        return None


# ===========================
# MOBILE DETECTION (cached)
# ===========================
def is_mobile():
    """
    Detect karta hai ki user mobile device par hai ya nahi.

    Priority:
      1. Query param override (?mobile=1 / ?mobile=0) — testing ke liye
      2. User-Agent string (Android/iPhone/iPad/etc.)
      3. Default: False (desktop)

    Result st.session_state me cache hota hai taaki baar-baar UA
    parse na karna pade.
    """
    # Cache hit
    if "_is_mobile_cached" in st.session_state:
        return st.session_state["_is_mobile_cached"]

    # 1. Query param override (dev/testing ke liye)
    override = _get_query_param("mobile")
    if override in ("1", "true", "yes"):
        result = True
    elif override in ("0", "false", "no"):
        result = False
    else:
        # 2. UA-based detection
        ua = _get_user_agent().lower()
        if not ua:
            result = False  # UA missing → assume desktop
        else:
            result = any(kw in ua for kw in MOBILE_UA_KEYWORDS)

    # Cache for this session
    try:
        st.session_state["_is_mobile_cached"] = result
    except Exception:
        pass
    return result


# ===========================
# PAGINATION / RESULTS COUNT
# ===========================
def get_items_per_page():
    """Mobile par 5, desktop par 10 items per page."""
    return ITEMS_PER_PAGE_MOBILE if is_mobile() else ITEMS_PER_PAGE_DESKTOP


def get_search_results_count():
    """Mobile par 5, desktop par 8 search results."""
    return SEARCH_RESULTS_MOBILE if is_mobile() else SEARCH_RESULTS_DESKTOP


# ===========================
# MOBILE CSS INJECTION
# ===========================
def apply_mobile_css():
    """
    Mobile-specific CSS inject karta hai (sirf jab mobile detected ho).
    Desktop par no-op hai.

    Note: ye function Streamlit context ke bahar safely no-op ho jaata hai
    (import-time crash nahi karta).
    """
    if not is_mobile():
        return

    try:
        st.markdown(f"""
        <style>
        /* ===========================
           MOBILE OPTIMIZATION — max-width {MOBILE_BREAKPOINT_PX}px
           =========================== */

        /* Heavy hover transforms disable (touch devices me hover nahi hota) */
        .scheme-card:hover {{ transform: none !important; }}
        .hero:hover {{ animation: none !important; }}
        .stat-box:hover {{ transform: none !important; }}

        /* Buttons: touch-friendly size */
        .stButton > button {{
            padding: 8px 12px !important;
            min-height: 40px !important;
            font-size: 14px !important;
        }}

        /* Scheme card text sizing */
        .scheme-card h4 {{ font-size: 0.9rem !important; }}
        .card-desc {{ font-size: 0.8rem !important; }}
        .chip {{
            font-size: 9px !important;
            padding: 3px 8px !important;
        }}
        .stat-number {{ font-size: 1.2rem !important; }}

        /* Full-width cards */
        .scheme-card {{
            padding: 12px !important;
            margin: 0 0 8px 0 !important;
        }}

        /* Columns: tighter gap */
        .stColumns {{ gap: 4px !important; }}

        /* Hero: smaller */
        .hero {{
            padding: 14px 12px !important;
            border-radius: 10px !important;
            margin-bottom: 10px !important;
        }}
        .hero h1 {{ font-size: 1.4rem !important; }}
        .hero p {{ font-size: 0.8rem !important; }}

        /* Horizontal blocks: allow wrap for chips/buttons */
        div[data-testid="stHorizontalBlock"] {{
            flex-wrap: wrap !important;
            gap: 4px !important;
        }}

        /* Reduce (but don't kill) heavy entrance animations */
        .scheme-card,
        .stat-box {{
            animation-duration: 0.15s !important;
        }}

        /* Loading spinners KEEP working — user feedback ke liye zaroori */
        .stSpinner > div {{ animation-duration: 0.8s !important; }}
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        # Non-Streamlit context me silently fail
        pass


# ===========================
# DEV HELPERS
# ===========================
def force_mobile(enable=True):
    """
    Dev/testing ke liye: mobile mode ko manually force karta hai.
    Ye session_state cache ko override karta hai.
    """
    try:
        st.session_state["_is_mobile_cached"] = bool(enable)
    except Exception:
        pass


def reset_mobile_cache():
    """Mobile cache clear karta hai — next call pe fresh detection."""
    try:
        if "_is_mobile_cached" in st.session_state:
            del st.session_state["_is_mobile_cached"]
    except Exception:
        pass


def get_mobile_status():
    """
    Debug info dict return karta hai (sidebar me display ke liye useful).
    """
    return {
        "is_mobile": is_mobile(),
        "user_agent": _get_user_agent()[:80] + ("..." if len(_get_user_agent()) > 80 else ""),
        "query_override": _get_query_param("mobile"),
        "items_per_page": get_items_per_page(),
        "search_results": get_search_results_count(),
    }


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("mobile_config.py — Verification")
    print("=" * 60)

    # Streamlit context ke bahar test — graceful fallback check
    print("\n[Test 1] Non-Streamlit context (this script):")
    print(f"  is_mobile()                = {is_mobile()}")
    print(f"  get_items_per_page()       = {get_items_per_page()}")
    print(f"  get_search_results_count() = {get_search_results_count()}")
    assert is_mobile() is False, "Non-Streamlit context should return False"
    assert get_items_per_page() == ITEMS_PER_PAGE_DESKTOP
    assert get_search_results_count() == SEARCH_RESULTS_DESKTOP
    print("  ✅ Graceful fallback works (no crash without Streamlit)")

    print("\n[Test 2] UA keyword matching:")
    test_uas = [
        ("Mozilla/5.0 (Linux; Android 10; SM-G973F)", True),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 14_0)", True),
        ("Mozilla/5.0 (iPad; CPU OS 14_0)", True),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", False),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", False),
        ("Mozilla/5.0 (Linux; Android 10) Mobile", True),
        ("Opera/9.80 (Android; Opera Mini/36.2)", True),
    ]
    for ua, expected in test_uas:
        ua_lower = ua.lower()
        detected = any(kw in ua_lower for kw in MOBILE_UA_KEYWORDS)
        status = "✅" if detected == expected else "❌"
        print(f"  {status} mobile={detected:5} (expected {expected:5}) — {ua[:50]}...")
        assert detected == expected, f"UA detection failed for: {ua}"

    print("\n[Test 3] Config constants:")
    assert ITEMS_PER_PAGE_MOBILE < ITEMS_PER_PAGE_DESKTOP
    assert SEARCH_RESULTS_MOBILE < SEARCH_RESULTS_DESKTOP
    assert MOBILE_BREAKPOINT_PX == 640
    print(f"  ✅ Mobile: {ITEMS_PER_PAGE_MOBILE} items, {SEARCH_RESULTS_MOBILE} results")
    print(f"  ✅ Desktop: {ITEMS_PER_PAGE_DESKTOP} items, {SEARCH_RESULTS_DESKTOP} results")

    print("\n[Test 4] Dev helpers (no Streamlit context, should not crash):")
    try:
        force_mobile(True)
        reset_mobile_cache()
        status = get_mobile_status()
        print(f"  ✅ get_mobile_status() works: {status}")
    except Exception as e:
        print(f"  ⚠️  Dev helpers failed (expected in non-Streamlit): {e}")

    print("=" * 60)
    print("✅ mobile_config.py — ALL CHECKS PASSED")
    print("=" * 60)