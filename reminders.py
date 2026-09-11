"""
Reminders - user kisi scheme ke liye reminder date set kar sakta hai.
"""

import json
import os
import datetime

REMINDERS_FILE = os.path.join("data", "reminders.json")


def load_reminders():
    if not os.path.exists(REMINDERS_FILE):
        return {}
    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data):
    os.makedirs(os.path.dirname(REMINDERS_FILE), exist_ok=True)
    with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_reminder(scheme_name, date_str, note=""):
    data = load_reminders()
    data[scheme_name] = {"date": date_str, "note": note}
    _save(data)


def remove_reminder(scheme_name):
    data = load_reminders()
    if scheme_name in data:
        del data[scheme_name]
        _save(data)


def get_reminder(scheme_name):
    return load_reminders().get(scheme_name)


def days_remaining(date_str):
    target = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.date.today()
    return (target - today).days


if __name__ == "__main__":
    set_reminder("Test Scheme", "2026-12-31", "Apply before year end")
    print(load_reminders())
    print("Days remaining:", days_remaining("2026-12-31"))
    remove_reminder("Test Scheme")
    print(load_reminders())