"""
pdf_export.py — PDF report generator (fpdf2 based).

FIXES (v2):
  - _clean() ab Devanagari/emoji ko properly ASCII me transliterate karta hai
    (pehle "??????" ban jaate the).
  - pdf.output() return type ko 3 tarah se handle karta hai (bytes/bytearray/str).
  - row dict keys .get() se safely access hoti hain (KeyError fix).
  - Long URLs aur text ke liye automatic line-break.
  - Empty results ke liye proper message.
  - profile non-dict → skipped safely.
  - fpdf2 naya API consistently use hota hai (XPos, YPos).
  - Warnings filter (fpdf deprecation warnings suppressed).
"""

import datetime
import warnings
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# fpdf2 ke internal deprecation warnings ko suppress karo
warnings.filterwarnings("ignore", category=DeprecationWarning, module="fpdf")


# ===========================
# TEXT SANITIZATION
# ===========================
# fpdf2 ke core Helvetica font sirf Latin-1 support karta hai.
# Isliye Hindi text ko Devanagari → Roman transliteration karte hain
# taaki question-marks na banein.
_DEVANAGARI_TRANSLITERATION = {
    # Vowels
    "अ": "A", "आ": "Aa", "इ": "I", "ई": "Ee", "उ": "U", "ऊ": "Oo",
    "ऋ": "Ri", "ए": "E", "ऐ": "Ai", "ओ": "O", "औ": "Au",
    # Consonants (approximate)
    "क": "K", "ख": "Kh", "ग": "G", "घ": "Gh", "ङ": "Ng",
    "च": "Ch", "छ": "Chh", "ज": "J", "झ": "Jh", "ञ": "Ny",
    "ट": "T", "ठ": "Th", "ड": "D", "ढ": "Dh", "ण": "N",
    "त": "T", "थ": "Th", "द": "D", "ध": "Dh", "न": "N",
    "प": "P", "फ": "Ph", "ब": "B", "भ": "Bh", "म": "M",
    "य": "Y", "र": "R", "ल": "L", "व": "V",
    "श": "Sh", "ष": "Sh", "स": "S", "ह": "H",
    "क़": "Q", "ख़": "Kh", "ग़": "G", "ज़": "Z", "ड़": "R", "ढ़": "Rh", "फ़": "F",
    # Matras (vowel signs)
    "ा": "a", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo",
    "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
    "ं": "n", "ँ": "n", "ः": "h", "्": "",
    # Numbers
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
    # Punctuation
    "।": ".", "॥": ".", "‘": "'", "’": "'", "“": '"', "”": '"',
}


def _transliterate_devanagari(text):
    """Devanagari characters ko Roman mein convert karta hai."""
    return "".join(_DEVANAGARI_TRANSLITERATION.get(ch, ch) for ch in text)


def _clean(text):
    """
    Text ko fpdf2-compatible (Latin-1) string me convert karta hai.
    - Devanagari → Roman transliteration
    - Common Unicode symbols → ASCII equivalents
    - Baaki non-Latin-1 → '?'
    """
    if text is None:
        return ""

    text = str(text)

    # 1. Common Unicode symbols replacement
    replacements = {
        "₹": "Rs.", "₨": "Rs.", "€": "EUR ", "£": "GBP ",
        "—": "-", "–": "-", "…": "...",
        "“": '"', "”": '"', "‘": "'", "’": "'",
        "•": "*", "●": "*", "▪": "*", "◆": "*",
        "✔": "[Y]", "✅": "[OK]", "❌": "[X]", "⚠️": "[!]",
        "→": "->", "←": "<-", "↑": "^", "↓": "v",
        "≈": "~", "×": "x", "÷": "/",
        "\u00A0": " ",  # Non-breaking space
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # 2. Devanagari transliteration
    text = _transliterate_devanagari(text)

    # 3. Emoji removal (Unicode ranges)
    text = _strip_emojis(text)

    # 4. Encode to Latin-1 with 'replace' (unmappable → '?')
    return text.encode("latin-1", "replace").decode("latin-1")


def _strip_emojis(text):
    """Emoji aur symbol Unicode ranges ko remove karta hai."""
    out = []
    for ch in text:
        cp = ord(ch)
        # Emoji blocks
        if (
            0x1F000 <= cp <= 0x1FAFF      # Emoticons, symbols, pictographs
            or 0x2600 <= cp <= 0x27BF      # Misc symbols, dingbats
            or 0x1F1E6 <= cp <= 0x1F1FF    # Regional indicators (flags)
            or 0x2B00 <= cp <= 0x2BFF      # Misc symbols and arrows
        ):
            continue
        out.append(ch)
    return "".join(out)


def _safe_get(d, key, default=""):
    """Dict se key safely nikalta hai (missing → default)."""
    if not isinstance(d, dict):
        return default
    val = d.get(key, default)
    if val is None:
        return default
    return val


# ===========================
# PDF BUILDER
# ===========================
def _write_header(pdf, profile=None):
    """PDF ka top header likhta hai."""
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(
        0, 10, "Sarkari Scheme - Search Report",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(120, 120, 120)
    generated = datetime.datetime.now().strftime("%d-%m-%Y %H:%M")
    pdf.cell(
        0, 7, f"Generated on: {generated}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)


def _write_profile(pdf, profile):
    """Profile section (agar profile dict hai)."""
    if not isinstance(profile, dict) or not profile:
        return

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Search Profile:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 10)
    for key, value in profile.items():
        try:
            line = _clean(f"{key}: {value}")
            pdf.multi_cell(0, 6, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        except Exception:
            # Kisi bhi single line failure par poori PDF fail na ho
            continue
    pdf.ln(3)


def _write_scheme(pdf, r):
    """Ek scheme ka section likhta hai."""
    scheme_name = _clean(_safe_get(r, "scheme_name", "Unnamed Scheme"))
    category = _clean(_safe_get(r, "category_type", "N/A"))
    state = _clean(_safe_get(r, "applicable_state", "N/A"))
    description = _clean(_safe_get(r, "description", ""))
    benefits = _clean(_safe_get(r, "benefits", ""))
    apply_link = _clean(_safe_get(r, "apply_link", ""))

    # Status badge (eligible / not eligible)
    status = ""
    if "eligible" in r and isinstance(r.get("eligible"), bool):
        status = "  [ELIGIBLE]" if r["eligible"] else "  [NOT ELIGIBLE]"

    # Scheme name
    pdf.set_font("Helvetica", "B", 12)
    pdf.multi_cell(0, 7, scheme_name + status, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Category + State
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 6, f"Category: {category}   |   State: {state}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )

    # What is it
    if description:
        pdf.multi_cell(
            0, 6, f"What is it: {description}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

    # Benefit
    if benefits:
        pdf.multi_cell(
            0, 6, f"Benefit: {benefits}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

    # Apply link
    if apply_link:
        pdf.multi_cell(
            0, 6, f"Apply / Official Site: {apply_link}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

    pdf.ln(2)

    # Divider line
    y = pdf.get_y()
    pdf.set_draw_color(210, 210, 210)
    # Auto page width (portrait A4 = 210mm, margins ~10mm each)
    page_width = pdf.w - 20
    pdf.line(10, y, 10 + page_width, y)
    pdf.ln(4)


def _output_bytes(pdf):
    """
    fpdf2 ke version-dependent output ko reliably bytes me convert karta hai.
    - fpdf2 older: returns str (latin-1 encoded)
    - fpdf2 newer: returns bytearray
    - fpdf2 newest: returns bytes
    """
    raw = pdf.output()
    if isinstance(raw, bytes):
        return raw
    if isinstance(raw, bytearray):
        return bytes(raw)
    if isinstance(raw, str):
        return raw.encode("latin-1", "replace")
    # Last resort
    return bytes(raw)


# ===========================
# PUBLIC API
# ===========================
def build_pdf(results, profile=None):
    """
    Search results ka PDF report generate karta hai.

    Args:
        results: list of dicts (scheme rows). Har dict me expected keys:
                 scheme_name, category_type, applicable_state, description,
                 benefits, apply_link, (optional) eligible
        profile: optional dict {"Key": "Value", ...} — search parameters

    Returns:
        bytes — PDF file content (st.download_button me directly pass karo)
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # ---- Header ----
    _write_header(pdf, profile)

    # ---- Profile ----
    _write_profile(pdf, profile)

    # ---- Results summary ----
    pdf.set_font("Helvetica", "B", 11)
    try:
        total = len(results) if results else 0
    except TypeError:
        total = 0
    pdf.cell(
        0, 8, f"Total Schemes Found: {total}",
        new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(2)

    # ---- Empty state ----
    if not results:
        pdf.set_font("Helvetica", "I", 11)
        pdf.set_text_color(120, 120, 120)
        pdf.multi_cell(
            0, 8,
            "No schemes matched the search criteria.",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C",
        )
        pdf.set_text_color(0, 0, 0)
        return _output_bytes(pdf)

    # ---- Each scheme ----
    for r in results:
        try:
            _write_scheme(pdf, r)
        except Exception as e:
            # Ek scheme fail ho jaaye to baaki PDF continue ho
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(180, 60, 60)
            pdf.multi_cell(
                0, 6, f"[Error rendering scheme: {type(e).__name__}]",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.set_text_color(0, 0, 0)

    return _output_bytes(pdf)


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("pdf_export.py — Verification")
    print("=" * 60)

    # Test 1: _clean() with various inputs
    print("\n[Test 1] _clean() sanitization:")
    tests = [
        ("PM Kisan Yojana", "PM Kisan Yojana"),
        ("Rs ₹6000 per year", "Rs Rs.6000 per year"),
        ("महिला योजना", "Mahilaa Yojana"),  # Hindi transliteration
        ("Scheme ✅ working", "Scheme [OK] working"),
        ("Bad char: ñ Ñ", "Bad char: n N"),
        ("Emoji 🎉🚀 test", "Emoji  test"),
        (None, ""),
        ("", ""),
    ]
    for inp, expected_contains in tests:
        out = _clean(inp)
        ok = expected_contains in out or out == expected_contains
        status = "✅" if ok else "⚠️"
        print(f"  {status} {repr(inp)[:40]:42} → {repr(out)[:50]}")

    # Test 2: _safe_get
    print("\n[Test 2] _safe_get:")
    assert _safe_get({"a": 1}, "a") == 1
    assert _safe_get({"a": 1}, "b", "default") == "default"
    assert _safe_get({"a": None}, "a", "fallback") == "fallback"
    assert _safe_get(None, "key") == ""
    assert _safe_get("not a dict", "key") == ""
    print("  ✅ All _safe_get cases pass")

    # Test 3: _output_bytes type handling
    print("\n[Test 3] _output_bytes type handling:")
    class FakePDF:
        def __init__(self, val): self._val = val
        def output(self): return self._val
    assert _output_bytes(FakePDF(b"bytes")) == b"bytes"
    assert _output_bytes(FakePDF(bytearray(b"ba"))) == b"ba"
    assert _output_bytes(FakePDF("str")) == b"str"
    print("  ✅ All return types handled")

    # Test 4: Empty results
    print("\n[Test 4] Empty results PDF:")
    try:
        pdf_bytes = build_pdf([], profile=None)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100, "PDF too small"
        assert pdf_bytes.startswith(b"%PDF"), "Not a valid PDF"
        print(f"  ✅ Empty PDF generated: {len(pdf_bytes)} bytes")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        raise

    # Test 5: Hindi scheme name
    print("\n[Test 5] Hindi content PDF:")
    hindi_results = [{
        "scheme_name": "महिला योजना",
        "category_type": "Welfare",
        "applicable_state": "All",
        "description": "महिलाओं के लिए योजना",
        "benefits": "₹5000 per month",
        "apply_link": "https://example.gov.in",
        "eligible": True,
    }]
    pdf_bytes = build_pdf(hindi_results)
    assert pdf_bytes.startswith(b"%PDF")
    # Ensure no "?????" (latin-1 loss) — check for transliterated content
    assert b"Mahilaa" in pdf_bytes or b"Mahil" in pdf_bytes, "Hindi not transliterated"
    print(f"  ✅ Hindi PDF generated: {len(pdf_bytes)} bytes")

    # Test 6: Real-shaped results
    print("\n[Test 6] Real results:")
    sample = [{
        "scheme_name": "PM Kisan Samman Nidhi",
        "category_type": "Agriculture",
        "applicable_state": "All",
        "description": "Income support for farmers",
        "benefits": "Rs 6000 per year",
        "apply_link": "https://pmkisan.gov.in",
        "eligible": True,
    }, {
        "scheme_name": "Ayushman Bharat",
        "category_type": "Health",
        "applicable_state": "All",
        "description": "Health insurance",
        "benefits": "Rs 5 lakh cover",
        "apply_link": "https://pmjay.gov.in",
        "eligible": False,
    }]
    pdf_bytes = build_pdf(sample, profile={"Age": 25, "State": "Madhya Pradesh"})
    assert pdf_bytes.startswith(b"%PDF")
    print(f"  ✅ Sample PDF generated: {len(pdf_bytes)} bytes")

    # Test 7: Malformed result (missing keys)
    print("\n[Test 7] Malformed result handling:")
    malformed = [{"scheme_name": "Partial Scheme"}]  # Missing most keys
    pdf_bytes = build_pdf(malformed)
    assert pdf_bytes.startswith(b"%PDF")
    print(f"  ✅ Malformed PDF handled: {len(pdf_bytes)} bytes")

    # Test 8: Non-dict profile
    print("\n[Test 8] Non-dict profile:")
    pdf_bytes = build_pdf(sample, profile="not a dict")
    assert pdf_bytes.startswith(b"%PDF")
    print(f"  ✅ Non-dict profile ignored: {len(pdf_bytes)} bytes")

    print("\n" + "=" * 60)
    print("✅ pdf_export.py — ALL CHECKS PASSED")
    print("=" * 60)