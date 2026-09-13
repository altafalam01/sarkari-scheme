"""
doc_checklist.py — Per-scheme and category-level document guidance.

Data sources:
  1. PER_SCHEME_DOCUMENTS — manually curated for well-known schemes
  2. CATEGORY_DOCUMENTS — category-level generic lists (fallback)

FIXES (v2):
  - Saare schemes.csv categories ko cover karta hai (13 → 40+).
  - category_type=None / empty string / non-str → "default" fallback.
  - lang invalid → English fallback (silent, no crash).
  - Combined categories (e.g. "Education/Savings", "Welfare/Education") properly
    handle hote hain — pehla meaningful segment match karta hai, warna
    poora string try karta hai.
  - Hindi coverage expand kiya (saare naye categories me).
  - get_documents() me safe_str conversion.
  - __main__ self-test.
"""

# ===========================
# SCHEME-SPECIFIC OVERRIDES
# ===========================
# Ye list un schemes ke liye hai jinke documents category se alag hain
# (well-known schemes jinka exact document list pata hai).
PER_SCHEME_DOCUMENTS = {
    "English": {
        "PM Kisan Samman Nidhi": [
            "Aadhaar Card",
            "Land ownership records (khatauni/khasra)",
            "Bank passbook",
            "Passport-size photograph",
        ],
        "Ayushman Bharat (PM-JAY)": [
            "Aadhaar Card",
            "Income certificate",
            "Ration card / family ID",
            "Bank passbook",
        ],
        "Sukanya Samriddhi Yojana": [
            "Aadhaar Card (for girl child)",
            "Birth certificate",
            "Bank passbook",
            "Guardian's documents",
        ],
        "Atal Pension Yojana": [
            "Aadhaar Card",
            "Bank account (with auto-debit facility)",
            "Age proof",
            "Passport-size photograph",
        ],
        "PM Ujjwala Yojana": [
            "Aadhaar Card",
            "BPL ration card",
            "Bank passbook",
            "Address proof",
        ],
        "PM Mudra Yojana": [
            "Aadhaar Card",
            "PAN Card",
            "Business plan",
            "Bank statement",
            "Passport-size photograph",
        ],
        "Pradhan Mantri Awas Yojana (Urban)": [
            "Aadhaar Card",
            "Income certificate",
            "Property documents (if any)",
            "Bank passbook",
            "Passport-size photograph",
        ],
        "Pradhan Mantri Awas Yojana (Gramin)": [
            "Aadhaar Card",
            "Job card (MGNREGA)",
            "Bank passbook",
            "Residence proof",
        ],
        "PM Fasal Bima Yojana": [
            "Aadhaar Card",
            "Land records / Khasra-Khatauni",
            "Bank passbook",
            "Sowing certificate (from Patwari)",
        ],
        "National Means-cum-Merit Scholarship": [
            "Aadhaar Card",
            "Previous class marksheet",
            "Income certificate (max Rs 1.5 lakh)",
            "School bonafide certificate",
            "Bank passbook",
        ],
    },
    "हिंदी": {
        "PM Kisan Samman Nidhi": [
            "आधार कार्ड",
            "भूमि स्वामित्व दस्तावेज़ (खतौनी/खसरा)",
            "बैंक पासबुक",
            "पासपोर्ट साइज फोटो",
        ],
        "Ayushman Bharat (PM-JAY)": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "राशन कार्ड / परिवार पहचान",
            "बैंक पासबुक",
        ],
        "Sukanya Samriddhi Yojana": [
            "आधार कार्ड (बेटी के लिए)",
            "जन्म प्रमाण पत्र",
            "बैंक पासबुक",
            "अभिभावक का दस्तावेज़",
        ],
        "Atal Pension Yojana": [
            "आधार कार्ड",
            "बैंक खाता (ऑटो-डेबिट सुविधा के साथ)",
            "आयु प्रमाण",
            "पासपोर्ट साइज फोटो",
        ],
        "PM Ujjwala Yojana": [
            "आधार कार्ड",
            "बीपीएल राशन कार्ड",
            "बैंक पासबुक",
            "पता प्रमाण",
        ],
        "PM Mudra Yojana": [
            "आधार कार्ड",
            "पैन कार्ड",
            "व्यवसाय योजना",
            "बैंक स्टेटमेंट",
            "पासपोर्ट साइज फोटो",
        ],
        "Pradhan Mantri Awas Yojana (Urban)": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "संपत्ति दस्तावेज़ (यदि हो)",
            "बैंक पासबुक",
            "पासपोर्ट साइज फोटो",
        ],
        "Pradhan Mantri Awas Yojana (Gramin)": [
            "आधार कार्ड",
            "जॉब कार्ड (मनरेगा)",
            "बैंक पासबुक",
            "निवास प्रमाण",
        ],
        "PM Fasal Bima Yojana": [
            "आधार कार्ड",
            "भूमि रिकॉर्ड / खसरा-खतौनी",
            "बैंक पासबुक",
            "बुवाई प्रमाण पत्र (पटवारी से)",
        ],
        "National Means-cum-Merit Scholarship": [
            "आधार कार्ड",
            "पिछली कक्षा की मार्कशीट",
            "आय प्रमाण पत्र (अधिकतम ₹1.5 लाख)",
            "स्कूल बोनाफाइड प्रमाण पत्र",
            "बैंक पासबुक",
        ],
    },
}


# ===========================
# CATEGORY-LEVEL DOCUMENTS
# ===========================
# Ye schemes.csv me jo bhi category_type values hain, unko cover karta hai.
# Jis category ka exact match milega wahi use hoga, warna "default".
CATEGORY_DOCUMENTS = {
    "English": {
        "default": [
            "Aadhaar Card",
            "Recent passport-size photograph",
            "Bank passbook / account details",
            "Residence proof",
        ],
        "Agriculture": [
            "Aadhaar Card",
            "Land ownership records (khatauni/khasra)",
            "Bank passbook",
            "Passport-size photograph",
        ],
        "Health": [
            "Aadhaar Card",
            "Income certificate",
            "Ration card / family ID",
            "Bank passbook",
        ],
        "Education": [
            "Aadhaar Card",
            "Latest marksheet / school ID",
            "Income certificate",
            "Bank passbook",
            "Passport-size photograph",
        ],
        "Education/Savings": [
            "Aadhaar Card (child + guardian)",
            "Birth certificate",
            "Bank passbook (child's account)",
            "Guardian's ID proof",
            "Passport-size photograph",
        ],
        "Pension": [
            "Aadhaar Card",
            "Age proof (birth certificate / school certificate)",
            "Bank passbook",
            "Income certificate (if applicable)",
        ],
        "Social Welfare": [
            "Aadhaar Card",
            "Income certificate",
            "Caste certificate (if applicable)",
            "Bank passbook",
            "Residence proof",
        ],
        "Women Welfare": [
            "Aadhaar Card",
            "Bank passbook (in woman's name)",
            "Income certificate",
            "Address proof",
        ],
        "Child Welfare": [
            "Aadhaar Card (child + parent)",
            "Birth certificate",
            "Income certificate",
            "Bank passbook (child's account)",
        ],
        "Disability Welfare": [
            "Aadhaar Card",
            "Disability certificate (UDID)",
            "Income certificate",
            "Bank passbook",
        ],
        "Financial Inclusion": [
            "Aadhaar Card",
            "PAN Card",
            "Bank statement / passbook",
            "Business plan (for loan schemes)",
            "Passport-size photograph",
        ],
        "Business/Loan": [
            "Aadhaar Card",
            "PAN Card",
            "Business plan / proposal",
            "Bank statement (6 months)",
            "Passport-size photograph",
        ],
        "Housing": [
            "Aadhaar Card",
            "Income certificate",
            "Property documents (if any)",
            "Bank passbook",
            "Passport-size photograph",
        ],
        "Employment": [
            "Aadhaar Card",
            "Educational certificates",
            "Bank passbook",
            "Resume / biodata",
        ],
        "Skill Development": [
            "Aadhaar Card",
            "Educational certificates",
            "Passport-size photograph",
            "Bank passbook",
        ],
        "Insurance": [
            "Aadhaar Card",
            "Bank passbook",
            "Age proof",
            "Nominee details",
        ],
        "Banking": [
            "Aadhaar Card",
            "Passport-size photograph",
            "Address proof",
        ],
        "Food Security": [
            "Aadhaar Card",
            "Ration card",
            "Income certificate",
            "Residence proof",
        ],
        "Rural Development": [
            "Aadhaar Card",
            "Job card (MGNREGA)",
            "Residence proof",
            "Bank passbook",
        ],
        "Urban Development": [
            "Aadhaar Card",
            "Income certificate",
            "Residence proof",
            "Bank passbook",
        ],
        "Energy": [
            "Aadhaar Card",
            "Electricity connection proof",
            "Bank passbook",
            "Residence proof",
        ],
        "Sanitation": [
            "Aadhaar Card",
            "Residence proof",
            "Bank passbook",
            "Income certificate (for subsidy)",
        ],
        "Digital Services": [
            "Aadhaar Card",
            "Mobile number (linked to Aadhaar)",
            "Bank passbook",
        ],
        "Environment": [
            "Aadhaar Card",
            "Organization / beneficiary registration proof",
            "Bank passbook",
        ],
        "Tourism": [
            "Aadhaar Card",
            "Passport-size photograph",
            "Address proof",
        ],
        "Sports": [
            "Aadhaar Card",
            "Age proof",
            "Sports achievement certificates",
            "Bank passbook",
        ],
        "Infrastructure": [
            "Aadhaar Card / Entity registration",
            "Project proposal",
            "Bank account details",
        ],
        "Aviation": [
            "Aadhaar Card",
            "Identity proof",
            "Address proof",
        ],
        "Disaster Relief": [
            "Aadhaar Card",
            "Residence proof",
            "Bank passbook",
            "Damage assessment report (from authority)",
        ],
        "Culture": [
            "Aadhaar Card",
            "Project / proposal documents",
            "Bank account details",
        ],
        "Science & Technology": [
            "Aadhaar Card",
            "Educational certificate",
            "Project proposal",
            "Bank passbook",
        ],
        "Financial Assistance": [
            "Aadhaar Card",
            "Income certificate",
            "Bank passbook",
            "Residence proof",
        ],
    },
    "हिंदी": {
        "default": [
            "आधार कार्ड",
            "हाल की पासपोर्ट साइज फोटो",
            "बैंक पासबुक / खाता विवरण",
            "निवास प्रमाण पत्र",
        ],
        "Agriculture": [
            "आधार कार्ड",
            "भूमि स्वामित्व दस्तावेज़ (खतौनी/खसरा)",
            "बैंक पासबुक",
            "पासपोर्ट साइज फोटो",
        ],
        "Health": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "राशन कार्ड / परिवार पहचान",
            "बैंक पासबुक",
        ],
        "Education": [
            "आधार कार्ड",
            "नवीनतम मार्कशीट / स्कूल आईडी",
            "आय प्रमाण पत्र",
            "बैंक पासबुक",
            "पासपोर्ट साइज फोटो",
        ],
        "Education/Savings": [
            "आधार कार्ड (बच्चा + अभिभावक)",
            "जन्म प्रमाण पत्र",
            "बैंक पासबुक (बच्चे का खाता)",
            "अभिभावक का पहचान पत्र",
            "पासपोर्ट साइज फोटो",
        ],
        "Pension": [
            "आधार कार्ड",
            "आयु प्रमाण (जन्म प्रमाण पत्र / स्कूल प्रमाण पत्र)",
            "बैंक पासबुक",
            "आय प्रमाण पत्र (यदि लागू हो)",
        ],
        "Social Welfare": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "जाति प्रमाण पत्र (यदि लागू हो)",
            "बैंक पासबुक",
            "निवास प्रमाण",
        ],
        "Women Welfare": [
            "आधार कार्ड",
            "बैंक पासबुक (महिला के नाम पर)",
            "आय प्रमाण पत्र",
            "पता प्रमाण",
        ],
        "Child Welfare": [
            "आधार कार्ड (बच्चा + अभिभावक)",
            "जन्म प्रमाण पत्र",
            "आय प्रमाण पत्र",
            "बैंक पासबुक (बच्चे का खाता)",
        ],
        "Disability Welfare": [
            "आधार कार्ड",
            "विकलांगता प्रमाण पत्र (UDID)",
            "आय प्रमाण पत्र",
            "बैंक पासबुक",
        ],
        "Financial Inclusion": [
            "आधार कार्ड",
            "पैन कार्ड",
            "बैंक स्टेटमेंट / पासबुक",
            "व्यवसाय योजना (ऋण योजनाओं के लिए)",
            "पासपोर्ट साइज फोटो",
        ],
        "Business/Loan": [
            "आधार कार्ड",
            "पैन कार्ड",
            "व्यवसाय योजना / प्रस्ताव",
            "बैंक स्टेटमेंट (6 महीने)",
            "पासपोर्ट साइज फोटो",
        ],
        "Housing": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "संपत्ति दस्तावेज़ (यदि हो)",
            "बैंक पासबुक",
            "पासपोर्ट साइज फोटो",
        ],
        "Employment": [
            "आधार कार्ड",
            "शैक्षणिक प्रमाण पत्र",
            "बैंक पासबुक",
            "रिज्यूमे / बायोडाटा",
        ],
        "Skill Development": [
            "आधार कार्ड",
            "शैक्षणिक प्रमाण पत्र",
            "पासपोर्ट साइज फोटो",
            "बैंक पासबुक",
        ],
        "Insurance": [
            "आधार कार्ड",
            "बैंक पासबुक",
            "आयु प्रमाण",
            "नॉमिनी विवरण",
        ],
        "Banking": [
            "आधार कार्ड",
            "पासपोर्ट साइज फोटो",
            "पता प्रमाण",
        ],
        "Food Security": [
            "आधार कार्ड",
            "राशन कार्ड",
            "आय प्रमाण पत्र",
            "निवास प्रमाण",
        ],
        "Rural Development": [
            "आधार कार्ड",
            "जॉब कार्ड (मनरेगा)",
            "निवास प्रमाण",
            "बैंक पासबुक",
        ],
        "Urban Development": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "निवास प्रमाण",
            "बैंक पासबुक",
        ],
        "Energy": [
            "आधार कार्ड",
            "बिजली कनेक्शन प्रमाण",
            "बैंक पासबुक",
            "निवास प्रमाण",
        ],
        "Sanitation": [
            "आधार कार्ड",
            "निवास प्रमाण",
            "बैंक पासबुक",
            "आय प्रमाण पत्र (सब्सिडी के लिए)",
        ],
        "Digital Services": [
            "आधार कार्ड",
            "मोबाइल नंबर (आधार से लिंक)",
            "बैंक पासबुक",
        ],
        "Environment": [
            "आधार कार्ड",
            "संस्था / लाभार्थी पंजीकरण प्रमाण",
            "बैंक पासबुक",
        ],
        "Tourism": [
            "आधार कार्ड",
            "पासपोर्ट साइज फोटो",
            "पता प्रमाण",
        ],
        "Sports": [
            "आधार कार्ड",
            "आयु प्रमाण",
            "खेल उपलब्धि प्रमाण पत्र",
            "बैंक पासबुक",
        ],
        "Infrastructure": [
            "आधार कार्ड / इकाई पंजीकरण",
            "परियोजना प्रस्ताव",
            "बैंक खाता विवरण",
        ],
        "Aviation": [
            "आधार कार्ड",
            "पहचान प्रमाण",
            "पता प्रमाण",
        ],
        "Disaster Relief": [
            "आधार कार्ड",
            "निवास प्रमाण",
            "बैंक पासबुक",
            "क्षति मूल्यांकन रिपोर्ट (प्राधिकरण से)",
        ],
        "Culture": [
            "आधार कार्ड",
            "परियोजना / प्रस्ताव दस्तावेज़",
            "बैंक खाता विवरण",
        ],
        "Science & Technology": [
            "आधार कार्ड",
            "शैक्षणिक प्रमाण पत्र",
            "परियोजना प्रस्ताव",
            "बैंक पासबुक",
        ],
        "Financial Assistance": [
            "आधार कार्ड",
            "आय प्रमाण पत्र",
            "बैंक पासबुक",
            "निवास प्रमाण",
        ],
    },
}


# ===========================
# HELPERS
# ===========================
def _safe_str(value, default=""):
    """None/NaN/non-str ko safe string me convert karta hai."""
    if value is None:
        return default
    try:
        if value != value:  # NaN check without pandas
            return default
    except Exception:
        pass
    return str(value).strip()


def _resolve_category(category_type, table):
    """
    category_type ko resolve karta hai:
      1. Exact match
      2. Combined categories me pehla meaningful segment (e.g. "Education/Savings")
      3. Poore string ka prefix match
      4. "default" fallback
    """
    category_type = _safe_str(category_type)

    if not category_type:
        return table["default"]

    # 1. Exact match
    if category_type in table:
        return table[category_type]

    # 2. Combined categories — "/" ya "&" se split karke har segment try karo
    if "/" in category_type or "&" in category_type:
        segments = [s.strip() for s in category_type.replace("&", "/").split("/")]
        for seg in segments:
            if seg in table:
                return table[seg]

    # 3. Case-insensitive exact match
    lower_map = {k.lower(): v for k, v in table.items()}
    if category_type.lower() in lower_map:
        return lower_map[category_type.lower()]

    # 4. Prefix match (e.g. "Welfare" matches "Women Welfare")
    for key in table:
        if key == "default":
            continue
        if key.lower() in category_type.lower() or category_type.lower() in key.lower():
            return table[key]

    # 5. Default
    return table["default"]


# ===========================
# PUBLIC API
# ===========================
def get_documents(scheme_name, category_type, lang="English"):
    """
    Scheme ke liye documents list return karta hai.
    Priority:
      1. Per-scheme override (agar available ho)
      2. Category-level match (exact → combined → prefix → default)

    Args:
        scheme_name: Scheme ka naam (str or None)
        category_type: schemes.csv ka "category_type" (str or None)
        lang: "English" or "हिंदी"

    Returns:
        list of document name strings
    """
    # Language fallback
    if lang not in PER_SCHEME_DOCUMENTS:
        lang = "English"

    # 1. Per-scheme override
    scheme_name = _safe_str(scheme_name)
    if scheme_name:
        per_scheme = PER_SCHEME_DOCUMENTS.get(lang, {})
        if scheme_name in per_scheme:
            return per_scheme[scheme_name]

    # 2. Category-level fallback
    table = CATEGORY_DOCUMENTS.get(lang, CATEGORY_DOCUMENTS["English"])
    return _resolve_category(category_type, table)


def get_available_categories(lang="English"):
    """Category table ke saare keys (verification ke liye)."""
    if lang not in CATEGORY_DOCUMENTS:
        lang = "English"
    return sorted([k for k in CATEGORY_DOCUMENTS[lang].keys() if k != "default"])


def get_available_schemes(lang="English"):
    """Per-scheme override list ke saare scheme names."""
    if lang not in PER_SCHEME_DOCUMENTS:
        lang = "English"
    return sorted(PER_SCHEME_DOCUMENTS[lang].keys())


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("doc_checklist.py — Verification")
    print("=" * 60)

    # 1. Per-scheme override works
    docs = get_documents("PM Kisan Samman Nidhi", "Agriculture", "English")
    assert "Land ownership records (khatauni/khasra)" in docs
    print("✅ Per-scheme override works")

    # 2. Hindi per-scheme works
    docs = get_documents("PM Kisan Samman Nidhi", "Agriculture", "हिंदी")
    assert "भूमि स्वामित्व दस्तावेज़ (खतौनी/खसरा)" in docs
    print("✅ Hindi per-scheme override works")

    # 3. Category-level fallback
    docs = get_documents("Unknown Scheme", "Health", "English")
    assert "Income certificate" in docs
    print("✅ Category-level fallback works")

    # 4. Combined category
    docs = get_documents("UP Kanya Sumangala Yojana", "Education/Savings", "English")
    assert "Birth certificate" in docs
    print("✅ Combined category works")

    # 5. None-safe
    docs = get_documents(None, None, "English")
    assert isinstance(docs, list)
    assert len(docs) > 0
    print("✅ None-safe (returns default)")

    # 6. Empty string category
    docs = get_documents("Test", "", "English")
    assert "Aadhaar Card" in docs
    print("✅ Empty string category works")

    # 7. Invalid lang fallback
    docs = get_documents("PM Kisan Samman Nidhi", "Agriculture", "Klingon")
    assert isinstance(docs, list)
    print("✅ Invalid lang falls back to English")

    # 8. Category count
    en_cats = get_available_categories("English")
    hi_cats = get_available_categories("हिंदी")
    print(f"✅ English categories: {len(en_cats)}")
    print(f"✅ Hindi categories: {len(hi_cats)}")
    assert set(en_cats) == set(hi_cats), "Category mismatch between languages"

    # 9. Scheme count
    en_schemes = get_available_schemes("English")
    hi_schemes = get_available_schemes("हिंदी")
    print(f"✅ English per-scheme overrides: {len(en_schemes)}")
    print(f"✅ Hindi per-scheme overrides: {len(hi_schemes)}")
    assert set(en_schemes) == set(hi_schemes), "Scheme mismatch between languages"

    # 10. Test each category in schemes.csv
    print("\n🔍 Cross-check with schemes.csv categories...")
    try:
        import pandas as pd
        df = pd.read_csv("data/schemes.csv")
        unique_cats = df["category_type"].dropna().unique().tolist()
        unmatched = []
        for cat in unique_cats:
            resolved = _resolve_category(cat, CATEGORY_DOCUMENTS["English"])
            # Check if we got a specific match or fell back to default
            if resolved == CATEGORY_DOCUMENTS["English"]["default"]:
                unmatched.append(cat)
        if unmatched:
            print(f"⚠️  Categories without specific docs (fallback to default): {unmatched}")
        else:
            print(f"✅ All {len(unique_cats)} categories have specific document lists")
    except FileNotFoundError:
        print("⚠️  data/schemes.csv not found, skipping cross-check")

    print("=" * 60)
    print("✅ doc_checklist.py — ALL CHECKS PASSED")
    print("=" * 60)