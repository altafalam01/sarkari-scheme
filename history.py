"""
history.py — Search history persistence (local JSON file).

FIXES (v2):
  - ORPHAN FILE BUG FIX: purana `data/history.json` detect karke
    `data/search_history.json` me auto-migrate karta hai (ek baar).
  - Corrupt JSON silently handled (quarantine + return []).
  - Atomic write (temp file + os.replace) — partial write se file corrupt nahi hoti.
  - Entry structure validate hoti hai (missing "mode" → skip).
  - Non-list JSON content reject.
  - save_entry() non-dict input reject.
  - Timestamp format consistent: "DD-MM-YYYY HH:MM" (display ke liye),
    but ISO fallback bhi parse ho jaata hai.
  - Clear operations bhi atomic hain.
"""

import json
import os
import tempfile
import datetime

HISTORY_FILE = os.path.join("data", "search_history.json")

# Purana (orphan) file jo kabhi read nahi hoti thi — ek baar migrate kar denge
LEGACY_HISTORY_FILE = os.path.join("data", "history.json")

MAX_ENTRIES = 50


# ===========================
# MIGRATION (one-time)
# ===========================
def _migrate_legacy_file_once():
    """
    Purana `data/history.json` agar exist karta hai aur naya
    `data/search_history.json` nahi, to ek baar migrate kar dete hain.
    Migration ke baad legacy file `.migrated` extension ke saath
    rename ho jaati hai taaki dobara trigger na ho.
    """
    if not os.path.exists(LEGACY_HISTORY_FILE):
        return

    # Agar naya file already exists, to migration skip (data collision avoid)
    if os.path.exists(HISTORY_FILE):
        return

    try:
        with open(LEGACY_HISTORY_FILE, "r", encoding="utf-8") as f:
            legacy_data = json.load(f)
        if isinstance(legacy_data, list):
            _save_all(legacy_data)
            # Migration success → legacy file ko rename karo (delete nahi, safety ke liye)
            os.replace(LEGACY_HISTORY_FILE, LEGACY_HISTORY_FILE + ".migrated")
    except Exception:
        # Migration fail ho jaaye to app crash nahi karna — silently skip
        pass


# ===========================
# CORRUPT FILE QUARANTINE
# ===========================
def _quarantine_corrupt_file():
    """Corrupt history file ko .corrupt extension ke saath rename kar deta hai."""
    try:
        corrupt_path = HISTORY_FILE + ".corrupt"
        if os.path.exists(corrupt_path):
            import time
            corrupt_path = f"{HISTORY_FILE}.{int(time.time())}.corrupt"
        os.replace(HISTORY_FILE, corrupt_path)
    except OSError:
        pass


# ===========================
# ENTRY VALIDATION
# ===========================
def _is_valid_entry(entry):
    """Entry me kam se kam 'mode' hona chahiye (str). Baaki fields optional."""
    if not isinstance(entry, dict):
        return False
    if "mode" not in entry:
        return False
    if not isinstance(entry.get("mode"), str):
        return False
    return True


def _normalize_timestamp(entry):
    """
    Entry me timestamp ko "DD-MM-YYYY HH:MM" format me normalize karta hai
    (agar already hai to chhod deta hai, agar ISO hai to convert karta hai).
    """
    ts = entry.get("timestamp")
    if not ts or not isinstance(ts, str):
        entry["timestamp"] = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
        return entry

    # Try ISO format (2026-09-12T15:58:41.913535)
    try:
        dt = datetime.datetime.fromisoformat(ts)
        entry["timestamp"] = dt.strftime("%d-%m-%Y %H:%M")
        return entry
    except (ValueError, TypeError):
        pass

    # Try "DD-MM-YYYY HH:MM"
    try:
        datetime.datetime.strptime(ts, "%d-%m-%Y %H:%M")
        return entry  # Already correct format
    except (ValueError, TypeError):
        pass

    # Unknown format → override with current
    entry["timestamp"] = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    return entry


# ===========================
# ATOMIC SAVE (internal)
# ===========================
def _save_all(entries):
    """
    Poori history atomically save karta hai.
    - Directory auto-create
    - Temp file + os.replace (atomic swap)
    - MAX_ENTRIES enforce
    """
    if not isinstance(entries, list):
        entries = []

    entries = entries[:MAX_ENTRIES]

    dir_path = os.path.dirname(HISTORY_FILE) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".hist_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, HISTORY_FILE)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


# ===========================
# LOAD / SAVE (public)
# ===========================
def load_history():
    """
    Saari history load karta hai (newest first).
    - Legacy file migrate karta hai (ek baar)
    - Corrupt JSON → []  (crash nahi karta)
    - Invalid entries skip ho jaate hain
    """
    # Ek baar legacy migration check
    _migrate_legacy_file_once()

    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        _quarantine_corrupt_file()
        return []
    except OSError:
        return []

    if not isinstance(data, list):
        return []

    # Sirf valid entries rakho
    valid = [_normalize_timestamp(e) for e in data if _is_valid_entry(e)]
    return valid


def save_entry(entry):
    """
    Naya entry save karta hai (newest first, max 50 entries).
    - entry non-dict → skip (return False)
    - entry me "mode" missing → skip
    """
    if not _is_valid_entry(entry):
        return False

    history = load_history()

    # Timestamp hamesha current rakhna
    entry["timestamp"] = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    history.insert(0, entry)
    history = history[:MAX_ENTRIES]

    _save_all(history)
    return True


def clear_history():
    """Saari history delete karta hai (atomic empty write)."""
    _save_all([])


# ===========================
# FILTERED HELPERS (Voice/Form/NL)
# ===========================
def get_voice_history():
    return [e for e in load_history() if e.get("mode") == "voice"]


def get_form_history():
    return [e for e in load_history() if e.get("mode") == "form"]


def get_nl_history():
    return [e for e in load_history() if e.get("mode") == "nl"]


def get_history_by_mode(mode):
    return [e for e in load_history() if e.get("mode") == mode]


def get_history_counts():
    """Har mode ke entries ka count."""
    history = load_history()
    counts = {
        "all": len(history),
        "voice": sum(1 for e in history if e.get("mode") == "voice"),
        "form": sum(1 for e in history if e.get("mode") == "form"),
        "nl": sum(1 for e in history if e.get("mode") == "nl"),
    }
    return counts


# ===========================
# MODE-SPECIFIC CLEAR
# ===========================
def _clear_by_mode(mode_to_remove):
    history = load_history()
    filtered = [e for e in history if e.get("mode") != mode_to_remove]
    _save_all(filtered)


def clear_voice_history():
    _clear_by_mode("voice")


def clear_form_history():
    _clear_by_mode("form")


def clear_nl_history():
    _clear_by_mode("nl")


# ===========================
# SELF-TEST (isolated)
# ===========================
if __name__ == "__main__":
    import shutil

    original_file = HISTORY_FILE
    original_legacy = LEGACY_HISTORY_FILE
    test_dir = tempfile.mkdtemp(prefix="hist_test_")

    globals()["HISTORY_FILE"] = os.path.join(test_dir, "search_history.json")
    globals()["LEGACY_HISTORY_FILE"] = os.path.join(test_dir, "history.json")

    try:
        # Clean slate
        clear_history()
        assert load_history() == []

        # Basic save
        save_entry({"mode": "form", "age": 25, "state": "MP", "total": 10, "eligible": 6})
        save_entry({"mode": "nl", "query": "scholarship", "total": 3})
        save_entry({"mode": "voice", "query": "kisan loan", "total": 5})

        h = load_history()
        assert len(h) == 3, f"Expected 3, got {len(h)}"
        assert h[0]["mode"] == "voice"  # newest first

        # Counts
        counts = get_history_counts()
        assert counts["all"] == 3
        assert counts["voice"] == 1
        assert counts["form"] == 1
        assert counts["nl"] == 1
        print("Basic save/load/count test passed")

        # Invalid entry test
        assert save_entry(None) is False
        assert save_entry({"no_mode_key": True}) is False
        assert save_entry("not a dict") is False
        print("Invalid entry rejection test passed")

        # Clear by mode
        clear_voice_history()
        counts = get_history_counts()
        assert counts["voice"] == 0
        assert counts["all"] == 2
        print("Clear-by-mode test passed")

        # Corrupt file test
        with open(globals()["HISTORY_FILE"], "w") as f:
            f.write("NOT JSON {{{")
        assert load_history() == []
        print("Corrupt file recovery test passed")

        # Legacy migration test
        globals()["HISTORY_FILE"] = os.path.join(test_dir, "fresh.json")
        legacy_path = globals()["LEGACY_HISTORY_FILE"]
        with open(legacy_path, "w", encoding="utf-8") as f:
            json.dump([{"mode": "form", "age": 30, "timestamp": "01-01-2026 10:00"}], f)

        migrated = load_history()
        assert len(migrated) == 1
        assert migrated[0]["mode"] == "form"
        assert os.path.exists(legacy_path + ".migrated")
        print("Legacy migration test passed")

        print("\n✅ All history.py tests passed")
    finally:
        globals()["HISTORY_FILE"] = original_file
        globals()["LEGACY_HISTORY_FILE"] = original_legacy
        shutil.rmtree(test_dir, ignore_errors=True)