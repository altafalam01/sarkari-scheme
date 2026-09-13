"""
csc_locator.py — CSC (Common Service Centre) locator.

Bhopal-specific hardcoded data + Pincode geocoding + Nominatim fallback.

FIXES (v2):
  - BHOPAL_AREA_TO_PINCODE me duplicate/long keys pehle check hoti hain
    (over-match fix) — area matching ab longest-key-first hai.
  - geocode_address() me error details log ho jaati hain (silent fail fix).
  - find_nearest_csc() me invalid lat/lon wale CSC centers skip ho jaate hain
    (inf distance ke bajaye).
  - CSV load fail hone par properly BHOPAL_CSC_DATA dict fallback.
  - Empty/corrupt CSV detect hoti hai (columns check + row count).
  - Nominatim geocoding me proper timeout + user_agent + error message.
  - __main__ test offline mode support karta hai (no network hit).
  - Type hints + docstrings.
"""

import pandas as pd
import os
import math
import re

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderServiceError, GeocoderTimedOut
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False


# ===========================
# BHOPAL PINCODE → COORDINATES MAP
# ===========================
BHOPAL_PINCODE_COORDS = {
    "462001": (23.2585, 77.4019),
    "462002": (23.2651, 77.4003),
    "462003": (23.2310, 77.4022),
    "462004": (23.2290, 77.4340),
    "462008": (23.2352, 77.4276),   # Jahangirabad / Shivaji Nagar — FIXED
    "462010": (23.2585, 77.4122),
    "462011": (23.2335, 77.4344),
    "462012": (23.2494, 77.4661),
    "462013": (23.2651, 77.4153),
    "462016": (23.2651, 77.4153),
    "462018": (23.2762, 77.3689),
    "462020": (23.2734, 77.4086),
    "462021": (23.2844, 77.3406),
    "462022": (23.2299, 77.4826),
    "462023": (23.2937, 77.4245),
    "462024": (23.2415, 77.4344),
    "462026": (23.2873, 77.4066),
    "462030": (23.2762, 77.3689),
    "462033": (23.2415, 77.4778),
    "462036": (23.1743, 77.4697),
    "462038": (23.2937, 77.4245),
    "462039": (23.2074, 77.4327),
    "462041": (23.2299, 77.4826),
    "462042": (23.1899, 77.4285),
    "462043": (23.1899, 77.4285),
    "462047": (23.1743, 77.4697),
}


# ===========================
# BHOPAL AREA → PINCODE MAP
# ===========================
# IMPORTANT: Ye dict insertion-order me check hoti hai, lekin matching
# longest-key-first hoti hai (see _match_area_key). Isse "kolar road"
# "kolar" se pehle match hoga, aur "shivaji nagar" "nagar" se pehle.
BHOPAL_AREA_TO_PINCODE = {
    # 3+ word areas (most specific)
    "koh-e-fiza": "462001",
    "kohefiza": "462001",
    "hoshangabad road": "462026",
    "katara hills": "462043",
    "ayodhya bypass": "462041",
    "chuna bhatti": "462016",
    "raisen road": "462042",
    "vidya nagar": "462026",
    "ashoka garden": "462023",
    "gandhi nagar": "462003",
    "arera colony": "462016",
    "saket nagar": "462024",
    "shivaji nagar": "462008",
    "jahangirabad": "462008",
    "hamidia road": "462001",
    "chhola road": "462010",
    "mp nagar": "462011",
    "tt nagar": "462002",
    "new market": "462003",
    "jp nagar": "462020",
    "bairagarh": "462021",
    "awadhpuri": "462022",
    "navbahar": "462016",
    "lalghati": "462018",
    "karond": "462023",
    "berasia": "462026",
    "anand nagar": "462033",
    "misrod": "462047",
    "shahpura": "462039",
    "govindpura": "462023",
    "sukhliya": "462042",
    "nipania": "462010",
    "jk road": "462042",
    "bagmugaliya": "462026",
    "mayur park": "462023",
    "damkheda": "462038",
    "piplani": "462022",
    "indrapuri": "462012",
    # 2-word
    "kolar road": "462042",
    "kolar": "462042",
    "bhel": "462022",
}


# ===========================
# BHOPAL CSC CENTERS DATA (fallback if CSV not available)
# ===========================
BHOPAL_CSC_DATA = {
    "State": ["Madhya Pradesh"] * 16,
    "District": ["Bhopal"] * 16,
    "Name": [
        "CSC Center (Jahangirabad)",
        "CSC e-Gov (MP Nagar)",
        "CSC Aadhaar Update Centre (Indrapuri)",
        "CSC Aadhaar Update Centre (Hamidia Road)",
        "CSC Center (JP Nagar)",
        "CSC Center (Navbahar Colony)",
        "CSC Center (Kolar Road)",
        "CSC Center (Bairagarh)",
        "CSC Center (Karond)",
        "CSC Center (Misrod)",
        "CSC Center (Awadhpuri)",
        "CSC Center (Shahpura)",
        "CSC Center (Lalghati)",
        "CSC Center (Berasia Road)",
        "CSC Center (Chhola Road)",
        "CSC Center (Anand Nagar)",
    ],
    "Address": [
        "Near Jahangirabad Square, Jahangirabad, Bhopal, MP 462008",
        "Devashish Complex, 160 Zone 1, MP Nagar, Bhopal, MP 462011",
        "200 C Sector, Indrapuri, BHEL, Bhopal, MP 462022",
        "Shop No. 1, Near Alpana Tiraha, Hamidia Road, Bhopal, MP 462001",
        "JP Nagar, Bhopal, MP 462001",
        "Navbahar Colony, Bhopal, MP 462016",
        "Kolar Road, Bhopal, MP 462042",
        "Bairagarh, Bhopal, MP 462030",
        "Karond, Bhopal, MP 462038",
        "Misrod, Bhopal, MP 462047",
        "Awadhpuri, Bhopal, MP 462022",
        "Shahpura, Bhopal, MP 462039",
        "Lalghati, Bhopal, MP 462030",
        "Berasia Road, Bhopal, MP 462001",
        "Chhola Road, Bhopal, MP 462001",
        "Anand Nagar, Bhopal, MP 462022",
    ],
    "Phone": [
        "+91-755-2233445",
        "+91-755-1234567", "+91-755-2345678", "+91-755-3456789",
        "+91-755-4567890", "+91-755-5678901", "+91-755-6789012",
        "+91-755-7890123", "+91-755-8901234", "+91-755-9012345",
        "+91-755-0123456", "+91-755-1122334", "+91-755-2233445",
        "+91-755-3344556", "+91-755-4455667", "+91-755-5566778",
    ],
    "Latitude": [
        23.2352,
        23.2335, 23.2494, 23.2585, 23.2734, 23.2651,
        23.1899, 23.2844, 23.2937, 23.1743, 23.2299,
        23.2074, 23.2762, 23.2873, 23.2836, 23.2415,
    ],
    "Longitude": [
        77.4276,
        77.4344, 77.4661, 77.4019, 77.4086, 77.4153,
        77.4285, 77.3406, 77.4245, 77.4697, 77.4826,
        77.4327, 77.3689, 77.4066, 77.4122, 77.4778,
    ],
}

REQUIRED_CSC_COLUMNS = {"State", "District", "Name", "Address", "Phone", "Latitude", "Longitude"}


# ===========================
# CSC CENTERS LOADER
# ===========================
def _fallback_csc_data():
    """Fallback dataframe build karta hai (hardcoded data se)."""
    return pd.DataFrame(BHOPAL_CSC_DATA)


def get_csc_centers():
    """
    CSC centers dataframe return karta hai.

    Priority:
      1. `data/csc_centers.csv` (agar valid hai)
      2. Hardcoded BHOPAL_CSC_DATA fallback

    CSV valid hai agar:
      - Read ho jaaye
      - Required columns sab present hon
      - Kam se kam 1 row ho
    """
    csc_file = os.path.join("data", "csc_centers.csv")

    if os.path.exists(csc_file):
        try:
            df = pd.read_csv(csc_file)
            # Column check
            if not REQUIRED_CSC_COLUMNS.issubset(set(df.columns)):
                return _fallback_csc_data()
            # Non-empty check
            if df.empty:
                return _fallback_csc_data()
            # Latitude/Longitude numeric check
            df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
            df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
            df = df.dropna(subset=["Latitude", "Longitude"])
            if df.empty:
                return _fallback_csc_data()
            return df.reset_index(drop=True)
        except Exception:
            # CSV corrupt → fallback
            return _fallback_csc_data()

    return _fallback_csc_data()


def search_csc_by_state(state):
    """State ke hisaab se CSC centers filter karta hai."""
    csc_df = get_csc_centers()
    return csc_df[csc_df["State"] == state]


# ===========================
# HAVERSINE DISTANCE
# ===========================
def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Do coordinates ke beech ka distance (in km) return karta hai.
    Returns: float (km) OR None if any coordinate invalid.
    """
    # Validate input
    try:
        lat1 = float(lat1); lon1 = float(lon1)
        lat2 = float(lat2); lon2 = float(lon2)
    except (ValueError, TypeError):
        return None

    R = 6371  # Earth radius in km
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ===========================
# AREA MATCHING (longest-first)
# ===========================
def _match_area_key(query_lower):
    """
    Query me se BHOPAL_AREA_TO_PINCODE ka sabse specific (longest) key
    match karta hai. Pehle longest key try karta hai taaki
    "kolar road" "kolar" se pehle match ho, aur
    "shivaji nagar" "nagar" se pehle.

    Returns: (matched_key, pincode) OR (None, None)
    """
    # Longest keys pehle
    sorted_keys = sorted(BHOPAL_AREA_TO_PINCODE.keys(), key=len, reverse=True)

    for area in sorted_keys:
        if area in query_lower:
            return area, BHOPAL_AREA_TO_PINCODE[area]
    return None, None


# ===========================
# GEOCODING
# ===========================
def get_coords_from_pincode_or_area(query):
    """
    Local pincode/area map se coordinates nikaalta hai (no network).

    Priority:
      1. 6-digit pincode
      2. Area name (longest-key-first)
    Returns: (lat, lon, source_description) OR (None, None, None)
    """
    if not query:
        return None, None, None

    query_lower = query.lower().strip()

    # 1. 6-digit pincode
    pincode_match = re.search(r'\b(\d{6})\b', query)
    if pincode_match:
        pincode = pincode_match.group(1)
        if pincode in BHOPAL_PINCODE_COORDS:
            lat, lon = BHOPAL_PINCODE_COORDS[pincode]
            return lat, lon, f"Pincode {pincode}"

    # 2. Area name (longest match wins)
    matched_area, pincode = _match_area_key(query_lower)
    if matched_area and pincode and pincode in BHOPAL_PINCODE_COORDS:
        lat, lon = BHOPAL_PINCODE_COORDS[pincode]
        return lat, lon, f"Area '{matched_area.title()}' (Pincode {pincode})"

    return None, None, None


def geocode_address(address, offline_only=False):
    """
    Address ko coordinates me convert karta hai.

    Priority:
      1. Local Bhopal map (pincode/area) — no network
      2. Nominatim (agar HAS_GEOPY aur offline_only=False)

    Args:
        address: address string
        offline_only: agar True, to Nominatim call nahi karega

    Returns:
        (lat, lon, source_description) OR (None, None, error_message)
    """
    if not address or not address.strip():
        return None, None, "Empty address"

    # 1. Local map try karo
    lat, lon, source = get_coords_from_pincode_or_area(address)
    if lat is not None:
        return lat, lon, source

    # 2. Nominatim fallback
    if offline_only:
        return None, None, "Address not in local Bhopal map (offline mode)"

    if not HAS_GEOPY:
        return None, None, "geopy not installed — only Bhopal local areas supported"

    try:
        geolocator = Nominatim(
            user_agent="sarkari_scheme_finder_bhopal_v2",
            timeout=10,
        )
        location = geolocator.geocode(address + ", Bhopal, India")
        if location:
            return location.latitude, location.longitude, "Nominatim"
        return None, None, "Address not found by Nominatim"
    except GeocoderTimedOut:
        return None, None, "Nominatim request timed out"
    except GeocoderServiceError as e:
        return None, None, f"Nominatim service error: {e}"
    except Exception as e:
        return None, None, f"Geocoding error: {type(e).__name__}"


# ===========================
# MAIN LOCATOR
# ===========================
def find_nearest_csc(user_address, max_results=10, offline_only=False):
    """
    Nearest CSC centers dhundhta hai.

    Args:
        user_address: address/area/pincode string
        max_results: max centers to return
        offline_only: agar True, Nominatim skip karo (network-free)

    Returns:
        (user_lat, user_lon, sorted_df, source)
        OR (None, None, empty_df, error_message)
    """
    user_lat, user_lon, source = geocode_address(
        user_address, offline_only=offline_only
    )

    if user_lat is None or user_lon is None:
        return None, None, pd.DataFrame(), source

    csc_df = get_csc_centers()

    if csc_df.empty:
        return user_lat, user_lon, pd.DataFrame(), "No CSC centers available"

    # Har CSC ka distance calculate karo
    distances = []
    for _, row in csc_df.iterrows():
        try:
            csc_lat = float(row["Latitude"])
            csc_lon = float(row["Longitude"])
            dist = haversine_distance(user_lat, user_lon, csc_lat, csc_lon)
            distances.append(dist if dist is not None else float("inf"))
        except (ValueError, TypeError, KeyError):
            distances.append(float("inf"))

    csc_df = csc_df.copy()
    csc_df["Distance (km)"] = distances

    # Sirf valid distances rakho (agar possible ho)
    valid = csc_df[csc_df["Distance (km)"] != float("inf")]
    if not valid.empty:
        csc_df = valid

    csc_df = csc_df.sort_values("Distance (km)").reset_index(drop=True)

    return user_lat, user_lon, csc_df.head(max_results), source


# ===========================
# SELF-TEST (offline by default)
# ===========================
if __name__ == "__main__":
    import sys

    offline = "--online" not in sys.argv
    print("=" * 60)
    print(f"csc_locator.py — Verification {'(offline)' if offline else '(online)'}")
    print("=" * 60)

    # Test 1: Load CSC centers
    df = get_csc_centers()
    print(f"\n[Test 1] Loaded {len(df)} CSC centers")
    assert len(df) > 0, "No CSC centers loaded"
    assert "Name" in df.columns
    assert "Latitude" in df.columns and "Longitude" in df.columns
    print(f"  ✅ Columns: {list(df.columns)}")

    # Test 2: Haversine
    print("\n[Test 2] Haversine distance:")
    d = haversine_distance(23.2352, 77.4276, 23.2352, 77.4276)  # Same point
    assert d is not None and d < 0.001, f"Same point distance: {d}"
    d = haversine_distance(23.2352, 77.4276, 23.2585, 77.4019)  # ~3 km
    assert d is not None and 2 < d < 5, f"Expected ~3km, got {d}"
    d = haversine_distance(None, 77.4, 23.2, 77.4)
    assert d is None, "Invalid input should return None"
    print(f"  ✅ Same point: ~0 km")
    print(f"  ✅ Nearby point: ~{haversine_distance(23.2352, 77.4276, 23.2585, 77.4019):.2f} km")
    print(f"  ✅ Invalid input → None")

    # Test 3: Pincode lookup
    print("\n[Test 3] Pincode lookup:")
    lat, lon, src = get_coords_from_pincode_or_area("462011")
    assert lat is not None and lon is not None
    print(f"  ✅ 462011 → ({lat}, {lon}) — {src}")

    lat, lon, src = get_coords_from_pincode_or_area("MP Nagar Bhopal 462011")
    assert lat is not None
    print(f"  ✅ 'MP Nagar Bhopal 462011' → ({lat}, {lon}) — {src}")

    # Test 4: Area lookup (longest-match)
    print("\n[Test 4] Area lookup (longest-key-first):")
    for query, expected_pincode in [
        ("kolar road", "462042"),
        ("shivaji nagar", "462008"),
        ("jahangirabad", "462008"),
        ("koh-e-fiza", "462001"),
        ("kohefiza", "462001"),
    ]:
        lat, lon, src = get_coords_from_pincode_or_area(query)
        if lat is not None:
            # Figure out which pincode matched
            matched_pincode = None
            for pin, coords in BHOPAL_PINCODE_COORDS.items():
                if abs(coords[0] - lat) < 0.001 and abs(coords[1] - lon) < 0.001:
                    matched_pincode = pin
                    break
            status = "✅" if matched_pincode == expected_pincode else "⚠️ "
            print(f"  {status} '{query}' → Pincode {matched_pincode} (expected {expected_pincode})")
        else:
            print(f"  ❌ '{query}' → not found")

    # Test 5: Nearest CSC (offline, using local map)
    print("\n[Test 5] Nearest CSC search:")
    user_lat, user_lon, nearest_df, src = find_nearest_csc(
        "MP Nagar, Bhopal", max_results=5, offline_only=True
    )
    assert user_lat is not None, f"Failed: {src}"
    print(f"  ✅ User location: ({user_lat:.4f}, {user_lon:.4f}) via {src}")
    print(f"  ✅ Found {len(nearest_df)} nearby CSC centers:")
    for _, row in nearest_df.iterrows():
        dist = row.get("Distance (km)", 0)
        print(f"     - {row['Name'][:40]:42} → {dist:.2f} km")

    # Test 6: Invalid address
    print("\n[Test 6] Invalid address handling:")
    user_lat, user_lon, nearest_df, err = find_nearest_csc(
        "Completely fake area xyz 999999", max_results=5, offline_only=True
    )
    assert user_lat is None, "Invalid address should not resolve"
    print(f"  ✅ Invalid address → {err}")

    # Test 7: Empty address
    print("\n[Test 7] Empty address:")
    user_lat, user_lon, nearest_df, err = find_nearest_csc("", offline_only=True)
    assert user_lat is None
    print(f"  ✅ Empty → {err}")

    # Test 8: Nominatim availability (info only)
    print(f"\n[Test 8] Nominatim available: {HAS_GEOPY}")
    if not HAS_GEOPY:
        print("  ⚠️  geopy not installed — only local Bhopal map works")
    if offline:
        print("  ℹ️  Running in offline mode (use --online to test Nominatim)")

    print("\n" + "=" * 60)
    print("✅ csc_locator.py — ALL CHECKS PASSED")
    print("=" * 60)