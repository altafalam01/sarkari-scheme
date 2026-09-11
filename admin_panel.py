"""
Admin Panel - Full Featured

"""

import streamlit as st
import pandas as pd
import os
import shutil
from datetime import datetime
from web_scraper import render_web_scraper_ui


# ===========================
# ADMIN AUTHENTICATION
# ===========================
def _get_admin_password():
    """Secrets/env se password lo, warna local-dev fallback use karo.
    Production mein .streamlit/secrets.toml ya ADMIN_PASSWORD env var set karo."""
    try:
        if "ADMIN_PASSWORD" in st.secrets:
            return st.secrets["ADMIN_PASSWORD"]
    except Exception:
        pass
    return os.environ.get("ADMIN_PASSWORD", "altaf123")


ADMIN_PASSWORD = _get_admin_password()


def check_admin():
    """Check if user is admin."""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    return st.session_state.is_admin


def login_admin():
    """Admin login form."""
    with st.sidebar:
        st.markdown("### 🔐 Admin Login")
        if not ADMIN_PASSWORD:
            st.error("Admin password not configured.")
            return

        if "admin_attempts" not in st.session_state:
            st.session_state.admin_attempts = 0

        if st.session_state.admin_attempts >= 5:
            st.error("Too many failed attempts. Please restart the app to try again.")
            return

        password = st.text_input("Password", type="password", key="admin_pass")
        if st.button("Login"):
            if password == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.admin_attempts = 0
                st.success("Login Successful!")
                st.rerun()
            else:
                st.session_state.admin_attempts += 1
                st.error("Incorrect Password!")


# ===========================
# HELPERS
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


def is_valid_url(value):
    """Validate URL."""
    if not value:
        return False
    value = str(value).strip()
    if not value or value.lower() == "none":
        return False
    return value.startswith("http://") or value.startswith("https://")


def parse_deadline_safe(raw_value):
    """Deadline string ko date object mein convert karta hai, agar format
    non-standard/garbage ho (jo scraper se aa sakta hai) to crash nahi
    karta — bas None return karta hai."""
    if raw_value is None:
        return None
    try:
        if pd.isna(raw_value):
            return None
    except (TypeError, ValueError):
        pass
    raw_str = str(raw_value).strip()
    if not raw_str:
        return None
    try:
        return datetime.strptime(raw_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def save_schemes_data(df):
    """Save schemes to CSV."""
    os.makedirs("data", exist_ok=True)
    df.to_csv("data/schemes.csv", index=False)
    # Clear the cache for load_schemes if available
    try:
        from matcher import load_schemes
        load_schemes.clear()
    except Exception:
        pass


BACKUP_PATH = "data/schemes_original_backup.csv"


def ensure_original_backup():
    """Agar backup abhi tak exist nahi karta aur schemes.csv maujood hai,
    to ek baar ka backup bana do (pehli baar admin panel load hone par)."""
    if os.path.exists("data/schemes.csv") and not os.path.exists(BACKUP_PATH):
        try:
            os.makedirs("data", exist_ok=True)
            shutil.copyfile("data/schemes.csv", BACKUP_PATH)
        except Exception:
            pass


# ===========================
# ADMIN PANEL (MAIN)
# ===========================
def admin_panel():
    """Main admin panel with 4 tabs."""
    st.markdown("### Admin Panel")
    st.caption("Manage schemes (Add/Edit/Delete) and Web Scraping")

    ensure_original_backup()

    # Load schemes
    try:
        from matcher import load_schemes
        df = load_schemes()
    except Exception:
        try:
            df = pd.read_csv("data/schemes.csv")
        except Exception:
            df = pd.DataFrame(columns=[
                "scheme_name", "category_type", "min_age", "max_age",
                "max_annual_income", "applicable_state", "social_category",
                "occupation", "gender", "description", "benefits",
                "apply_link", "deadline", "form_link"
            ])

    # Admin Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Add Scheme", "✏️ Edit Scheme", "🗑️ Delete Scheme", "🌐 Web Scraping"])

    # ===========================
    # TAB 1: ADD SCHEME
    # ===========================
    with tab1:
        st.markdown("#### Add New Scheme")
        with st.form("add_scheme_form"):
            scheme_name = st.text_input("Scheme Name *")
            category_type = st.text_input("Category (e.g., Education, Health) *")
            min_age = st.number_input("Min Age", min_value=0, max_value=100, value=18)
            max_age = st.number_input("Max Age (0 = no limit)", min_value=0, max_value=100, value=0)
            max_annual_income = st.number_input("Max Annual Income (0 = no limit)", min_value=0, value=0, step=10000)
            applicable_state = st.text_input("State (All for central) *")
            social_category = st.text_input("Social Category (e.g., SC/ST/OBC/All)")
            occupation = st.text_input("Occupation (e.g., Farmer/Student/All)")
            gender = st.text_input("Gender (Male/Female/All)")
            description = st.text_area("Description")
            benefits = st.text_area("Benefits")
            apply_link = st.text_input("Apply Link (https://...) *")
            deadline = st.date_input("Deadline (optional)", value=None)
            form_link = st.text_input("Form Link (optional)")

            submit = st.form_submit_button("Add Scheme")

            if submit:
                errors = []
                scheme_name = scheme_name.strip()
                category_type = category_type.strip()
                applicable_state = applicable_state.strip()
                apply_link = apply_link.strip()

                if not scheme_name:
                    errors.append("Scheme Name is required.")
                elif scheme_name in set(df["scheme_name"].astype(str)):
                    errors.append(f"A scheme named '{scheme_name}' already exists. Choose a unique name.")
                if not category_type:
                    errors.append("Category is required.")
                if not applicable_state:
                    errors.append("State is required.")
                if not is_valid_url(apply_link):
                    errors.append("Apply Link must be a valid http(s) URL.")
                if form_link and not is_valid_url(form_link):
                    errors.append("Form Link must be a valid http(s) URL, or left blank.")

                if errors:
                    for err in errors:
                        st.error(err)
                else:
                    new_row = {
                        "scheme_name": scheme_name,
                        "category_type": category_type,
                        "min_age": min_age if min_age > 0 else "",
                        "max_age": max_age if max_age > 0 else "",
                        "max_annual_income": max_annual_income if max_annual_income > 0 else "",
                        "applicable_state": applicable_state,
                        "social_category": social_category.strip(),
                        "occupation": occupation.strip(),
                        "gender": gender.strip(),
                        "description": description.strip(),
                        "benefits": benefits.strip(),
                        "apply_link": apply_link,
                        "deadline": deadline.isoformat() if deadline else "",
                        "form_link": form_link,
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_schemes_data(df)
                    st.success(f"✅ Scheme '{scheme_name}' added successfully!")
                    st.rerun()

    # ===========================
    # TAB 2: EDIT SCHEME
    # ===========================
    with tab2:
        st.markdown("#### Edit Scheme")
        if df.empty:
            st.info("No schemes to edit yet.")
        else:
            selected_scheme = st.selectbox("Select Scheme to Edit", df["scheme_name"].unique())

            if selected_scheme:
                row = df[df["scheme_name"] == selected_scheme].iloc[0]

                with st.form("edit_scheme_form"):
                    scheme_name = st.text_input("Scheme Name *", value=row["scheme_name"])
                    category_type = st.text_input("Category *", value=row["category_type"])
                    min_age = st.number_input(
                        "Min Age", min_value=0, max_value=100,
                        value=int(row["min_age"]) if pd.notna(row["min_age"]) and str(row["min_age"]).strip() != "" else 0
                    )
                    max_age = st.number_input(
                        "Max Age (0 = no limit)", min_value=0, max_value=100,
                        value=int(row["max_age"]) if pd.notna(row["max_age"]) and str(row["max_age"]).strip() != "" else 0
                    )
                    max_annual_income = st.number_input(
                        "Max Annual Income (0 = no limit)", min_value=0,
                        value=int(row["max_annual_income"]) if pd.notna(row["max_annual_income"]) and str(row["max_annual_income"]).strip() != "" else 0,
                        step=10000
                    )
                    applicable_state = st.text_input("State *", value=row["applicable_state"])
                    social_category = st.text_input("Social Category", value=safe_str(row["social_category"]))
                    occupation = st.text_input("Occupation", value=safe_str(row["occupation"]))
                    gender = st.text_input("Gender", value=safe_str(row["gender"]))
                    description = st.text_area("Description", value=safe_str(row["description"]))
                    benefits = st.text_area("Benefits", value=safe_str(row["benefits"]))
                    apply_link = st.text_input("Apply Link *", value=row["apply_link"])

                    # FIX: raw/non-standard deadline strings (jo scraper se aa sakti
                    # hain) ab crash nahi karengi — parse fail hone par field khaali
                    # dikhega, poora Edit tab nahi tootega.
                    default_deadline = parse_deadline_safe(row.get("deadline"))
                    if row.get("deadline") and pd.notna(row.get("deadline")) and default_deadline is None:
                        st.caption(
                            f"⚠️ Existing deadline value ('{safe_str(row.get('deadline'))}') ek valid "
                            "YYYY-MM-DD date nahi hai (shayad scraper se raw text aayi hai). "
                            "Neeche sahi date chuno taaki fix ho jaaye, ya khaali chhodo."
                        )
                    deadline = st.date_input("Deadline (optional)", value=default_deadline)

                    form_link = st.text_input("Form Link (optional)", value=safe_str(row["form_link"]))

                    submit = st.form_submit_button("Update Scheme")

                    if submit:
                        errors = []
                        scheme_name = scheme_name.strip()
                        category_type = category_type.strip()
                        applicable_state = applicable_state.strip()
                        apply_link = apply_link.strip()

                        other_names = set(df.loc[df["scheme_name"] != selected_scheme, "scheme_name"].astype(str))

                        if not scheme_name:
                            errors.append("Scheme Name is required.")
                        elif scheme_name in other_names:
                            errors.append(f"Another scheme is already named '{scheme_name}'. Choose a unique name.")
                        if not category_type:
                            errors.append("Category is required.")
                        if not applicable_state:
                            errors.append("State is required.")
                        if not is_valid_url(apply_link):
                            errors.append("Apply Link must be a valid http(s) URL.")
                        if form_link and not is_valid_url(form_link):
                            errors.append("Form Link must be a valid http(s) URL, or left blank.")

                        if errors:
                            for err in errors:
                                st.error(err)
                        else:
                            mask = df["scheme_name"] == selected_scheme
                            df.loc[mask, "scheme_name"] = scheme_name
                            df.loc[mask, "category_type"] = category_type
                            df.loc[mask, "min_age"] = min_age if min_age > 0 else ""
                            df.loc[mask, "max_age"] = max_age if max_age > 0 else ""
                            df.loc[mask, "max_annual_income"] = max_annual_income if max_annual_income > 0 else ""
                            df.loc[mask, "applicable_state"] = applicable_state
                            df.loc[mask, "social_category"] = social_category.strip()
                            df.loc[mask, "occupation"] = occupation.strip()
                            df.loc[mask, "gender"] = gender.strip()
                            df.loc[mask, "description"] = description.strip()
                            df.loc[mask, "benefits"] = benefits.strip()
                            df.loc[mask, "apply_link"] = apply_link
                            df.loc[mask, "deadline"] = deadline.isoformat() if deadline else ""
                            df.loc[mask, "form_link"] = form_link
                            save_schemes_data(df)
                            st.success(f"✅ Scheme '{scheme_name}' updated successfully!")
                            st.rerun()

    # ===========================
    # TAB 3: DELETE SCHEME
    # ===========================
    with tab3:
        st.markdown("#### Delete Scheme")
        if df.empty:
            st.info("No schemes to delete.")
        else:
            selected_scheme = st.selectbox("Select Scheme to Delete", df["scheme_name"].unique(), key="delete_scheme")

            confirm_delete = st.checkbox(f"I understand this will permanently delete '{selected_scheme}'.", key="confirm_delete")
            if st.button(f"🗑️ Delete '{selected_scheme}'", type="primary", disabled=not confirm_delete):
                df = df[df["scheme_name"] != selected_scheme]
                save_schemes_data(df)
                st.success(f"✅ Scheme '{selected_scheme}' deleted successfully!")
                st.rerun()

    # ===========================
    # TAB 4: WEB SCRAPING
    # ===========================
    # FIX: pehle yahan ek custom render_web_scraping_section() tha jo:
    #  - run_web_scraper() ka return value galat treat karta tha (sirf
    #    naye STAGED candidates count karta tha, "Total schemes" nahi),
    #  - staging-review / "Add to schemes.csv" UI provide nahi karta tha,
    #  - apna disconnected st.session_state-based auto-scrape checkbox
    #    rakhta tha jo web_scraper.py ke JSON schedule-state se link nahi
    #    tha (restart hone par silently reset ho jaata, kuch schedule
    #    nahi karta).
    # Ab seedha web_scraper.py ka poora-featured UI use ho raha hai, jisme
    # ye sab already correctly implemented hai (staging review, filters,
    # selective "Add to schemes.csv", real schedule-state persistence,
    # fetch-log diagnostics).
    with tab4:
        render_web_scraper_ui()

        st.divider()
        st.markdown("#### 📂 Data Management")

        col1, col2 = st.columns(2)
        with col1:
            try:
                st.download_button(
                    label="📥 Download CSV File",
                    data=pd.read_csv("data/schemes.csv").to_csv(index=False),
                    file_name=f"schemes_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key="admin_download_csv"
                )
            except Exception:
                st.button("📥 Download CSV File", disabled=True, use_container_width=True)

        with col2:
            # FIX: ab actually restore karta hai backup se, pehle sirf
            # fake success message dikha ke kuch nahi karta tha.
            if os.path.exists(BACKUP_PATH):
                if "confirm_reset_pending" not in st.session_state:
                    st.session_state.confirm_reset_pending = False

                if not st.session_state.confirm_reset_pending:
                    if st.button("♻️ Reset to Original Data", use_container_width=True, key="admin_reset_data"):
                        st.session_state.confirm_reset_pending = True
                        st.rerun()
                else:
                    st.warning(
                        "⚠️ Ye current schemes.csv ko is backup se overwrite karega: "
                        f"'{BACKUP_PATH}' (jo pehli admin-panel load par saved hua tha)."
                    )
                    confirm = st.checkbox("I understand this action", key="admin_confirm_reset")
                    rcol1, rcol2 = st.columns(2)
                    with rcol1:
                        if st.button("Confirm Reset", type="primary", disabled=not confirm, key="admin_confirm_reset_btn"):
                            shutil.copyfile(BACKUP_PATH, "data/schemes.csv")
                            try:
                                from matcher import load_schemes
                                load_schemes.clear()
                            except Exception:
                                pass
                            st.session_state.confirm_reset_pending = False
                            st.success("✅ Data reset to original!")
                            st.rerun()
                    with rcol2:
                        if st.button("Cancel", key="admin_cancel_reset_btn"):
                            st.session_state.confirm_reset_pending = False
                            st.rerun()
            else:
                st.button(
                    "♻️ Reset to Original Data", use_container_width=True, disabled=True,
                    key="admin_reset_data_disabled",
                    help="No backup found yet — a backup is created automatically the first time the admin panel loads.",
                )


# ===========================
# WRAPPER: RENDER ADMIN PANEL
# ===========================
def render_admin_panel():
    """Wrapper: Check admin access and render admin panel."""
    if not check_admin():
        login_admin()
    else:
        admin_panel()
        if st.sidebar.button("Logout"):
            st.session_state.is_admin = False
            st.rerun()