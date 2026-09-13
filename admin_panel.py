"""
admin_panel.py — Admin panel for scheme management + web scraping UI.

Features:
  - Sidebar password authentication (st.secrets or env var)
  - 4 tabs: Add Scheme / Edit Scheme / Delete Scheme / Web Scraping
  - Backup file (schemes_original_backup.csv) auto-created on first load
  - Reset-to-original-data feature (with confirmation)

FIXES (v3):
  - All st.success + st.rerun() combos replaced with st.toast() — success
    messages ab user ko dikhte hain (pehle wipe ho jaate the).
  - ADMIN_PASSWORD fallback "altaf123" REMOVED — ab None return hota hai
    agar password configured nahi hai, aur login form clearly message deta hai.
  - _render_edit_tab: row lookup se pehle empty check — IndexError crash fix.
  - _render_delete_tab: widget key mein hash use — collision fix.
  - _render_scraping_tab: unused df param removed.
  - ensure_original_backup: dead FileExistsError handler removed; race-safe
    via tempfile + os.replace pattern.
  - existing_norms: dropna() added (NaN names skip).
  - Cache clear failure ab explicit toast ke saath surface hoti hai.
  - Non-Streamlit context me st.* calls safe.
"""

import os
import re
import shutil
import tempfile
from datetime import datetime

import pandas as pd
import streamlit as st

from web_scraper import render_web_scraper_ui


# ===========================
# CONSTANTS
# ===========================
MAIN_CSV = "data/schemes.csv"
BACKUP_PATH = "data/schemes_original_backup.csv"

SCHEME_COLUMNS = [
    "scheme_name", "category_type", "min_age", "max_age",
    "max_annual_income", "applicable_state", "social_category",
    "occupation", "gender", "description", "benefits",
    "apply_link", "deadline", "form_link",
]


# ===========================
# SAFE HELPERS
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
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def _safe_int(value, default=0):
    """Value → int or default. Handles empty string, whitespace, garbage."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def is_valid_url(value):
    """http:// or https:// only."""
    if not value:
        return False
    value = str(value).strip()
    if not value:
        return False
    return value.startswith("http://") or value.startswith("https://")


def _normalize_name(name):
    """Duplicate check ke liye case-insensitive normalized name."""
    if not name:
        return ""
    n = str(name).lower().strip()
    n = re.sub(r"\s+", " ", n)
    return n


def _safe_toast(message, icon=None):
    """
    st.toast() safely call karta hai (non-Streamlit context safe).
    Returns True on success, False otherwise.
    """
    try:
        kwargs = {}
        if icon:
            kwargs["icon"] = icon
        st.toast(message, **kwargs)
        return True
    except Exception:
        # Non-Streamlit context ya streamlit error — silently skip
        return False


def parse_deadline_safe(raw_value):
    """
    Multiple date formats try karta hai. Returns date or None.

    Supported:
      - YYYY-MM-DD (primary)
      - DD-MM-YYYY
      - DD/MM/YYYY
      - DD Mon YYYY  (e.g. "15 Oct 2026")
      - Mon DD, YYYY  (e.g. "Oct 15, 2026")
    """
    if raw_value is None:
        return None
    try:
        if pd.isna(raw_value):
            return None
    except (TypeError, ValueError):
        pass

    raw_str = str(raw_value).strip()
    if not raw_str or raw_str.lower() in ("none", "null", "nan", "n/a"):
        return None

    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(raw_str, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# ===========================
# ATOMIC CSV WRITE
# ===========================
def _atomic_csv_write(df, path):
    """DataFrame ko CSV me atomically likhta hai (temp file + os.replace)."""
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".csv_", suffix=".tmp", dir=dir_path)
    try:
        os.close(fd)
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
    except Exception:
        _safe_remove(tmp_path)
        raise


# ===========================
# CACHE MANAGEMENT
# ===========================
def _clear_schemes_cache():
    """
    matcher.load_schemes cache clear karta hai.
    Returns: True on success, False on failure.
    """
    try:
        from matcher import load_schemes
        load_schemes.clear()
        return True
    except Exception as e:
        print(f"[admin_panel] Cache clear failed: {e}")
        return False


def save_schemes_data(df):
    """
    Schemes CSV save karta hai + cache clear karta hai.
    Cache clear fail ho to admin ko explicit toast warning.
    """
    _atomic_csv_write(df, MAIN_CSV)
    if not _clear_schemes_cache():
        _safe_toast(
            "⚠️ Schemes saved, but cache clear failed. "
            "Agar naya scheme list me nahi dikhe to app ko restart karein.",
            icon="⚠️",
        )


# ===========================
# BACKUP MANAGEMENT
# ===========================
def ensure_original_backup():
    """
    First-run backup create karta hai (race-safe).
    Agar backup already exists → kuch nahi karta.

    Race-safety: temp file mein copy karo, phir os.replace se atomic
    rename. Agar do processes simultaneously chalein, dono ek hi
    final file ko atomically replace karenge — koi half-written state
    nahi hoga.
    """
    if not os.path.exists(MAIN_CSV):
        return  # Main CSV hi nahi hai, backup ka scope nahi
    if os.path.exists(BACKUP_PATH):
        return  # Already exists

    dir_path = os.path.dirname(BACKUP_PATH) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".bak_", suffix=".tmp", dir=dir_path)
    try:
        os.close(fd)
        shutil.copyfile(MAIN_CSV, tmp_path)
        os.replace(tmp_path, BACKUP_PATH)
    except Exception as e:
        _safe_remove(tmp_path)
        print(f"[admin_panel] Backup creation failed: {e}")


# ===========================
# ADMIN AUTH
# ===========================
def _get_admin_password():
    """
    Password from secrets or env.
    Agar configured nahi hai → None (admin login disabled).
    NOTE: Pehle hardcoded fallback "altaf123" tha — security issue, hata diya.
    """
    try:
        if "ADMIN_PASSWORD" in st.secrets:
            val = st.secrets["ADMIN_PASSWORD"]
            if val:
                return str(val)
    except Exception:
        pass
    env_val = os.environ.get("ADMIN_PASSWORD", "")
    if env_val:
        return env_val
    return None


ADMIN_PASSWORD = _get_admin_password()
MAX_LOGIN_ATTEMPTS = 5


def check_admin():
    """Check karta hai ki user admin hai ya nahi."""
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False
    return st.session_state.is_admin


def login_admin():
    """Sidebar admin login form."""
    with st.sidebar:
        st.markdown("### 🔐 Admin Login")
        if not ADMIN_PASSWORD:
            st.error(
                "Admin password not configured. "
                "Please set ADMIN_PASSWORD in st.secrets or environment variables."
            )
            return

        if "admin_attempts" not in st.session_state:
            st.session_state.admin_attempts = 0

        if st.session_state.admin_attempts >= MAX_LOGIN_ATTEMPTS:
            st.error(
                f"Too many failed attempts ({MAX_LOGIN_ATTEMPTS}). "
                "Please restart the app to try again."
            )
            return

        password = st.text_input(
            "Password", type="password", key="admin_pass"
        )
        if st.button("Login", key="admin_login_btn"):
            if password == ADMIN_PASSWORD:
                st.session_state.is_admin = True
                st.session_state.admin_attempts = 0
                _safe_toast("Login Successful!", icon="✅")
                st.rerun()
            else:
                st.session_state.admin_attempts += 1
                remaining = MAX_LOGIN_ATTEMPTS - st.session_state.admin_attempts
                st.error(f"Incorrect Password! ({remaining} attempts left)")


# ===========================
# LOAD SCHEMES (fresh)
# ===========================
def _load_schemes_fresh():
    """
    Cache bypass karke fresh schemes load karta hai.
    Returns: DataFrame with SCHEME_COLUMNS ensured.
    """
    _clear_schemes_cache()

    df = None
    try:
        from matcher import load_schemes
        df = load_schemes()
    except Exception:
        try:
            df = pd.read_csv(MAIN_CSV)
        except Exception:
            df = pd.DataFrame(columns=SCHEME_COLUMNS)

    # Ensure all expected columns exist
    for col in SCHEME_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[SCHEME_COLUMNS]


# ===========================
# ADD SCHEME TAB
# ===========================
def _render_add_tab(df):
    st.markdown("#### Add New Scheme")
    with st.form("add_scheme_form"):
        scheme_name = st.text_input("Scheme Name *")
        category_type = st.text_input("Category (e.g., Education, Health) *")
        min_age = st.number_input("Min Age", min_value=0, max_value=100, value=18)
        max_age = st.number_input(
            "Max Age (0 = no limit)", min_value=0, max_value=100, value=0
        )
        max_annual_income = st.number_input(
            "Max Annual Income (0 = no limit)", min_value=0, value=0, step=10000
        )
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
            form_link = form_link.strip()

            # Case-insensitive duplicate check (dropna to skip NaN names)
            existing_norms = set(
                _normalize_name(n)
                for n in df["scheme_name"].dropna().astype(str).tolist()
            )

            if not scheme_name:
                errors.append("Scheme Name is required.")
            elif _normalize_name(scheme_name) in existing_norms:
                errors.append(
                    f"A scheme named '{scheme_name}' already exists. "
                    "Choose a unique name."
                )
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
                new_df = pd.DataFrame([new_row])[SCHEME_COLUMNS]
                df_updated = pd.concat([df[SCHEME_COLUMNS], new_df], ignore_index=True)
                save_schemes_data(df_updated)
                # Toast survives st.rerun()
                _safe_toast(f"✅ Scheme '{scheme_name}' added!", icon="✅")
                st.rerun()


# ===========================
# EDIT SCHEME TAB
# ===========================
def _render_edit_tab(df):
    st.markdown("#### Edit Scheme")
    if df.empty:
        st.info("No schemes to edit yet.")
        return

    selected_scheme = st.selectbox(
        "Select Scheme to Edit",
        df["scheme_name"].dropna().unique(),
        key="edit_scheme_select",
    )

    if not selected_scheme:
        return

    # CRASH FIX: empty check before iloc[0]
    filtered = df[df["scheme_name"] == selected_scheme]
    if filtered.empty:
        st.warning(
            "Selected scheme could not be found (data may have changed). "
            "Please refresh."
        )
        return
    row = filtered.iloc[0]

    with st.form("edit_scheme_form"):
        scheme_name = st.text_input(
            "Scheme Name *", value=safe_str(row["scheme_name"])
        )
        category_type = st.text_input(
            "Category *", value=safe_str(row["category_type"])
        )
        min_age = st.number_input(
            "Min Age", min_value=0, max_value=100,
            value=_safe_int(row["min_age"], 0),
        )
        max_age = st.number_input(
            "Max Age (0 = no limit)", min_value=0, max_value=100,
            value=_safe_int(row["max_age"], 0),
        )
        max_annual_income = st.number_input(
            "Max Annual Income (0 = no limit)", min_value=0,
            value=_safe_int(row["max_annual_income"], 0),
            step=10000,
        )
        applicable_state = st.text_input(
            "State *", value=safe_str(row["applicable_state"])
        )
        social_category = st.text_input(
            "Social Category", value=safe_str(row["social_category"])
        )
        occupation = st.text_input(
            "Occupation", value=safe_str(row["occupation"])
        )
        gender = st.text_input("Gender", value=safe_str(row["gender"]))
        description = st.text_area(
            "Description", value=safe_str(row["description"])
        )
        benefits = st.text_area("Benefits", value=safe_str(row["benefits"]))
        apply_link = st.text_input(
            "Apply Link *", value=safe_str(row["apply_link"])
        )

        # Deadline — multi-format parse
        default_deadline = parse_deadline_safe(row.get("deadline"))
        if row.get("deadline") and pd.notna(row.get("deadline")) and default_deadline is None:
            st.caption(
                f"⚠️ Existing deadline ('{safe_str(row.get('deadline'))}') "
                "ek valid date format nahi hai. Neeche sahi date chuno, "
                "ya khaali chhodo."
            )
        deadline = st.date_input(
            "Deadline (optional)", value=default_deadline
        )

        form_link = st.text_input(
            "Form Link (optional)", value=safe_str(row["form_link"])
        )

        submit = st.form_submit_button("Update Scheme")

        if submit:
            errors = []
            scheme_name = scheme_name.strip()
            category_type = category_type.strip()
            applicable_state = applicable_state.strip()
            apply_link = apply_link.strip()
            form_link = form_link.strip()

            # Case-insensitive duplicate check (excluding self)
            other_norms = set(
                _normalize_name(n)
                for n in df.loc[df["scheme_name"] != selected_scheme, "scheme_name"]
                       .dropna().astype(str).tolist()
            )

            if not scheme_name:
                errors.append("Scheme Name is required.")
            elif _normalize_name(scheme_name) in other_norms:
                errors.append(
                    f"Another scheme is already named '{scheme_name}'. "
                    "Choose a unique name."
                )
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
                df.loc[mask, "max_annual_income"] = (
                    max_annual_income if max_annual_income > 0 else ""
                )
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
                _safe_toast(f"✅ Scheme '{scheme_name}' updated!", icon="✅")
                st.rerun()


# ===========================
# DELETE SCHEME TAB
# ===========================
def _render_delete_tab(df):
    st.markdown("#### Delete Scheme")
    if df.empty:
        st.info("No schemes to delete.")
        return

    selected_scheme = st.selectbox(
        "Select Scheme to Delete",
        df["scheme_name"].dropna().unique(),
        key="delete_scheme_select",
    )

    if not selected_scheme:
        return

    # Unique checkbox key per scheme — hash-based to avoid collision
    norm_name = _normalize_name(selected_scheme)
    key_hash = abs(hash(norm_name))
    confirm_key = f"confirm_delete_{key_hash}"
    confirm_delete = st.checkbox(
        f"I understand this will permanently delete '{selected_scheme}'.",
        key=confirm_key,
    )

    if st.button(
        f"🗑️ Delete '{selected_scheme}'",
        type="primary",
        disabled=not confirm_delete,
        key=f"delete_btn_{key_hash}",
    ):
        df_updated = df[df["scheme_name"] != selected_scheme]
        save_schemes_data(df_updated)
        _safe_toast(f"✅ Scheme '{selected_scheme}' deleted!", icon="✅")
        st.rerun()


# ===========================
# WEB SCRAPING + DATA MANAGEMENT TAB
# ===========================
def _render_scraping_tab():
    # Web scraper UI (imported from web_scraper.py)
    try:
        render_web_scraper_ui()
    except Exception as e:
        st.error(f"Web Scraper UI failed to load: {safe_str(e)[:150]}")

    st.divider()
    st.markdown("#### 📂 Data Management")

    col1, col2 = st.columns(2)

    # ---- Download CSV ----
    with col1:
        try:
            csv_data = pd.read_csv(MAIN_CSV).to_csv(index=False)
            st.download_button(
                label="📥 Download CSV File",
                data=csv_data,
                file_name=f"schemes_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="admin_download_csv",
            )
        except Exception:
            st.button(
                "📥 Download CSV File",
                disabled=True,
                use_container_width=True,
                key="admin_download_csv_disabled",
            )

    # ---- Reset to original data ----
    with col2:
        _render_reset_button()


def _render_reset_button():
    """Reset-to-original-data button with 2-step confirmation."""
    if not os.path.exists(BACKUP_PATH):
        st.button(
            "♻️ Reset to Original Data",
            use_container_width=True,
            disabled=True,
            key="admin_reset_data_disabled",
            help=(
                "No backup found yet — a backup is created automatically "
                "the first time the admin panel loads."
            ),
        )
        return

    if "confirm_reset_pending" not in st.session_state:
        st.session_state.confirm_reset_pending = False

    if not st.session_state.confirm_reset_pending:
        if st.button(
            "♻️ Reset to Original Data",
            use_container_width=True,
            key="admin_reset_data",
        ):
            st.session_state.confirm_reset_pending = True
            st.rerun()
    else:
        st.warning(
            f"⚠️ Ye current schemes.csv ko is backup se overwrite karega: "
            f"'{BACKUP_PATH}'"
        )
        confirm = st.checkbox(
            "I understand this action",
            key="admin_confirm_reset",
        )
        rcol1, rcol2 = st.columns(2)

        with rcol1:
            if st.button(
                "Confirm Reset",
                type="primary",
                disabled=not confirm,
                key="admin_confirm_reset_btn",
            ):
                try:
                    backup_df = pd.read_csv(BACKUP_PATH)
                    _atomic_csv_write(backup_df, MAIN_CSV)
                    _clear_schemes_cache()
                    st.session_state.confirm_reset_pending = False
                    _safe_toast("✅ Data reset to original!", icon="✅")
                    st.rerun()
                except Exception as e:
                    st.error(f"Reset failed: {safe_str(e)[:150]}")

        with rcol2:
            if st.button("Cancel", key="admin_cancel_reset_btn"):
                st.session_state.confirm_reset_pending = False
                st.rerun()


# ===========================
# MAIN ADMIN PANEL
# ===========================
def admin_panel():
    """Main admin panel with 4 tabs."""
    st.markdown("### Admin Panel")
    st.caption("Manage schemes (Add/Edit/Delete) and Web Scraping")

    ensure_original_backup()

    # Fresh load (cache bypass)
    df = _load_schemes_fresh()

    tab1, tab2, tab3, tab4 = st.tabs([
        "➕ Add Scheme",
        "✏️ Edit Scheme",
        "🗑️ Delete Scheme",
        "🌐 Web Scraping",
    ])

    with tab1:
        _render_add_tab(df)
    with tab2:
        _render_edit_tab(df)
    with tab3:
        _render_delete_tab(df)
    with tab4:
        _render_scraping_tab()


# ===========================
# WRAPPER
# ===========================
def render_admin_panel():
    """Wrapper: admin auth check + panel."""
    if not check_admin():
        login_admin()
    else:
        admin_panel()
        if st.sidebar.button("Logout", key="admin_logout_btn"):
            st.session_state.is_admin = False
            st.rerun()


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("admin_panel.py — Verification")
    print("=" * 60)

    # Test 1: safe_str
    print("\n[Test 1] safe_str:")
    assert safe_str(None) == ""
    assert safe_str(float("nan")) == ""
    assert safe_str("test") == "test"
    assert safe_str("  ") == ""
    assert safe_str(123) == "123"
    print("  ✅ All safe_str cases pass")

    # Test 2: _safe_int (garbage scraper data)
    print("\n[Test 2] _safe_int:")
    assert _safe_int(None) == 0
    assert _safe_int("") == 0
    assert _safe_int("   ") == 0
    assert _safe_int("abc") == 0
    assert _safe_int("18") == 18
    assert _safe_int("18.5") == 18
    assert _safe_int("18.0") == 18
    assert _safe_int("18abc") == 0
    assert _safe_int(float("nan")) == 0
    print("  ✅ Handles None / empty / whitespace / garbage")

    # Test 3: _normalize_name
    print("\n[Test 3] _normalize_name:")
    assert _normalize_name("PM Kisan") == "pm kisan"
    assert _normalize_name("  PM  KISAN  ") == "pm kisan"
    assert _normalize_name("PM-Kisan!") == "pm-kisan!"
    assert _normalize_name(None) == ""
    assert _normalize_name("") == ""
    print("  ✅ Normalization works (case + whitespace)")

    # Test 4: is_valid_url
    print("\n[Test 4] is_valid_url:")
    assert is_valid_url("https://test.gov.in") is True
    assert is_valid_url("http://test.gov.in") is True
    assert is_valid_url("javascript:alert(1)") is False
    assert is_valid_url("") is False
    assert is_valid_url(None) is False
    assert is_valid_url("none") is False
    print("  ✅ Only http/https accepted")

    # Test 5: parse_deadline_safe (multi-format)
    print("\n[Test 5] parse_deadline_safe:")
    assert parse_deadline_safe("2026-12-31").isoformat() == "2026-12-31"
    assert parse_deadline_safe("31-12-2026").isoformat() == "2026-12-31"
    assert parse_deadline_safe("31/12/2026").isoformat() == "2026-12-31"
    assert parse_deadline_safe("31 Dec 2026").isoformat() == "2026-12-31"
    assert parse_deadline_safe("Dec 31, 2026").isoformat() == "2026-12-31"
    assert parse_deadline_safe(None) is None
    assert parse_deadline_safe("") is None
    assert parse_deadline_safe("garbage") is None
    assert parse_deadline_safe("n/a") is None
    print("  ✅ Multi-format date parsing works")

    # Test 6: _atomic_csv_write
    print("\n[Test 6] _atomic_csv_write:")
    tmpdir = tempfile.mkdtemp(prefix="admin_test_")
    try:
        test_csv = os.path.join(tmpdir, "test.csv")
        df = pd.DataFrame([
            {"scheme_name": "Test 1", "category_type": "Health"},
            {"scheme_name": "Test 2", "category_type": "Education"},
        ])
        _atomic_csv_write(df, test_csv)
        assert os.path.exists(test_csv)
        loaded = pd.read_csv(test_csv)
        assert len(loaded) == 2
        assert "Test 1" in loaded["scheme_name"].values
        print(f"  ✅ Wrote {len(loaded)} rows atomically")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 7: SCHEME_COLUMNS count
    print("\n[Test 7] SCHEME_COLUMNS:")
    assert len(SCHEME_COLUMNS) == 14
    assert "scheme_name" in SCHEME_COLUMNS
    assert "form_link" in SCHEME_COLUMNS
    print(f"  ✅ 14 columns as expected")

    # Test 8: Case-insensitive duplicate check
    print("\n[Test 8] Duplicate check:")
    existing = ["PM Kisan Samman Nidhi", "Ayushman Bharat"]
    existing_norms = set(_normalize_name(n) for n in existing)
    assert _normalize_name("pm kisan samman nidhi") in existing_norms
    assert _normalize_name("  PM KISAN SAMMAN NIDHI  ") in existing_norms
    assert _normalize_name("PM Fasal Bima") not in existing_norms
    print("  ✅ Case-insensitive duplicate detection works")

    # Test 9: ADMIN_PASSWORD fallback removed
    print("\n[Test 9] ADMIN_PASSWORD fallback removed:")
    # When no env var / secret set, should return None (not "altaf123")
    import os as _os
    old_env = _os.environ.pop("ADMIN_PASSWORD", None)
    try:
        # Note: _get_admin_password uses st.secrets which fails outside Streamlit → returns None
        pw = _get_admin_password()
        assert pw is None or pw != "altaf123", (
            f"Password fallback 'altaf123' should be removed, got: {pw}"
        )
        print(f"  ✅ No hardcoded fallback (returned {pw!r})")
    finally:
        if old_env is not None:
            _os.environ["ADMIN_PASSWORD"] = old_env

    # Test 10: _safe_toast in non-Streamlit context
    print("\n[Test 10] _safe_toast non-Streamlit:")
    result = _safe_toast("test message")
    # Should return False (no Streamlit context), not crash
    assert result is False
    print("  ✅ Returns False without crashing")

    print("\n" + "=" * 60)
    print("✅ admin_panel.py — ALL CHECKS PASSED")
    print("=" * 60)