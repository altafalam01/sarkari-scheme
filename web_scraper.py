"""
Web Scraper for Government Schemes — DETAIL-PAGE VERSION (v5, hardened)

v4 ke upar v5 mein sirf RELIABILITY / SAFETY fixes hain (10 bugs), feature-set
same hai (two-stage scraping, category_type auto-detect, state-specific
portals). Konsa bug kahaan fix hua hai, wo har jagah `# BUG #N FIX:` comment
se clearly maarked hai.

  BUG #1  — Selenium driver leak                -> try/finally around scrape loop
  BUG #2  — Non-atomic schemes.csv write         -> _atomic_csv_write()
  BUG #3  — setup_scheduled_scraping() crash     -> try/except around run_web_scraper()
  BUG #4  — No CSV validation                    -> _validate_scheme_csv()
  BUG #5  — No per-source health tracking        -> data/source_health.json
  BUG #6  — Selenium ImportError kills scrape    -> _SELENIUM_AVAILABLE guard
  BUG #7  — Race condition on schedule json      -> _atomic_json_write()
  BUG #8  — Partial-add double-add risk          -> ordered atomic main-then-staging write
  BUG #9  — Non-atomic visited_urls append       -> save_visited_urls_batch() (in-memory + one atomic write)
  BUG #10 — No self-test                         -> __main__ offline test suite

Baaki sab v4 jaisa hi hai:
  - TWO-STAGE scraping (listing pages -> detail pages)
  - Regex se: min_age/max_age, max_annual_income, social_category,
    gender, deadline, benefits, description
  - JS-heavy sites ke liye Selenium (headless Chrome)
  - CATEGORY_TYPE auto-detection (keyword-based)
  - STATE-SPECIFIC portals (state seedha tag ho jaata hai) + central
    sources ke liye text-based best-effort state detection
  - STRICT 3-way dedup (main csv + staging csv + current batch)
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
khud install nahi karta). Agar selenium / webdriver-manager installed
nahi hain, ya Chrome missing hai, to Selenium-based sources SKIP ho
jaayenge (crash nahi) — BUG #6 FIX.

NOTE: Ye code is sandbox mein live gov.in / state-govt sites ke against
test NAHI kiya gaya hai (network access restricted hai). Apne local
machine par `streamlit run app.py` se test karo. State-portal URLs/markup
samay ke saath badal sakte hain — agar koi source 0 links de raha hai
(ya Source Health section mein "broken" dikh raha hai) to sabse pehle us
site ko browser mein khol ke check karo ki URL/markup abhi bhi wahi hai.
"""

import os
import re
import time
import json
import tempfile
import traceback
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import requests

# Streamlit is optional at import-time so this module can be imported /
# self-tested from a plain `python web_scraper.py` context without a
# Streamlit runtime available.
try:
    import streamlit as st
except ImportError:  # pragma: no cover - streamlit should normally be present
    st = None

try:
    from dateutil import parser as date_parser
except ImportError:
    date_parser = None

# BUG #6 FIX: check Selenium/webdriver-manager availability ONCE at module
# load. If missing, we don't crash — we just skip Selenium-based sources
# later (with a warning) instead of raising ImportError mid-scrape.
_SELENIUM_AVAILABLE = True
try:
    from selenium import webdriver  # noqa: F401
    from selenium.webdriver.chrome.options import Options  # noqa: F401
    from selenium.webdriver.chrome.service import Service  # noqa: F401
    from webdriver_manager.chrome import ChromeDriverManager  # noqa: F401
except ImportError:
    _SELENIUM_AVAILABLE = False


def _st_safe(fn_name, *args, **kwargs):
    """Style requirement #5: safely call an st.* function even when this
    module is imported outside a real Streamlit runtime (e.g. self-test,
    scheduled background call, plain script). Never raises."""
    if st is None:
        return None
    try:
        fn = getattr(st, fn_name, None)
        if fn is None:
            return None
        return fn(*args, **kwargs)
    except Exception:
        return None


# ===========================
# CONFIGURATION
# ===========================
DATA_DIR = "data"
MAIN_CSV_FILE = os.path.join(DATA_DIR, "schemes.csv")
STAGING_CSV_FILE = os.path.join(DATA_DIR, "scraped_candidates.csv")
VISITED_LOG_FILE = os.path.join(DATA_DIR, "scraped_visited_urls.csv")   # already-visited detail pages (resume support)
SCHEDULE_STATE_FILE = os.path.join(DATA_DIR, "scraper_schedule.json")  # auto-scraping ka on/off + last-run tracking
SOURCE_HEALTH_FILE = os.path.join(DATA_DIR, "source_health.json")      # BUG #5: per-source health metrics

os.makedirs(DATA_DIR, exist_ok=True)

SCHEME_COLUMNS = [
    "scheme_name", "category_type", "min_age", "max_age", "max_annual_income",
    "applicable_state", "social_category", "occupation", "gender", "description",
    "benefits", "apply_link", "deadline", "form_link"
]


# ===========================
# STYLE HELPERS (project conventions)
# ===========================
def _safe_str(value, default=""):
    """None/NaN/empty-string ko safely handle karta hai — kabhi bhi 'nan'
    string ya crash nahi dega."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def _safe_remove(path):
    """Best-effort file delete — file na ho ya permission issue ho to bhi crash nahi karta."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _quarantine_corrupt_file(path):
    """Corrupt JSON/CSV file ko delete karne ke bajaye '.corrupt' extension
    de ke side mein rakh deta hai — taaki data lost na ho aur debug ho sake."""
    try:
        if not os.path.exists(path):
            return
        corrupt = path + ".corrupt"
        if os.path.exists(corrupt):
            corrupt = f"{path}.{int(time.time())}.corrupt"
        os.replace(path, corrupt)
    except OSError:
        pass


def _atomic_write_bytes(path, write_fn):
    """Generic atomic-write helper: temp file mein likho, fir os.replace() se
    swap karo. write_fn(tmp_path) is the caller-provided function that
    actually writes content to tmp_path."""
    dir_path = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", suffix=".part", dir=dir_path)
    os.close(fd)
    try:
        write_fn(tmp_path)
        os.replace(tmp_path, path)
        return True
    except Exception:
        _safe_remove(tmp_path)
        return False


def _atomic_csv_write(df, path):
    """BUG #2 / #7-style fix, generalized for any DataFrame: write to a temp
    file in the same directory, then os.replace() so readers never see a
    half-written CSV even on power loss / crash mid-write."""
    return _atomic_write_bytes(path, lambda tmp: df.to_csv(tmp, index=False))


def _atomic_json_write(path, data):
    """Atomic JSON write — same reasoning as _atomic_csv_write, used for
    scraper_schedule.json and source_health.json (BUG #7 fix)."""
    def _write(tmp):
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
    return _atomic_write_bytes(path, _write)


def _validate_scheme_csv(df):
    """BUG #4 FIX: sanity-check a loaded schemes DataFrame before using it.
    Returns True only if df is non-empty and has the minimum required columns."""
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return False
    required = {"scheme_name", "category_type", "applicable_state"}
    return required.issubset(set(df.columns))


def _load_scheme_csv_safe(path):
    """Load a schemes-shaped CSV with corruption handling: on parse failure,
    quarantine the bad file and return an empty, correctly-shaped DataFrame
    instead of crashing the caller."""
    if not os.path.exists(path):
        return pd.DataFrame(columns=SCHEME_COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception:
        _quarantine_corrupt_file(path)
        return pd.DataFrame(columns=SCHEME_COLUMNS)
    if not _validate_scheme_csv(df):
        # Missing required columns / empty-but-present file: quarantine so
        # the admin can inspect it, then hand back a clean empty frame.
        _quarantine_corrupt_file(path)
        return pd.DataFrame(columns=SCHEME_COLUMNS)
    for col in SCHEME_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[SCHEME_COLUMNS]


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
    """Heuristic filter to reject nav-menu junk ('Contact Us', 'Login', etc.)
    while keeping plausible scheme names."""
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
# SELENIUM DRIVER MANAGEMENT
# ===========================
_selenium_driver = None


def get_selenium_driver():
    """Headless Chrome driver ko lazily start karta hai (sirf JS-heavy sites
    ke liye). BUG #6 FIX: caller (fetch_html) already checks
    _SELENIUM_AVAILABLE before calling this, so an ImportError here should
    not normally happen — but we still let real Selenium/WebDriver errors
    (Chrome missing, driver mismatch, etc.) propagate so fetch_html can log
    them per-URL instead of crashing the whole scrape."""
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
    """Chrome driver ko safely band karta hai. Idempotent — dobara call karne
    se error nahi aata."""
    global _selenium_driver
    if _selenium_driver is not None:
        try:
            _selenium_driver.quit()
        except Exception:
            pass
        _selenium_driver = None


# ===========================
# HTML FETCHING (static vs selenium)
# ===========================
def fetch_html(url, use_selenium=False, wait_seconds=3, timeout=15, retries=2):
    """Ek URL ka rendered HTML laata hai. Retry ke saath — pehli koshish fail
    ho to dusri baar thoda wait ke saath try karta hai.

    BUG #6 FIX: agar use_selenium=True hai lekin selenium/webdriver-manager
    installed nahi hain, to turant (koi retry ki koshish kiye bina) ek clear
    error message ke saath return karta hai, taaki caller us source ko
    gracefully skip kar sake.

    Returns: (html_or_None, error_message_or_None)"""
    if use_selenium and not _SELENIUM_AVAILABLE:
        return None, "Selenium not available (selenium/webdriver-manager not installed, or Chrome missing)"

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
# CATEGORY_TYPE KEYWORD MAPPING
# ---------------------------------------------------------------------------
# Order matters: pehle jo pattern match ho jaaye wahi category assign hoti
# hai, isliye zyada "specific" categories upar rakhi hain aur generic
# waali (jaise Financial Inclusion / Employment) neeche.
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
# STATE DETECTION (central sources ke liye best-effort fallback)
# ---------------------------------------------------------------------------
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
    karta hai. Agar 0 ya 2+ alag states mention hon, to "All" return
    karta hai (ambiguous / genuinely multi-state / central scheme)."""
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
    """Page ka main intro paragraph best-effort nikalta hai (meta description
    ya pehla bada <p>)."""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content") and len(meta["content"]) > 30:
        return meta["content"][:300]
    for p in soup.find_all("p"):
        text = p.get_text(" ", strip=True)
        if len(text) > 60:
            return text[:300]
    return ""


def extract_fields_from_detail_page(html, scheme_name, detail_url, state_hint=None):
    """Ek scheme ke poore detail-page HTML se saari fields regex/heuristics
    se nikalta hai.

    state_hint: agar diya gaya (state-specific source se aaya), to
    applicable_state seedha isi se set hoga. Agar None hai (central
    source), to page text se best-effort detect (extract_state_from_text)
    kiya jaata hai, warna "All"."""
    soup = BeautifulSoup(html, "lxml")
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
    scheme["category_type"] = extract_category_type(scheme_name, full_text)
    return scheme


# ===========================
# STAGE 1: DISCOVER DETAIL-PAGE LINKS FROM LISTING PAGES
# ===========================
def find_next_page_url(soup, current_url):
    """Pagination ka 'Next' link dhoondta hai (best-effort — sites alag-alag
    markup use karte hain)."""
    next_link = soup.find("a", string=re.compile(r'next|अगला', re.I))
    if not next_link:
        next_link = soup.find("a", attrs={"rel": "next"})
    if next_link and next_link.get("href"):
        return urljoin(current_url, next_link["href"])
    return None


def discover_scheme_links(source, delay_seconds=1.0):
    """Ek listing source (aur uske pagination pages) se (name, detail_url)
    pairs nikalta hai. Returns (found_pairs, fetch_errors_list)."""
    found = []
    seen_names = set()
    errors = []
    url = source["url"]
    use_selenium = source.get("use_selenium", False)
    max_pages = source.get("max_pages", 3)

    for page_num in range(max_pages):
        if not url:
            break
        html, error = fetch_html(url, use_selenium=use_selenium)
        if not html:
            if error:
                errors.append(error)
                _st_safe("caption", f"⚠️ {url} — {error}")
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

    return found, errors


# ===========================
# ALREADY-VISITED TRACKING (resume support, avoid re-scraping same URL)
# ===========================
def load_visited_urls():
    """Visited-URL set load karta hai. Corrupt file ho to quarantine karke
    khaali set return karta hai (crash nahi)."""
    if not os.path.exists(VISITED_LOG_FILE):
        return set()
    try:
        df = pd.read_csv(VISITED_LOG_FILE)
        if "url" not in df.columns:
            _quarantine_corrupt_file(VISITED_LOG_FILE)
            return set()
        return set(df["url"].dropna().tolist())
    except Exception:
        _quarantine_corrupt_file(VISITED_LOG_FILE)
        return set()


def save_visited_urls_batch(new_urls, existing_set):
    """BUG #9 FIX: pehle ye function har URL ke baad file ko append-mode
    mein khol ke likhta tha — crash mid-write se CSV corrupt ho sakta tha.
    Ab poore scrape ke dauraan visited URLs sirf IN-MEMORY collect hote hain
    (existing_set + new_urls), aur end mein EK hi atomic write hoti hai."""
    combined = set(existing_set) | set(u for u in new_urls if u)
    if not combined:
        return True
    df = pd.DataFrame({"url": sorted(combined)})
    return _atomic_csv_write(df, VISITED_LOG_FILE)


# ===========================
# DATA CLEANER
# ===========================
def clean_data(df):
    if df.empty:
        return df
    df = df.copy()
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
    """Naye scraped schemes ko staging file mein add karta hai, main csv aur
    existing staging dono ke against dedup karke. BUG #4 FIX: main/staging
    dono _load_scheme_csv_safe() se load hote hain, isliye corrupt/malformed
    files crash nahi karvatin."""
    new_df = pd.DataFrame(new_schemes, columns=SCHEME_COLUMNS)
    new_df = clean_data(new_df)
    if new_df.empty:
        return new_df

    new_df["_norm_name"] = new_df["scheme_name"].apply(normalize_name)

    existing_norm_names = set()
    main_df = _load_scheme_csv_safe(MAIN_CSV_FILE)
    if not main_df.empty:
        existing_norm_names |= set(main_df["scheme_name"].apply(normalize_name))

    staging_df = _load_scheme_csv_safe(STAGING_CSV_FILE)
    if not staging_df.empty:
        existing_norm_names |= set(staging_df["scheme_name"].apply(normalize_name))

    new_df = new_df[~new_df["_norm_name"].isin(existing_norm_names)]
    new_df = new_df.drop(columns=["_norm_name"])

    if new_df.empty:
        return new_df

    combined = pd.concat([staging_df, new_df], ignore_index=True)
    combined = clean_data(combined)
    _atomic_csv_write(combined, STAGING_CSV_FILE)  # BUG #2-style fix applied here too
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

    BUG #2 FIX: main csv ka write ab atomic hai (temp file + os.replace) —
    crash/power-cut se schemes.csv corrupt nahi hoga.

    BUG #8 FIX (partial-add safety): order of operations hamesha:
        1. Read staging + main (safely, via _load_scheme_csv_safe)
        2. Compute rows to add (dedup against main)
        3. Atomic-write NEW main (with additions) FIRST
        4. Only if step 3 succeeds -> atomic-write NEW staging (with removals)
    Agar step 3 fail ho jaaye, to staging untouched rehta hai (kuch add nahi
    hua maana jaata) — no double-write risk. Agar step 3 succeed ho jaaye
    lekin step 4 (staging cleanup) fail ho jaaye, to worst case ye hai ki
    wahi scheme staging mein bhi reh jaati hai — lekin agli baar isi function
    ke "existing_norm_names" check (step 2) use dobara add hone se rok dega,
    isliye schemes.csv mein KABHI double-add nahi hoga.

    Returns: (added_count, added_df)
    """
    staging_df = _load_scheme_csv_safe(STAGING_CSV_FILE)
    if staging_df.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    if selected_names is not None:
        selected_norm = {normalize_name(n) for n in selected_names}
        to_add = staging_df[staging_df["scheme_name"].apply(normalize_name).isin(selected_norm)]
    else:
        to_add = staging_df.copy()

    if to_add.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    main_df = _load_scheme_csv_safe(MAIN_CSV_FILE)

    # Final safety dedup — main csv mein already naam se match na ho
    existing_norm_names = set(main_df["scheme_name"].apply(normalize_name)) if not main_df.empty else set()
    to_add = to_add[~to_add["scheme_name"].apply(normalize_name).isin(existing_norm_names)]

    if to_add.empty:
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    to_add = to_add[SCHEME_COLUMNS]
    merged_main = pd.concat([main_df, to_add], ignore_index=True)
    merged_main = clean_data(merged_main)

    # Step 3: atomic write of NEW main FIRST.
    main_write_ok = _atomic_csv_write(merged_main, MAIN_CSV_FILE)
    if not main_write_ok:
        # Main csv write failed — nothing was added, staging left untouched.
        return 0, pd.DataFrame(columns=SCHEME_COLUMNS)

    # Step 4: only after main is safely written, remove added rows from staging.
    added_norm = set(to_add["scheme_name"].apply(normalize_name))
    remaining_staging = staging_df[~staging_df["scheme_name"].apply(normalize_name).isin(added_norm)]
    _atomic_csv_write(remaining_staging, STAGING_CSV_FILE)

    return len(to_add), to_add


# ===========================
# SOURCE HEALTH TRACKING (BUG #5 FIX)
# ===========================
def load_source_health():
    """Per-source health metrics load karta hai. Corrupt file -> quarantine + empty dict."""
    if not os.path.exists(SOURCE_HEALTH_FILE):
        return {}
    try:
        with open(SOURCE_HEALTH_FILE, "r") as f:
            return json.load(f)
    except Exception:
        _quarantine_corrupt_file(SOURCE_HEALTH_FILE)
        return {}


def _compute_health_status(links_found, links_fetched, errors):
    """'broken' agar site se koi link hi nahi mila (site redesign ka signal),
    'warning' agar error-rate > 30%, warna 'ok'."""
    if links_found == 0:
        return "broken"
    attempted = links_fetched + errors
    error_rate = (errors / attempted) if attempted > 0 else 0.0
    if error_rate > 0.30:
        return "warning"
    return "ok"


def record_source_health(source_url, links_found, links_fetched, errors):
    """Ek source ke liye health entry update karta hai aur atomically save
    karta hai (BUG #7-style atomic write applied here too)."""
    health = load_source_health()
    health[source_url] = {
        "last_run": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "links_found": links_found,
        "links_fetched": links_fetched,
        "errors": errors,
        "health": _compute_health_status(links_found, links_fetched, errors),
    }
    _atomic_json_write(SOURCE_HEALTH_FILE, health)
    return health[source_url]


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

    BUG #1 FIX: poora scraping loop try/finally mein wrap kiya gaya hai, taaki
    Chrome driver har haal mein (exception, network error, parsing error,
    ya normal completion) close ho — zombie Chrome processes accumulate
    nahi honge.

    BUG #6 FIX: Selenium-based sources, agar Selenium available nahi hai,
    to gracefully SKIP ho jaate hain (warning ke saath), scrape crash nahi
    hoti.

    BUG #9 FIX: visited URLs is run ke dauraan sirf in-memory collect hoti
    hain aur end mein EK hi atomic write se save hoti hain.
    """
    if sources is None:
        sources = LISTING_SOURCES

    visited = load_visited_urls()
    newly_visited = []
    all_scraped_schemes = []
    fetch_log = []   # diagnostics: (source_url, scheme_name, detail_url, status, detail)

    try:
        for source in sources:
            state_hint = source.get("state")   # None for central sources, else e.g. "Madhya Pradesh"
            source_label = f"{source['url']}" + (f" [{state_hint}]" if state_hint else " [central]")
            use_selenium = source.get("use_selenium", False)

            # BUG #6 FIX: skip Selenium sources gracefully if unavailable.
            if use_selenium and not _SELENIUM_AVAILABLE:
                _st_safe("warning", f"⏭️ Skipping {source_label} — Selenium/webdriver-manager not installed.")
                record_source_health(source["url"], links_found=0, links_fetched=0, errors=1)
                fetch_log.append((source_label, "", "", "⏭️ Skipped", "Selenium not available"))
                continue

            status_ctx = None
            if st is not None:
                try:
                    status_ctx = st.status(f"Discovering links from {source_label}...")
                    status_ctx.__enter__()
                except Exception:
                    status_ctx = None

            links, discover_errors = discover_scheme_links(source, delay_seconds=delay_seconds)

            if status_ctx is not None:
                try:
                    status_ctx.update(label=f"Found {len(links)} candidate links from {source_label}", state="complete")
                    status_ctx.__exit__(None, None, None)
                except Exception:
                    pass

            links_to_visit = [(n, u) for n, u in links if u not in visited][:max_detail_pages_per_source]

            if not links_to_visit and links:
                _st_safe(
                    "caption",
                    f"ℹ️ {source_label} se saare {len(links)} links pehle hi visited ho chuke hain "
                    f"(purani run mein). Naye results ke liye '{VISITED_LOG_FILE}' delete karo."
                )

            progress = _st_safe("progress", 0.0, text=f"Scraping detail pages from {source_label}...")
            source_fetched = 0
            source_errors = len(discover_errors)

            for i, (name, detail_url) in enumerate(links_to_visit):
                html, error = fetch_html(detail_url, use_selenium=use_selenium)
                if html:
                    scheme = extract_fields_from_detail_page(html, name, detail_url, state_hint=state_hint)
                    all_scraped_schemes.append(scheme)
                    newly_visited.append(detail_url)   # sirf success par visited mark karenge (batch save end mein)
                    fetch_log.append((source_label, name, detail_url, "✅ OK", ""))
                    source_fetched += 1
                else:
                    # Fail hone par visited mark NAHI karte — taaki agli baar retry ho sake
                    fetch_log.append((source_label, name, detail_url, "❌ Failed", error or "Unknown error"))
                    source_errors += 1
                time.sleep(delay_seconds)
                if progress is not None:
                    try:
                        progress.progress((i + 1) / max(len(links_to_visit), 1))
                    except Exception:
                        pass

            # BUG #5 FIX: log per-source health after each source finishes.
            record_source_health(
                source["url"],
                links_found=len(links),
                links_fetched=source_fetched,
                errors=source_errors,
            )
    finally:
        # BUG #1 FIX: this runs no matter what happened above (success,
        # exception, or even a KeyboardInterrupt), so the Chrome driver
        # never leaks.
        close_selenium_driver()

    # BUG #9 FIX: single atomic batch write of visited URLs at the very end.
    save_visited_urls_batch(newly_visited, visited)

    staged_new = save_to_staging(all_scraped_schemes)

    ok_count = sum(1 for row in fetch_log if row[3].startswith("✅"))
    fail_count = sum(1 for row in fetch_log if row[3].startswith("❌"))
    skip_count = sum(1 for row in fetch_log if row[3].startswith("⏭️"))

    if fetch_log and st is not None:
        try:
            with st.expander(f"🔍 Fetch details ({ok_count} OK, {fail_count} failed, {skip_count} skipped)",
                              expanded=(fail_count > 0 and ok_count == 0)):
                log_df = pd.DataFrame(fetch_log, columns=["source", "scheme_name", "detail_url", "status", "error"])
                st.dataframe(log_df, use_container_width=True, height=250)
        except Exception:
            pass

    if fail_count > 0 and ok_count == 0:
        _st_safe(
            "error",
            "Saare detail-page fetch fail hue. Common causes: (1) site bot-traffic block kar rahi hai "
            "(403/timeout — upar 'error' column check karo), (2) site JS-rendered hai aur "
            "'use_selenium: True' set nahi hai us source ke liye, (3) internet/firewall issue, "
            "(4) Selenium/Chrome installed nahi hai, (5) state-portal ka URL/markup badal gaya ho "
            "(state sites often redesign hote rehte hain — Source Health section check karo)."
        )

    _st_safe(
        "success",
        f"Done. {len(staged_new)} NAYE candidate schemes '{STAGING_CSV_FILE}' mein add hue "
        f"(review ke liye) — main dataset touch nahi hua."
    )
    return staged_new


# ===========================
# SCHEDULED / AUTO SCRAPING
# ===========================
def load_schedule_state():
    """Auto-scraping ka state load karta hai: enabled?, last run kab hua,
    kitni baar chala. Corrupt file -> quarantine + defaults."""
    default = {"enabled": False, "last_scrape": None, "scrape_count": 0, "interval_hours": 24}
    if not os.path.exists(SCHEDULE_STATE_FILE):
        return default
    try:
        with open(SCHEDULE_STATE_FILE, "r") as f:
            state = json.load(f)
        if not isinstance(state, dict):
            raise ValueError("schedule state is not a dict")
        for k, v in default.items():
            state.setdefault(k, v)
        return state
    except Exception:
        _quarantine_corrupt_file(SCHEDULE_STATE_FILE)
        return default


def save_schedule_state(state):
    """BUG #7 FIX: atomic write (temp file + os.replace) instead of a direct
    json.dump straight into the live file — prevents corruption if
    auto-scrape and a manual admin run happen to write at the same time."""
    return _atomic_json_write(SCHEDULE_STATE_FILE, state)


def set_auto_scraping_enabled(enabled, interval_hours=24):
    """UI ke checkbox se call hota hai — auto-scraping on/off karta hai."""
    state = load_schedule_state()
    state["enabled"] = enabled
    state["interval_hours"] = interval_hours
    save_schedule_state(state)
    return state


def get_scrape_stats():
    """Dashboard ke liye stats: total schemes (main csv), last scrape time,
    scrape count. BUG #4 FIX: uses _load_scheme_csv_safe so a corrupt
    schemes.csv can't crash the dashboard."""
    main_df = _load_scheme_csv_safe(MAIN_CSV_FILE)
    total_schemes = 0 if main_df.empty else len(main_df)

    state = load_schedule_state()
    last_scrape_raw = state.get("last_scrape")

    if last_scrape_raw:
        try:
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

    BUG #3 FIX: run_web_scraper() call ab try/except mein wrapped hai — agar
    auto-scrape fail ho (network down, site redesign, Chrome missing,
    koi bhi unexpected exception), to error log ho jaata hai lekin
    Streamlit app CRASH nahi hoti. schedule state 'last_scrape' / count ab
    bhi update hoti hai taaki ek baar-baar fail ho raha source scraper ko
    loop mein har rerun par turant dobara try karte rehne se na roke.
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

    # BUG #3 FIX: never let a scraping failure propagate and crash the app.
    try:
        run_web_scraper(sources=sources, max_detail_pages_per_source=max_detail_pages_per_source)
    except Exception as e:
        _st_safe("error", f"⚠️ Scheduled auto-scrape failed (app continues normally): {e}")
        try:
            traceback.print_exc()
        except Exception:
            pass
        state["last_error"] = f"{type(e).__name__}: {e}"

    state["last_scrape"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["scrape_count"] = state.get("scrape_count", 0) + 1
    save_schedule_state(state)
    return state


# ===========================
# STREAMLIT UI
# ===========================
def render_web_scraper_ui():
    """Admin panel for running/scheduling the scraper and reviewing staged
    candidates before they go into schemes.csv. No-ops safely if Streamlit
    isn't available (style requirement #6)."""
    if st is None:
        print("render_web_scraper_ui() requires a Streamlit runtime.")
        return

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

    if not _SELENIUM_AVAILABLE:
        st.info(
            "ℹ️ Selenium / webdriver-manager not installed (or Chrome missing) in this environment — "
            "Selenium-based sources will be skipped automatically during scraping."
        )

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
            try:
                with open(STAGING_CSV_FILE, "rb") as f:
                    st.download_button(
                        "Download Staging File", data=f, file_name="scraped_candidates.csv",
                        mime="text/csv", use_container_width=True,
                    )
            except OSError:
                st.caption("Staging file exists but couldn't be opened for download.")

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

    if schedule_state.get("last_error"):
        st.caption(f"⚠️ Last scheduled-scrape error: {schedule_state['last_error']}")

    # ===========================
    # SOURCE HEALTH (BUG #5 FIX — surfaced in UI)
    # ===========================
    st.markdown("#### 🩺 Source Health")
    health = load_source_health()
    if not health:
        st.caption("No health data yet — run the scraper at least once.")
    else:
        health_rows = []
        for url, info in health.items():
            health_rows.append({
                "Source": url,
                "Last Run": info.get("last_run", ""),
                "Links Found": info.get("links_found", 0),
                "Links Fetched": info.get("links_fetched", 0),
                "Errors": info.get("errors", 0),
                "Health": info.get("health", "ok"),
            })
        health_df = pd.DataFrame(health_rows)

        def _highlight_health(row):
            color = {"ok": "#d4edda", "warning": "#fff3cd", "broken": "#f8d7da"}.get(row["Health"], "")
            return [f"background-color: {color}"] * len(row)

        try:
            st.dataframe(health_df.style.apply(_highlight_health, axis=1), use_container_width=True, height=220)
        except Exception:
            st.dataframe(health_df, use_container_width=True, height=220)

    # ===========================
    # REVIEW STAGING + ADD TO schemes.csv (sirf yahan se main dataset update hota hai)
    # ===========================
    st.markdown("#### 📋 Review Scraped Candidates")

    staging_df = _load_scheme_csv_safe(STAGING_CSV_FILE)

    if staging_df.empty:
        st.info("No new candidate schemes are in staging right now. Please run the scraper first.")
    else:
        st.caption(f"{len(staging_df)} candidate schemes review ke liye taiyaar hain.")

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
                    st.warning("Kuch add nahi hua — ho sakta hai ye schemes already schemes.csv mein hon (duplicate), ya save fail ho gaya ho.")

        with add_col2:
            if st.button("🗑️ Clear Staging (bina add kiye)", use_container_width=True, key="clear_staging_btn"):
                confirm_key = "confirm_clear_staging"
                if st.session_state.get(confirm_key):
                    _atomic_csv_write(pd.DataFrame(columns=SCHEME_COLUMNS), STAGING_CSV_FILE)
                    st.session_state[confirm_key] = False
                    st.toast("🗑️ Staging file clear ho gayi")
                    st.rerun()
                else:
                    st.session_state[confirm_key] = True
                    st.warning("Are you sure? Click '🗑️ Clear Staging' again to confirm — this cannot be undone.")

        fetch_log_key = "_last_fetch_log_df"
        if fetch_log_key in st.session_state:
            with st.expander("🔍 Last fetch log", expanded=False):
                st.dataframe(st.session_state[fetch_log_key], use_container_width=True, height=250)


# ===========================
# SELF-TEST (offline, no network, no Selenium) — BUG #10 FIX
# ===========================
def _run_self_tests():
    """Runs a small offline test suite covering the pure-logic helpers and
    the atomic-write / merge machinery, printing ✅ / ❌ per test. No network
    calls and no Selenium are used."""
    import shutil

    results = []

    def check(label, condition):
        results.append((label, bool(condition)))
        print(("✅ " if condition else "❌ ") + label)

    # 1. _safe_str
    check("_safe_str(None) == ''", _safe_str(None) == "")
    check("_safe_str(float('nan')) == ''", _safe_str(float("nan")) == "")
    check("_safe_str('') == ''", _safe_str("") == "")
    check("_safe_str('test') == 'test'", _safe_str("test") == "test")

    # 2. normalize_name
    check('normalize_name("PM Kisan") == "pm kisan"', normalize_name("PM Kisan") == "pm kisan")
    check(
        'normalize_name("Ladli  Behna, Yojana!") == normalize_name("Ladli Behna Yojana")',
        normalize_name("Ladli  Behna, Yojana!") == normalize_name("Ladli Behna Yojana"),
    )

    # 3 & 4. is_valid_scheme_name
    check('is_valid_scheme_name("Apply Now!") == False', is_valid_scheme_name("Apply Now!") is False)
    check(
        'is_valid_scheme_name("PM Kisan Samman Nidhi") == True',
        is_valid_scheme_name("PM Kisan Samman Nidhi") is True,
    )

    # 5. extract_age
    check(
        'extract_age("Age: 18 to 40 years") == (18, 40)',
        extract_age("Age: 18 to 40 years") == (18, 40),
    )

    # 6. extract_income
    check(
        'extract_income("Annual income Rs 2,00,000") == 200000',
        extract_income("Annual income Rs 2,00,000") == 200000,
    )

    # 7. extract_category_type
    check(
        'extract_category_type("PM Kisan Yojana", "") == "Agriculture"',
        extract_category_type("PM Kisan Yojana", "") == "Agriculture",
    )
    check(
        'extract_category_type("Beti Bachao Beti Padhao", "") == "Women & Child"',
        extract_category_type("Beti Bachao Beti Padhao", "") == "Women & Child",
    )

    # Set up an isolated temp "data" dir so tests never touch real project data.
    tmp_dir = tempfile.mkdtemp(prefix="scraper_selftest_")
    orig_globals = {
        "MAIN_CSV_FILE": globals()["MAIN_CSV_FILE"],
        "STAGING_CSV_FILE": globals()["STAGING_CSV_FILE"],
        "VISITED_LOG_FILE": globals()["VISITED_LOG_FILE"],
        "SCHEDULE_STATE_FILE": globals()["SCHEDULE_STATE_FILE"],
        "SOURCE_HEALTH_FILE": globals()["SOURCE_HEALTH_FILE"],
    }
    try:
        globals()["MAIN_CSV_FILE"] = os.path.join(tmp_dir, "schemes.csv")
        globals()["STAGING_CSV_FILE"] = os.path.join(tmp_dir, "scraped_candidates.csv")
        globals()["VISITED_LOG_FILE"] = os.path.join(tmp_dir, "scraped_visited_urls.csv")
        globals()["SCHEDULE_STATE_FILE"] = os.path.join(tmp_dir, "scraper_schedule.json")
        globals()["SOURCE_HEALTH_FILE"] = os.path.join(tmp_dir, "source_health.json")

        # 8. Atomic CSV write to temp dir
        test_df = pd.DataFrame([{c: "" for c in SCHEME_COLUMNS}])
        test_df.loc[0, "scheme_name"] = "Test Scheme Yojana"
        write_ok = _atomic_csv_write(test_df, globals()["MAIN_CSV_FILE"])
        readback = pd.read_csv(globals()["MAIN_CSV_FILE"]) if write_ok else pd.DataFrame()
        check(
            "Atomic CSV write to temp dir",
            write_ok and not readback.empty and readback.loc[0, "scheme_name"] == "Test Scheme Yojana",
        )

        # 9. merge_staging_to_main() in temp dir with sample data
        _safe_remove(globals()["MAIN_CSV_FILE"])
        sample_staging = pd.DataFrame([
            {**{c: "" for c in SCHEME_COLUMNS}, "scheme_name": "PM Kisan Samman Nidhi Yojana",
             "category_type": "Agriculture", "applicable_state": "All"},
            {**{c: "" for c in SCHEME_COLUMNS}, "scheme_name": "Ladli Behna Yojana",
             "category_type": "Women & Child", "applicable_state": "Madhya Pradesh"},
        ])
        _atomic_csv_write(sample_staging, globals()["STAGING_CSV_FILE"])
        added_count, added_df = merge_staging_to_main()
        main_after = _load_scheme_csv_safe(globals()["MAIN_CSV_FILE"])
        staging_after = _load_scheme_csv_safe(globals()["STAGING_CSV_FILE"])
        check(
            "merge_staging_to_main() adds all rows and empties staging",
            added_count == 2 and len(main_after) == 2 and staging_after.empty,
        )

        # Re-running merge with same staging content should add nothing new (dedup safety, BUG #8).
        _atomic_csv_write(sample_staging, globals()["STAGING_CSV_FILE"])
        added_count_2, _ = merge_staging_to_main()
        check(
            "merge_staging_to_main() dedups against main on re-run (no double-add)",
            added_count_2 == 0,
        )

        # 10. Schedule state save/load roundtrip
        state = {"enabled": True, "last_scrape": "2026-09-01 10:00:00", "scrape_count": 3, "interval_hours": 24}
        save_schedule_state(state)
        loaded_state = load_schedule_state()
        check(
            "Schedule state save/load roundtrip",
            loaded_state.get("enabled") is True and loaded_state.get("scrape_count") == 3,
        )

        # Bonus: _validate_scheme_csv + corrupt-file quarantine behaviour.
        bad_path = os.path.join(tmp_dir, "bad.json")
        with open(bad_path, "w") as f:
            f.write("{not valid json")
        _quarantine_corrupt_file(bad_path)
        check(
            "_quarantine_corrupt_file() renames corrupt file instead of deleting/crashing",
            (not os.path.exists(bad_path)) and os.path.exists(bad_path + ".corrupt"),
        )

    finally:
        globals().update(orig_globals)
        shutil.rmtree(tmp_dir, ignore_errors=True)

    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"\n{passed}/{total} self-tests passed.")
    return passed == total


if __name__ == "__main__":
    import sys
    if st is None or "streamlit" not in sys.modules:
        print("Tip: 'streamlit run app.py' se chalao poore UI ke saath.\n")
    print("Running offline self-tests (no network, no Selenium)...\n")
    _run_self_tests()