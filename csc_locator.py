"""
CSC (Common Service Centre) locator — Bhopal-specific with Pincode-based geocoding.
"""

import pandas as pd
import os
import math
import re

try:
    from geopy.geocoders import Nominatim
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
    "462008": (23.2415, 77.4344),   # Shivaji Nagar / Jahangirabad
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
BHOPAL_AREA_TO_PINCODE = {
    "mp nagar": "462011",
    "tt nagar": "462002",
    "new market": "462003",
    "shivaji nagar": "462008",
    "jahangirabad": "462008",
    "hamidia road": "462001",
    "chhola road": "462010",
    "indrapuri": "462012",
    "navbahar": "462016",
    "lalghati": "462018",
    "jp nagar": "462020",
    "bairagarh": "462021",
    "awadhpuri": "462022",
    "bhel": "462022",
    "karond": "462023",
    "berasia": "462026",
    "anand nagar": "462033",
    "misrod": "462047",
    "shahpura": "462039",
    "kolar": "462042",
    "gandhi nagar": "462003",
    "arera colony": "462016",
    "habibganj": "462024",
    "koh-e-fiza": "462001",
    "kohefiza": "462001",
    "ashoka garden": "462023",
    "govindpura": "462023",
    "saket nagar": "462024",
    "piplani": "462022",
    "sukhliya": "462042",
    "nipania": "462010",
    "jk road": "462042",
    "hoshangabad road": "462026",
    "katara hills": "462043",
    "ayodhya bypass": "462041",
    "bagmugaliya": "462026",
    "chuna bhatti": "462016",
    "raisen road": "462042",
    "vidya nagar": "462026",
    "damkheda": "462038",
    "mayur park": "462023",
}


# ===========================
# BHOPAL CSC CENTERS DATA (16 centers, including Jahangirabad)
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
        23.2352,   # Jahangirabad
        23.2335, 23.2494, 23.2585, 23.2734, 23.2651,
        23.1899, 23.2844, 23.2937, 23.1743, 23.2299,
        23.2074, 23.2762, 23.2873, 23.2836, 23.2415,
    ],
    "Longitude": [
        77.4276,   # Jahangirabad
        77.4344, 77.4661, 77.4019, 77.4086, 77.4153,
        77.4285, 77.3406, 77.4245, 77.4697, 77.4826,
        77.4327, 77.3689, 77.4066, 77.4122, 77.4778,
    ],
}


def get_csc_centers():
    """Returns CSC centers dataframe."""
    csc_file = os.path.join("data", "csc_centers.csv")
    
    if os.path.exists(csc_file):
        try:
            df = pd.read_csv(csc_file)
            if "Latitude" not in df.columns or "Longitude" not in df.columns:
                df = pd.DataFrame(BHOPAL_CSC_DATA)
            return df
        except Exception:
            pass
    
    return pd.DataFrame(BHOPAL_CSC_DATA)


def search_csc_by_state(state):
    csc_df = get_csc_centers()
    return csc_df[csc_df["State"] == state]


# ===========================
# HAVERSINE DISTANCE
# ===========================
def haversine_distance(lat1, lon1, lat2, lon2):
    """Do coordinates ke beech ka distance (in km) return karta hai."""
    R = 6371
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
# GEOCODING (Pincode/Area first, Nominatim fallback)
# ===========================
def get_coords_from_pincode_or_area(query):
    """Local map se coordinates nikaalta hai."""
    if not query:
        return None, None, None
    
    query_lower = query.lower().strip()
    
    # 1) 6-digit pincode
    pincode_match = re.search(r'\b(\d{6})\b', query)
    if pincode_match:
        pincode = pincode_match.group(1)
        if pincode in BHOPAL_PINCODE_COORDS:
            lat, lon = BHOPAL_PINCODE_COORDS[pincode]
            return lat, lon, f"Pincode {pincode}"
    
    # 2) Area name
    for area, pincode in BHOPAL_AREA_TO_PINCODE.items():
        if area in query_lower:
            if pincode in BHOPAL_PINCODE_COORDS:
                lat, lon = BHOPAL_PINCODE_COORDS[pincode]
                return lat, lon, f"Area '{area.title()}' (Pincode {pincode})"
    
    return None, None, None


def geocode_address(address):
    """Pehle local map, phir Nominatim."""
    if not address or not address.strip():
        return None, None, None
    
    lat, lon, source = get_coords_from_pincode_or_area(address)
    if lat is not None:
        return lat, lon, source
    
    # Nominatim fallback
    if HAS_GEOPY:
        try:
            geolocator = Nominatim(user_agent="sarkari_scheme_finder_bhopal", timeout=10)
            location = geolocator.geocode(address + ", Bhopal, India")
            if location:
                return location.latitude, location.longitude, "Nominatim"
        except Exception:
            pass
    
    return None, None, None


def find_nearest_csc(user_address, max_results=10):
    """
    Nearest CSC centers dhoondhta hai.
    Returns: (user_lat, user_lon, sorted_df, source) — YA — (None, None, empty_df, None)
    """
    user_lat, user_lon, source = geocode_address(user_address)
    
    if user_lat is None or user_lon is None:
        return None, None, pd.DataFrame(), None
    
    csc_df = get_csc_centers()
    
    distances = []
    for _, row in csc_df.iterrows():
        try:
            csc_lat = float(row["Latitude"])
            csc_lon = float(row["Longitude"])
            dist = haversine_distance(user_lat, user_lon, csc_lat, csc_lon)
            distances.append(dist)
        except (ValueError, TypeError, KeyError):
            distances.append(float("inf"))
    
    csc_df = csc_df.copy()
    csc_df["Distance (km)"] = distances
    csc_df = csc_df.sort_values("Distance (km)").reset_index(drop=True)
    
    return user_lat, user_lon, csc_df.head(max_results), source


if __name__ == "__main__":
    df = get_csc_centers()
    print(f"Loaded {len(df)} CSC centers in Bhopal")
    print(df[["Name", "District"]].to_string(index=False))
    
    print("\n--- Geocoding Tests ---")
    for test in ["MP Nagar", "462011", "Kolar Road", "jahangirabad, 462008", "Jahangirabad, Bhopal"]:
        lat, lon, source = geocode_address(test)
        print(f"'{test}' → ({lat}, {lon}) via {source}")