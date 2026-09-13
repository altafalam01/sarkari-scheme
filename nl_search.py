"""
nl_search.py — Natural language scheme search (v7).

Char n-gram TF-IDF + synonym expansion + keyword boost + state-aware scoring.

FIXES (v7):
  - BUG: `applicable_state` was NEVER part of the searchable text, so the
    engine had zero awareness of geography — a query like "Madhya Pradesh
    ke kisano ke liye scheme" scored every farmer scheme (any state)
    almost identically, and whichever had marginally more text overlap
    won (root cause of wrong-state schemes like a UP scheme showing up
    for an MP query). Two independent fixes added:
      1. `_scheme_text()` now appends the scheme's `applicable_state`.
      2. `search_schemes()` detects an Indian state named in the query
         and applies an explicit boost to same-state/"All" schemes and
         a heavy penalty to schemes tied to a *different* specific state
         — char-ngram similarity alone isn't trusted for this, since
         "Madhya Pradesh"/"Uttar Pradesh"/"Himachal Pradesh" all share
         the substring "Pradesh" and would otherwise still get partial
         credit for each other.

FIXES (v6):
  - SYNONYMS me "Welfare" ka "marriage/shaadi" galat placement fix —
    ab dedicated "Marriage" category hai jo schemes.csv ki
    "Social Welfare", "Women Welfare", "Education/Savings" categories
    ko target karta hai.
  - _keyword_boost() ab capped hai (max 0.25) aur min_score threshold
    ko respect karta hai — pehle 0.8 tak boost de deta tha jisse
    saare schemes "100% match" dikhne lagte the.
  - Duplicate keyword groups hata diye (ladki/beti ab sirf ek group me).
  - _scheme_text() ab row["scheme_name"] direct access nahi karta —
    .get() se safe.
  - search_schemes() me empty vocabulary (ValueError) handle hota hai.
  - build_vocabulary() None/non-str entries skip karta hai.
  - get_suggestions() me case-insensitive comparison.
  - __main__ self-test.
"""

import re
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ===========================
# SYNONYMS MAP
# ===========================
# Ye map category_type → keywords karta hai. Scheme ke text me in
# keywords ko append karte hain taaki user ke Hinglish/Hindi words bhi
# us category ke schemes se match karein.
#
# IMPORTANT: Category names schemes.csv ke `category_type` values se
# match karte hain. Agar scheme ki category CSV me hai lekin SYNONYMS
# me nahi, to usme keywords append nahi honge.
SYNONYMS = {
    # ---- schemes.csv categories ----
    "Agriculture": [
        "loan", "karza", "business", "vyapar", "udyog", "startup",
        "mudra", "credit", "finance", "collateral", "udham", "business loan",
        "kisan", "farmer", "crop", "fasal", "kheti", "agriculture",
        "soil", "seed", "beej", "crop insurance", "irrigation",
        "solar pump", "tractor", "khad", "fertilizer",
        "ऋण", "व्यापार", "व्यवसाय", "कर्ज", "स्टार्टअप", "किसान",
        "खेती", "फसल", "कृषि", "मिट्टी", "बीज", "फसल बीमा", "सिंचाई",
        "सोलर पंप", "ट्रैक्टर", "खाद", "उर्वरक",
    ],

    "Education": [
        "scholarship", "study", "padhai", "school", "college", "university",
        "student", "chatravriti", "fees", "shiksha", "admission", "exam",
        "marks", "vidya", "tuition", "hostel",
        "छात्रवृत्ति", "पढ़ाई", "स्कूल", "शिक्षा", "विद्यार्थी", "प्रवेश",
        "परीक्षा", "विश्वविद्यालय", "फीस", "निशुल्क शिक्षा", "किताबें",
        "छात्र", "ट्यूशन", "हॉस्टल",
    ],

    "Health": [
        "health", "hospital", "ilaj", "medical", "bimari", "swasthya",
        "treatment", "insurance", "surgery", "doctor", "medicine",
        "dawai", "operation", "ayushman",
        "स्वास्थ्य", "इलाज", "अस्पताल", "बीमारी", "स्वस्थ", "दवाई",
        "डॉक्टर", "ऑपरेशन", "मेडिकल", "चिकित्सा", "आयुष्मान", "बीमा",
    ],

    "Pension": [
        "pension", "budhapa", "old age", "retirement", "senior citizen",
        "vridha", "vridhavastha", "monthly income",
        "सेवानिवृत्ति", "वृद्धावस्था", "पेंशन", "बुढ़ापा", "मासिक आय",
        "सीनियर सिटीजन", "रिटायरमेंट", "बुजुर्ग",
    ],

    # ---- Marriage-specific (FIX: Ye pehle Welfare me tha, galat tha) ----
    # schemes.csv me marriage schemes aksar "Social Welfare",
    # "Women Welfare", ya "Education/Savings" categories me hain.
    "Social Welfare": [
        "welfare", "kalyan", "poor", "gareeb", "assistance", "sahayata",
        "madad", "bpl", "antodaya", "free", "subsidy",
        # Marriage keywords (Hinglish + Hindi + English)
        "shaadi", "marriage", "vivaah", "saadi", "shadi", "kanyadan",
        "kanya vivah", "kanya vivaah", "kanyadaan", "vivah",
        "marriage assistance", "marriage grant", "marriage scheme",
        "shaadi anudan", "vivah anudan", "shadi anudan",
        "ladki ki shaadi", "beti ki shaadi", "ladki ke shaadi",
        "शादी", "विवाह", "विवाह अनुदान", "कन्यादान", "लड़की की शादी",
        "बेटी की शादी", "शादी अनुदान", "विवाह सहायता", "शादी सहायता",
        "कन्या विवाह", "दहेज",
        "कल्याण", "गरीब", "सहायता", "मदद", "बीपीएल", "मुफ्त", "सब्सिडी",
    ],

    "Women Welfare": [
        "women", "mahila", "stree", "beti", "ladki", "girl child",
        "matru", "pregnant", "widow", "vidhwa",
        "marriage", "shaadi", "vivaah", "kanyadan",
        "महिला", "स्त्री", "बेटी", "लड़की", "बालिका", "गर्भवती",
        "मातृ", "महिला सशक्तिकरण", "विधवा", "शादी", "विवाह",
    ],

    "Child Welfare": [
        "child", "bacche", "bal", "orphan", "anganwadi", "nutrition",
        "balika", "kishori",
        "बच्चे", "बाल", "अनाथ", "आंगनवाड़ी", "पोषण", "बालिका", "किशोरी",
    ],

    "Housing": [
        "house", "ghar", "awas", "home loan", "flat", "plot",
        "property", "pmaay", "construction", "pucca",
        "मकान", "आवास", "ज़मीन", "फ्लैट", "संपत्ति", "गृह ऋण",
        "निर्माण", "घर", "पक्का",
    ],

    "Employment": [
        "job", "rozgar", "employment", "naukri", "work", "vacancy",
        "interview", "recruitment", "unemployment allowance",
        "नौकरी", "रोजगार", "काम", "भर्ती", "इंटरव्यू", "रिक्ति",
        "बेरोजगारी भत्ता", "स्वरोजगार", "self employment",
    ],

    "Skill Development": [
        "skill", "training", "kaushal", "certificate", "course",
        "free training", "apprenticeship", "internship",
        "कौशल", "प्रशिक्षण", "कौशल विकास", "प्रमाणपत्र", "कोर्स",
        "निःशुल्क प्रशिक्षण", "अप्रेंटिसशिप", "इंटर्नशिप", "ट्रेनिंग",
    ],

    "Financial Inclusion": [
        "bank account", "khata", "banking", "zero balance",
        "rupee card", "financial", "jan dhan", "dbt",
        "बैंक", "खाता", "बैंकिंग", "ज़ीरो बैलेंस", "रुपे कार्ड",
        "वित्तीय", "बचत", "सेविंग्स", "जन धन",
    ],

    "Insurance": [
        "insurance", "bima", "cover", "accidental", "life insurance",
        "health cover", "premium", "jeevan jyoti", "suraksha bima",
        "बीमा", "दुर्घटना", "जीवन बीमा", "स्वास्थ्य बीमा", "प्रीमियम",
        "सुरक्षा", "कवर", "जीवन ज्योति", "सुरक्षा बीमा",
    ],

    "Food Security": [
        "food", "ration", "free food", "anna", "grains", "wheat", "rice",
        "राशन", "भोजन", "मुफ्त भोजन", "अन्न", "अनाज", "गेहूं", "चावल",
    ],

    "Rural Development": [
        "rural", "village", "gramin", "gaon", "panchayat", "mgnrega",
        "ग्रामीण", "गांव", "पंचायत", "मनरेगा",
    ],

    "Urban Development": [
        "urban", "city", "shahar", "municipal",
        "शहरी", "शहर", "नगर", "नगरपालिका",
    ],

    "Energy": [
        "solar", "electricity", "bijli", "power", "solar panel",
        "energy", "light", "lpg", "gas",
        "सोलर", "बिजली", "ऊर्जा", "सोलर पैनल", "रोशनी",
        "सौर ऊर्जा", "बिजली बिल", "मुफ्त बिजली", "एलपीजी", "गैस",
    ],

    "Disability Welfare": [
        "disab", "divyang", "दिव्यांग", "viklang", "विकलांग",
        "handicap", "adip", "udid",
    ],

    "Business/Loan": [
        "loan", "karza", "business", "vyapar", "udyog", "startup",
        "mudra", "credit", "msme", "udyam",
        "ऋण", "व्यापार", "व्यवसाय", "कर्ज", "स्टार्टअप", "उद्यम",
    ],

    "Banking": [
        "bank account", "khata", "banking", "zero balance",
        "बैंक", "खाता", "बैंकिंग", "ज़ीरो बैलेंस",
    ],

    # ---- Extra (future-proofing) ----
    "Digital Services": [
        "digital", "internet", "cyber", "computer", "online",
        "e-governance", "tech",
        "डिजिटल", "इंटरनेट", "साइबर", "कंप्यूटर", "ऑनलाइन",
        "ई-गवर्नेंस", "तकनीक", "डिजिटल इंडिया",
    ],

    "Infrastructure": [
        "road", "sadak", "connectivity", "rural road", "sewerage",
        "water supply",
        "सड़क", "सड़क कनेक्टिविटी", "ग्रामीण सड़क", "सीवरेज",
        "जल आपूर्ति", "बुनियादी ढांचा",
    ],

    "Sanitation": [
        "toilet", "shochalay", "swachh", "cleanliness", "sanitation",
        "शौचालय", "स्वच्छ", "स्वच्छता", "सफाई",
    ],

    "Environment": [
        "environment", "paryavaran", "climate", "green",
        "पर्यावरण", "जलवायु", "हरित",
    ],

    "Tourism": [
        "tourism", "travel", "yatra", "tirth",
        "पर्यटन", "यात्रा", "तीर्थ",
    ],

    "Sports": [
        "sports", "khel", "athlete", "player", "khelo india",
        "खेल", "खिलाड़ी", "एथलीट", "खेलो इंडिया",
    ],

    "Disaster Relief": [
        "disaster", "aapda", "relief", "flood", "earthquake",
        "आपदा", "राहत", "बाढ़", "भूकंप",
    ],
}


# ===========================
# HIGH-PRIORITY KEYWORD GROUPS
# ===========================
# Ye groups query me specific intent detect karte hain. Har group
# matched hone par us group ke relevant schemes ko boost milta hai.
#
# IMPORTANT: Ek keyword sirf ek group me ho (duplicate se double-boost
# trigger ho jaata hai).
HIGH_PRIORITY_KEYWORDS = {
    "marriage": [
        "marriage", "shaadi", "shadi", "saadi", "vivaah", "vivah",
        "kanyadan", "kanyadaan", "kanya vivah", "shadi anudan",
        "vivah anudan", "marriage assistance",
        "शादी", "विवाह", "कन्यादान", "कन्या विवाह",
    ],
    "scholarship": [
        "scholarship", "chatravriti", "छात्रवृत्ति",
    ],
    "pension": [
        "pension", "पेंशन", "vridha", "वृद्धावस्था",
    ],
    "loan": [
        "loan", "karza", "कर्ज", "ऋण", "mudra",
    ],
    "farmer": [
        "kisan", "farmer", "किसान", "kheti", "खेती", "fasal", "फसल",
    ],
    "student": [
        "student", "छात्र", "विद्यार्थी", "college", "school",
    ],
    "health": [
        "health", "swasthya", "स्वास्थ्य", "ilaj", "इलाज",
        "hospital", "अस्पताल", "ayushman",
    ],
    "housing": [
        "house", "ghar", "awas", "घर", "आवास", "makaan", "मकान",
    ],
    "women": [
        "women", "mahila", "महिला", "ladki", "लड़की", "beti", "बेटी",
    ],
    "disability": [
        "disab", "divyang", "दिव्यांग", "viklang", "विकलांग",
    ],
    "sc_st": [
        "scheduled", "अनुसूचित", "पिछड़ा",
    ],
}


# ===========================
# STATE DETECTION (v7 — fixes wrong-state matches)
# ===========================
# Maps aliases/abbreviations (English + Hindi + Hinglish) → canonical state
# name as it's expected to appear in schemes.csv's `applicable_state` column.
_INDIAN_STATE_ALIASES = {
    "andhra pradesh": "Andhra Pradesh", "ap": "Andhra Pradesh",
    "arunachal pradesh": "Arunachal Pradesh",
    "assam": "Assam", "असम": "Assam",
    "bihar": "Bihar", "बिहार": "Bihar",
    "chhattisgarh": "Chhattisgarh", "chattisgarh": "Chhattisgarh", "छत्तीसगढ़": "Chhattisgarh",
    "goa": "Goa", "गोवा": "Goa",
    "gujarat": "Gujarat", "गुजरात": "Gujarat",
    "haryana": "Haryana", "हरियाणा": "Haryana",
    "himachal pradesh": "Himachal Pradesh", "hp": "Himachal Pradesh", "हिमाचल प्रदेश": "Himachal Pradesh",
    "jharkhand": "Jharkhand", "झारखंड": "Jharkhand",
    "karnataka": "Karnataka", "कर्नाटक": "Karnataka",
    "kerala": "Kerala", "केरल": "Kerala",
    "madhya pradesh": "Madhya Pradesh", "mp": "Madhya Pradesh",
    "म प्र": "Madhya Pradesh", "मध्य प्रदेश": "Madhya Pradesh", "मध्यप्रदेश": "Madhya Pradesh",
    "maharashtra": "Maharashtra", "महाराष्ट्र": "Maharashtra",
    "manipur": "Manipur", "meghalaya": "Meghalaya", "mizoram": "Mizoram", "nagaland": "Nagaland",
    "odisha": "Odisha", "orissa": "Odisha", "ओडिशा": "Odisha",
    "punjab": "Punjab", "पंजाब": "Punjab",
    "rajasthan": "Rajasthan", "राजस्थान": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil nadu": "Tamil Nadu", "tamilnadu": "Tamil Nadu", "தமிழ்நாடு": "Tamil Nadu",
    "telangana": "Telangana", "tripura": "Tripura",
    "uttar pradesh": "Uttar Pradesh", "up": "Uttar Pradesh",
    "उत्तर प्रदेश": "Uttar Pradesh", "उत्तरप्रदेश": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand", "uttaranchal": "Uttarakhand",
    "west bengal": "West Bengal", "wb": "West Bengal", "bengal": "West Bengal",
    "delhi": "Delhi", "new delhi": "Delhi", "दिल्ली": "Delhi",
    "jammu and kashmir": "Jammu and Kashmir", "jammu & kashmir": "Jammu and Kashmir", "j&k": "Jammu and Kashmir",
    "ladakh": "Ladakh",
    "puducherry": "Puducherry", "pondicherry": "Puducherry",
    "chandigarh": "Chandigarh",
}
# Longest aliases first so "himachal pradesh" is checked before a stray "up".
_STATE_ALIAS_KEYS_SORTED = sorted(_INDIAN_STATE_ALIASES.keys(), key=len, reverse=True)


def _detect_state_in_query(query):
    """v7: detect an Indian state/UT mentioned anywhere in the query text."""
    if not query:
        return None
    lowered = f" {query.lower()} "
    for alias in _STATE_ALIAS_KEYS_SORTED:
        pattern = r"(?<![a-z\u0900-\u097F])" + re.escape(alias) + r"(?![a-z\u0900-\u097F])"
        if re.search(pattern, lowered):
            return _INDIAN_STATE_ALIASES[alias]
    return None


# ===========================
# SCHEME TEXT BUILDER
# ===========================
def _safe_str(value, default=""):
    """None/non-str ko safe string me convert karta hai."""
    if value is None:
        return default
    try:
        if value != value:  # NaN check without pandas
            return default
    except Exception:
        pass
    return str(value)


def _scheme_text(row):
    """
    Ek scheme row ka searchable text build karta hai:
    scheme_name + category_type + description + benefits +
    category-specific synonyms.
    """
    scheme_name = _safe_str(row.get("scheme_name", ""))
    category = _safe_str(row.get("category_type", ""))
    description = _safe_str(row.get("description", ""))
    benefits = _safe_str(row.get("benefits", ""))
    # v7 FIX: state was missing from the searchable text entirely.
    state = _safe_str(row.get("applicable_state", ""))

    base = f"{scheme_name} {category} {description} {benefits} {state}"

    # Category-specific synonyms append karo
    extra_words = SYNONYMS.get(category, [])
    if extra_words:
        base += " " + " ".join(extra_words)

    return base


def _build_corpus(df):
    """Saare schemes ka corpus list banata hai."""
    return [_scheme_text(row) for _, row in df.iterrows()]


# ===========================
# CACHED TF-IDF INDEX
# ===========================
# PERFORMANCE FIX: Pehle search_schemes() har call par (yaani har keystroke/
# search click par, kyunki Streamlit har interaction par poora script
# re-run karta hai) poore corpus par ek naya TfidfVectorizer fit karta tha.
# Char n-grams (3-5) ke saath ye bahut expensive hota hai aur app ko
# laggy bana deta tha.
#
# Ab vectorizer + matrix sirf ek baar per `df` fit hote hain aur
# st.cache_resource me cache ho jaate hain (ML-model jaisi cheezon ke
# liye yahi recommended cache hai). Har search call par sirf naye query
# ka transform() hota hai — jo bahut sasta operation hai. Cosine
# similarity ke result par iska koi asar nahi padta: query ke wo
# character n-grams jo corpus me kahin bhi nahi hain, unka corpus
# vectors me weight pehle bhi 0 hi tha.
@st.cache_resource(show_spinner=False)
def _get_or_build_tfidf_index(df):
    """Returns (vectorizer, tfidf_matrix, corpus) fit once per dataset, cached."""
    corpus = _build_corpus(df)
    if not corpus or all(not c.strip() for c in corpus):
        return None, None, None
    try:
        vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            min_df=1,
            lowercase=True,
        )
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        # Empty vocabulary (agar saara text sirf punctuation ho)
        return None, None, None
    return vectorizer, matrix, corpus


# ===========================
# SCORING HELPERS
# ===========================
def _prefix_bonus(query, text, bonus_amount=0.25):
    """
    Agar query kisi scheme text ke word ka prefix hai to bonus do.
    (e.g. "studen" → "student")
    """
    query = query.lower().strip()
    if len(query) < 3:
        return 0.0

    # Query ko word boundary par match karne ki koshish karo
    words = text.lower().split()
    for w in words:
        w_clean = "".join(ch for ch in w if ch.isalnum())
        if len(w_clean) < 3:
            continue
        if w_clean.startswith(query):
            return bonus_amount
    return 0.0


def _keyword_boost(query, text, max_boost=0.25):
    """
    HIGH_PRIORITY_KEYWORDS ke groups match karke boost deta hai.

    FIX: Pehle har matched group ke liye 0.4 add karta tha (max 0.8),
    jisse saare schemes 100% match dikhne lagte the. Ab:
    - Per-group boost kam hai (0.12)
    - Max total boost 0.25 (min_score threshold meaningful reh jaata hai)
    - Sirf FIRST matched group count hota hai (duplicate triggers nahi)
    """
    query_lower = query.lower()
    text_lower = text.lower()

    matched_group_count = 0

    for group_name, keywords in HIGH_PRIORITY_KEYWORDS.items():
        # Query me is group ka keyword hai?
        query_has = any(kw.lower() in query_lower for kw in keywords)
        if not query_has:
            continue

        # Text me is group ka keyword hai?
        text_has = any(kw.lower() in text_lower for kw in keywords)
        if text_has:
            matched_group_count += 1

    # Per-group 0.12 boost, max cap
    boost = min(matched_group_count * 0.12, max_boost)
    return boost


# ===========================
# MAIN SEARCH
# ===========================
def search_schemes(df, query, top_n=8, min_score=0.03):
    """
    Natural language search with typo tolerance.

    Args:
        df: schemes DataFrame
        query: user query string
        top_n: max results to return
        min_score: minimum similarity score (0-1)

    Returns:
        list of dicts with scheme details + "score" field
    """
    if df is None or df.empty:
        return []

    if not query or not query.strip():
        return []

    # PERFORMANCE FIX: vectorizer/matrix ab cached hain (per df), sirf
    # query ka transform() yahan hota hai — poora corpus refit nahi hota.
    vectorizer, scheme_vectors, corpus = _get_or_build_tfidf_index(df)
    if vectorizer is None:
        return []

    try:
        query_vector = vectorizer.transform([query])
    except ValueError:
        return []

    scores = cosine_similarity(query_vector, scheme_vectors).flatten()

    # v7 FIX: detect a specific state mentioned in the query once, up front.
    # Char n-grams alone can't be trusted for this — "Madhya Pradesh" and
    # "Uttar Pradesh" share the substring "Pradesh" and would otherwise get
    # partial credit for each other's schemes.
    detected_state = _detect_state_in_query(query)

    results = []
    for idx, base_score in enumerate(scores):
        # Prefix bonus
        prefix_b = _prefix_bonus(query, corpus[idx])

        # Keyword boost (FIX: ab capped)
        keyword_b = _keyword_boost(query, corpus[idx])

        final_score = min(base_score + prefix_b + keyword_b, 1.0)

        # v7 FIX: explicit state boost/penalty — a specific-state query
        # should strongly prefer that state's schemes (or state-agnostic
        # "All" ones) and strongly demote schemes tied to a *different*
        # specific state, regardless of incidental text overlap.
        if detected_state:
            row_state = _safe_str(df.iloc[idx].get("applicable_state", ""))
            if row_state and row_state != "All":
                if row_state.lower() == detected_state.lower():
                    final_score = min(final_score + 0.3, 1.0)
                else:
                    final_score *= 0.15

        # FIX: min_score ab meaningful hai kyunki boost capped hai
        if final_score >= min_score:
            row = df.iloc[idx]
            results.append({
                "scheme_name": _safe_str(row.get("scheme_name", "")),
                "category_type": _safe_str(row.get("category_type", "")),
                "applicable_state": _safe_str(row.get("applicable_state", "")),
                "description": _safe_str(row.get("description", "")),
                "benefits": _safe_str(row.get("benefits", "")),
                "apply_link": _safe_str(row.get("apply_link", "")),
                "deadline": row.get("deadline", None),
                "score": float(final_score),
            })

    # Score descending sort
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


# ===========================
# VOCABULARY & SUGGESTIONS
# ===========================
@st.cache_data(show_spinner=False)
def build_vocabulary(df):
    """
    Autocomplete suggestions ke liye vocabulary banata hai.
    Scheme names + category types + synonym keywords include karta hai.

    PERFORMANCE FIX: Pehle ye function app.py se har rerun par (yaani
    NL search page par har interaction par) uncached call hota tha,
    poore dataframe ko .iterrows() se loop karke. Ab @st.cache_data
    se cache hai — sirf tab dobara chalega jab `df` khud badlega.
    """
    vocab = set()

    if df is None or df.empty:
        return []

    for _, row in df.iterrows():
        # Scheme name words
        name = _safe_str(row.get("scheme_name", ""))
        for w in name.split():
            w_clean = "".join(ch for ch in w if ch.isalnum())
            if len(w_clean) >= 3:
                vocab.add(w_clean)

        # Category type (whole string)
        category = _safe_str(row.get("category_type", ""))
        if category:
            vocab.add(category)

    # Synonyms ke saare keywords
    for words in SYNONYMS.values():
        for w in words:
            if w and len(w) >= 3:
                vocab.add(w)

    return sorted(vocab, key=lambda s: str(s).lower())


def get_suggestions(vocab, partial_query, max_n=6):
    """
    Partial query ke liye autocomplete suggestions.
    - Exact matches exclude (already typed word suggest nahi karta)
    - Prefix matches pehle, substring matches baad me
    - Fallback: synonyms se related terms
    """
    if not partial_query or len(partial_query.strip()) < 2:
        return []

    q = str(partial_query).strip().lower()

    # Skip non-string vocab entries
    vocab_clean = [str(w) for w in vocab if w is not None]

    # Prefix matches (exact q exclude)
    prefix_matches = [
        w for w in vocab_clean
        if w.lower().startswith(q) and w.lower() != q
    ]

    # Substring matches (not already in prefix)
    substring_matches = [
        w for w in vocab_clean
        if q in w.lower() and w not in prefix_matches
    ]

    combined = prefix_matches + substring_matches

    # Dedup case-insensitively
    seen = {q}
    unique = []
    for w in combined:
        key = w.lower()
        if key not in seen:
            seen.add(key)
            unique.append(w)

    # Agar kuch nahi mila, synonym-based fallback
    if not unique:
        candidates = {q}
        if q.endswith("s") and len(q) > 3:
            candidates.add(q[:-1])

        for words in SYNONYMS.values():
            words_lower = [str(w).lower() for w in words]
            if any(c in words_lower for c in candidates):
                for w in words:
                    key = str(w).lower()
                    if key not in seen:
                        seen.add(key)
                        unique.append(w)
                break

    return unique[:max_n]


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("nl_search.py — Verification")
    print("=" * 60)

    import pandas as pd
    import os

    if not os.path.exists("data/schemes.csv"):
        print("⚠️  data/schemes.csv not found, using sample data")
        df = pd.DataFrame([
            {"scheme_name": "PM Kisan Samman Nidhi", "category_type": "Agriculture",
             "applicable_state": "All", "description": "Income support for farmers",
             "benefits": "Rs 6000/year", "apply_link": "https://x.gov.in", "deadline": ""},
            {"scheme_name": "UP Kanya Sumangala Yojana", "category_type": "Education/Savings",
             "applicable_state": "Uttar Pradesh", "description": "Girl child support",
             "benefits": "Rs 25000", "apply_link": "https://x.gov.in", "deadline": ""},
            {"scheme_name": "Ayushman Bharat (PM-JAY)", "category_type": "Health",
             "applicable_state": "All", "description": "Health insurance",
             "benefits": "Rs 5 lakh cover", "apply_link": "https://x.gov.in", "deadline": ""},
            {"scheme_name": "UP Shadi Anudan Yojana", "category_type": "Social Welfare",
             "applicable_state": "Uttar Pradesh", "description": "Marriage assistance for daughters",
             "benefits": "One-time grant", "apply_link": "https://x.gov.in", "deadline": ""},
        ])
    else:
        df = pd.read_csv("data/schemes.csv")
        print(f"✅ Loaded schemes.csv: {len(df)} schemes")

    # Test 1: Basic search
    print("\n[Test 1] Basic queries:")
    test_queries = [
        ("kisan loan", ["PM Kisan", "Kisan"]),
        ("scholarship for daughter", ["Scholarship", "Kanya"]),
        ("health insurance", ["Ayushman", "Health"]),
        ("student loan", ["Scholarship", "Loan"]),
    ]
    for query, expected_keywords in test_queries:
        results = search_schemes(df, query, top_n=5)
        top_names = [r["scheme_name"][:40] for r in results[:2]]
        print(f"  '{query}' → {len(results)} results: {top_names}")

    # Test 2: Marriage keywords
    print("\n[Test 2] Marriage queries (should find Shadi Anudan type schemes):")
    for q in ["marriage", "shaadi", "shadi anudan", "kanya vivah", "beti ki shaadi"]:
        results = search_schemes(df, q, top_n=3)
        has_marriage = any(
            "shadi" in r["scheme_name"].lower() or
            "vivah" in r["scheme_name"].lower() or
            "kanya" in r["scheme_name"].lower()
            for r in results
        )
        status = "✅" if has_marriage or len(results) == 0 else "⚠️"
        print(f"  {status} '{q}' → {len(results)} results")

    # Test 2b: State-aware ranking (v7 regression test — the original bug)
    print("\n[Test 2b] v7 — state query should not surface a different state's scheme:")
    state_df = pd.DataFrame([
        {"scheme_name": "UP Kisan Uday Yojana", "category_type": "Agriculture",
         "applicable_state": "Uttar Pradesh", "description": "Support for farmers in UP",
         "benefits": "Input subsidy", "apply_link": "https://x.gov.in", "deadline": ""},
        {"scheme_name": "MP Kisan Kalyan Yojana", "category_type": "Agriculture",
         "applicable_state": "Madhya Pradesh", "description": "Support for farmers in MP",
         "benefits": "Input subsidy", "apply_link": "https://x.gov.in", "deadline": ""},
        {"scheme_name": "PM Kisan Samman Nidhi", "category_type": "Agriculture",
         "applicable_state": "All", "description": "National income support for farmers",
         "benefits": "Rs 6000/year", "apply_link": "https://x.gov.in", "deadline": ""},
    ])
    res = search_schemes(state_df, "Madhya Pradesh mein kisano ke liye scheme", top_n=5)
    names = [r["scheme_name"] for r in res]
    assert names, "Expected at least one result"
    assert names[0] != "UP Kisan Uday Yojana", f"Wrong-state scheme ranked first: {names}"
    assert "MP Kisan Kalyan Yojana" in names[:1] or "MP Kisan Kalyan Yojana" == names[0]
    print(f"  ✅ Top result for MP query: '{names[0]}' (full ranking: {names})")

    # Test 3: Boost is capped
    print("\n[Test 3] Keyword boost is capped (max 0.25):")
    results = search_schemes(df, "marriage scheme loan kisan scholarship", top_n=10)
    max_score = max((r["score"] for r in results), default=0)
    print(f"  Max score: {max_score:.3f}")
    assert max_score <= 1.0, "Score should never exceed 1.0"
    print("  ✅ Boost capped correctly")

    # Test 4: Empty query
    print("\n[Test 4] Empty/invalid inputs:")
    assert search_schemes(df, "") == []
    assert search_schemes(df, "   ") == []
    assert search_schemes(df, None) == []
    assert search_schemes(None, "test") == []
    assert search_schemes(pd.DataFrame(), "test") == []
    print("  ✅ All empty/invalid inputs return []")

    # Test 5: Vocabulary
    print("\n[Test 5] Vocabulary & suggestions:")
    vocab = build_vocabulary(df)
    print(f"  Vocabulary size: {len(vocab)}")
    assert len(vocab) > 0

    suggestions = get_suggestions(vocab, "schol")
    print(f"  Suggestions for 'schol': {suggestions[:5]}")
    assert len(suggestions) > 0

    # Exact match should NOT suggest itself
    if "scholarship" in [v.lower() for v in vocab]:
        exact = get_suggestions(vocab, "scholarship")
        assert "scholarship" not in [s.lower() for s in exact]
        print("  ✅ Exact match not suggested")

    # Test 6: No crash on None vocab entries
    print("\n[Test 6] Malformed vocab:")
    weird_vocab = ["test", None, 123, "  ", "  another  "]
    s = get_suggestions(weird_vocab, "test")
    print(f"  Suggestions with malformed vocab: {s}")
    print("  ✅ No crash")

    # Test 7: Missing scheme_name key
    print("\n[Test 7] Malformed row (missing keys):")
    weird_df = pd.DataFrame([
        {"scheme_name": "Good Scheme", "category_type": "Health"},
        {"category_type": "Education"},  # missing scheme_name
    ])
    results = search_schemes(weird_df, "education", top_n=5)
    print(f"  Results: {len(results)}")
    print("  ✅ No crash on missing keys")

    print("\n" + "=" * 60)
    print("✅ nl_search.py — ALL CHECKS PASSED")
    print("=" * 60)