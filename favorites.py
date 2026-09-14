"""
favorites.py — Favorites / Bookmarks persistence (local JSON file).

FIXES (v2):
  - Corrupt JSON file ab silently handle hoti hai (crash nahi karta).
  - Missing directory auto-create hoti hai (donon read + write path me).
  - Atomic write (temp file + os.replace) — partial write se file corrupt nahi hoti.
  - Non-string scheme names filter ho jaate hain.
  - Real data ke saath test nahi karta __main__ me.

PERFORMANCE (v4):
  - load_favorites() ab @st.cache_data se cached hai (60 sec TTL).
    Pehle 2 sec tha — paginated rendering mein 2 sec kaafi nahi tha,
    isliye 60 kar diya. Ye OneDrive ki slow I/O problem solve karta hai.
  - Har save ke baad cache automatically clear ho jaata hai.
  - app.py ab is function ko loop ke bahar ek baar call karta hai aur
    sab cards mein pass karta hai (render_scheme_card ke through).
"""

import json
import os
import tempfile
import streamlit as st

FAV_FILE = os.path.join("data", "favorites.json")


# ===========================
# SAFE LOAD (CACHED)
# ===========================
@st.cache_data(ttl=60, show_spinner=False)
def load_favorites():
    """
    Favorites list load karta hai (cached for 60 seconds).
    - File missing → []
    - Corrupt JSON → []  (crash nahi karta, purana data move ho jaata hai)
    - Non-list content → []
    """
    if not os.path.exists(FAV_FILE):
        return []

    try:
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError:
        # Corrupt file → backup le lo taaki user ka data accidentally lose na ho
        _quarantine_corrupt_file()
        return []
    except OSError:
        return []

    if not isinstance(data, list):
        return []

    # Sirf strings rakho (defensive — kabhi corrupted data me int aa jaate hain)
    return [str(x) for x in data if isinstance(x, (str, int, float))]


def _quarantine_corrupt_file():
    """Corrupt favorites.json ko .corrupt extension ke saath rename kar deta hai."""
    try:
        corrupt_path = FAV_FILE + ".corrupt"
        # Agar pehle se .corrupt exists, to timestamp add karo
        if os.path.exists(corrupt_path):
            import time
            corrupt_path = f"{FAV_FILE}.{int(time.time())}.corrupt"
        os.replace(FAV_FILE, corrupt_path)
    except OSError:
        # Quarantine fail ho jaaye to bhi crash nahi karna
        pass


# ===========================
# SAFE SAVE (atomic)
# ===========================
def _save_favorites(favs):
    """
    Favorites list ko JSON file me atomically save karta hai.
    - Directory auto-create
    - Temp file me likh ke os.replace (atomic on POSIX/Windows)
    - Cache clear karta hai taaki next read fresh ho
    """
    parent_dir = os.path.dirname(FAV_FILE)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    # Temp file usi directory me banao (os.replace cross-device fail hota hai)
    dir_path = parent_dir or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".fav_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(favs, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, FAV_FILE)
    except Exception:
        # Kuch bhi fail ho, temp file cleanup karo
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise

    # ✅ Cache clear karo taaki next read fresh ho
    load_favorites.clear()


# ===========================
# PUBLIC API
# ===========================
def is_favorite(scheme_name):
    """Check karta hai ki scheme favorites me hai ya nahi."""
    if not scheme_name:
        return False
    return str(scheme_name) in load_favorites()


def toggle_favorite(scheme_name):
    """
    Favorites me add/remove toggle karta hai.
    Returns: True if added, False if removed.
    """
    if not scheme_name:
        return False

    scheme_name = str(scheme_name)
    favs = load_favorites()

    if scheme_name in favs:
        favs.remove(scheme_name)
        added = False
    else:
        favs.append(scheme_name)
        added = True

    _save_favorites(favs)
    return added


def add_favorite(scheme_name):
    """Explicitly add (idempotent)."""
    if not scheme_name:
        return False
    favs = load_favorites()
    if scheme_name in favs:
        return False
    favs.append(str(scheme_name))
    _save_favorites(favs)
    return True


def remove_favorite(scheme_name):
    """Explicitly remove (idempotent)."""
    if not scheme_name:
        return False
    favs = load_favorites()
    if scheme_name not in favs:
        return False
    favs.remove(scheme_name)
    _save_favorites(favs)
    return True


def clear_favorites():
    """Saare favorites delete karta hai."""
    _save_favorites([])


# ===========================
# SELF-TEST (isolated — real data touch nahi karta)
# ===========================
if __name__ == "__main__":
    # Temp directory me test karo, real data/ folder me nahi
    import shutil

    original_file = FAV_FILE
    test_dir = tempfile.mkdtemp(prefix="fav_test_")
    test_file = os.path.join(test_dir, "favorites.json")

    # Module-level constant patch
    globals()["FAV_FILE"] = test_file

    # ✅ Cache clear karo taaki purana data affect na kare
    load_favorites.clear()

    try:
        print("Initial favorites:", load_favorites())
        assert load_favorites() == []

        print("Add 'Test Scheme':", toggle_favorite("Test Scheme"))
        assert load_favorites() == ["Test Scheme"]

        print("Add again (should remove):", toggle_favorite("Test Scheme"))
        assert load_favorites() == []

        # Corrupt file test
        with open(test_file, "w") as f:
            f.write("NOT VALID JSON {{{")
        load_favorites.clear()  # ✅ Cache clear before corrupt read test
        print("After corrupt write, load_favorites():", load_favorites())
        assert load_favorites() == []

        # Corrupt file quarantine check
        assert os.path.exists(test_file + ".corrupt")

        # Unicode test
        add_favorite("महिला योजना")
        assert "महिला योजना" in load_favorites()
        print("Unicode test passed")

        # Non-string input test
        assert toggle_favorite(None) is False
        assert toggle_favorite("") is False
        print("Non-string input test passed")

        print("\n✅ All favorites.py tests passed")
    finally:
        globals()["FAV_FILE"] = original_file
        load_favorites.clear()  # ✅ Final cache clear
        shutil.rmtree(test_dir, ignore_errors=True)