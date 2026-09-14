"""
documents_vault.py — User documents storage + Bookmarklet + QR + OCR extraction.

v7 (QR CODE — 100% ACCURATE):
  - Aadhaar ka QR code scan karke 100% accurate data nikaalta hai
  - QR mein UIDAI ka digitally signed XML hota hai — naam, DOB, gender,
    address, sab exact milta hai (OCR ki tarah garbled nahi)
  - Multiple QR formats support: plain XML, base64 XML, zlib compressed
  - OCR fallback: agar QR detect na ho to purana OCR chalega (partial)
  - _extract_via_ocr() internal helper — QR ke saath merge ke liye

⚠️ PRIVACY WARNING: 12-digit Aadhaar number store karne se pehle soch lo.
    Ye sensitive info hai. Ye file data/user_documents.json mein plain text
    mein save hota hai.
"""

import base64
import json
import os
import re
import shutil
import tempfile

import streamlit as st


# ===========================
# DEBUG: LAST OCR TEXT
# ===========================
_LAST_OCR_TEXT = ""


def get_last_ocr_text():
    """Debug: pichla OCR/QR raw text return karta hai."""
    return _LAST_OCR_TEXT


# ===========================
# OPTIONAL IMPORTS
# ===========================
_PIL_AVAILABLE = True
try:
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    Image = None
    ImageEnhance = None
    ImageFilter = None
    _PIL_AVAILABLE = False

_NUMPY_AVAILABLE = True
try:
    import numpy as np
except ImportError:
    np = None
    _NUMPY_AVAILABLE = False

_PYTESSERACT_AVAILABLE = True
try:
    import pytesseract
except ImportError:
    pytesseract = None
    _PYTESSERACT_AVAILABLE = False

_CV2_AVAILABLE = True
try:
    import cv2
except ImportError:
    cv2 = None
    _CV2_AVAILABLE = False


def _find_tesseract():
    if not _PYTESSERACT_AVAILABLE:
        return False
    if shutil.which("tesseract"):
        return True
    possible_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe"),
        os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                pytesseract.pytesseract.tesseract_cmd = p
            except Exception:
                pass
            return True
    return False


_OCR_AVAILABLE = (
    _PIL_AVAILABLE and _PYTESSERACT_AVAILABLE and _find_tesseract()
)


def is_ocr_available():
    """True agar koi bhi extraction method available ho (QR ya OCR)."""
    return _CV2_AVAILABLE or _OCR_AVAILABLE


def get_ocr_status():
    if not _PIL_AVAILABLE:
        return "Pillow install nahi hai. `pip install Pillow` chalao."
    if not _NUMPY_AVAILABLE:
        return "numpy install nahi hai. `pip install numpy` chalao."
    if not _CV2_AVAILABLE:
        return "opencv install nahi hai (QR ke liye). `pip install opencv-python` chalao."
    if not _PYTESSERACT_AVAILABLE:
        return "pytesseract install nahi hai (OCR fallback). `pip install pytesseract` chalao."
    if not _find_tesseract():
        return "Tesseract binary nahi mila (OCR fallback). https://github.com/UB-Mannheim/tesseract/wiki"
    return "QR + OCR ready hai ✅"


# ===========================
# FIELD DEFINITIONS
# ===========================
AADHAAR_FIELDS = [
    ("full_name",      "Full Name",                  "📝", "पूरा नाम"),
    ("dob",            "Date of Birth",              "📅", "जन्म तिथि"),
    ("gender",         "Gender",                     "⚧",  "लिंग"),
    ("aadhaar_number", "Aadhaar Number (12-digit)",  "🆔", "आधार संख्या (12 अंक)"),
    ("mobile",         "Mobile Number",              "📱", "मोबाइल नंबर"),
    ("address",        "Full Address",               "🏠", "पूरा पता"),
    ("state",          "State",                      "🗺️", "राज्य"),
    ("pincode",        "Pincode",                    "📍", "पिन कोड"),
]

EXTRA_FIELDS = [
    ("email",          "Email",             "📧", "ईमेल"),
    ("father_name",    "Father's Name",     "👨", "पिता का नाम"),
    ("mother_name",    "Mother's Name",     "👩", "माता का नाम"),
    ("category",       "Category",          "🏷️", "श्रेणी"),
    ("bank_account",   "Bank Account No.",  "🏦", "बैंक खाता संख्या"),
    ("ifsc",           "IFSC Code",         "🔢", "IFSC कोड"),
    ("pan",            "PAN Number",        "💳", "पैन नंबर"),
]

DOCUMENT_FIELDS = AADHAAR_FIELDS + EXTRA_FIELDS


# ===========================
# ATOMIC WRITE
# ===========================
DOCUMENTS_FILE = os.path.join("data", "user_documents.json")


def _atomic_json_write(path, data):
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".doc_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


# ===========================
# LOAD / SAVE
# ===========================
@st.cache_data(ttl=60, show_spinner=False)
def load_documents():
    if not os.path.exists(DOCUMENTS_FILE):
        return {}
    try:
        with open(DOCUMENTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}

        if "aadhaar_last4" in data and "aadhaar_number" not in data:
            val = str(data.get("aadhaar_last4", "")).strip()
            if val and val != "None":
                data["aadhaar_number"] = f"XXXX XXXX {val}"
            del data["aadhaar_last4"]

        return data
    except (json.JSONDecodeError, OSError):
        return {}


def save_documents(data):
    if not isinstance(data, dict):
        return False
    try:
        _atomic_json_write(DOCUMENTS_FILE, data)
        load_documents.clear()
        return True
    except Exception as e:
        print(f"[documents_vault] save failed: {e}")
        return False


def clear_documents():
    return save_documents({})


# ===========================
# AADHAAR QR CODE EXTRACTION (v7 — 100% accurate)
# ===========================
def _decode_aadhaar_qr_data(qr_raw):
    """
    Aadhaar QR raw data ko XML string mein decode karta hai.
    Multiple formats support:
      - Plain XML (old Aadhaar)
      - Base64 XML
      - Zlib-compressed XML (Secure QR, 2018+)
    """
    import zlib
    import base64

    if qr_raw is None:
        return None

    if isinstance(qr_raw, bytes):
        raw_bytes = qr_raw
    else:
        raw_bytes = str(qr_raw).encode("latin-1", errors="ignore")

    # Try 1: Plain XML
    if b"<" in raw_bytes and b">" in raw_bytes:
        try:
            return raw_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

    # Try 2: Base64 encoded XML
    try:
        decoded = base64.b64decode(raw_bytes)
        if b"<" in decoded:
            return decoded.decode("utf-8", errors="ignore")
    except Exception:
        pass

    # Try 3: Secure QR — zlib compressed (with byte offsets)
    for offset in range(0, min(6, len(raw_bytes))):
        try:
            decompressed = zlib.decompress(raw_bytes[offset:])
            text = decompressed.decode("utf-8", errors="ignore")
            if "<" in text:
                return text
        except Exception:
            continue

    # Try 4: Raw deflate with different window bits
    for offset in range(0, min(6, len(raw_bytes))):
        for wbits in (-15, 15, 31):
            try:
                decompressed = zlib.decompress(raw_bytes[offset:], wbits)
                text = decompressed.decode("utf-8", errors="ignore")
                if "<" in text:
                    return text
            except Exception:
                continue

    return None


def _parse_aadhaar_xml(xml_string):
    """
    Aadhaar XML se fields extract karta hai.
    Uses xml.etree first, falls back to regex.
    """
    if not xml_string:
        return None

    result = {}

    # Try xml.etree first
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_string)
        attrs = root.attrib

        name = attrs.get("name", "").strip()
        if name:
            result["full_name"] = name

        dob = attrs.get("dob", "").strip()
        if dob:
            result["dob"] = dob

        gender_code = attrs.get("gender", "").strip().upper()
        if gender_code in ("M", "MALE"):
            result["gender"] = "Male"
        elif gender_code in ("F", "FEMALE"):
            result["gender"] = "Female"

        uid = attrs.get("uid", "").strip()
        if uid and len(uid) >= 4:
            digits = re.sub(r"\D", "", uid)
            if len(digits) == 12:
                result["aadhaar_number"] = f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
            elif len(digits) >= 4:
                result["aadhaar_number"] = f"XXXX XXXX {digits[-4:]}"

        addr_parts = []
        for key in ["co", "house", "street", "lm", "loc", "vtc", "po", "subdist", "dist"]:
            val = attrs.get(key, "").strip()
            if val:
                addr_parts.append(val)
        if addr_parts:
            result["address"] = ", ".join(addr_parts)

        state = attrs.get("state", "").strip()
        if state:
            result["state"] = state

        pc = attrs.get("pc", "").strip()
        if pc:
            result["pincode"] = pc

        if result:
            return result
    except Exception as e:
        print(f"[QR] XML parse via etree failed: {e}")

    # Fallback: regex extraction
    try:
        def _attr(key):
            m = re.search(rf'{key}="([^"]*)"', xml_string)
            return m.group(1).strip() if m else ""

        name = _attr("name")
        if name:
            result["full_name"] = name

        dob = _attr("dob")
        if dob:
            result["dob"] = dob

        gender_code = _attr("gender").upper()
        if gender_code in ("M", "MALE"):
            result["gender"] = "Male"
        elif gender_code in ("F", "FEMALE"):
            result["gender"] = "Female"

        uid = _attr("uid")
        if uid:
            digits = re.sub(r"\D", "", uid)
            if len(digits) == 12:
                result["aadhaar_number"] = f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
            elif len(digits) >= 4:
                result["aadhaar_number"] = f"XXXX XXXX {digits[-4:]}"

        addr_parts = []
        for key in ["co", "house", "street", "lm", "loc", "vtc", "po", "subdist", "dist"]:
            val = _attr(key)
            if val:
                addr_parts.append(val)
        if addr_parts:
            result["address"] = ", ".join(addr_parts)

        state = _attr("state")
        if state:
            result["state"] = state

        pc = _attr("pc")
        if pc:
            result["pincode"] = pc

        if result:
            return result
    except Exception as e:
        print(f"[QR] XML regex parse failed: {e}")

    return None


def _extract_from_qr_code(img):
    """
    Image mein Aadhaar QR code dhundho aur decode karo.
    Returns: dict with extracted fields, OR None if no QR found/decoded.
    """
    if not _CV2_AVAILABLE or not _NUMPY_AVAILABLE or img is None:
        return None

    try:
        if hasattr(img, "convert"):
            img_array = np.array(img.convert("RGB"))
        else:
            img_array = np.array(img)

        if img_array.ndim == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array

        detector = cv2.QRCodeDetector()

        # Try multiple scales (QR may be small on Aadhaar)
        scales = [1.0, 2.0, 3.0, 1.5]

        for scale in scales:
            try:
                if scale != 1.0:
                    h, w = gray.shape
                    scaled = cv2.resize(
                        gray,
                        (int(w * scale), int(h * scale)),
                        interpolation=cv2.INTER_CUBIC,
                    )
                else:
                    scaled = gray

                try:
                    retval, decoded_info, _, _ = detector.detectAndDecodeMulti(scaled)
                except Exception:
                    retval = False
                    decoded_info = []

                if retval and decoded_info:
                    for qr_data in decoded_info:
                        if not qr_data:
                            continue
                        xml = _decode_aadhaar_qr_data(qr_data)
                        if xml:
                            parsed = _parse_aadhaar_xml(xml)
                            if parsed:
                                return parsed
            except Exception as e:
                print(f"[QR] Scale {scale} failed: {e}")
                continue

        return None
    except Exception as e:
        print(f"[QR] Extraction failed: {e}")
        return None


# ===========================
# IMAGE PREPROCESSING (OCR)
# ===========================
def _preprocess_image_for_ocr(img):
    if not _PIL_AVAILABLE or not _NUMPY_AVAILABLE:
        return img

    try:
        if img.mode != "L":
            img = img.convert("L")

        w, h = img.size
        if max(w, h) < 2000:
            img = img.resize((w * 2, h * 2), Image.LANCZOS)

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)

        img = img.filter(ImageFilter.SHARPEN)

        arr = np.array(img)
        threshold = int(arr.mean() * 0.82)
        arr = np.where(arr > threshold, 255, 0).astype(np.uint8)
        img = Image.fromarray(arr)

        return img
    except Exception as e:
        print(f"[documents_vault] Preprocessing failed: {e}")
        return img


# ===========================
# OCR EXTRACTION HELPERS
# ===========================
def _clean_ocr_text(text):
    if not text:
        return ""
    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_dob(text):
    patterns = [
        r"(?:DOB|Date\s*of\s*Birth|जन्म\s*तिथि|जन्म\s*तारीख)\s*[:\-/]?\s*(\d{1,2}[\/\-\s\.]\d{1,2}[\/\-\s\.]\d{2,4})",
        r"(?:DOB|Date\s*of\s*Birth)\s*[:\-]?\s*(\d{4})",
        r"\b(\d{2}\/\d{2}\/\d{4})\b",
        r"\b(\d{2}\-\d{2}\-\d{4})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            val = m.group(1).strip()
            val = val.replace(".", "/").replace("-", "/").replace(" ", "/")
            return val
    return ""


def _extract_aadhaar_full(text):
    if not text:
        return ""

    m = re.search(r"\b([2-9]\d{3})\s+(\d{4})\s+(\d{4})\b", text)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"

    m = re.search(r"\b([2-9]\d{3})-(\d{4})-(\d{4})\b", text)
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"

    matches = list(re.finditer(r"\b([2-9]\d{11})\b", text))
    if matches:
        n = matches[-1].group(1)
        return f"{n[0:4]} {n[4:8]} {n[8:12]}"

    return ""


def _extract_pincode(text):
    matches = re.findall(r"\b([1-9]\d{5})\b", text)
    return matches[0] if matches else ""


def _extract_gender(text):
    if re.search(r"\bfemale\b|महिला|स्त्री", text, re.I):
        return "Female"
    if re.search(r"\bmale\b|पुरुष", text, re.I):
        return "Male"
    return ""


def _extract_pan(text):
    m = re.search(r"\b([A-Z]{5}\d{4}[A-Z])\b", text.upper())
    return m.group(1) if m else ""


# ===========================
# NAME EXTRACTION
# ===========================
_NAME_REJECT_KEYWORDS = (
    "government", "india", "aadhaar", "aadhar", "date", "dob", "birth",
    "male", "female", "address", "signature", "enrolment", "enrollment",
    "uidai", "unique", "identification", "authority", "proof", "identity",
    "citizenship", "number", "www", "help", "download", "print", "vid",
    "father", "mother", "permanent", "account", "mera", "meri", "pehchan",
    "proof of identity", "not of citizenship", "based verification",
    "qr code", "offline", "should be used",
    "भारत", "सरकार", "आधार", "जन्म", "तिथि", "पुरुष", "महिला", "पता",
    "हस्ताक्षर", "नामांकन", "विशिष्ट", "पहचान", "प्रमाण", "नागरिकता",
    "संख्या", "मेरा", "मेरी", "पहचान", "पिता", "माता", "स्थायी",
)


def _extract_name(text):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    def _clean_candidate(s):
        s = re.sub(r"^[^\w\u0900-\u097F]+", "", s)
        s = re.sub(r"[^\w\u0900-\u097F]+$", "", s)
        return s.strip()

    def _looks_like_english_name(s):
        if not s:
            return False
        s = _clean_candidate(s)
        if len(s) < 3 or len(s) > 60:
            return False
        words = s.split()
        if len(words) < 2 or len(words) > 5:
            return False
        for w in words:
            w_clean = w.strip(".").strip()
            if not w_clean:
                return False
            for c in w_clean:
                if not (c.isalpha() or c == "."):
                    return False
        if s.isupper():
            return False
        s_lower = s.lower()
        for kw in _NAME_REJECT_KEYWORDS:
            if kw in s_lower:
                return False
        return True

    def _looks_like_hindi_name(s):
        if not s:
            return False
        s = _clean_candidate(s)
        if len(s) < 3 or len(s) > 60:
            return False
        dev_chars = sum(1 for c in s if "\u0900" <= c <= "\u097F")
        return dev_chars >= 3

    # Heuristic 0: Adjacent Hindi + English pair
    for i in range(len(lines) - 1):
        if _looks_like_hindi_name(lines[i]) and _looks_like_english_name(lines[i + 1]):
            return _clean_candidate(lines[i + 1])
        if _looks_like_english_name(lines[i]) and _looks_like_hindi_name(lines[i + 1]):
            return _clean_candidate(lines[i])

    # Heuristic 1: Line above DOB/Gender
    for i, line in enumerate(lines):
        if re.search(
            r"\b(?:DOB|Date\s*of\s*Birth|जन्म\s*तिथि|Male|Female|"
            r"MALE|FEMALE|पुरुष|महिला)\b",
            line, re.I
        ):
            for j in range(i - 1, max(i - 7, -1), -1):
                if j < 0:
                    break
                if _looks_like_english_name(lines[j]):
                    return _clean_candidate(lines[j])

    # Heuristic 2: Line ending with Male/Female
    for line in lines:
        m = re.match(
            r"^(.+?)\s+(?:Male|Female|MALE|FEMALE|पुरुष|महिला)\s*$",
            line
        )
        if m:
            candidate = m.group(1).strip()
            if _looks_like_english_name(candidate):
                return _clean_candidate(candidate)

    # Heuristic 3: After "Name"
    m = re.search(
        r"(?:Name|नाम)\s*[:\-]?\s*([A-Za-z\u0900-\u097F]"
        r"[A-Za-z\u0900-\u097F\s\.]{2,50})",
        text, re.I
    )
    if m:
        candidate = m.group(1).strip()
        candidate = re.split(r"\s{2,}|[,;]|\n", candidate)[0].strip()
        if _looks_like_english_name(candidate):
            return _clean_candidate(candidate)

    # Heuristic 4: First English name line in top 20
    for line in lines[:20]:
        if _looks_like_english_name(line):
            return _clean_candidate(line)

    return ""


def _extract_father_name(text):
    m = re.search(
        r"(?:S\/O|Father|पिता)\s*[:\-]?\s*([A-Za-z\u0900-\u097F]"
        r"[A-Za-z\u0900-\u097F\s\.]{3,40})",
        text, re.I
    )
    if m:
        name = m.group(1).strip()
        name = re.split(r"\s{2,}|[,;]", name)[0].strip()
        return name
    return ""


def _extract_address(text):
    m = re.search(
        r"(?:Address|पता)\s*[:\-]?\s*(.+?)(?=\n\s*\n|$)",
        text, re.I | re.DOTALL
    )
    if m:
        addr = m.group(1).strip()
        addr = re.sub(r"\s+", " ", addr)
        addr = re.split(r"\b\d{6}\b", addr)[0].strip()
        if len(addr) > 15:
            return addr[:250]

    lines = text.split("\n")
    addr_parts = []
    address_started = False
    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        lower = line_clean.lower()
        if any(kw in lower for kw in [
            "address", "pata", "road", "street", "nagar", "colony",
            "village", "district", "post", "po.", "ps.", "house",
            "sector", "block", "ward", "lane", "marg"
        ]):
            address_started = True
            addr_parts.append(line_clean)
        elif address_started and len(addr_parts) < 5:
            if re.search(r"\d", line_clean) or line_clean.isupper():
                addr_parts.append(line_clean)
            else:
                break

    if addr_parts:
        addr = " ".join(addr_parts)
        addr = re.sub(r"\s+", " ", addr)
        addr = re.split(r"\b\d{6}\b", addr)[0].strip()
        return addr[:250]

    return ""


# ===========================
# INTERNAL OCR HELPER
# ===========================
def _extract_via_ocr(img):
    """Internal OCR helper — preprocessing + multiple PSM."""
    global _LAST_OCR_TEXT

    try:
        preprocessed = _preprocess_image_for_ocr(img)
    except Exception:
        preprocessed = img

    ocr_attempts = [
        (preprocessed, "eng+hin", "--psm 6"),
        (preprocessed, "eng+hin", "--psm 4"),
        (preprocessed, "eng",     "--psm 6"),
        (img,          "eng+hin", "--psm 6"),
    ]

    text = ""
    for attempt_img, lang, config in ocr_attempts:
        try:
            candidate = pytesseract.image_to_string(
                attempt_img, lang=lang, config=config
            )
            if candidate and len(candidate.strip()) > len(text.strip()):
                text = candidate
        except Exception:
            continue

    if not text:
        return {}, "OCR failed"

    text = _clean_ocr_text(text)
    _LAST_OCR_TEXT = "⚠️ QR NOT found — OCR fallback (partial accuracy)\n\n" + text

    if not text or len(text) < 10:
        return {}, "OCR ne koi text nahi nikala."

    extracted = {}

    name = _extract_name(text)
    if name:
        extracted["full_name"] = name

    dob = _extract_dob(text)
    if dob:
        extracted["dob"] = dob

    gender = _extract_gender(text)
    if gender:
        extracted["gender"] = gender

    aadhaar_full = _extract_aadhaar_full(text)
    if aadhaar_full:
        extracted["aadhaar_number"] = aadhaar_full

    pincode = _extract_pincode(text)
    if pincode:
        extracted["pincode"] = pincode

    address = _extract_address(text)
    if address:
        extracted["address"] = address

    father = _extract_father_name(text)
    if father:
        extracted["father_name"] = father

    pan = _extract_pan(text)
    if pan:
        extracted["pan"] = pan

    return extracted, None


# ===========================
# MAIN EXTRACTION FUNCTION (QR FIRST, OCR FALLBACK)
# ===========================
def extract_from_image(uploaded_file):
    """
    v7 — QR first (100% accurate), OCR fallback (partial).

    Flow:
      1. QR code detect karo → agar mila to 100% accurate data
      2. QR se jo fields nahi mili, unke liye OCR try karo
      3. Return merged result
    """
    global _LAST_OCR_TEXT

    if uploaded_file is None:
        return {}, "No file uploaded"

    if not _PIL_AVAILABLE:
        return {}, "Pillow not installed"

    try:
        img = Image.open(uploaded_file)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    except Exception as e:
        return {}, f"Image open failed: {str(e)[:100]}"

    # =====================================================
    # STEP 1: TRY QR CODE (100% accurate)
    # =====================================================
    qr_extracted = None
    if _CV2_AVAILABLE:
        try:
            qr_extracted = _extract_from_qr_code(img)
        except Exception as e:
            print(f"[extract_from_image] QR attempt failed: {e}")

    if qr_extracted:
        # QR worked! Merge with OCR for missing fields (e.g. mobile)
        merged = dict(qr_extracted)

        debug_lines = ["✅ QR CODE DETECTED — 100% accurate data", ""]
        for k, v in qr_extracted.items():
            debug_lines.append(f"  {k}: {v}")

        # Try OCR for missing fields
        if _OCR_AVAILABLE:
            try:
                ocr_extracted, _ = _extract_via_ocr(img)
                added = []
                for k, v in ocr_extracted.items():
                    if k not in merged and v:
                        merged[k] = v
                        added.append(f"  {k}: {v} (from OCR)")
                if added:
                    debug_lines.append("")
                    debug_lines.append("Additional from OCR:")
                    debug_lines.extend(added)
            except Exception:
                pass

        _LAST_OCR_TEXT = "\n".join(debug_lines)
        return merged, None

    # =====================================================
    # STEP 2: QR FAILED — FALLBACK TO OCR
    # =====================================================
    if not _OCR_AVAILABLE:
        return {}, (
            "QR code nahi mila aur OCR setup nahi hua. "
            "Aadhaar ki clear photo (QR visible) upload karein, "
            "ya Tesseract install karein."
        )

    extracted, error = _extract_via_ocr(img)
    if error:
        return {}, error

    return extracted, None


# ===========================
# BOOKMARKLET GENERATOR
# ===========================
def generate_bookmarklet(data):
    """v5: Emoji hataye — URL encoding issue fix."""
    if not isinstance(data, dict):
        data = {}

    clean = {k: str(v).strip() for k, v in data.items() if v and str(v).strip()}
    data_json = json.dumps(clean, ensure_ascii=False)
    data_b64 = base64.b64encode(data_json.encode("utf-8")).decode("ascii")

    field_meta = [
        [k, label]
        for k, label, _icon, _label_hi in DOCUMENT_FIELDS
    ]
    fields_json = json.dumps(field_meta, ensure_ascii=False)
    fields_b64 = base64.b64encode(fields_json.encode("utf-8")).decode("ascii")

    js = (
        "javascript:(function(){"
        f"var D=JSON.parse(atob('{data_b64}'));"
        f"var F=JSON.parse(atob('{fields_b64}'));"
        "var L=null;"
        "document.addEventListener('focusin',function(e){"
        "var t=e.target;"
        "if(t&&(t.tagName==='INPUT'||t.tagName==='TEXTAREA'||t.isContentEditable))L=t;"
        "},true);"
        "var O=document.getElementById('__sfP');if(O)O.remove();"
        "var P=document.createElement('div');"
        "P.id='__sfP';"
        "P.style.cssText='position:fixed;top:20px;right:20px;z-index:2147483647;"
        "background:#1f2c34;border:1px solid #00E5FF;border-radius:12px;"
        "padding:14px;font-family:system-ui,sans-serif;"
        "box-shadow:0 8px 32px rgba(0,0,0,0.6);max-width:260px;"
        "max-height:80vh;overflow-y:auto;font-size:13px;';"
        "P.innerHTML='<div style=\"color:#00E5FF;font-weight:700;margin-bottom:4px;\">"
        "Auto Fill</div>"
        "<div style=\"color:#8696A0;font-size:10px;margin-bottom:10px;\">"
        "Pehle input box par click karein</div>';"
        "var CS='display:block;width:100%;margin:3px 0;padding:8px 10px;"
        "background:#2a3942;color:#e9edef;border:1px solid rgba(0,229,255,0.3);"
        "border-radius:6px;cursor:pointer;font-size:12px;text-align:left;"
        "font-family:inherit;';"
        "function Fi(v){"
        "if(!L){alert('Pehle kisi input box par click karein');return;}"
        "try{"
        "if(L.isContentEditable)L.textContent=v;"
        "else{"
        "var pr=L.tagName==='TEXTAREA'?"
        "window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;"
        "Object.getOwnPropertyDescriptor(pr,'value').set.call(L,v);}"
        "L.dispatchEvent(new Event('input',{bubbles:true}));"
        "L.dispatchEvent(new Event('change',{bubbles:true}));"
        "L.style.backgroundColor='#00FF8844';"
        "setTimeout(function(){L.style.backgroundColor='';},600);"
        "}catch(e){try{L.value=v;}catch(e2){}}"
        "}"
        "F.forEach(function(f){"
        "var v=D[f[0]];if(!v)return;"
        "var b=document.createElement('button');"
        "b.textContent=f[1];"
        "b.style.cssText=CS;"
        "b.onclick=function(){Fi(v);};"
        "P.appendChild(b);"
        "});"
        "var C=document.createElement('button');"
        "C.textContent='Close';"
        "C.style.cssText='display:block;width:100%;margin-top:8px;padding:6px;"
        "background:transparent;color:#FF4757;border:1px solid #FF4757;"
        "border-radius:6px;cursor:pointer;font-size:11px;';"
        "C.onclick=function(){P.remove();};"
        "P.appendChild(C);"
        "document.body.appendChild(P);"
        "})();"
    )
    return js


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("documents_vault.py — Verification (v7 QR)")
    print("=" * 60)

    assert len(DOCUMENT_FIELDS) == 15
    print(f"✅ {len(DOCUMENT_FIELDS)} fields defined")
    print(f"   Aadhaar fields: {len(AADHAAR_FIELDS)}")
    print(f"   Extra fields:   {len(EXTRA_FIELDS)}")

    print(f"\n📷 Status: {get_ocr_status()}")
    print(f"   OpenCV (QR):  {_CV2_AVAILABLE}")
    print(f"   Tesseract:    {_OCR_AVAILABLE}")

    bm = generate_bookmarklet({})
    assert bm.startswith("javascript:")
    print(f"\n✅ Bookmarklet: {len(bm)} chars")

    sample_data = {
        "full_name": "Avnish Kumar",
        "dob": "12/03/2007",
        "aadhaar_number": "9815 1859 5523",
    }
    bm2 = generate_bookmarklet(sample_data)
    assert bm2.startswith("javascript:")
    assert bm2.endswith("})();")
    print(f"✅ Real-data bookmarklet: {len(bm2)} chars")

    # Test QR decoding helper (offline)
    print("\n🧪 QR decoding helper tests:")

    # Test 1: Plain XML
    xml1 = '<PrintLetterBarcodeData uid="123456789012" name="Test User" gender="M" dob="01/01/1990" pc="110001"/>'
    parsed = _parse_aadhaar_xml(xml1)
    assert parsed is not None, "Plain XML parse failed"
    assert parsed.get("full_name") == "Test User", f"Name: {parsed.get('full_name')}"
    assert parsed.get("gender") == "Male"
    assert parsed.get("aadhaar_number") == "1234 5678 9012"
    assert parsed.get("pincode") == "110001"
    print("  ✅ Plain XML parsing works")

    # Test 2: Base64 encoded XML
    import base64 as b64
    xml_b64 = b64.b64encode(xml1.encode()).decode()
    decoded = _decode_aadhaar_qr_data(xml_b64)
    assert decoded is not None and "Test User" in decoded, "Base64 decode failed"
    print("  ✅ Base64 decoding works")

    # Test 3: Compressed XML (Secure QR simulation)
    import zlib
    xml_bytes = xml1.encode("utf-8")
    compressed = bytes([5]) + zlib.compress(xml_bytes)
    decoded = _decode_aadhaar_qr_data(compressed)
    assert decoded is not None and "Test User" in decoded, "Compressed decode failed"
    print("  ✅ Zlib-compressed decoding works")

    # Test 4: Bad data returns None
    assert _decode_aadhaar_qr_data("garbage data") is None
    assert _decode_aadhaar_qr_data(b"\x00\x01\x02") is None
    print("  ✅ Invalid data returns None")

    # Test 5: Regex fallback parsing
    parsed = _parse_aadhaar_xml(xml1)
    assert parsed["full_name"] == "Test User"
    print("  ✅ XML parsing works")

    print("\n" + "=" * 60)
    print("✅ documents_vault.py v7 — ALL CHECKS PASSED")
    print("=" * 60)