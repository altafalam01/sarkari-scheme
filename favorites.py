"""
Favorites / Bookmarks - local JSON file mein save hoti hain.
"""

import json
import os

FAV_FILE = os.path.join("data", "favorites.json")


def load_favorites():
    if not os.path.exists(FAV_FILE):
        return []
    try:
        with open(FAV_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def is_favorite(scheme_name):
    return scheme_name in load_favorites()


def toggle_favorite(scheme_name):
    favs = load_favorites()
    if scheme_name in favs:
        favs.remove(scheme_name)
        added = False
    else:
        favs.append(scheme_name)
        added = True

    os.makedirs(os.path.dirname(FAV_FILE), exist_ok=True)
    with open(FAV_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)

    return added


if __name__ == "__main__":
    print(toggle_favorite("Test Scheme"))
    print(load_favorites())
    print(toggle_favorite("Test Scheme"))
    print(load_favorites())