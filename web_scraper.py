"""
Web Scraper for Government Schemes — DETAIL-PAGE VERSION (v4)

v3 se aage badhta hai. Is version (v4) mein 2 naye improvements hain:

  A) CATEGORY_TYPE AUTO-DETECTION (keyword-based mapping)
     Pehle 'category_type' hamesha khaali reh jaata tha (comment tha:
     "regex se reliably classify nahi ho sakta"). Ab ek keyword->category
     mapping table (CATEGORY_TYPE_KEYWORDS) hai jo scheme name + page text
     dono mein keywords dhoondh ke best-guess category assign karta hai
     (Education / Health / Pension / Agriculture / Housing / Employment /
     Women & Child / Business & MSME / Disability / Financial Inclusion /
     Other). Ye bhi best-effort hai (100% accurate nahi), isliye staging
     file mein review zaroori hai.

  B) STATE-SPECIFIC PORTALS
     Pehle sirf central portals (india.gov.in, scholarships.gov.in,
     myscheme.gov.in) the — jo mostly CENTRAL schemes dikhate hain.
     Ab LISTING_SOURCES mein state-specific govt scheme portals bhi add
     kiye hain (MP, UP, Maharashtra — aur aasani se aur states add kar
     sakte ho). Har state-source ko "state" key diya hai; jab us source
     se koi scheme discover hoti hai, to uska applicable_state seedha
     us state se set ho jaata hai (regex-guess ki zaroorat nahi padti
     state-sources ke liye). Central sources ke liye ab bhi text-based
     best-effort state-detection (STATE_NAME_PATTERNS) chalta hai —
     agar kisi central scheme ke page mein ek hi state ka naam baar-baar
     aaye to wahi assign hota hai, warna "All".

Baaki sab v3 jaisa hi hai:
  - TWO-STAGE scraping (listing pages -> detail pages)
  - Regex se: min_age/max_age, max_annual_income, social_category,
    gender, deadline, benefits, description
  - JS-heavy sites ke liye Selenium (headless Chrome)
  - STRICT 3-way dedup (main csv + staging csv + current batch), naam
    normalize karke
  - Scraped data seedha schemes.csv mein MERGE nahi hota — staging file
    (data/scraped_candidates.csv) mein jaata hai, manual review ke liye

REQUIREMENTS (requirements.txt mein add karo):
    selenium
    webdriver-manager
    python-dateutil
    lxml
    beautifulsoup4
    requests

SYSTEM REQUIREMENT: Chrome/Chromium browser installed hona chahiye
(webdriver-manager sirf matching driver download karta hai, browser
khud install nahi karta). Streamlit Cloud jaise managed hosting par
Chrome install karna mushkil ho sakta hai — is scraper ko local machine
ya apne server par chalana zyada reliable rahega.

NOTE: Ye code yahan is sandbox mein live gov.in / state-govt sites ke
against test NAHI kiya gaya hai (network access restricted hai). Apne
local machine par `streamlit run app.py` se test karo. State-portal
URLs/markup samay ke saath badal sakte hain — agar koi source 0 links
de raha hai to sabse pehle us site ko browser mein khol ke check karo
ki URL/markup abhi bhi wahi hai ya badal gaya.
"""

import os
import re
import time
import json
import hashlib
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
import streamlit as st

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

# ===========================
# CONFIGURATION
# ===========================
MAIN_CSV_FILE = "data/schemes.csv"
STAGING_CSV_FILE = "data/scraped_candidates.csv"
VISITED_LOG_FILE = "data/scraped_visited_urls.csv"   # already-visited detail pages (resume support)
SCHEDULE_STATE_FILE = "data/scraper_schedule.json"   # auto-scraping ka on/off + last-run tracking

os.makedirs("data", exist_ok=True)

SCHEME_COLUMNS = [
    "scheme_name", "category_type", "min_age", "max_age", "max_annual_income",
    "applicable_state", "social_category", "occupation", "gender", "description",
    "benefits", "apply_link", "deadline", "form_link"
]

# ===========================
# LISTING SOURCES
# ===========================
# 'use_selenium': True un sites ke liye jo JS-rendered hain.
# 'state': agar diya gaya, to is source se milne wali HAR scheme ka
#          applicable_state seedha isi value se set hoga (regex-guess
#          ki zaroorat nahi). Central/multi-state sources ke liye
#          'state' key OMIT karo — unke liye text-based best-effort
#          detection chalegi (STATE_NAME_PATTERNS).
LISTING_SOURCES = [
    # ---- CENTRAL PORTALS (multi-state / all-India schemes) ----
    {"url": "https://www.india.gov.in/topics/schemes", "use_selenium": False, "max_pages": 5},
    {"url": "https://scholarships.gov.in/", "use_selenium": False, "max_pages": 3},
    {"url": "https://www.myscheme.gov.in/find-scheme", "use_selenium": True, "max_pages": 10},
    # PIB (Press Information Bureau) — naye scheme announcements/launches
    # yahan jaldi aate hain, isliye "latest schemes" ke liye acha source hai.
    {"url": "https://pib.gov.in/AllReleasem.aspx?MenuId=3", "use_selenium": True, "max_pages": 5},

    # ---- STATE-SPECIFIC PORTALS ----
    # Madhya Pradesh
    {"url": "https://mp.gov.in/en/web/guest/schemes", "use_selenium": False, "max_pages": 5, "state": "Madhya Pradesh"},
    {"url": "https://cmhelpline.mp.gov.in/", "use_selenium": True, "max_pages": 3, "state": "Madhya Pradesh"},

    # Uttar Pradesh
    {"url": "https://up.gov.in/en/schemes", "use_selenium": False, "max_pages": 5, "state": "Uttar Pradesh"},
    {"url": "https://jansunwai.up.nic.in/", "use_selenium": True, "max_pages": 3, "state": "Uttar Pradesh"},

    # Maharashtra
    {"url": "https://www.maharashtra.gov.in/Site/Common/InnerRightview.aspx?count=1&Sub_MenuID=118", "use_selenium": False, "max_pages": 5, "state": "Maharashtra"},
    {"url": "https://aaplesarkar.mahaonline.gov.in/en/Login/Login", "use_selenium": True, "max_pages": 3, "state": "Maharashtra"},

    # NOTE: Aur states add karne ke liye bas ek naya dict entry daal do,
    # jaise:
    # {"url": "https://rajasthan.gov.in/schemes", "use_selenium": False,
    #  "max_pages": 5, "state": "Rajasthan"},
]

GARBAGE_NAMES = [
    "institute", "officer", "apply for one time registration (otr)", "apply for scholarship",
    "schemes on nsp", "scholarship eligibility", "application status", "registration form",
    "dashboard", "nsp helpdesk", "grievance registration", "contact us",
    "unknown scheme", "apply now!", "student", "students", "nsp otr app", "institutes",
    "how to fill registration form", "officers", "nodal officers (scheme-wise)",
    "grievance redressal officers (gros)", "public", "find institutes on nsp",
    "list of applicants processed for scholarships", "nodal officers (district-wise)",
    "pfms helpdesk", "csc login", "about nsp", "site map", "announcements", "helpdesk",
    "institutions", "fellowship", "view more", "copyright policy", "terms and conditions",
    "hyperlink", "screen reader", "calendar", "view sitemap", "content sources",
    "india portal 2.0 brochure", "translationdisclaimer",
    "back to home page", "about us", "accessibility statement", "frequently asked questions",
    "disclaimer", "terms & conditions", "skip to content", "di ecosystem",
    "click here", "apply now", "none", "application", "read more", "learn more", "login",
    "register", "home", "about", "contact", "faq", "help", "privacy policy", "terms",
    "sitemap", "logout", "sign in", "sign up", "search", "menu", "close",
]

SCHEME_KEYWORDS = ["yojana", "scheme", "scholarship", "pension", "mission",
                   "bima", "nidhi", "sahayata", "kanya", "ladli", "awas", "kisan",
                   "abhiyan", "programme", "program", "card", "fund"]

URL_KEYWORDS = ["scheme", "yojana", "scholarship", "nsp", "benefit",
                "pension", "loan", "housing", "health", "education"]


# ===========================
# VALID SCHEME NAME DETECTION
# ===========================
def is_valid_scheme_name(name):
    if not name or len(name.strip()) < 6:
        return False
    name_clean = name.strip()
    name_lower = name_clean.lower()
    if name_lower in GARBAGE_NAMES:
        return False
    if re.match(r'^[\d\s\-\./]+$', name_clean):
        return False
    if not re.search(r'[a-zA-Z]', name_clean):
        return False
    word_count = len(name_clean.split())
    has_keyword = any(k in name_lower for k in SCHEME_KEYWORDS)
    if has_keyword:
        return True
    if word_count >= 3:
        return True
    return False


def normalize_name(name):
    """Dedup ke liye naam ko normalize karta hai — lowercase, punctuation/extra
    space hata ke, taaki 'Ladli Behna Yojana' aur 'Ladli  Behna, Yojana!' same maane jaayen."""
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'[^a-z0-9\s]', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n


# ===========================
# HTML FETCHING (static vs selenium)
# ===========================
_selenium_driver = None

def get_selenium_driver():
    """Headless Chrome driver ko lazily start karta hai (sirf JS-heavy sites ke liye)."""
    global _selenium_driver
    if _selenium_driver is not None:
        return _selenium_driver
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    service = Service(ChromeDriverManager().install())
    _selenium_driver = webdriver.Chrome(service=service, options=options)
    return _selenium_driver


def close_selenium_driver():
    global _selenium_driver
    if _selenium_driver is not None:
        try:
            _selenium_driver.quit()
        except Exception:
            pass
        _selenium_driver = None


def fetch_html(url, use_selenium=False, wait_seconds=3, timeout=15, retries=2):
    """Ek URL ka rendered HTML laata hai. Retry ke saath — pehli koshish fail ho to
    dusri baar alag headers/thoda wait ke saath try karta hai.
    Returns: (html_or_None, error_message_or_None)"""
    last_error = None
    for attempt in range(retries):
        if use_selenium:
            try:
                driver = get_selenium_driver()
                driver.get(url)
                time.sleep(wait_seconds)
                return driver.page_source, None
            except Exception as e:
                last_error = f"Selenium error: {e}"
                time.sleep(1)
        else:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,hi;q=0.8",
                "Referer": "https://www.google.com/",
            }
            try:
                resp = requests.get(url, headers=headers, timeout=timeout)
                resp.raise_for_status()
                return resp.text, None
            except requests.exceptions.RequestException as e:
                last_error = f"{type(e).__name__}: {e}"
                time.sleep(1.5)
    return None, last_error


# ===========================
# REGEX EXTRACTORS (best-effort — hamesha 100% sahi nahi honge, isliye
# manual review zaroori hai staging file par)
# ===========================
AGE_PATTERNS = [
    re.compile(r'(?:age|आयु)[^\d]{0,15}?(\d{1,2})\s*(?:to|-|–|se|और)\s*(\d{1,2})\s*(?:years?|वर्ष)', re.I),
    re.compile(r'(\d{1,2})\s*(?:to|-|–)\s*(\d{1,2})\s*years\s*of\s*age', re.I),
]
MIN_AGE_ONLY = re.compile(r'(?:minimum age|min\.?\s*age|कम से कम आयु)[^\d]{0,10}(\d{1,2})', re.I)
MAX_AGE_ONLY = re.compile(r'(?:maximum age|max\.?\s*age|अधिकतम आयु)[^\d]{0,10}(\d{1,2})', re.I)

INCOME_PATTERNS = [
    re.compile(r'(?:income|आय)[^\d₹Rs]{0,20}?(?:rs\.?|₹|inr)?\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|लाख)?', re.I),
]

CATEGORY_KEYWORDS = {
    "SC": r'\bsc\b|scheduled caste',
    "ST": r'\bst\b|scheduled tribe',
    "OBC": r'\bobc\b|other backward class',
    "EWS": r'\bews\b|economically weaker',
    "Minority": r'minorit(?:y|ies)',
    "General": r'\bgeneral category\b',
}

GENDER_KEYWORDS = {
    "Female": r'\bwomen\b|\bfemale\b|\bgirls?\b|mahila|beti',
    "Male": r'\bmen\b(?!tion)|\bmale\b|\bboys?\b',
}

DEADLINE_PATTERNS = [
    re.compile(r'(?:last date|deadline|closing date|apply before)[^\d]{0,20}([\d]{1,2}[\/\-\s](?:[A-Za-z]+|\d{1,2})[\/\-\s]\d{2,4})', re.I),
]

BENEFITS_HEADING = re.compile(r'benefits?\s*[:\-]?\s*', re.I)

# ---------------------------------------------------------------------------
# (A) CATEGORY_TYPE KEYWORD MAPPING
# ---------------------------------------------------------------------------
# Order matters: pehle jo pattern match ho jaaye wahi category assign hoti
# hai, isliye zyada "specific" categories upar rakhi hain aur generic
# waali (jaise Financial Inclusion / Employment) neeche.
# Har category ke liye keywords English + Hindi/Hinglish dono mein hain
# taaki bilingual scheme names/text par bhi match ho sake.
CATEGORY_TYPE_KEYWORDS = [
    ("Education", r'scholarship|shiksha|education|school|college|student|chatra|vidya|padhai|tuition|fee waiver'),
    ("Health", r'health|ayushman|bima\s*yojana|insurance|hospital|medical|swasthya|nirogi|treatment|maternity|janani'),
    ("Pension", r'pension|old age|senior citizen|vridha|vridhavastha|social security pension'),
    ("Agriculture", r'kisan|farmer|krishi|agricult|crop|fasal|irrigation|sinchai|dairy|fisher(?:y|ies)|animal husbandry'),
    ("Housing", r'awas|housing|ghar|pucca house|indira awas|pmay'),
    ("Women & Child", r'kanya|beti|ladli|mahila|women|girl child|matru|anganwadi|widow|vidhwa'),
    ("Disability", r'divyang|disab(?:led|ility)|handicap|viklang'),
    ("Business & MSME", r'msme|udyam|udyog|business loan|startup|self[- ]?employ|swarozgar|mudra|entrepreneur'),
    ("Employment", r'employ(?:ment)?|rozgar|skill development|training|apprentice|job\b'),
    ("Financial Inclusion", r'bank account|jan dhan|subsidy|financial inclusion|direct benefit transfer|\bdbt\b'),
]


def extract_category_type(name, text):
    """Scheme ka best-guess category keyword-matching se nikalta hai.
    Pehle scheme NAME par try karta hai (zyada reliable, kam noise),
    fir agar wahan match na mile to poore PAGE TEXT par try karta hai.
    Kuch bhi match na ho to khaali string return karta hai (manual
    review ke waqt admin khud bhar sakta hai)."""
    name_lower = (name or "").lower()
    for category, pattern in CATEGORY_TYPE_KEYWORDS:
        if re.search(pattern, name_lower, re.I):
            return category

    text_lower = (text or "").lower()
    for category, pattern in CATEGORY_TYPE_KEYWORDS:
        if re.search(pattern, text_lower, re.I):
            return category

    return ""


# ---------------------------------------------------------------------------
# (B) STATE DETECTION (central sources ke liye best-effort fallback)
# ---------------------------------------------------------------------------
# Agar source khud "state" tag ke saath aaya hai (state-specific portal),
# to ye list use hi nahi hoti — seedha source ka state assign ho jaata hai.
# Ye sirf central/multi-state sources (jaha state pata nahi) ke liye hai.
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Delhi", "Jammu and Kashmir", "Ladakh", "Puducherry",
    "Chandigarh",
]

STATE_NAME_PATTERNS = [(s, re.compile(r'\b' + re.escape(s) + r'\b', re.I)) for s in INDIAN_STATES]


def extract_state_from_text(text):
    """Central/multi-state source ke page text mein agar EK hi state ka
    naam baar-baar (aur sirf usi ka) mention ho, to wahi state return
    karta hai — matlab scheme us particular state ke liye hai (e.g. ek
    central-listed page jo actually kisi ek state-scheme ka detail ho).
    Agar 0 ya 2+ alag states mention hon, to "All" return karta hai
    (ambiguous / genuinely multi-state / central scheme)."""
    if not text:
        return "All"
    matched_states = set()
    for state, pattern in STATE_NAME_PATTERNS:
        if pattern.search(text):
            matched_states.add(state)
            if len(matched_states) > 1:
                return "All"
    if len(matched_states) == 1:
        return next(iter(matched_states))
    return "All"


def extract_age(text):
    for pat in AGE_PATTERNS:
        m = pat.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
    min_age = MIN_AGE_ONLY.search(text)
    max_age = MAX_AGE_ONLY.search(text)
    return (int(min_age.group(1)) if min_age else None,
            int(max_age.group(1)) if max_age else None)


def extract_income(text):
    for pat in INCOME_PATTERNS:
        m = pat.search(text)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if m.group(2) and "lakh" in m.group(2).lower():
                val *= 100000
            return int(val)
    return None


def extract_category(text):
    for cat, pattern in CATEGORY_KEYWORDS.items():
        if re.search(pattern, text, re.I):
            return cat
    return ""


def extract_gender(text):
    for gender, pattern in GENDER_KEYWORDS.items():
        if re.search(pattern, text, re.I):
            return gender
    return "All"


def extract_deadline(text):
    for pat in DEADLINE_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1)
            if date_parser:
                try:
                    return date_parser.parse(raw, dayfirst=True, fuzzy=True).strftime("%Y-%m-%d")
                except Exception:
                    return raw
            return raw
    return ""


def extract_benefits(soup):
    """'Benefits' heading dhoondh ke uske baad ka text/list nikalta hai."""
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
        if BENEFITS_HEADING.match(tag.get_text(strip=True)):
            collected = []
            for sib in tag.find_next_siblings():
                if sib.name in ["h1", "h2", "h3", "h4"]:
                    break
                text = sib.get_text(" ", strip=True)
                if text:
                    collected.append(text)
                if len(" ".join(collected)) > 400:
                    break
            if collected:
                return " ".join(collected)[:500]
    return ""


def extract_description(soup):
    """Page ka main intro paragraph best-effort nikalta hai (meta description ya pehla bada <p>)."""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content") and len(meta["content"]) > 30:
        return meta["content"][:300]
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) > 60:
            return text[:300]
    return ""


def extract_fields_from_detail_page(html, scheme_name, detail_url, state_hint=None):
    """Ek scheme ke poore detail-page HTML se saari fields regex/heuristics se nikalta hai.

    state_hint: agar diya gaya (state-specific source se aaya), to
    applicable_state seedha isi se set hoga. Agar None hai (central
    source), to page text se best-effort detect (extract_state_from_text)
    kiya jaata hai, warna "All"."""
    soup = BeautifulSoup(html, "lxml")
    # scripts/styles ko text extraction se hata do
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    full_text = soup.get_text(" ", strip=True)

    min_age, max_age = extract_age(full_text)

    scheme = {col: "" for col in SCHEME_COLUMNS}
    scheme["scheme_name"] = scheme_name
    scheme["applicable_state"] = state_hint if state_hint else extract_state_from_text(full_text)
    scheme["social_category"] = extract_category(full_text) or "All"
    scheme["occupation"] = "All"
    scheme["gender"] = extract_gender(full_text)
    scheme["description"] = extract_description(soup)
    scheme["benefits"] = extract_benefits(soup)
    scheme["apply_link"] = detail_url
    scheme["form_link"] = detail_url
    scheme["deadline"] = extract_deadline(full_text)
    scheme["min_age"] = min_age if min_age is not None else ""
    scheme["max_age"] = max_age if max_age is not None else ""
    income = extract_income(full_text)
    scheme["max_annual_income"] = income if income is not None else ""
    # (A) category_type ab keyword-mapping se best-guess fill hoti hai
    # (pehle jaan-boojh kar khaali chhodi jaati thi).
    scheme["category_type"] = extract_category_type(scheme_name, full_text)
    return scheme


# ===========================
# STAGE 1: DISCOVER DETAIL-PAGE LINKS FROM LISTING PAGES
# ===========================
def find_next_page_url(soup, current_url):
    """Pagination ka 'Next' link dhoondta hai (best-effort — sites alag-alag markup use karte hain)."""
    next_link = soup.find("a", string=re.compile(r'next|अगला', re.I))
    if not next_link:
        next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])
    return None


def discover_scheme_links(source, delay_seconds=1.0):
    """Ek listing source (aur uske pagination pages) se (name, detail_url) pairs nikalta hai."""
    found = []
    seen_names = set()
    url = source["url"]
    use_selenium = source.get("use_selenium", False)
    max_pages = source.get("max_pages", 3)

    for page_num in range(max_pages):
        if not url:
            break
        html, error = fetch_html(url, use_selenium=use_selenium)
        if not html:
            if error:
                st.caption(f"⚠️ {url} — {error}")
            break
        soup = BeautifulSoup(html, "lxml")

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True)
            if not is_valid_scheme_name(text):
                continue
            full_url = urljoin(url, link["href"])
            if not any(k in full_url.lower() for k in URL_KEYWORDS):
                continue
            key = normalize_name(text)
            if key in seen_names:
                continue
            seen_names.add(key)
            found.append((text, full_url))

        next_url = find_next_page_url(soup, url)
        time.sleep(delay_seconds)
        if next_url == url:
            break
        url = next_url

    return found


# ===========================
# ALREADY-VISITED TRACKING (resume support, avoid re-scraping same URL)
# ===========================
def load_visited_urls():
    if os.path.exists(VISITED_LOG_FILE):
        try:
            return set(pd.read_csv(VISITED_LOG_FILE)["url"].tolist())
        except Exception:
            return set()
    return set()


def append_visited_url(url):
    df = pd.DataFrame([{"url": url}])
    header = not os.path.exists(VISITED_LOG_FILE)
    df.to_csv(VISITED_LOG_FILE, mode="a", header=header, index=False)


# ===========================
# DATA CLEANER
# ===========================
def clean_data(df):
    if df.empty:
        return df
    df["_norm_name"] = df["scheme_name"].apply(normalize_name)
    df = df.drop_duplicates(subset=["_norm_name"], keep="first")
    df = df[~df["_norm_name"].isin([normalize_name(g) for g in GARBAGE_NAMES])]
    df = df[df["scheme_name"].str.len() >= 6]
    df = df.drop(columns=["_norm_name"])

    for col in SCHEME_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for col in ["min_age", "max_age", "max_annual_income"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df[SCHEME_COLUMNS]


# ===========================
# SAVE TO STAGING (strict 3-way dedup: main csv + staging csv + current batch)
# ===========================
def save_to_staging(new_schemes):
    new_df = pd.DataFrame(new_schemes, columns=SCHEME_COLUMNS)
    new_df = clean_data(new_df)
    if new_df.empty:
        return new_df

    new_df["_norm_name"] = new_df["scheme_name"].apply(normalize_name)

    existing_norm_names = set()
    if os.path.exists(MAIN_CSV_FILE):
        try:
            main_df = pd.read_csv(MAIN_CSV_FILE)
            existing_norm_names |= set(main_df["scheme_name"].apply(normalize_name))
        except Exception:
            pass

    if os.path.exists(STAGING_CSV_FILE):
        try:
            staging_df = pd.read_csv(STAGING_CSV_FILE)
            existing_norm_names |= set(staging_df["scheme_name"].apply(normalize_name))
        except Exception:
            staging_df = pd.DataFrame(columns=SCHEME_COLUMNS)
    else:
        staging_df = pd.DataFrame(columns=SCHEME_COLUMNS)

    new_df = new_df[~new_df["_norm_name"].isin(existing_norm_names)]
    new_df = new_df.drop(columns=["_norm_name"])

    if new_df.empty:
        return new_df

    combined = pd.concat([staging_df, new_df], ignore_index=True)
    combined = clean_data(combined)
    combined.to_csv(STAGING_CSV_FILE, index=False)
    return new_df


# ===========================
# STAGING -> MAIN CSV (sirf tab hota hai jab user "Add to schemes.csv" button dabaye)
# ===========================
def merge_staging_to_main(selected_names=None):
    """
    Staging file (scraped_candidates.csv) ke schemes ko main schemes.csv mein
    APPEND karta hai — sirf jab ye function explicitly call ho (button click par).
    Scraping khud se kabhi ye nahi karta.

    selected_names: agar diya gaya (list of scheme_name), to sirf unhi rows ko
    add karega — warna staging ke SAARE rows add honge.

    Merge ke baad: successfully add hui rows staging file se hata di jaati hain
    (taaki dobara add na ho jaayein), baaki (agar selective add tha) staging
    mein reh jaati hain.

    Returns: (added_count, added_df)
    """
    if not os.path.exists(STAGING_CSV_FILE):
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    try:
        staging_df = pd.read_csv(STAGING_CSV_FILE)
    except Exception:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    if staging_df.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    for col in SCHEME_COLUMNS:
        if col not in staging_df.columns:
            staging_df[col] = ""

    if selected_names is not None:
        selected_norm = {normalize_name(n) for n in selected_names}
        to_add = staging_df[staging_df["scheme_name"].apply(normalize_name).isin(selected_norm)]
    else:
        to_add = staging_df.copy()

    if to_add.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    # Main csv load / create karo
    if os.path.exists(MAIN_CSV_FILE):
        try:
            main_df = pd.read_csv(MAIN_CSV_FILE)
        except Exception:
            main_df = pd.DataFrame(columns=SCHEME_COLUMNS)
    else:
        main_df = pd.DataFrame(columns=SCHEME_COLUMNS)

    for col in SCHEME_COLUMNS:
        if col not in main_df.columns:
            main_df[col] = ""

    # Final safety dedup — main csv mein already naam se match na ho
    existing_norm_names = set(main_df["scheme_name"].apply(normalize_name))
    to_add = to_add[~to_add["scheme_name"].apply(normalize_name).isin(existing_norm_names)]

    if to_add.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    to_add = to_add[SCHEME_COLUMNS]
    merged_main = pd.concat([main_df, to_add], ignore_index=True)
    merged_main = clean_data(merged_main)
    merged_main.to_csv(MAIN_CSV_FILE, index=False)

    # Ab jo add ho gaya, use staging se hata do (baaki, agar selective add tha, reh jaayega)
    added_norm = set(to_add["scheme_name"].apply(normalize_name))
    remaining_staging = staging_df[~staging_df["scheme_name"].apply(normalize_name).isin(added_norm)]
    remaining_staging.to_csv(STAGING_CSV_FILE, index=False)

    return len(to_add), to_add


# ===========================
# MAIN TWO-STAGE SCRAPER
# ===========================
def run_web_scraper(sources=None, max_detail_pages_per_source=50, delay_seconds=1.0):
    """
    Stage 1: har source se scheme links discover karo.
    Stage 2: har link ke detail page par jaake fields extract karo
             (state-specific source ho to uska 'state' field bhi
             applicable_state ke liye pass hota hai).
    Naye schemes staging file mein jaate hain (dedup ke saath).
    """
    if sources is None:
        sources = LISTING_SOURCES

    visited = load_visited_urls()
    all_scraped_schemes = []
    fetch_log = []   # diagnostics: (source_url, scheme_name, detail_url, status, detail)

    for source in sources:
        state_hint = source.get("state")   # None for central sources, else e.g. "Madhya Pradesh"
        source_label = f"{source['url']}" + (f" [{state_hint}]" if state_hint else " [central]")

        with st.status(f"Discovering links from {source_label}...") as status:
            links = discover_scheme_links(source, delay_seconds=delay_seconds)
            status.update(label=f"Found {len(links)} candidate links from {source_label}", state="complete")

        links_to_visit = [(n, u) for n, u in links if u not in visited][:max_detail_pages_per_source]

        if not links_to_visit and links:
            st.caption(
                f"ℹ️ {source_label} se saare {len(links)} links pehle hi visited ho chuke hain "
                f"(purani run mein). Naye results ke liye 'data/scraped_visited_urls.csv' delete karo."
            )

        progress = st.progress(0.0, text=f"Scraping detail pages from {source_label}...")
        for i, (name, detail_url) in enumerate(links_to_visit):
            html, error = fetch_html(detail_url, use_selenium=source.get("use_selenium", False))
            if html:
                scheme = extract_fields_from_detail_page(html, name, detail_url, state_hint=state_hint)
                all_scraped_schemes.append(scheme)
                append_visited_url(detail_url)   # sirf success par visited mark karo
                fetch_log.append((source_label, name, detail_url, "✅ OK", ""))
            else:
                # Fail hone par visited MARK NAHI karte — taaki agli baar retry ho sake
                fetch_log.append((source_label, name, detail_url, "❌ Failed", error or "Unknown error"))
            time.sleep(delay_seconds)
            progress.progress((i + 1) / max(len(links_to_visit), 1))

    close_selenium_driver()

    staged_new = save_to_staging(all_scraped_schemes)

    ok_count = sum(1 for row in fetch_log if row[3].startswith("✅"))
    fail_count = sum(1 for row in fetch_log if row[3].startswith("❌"))

    if fetch_log:
        with st.expander(f"🔍 Fetch details ({ok_count} OK, {fail_count} failed)", expanded=(fail_count > 0 and ok_count == 0)):
            log_df = pd.DataFrame(fetch_log, columns=["source", "scheme_name", "detail_url", "status", "error"])
            st.dataframe(log_df, use_container_width=True, height=250)

    if fail_count > 0 and ok_count == 0:
        st.error(
            "Saare detail-page fetch fail hue. Common causes: (1) site bot-traffic block kar rahi hai "
            "(403/timeout — upar 'error' column check karo), (2) site JS-rendered hai aur "
            "'use_selenium: True' set nahi hai us source ke liye, (3) internet/firewall issue, "
            "(4) state-portal ka URL/markup badal gaya ho (state sites often redesign hote rehte hain)."
        )

    st.success(
        f"Done. {len(staged_new)} NAYE candidate schemes '{STAGING_CSV_FILE}' mein add hue "
        f"(review ke liye) — main dataset touch nahi hua."
    )
    return staged_new


# ===========================
# SCHEDULED / AUTO SCRAPING
# ===========================
def load_schedule_state():
    """Auto-scraping ka state load karta hai: enabled?, last run kab hua, kitni baar chala."""
    default = {"enabled": False, "last_scrape": None, "scrape_count": 0, "interval_hours": 24}
    if os.path.exists(SCHEDULE_STATE_FILE):
        try:
            with open(SCHEDULE_STATE_FILE, "r") as f:
                state = json.load(f)
            for k, v in default.items():
                state.setdefault(k, v)
            return state
        except Exception:
            return default
    return default


def save_schedule_state(state):
    os.makedirs("data", exist_ok=True)
    with open(SCHEDULE_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def set_auto_scraping_enabled(enabled, interval_hours=24):
    """UI ke checkbox se call hota hai — auto-scraping on/off karta hai."""
    state = load_schedule_state()
    state["enabled"] = enabled
    state["interval_hours"] = interval_hours
    save_schedule_state(state)
    return state


def get_scrape_stats():
    """Dashboard ke liye stats: total schemes (main csv), last scrape time, scrape count."""
    total_schemes = 0
    if os.path.exists(MAIN_CSV_FILE):
        try:
            total_schemes = len(pd.read_csv(MAIN_CSV_FILE))
        except Exception:
            total_schemes = 0
    state = load_schedule_state()
    last_scrape_raw = state.get("last_scrape")
    
    # ✅ Sirf date dikhao (time hatao)
    if last_scrape_raw:
        try:
            # "2026-09-10 22:19:16" → "2026-09-10"
            last_scrape = last_scrape_raw.split(" ")[0]
        except Exception:
            last_scrape = last_scrape_raw
    else:
        last_scrape = "Never"
    
    scrape_count = state.get("scrape_count", 0)
    return total_schemes, last_scrape, scrape_count


def setup_scheduled_scraping(interval_hours=24, sources=None, max_detail_pages_per_source=50):
    """
    App start hone par call hota hai. Agar auto-scraping ON hai aur
    'interval_hours' se zyada time ho gaya hai last run ke baad, to
    scraper apne aap chal jaata hai aur state update ho jaati hai.
    Auto-scraping OFF hone par kuch nahi karta (bas state return karta hai).
    """
    state = load_schedule_state()

    if not state.get("enabled"):
        return state

    last_scrape_str = state.get("last_scrape")
    due = True
    if last_scrape_str:
        try:
            last_scrape_dt = datetime.strptime(last_scrape_str, "%Y-%m-%d %H:%M:%S")
            due = datetime.now() - last_scrape_dt >= timedelta(hours=state.get("interval_hours", interval_hours))
        except Exception:
            due = True

    if not due:
        return state

    run_web_scraper(sources=sources, max_detail_pages_per_source=max_detail_pages_per_source)

    state["last_scrape"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["scrape_count"] = state.get("scrape_count", 0) + 1
    save_schedule_state(state)
    return state


# ===========================
# STREAMLIT UI
# ===========================
def render_web_scraper_ui():
    st.markdown("### Web Scraping (Detail-Page Mode)")
    st.caption(
        "Har scheme ke detail page par jaake poora text padhta hai aur regex se "
        "age/income/category/gender/deadline/benefits/category_type nikalne ki koshish karta hai. "
        "State-specific portals se aayi schemes ka state seedha tag ho jaata hai; central portals "
        "ke liye state best-effort text-detection se aata hai. Result ek review file mein jaata hai, "
        "main schemes.csv ko seedha modify nahi karta."
    )
    st.warning(
        "Har scrape ke baad staging file ko manually review karke hi "
        "main dataset mein copy karo."
    )

    total_schemes, last_scrape, scrape_count = get_scrape_stats()
    stat1, stat2, stat3 = st.columns(3)
    stat1.metric("Total Schemes", total_schemes)
    stat2.metric("Last Scrape", last_scrape)
    stat3.metric("Scrape Count", scrape_count)

    st.divider()

    st.markdown("#### 📍 Active Sources")
    source_rows = []
    for s in LISTING_SOURCES:
        source_rows.append({
            "URL": s["url"],
            "Type": "Selenium (JS)" if s.get("use_selenium") else "Static",
            "State": s.get("state", "Central / Multi-state"),
            "Max Pages": s.get("max_pages", 3),
        })
    st.dataframe(pd.DataFrame(source_rows), use_container_width=True, height=220)

    st.divider()

    max_pages = st.slider("Max detail pages per source", 5, 200, 50)
    delay = st.slider("Delay between requests (seconds)", 0.5, 5.0, 1.0)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🕸️ Run Web Scraper Now", type="primary", use_container_width=True, key="run_scraper_btn"):
            df = run_web_scraper(max_detail_pages_per_source=max_pages, delay_seconds=delay)
            state = load_schedule_state()
            state["last_scrape"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            state["scrape_count"] = state.get("scrape_count", 0) + 1
            save_schedule_state(state)
            if len(df) > 0:
                st.dataframe(df.head(10))

    with col2:
        if os.path.exists(STAGING_CSV_FILE):
            with open(STAGING_CSV_FILE, "rb") as f:
                st.download_button(
                    "Download Staging File", data=f, file_name="scraped_candidates.csv",
                    mime="text/csv", use_container_width=True,
                )

    st.markdown("#### 📅 Scheduled Scraping")
    schedule_state = load_schedule_state()
    auto_enabled = st.checkbox(
        "Enable Auto-Scraping (Every 24 hours)",
        value=schedule_state.get("enabled", False),
        key="auto_scrape_checkbox",
    )
    if auto_enabled != schedule_state.get("enabled", False):
        set_auto_scraping_enabled(auto_enabled, interval_hours=24)
        st.toast("✅ Auto-Scraping ON" if auto_enabled else "🛑 Auto-Scraping OFF")
        st.rerun()
    

    # ===========================
    # REVIEW STAGING + ADD TO schemes.csv (sirf yahan se main dataset update hota hai)
    # ===========================
    st.markdown("#### 📋 Review Scraped Candidates")

    if os.path.exists(STAGING_CSV_FILE):
        try:
            staging_df = pd.read_csv(STAGING_CSV_FILE)
        except Exception:
            staging_df = pd.DataFrame(columns=SCHEME_COLUMNS)
    else:
        staging_df = pd.DataFrame(columns=SCHEME_COLUMNS)

    if staging_df.empty:
        st.info("No new candidate schemes are in staging right now. Please run the scraper first.")
    else:
        st.caption(f"{len(staging_df)} candidate schemes review ke liye taiyaar hain.")

        # Quick filter by category_type / state taaki review aasan ho
        filt_col1, filt_col2 = st.columns(2)
        with filt_col1:
            cat_options = ["All"] + sorted([c for c in staging_df["category_type"].dropna().unique() if c])
            cat_filter = st.selectbox("Filter by category_type", cat_options, key="staging_cat_filter")
        with filt_col2:
            state_options = ["All"] + sorted([s for s in staging_df["applicable_state"].dropna().unique() if s])
            state_filter = st.selectbox("Filter by state", state_options, key="staging_state_filter")

        display_df = staging_df.copy()
        if cat_filter != "All":
            display_df = display_df[display_df["category_type"] == cat_filter]
        if state_filter != "All":
            display_df = display_df[display_df["applicable_state"] == state_filter]

        st.dataframe(display_df, use_container_width=True, height=300)

        selected = st.multiselect(
            "Sirf specific schemes add karni hain? (khaali chhodo to SAARI [filtered] add hongi)",
            options=display_df["scheme_name"].tolist(),
            key="staging_select",
        )

        add_col1, add_col2 = st.columns(2)
        with add_col1:
            if st.button("➕ Add to schemes.csv", type="primary", use_container_width=True, key="add_to_main_btn"):
                names_to_add = selected if selected else display_df["scheme_name"].tolist()
                added_count, added_df = merge_staging_to_main(selected_names=names_to_add)
                if added_count > 0:
                    st.success(f"✅ {added_count} scheme(s) 'schemes.csv' mein add ho gaye!")
                    st.rerun()
                else:
                    st.warning("Kuch add nahi hua — ho sakta hai ye schemes already schemes.csv mein hon (duplicate).")

        with add_col2:
            if st.button("🗑️ Clear Staging (bina add kiye)", use_container_width=True, key="clear_staging_btn"):
                pd.DataFrame(columns=SCHEME_COLUMNS).to_csv(STAGING_CSV_FILE, index=False)
                st.toast("🗑️ Staging file clear ho gayi")
                st.rerun()


if __name__ == "__main__":
    import sys
    if "streamlit" not in sys.modules or not hasattr(st, "runtime"):
        print("Tip: 'streamlit run' se chalao poore UI ke saath.")
    result = run_web_scraper()
    print(result)