"""
simple_explain.py — Simple-language scheme explanations.

Uses Groq (via langchain-groq) when available; falls back to template-based
simple text otherwise.

FIXES (v3):
  - explain_scheme_ai() ab (text, error) tuple return karta hai — caller
    "❌" string matching par nahi depend karta (fragile tha).
  - LLM ab @st.cache_resource se cache hoti hai — har call pe naya ChatGroq
    nahi banta (performance fix).
  - GROQ_MODEL_NAME default ab ai_chatbot.py ke saath consistent.
  - ChatGroq call me timeout set kiya (hang prevention).
  - Error messages sanitize hote hain (API key leak prevention).
  - Non-string inputs None-safe.
  - HAS_GROQ False + no API key — clear signal (ki AI off hai).
  - __main__ self-test (offline, no API call).
"""

import os
from dotenv import load_dotenv
import streamlit as st

# Langchain Groq (optional)
try:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ✅ CONSISTENT DEFAULT with ai_chatbot.py
DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-20b")

# Groq API timeout (seconds)
GROQ_TIMEOUT = 20


# ===========================
# LANGUAGE PROMPTS
# ===========================
_LANG_PROMPTS = {
    "हिंदी": "आप एक सहायक हैं। सरकारी योजनाओं को सरल हिंदी में समझाएं। 2-3 वाक्यों में रखें।",
    "मराठी": "तुम्ही एक सहाय्यक आहात. सरकारी योजना सोप्या मराठीत समजावून सांगा. 2-3 वाक्यांत ठेवा.",
    "தமிழ்": "நீங்கள் ஒரு உதவியாளர். அரசாங்க திட்டங்களை எளிய தமிழில் விளக்குங்கள். 2-3 வாக்கியங்களில் வைக்கவும்.",
}
_DEFAULT_PROMPT = (
    "You are a helpful assistant. Explain government schemes in simple "
    "English. Keep it concise (2-3 sentences)."
)


# ===========================
# HELPERS
# ===========================
def _safe_str(value, default=""):
    """None/NaN/non-str → safe string."""
    if value is None:
        return default
    try:
        if value != value:  # NaN check without pandas
            return default
    except Exception:
        pass
    return str(value)


def _sanitize_error(error):
    """
    Error message ko safe banata hai — API key / URLs strip karta hai.
    Log me full error jaata hai, UI me sirf sanitized version.
    """
    msg = _safe_str(error, "unknown error")
    # API keys redact (gsk_... format)
    msg = __import__("re").sub(r'gsk_[A-Za-z0-9]+', 'gsk_***', msg)
    # Long URLs truncate (could contain tokens)
    msg = __import__("re").sub(r'https?://\S+', '[URL]', msg)
    # Max 200 chars
    return msg[:200]


def _get_lang_prompt(lang_choice):
    """Language-specific system prompt."""
    return _LANG_PROMPTS.get(lang_choice, _DEFAULT_PROMPT)


def _is_groq_available():
    """True agar API key set hai AND langchain_groq installed hai."""
    return bool(GROQ_API_KEY) and HAS_GROQ


# ===========================
# CACHED LLM
# ===========================
@st.cache_resource(show_spinner=False)
def _get_cached_llm():
    """
    ChatGroq instance cached — har call pe naya object nahi.
    Returns None if not available.
    """
    if not _is_groq_available():
        return None
    try:
        return ChatGroq(
            temperature=0.7,
            groq_api_key=GROQ_API_KEY,
            model_name=DEFAULT_GROQ_MODEL,
            timeout=GROQ_TIMEOUT,
        )
    except Exception as e:
        print(f"[simple_explain] LLM init failed: {_sanitize_error(e)}")
        return None


@st.cache_resource(show_spinner=False)
def _get_cached_prompt():
    """Cached ChatPromptTemplate (rebuild cost avoid)."""
    return ChatPromptTemplate.from_messages([
        ("system", "{system_prompt}"),
        ("human",
         "Scheme: {scheme_name}\n"
         "Category: {category_type}\n"
         "Description: {description}\n"
         "Benefits: {benefits}\n"
         "State: {applicable_state}\n\n"
         "Explain this scheme in simple words for a common person."),
    ])


# ===========================
# AI-BASED EXPLANATION
# ===========================
def explain_scheme_ai(scheme_name, description, benefits, lang_choice,
                       category_type, applicable_state, apply_link,
                       deadline, eligible, score):
    """
    Groq AI se scheme explanation generate karta hai.

    Returns:
        (text: str | None, error: str | None)
        - On success: (explanation_text, None)
        - On failure: (None, error_message)
    """
    # Availability checks
    if not _is_groq_available():
        return None, "AI not configured"

    llm = _get_cached_llm()
    if llm is None:
        return None, "AI initialization failed"

    prompt = _get_cached_prompt()

    # All inputs None-safe
    inputs = {
        "system_prompt": _get_lang_prompt(lang_choice),
        "scheme_name": _safe_str(scheme_name, "Unnamed Scheme"),
        "category_type": _safe_str(category_type, "N/A"),
        "description": _safe_str(description, "No description available"),
        "benefits": _safe_str(benefits, "No benefits listed"),
        "applicable_state": _safe_str(applicable_state, "All"),
    }

    try:
        chain = prompt | llm
        response = chain.invoke(inputs)
        text = _safe_str(getattr(response, "content", None), "").strip()
        if not text:
            return None, "Empty AI response"
        return text, None
    except Exception as e:
        # Log full error, return sanitized
        print(f"[simple_explain] AI call failed: {type(e).__name__}: {e}")
        return None, _sanitize_error(e)


# ===========================
# TEMPLATE FALLBACK (no AI)
# ===========================
def explain_scheme_text(scheme_name, description, benefits, lang_choice,
                         category_type, applicable_state, apply_link,
                         deadline, eligible, score):
    """
    Simple template-based explanation (AI ke bina).

    Har language ke liye ek template. All inputs None-safe.
    """
    scheme_name = _safe_str(scheme_name, "This scheme")
    category_type = _safe_str(category_type, "welfare")
    description = _safe_str(description, "no description available")
    benefits = _safe_str(benefits, "no specific benefits listed")
    applicable_state = _safe_str(applicable_state, "All")

    state_display = (
        "all India" if applicable_state == "All"
        else applicable_state
    )

    if lang_choice == "हिंदी":
        return (
            f"**{scheme_name}** एक {category_type} योजना है। "
            f"इसका मुख्य उद्देश्य है: {description}। "
            f"इसमें आपको ये लाभ मिलते हैं: {benefits}। "
            f"आप {state_display} से आवेदन कर सकते हैं।"
        )
    elif lang_choice == "मराठी":
        return (
            f"**{scheme_name}** ही एक {category_type} योजना आहे. "
            f"याचा मुख्य उद्देश्य आहे: {description}. "
            f"यामध्ये तुम्हाला हे लाभ मिळतात: {benefits}. "
            f"तुम्ही {state_display} मधून अर्ज करू शकता."
        )
    elif lang_choice == "தமிழ்":
        return (
            f"**{scheme_name}** என்பது ஒரு {category_type} திட்டம். "
            f"இதன் முக்கிய நோக்கம்: {description}. "
            f"இதில் உங்களுக்கு இந்த பலன்கள் கிடைக்கும்: {benefits}. "
            f"நீங்கள் {state_display} இலிருந்து விண்ணப்பிக்கலாம்."
        )
    else:
        return (
            f"**{scheme_name}** is a {category_type} scheme. "
            f"Its main objective is: {description}. "
            f"You get these benefits: {benefits}. "
            f"You can apply from {state_display}."
        )


# ===========================
# MAIN EXPLAIN (public)
# ===========================
def explain_scheme(scheme_name, description, benefits, lang_choice,
                    category_type, applicable_state, apply_link,
                    deadline, eligible, score):
    """
    Main explanation function.

    Priority:
      1. AI (if configured)
      2. Template-based fallback

    Never returns an error string — hamesha usable explanation deta hai.
    """
    # Try AI first
    ai_text, ai_error = explain_scheme_ai(
        scheme_name=scheme_name,
        description=description,
        benefits=benefits,
        lang_choice=lang_choice,
        category_type=category_type,
        applicable_state=applicable_state,
        apply_link=apply_link,
        deadline=deadline,
        eligible=eligible,
        score=score,
    )

    if ai_text:
        return ai_text

    # AI unavailable or failed → template fallback
    # Note: ai_error me specific reason hai — caller chahe to log/display kar sakta hai
    return explain_scheme_text(
        scheme_name=scheme_name,
        description=description,
        benefits=benefits,
        lang_choice=lang_choice,
        category_type=category_type,
        applicable_state=applicable_state,
        apply_link=apply_link,
        deadline=deadline,
        eligible=eligible,
        score=score,
    )


def get_ai_status():
    """
    Debug/info: AI configuration status.
    Returns dict {"available": bool, "reason": str, "model": str|None}
    """
    if not HAS_GROQ:
        return {
            "available": False,
            "reason": "langchain-groq not installed",
            "model": None,
        }
    if not GROQ_API_KEY:
        return {
            "available": False,
            "reason": "GROQ_API_KEY not set in .env",
            "model": None,
        }
    return {
        "available": True,
        "reason": "OK",
        "model": DEFAULT_GROQ_MODEL,
    }


# ===========================
# SELF-TEST (offline)
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("simple_explain.py — Verification")
    print("=" * 60)

    # Test 1: AI status
    print("\n[Test 1] AI status:")
    status = get_ai_status()
    print(f"  Available: {status['available']}")
    print(f"  Reason:    {status['reason']}")
    print(f"  Model:     {status['model']}")

    # Test 2: _sanitize_error
    print("\n[Test 2] _sanitize_error:")
    dirty = "Error at https://api.groq.com/v1/chat with key gsk_abc123XYZ"
    clean = _sanitize_error(dirty)
    assert "gsk_***" in clean, f"API key not redacted: {clean}"
    assert "https://" not in clean, f"URL not stripped: {clean}"
    print(f"  ✅ Sanitized: {clean}")

    # Test 3: Template fallback — English
    print("\n[Test 3] Template fallback (English):")
    text = explain_scheme_text(
        "PM Kisan", "Income support for farmers", "Rs 6000 per year",
        "English", "Agriculture", "All", "https://x.gov.in", "", True, 0,
    )
    assert "PM Kisan" in text
    assert "Agriculture" in text
    assert "Rs 6000" in text
    print(f"  ✅ {text[:80]}...")

    # Test 4: Template fallback — Hindi
    print("\n[Test 4] Template fallback (Hindi):")
    text = explain_scheme_text(
        "PM Kisan", "किसानों के लिए आय सहायता", "₹6000 प्रति वर्ष",
        "हिंदी", "कृषि", "All", "https://x.gov.in", "", True, 0,
    )
    assert "PM Kisan" in text
    assert "कृषि" in text
    print(f"  ✅ {text[:80]}...")

    # Test 5: Template handles None inputs
    print("\n[Test 5] Template handles None inputs:")
    text = explain_scheme_text(
        None, None, None, "English", None, None, None, None, False, 0,
    )
    assert "This scheme" in text
    assert "None" not in text, "None leaked into template output"
    print(f"  ✅ {text[:80]}...")

    # Test 6: Template unknown language → English
    print("\n[Test 6] Template unknown language:")
    text = explain_scheme_text(
        "Test", "Desc", "Ben", "Klingon", "Cat", "All", "", "", True, 0,
    )
    assert "is a" in text, "Should fall back to English template"
    print(f"  ✅ Falls back to English")

    # Test 7: explain_scheme (main) without API key
    print("\n[Test 7] explain_scheme() fallback path:")
    text = explain_scheme(
        "Test Scheme", "Test description", "Test benefits",
        "English", "Health", "All", "https://x.gov.in", "", True, 0,
    )
    assert isinstance(text, str) and len(text) > 0
    # Should NEVER contain "❌" error marker now (returns template fallback)
    assert "❌" not in text, "Error marker leaked into explanation"
    print(f"  ✅ Got usable explanation: {text[:60]}...")

    # Test 8: AI call returns (text, error) tuple
    print("\n[Test 8] explain_scheme_ai() return signature:")
    result = explain_scheme_ai(
        "Test", "Desc", "Ben", "English", "Cat", "All", "", "", True, 0,
    )
    assert isinstance(result, tuple) and len(result) == 2
    text, err = result
    # Without API key, should return (None, error_message)
    if not status["available"]:
        assert text is None
        assert err is not None
        print(f"  ✅ Without AI: (None, '{err}')")
    else:
        print(f"  ✅ With AI: text={text is not None}, err={err}")

    # Test 9: Language prompt selection
    print("\n[Test 9] Language prompt selection:")
    for lang in ["English", "हिंदी", "मराठी", "தமிழ்", "Unknown"]:
        p = _get_lang_prompt(lang)
        assert isinstance(p, str) and len(p) > 10
    print("  ✅ All languages have prompts (or English fallback)")

    # Test 10: _is_groq_available logic
    print("\n[Test 10] _is_groq_available():")
    avail = _is_groq_available()
    expected = bool(GROQ_API_KEY) and HAS_GROQ
    assert avail == expected
    print(f"  ✅ {avail} (HAS_GROQ={HAS_GROQ}, API_KEY={'set' if GROQ_API_KEY else 'missing'})")

    print("\n" + "=" * 60)
    print("✅ simple_explain.py — ALL CHECKS PASSED")
    print("=" * 60)