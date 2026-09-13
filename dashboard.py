"""
dashboard.py — Modern dashboard with charts, stats, and urgent alerts.

FIXES (v2):
  - Empty DataFrame / missing columns / wrong types — sab safely handle.
  - get_urgent_schemes() return value validate hoti hai (None / non-list → []).
  - Urgent scheme dict access .get() se safe.
  - load_applications() corrupt JSON → {} (crash nahi karta).
  - Non-dict JSON content → {}.
  - Plotly theme ab parameter-controlled (Light theme me dark charts nahi).
  - URL sanitization: javascript: / data: URLs filter hoti hain.
  - Division-by-zero / NaN pie chart edge cases.
  - html.escape() with quote=True for attribute-safe injection.
  - __main__ self-test.
"""

import streamlit as st
import html
import pandas as pd
import plotly.express as px
import os
import json


# ===========================
# HELPERS
# ===========================
def safe_str(value, default=""):
    """None/NaN/non-str → safe string."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def _is_safe_url(url):
    """
    URL safe hai agar http:// ya https:// se start ho.
    javascript:, data:, file: etc. reject.
    """
    if not url:
        return False
    url = str(url).strip().lower()
    return url.startswith("http://") or url.startswith("https://")


def _escape_attr(value):
    """HTML attribute-safe escaping (quotes bhi escape ho jaate hain)."""
    return html.escape(str(value), quote=True)


def load_applications():
    """
    Applications JSON load karta hai.
    - File missing → {}
    - Corrupt JSON → {}
    - Non-dict content → {}
    """
    path = "data/applications.json"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _safe_urgent_schemes(get_urgent_schemes, df, threshold=30):
    """
    get_urgent_schemes() ko safely call karta hai.
    Return None / non-list / crash → [].
    """
    try:
        result = get_urgent_schemes(df, days_threshold=threshold)
        if not isinstance(result, list):
            return []
        # Sirf dict items rakho
        return [u for u in result if isinstance(u, dict)]
    except Exception:
        return []


# ===========================
# CHART THEME
# ===========================
def _chart_layout(title, title_color, is_light=False):
    """Return common plotly layout kwargs for both themes."""
    return dict(
        template="plotly_white" if is_light else "plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Poppins, sans-serif", size=11,
                  color="#1F2C34" if is_light else "#E9EDEF"),
        title=dict(font=dict(size=16, color=title_color), x=0.5, xanchor="center"),
        hoverlabel=dict(
            bgcolor="#FFFFFF" if is_light else "#1F2C34",
            font_size=12,
            font_family="Poppins",
            bordercolor=title_color,
        ),
    )


# ===========================
# URGENT ALERTS SECTION
# ===========================
def _render_urgent_alerts(df, get_urgent_schemes, C):
    """Urgent deadline alerts render karta hai."""
    urgent_schemes = _safe_urgent_schemes(get_urgent_schemes, df, threshold=30)

    if not urgent_schemes:
        st.success("✅ No urgent deadlines right now!")
        return

    st.markdown("### 🔴 Urgent Deadline Alerts")
    st.caption("Ye schemes jald hi band ho rahi hain. Aaj hi apply karein!")

    for u in urgent_schemes[:5]:
        try:
            color = safe_str(u.get("color"), "#FF4757")
            days_left = u.get("days_left", 999)
            status_text = safe_str(u.get("status_text"), "Unknown")
            scheme_name = safe_str(u.get("scheme_name"), "Unnamed")
            category = safe_str(u.get("category_type"), "")
            state = safe_str(u.get("applicable_state"), "")
            apply_link = safe_str(u.get("apply_link"), "")

            # Emoji based on urgency
            try:
                dl = int(days_left)
            except (ValueError, TypeError):
                dl = 999

            if dl < 0:
                emoji = "❌"
            elif dl == 0:
                emoji = "🚨"
            elif dl <= 7:
                emoji = "🔥"
            else:
                emoji = "⚠️"

            # Apply link safely render karo
            if _is_safe_url(apply_link):
                link_html = (
                    f'<a href="{_escape_attr(apply_link)}" target="_blank" '
                    f'style="color:{color};">{html.escape(apply_link)}</a>'
                )
            else:
                link_html = html.escape(apply_link) if apply_link else "N/A"

            # Single-line HTML concatenation (CommonMark safe)
            card_html = (
                f'<div class="scheme-card" style="border-left: 6px solid {color};">'
                f'<span class="chip" style="background-color:rgba(255,71,87,0.2); '
                f'color:{color}; border:1px solid {color};">'
                f'{emoji} {html.escape(status_text)}</span>'
                f'<h4 style="margin:8px 0 4px 0;">{html.escape(scheme_name)}</h4>'
                f'<p class="card-desc">{html.escape(category)} | {html.escape(state)}</p>'
                f'<p class="card-desc"><b>Apply:</b> {link_html}</p>'
                f'</div>'
            )
            st.markdown(card_html, unsafe_allow_html=True)
            st.write("")
        except Exception:
            # Ek urgent card fail ho jaaye to baaki continue
            continue


# ===========================
# STATS CARDS
# ===========================
def _render_stats_cards(df, apps):
    """Top 4 stat cards render karta hai."""
    # Safe extraction of stats
    total_schemes = len(df) if df is not None else 0

    if df is not None and not df.empty and "applicable_state" in df.columns:
        total_states = len(df["applicable_state"].dropna().unique())
    else:
        total_states = 0

    if df is not None and not df.empty and "category_type" in df.columns:
        total_categories = len(df["category_type"].dropna().unique())
    else:
        total_categories = 0

    total_applications = len(apps) if isinstance(apps, dict) else 0

    stats_data = [
        ("📋", "Total Schemes", total_schemes, "#00E5FF"),
        ("🗺️", "States", total_states, "#A855F7"),
        ("📂", "Categories", total_categories, "#FF9933"),
        ("📝", "Applications", total_applications, "#00FF88"),
    ]

    cols = st.columns(4)
    for col, (icon, label, value, color) in zip(cols, stats_data):
        with col:
            # Single-line HTML
            st.markdown(
                f'<div style="background: linear-gradient(135deg, rgba(31, 44, 52, 0.8), '
                f'rgba(20, 30, 40, 0.9)); border: 1px solid {color}; border-radius: 15px; '
                f'padding: 20px; text-align: center; '
                f'box-shadow: 0 0 20px {color}33, inset 0 0 20px {color}11;">'
                f'<div style="font-size: 2rem; margin-bottom: 5px;">{icon}</div>'
                f'<div style="font-size: 2.2rem; font-weight: 800; color: {color}; '
                f'text-shadow: 0 0 15px {color}88; font-family: \'Orbitron\', sans-serif;">'
                f'{value}</div>'
                f'<div style="font-size: 0.8rem; color: #8696A0; letter-spacing: 1.5px; '
                f'text-transform: uppercase; margin-top: 5px;">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ===========================
# BAR CHART
# ===========================
def _render_bar_chart(df, is_light):
    """Schemes-by-category bar chart."""
    if df is None or df.empty or "category_type" not in df.columns:
        st.info("No category data available.")
        return

    try:
        category_counts = df["category_type"].value_counts().reset_index()
        category_counts.columns = ["Category", "Count"]

        if category_counts.empty:
            st.info("No category data available.")
            return

        fig = px.bar(
            category_counts,
            x="Category",
            y="Count",
            title="📊 Schemes by Category",
            color="Count",
            color_continuous_scale=["#00E5FF", "#A855F7", "#FF9933"],
            text="Count",
        )

        fig.update_traces(
            textposition="outside",
            textfont=dict(size=11, color="#1F2C34" if is_light else "#FFFFFF"),
            marker=dict(line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>Schemes: %{y}<extra></extra>",
        )

        layout_kwargs = _chart_layout(
            "📊 Schemes by Category",
            "#00E5FF",
            is_light=is_light,
        )
        fig.update_layout(
            **layout_kwargs,
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(l=20, r=20, t=50, b=80),
            xaxis=dict(
                title="",
                tickangle=-45,
                tickfont=dict(size=9),
                showgrid=False,
            ),
            yaxis=dict(
                title=dict(text="Count", font=dict(size=11, color="#8696A0")),
                tickfont=dict(size=10),
                showgrid=True,
                gridcolor="rgba(100, 100, 255, 0.1)",
                zeroline=False,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render category chart: {type(e).__name__}")


# ===========================
# DONUT CHART
# ===========================
def _render_donut_chart(df, is_light):
    """Schemes-by-state donut chart (Top 10 + Others)."""
    if df is None or df.empty or "applicable_state" not in df.columns:
        st.info("No state data available.")
        return

    try:
        # "All" (central schemes) exclude
        state_df = df[df["applicable_state"] != "All"]
        if state_df.empty:
            st.info("No state-specific schemes.")
            return

        state_counts = state_df["applicable_state"].value_counts().reset_index()
        state_counts.columns = ["State", "Count"]

        if state_counts.empty or state_counts["Count"].sum() == 0:
            st.info("No state data available.")
            return

        # Top 10 + Others
        top_10 = state_counts.head(10).copy()
        others_count = state_counts.iloc[10:]["Count"].sum() if len(state_counts) > 10 else 0
        if others_count > 0:
            top_10 = pd.concat(
                [top_10, pd.DataFrame([{"State": "Others", "Count": others_count}])],
                ignore_index=True,
            )

        fig = px.pie(
            top_10,
            values="Count",
            names="State",
            title="🗺️ Schemes by State (Top 10 — Central Excluded)",
            hole=0.5,
            color_discrete_sequence=[
                "#00E5FF", "#A855F7", "#FF9933", "#EC4899", "#00FF88",
                "#FFB648", "#53BDEB", "#F15C6D", "#FF7A45", "#00A884",
                "#8080A0",
            ],
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            textfont=dict(size=10, color="#FFFFFF", family="Poppins"),
            hovertemplate=(
                "<b>%{label}</b><br>Schemes: %{value}<br>"
                "Percentage: %{percent}<extra></extra>"
            ),
            marker=dict(line=dict(color="#0B141A", width=2)),
        )

        layout_kwargs = _chart_layout(
            "🗺️ Schemes by State (Top 10 — Central Excluded)",
            "#A855F7",
            is_light=is_light,
        )
        fig.update_layout(
            **layout_kwargs,
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=10),
                bgcolor="rgba(255,255,255,0.5)" if is_light else "rgba(31, 44, 52, 0.5)",
                bordercolor="#2A3942",
                borderwidth=1,
            ),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.warning(f"Could not render state chart: {type(e).__name__}")


# ===========================
# MAIN DASHBOARD RENDER
# ===========================
def render_dashboard(df, get_urgent_schemes, C, is_light=False):
    """
    Render the full dashboard.

    Args:
        df: Schemes DataFrame (may be None/empty — handled safely)
        get_urgent_schemes: Function to get urgent schemes
        C: Colors dictionary (from app.py)
        is_light: True if Light theme active (for chart theme)
    """
    # ---- Header ----
    st.markdown(
        '<div style="background: linear-gradient(135deg, rgba(0, 229, 255, 0.15), '
        'rgba(168, 85, 247, 0.15), rgba(255, 153, 51, 0.15)); '
        'border-radius: 20px; padding: 25px 30px; margin-bottom: 25px; '
        'border: 1px solid rgba(0, 229, 255, 0.3); '
        'box-shadow: 0 0 30px rgba(0, 229, 255, 0.1);">'
        '<h2 style="color: #FFFFFF; font-family: \'Orbitron\', sans-serif; '
        'font-size: 2rem; margin: 0; text-align: center; '
        'text-shadow: 0 0 20px rgba(0, 229, 255, 0.5);">📊 Dashboard</h2>'
        '<p style="color: #8696A0; text-align: center; margin: 5px 0 0 0; '
        'font-size: 1rem;">Overview of schemes, states, and applications</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ---- Urgent alerts ----
    _render_urgent_alerts(df, get_urgent_schemes, C)
    st.divider()

    # ---- Stats ----
    apps = load_applications()
    _render_stats_cards(df, apps)
    st.write("")
    st.divider()

    # ---- Charts (side by side) ----
    col1, col2 = st.columns(2)
    with col1:
        _render_bar_chart(df, is_light)
    with col2:
        _render_donut_chart(df, is_light)


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("dashboard.py — Verification")
    print("=" * 60)

    # Dummy colors
    C = {
        "glow_cyan": "#00E5FF", "glow_purple": "#A855F7",
        "glow_orange": "#FF9933", "glow_green": "#00FF88",
        "glow_red": "#FF4757",
    }

    # Dummy urgent function
    def dummy_urgent(df, days_threshold=30):
        return [
            {"scheme_name": "Test Scheme", "category_type": "Health",
             "applicable_state": "All", "deadline": "2026-10-15",
             "days_left": 5, "status_text": "5 days left",
             "color": "#FF9933", "apply_link": "https://test.gov.in"},
            {"scheme_name": "Expired Scheme", "category_type": "Education",
             "applicable_state": "All", "deadline": "2026-09-01",
             "days_left": -5, "status_text": "Expired",
             "color": "#FF4757", "apply_link": "https://test.gov.in"},
        ]

    def bad_urgent(df, days_threshold=30):
        return None  # Simulates buggy caller

    def crash_urgent(df, days_threshold=30):
        raise RuntimeError("Simulated failure")

    # Test 1: safe_str
    print("\n[Test 1] safe_str:")
    assert safe_str(None) == ""
    assert safe_str(float("nan")) == ""
    assert safe_str("test") == "test"
    assert safe_str(123) == "123"
    print("  ✅ All safe_str cases pass")

    # Test 2: _is_safe_url
    print("\n[Test 2] _is_safe_url:")
    assert _is_safe_url("https://test.gov.in") is True
    assert _is_safe_url("http://test.gov.in") is True
    assert _is_safe_url("javascript:alert(1)") is False
    assert _is_safe_url("data:text/html,<script>") is False
    assert _is_safe_url("") is False
    assert _is_safe_url(None) is False
    print("  ✅ URL safety check works (javascript:, data: blocked)")

    # Test 3: _escape_attr
    print("\n[Test 3] _escape_attr:")
    assert _escape_attr('test"quote') == "test&quot;quote"
    assert _escape_attr("test<tag>") == "test&lt;tag&gt;"
    print("  ✅ Attribute escaping works")

    # Test 4: _safe_urgent_schemes
    print("\n[Test 4] _safe_urgent_schemes:")
    empty_df = pd.DataFrame()
    assert _safe_urgent_schemes(dummy_urgent, empty_df) == dummy_urgent(empty_df)
    assert _safe_urgent_schemes(bad_urgent, empty_df) == []   # None → []
    assert _safe_urgent_schemes(crash_urgent, empty_df) == []  # Crash → []
    print("  ✅ Handles None return / exception / valid list")

    # Test 5: load_applications with missing file
    print("\n[Test 5] load_applications:")
    apps = load_applications()
    assert isinstance(apps, dict)
    print(f"  ✅ Returns dict: {len(apps)} entries")

    # Test 6: Empty df handling
    print("\n[Test 6] Empty dataframe handling:")
    try:
        # Emulate stats calculation without Streamlit
        df = pd.DataFrame()
        total_schemes = len(df)
        total_states = len(df["applicable_state"].dropna().unique()) if "applicable_state" in df.columns else 0
        total_categories = len(df["category_type"].dropna().unique()) if "category_type" in df.columns else 0
        print(f"  ✅ Empty df: {total_schemes} schemes, {total_states} states, {total_categories} cats")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        raise

    # Test 7: Sample real df
    print("\n[Test 7] Real-shaped dataframe:")
    df = pd.DataFrame([
        {"scheme_name": "A", "category_type": "Health", "applicable_state": "All"},
        {"scheme_name": "B", "category_type": "Health", "applicable_state": "MP"},
        {"scheme_name": "C", "category_type": "Education", "applicable_state": "UP"},
        {"scheme_name": "D", "category_type": "Education", "applicable_state": "All"},
        {"scheme_name": "E", "category_type": "Agriculture", "applicable_state": "MP"},
    ])
    total_states = len(df["applicable_state"].dropna().unique())
    total_categories = len(df["category_type"].dropna().unique())
    print(f"  ✅ Stats: {len(df)} schemes, {total_states} states, {total_categories} categories")

    # Test 8: Donut chart data prep (excluding "All")
    print("\n[Test 8] Donut chart data prep:")
    state_df = df[df["applicable_state"] != "All"]
    assert len(state_df) == 3, f"Expected 3 non-All rows, got {len(state_df)}"
    print(f"  ✅ Excluded 'All' — {len(state_df)} state-specific schemes")

    # Test 9: Bar chart data prep
    print("\n[Test 9] Bar chart data prep:")
    cat_counts = df["category_type"].value_counts().reset_index()
    cat_counts.columns = ["Category", "Count"]
    assert len(cat_counts) == 3
    print(f"  ✅ {len(cat_counts)} category buckets")

    # Test 10: is_light flag default
    print("\n[Test 10] is_light flag:")
    # Just verify signature accepts both
    import inspect
    sig = inspect.signature(render_dashboard)
    params = list(sig.parameters.keys())
    assert "is_light" in params, "is_light parameter missing"
    print(f"  ✅ render_dashboard params: {params}")

    print("\n" + "=" * 60)
    print("✅ dashboard.py — ALL CHECKS PASSED")
    print("=" * 60)