"""
reminders.py — Per-scheme reminder dates persistence (local JSON file).

Data structure:
    {
        "Scheme Name": {"date": "YYYY-MM-DD", "note": "optional note"},
        ...
    }

FIXES (v2):
  - Corrupt JSON silently handled (quarantine + return {}).
  - Non-dict entries skip ho jaate hain.
  - Missing directory auto-create (donon read + write path me).
  - Atomic write (temp file + os.replace).
  - days_remaining() invalid date pe None return karta hai (crash nahi karta).
  - set_reminder() date format validate karta hai (YYYY-MM-DD).
  - Entry me "date" missing ho to skip.
  - Non-string scheme names filter.
  - Isolated __main__ test (real data touch nahi karta).
"""

import json
import os
import tempfile
import datetime

REMINDERS_FILE = os.path.join("data", "reminders.json")


# ===========================
# CORRUPT FILE QUARANTINE
# ===========================
def _quarantine_corrupt_file():
    """Corrupt reminders file ko .corrupt extension ke saath rename kar deta hai."""
    try:
        corrupt_path = REMINDERS_FILE + ".corrupt"
        if os.path.exists(corrupt_path):
            import time
            corrupt_path = f"{REMINDERS_FILE}.{int(time.time())}.corrupt"
        os.replace(REMINDERS_FILE, corrupt_path)
    except OSError:
        pass


# ===========================
# ENTRY VALIDATION
# ===========================
def _is_valid_reminder_entry(entry):
    """Reminder entry me kam se kam 'date' (str, YYYY-MM-DD) hona chahiye."""
    if not isinstance(entry, dict):
        return False
    date_val = entry.get("date")
    if not isinstance(date_val, str):
        return False
    # Date format validate karo
    try:
        datetime.datetime.strptime(date_val, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def _is_valid_date_string(date_str):
    """Check karta hai ki date_str YYYY-MM-DD format me valid hai ya nahi."""
    if not isinstance(date_str, str):
        return False
    try:
        datetime.datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


# ===========================
# ATOMIC SAVE
# ===========================
def _save(data):
    """
    Poora reminders dict atomically save karta hai.
    - Directory auto-create
    - Temp file + os.replace (atomic swap)
    """
    if not isinstance(data, dict):
        data = {}

    dir_path = os.path.dirname(REMINDERS_FILE) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".rem_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, REMINDERS_FILE)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


# ===========================
# LOAD
# ===========================
def load_reminders():
    """
    Saare reminders load karta hai.
    - File missing → {}
    - Corrupt JSON → {}  (crash nahi karta, purana quarantine hota hai)
    - Non-dict content → {}
    - Invalid entries skip ho jaate hain
    """
    if not os.path.exists(REMINDERS_FILE):
        return {}

    try:
        with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        _quarantine_corrupt_file()
        return {}
    except OSError:
        return {}

    if not isinstance(data, dict):
        return {}

    # Sirf valid entries rakho
    cleaned = {}
    for scheme_name, entry in data.items():
        if not isinstance(scheme_name, str):
            continue
        if _is_valid_reminder_entry(entry):
            cleaned[scheme_name] = {
                "date": entry["date"],
                "note": str(entry.get("note", "")) if entry.get("note") else "",
            }
    return cleaned


# ===========================
# PUBLIC API
# ===========================
def set_reminder(scheme_name, date_str, note=""):
    """
    Reminder set karta hai.
    Returns: True if successful, False if invalid input.
    """
    if not scheme_name or not isinstance(scheme_name, str):
        return False
    if not _is_valid_date_string(date_str):
        return False

    scheme_name = scheme_name.strip()
    if not scheme_name:
        return False

    data = load_reminders()
    data[scheme_name] = {
        "date": date_str,
        "note": str(note).strip() if note else "",
    }
    _save(data)
    return True


def remove_reminder(scheme_name):
    """
    Reminder remove karta hai.
    Returns: True if removed, False if not found.
    """
    if not scheme_name:
        return False
    data = load_reminders()
    if scheme_name in data:
        del data[scheme_name]
        _save(data)
        return True
    return False


def get_reminder(scheme_name):
    """Ek scheme ka reminder return karta hai, ya None."""
    if not scheme_name:
        return None
    return load_reminders().get(scheme_name)


def days_remaining(date_str):
    """
    Diye gaye date string ka aaj se kitne din bache hain.
    Returns: int (positive = future, negative = overdue, 0 = today)
             None if date invalid.
    """
    if not _is_valid_date_string(date_str):
        return None
    try:
        target = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    today = datetime.date.today()
    return (target - today).days


def get_all_reminders_sorted():
    """
    Saare reminders sorted by date (soonest first).
    Returns: list of (scheme_name, entry_dict, days_remaining_or_None)
    """
    data = load_reminders()
    result = []
    for scheme_name, entry in data.items():
        days = days_remaining(entry["date"])
        result.append((scheme_name, entry, days))
    # Sort: valid days first (ascending), invalid days last
    result.sort(key=lambda x: (x[2] is None, x[2] if x[2] is not None else 999999))
    return result


def clear_all_reminders():
    """Saare reminders delete karta hai."""
    _save({})


# ===========================
# SELF-TEST (isolated)
# ===========================
if __name__ == "__main__":
    import shutil

    original_file = REMINDERS_FILE
    test_dir = tempfile.mkdtemp(prefix="rem_test_")
    globals()["REMINDERS_FILE"] = os.path.join(test_dir, "reminders.json")

    try:
        # Clean slate
        clear_all_reminders()
        assert load_reminders() == {}

        # Basic set/get
        assert set_reminder("Test Scheme", "2026-12-31", "Apply before year end") is True
        r = get_reminder("Test Scheme")
        assert r is not None
        assert r["date"] == "2026-12-31"
        assert r["note"] == "Apply before year end"
        print("Basic set/get test passed")

        # Invalid date test
        assert set_reminder("Bad Scheme", "31-12-2026") is False  # Wrong format
        assert set_reminder("Bad Scheme", "not-a-date") is False
        assert set_reminder("Bad Scheme", None) is False
        assert get_reminder("Bad Scheme") is None
        print("Invalid date rejection test passed")

        # Invalid scheme name
        assert set_reminder("", "2026-12-31") is False
        assert set_reminder(None, "2026-12-31") is False
        print("Invalid scheme name rejection test passed")

        # days_remaining
        d = days_remaining("2026-12-31")
        assert d is not None
        assert isinstance(d, int)
        assert days_remaining("invalid") is None
        print("days_remaining test passed")

        # Multiple reminders sorted
        set_reminder("Scheme A", "2026-12-01")
        set_reminder("Scheme B", "2026-06-01")
        set_reminder("Scheme C", "2026-09-01")
        sorted_list = get_all_reminders_sorted()
        # Verify sorted by date ascending
        dates = [entry["date"] for _, entry, _ in sorted_list]
        assert dates == sorted(dates), f"Not sorted: {dates}"
        print("Sort test passed")

        # Remove
        assert remove_reminder("Test Scheme") is True
        assert remove_reminder("Test Scheme") is False  # Already removed
        assert get_reminder("Test Scheme") is None
        print("Remove test passed")

        # Corrupt file recovery
        with open(globals()["REMINDERS_FILE"], "w") as f:
            f.write("NOT JSON {{{")
        assert load_reminders() == {}
        print("Corrupt file recovery test passed")

        # Non-dict content
        with open(globals()["REMINDERS_FILE"], "w") as f:
            json.dump(["not", "a", "dict"], f)
        assert load_reminders() == {}
        print("Non-dict content rejection test passed")

        # Invalid entry skip
        with open(globals()["REMINDERS_FILE"], "w") as f:
            json.dump({
                "Good": {"date": "2026-12-31", "note": "ok"},
                "Bad": {"date": "invalid", "note": ""},
                "NoDate": {"note": "missing date"},
                "NotDict": "string entry",
            }, f)
        loaded = load_reminders()
        assert "Good" in loaded
        assert "Bad" not in loaded
        assert "NoDate" not in loaded
        assert "NotDict" not in loaded
        print("Invalid entry skip test passed")

        print("\n✅ All reminders.py tests passed")
    finally:
        globals()["REMINDERS_FILE"] = original_file
        shutil.rmtree(test_dir, ignore_errors=True)