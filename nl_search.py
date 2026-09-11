"""
Natural language scheme search — v5 (Marriage keyword boost + Smart matching)
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SYNONYMS = {
    "Business/Loan": ["loan", "karza", "business", "vyapar", "udyog", "startup",
                       "mudra", "credit", "finance", "collateral", "udham", "business loan",
                       "ऋण", "व्यापार", "व्यवसाय", "कर्ज", "स्टार्टअप", "बिना गारंटी", "उद्यम", "पैसा"],
    
    "Education": ["scholarship", "study", "padhai", "school", "college", "university",
                  "student", "chatravriti", "fees", "shiksha", "admission", "exam", "marks",
                  "छात्रवृत्ति", "पढ़ाई", "स्कूल", "शिक्षा", "विद्यार्थी", "प्रवेश", "परीक्षा", 
                  "विश्वविद्यालय", "फीस", "निशुल्क शिक्षा", "किताबें", "स्टेशनरी"],
    
    "Health": ["health", "hospital", "ilaj", "medical", "bimari", "swasthya", "treatment",
               "insurance", "surgery", "doctor", "medicine", "dawai", "operation",
               "स्वास्थ्य", "इलाज", "अस्पताल", "बीमारी", "स्वस्थ", "दवाई", "डॉक्टर", "ऑपरेशन", 
               "मेडिकल", "चिकित्सा", "आयुष्मान", "बीमा"],
    
    "Pension": ["pension", "budhapa", "old age", "retirement", "senior citizen", "vridha",
                "monthly income", "सेवानिवृत्ति", "वृद्धावस्था", "पेंशन", "बुढ़ापा", "मासिक आय", 
                "सीनियर सिटीजन", "रिटायरमेंट", "बुजुर्ग"],
    
    "Agriculture": ["farmer", "kisan", "crop", "fasal", "kheti", "agriculture", "soil", 
                    "seed", "beej", "crop insurance", "irrigation", "solar pump", "tractor",
                    "किसान", "खेती", "फसल", "कृषि", "मिट्टी", "बीज", "फसल बीमा", "सिंचाई", 
                    "सोलर पंप", "ट्रैक्टर", "खाद", "उर्वरक"],
    
    "Welfare": ["welfare", "kalyan", "poor", "gareeb", "assistance", "sahayata", "madad",
                "BPL", "antodaya", "housing", "financial help", "free", "subsidy",
                "कल्याण", "गरीब", "सहायता", "मदद", "बीपीएल", "आवास", "मुफ्त", "सब्सिडी", 
                # ✅ MARRIAGE EXPANDED (English + Hindi + Hinglish)
                "shaadi", "marriage", "vivaah", "saadi", "vivah", "shadi", "kanyadan",
                "kanya vivah", "kanya vivaah", "marriage assistance", "marriage grant",
                "marriage scheme", "marriage loan", "shaadi anudan", "vivah anudan",
                "kanyadaan", "ladki ki shaadi", "beti ki shaadi", "ladki ke shaadi",
                "शादी", "विवाह", "विवाह अनुदान", "कन्यादान", "लड़की की शादी", "बेटी की शादी",
                "शादी अनुदान", "विवाह सहायता", "शादी सहायता", "कन्या विवाह",
                # Other welfare
                "लड़की", "ladki", "beti", "kanya", "बेटी", "कन्या", "दहेज", "dowry",
                "निःशुल्क गैस", "गैस कनेक्शन", "महिला", "औरत", "women", "female"],
    
    "Housing": ["house", "ghar", "awas", "home loan", "flat", "plot", "property", "pmaay",
                "construction", "मकान", "आवास", "ज़मीन", "फ्लैट", "संपत्ति", "गृह ऋण", "निर्माण", 
                "घर", "मकान"],
    
    "Employment": ["job", "rozgar", "employment", "naukri", "work", "vacancy", "interview",
                   "recruitment", "unemployment allowance", "नौकरी", "रोजगार", "काम", "भर्ती", 
                   "इंटरव्यू", "रिक्ति", "बेरोजगारी भत्ता", "स्वरोजगार", "self employment"],
    
    "Skill Development": ["skill", "training", "kaushal", "certificate", "course", 
                          "free training", "apprenticeship", "internship",
                          "कौशल", "प्रशिक्षण", "कौशल विकास", "प्रमाणपत्र", "कोर्स", 
                          "निःशुल्क प्रशिक्षण", "अप्रेंटिसशिप", "इंटर्नशिप", "ट्रेनिंग"],
    
    "Banking": ["bank account", "khata", "banking", "zero balance", "rupee card", "financial",
                "बैंक", "खाता", "बैंकिंग", "ज़ीरो बैलेंस", "रुपे कार्ड", "वित्तीय", "बचत", "सेविंग्स"],
    
    "Insurance": ["insurance", "bima", "cover", "accidental", "life insurance", "health cover",
                  "premium", "बीमा", "दुर्घटना", "जीवन बीमा", "स्वास्थ्य बीमा", "प्रीमियम", 
                  "सुरक्षा", "कवर"],
    
    "Food Security": ["food", "ration", "free food", "anna", "grains", "wheat", "rice",
                       "राशन", "भोजन", "मुफ्त भोजन", "अन्न", "अनाज", "गेहूं", "चावल", "किराना"],
    
    "Infrastructure": ["road", "sadak", "connectivity", "rural road", "sewerage", "water supply",
                        "सड़क", "सड़क कनेक्टिविटी", "ग्रामीण सड़क", "सीवरेज", "जल आपूर्ति", "बुनियादी ढांचा"],
    
    "Energy": ["solar", "electricity", "bijli", "power", "solar panel", "energy", "light",
               "सोलर", "बिजली", "ऊर्जा", "सोलर पैनल", "रोशनी", "सौर ऊर्जा", "बिजली बिल", "मुफ्त बिजली"],

    "Technology": ["digital", "internet", "cyber", "computer", "online", "e-governance", "tech",
                   "डिजिटल", "इंटरनेट", "साइबर", "कंप्यूटर", "ऑनलाइन", "ई-गवर्नेंस", "तकनीक", "डिजिटल इंडिया"],
    
    "Women": ["women", "mahila", "stree", "beti", "ladki", "girl child", "matru", "pregnant",
              "महिला", "स्त्री", "बेटी", "लड़की", "बालिका", "गर्भवती", "मातृ", "महिला सशक्तिकरण"],
}


# ===========================
# IMPORTANT KEYWORDS FOR BOOST
# ===========================
# Ye words query mein aaye to us scheme ko extra boost milega
HIGH_PRIORITY_KEYWORDS = {
    # Marriage
    "marriage": ["marriage", "shaadi", "vivaah", "vivah", "shadi", "kanyadan", 
                 "kanya vivah", "kanyadaan", "शादी", "विवाह", "कन्यादान", 
                 "ladki ki shaadi", "beti ki shaadi", "marriage assistance"],
    # Education
    "scholarship": ["scholarship", "chatravriti", "छात्रवृत्ति", "padhai", "study"],
    # Pension
    "pension": ["pension", "पेंशन", "vridha", "old age", "वृद्धावस्था"],
    # Loan
    "loan": ["loan", "karza", "कर्ज", "ऋण", "mudra", "credit"],
    # Farmer
    "farmer": ["kisan", "farmer", "किसान", "kheti", "खेती", "fasal", "फसल"],
    # Student
    "student": ["student", "छात्र", "विद्यार्थी", "college", "school"],
    # Health
    "health": ["health", "swasthya", "स्वास्थ्य", "ilaj", "इलाज", "hospital", "अस्पताल"],
    # Housing
    "housing": ["house", "ghar", "awas", "घर", "आवास", "makaan", "मकान"],
    # Women
    "women": ["women", "mahila", "महिला", "ladki", "लड़की", "beti", "बेटी"],
    # Disability
    "disability": ["disab", "divyang", "दिव्यांग", "viklang", "विकलांग"],
    # SC/ST/OBC
    "sc_st": ["sc", "st", "obc", "scheduled", "अनुसूचित", "पिछड़ा"],
}


def _scheme_text(row):
    base = f"{row['scheme_name']} {row['category_type']} {row['description']} {row['benefits']}"
    extra_words = SYNONYMS.get(row["category_type"], [])
    return base + " " + " ".join(extra_words)


def _build_corpus(df):
    return [_scheme_text(row) for _, row in df.iterrows()]


def _prefix_bonus(query, text, bonus_amount=0.35):
    query = query.lower().strip()
    if len(query) < 3:
        return 0.0
    words = text.lower().split()
    for w in words:
        w_clean = "".join(ch for ch in w if ch.isalnum())
        if w_clean.startswith(query):
            return bonus_amount
    return 0.0


# ===========================
# KEYWORD BOOST (NEW)
# ===========================
def _keyword_boost(query, text, boost_amount=0.4):
    """Agar query ke keywords text mein match karein, to boost do."""
    query_lower = query.lower()
    text_lower = text.lower()
    
    boost = 0.0
    matched_groups = 0
    
    for group_name, keywords in HIGH_PRIORITY_KEYWORDS.items():
        # Check if query has any keyword from this group
        query_has = any(kw.lower() in query_lower for kw in keywords)
        if not query_has:
            continue
        
        # Check if text has any keyword from this group
        text_has = any(kw.lower() in text_lower for kw in keywords)
        if text_has:
            matched_groups += 1
    
    # Har matched group ke liye bonus
    boost = min(matched_groups * boost_amount, 0.8)  # Max 0.8
    return boost


def search_schemes(df, query, top_n=8, min_score=0.03):
    if not query or not query.strip():
        return []
    
    corpus = _build_corpus(df)
    
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
    tfidf_matrix = vectorizer.fit_transform(corpus + [query])
    
    query_vector = tfidf_matrix[-1]
    scheme_vectors = tfidf_matrix[:-1]
    
    scores = cosine_similarity(query_vector, scheme_vectors).flatten()
    
    results = []
    for idx, base_score in enumerate(scores):
        # Prefix bonus (partial word match)
        prefix_b = _prefix_bonus(query, corpus[idx])
        
        # ✅ Keyword boost (NEW)
        keyword_b = _keyword_boost(query, corpus[idx])
        
        final_score = min(base_score + prefix_b + keyword_b, 1.0)
        
        if final_score >= min_score:
            row = df.iloc[idx]
            results.append({
                "scheme_name": row["scheme_name"],
                "category_type": row["category_type"],
                "applicable_state": row["applicable_state"],
                "description": row["description"],
                "benefits": row["benefits"],
                "apply_link": row["apply_link"],
                "deadline": row.get("deadline", None),
                "score": float(final_score),
            })
    
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_n]


def build_vocabulary(df):
    vocab = set()
    
    for _, row in df.iterrows():
        for w in str(row["scheme_name"]).split():
            w_clean = "".join(ch for ch in w if ch.isalnum())
            if len(w_clean) >= 3:
                vocab.add(w_clean)
        vocab.add(str(row["category_type"]))
    
    for words in SYNONYMS.values():
        for w in words:
            vocab.add(w)
    
    return sorted(vocab, key=str.lower)


def get_suggestions(vocab, partial_query, max_n=6):
    if not partial_query or len(partial_query.strip()) < 2:
        return []
    
    q = partial_query.strip().lower()
    
    prefix_matches = [w for w in vocab if w.lower().startswith(q)]
    substring_matches = [w for w in vocab if q in w.lower() and w not in prefix_matches]
    
    combined = prefix_matches + substring_matches
    
    seen = {q}
    unique = []
    for w in combined:
        key = w.lower()
        if key not in seen:
            seen.add(key)
            unique.append(w)
    
    if not unique:
        candidates = [q]
        if q.endswith("s") and len(q) > 3:
            candidates.append(q[:-1])
        
        for category, words in SYNONYMS.items():
            words_lower = [w.lower() for w in words]
            if any(c in words_lower for c in candidates):
                for w in words:
                    key = w.lower()
                    if key not in seen and key not in candidates:
                        seen.add(key)
                        unique.append(w)
                break
    
    return unique[:max_n]


if __name__ == "__main__":
    import pandas as pd
    df = pd.read_csv("data/schemes.csv")
    
    print("=== Marriage Search Test ===")
    for q in ["loan for marriage", "shaadi ke liye", "शादी के लिए", "kanya vivah", "marriage assistance"]:
        results = search_schemes(df, q, top_n=5)
        print(f"\n'{q}':")
        for r in results:
            print(f"  ({r['score']:.2f}) {r['scheme_name']}")