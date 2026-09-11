"""
Document checklist - per-scheme and category-level support.
"""

CATEGORY_DOCUMENTS = {
    "English": {
        "default": ["Aadhaar Card", "Recent passport-size photograph", "Bank passbook / account details",
                     "Residence proof"],
        "Agriculture": ["Aadhaar Card", "Land ownership records (khatauni/khasra)", "Bank passbook",
                          "Passport-size photograph"],
        "Health": ["Aadhaar Card", "Income certificate", "Ration card / family ID", "Bank passbook"],
        "Education": ["Aadhaar Card", "Latest marksheet / school ID", "Income certificate",
                       "Bank passbook", "Passport-size photograph"],
        "Pension": ["Aadhaar Card", "Age proof", "Bank passbook", "Income certificate (if applicable)"],
        "Business/Loan": ["Aadhaar Card", "PAN Card", "Business plan / proposal", "Bank statement"],
        "Welfare": ["Aadhaar Card", "Income certificate", "Caste certificate (if applicable)",
                    "Bank passbook"],
        "Housing": ["Aadhaar Card", "Income certificate", "Property documents (if any)", "Bank passbook"],
        "Employment": ["Aadhaar Card", "Educational certificates", "Bank passbook"],
        "Skill Development": ["Aadhaar Card", "Educational certificates", "Passport-size photograph"],
        "Insurance": ["Aadhaar Card", "Bank passbook", "Age proof"],
        "Banking": ["Aadhaar Card", "Passport-size photograph", "Address proof"],
        "Food Security": ["Aadhaar Card", "Ration card", "Income certificate"],
    },
    "हिंदी": {
        "default": ["आधार कार्ड", "हाल की पासपोर्ट साइज फोटो", "बैंक पासबुक / खाता विवरण", "निवास प्रमाण पत्र"],
        "Agriculture": ["आधार कार्ड", "भूमि स्वामित्व दस्तावेज़ (खतौनी/खसरा)", "बैंक पासबुक", "पासपोर्ट साइज फोटो"],
        "Health": ["आधार कार्ड", "आय प्रमाण पत्र", "राशन कार्ड / परिवार पहचान", "बैंक पासबुक"],
        "Education": ["आधार कार्ड", "नवीनतम मार्कशीट / स्कूल आईडी", "आय प्रमाण पत्र",
                       "बैंक पासबुक", "पासपोर्ट साइज फोटो"],
        "Pension": ["आधार कार्ड", "आयु प्रमाण", "बैंक पासबुक", "आय प्रमाण पत्र (यदि लागू हो)"],
        "Business/Loan": ["आधार कार्ड", "पैन कार्ड", "व्यवसाय योजना / प्रस्ताव", "बैंक स्टेटमेंट"],
        "Welfare": ["आधार कार्ड", "आय प्रमाण पत्र", "जाति प्रमाण पत्र (यदि लागू हो)", "बैंक पासबुक"],
        "Housing": ["आधार कार्ड", "आय प्रमाण पत्र", "संपत्ति दस्तावेज़ (यदि कोई हो)", "बैंक पासबुक"],
        "Employment": ["आधार कार्ड", "शैक्षणिक प्रमाण पत्र", "बैंक पासबुक"],
        "Skill Development": ["आधार कार्ड", "शैक्षणिक प्रमाण पत्र", "पासपोर्ट साइज फोटो"],
        "Insurance": ["आधार कार्ड", "बैंक पासबुक", "आयु प्रमाण"],
        "Banking": ["आधार कार्ड", "पासपोर्ट साइज फोटो", "पता प्रमाण"],
        "Food Security": ["आधार कार्ड", "राशन कार्ड", "आय प्रमाण पत्र"],
    },
}

PER_SCHEME_DOCUMENTS = {
    "English": {
        "PM Kisan Samman Nidhi": ["Aadhaar Card", "Land ownership records (khatauni/khasra)", 
                                   "Bank passbook", "Passport-size photograph"],
        "Ayushman Bharat (PM-JAY)": ["Aadhaar Card", "Income certificate", "Ration card / family ID",
                                      "Bank passbook"],
        "Sukanya Samriddhi Yojana": ["Aadhaar Card (for girl child)", "Birth certificate", 
                                      "Bank passbook", "Guardian's documents"],
        "Atal Pension Yojana": ["Aadhaar Card", "Bank account (with auto-debit facility)",
                                 "Age proof", "Passport-size photograph"],
        "PM Ujjwala Yojana": ["Aadhaar Card", "BPL ration card", "Bank passbook",
                               "Address proof"],
        "PM Mudra Yojana": ["Aadhaar Card", "PAN Card", "Business plan", "Bank statement",
                             "Passport-size photograph"],
    },
    "हिंदी": {
        "PM Kisan Samman Nidhi": ["आधार कार्ड", "भूमि स्वामित्व दस्तावेज़ (खतौनी/खसरा)", 
                                   "बैंक पासबुक", "पासपोर्ट साइज फोटो"],
        "Ayushman Bharat (PM-JAY)": ["आधार कार्ड", "आय प्रमाण पत्र", "राशन कार्ड / परिवार पहचान",
                                      "बैंक पासबुक"],
        "Sukanya Samriddhi Yojana": ["आधार कार्ड (बेटी के लिए)", "जन्म प्रमाण पत्र", 
                                      "बैंक पासबुक", "अभिभावक का दस्तावेज़"],
        "Atal Pension Yojana": ["आधार कार्ड", "बैंक खाता (ऑटो-डेबिट सुविधा के साथ)",
                                 "आयु प्रमाण", "पासपोर्ट साइज फोटो"],
        "PM Ujjwala Yojana": ["आधार कार्ड", "बीपीएल राशन कार्ड", "बैंक पासबुक",
                               "पता प्रमाण"],
        "PM Mudra Yojana": ["आधार कार्ड", "पैन कार्ड", "व्यवसाय योजना", "बैंक स्टेटमेंट",
                             "पासपोर्ट साइज फोटो"],
    },
}


def get_documents(scheme_name, category_type, lang="English"):
    per_scheme = PER_SCHEME_DOCUMENTS.get(lang, PER_SCHEME_DOCUMENTS["English"])
    if scheme_name in per_scheme:
        return per_scheme[scheme_name]
    
    table = CATEGORY_DOCUMENTS.get(lang, CATEGORY_DOCUMENTS["English"])
    
    if category_type in table:
        return table[category_type]
    
    first_part = category_type.split("/")[0].strip()
    if first_part in table:
        return table[first_part]
    
    return table["default"]