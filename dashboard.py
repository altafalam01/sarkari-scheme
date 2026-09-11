"""
Dashboard Module
- Attractive, modern dashboard with colorful stat cards
- Bar chart with gradient + donut chart with top 10 states
- Urgent deadline alerts
"""

import streamlit as st
import html
import pandas as pd
import plotly.express as px
import os
import json


# ===========================
# HELPERS (Dashboard-specific)
# ===========================
def safe_str(value, default=""):
    """Guard against NaN/None/non-str values."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def load_applications():
    """Load applications from JSON."""
    if os.path.exists("data/applications.json"):
        with open("data/applications.json", "r") as f:
            return json.load(f)
    return {}


# ===========================
# MAIN DASHBOARD RENDER
# ===========================
def render_dashboard(df, get_urgent_schemes, C):
    """
    Render the full dashboard.
    
    Args:
        df: Schemes DataFrame
        get_urgent_schemes: Function to get urgent schemes (from app.py)
        C: Colors dictionary
    """
    
    # ===========================
    # HEADER
    # ===========================
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(168, 85, 247, 0.15), rgba(255, 153, 51, 0.15));
        border-radius: 20px;
        padding: 25px 30px;
        margin-bottom: 25px;
        border: 1px solid rgba(0, 229, 255, 0.3);
        backdrop-filter: blur(10px);
        box-shadow: 0 0 30px rgba(0, 229, 255, 0.1);
    ">
        <h2 style="
            color: #FFFFFF;
            font-family: 'Orbitron', sans-serif;
            font-size: 2rem;
            margin: 0;
            text-align: center;
            text-shadow: 0 0 20px rgba(0, 229, 255, 0.5);
        ">📊 Dashboard</h2>
        <p style="
            color: #8696A0;
            text-align: center;
            margin: 5px 0 0 0;
            font-size: 1rem;
        ">Overview of schemes, states, and applications</p>
    </div>
    """, unsafe_allow_html=True)

    # ===========================
    # URGENT DEADLINE ALERTS
    # ===========================
    urgent_schemes = get_urgent_schemes(df, days_threshold=30)

    if urgent_schemes:
        st.markdown("### 🔴 Urgent Deadline Alerts")
        st.caption("Ye schemes jald hi band ho rahi hain. Aaj hi apply karein!")

        for u in urgent_schemes[:5]:
            color = u["color"]
            if u["days_left"] < 0:
                emoji = "❌"
            elif u["days_left"] == 0:
                emoji = "🚨"
            elif u["days_left"] <= 7:
                emoji = "🔥"
            else:
                emoji = "⚠️"

            st.markdown(
                f'<div class="scheme-card" style="border-left: 6px solid {color};">'
                f'<span class="chip" style="background-color:rgba(255,71,87,0.2); color:{color}; border:1px solid {color};">{emoji} {html.escape(u["status_text"])}</span>'
                f'<h4 style="margin:8px 0 4px 0;">{html.escape(u["scheme_name"])}</h4>'
                f'<p class="card-desc">{html.escape(u["category_type"])} | {html.escape(u["applicable_state"])}</p>'
                f'<p class="card-desc"><b>Apply:</b> <a href="{u["apply_link"]}" target="_blank" style="color:{C["glow_cyan"]};">{html.escape(u["apply_link"])}</a></p>'
                f'</div>',
                unsafe_allow_html=True
            )
            st.write("")
    else:
        st.success("✅ No urgent deadlines right now!")

    st.divider()

    # ===========================
    # STATS CARDS (Attractive)
    # ===========================
    total_schemes = len(df)
    total_states = len(df["applicable_state"].dropna().unique()) if "applicable_state" in df.columns else 0
    total_categories = len(df["category_type"].dropna().unique()) if "category_type" in df.columns else 0
    apps = load_applications()

    col1, col2, col3, col4 = st.columns(4)

    stats_data = [
        ("📋", "Total Schemes", total_schemes, "#00E5FF"),
        ("🗺️", "States", total_states, "#A855F7"),
        ("📂", "Categories", total_categories, "#FF9933"),
        ("📝", "Applications", len(apps), "#00FF88"),
    ]

    for col, (icon, label, value, color) in zip([col1, col2, col3, col4], stats_data):
        with col:
            st.markdown(f"""
            <div style="
                background: linear-gradient(135deg, rgba(31, 44, 52, 0.8), rgba(20, 30, 40, 0.9));
                border: 1px solid {color};
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                box-shadow: 0 0 20px {color}33, inset 0 0 20px {color}11;
                transition: all 0.3s ease;
            ">
                <div style="font-size: 2rem; margin-bottom: 5px;">{icon}</div>
                <div style="
                    font-size: 2.2rem;
                    font-weight: 800;
                    color: {color};
                    text-shadow: 0 0 15px {color}88;
                    font-family: 'Orbitron', sans-serif;
                ">{value}</div>
                <div style="
                    font-size: 0.8rem;
                    color: #8696A0;
                    letter-spacing: 1.5px;
                    text-transform: uppercase;
                    margin-top: 5px;
                ">{label}</div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    st.divider()

    # ===========================
    # CHARTS
    # ===========================
    col1, col2 = st.columns(2)

    # ---- Bar Chart (Attractive) ----
    with col1:
        category_counts = df["category_type"].value_counts().reset_index()
        category_counts.columns = ["Category", "Count"]

        fig = px.bar(
            category_counts,
            x="Category",
            y="Count",
            title="📊 Schemes by Category",
            color="Count",
            color_continuous_scale=["#00E5FF", "#A855F7", "#FF9933"],
            text="Count"
        )

        fig.update_traces(
            textposition="outside",
            textfont=dict(size=11, color="#FFFFFF"),
            marker=dict(line=dict(width=0)),
            hovertemplate="<b>%{x}</b><br>Schemes: %{y}<extra></extra>"
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            coloraxis_showscale=False,
            font=dict(family="Poppins, sans-serif", size=11, color="#E9EDEF"),
            title=dict(font=dict(size=16, color="#00E5FF"), x=0.5, xanchor="center"),
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
                zeroline=False
            ),
            hoverlabel=dict(
                bgcolor="#1F2C34",
                font_size=12,
                font_family="Poppins",
                bordercolor="#00E5FF"
            )
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---- Donut Chart (Top 10 + Others, "All" excluded) ----
    with col2:
        # ✅ "All" (central schemes) ko exclude karo
        state_df = df[df["applicable_state"] != "All"]
        state_counts = state_df["applicable_state"].value_counts().reset_index()
        state_counts.columns = ["State", "Count"]

        top_10 = state_counts.head(10).copy()
        others_count = state_counts.iloc[10:]["Count"].sum()
        if others_count > 0:
            top_10 = pd.concat([
                top_10,
                pd.DataFrame([{"State": "Others", "Count": others_count}])
            ], ignore_index=True)

        fig = px.pie(
            top_10,
            values="Count",
            names="State",
            title="🗺️ Schemes by State (Top 10 — Central Excluded)",
            hole=0.5,
            color_discrete_sequence=[
                "#00E5FF", "#A855F7", "#FF9933", "#EC4899", "#00FF88",
                "#FFB648", "#53BDEB", "#F15C6D", "#FF7A45", "#00A884",
                "#8080A0"
            ]
        )

        fig.update_traces(
            textposition="inside",
            textinfo="percent",
            textfont=dict(size=10, color="#FFFFFF", family="Poppins"),
            hovertemplate="<b>%{label}</b><br>Schemes: %{value}<br>Percentage: %{percent}<extra></extra>",
            marker=dict(line=dict(color="#0B141A", width=2))
        )

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Poppins, sans-serif", size=11, color="#E9EDEF"),
            title=dict(font=dict(size=16, color="#A855F7"), x=0.5, xanchor="center"),
            margin=dict(l=20, r=20, t=50, b=20),
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=10),
                bgcolor="rgba(31, 44, 52, 0.5)",
                bordercolor="#2A3942",
                borderwidth=1
            ),
            hoverlabel=dict(
                bgcolor="#1F2C34",
                font_size=12,
                font_family="Poppins",
                bordercolor="#A855F7"
            )
        )
        st.plotly_chart(fig, use_container_width=True)