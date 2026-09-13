"""
reminders.py — Reminders persistence (local JSON file).

PERFORMANCE (v2):
  - load_reminders() ab @st.cache_data se cached hai (2 sec TTL).
  - Ye OneDrive ki slow I/O problem solve karta hai.
  - Har save ke baad cache automatically clear ho jaata hai.
"""

import json
import os
import datetime
import streamlit as st

REMINDERS_FILE = os.path.join("data", "reminders.json")


# ===========================
# SAFE LOAD (CACHED)
# ===========================
@st.cache_data(ttl=2, show_spinner=False)
def load_reminders():
    """
    Saare reminders load karta hai (cached for 2 seconds).
    Returns: dict {scheme_name: {"date": "YYYY-MM-DD", "note": "..."}}
    """
    if not os.path.exists(REMINDERS_FILE):
        return {}
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}
    return data


# ===========================
# SAFE SAVE (atomic + cache clear)
# ===========================
def _save(data):
    """Reminders ko atomically save karta hai aur cache clear karta hai."""
    parent_dir = os.path.dirname(REMINDERS_FILE)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ✅ Cache clear karo taaki next read fresh ho
    load_reminders.clear()


# ===========================
# PUBLIC API
# ===========================
def set_reminder(scheme_name, date_str, note=""):
    """Ek scheme ke liye reminder set karta hai."""
    if not scheme_name:
        return
    data = load_reminders()
    data[str(scheme_name)] = {"date": date_str, "note": note}
    _save(data)


def remove_reminder(scheme_name):
    """Reminder hataata hai."""
    if not scheme_name:
        return
    data = load_reminders()
    if scheme_name in data:
        del data[scheme_name]
        _save(data)


def get_reminder(scheme_name):
    """Ek scheme ka reminder return karta hai (ya None)."""
    if not scheme_name:
        return None
    return load_reminders().get(scheme_name)


def days_remaining(date_str):
    """Aaj se target date tak kitne din bache hain."""
    try:
        target = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        today = datetime.date.today()
        return (target - today).days
    except (ValueError, TypeError):
        return 0


def clear_all_reminders():
    """Saare reminders delete karta hai."""
    _save({})


# ===========================
# SELF-TEST (isolated — real data touch nahi karta)
# ===========================
if __name__ == "__main__":
    import shutil
    import tempfile

    original_file = REMINDERS_FILE
    test_dir = tempfile.mkdtemp(prefix="rem_test_")
    test_file = os.path.join(test_dir, "reminders.json")

    globals()["REMINDERS_FILE"] = test_file
    load_reminders.clear()

    try:
        print("Initial reminders:", load_reminders())
        assert load_reminders() == {}

        set_reminder("Test Scheme", "2026-12-31", "Apply before year end")
        print("After set:", load_reminders())
        assert "Test Scheme" in load_reminders()

        print("Days remaining:", days_remaining("2026-12-31"))

        remove_reminder("Test Scheme")
        print("After remove:", load_reminders())
        assert load_reminders() == {}

        print("\n✅ All reminders.py tests passed")
    finally:
        globals()["REMINDERS_FILE"] = original_file
        load_reminders.clear()
        shutil.rmtree(test_dir, ignore_errors=True)