import pandas as pd
import streamlit as st

@st.cache_data
def load_schemes(path="data/schemes.csv"):
    df = pd.read_csv(path)
    return df

def get_all_states(df):
    states = sorted(df["applicable_state"].unique().tolist())
    if "All" in states:
        states.remove("All")
    return ["All"] + states

def get_all_categories(df):
    return sorted(df["category_type"].unique().tolist())

def evaluate_scheme(row, age=None, annual_income=None, gender="All",
                     social_category="All", occupation="All"):
    checks = []
    eligible = True

    # Age check
    if age is not None:
        age_ok = True
        if not pd.isna(row["min_age"]) and age < row["min_age"]:
            age_ok = False
        if not pd.isna(row["max_age"]) and age > row["max_age"]:
            age_ok = False
        if not pd.isna(row["min_age"]) or not pd.isna(row["max_age"]):
            checks.append({"label": "Age", "passed": age_ok})
            if not age_ok:
                eligible = False

    # Income check
    if annual_income is not None and not pd.isna(row["max_annual_income"]):
        income_ok = annual_income <= row["max_annual_income"]
        checks.append({"label": "Income limit", "passed": income_ok})
        if not income_ok:
            eligible = False

    # Gender check
    if row["gender"] != "All":
        gender_ok = (gender == row["gender"]) or (gender == "All")
        checks.append({"label": f"Gender ({row['gender']})", "passed": gender_ok})
        if not gender_ok:
            eligible = False

    # Social category check
    if row["social_category"] != "All":
        allowed = str(row["social_category"]).split("/")
        cat_ok = (social_category in allowed) or (social_category == "All")
        checks.append({"label": f"Category ({row['social_category']})", "passed": cat_ok})
        if not cat_ok:
            eligible = False

    # Occupation check
    if row["occupation"] != "All" and occupation != "All":
        occ_ok = occupation.lower() in str(row["occupation"]).lower()
        checks.append({"label": f"Occupation ({row['occupation']})", "passed": occ_ok})
        if not occ_ok:
            eligible = False

    return eligible, checks

def match_schemes(df, age=None, annual_income=None, gender="All",
                   social_category="All", occupation="All", state="All",
                   category_type="All", only_eligible=False):
    if state != "All":
        candidates = df[(df["applicable_state"] == "All") | (df["applicable_state"] == state)]
    else:
        candidates = df

    if category_type != "All":
        candidates = candidates[candidates["category_type"] == category_type]

    results = []
    for _, row in candidates.iterrows():
        eligible, checks = evaluate_scheme(
            row, age=age, annual_income=annual_income, gender=gender,
            social_category=social_category, occupation=occupation
        )

        if only_eligible and not eligible:
            continue

        results.append({
            "scheme_name": row["scheme_name"],
            "category_type": row["category_type"],
            "applicable_state": row["applicable_state"],
            "description": row["description"],
            "benefits": row["benefits"],
            "apply_link": row["apply_link"],
            "deadline": row.get("deadline", None),
            "eligible": eligible,
            "checks": checks,
        })

    results.sort(key=lambda r: not r["eligible"])
    return results

if __name__ == "__main__":
    df = load_schemes()
    print("States:", get_all_states(df))
    print("Categories:", get_all_categories(df))