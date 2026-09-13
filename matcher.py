"""
matcher.py — Rule-based eligibility matching engine.

FIXES (v2):
  - Empty string "" ab properly blank detect hota hai (pd.isna("") = False hota hai,
    isliye _is_blank() helper banaya).
  - row["min_age"] direct access ki jagah .get() + safe conversion —
    missing column par KeyError nahi aayega.
  - Age/Income float conversion errors silently handled.
  - form_link field properly return hoti hai (app.py isko use karta hai).
"""

import pandas as pd
import streamlit as st


# ===========================
# SAFE CONVERSION HELPERS
# ===========================
def _is_blank(value):
    """Check karta hai ki value None / NaN / empty-string hai ya nahi.
    Note: pd.isna("") → False hota hai, isliye empty string ko bhi
    explicitly check karte hain."""
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _safe_int(value):
    """Value ko int me convert karta hai; blank/invalid ho to None deta hai."""
    if _is_blank(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value):
    """Value ko float me convert karta hai; blank/invalid ho to None deta hai."""
    if _is_blank(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ===========================
# CACHE LOADER
# ===========================
@st.cache_data
def load_schemes(path="data/schemes.csv"):
    """Schemes CSV load karta hai (cached). Admin panel save ke baad
    load_schemes.clear() call karta hai taaki fresh data mile."""
    df = pd.read_csv(path)
    return df


def get_all_states(df):
    """Dropdown ke liye sorted states list (with 'All' at front)."""
    if df is None or df.empty or "applicable_state" not in df.columns:
        return ["All"]
    states = sorted(df["applicable_state"].dropna().unique().tolist())
    if "All" in states:
        states.remove("All")
    return ["All"] + states


def get_all_categories(df):
    """Unique scheme categories."""
    if df is None or df.empty or "category_type" not in df.columns:
        return []
    return sorted(df["category_type"].dropna().unique().tolist())


# ===========================
# ELIGIBILITY EVALUATION
# ===========================
def evaluate_scheme(row, age=None, annual_income=None, gender="All",
                     social_category="All", occupation="All"):
    """
    Ek scheme row ko evaluate karta hai.
    Returns: (eligible: bool, checks: list_of_dicts)
    Har check: {"label": str, "passed": bool}
    """
    checks = []
    eligible = True

    # ---- Age check ----
    if age is not None:
        min_age = _safe_int(row.get("min_age"))
        max_age = _safe_int(row.get("max_age"))
        age_ok = True
        if min_age is not None and age < min_age:
            age_ok = False
        if max_age is not None and age > max_age:
            age_ok = False
        # Sirf tab check add karo jab scheme me koi age limit ho
        if min_age is not None or max_age is not None:
            checks.append({"label": "Age", "passed": age_ok})
            if not age_ok:
                eligible = False

    # ---- Income check ----
    if annual_income is not None:
        max_income = _safe_float(row.get("max_annual_income"))
        # Sirf tab check karo jab scheme me income limit defined ho (blank = no limit)
        if max_income is not None:
            try:
                income_ok = float(annual_income) <= max_income
            except (ValueError, TypeError):
                income_ok = True  # Invalid user income → skip check
            checks.append({"label": "Income limit", "passed": income_ok})
            if not income_ok:
                eligible = False

    # ---- Gender check ----
    scheme_gender = str(row.get("gender", "All")).strip() or "All"
    if scheme_gender != "All":
        gender_ok = (gender == scheme_gender) or (gender == "All")
        checks.append({"label": f"Gender ({scheme_gender})", "passed": gender_ok})
        if not gender_ok:
            eligible = False

    # ---- Social category check ----
    scheme_cat = str(row.get("social_category", "All")).strip() or "All"
    if scheme_cat != "All":
        allowed = [c.strip() for c in scheme_cat.split("/") if c.strip()]
        # Multiple categories (SC/ST/OBC) — koi ek match kaafi hai
        cat_ok = (social_category in allowed) or (social_category == "All")
        checks.append({"label": f"Category ({scheme_cat})", "passed": cat_ok})
        if not cat_ok:
            eligible = False

    # ---- Occupation check ----
    scheme_occ = str(row.get("occupation", "All")).strip() or "All"
    if scheme_occ != "All" and occupation != "All":
        # Case-insensitive substring match (e.g. "Farmer" in "Small Farmer")
        occ_ok = occupation.lower() in scheme_occ.lower()
        checks.append({"label": f"Occupation ({scheme_occ})", "passed": occ_ok})
        if not occ_ok:
            eligible = False

    return eligible, checks


# ===========================
# MAIN MATCHER
# ===========================
def match_schemes(df, age=None, annual_income=None, gender="All",
                   social_category="All", occupation="All", state="All",
                   category_type="All", only_eligible=False):
    """
    Saare filters apply karke matching schemes return karta hai.
    Har result dict me: scheme details + eligible flag + checks list.
    """
    if df is None or df.empty:
        return []

    # ---- State filter ----
    if state != "All":
        candidates = df[(df["applicable_state"] == "All") | (df["applicable_state"] == state)]
    else:
        candidates = df

    # ---- Category filter ----
    if category_type != "All":
        candidates = candidates[candidates["category_type"] == category_type]

    results = []
    for _, row in candidates.iterrows():
        eligible, checks = evaluate_scheme(
            row, age=age, annual_income=annual_income, gender=gender,
            social_category=social_category, occupation=occupation
        )

        # Agar "only eligible" checked hai aur scheme eligible nahi, to skip
        if only_eligible and not eligible:
            continue

        results.append({
            "scheme_name": row.get("scheme_name", ""),
            "category_type": row.get("category_type", ""),
            "applicable_state": row.get("applicable_state", "All"),
            "description": row.get("description", ""),
            "benefits": row.get("benefits", ""),
            "apply_link": row.get("apply_link", ""),
            "deadline": row.get("deadline", None),
            "form_link": row.get("form_link", None),
            "eligible": eligible,
            "checks": checks,
        })

    # Eligible schemes pehle, phir baaki
    results.sort(key=lambda r: not r["eligible"])
    return results


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    df = load_schemes()
    print("States:", get_all_states(df))
    print("Categories:", get_all_categories(df))

    # Test: empty string income bug
    sample = pd.DataFrame([{
        "scheme_name": "Test Scheme",
        "category_type": "Test",
        "min_age": "",
        "max_age": "",
        "max_annual_income": "",  # Empty string — bug reproducer
        "applicable_state": "All",
        "social_category": "All",
        "occupation": "All",
        "gender": "All",
        "description": "Test",
        "benefits": "Test",
        "apply_link": "https://test.com",
        "deadline": "",
        "form_link": "",
    }])
    res = match_schemes(sample, age=25, annual_income=100000)
    print("Empty-string income test passed:", len(res) == 1)