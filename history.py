"""
Search history - local JSON file mein save hoti hai.
Supports: form, nl, voice modes.
"""

import json
import os
import datetime

HISTORY_FILE = os.path.join("data", "search_history.json")
MAX_ENTRIES = 50


# ===========================
# LOAD / SAVE
# ===========================
def load_history():
    """Saari history load karta hai (newest first)."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_entry(entry: dict):
    """Naya entry save karta hai (newest first, max 50 entries)."""
    history = load_history()
    entry["timestamp"] = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    history.insert(0, entry)
    history = history[:MAX_ENTRIES]

    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def clear_history():
    """Saari history delete karta hai."""
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)


# ===========================
# FILTERED HELPERS (Voice/Form/NL)
# ===========================
def get_voice_history():
    """Sirf voice mode ke entries return karta hai."""
    return [e for e in load_history() if e.get("mode") == "voice"]


def get_form_history():
    """Sirf form mode ke entries return karta hai."""
    return [e for e in load_history() if e.get("mode") == "form"]


def get_nl_history():
    """Sirf natural language mode ke entries return karta hai."""
    return [e for e in load_history() if e.get("mode") == "nl"]


def get_history_by_mode(mode: str):
    """Kisi bhi specific mode ke entries return karta hai."""
    return [e for e in load_history() if e.get("mode") == mode]


def get_history_counts():
    """Har mode ke entries ka count return karta hai."""
    history = load_history()
    counts = {
        "all": len(history),
        "voice": sum(1 for e in history if e.get("mode") == "voice"),
        "form": sum(1 for e in history if e.get("mode") == "form"),
        "nl": sum(1 for e in history if e.get("mode") == "nl"),
    }
    return counts


def clear_voice_history():
    """Sirf voice mode ke entries delete karta hai."""
    history = load_history()
    filtered = [e for e in history if e.get("mode") != "voice"]
    _save_all(filtered)


def clear_form_history():
    """Sirf form mode ke entries delete karta hai."""
    history = load_history()
    filtered = [e for e in history if e.get("mode") != "form"]
    _save_all(filtered)


def clear_nl_history():
    """Sirf NL mode ke entries delete karta hai."""
    history = load_history()
    filtered = [e for e in history if e.get("mode") != "nl"]
    _save_all(filtered)


def _save_all(entries: list):
    """Internal helper — poora history overwrite karta hai."""
    entries = entries[:MAX_ENTRIES]
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


# ===========================
# TEST
# ===========================
if __name__ == "__main__":
    clear_history()
    save_entry({"mode": "form", "age": 25, "state": "Madhya Pradesh",
                "total": 10, "eligible": 6})
    save_entry({"mode": "nl", "query": "scholarship for daughter", "total": 3})
    save_entry({"mode": "voice", "query": "student ke liye scheme",
                "total": 5})
    
    print("--- All History ---")
    for h in load_history():
        print(h)
    
    print("\n--- Counts ---")
    print(get_history_counts())
    
    print("\n--- Voice History ---")
    for h in get_voice_history():
        print(h)