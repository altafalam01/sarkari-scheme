"""
Mobile optimization settings.
"""

import streamlit as st

def is_mobile():
    """Detect if user is on mobile device."""
    try:
        user_agent = st.context.headers.get("User-Agent", "").lower()
        mobile_keywords = ["android", "iphone", "ipad", "mobile", "phone"]
        return any(k in user_agent for k in mobile_keywords)
    except:
        return False

def get_items_per_page():
    """Get number of items to show per page."""
    return 5 if is_mobile() else 10

def get_search_results_count():
    """Get number of search results to return."""
    return 5 if is_mobile() else 8

def apply_mobile_css():
    """Apply mobile-specific CSS."""
    if is_mobile():
        st.markdown("""
        <style>
        /* Disable heavy animations */
        .scheme-card:hover { transform: none !important; }
        .hero { animation: none !important; }
        .stat-box:hover { transform: none !important; }
        .stButton > button { padding: 8px 12px !important; }
        
        /* Smaller text on mobile */
        .scheme-card h4 { font-size: 0.9rem !important; }
        .card-desc { font-size: 0.8rem !important; }
        .chip { font-size: 9px !important; padding: 3px 8px !important; }
        .stat-number { font-size: 1.2rem !important; }
        
        /* Full width on mobile */
        .scheme-card { padding: 12px !important; margin: 0 0 8px 0 !important; }
        .stColumns { gap: 4px !important; }
        
        /* Reduce animations */
        * { animation-duration: 0.01ms !important; }
        </style>
        """, unsafe_allow_html=True)

# Use in app.py
# from mobile_config import is_mobile, get_items_per_page, get_search_results_count, apply_mobile_css