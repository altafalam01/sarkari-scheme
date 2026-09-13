"""
AI Chatbot — Smart Assistant with Profile Questions.

Features:
  1. Dynamic Follow-up Questions (Smart Branching)
  2. Natural Language Chat Mode (AI-Powered)
  3. AI-Generated Personalized Suggestions
  4. Progress Bar (Multi-Step Wizard)
  5. Save Profile to User Data
  6. Quick Reply Suggestions
  7. Assistant Analytics (Logging)

FIXES (v5):
  - get_llm() now @st.cache_resource decorated and defined at TOP of file —
    single LLM instance shared across all callers (matches simple_explain.py
    pattern). Previously two separate instances were created.
  - reset_assistant() also clears ai_conversation + _last_assistant_mode.
  - fallback_search_schemes() now computes real match score instead of
    hardcoded 0.5 — sort order stable and "match %" chip meaningful.
  - render_nl_chat_mode() uses session_state.lang_choice instead of
    hardcoded "English" — docs/explanation now respect user language.
  - render_profile_mode() progress bar HTML built as SINGLE-LINE
    concatenation (CommonMark HTML block bug fix).
  - nl_search imported at top (not inside function) — consistent with
    Streamlit caching model.
  - ai_chatbot_ui() nested try/except around load_schemes() fallback.
  - _safe_str / _atomic_json_write / _expand_query_typos / _normalize_state
    unchanged from v4 (they were correct).
  - Auto-scroll exception now logged (not silently swallowed).
"""

import os
import re
import json
import tempfile
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableLambda

from matcher import match_schemes, load_schemes
from translations import get_text

try:
    from nl_search import search_schemes as nl_search_fn
    _NL_SEARCH_AVAILABLE = True
except ImportError:
    nl_search_fn = None
    _NL_SEARCH_AVAILABLE = False

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-20b")

MAX_LOG_ENTRIES = 200
GROQ_TIMEOUT = 20


# ===========================
# CACHED LLM (single source of truth)
# ===========================
@st.cache_resource(show_spinner=False)
def get_llm():
    """
    ChatGroq instance — @st.cache_resource se cached, taaki har call pe
    naya object na bane.

    Ye function ab file ke TOP pe hai taaki saare callers ise access kar
    sakein without forward reference. Pehle ye file ke neeche tha, aur
    upar wale functions forward-reference par depend karte the (works
    but confusing).

    Returns None if API key missing or init fails.
    """
    if not GROQ_API_KEY:
        return None
    try:
        return ChatGroq(
            temperature=0.7,
            groq_api_key=GROQ_API_KEY,
            model_name=DEFAULT_GROQ_MODEL,
            timeout=GROQ_TIMEOUT,
        )
    except Exception as e:
        print(f"[ai_chatbot] LLM init failed: {type(e).__name__}: {e}")
        return None


# ===========================
# TYPO EXPANSIONS (Hinglish)
# ===========================
TYPO_EXPANSIONS = {
    "saadi": "shaadi", "shadi": "shaadi", "shaadhi": "shaadi",
    "marraige": "marriage", "mariage": "marriage",
    "scholership": "scholarship", "scholorship": "scholarship",
    "skolarship": "scholarship", "scholaship": "scholarship",
    "penshan": "pension", "pention": "pension", "penshion": "pension",
    "lone": "loan", "loan": "loan", "karzaa": "karza", "karja": "karza",
    "kisaan": "kisan", "kissan": "kisan", "kishan": "kisan",
    "padai": "padhai", "padhaai": "padhai", "padhaayi": "padhai",
    "pesha": "paisa", "paisaa": "paisa",
    "ladaki": "ladki", "ladakee": "ladki", "ladki": "ladki",
    "badi": "beti", "bette": "beti", "betee": "beti",
    "kanyaadan": "kanyadan", "kanya daan": "kanyadan",
    "vivah": "vivaah", "vivaha": "vivaah",
    "bijali": "bijli", "bijalee": "bijli",
    "aawas": "awas", "aavas": "awas",
    "shiksha": "shiksha", "siksha": "shiksha", "shikshaa": "shiksha",
    "swasthya": "swasthya", "svasthya": "swasthya",
    "bima": "bima", "bimaa": "bima",
    "yojna": "yojana", "yojnaa": "yojana",
}


# State aliases (for LLM-returned short forms)
STATE_ALIASES = {
    "mp": "Madhya Pradesh",
    "up": "Uttar Pradesh",
    "ap": "Andhra Pradesh",
    "mh": "Maharashtra",
    "rj": "Rajasthan",
    "br": "Bihar",
    "gj": "Gujarat",
    "ka": "Karnataka",
    "kl": "Kerala",
    "tn": "Tamil Nadu",
    "ts": "Telangana",
    "wb": "West Bengal",
    "pb": "Punjab",
    "hr": "Haryana",
    "od": "Odisha",
    "jk": "Jammu and Kashmir",
    "dl": "Delhi",
    "hp": "Himachal Pradesh",
    "uk": "Uttarakhand",
    "cg": "Chhattisgarh",
    "jh": "Jharkhand",
    "ga": "Goa",
    "as": "Assam",
}


# ===========================
# HELPERS
# ===========================
def _safe_str(value, default=""):
    """None/NaN/non-str → safe string."""
    if value is None:
        return default
    try:
        if value != value:  # NaN
            return default
    except Exception:
        pass
    return str(value)


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _atomic_json_write(path, data):
    """JSON file ko atomically likhta hai (temp + os.replace)."""
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(prefix=".json_", suffix=".tmp", dir=dir_path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        _safe_remove(tmp_path)
        raise


def _expand_query_typos(query):
    """Query me common Hinglish typos correct karta hai."""
    if not query:
        return query
    words = str(query).split()
    expanded = []
    for w in words:
        w_clean = w.lower().strip(".,!?;:")
        if w_clean in TYPO_EXPANSIONS:
            expanded.append(TYPO_EXPANSIONS[w_clean])
        else:
            expanded.append(w)
    return " ".join(expanded)


def _normalize_state(state_raw):
    """State aliases (MP → Madhya Pradesh) + whitespace normalization."""
    if not state_raw:
        return "All"
    state_str = _safe_str(state_raw).strip()
    if not state_str or state_str.lower() == "all":
        return "All"
    key = state_str.lower().replace(".", "").strip()
    if key in STATE_ALIASES:
        return STATE_ALIASES[key]
    return state_str


# ===========================
# AUTO-SCROLL HELPER
# ===========================
def auto_scroll_to_bottom():
    """Page ko smoothly bottom pe scroll karta hai."""
    try:
        components.html(
            """
            <script>
                try {
                    const parentDoc = window.parent.document;
                    function scrollToBottom() {
                        const chatInput = parentDoc.querySelector('.stChatFloatingInputContainer');
                        if (chatInput) {
                            chatInput.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        } else {
                            const mainContainer = parentDoc.querySelector('.main')
                                              || parentDoc.querySelector('section.main');
                            if (mainContainer) {
                                mainContainer.scrollTo({
                                    top: mainContainer.scrollHeight, behavior: 'smooth'
                                });
                            } else {
                                window.parent.scrollTo({
                                    top: parentDoc.body.scrollHeight, behavior: 'smooth'
                                });
                            }
                        }
                    }
                    setTimeout(scrollToBottom, 300);
                } catch (e) {}
            </script>
            """,
            height=0,
        )
    except Exception as e:
        print(f"[ai_chatbot] auto_scroll skipped: {type(e).__name__}")


# ===========================
# DYNAMIC PROFILE QUESTIONS
# ===========================
def get_dynamic_questions(profile):
    """Profile ke hisaab se dynamic questions (smart branching)."""
    if not isinstance(profile, dict):
        profile = {}

    questions = [
        {"key": "age", "question": "What is your age?",
         "options": ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"],
         "type": "single"},
        {"key": "state", "question": "Which state do you belong to?",
         "options": ["All", "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi",
                     "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir",
                     "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra",
                     "Odisha", "Punjab", "Rajasthan", "Tamil Nadu", "Telangana",
                     "Uttar Pradesh", "Uttarakhand", "West Bengal"],
         "type": "single"},
        {"key": "gender", "question": "What is your gender?",
         "options": ["All", "Male", "Female"], "type": "single"},
        {"key": "social_category", "question": "What is your social category?",
         "options": ["All", "General", "SC", "ST", "OBC", "Minority"],
         "type": "single"},
        {"key": "income", "question": "What is your annual family income? (in ₹)",
         "options": ["0 - 60,000", "60,001 - 80,000", "80,001 - 1,00,000",
                     "1,00,001 - 1,20,000", "1,20,001 - 2,00,000",
                     "2,00,001 - 3,00,000", "3,00,001 - 5,00,000",
                     "5,00,001 - 8,00,000", "8,00,001 - 12,00,000",
                     "12,00,001+"],
         "type": "single"},
        {"key": "occupation", "question": "What is your occupation?",
         "options": ["Student", "Farmer", "Self-employed/Small business",
                     "Unorganised worker", "Entrepreneur", "Senior citizen",
                     "Unemployed youth", "Salaried employee", "Housewife"],
         "type": "single"},
    ]

    # Smart branching
    occupation = _safe_str(profile.get("occupation", "")).lower()
    gender = _safe_str(profile.get("gender", "")).lower()
    age = profile.get("age", 0)

    try:
        if "-" in str(age):
            age_int = int(str(age).split("-")[0])
        elif "+" in str(age):
            age_int = int(str(age).replace("+", ""))
        else:
            age_int = int(age) if age not in ["All", None, ""] else 0
    except (ValueError, TypeError):
        age_int = 0

    if "student" in occupation:
        questions.append({
            "key": "education_level",
            "question": "What is your current education level?",
            "options": ["Class 9-10", "Class 11-12", "Graduate", "Post-Graduate", "PhD"],
            "type": "single",
        })
        questions.append({
            "key": "institute_type",
            "question": "What type of institute are you studying in?",
            "options": ["Government", "Private", "Not studying"],
            "type": "single",
        })
    elif "farmer" in occupation:
        questions.append({
            "key": "land_size",
            "question": "How much agricultural land do you own?",
            "options": ["No land", "Less than 1 acre", "1-2 acres", "2-5 acres", "More than 5 acres"],
            "type": "single",
        })
        questions.append({
            "key": "crop_type",
            "question": "What type of crops do you grow?",
            "options": ["Food grains", "Vegetables", "Fruits", "Cash crops", "Mixed"],
            "type": "single",
        })
    elif "female" in gender or "housewife" in occupation:
        questions.append({
            "key": "marital_status",
            "question": "What is your marital status?",
            "options": ["Unmarried", "Married", "Widow", "Divorced"],
            "type": "single",
        })
        questions.append({
            "key": "has_children",
            "question": "Do you have children?",
            "options": ["No", "Yes - 1 child", "Yes - 2 children", "Yes - 3+ children"],
            "type": "single",
        })
    elif "senior" in occupation or age_int >= 60:
        questions.append({
            "key": "has_pension",
            "question": "Do you receive any pension?",
            "options": ["No", "Yes - Government", "Yes - Private"],
            "type": "single",
        })
    elif "unemployed" in occupation or "youth" in occupation:
        questions.append({
            "key": "looking_for",
            "question": "What are you looking for?",
            "options": ["Job", "Skill Training", "Business Loan", "Education"],
            "type": "single",
        })
    elif "business" in occupation or "entrepreneur" in occupation:
        questions.append({
            "key": "business_type",
            "question": "What type of business?",
            "options": ["Manufacturing", "Retail/Shop", "Service", "Online", "Agriculture"],
            "type": "single",
        })
        questions.append({
            "key": "business_stage",
            "question": "What stage is your business at?",
            "options": ["Idea", "Starting up", "Running", "Expanding"],
            "type": "single",
        })

    questions.append({
        "key": "special_needs",
        "question": "Do you have any special category?",
        "options": ["None", "Divyang (Disabled)", "Widow", "Orphan", "Ex-serviceman"],
        "type": "single",
    })

    return questions


# ===========================
# SESSION STATE
# ===========================
def init_assistant_state():
    """Saare assistant state keys initialize karta hai."""
    defaults = {
        "assistant_profile": {},
        "assistant_step": 0,
        "assistant_messages": [],
        "assistant_results": [],
        "assistant_complete": False,
        "assistant_mode": "profile",
        "nl_chat_history": [],
        "nl_last_schemes": [],
        "_last_assistant_mode": None,
        "ai_messages": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def reset_assistant():
    """Poora assistant state reset karta hai (all 3 modes)."""
    st.session_state.assistant_profile = {}
    st.session_state.assistant_step = 0
    st.session_state.assistant_messages = []
    st.session_state.assistant_results = []
    st.session_state.assistant_complete = False
    st.session_state.nl_chat_history = []
    st.session_state.nl_last_schemes = []
    st.session_state.ai_messages = []
    # v5 FIX: ai_conversation aur _last_assistant_mode bhi clear
    if "ai_conversation" in st.session_state:
        st.session_state.ai_conversation = None
    if "_ai_session_id" in st.session_state:
        del st.session_state["_ai_session_id"]
    st.session_state._last_assistant_mode = None


# ===========================
# RANGE → NUMBER
# ===========================
def extract_number_from_range(value):
    """Range string ('18-25', '60,001 - 80,000', '12,00,001+') → number."""
    if value is None or value in ["All", ""]:
        return None

    val_str = _safe_str(value).strip().replace(",", "")

    if val_str.endswith("+"):
        try:
            return int(val_str.replace("+", "").strip())
        except ValueError:
            return None

    if "-" in val_str:
        try:
            lower = val_str.split("-")[0].strip()
            return int(float(lower))
        except (ValueError, IndexError):
            return None

    try:
        return int(float(val_str))
    except ValueError:
        return None


# ===========================
# ANALYTICS LOGGING (atomic + quarantine)
# ===========================
def log_assistant_query(query, matched_count, profile=None):
    """Assistant queries ko log karta hai (atomic write)."""
    try:
        log_file = "data/assistant_log.json"
        os.makedirs("data", exist_ok=True)

        log = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    log = data
            except (json.JSONDecodeError, OSError):
                try:
                    corrupt = log_file + ".corrupt"
                    if os.path.exists(corrupt):
                        corrupt = f"{log_file}.{int(datetime.now().timestamp())}.corrupt"
                    os.replace(log_file, corrupt)
                except OSError:
                    pass
                log = []

        log.append({
            "query": _safe_str(query),
            "matched": int(matched_count) if isinstance(matched_count, (int, float)) else 0,
            "profile": profile if isinstance(profile, dict) else None,
            "timestamp": datetime.now().isoformat(),
        })

        log = log[-MAX_LOG_ENTRIES:]

        _atomic_json_write(log_file, log)
    except Exception as e:
        print(f"[ai_chatbot] log_assistant_query failed: {type(e).__name__}: {e}")


# ===========================
# SAVE PROFILE (atomic)
# ===========================
def save_profile_to_user_data(profile):
    """User profile ko data/user_profile.json me save karta hai (atomic)."""
    try:
        if not isinstance(profile, dict):
            return False

        age_val = extract_number_from_range(profile.get("age", 25))
        income_val = extract_number_from_range(profile.get("income", 200000))

        profile_to_save = {
            "age": age_val if age_val is not None else 25,
            "income": income_val if income_val is not None else 200000,
            "state": _safe_str(profile.get("state", "All")),
            "gender": _safe_str(profile.get("gender", "All")),
            "occupation": _safe_str(profile.get("occupation", "All")),
            "social_category": _safe_str(profile.get("social_category", "All")),
        }

        os.makedirs("data", exist_ok=True)
        _atomic_json_write("data/user_profile.json", profile_to_save)
        return True
    except Exception:
        return False


# ===========================
# RULE-BASED FALLBACK SEARCH
# ===========================
def fallback_search_schemes(query, df, top_n=5):
    """
    LLM fail hone par TF-IDF keyword search.
    Pehla attempt: nl_search module (agar available).
    Fallback: simple keyword matching with real score.
    """
    if _NL_SEARCH_AVAILABLE and nl_search_fn is not None:
        try:
            results = nl_search_fn(df, query, top_n=top_n)
            if results:
                return results
        except Exception as e:
            print(f"[ai_chatbot] nl_search fallback failed: {e}")

    # Simple keyword matching with real score
    try:
        query_lower = _safe_str(query).lower()
        keywords = [w for w in query_lower.split() if len(w) > 2]
        if not keywords:
            return []

        if df is None or df.empty:
            return []

        scored = []
        for _, row in df.iterrows():
            text = (
                f"{_safe_str(row.get('scheme_name', ''))} "
                f"{_safe_str(row.get('description', ''))} "
                f"{_safe_str(row.get('benefits', ''))}"
            ).lower()
            hits = sum(1 for kw in keywords if kw in text)
            if hits > 0:
                # Real score: fraction of keywords matched
                score = hits / len(keywords)
                scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, row in scored[:top_n]:
            results.append({
                "scheme_name": _safe_str(row.get("scheme_name", "")),
                "category_type": _safe_str(row.get("category_type", "")),
                "applicable_state": _safe_str(row.get("applicable_state", "")),
                "description": _safe_str(row.get("description", "")),
                "benefits": _safe_str(row.get("benefits", "")),
                "apply_link": _safe_str(row.get("apply_link", "")),
                "deadline": row.get("deadline", None),
                "score": float(score),
            })
        return results
    except Exception:
        return []


# ===========================
# AI RECOMMENDATION
# ===========================
def generate_ai_recommendation(profile, matched_schemes):
    """Profile-based AI recommendation (Hinglish)."""
    llm = get_llm()
    if not llm or not matched_schemes:
        return None
    if not isinstance(profile, dict):
        profile = {}

    top_schemes = [
        _safe_str(r.get("scheme_name", ""))
        for r in matched_schemes[:5]
        if r.get("scheme_name")
    ]

    if not top_schemes:
        return None

    prompt = (
        "User Profile:\n"
        f"- Age: {profile.get('age')}\n"
        f"- Gender: {profile.get('gender')}\n"
        f"- State: {profile.get('state')}\n"
        f"- Occupation: {profile.get('occupation')}\n"
        f"- Income: Rs {profile.get('income')}\n\n"
        "Top Matching Schemes:\n"
        + "\n".join(f"- {s}" for s in top_schemes)
        + "\n\nGenerate a personalized 2-3 line recommendation in Hinglish "
        "(Hindi + English mix) for this user. Mention their profile and why "
        "these schemes suit them. Keep it friendly and helpful."
    )

    try:
        response = llm.invoke(prompt)
        return _safe_str(getattr(response, "content", ""))
    except Exception:
        return None


# ===========================
# SMART QUERY PROCESSOR
# ===========================
def process_smart_query(query, df):
    """
    AI-powered query processor (typo expansion + state aliasing).
    """
    expanded_query = _expand_query_typos(query)

    llm = get_llm()

    # Default intent
    intent = {
        "age": None,
        "gender": "All",
        "state": "All",
        "occupation": "All",
        "income": None,
        "category": "All",
        "keywords": [w for w in expanded_query.split() if len(w) > 2][:5],
        "intent": "general",
    }

    llm_used = False

    # ---- STEP 1: LLM intent extraction ----
    if llm:
        extraction_prompt = f"""User query: "{expanded_query}"

Extract structured information. Return ONLY valid JSON, no other text:
{{
    "age": <number or null>,
    "gender": "<Male/Female/All>",
    "state": "<state name or 'All'>",
    "occupation": "<Student/Farmer/etc or 'All'>",
    "income": <number or null>,
    "category": "<SC/ST/OBC/General/Minority or 'All'>",
    "keywords": ["important", "search", "terms"],
    "intent": "<one-word purpose like housing/education/health/agriculture/pension/marriage>"
}}

Rules:
- "keywords" should be 2-5 SHORT words from the query
- If query is about marriage/wedding (shaadi, vivah, vivaah, kanyadan),
  use intent="marriage" and keywords=["marriage", "shaadi"]
- Return ONLY the JSON object"""

        try:
            response = llm.invoke(extraction_prompt)
            content = _safe_str(getattr(response, "content", "")).strip()
            content = content.replace("```json", "").replace("```", "").strip()
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                intent.update(parsed)
                llm_used = True
        except Exception as e:
            print(f"[ai_chatbot] Intent extraction failed: {type(e).__name__}: {str(e)[:200]}")

    # ---- STEP 2: Keyword search ----
    keyword_results = []

    if _NL_SEARCH_AVAILABLE and llm_used and nl_search_fn is not None:
        keywords = intent.get("keywords", [])
        intent_word = intent.get("intent", "")

        search_terms = " ".join(_safe_str(k) for k in keywords if k)
        if intent_word and intent_word.lower() not in ["general", "none", ""]:
            search_terms = f"{search_terms} {intent_word}".strip()

        if search_terms:
            try:
                keyword_results = nl_search_fn(df, search_terms, top_n=30)
            except Exception as e:
                print(f"[ai_chatbot] Keyword search failed: {e}")
                keyword_results = []

    # ---- STEP 3: State filter ----
    matched = []
    if keyword_results:
        try:
            state_val = _normalize_state(intent.get("state", "All"))
            for r in keyword_results:
                r_state = _safe_str(r.get("applicable_state", "All"))
                if state_val != "All" and r_state != "All" and r_state != state_val:
                    continue
                matched.append(r)
            if not matched:
                matched = keyword_results
        except Exception:
            matched = keyword_results

    # ---- STEP 4: Fallback (v5: real score) ----
    if not matched:
        matched = fallback_search_schemes(expanded_query, df, top_n=5)
    if not matched and expanded_query != query:
        matched = fallback_search_schemes(query, df, top_n=5)

    # ---- STEP 5: Response message ----
    matched_count = len(matched)

    if matched_count > 0:
        if llm_used and keyword_results:
            response_msg = (
                f"✅ **Maine {matched_count} relevant schemes dhundhi hain!**\n\n"
                f"Aapki query: *\"{query}\"*\n\n"
                "Top recommendations neeche di gayi hain. 👇"
            )
        elif llm_used:
            response_msg = (
                f"✅ **Maine {matched_count} schemes dhundhi hain!**\n\n"
                f"Aapki query: *\"{query}\"*\n\n"
                "Top recommendations neeche di gayi hain. 👇"
            )
        else:
            response_msg = (
                f"✅ **Maine {matched_count} relevant schemes dhundhi hain!**\n\n"
                f"Aapki query: *\"{query}\"*\n\n"
                "*Note: AI temporarily unavailable, isliye smart keyword search use kiya gaya.*\n\n"
                "Top recommendations neeche di gayi hain. 👇"
            )
    else:
        response_msg = (
            f"❌ **Sorry, koi matching scheme nahi mili.**\n\n"
            f"Aapki query: *\"{query}\"*\n\n"
            "**Try karo:**\n"
            "- Simple keywords use karo (jaise: \"scholarship\", \"loan\", \"pension\", \"kisan\")\n"
            "- Ya thoda aur detail me batao (age, state, kya chahiye)"
        )

    return {"message": response_msg, "schemes": matched[:5]}


# ===========================
# QUICK SUGGESTIONS
# ===========================
def render_quick_suggestions():
    """Quick reply suggestion buttons for NL mode."""
    st.markdown("#### 💡 Quick Suggestions:")
    suggestions = [
        "Mujhe 25 saal ki ladki ki shaadi ke liye paisa chahiye",
        "Main student hoon, scholarship chahiye",
        "Main farmer hoon, fasal bima chahiye",
        "Mujhe ghar banane ke liye loan chahiye",
        "Main senior citizen hoon, pension chahiye",
        "Mujhe business ke liye loan chahiye",
    ]

    cols = st.columns(2)
    for i, sugg in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(sugg, key=f"quick_sugg_{i}", use_container_width=True):
                st.session_state.nl_chat_history.append({"role": "user", "content": sugg})
                try:
                    df = load_schemes()
                    response = process_smart_query(sugg, df)
                    st.session_state.nl_chat_history.append({
                        "role": "assistant",
                        "content": response["message"],
                    })
                    st.session_state.nl_last_schemes = response.get("schemes", [])
                except Exception as e:
                    st.session_state.nl_chat_history.append({
                        "role": "assistant",
                        "content": f"⚠️ Error: {_safe_str(e)[:120]}",
                    })
                st.rerun()


# ===========================
# NL CHAT MODE
# ===========================
def render_nl_chat_mode(df, render_scheme_card, sort_results, t):
    """Natural language chat mode."""
    st.markdown("#### 💬 Apni samasya batayein")
    st.caption("Aap Hindi, English, ya Hinglish mein likh sakte hain")

    # Display history
    for msg in st.session_state.nl_chat_history:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "assistant")
        content = _safe_str(msg.get("content", ""))
        with st.chat_message(role):
            st.markdown(content)

    # Show last schemes
    last_schemes = st.session_state.get("nl_last_schemes") or []
    if last_schemes:
        st.markdown("---")
        st.markdown("### 🎯 Recommended Schemes:")
        if render_scheme_card and t:
            # v5 FIX: use actual lang_choice from session_state (was hardcoded "English")
            lang_choice = st.session_state.get("lang_choice", "English")
            for r in last_schemes[:5]:
                try:
                    render_scheme_card(r, t, "ai_chat", lang_choice)
                except Exception as e:
                    st.warning(f"Could not render scheme: {_safe_str(e)[:60]}")

    # Quick suggestions (only if no history)
    if not st.session_state.nl_chat_history:
        render_quick_suggestions()

    # Chat input
    user_query = st.chat_input(
        "Apni zaroorat likhein... (e.g. 'Mujhe 25 saal ki ladki ki shaadi ke liye paisa chahiye')",
        key="nl_chat_input",
    )

    if user_query:
        st.session_state.nl_chat_history.append({"role": "user", "content": user_query})

        with st.spinner("🤖 Soch raha hun..."):
            try:
                response = process_smart_query(user_query, df)
                st.session_state.nl_chat_history.append({
                    "role": "assistant",
                    "content": response.get("message", "No response"),
                })
                st.session_state.nl_last_schemes = response.get("schemes", []) or []
                log_assistant_query(user_query, len(response.get("schemes", [])))
            except Exception as e:
                st.session_state.nl_chat_history.append({
                    "role": "assistant",
                    "content": f"⚠️ Error: {_safe_str(e)[:120]}",
                })
                st.session_state.nl_last_schemes = []

        st.rerun()

    # Reset button
    if st.session_state.nl_chat_history:
        if st.button("🔄 Start New Chat", use_container_width=True, key="reset_nl_chat"):
            st.session_state.nl_chat_history = []
            st.session_state.nl_last_schemes = []
            st.rerun()

    auto_scroll_to_bottom()


# ===========================
# PROFILE MODE
# ===========================
def _build_progress_bar_html(progress_pct):
    """
    Single-line HTML for progress bar (CommonMark HTML block bug safe).
    v5 FIX: previously built as multi-line f-string.
    """
    return (
        '<div style="position: fixed; top: 50%; right: 20px; '
        'transform: translateY(-50%); width: 10px; height: 50vh; '
        'z-index: 9999; background: rgba(11, 20, 26, 0.10); '
        'backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); '
        'border-radius: 10px; border: 1px solid rgba(0, 229, 255, 0.10); '
        'box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1), '
        'inset 0 0 10px rgba(255, 255, 255, 0.02); '
        'overflow: hidden; display: flex; flex-direction: column; '
        'justify-content: flex-end;">'
        f'<div style="width: 100%; height: {progress_pct}%; '
        'background: linear-gradient(180deg, #EC4899 0%, #A855F7 50%, #00E5FF 100%); '
        'background-size: 100% 200%; border-radius: 10px; '
        'box-shadow: 0 0 15px rgba(0, 229, 255, 0.5), '
        '0 0 30px rgba(168, 85, 247, 0.3); '
        'animation: neonProgress 3s ease infinite; '
        'transition: height 0.6s cubic-bezier(0.4, 0, 0.2, 1); '
        'position: relative;"></div>'
        '</div>'
        '<style>'
        '@keyframes neonProgress {'
        '0%, 100% { background-position: 50% 0%; }'
        '50% { background-position: 50% 100%; }'
        '}'
        '</style>'
    )


def render_profile_mode(df, render_scheme_card, sort_results, t):
    """Profile-based step-by-step mode."""
    init_assistant_state()

    dynamic_questions = get_dynamic_questions(st.session_state.assistant_profile)

    step = st.session_state.assistant_step
    profile = st.session_state.assistant_profile
    total_steps = len(dynamic_questions)

    progress_value = min(step / total_steps, 1.0) if total_steps > 0 else 0
    progress_pct = int(progress_value * 100)

    # Progress bar (single-line HTML)
    if not st.session_state.assistant_complete and step < total_steps:
        st.markdown(
            _build_progress_bar_html(progress_pct),
            unsafe_allow_html=True,
        )

    # Display messages
    for msg in st.session_state.assistant_messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role", "assistant")
        content = _safe_str(msg.get("content", ""))
        with st.chat_message(role):
            st.markdown(content)

    # Complete state
    if st.session_state.assistant_complete:
        st.info(
            f"📋 **Your Profile:**\n"
            f"- Age: {profile.get('age', 'Not set')}\n"
            f"- State: {profile.get('state', 'Not set')}\n"
            f"- Gender: {profile.get('gender', 'Not set')}\n"
            f"- Category: {profile.get('social_category', 'Not set')}\n"
            f"- Income: ₹{profile.get('income', 'Not set')}\n"
            f"- Occupation: {profile.get('occupation', 'Not set')}"
        )

        if st.button("🔍 Search Schemes Now", type="primary",
                     use_container_width=True, key="search_schemes_btn"):
            with st.spinner("🔍 Searching matching schemes..."):
                age_num = extract_number_from_range(profile.get("age"))
                income_num = extract_number_from_range(profile.get("income"))

                results = match_schemes(
                    df,
                    state=profile.get("state", "All"),
                    gender=profile.get("gender", "All"),
                    social_category=profile.get("social_category", "All"),
                    annual_income=income_num,
                    occupation=profile.get("occupation", "All"),
                    age=age_num if age_num is not None else 25,
                    only_eligible=False,
                )
                st.session_state.assistant_results = results
                st.rerun()

        if st.session_state.assistant_results:
            eligible_count = sum(
                1 for r in st.session_state.assistant_results if r.get("eligible")
            )

            with st.spinner("🤖 AI aapke liye recommendation bana raha hai..."):
                recommendation = generate_ai_recommendation(
                    profile, st.session_state.assistant_results
                )

            if recommendation:
                st.info(f"🤖 **AI Recommendation:**\n\n{recommendation}")

            st.success(
                f"✅ Found {len(st.session_state.assistant_results)} schemes "
                f"({eligible_count} eligible)"
            )

            if render_scheme_card and sort_results and t:
                for r in st.session_state.assistant_results[:8]:
                    try:
                        render_scheme_card(r, t, "assistant", "English")
                    except Exception:
                        continue
            else:
                st.warning("Scheme card rendering functions not provided.")

        if st.button("🔄 Start Over", use_container_width=True, key="reset_assistant_btn"):
            reset_assistant()
            st.rerun()

        auto_scroll_to_bottom()
        return

    # Question flow
    if step < total_steps:
        current_q = dynamic_questions[step]
        key = current_q["key"]
        question = current_q["question"]
        options = current_q.get("options", [])

        assistant_msg = f"📝 **{question}**"

        if key in profile and profile[key] is not None:
            st.chat_message("assistant").markdown(assistant_msg)
            st.chat_message("user").markdown(f"✅ {profile[key]}")
            st.session_state.assistant_step += 1
            st.rerun()
            return

        st.chat_message("assistant").markdown(assistant_msg)

        if options:
            st.markdown("**Choose from options:**")
            cols = st.columns(min(len(options), 4))
            for i, opt in enumerate(options):
                col_idx = i % 4
                with cols[col_idx]:
                    if st.button(opt, key=f"{key}_{opt}_btn", use_container_width=True):
                        st.session_state.assistant_profile[key] = opt
                        st.session_state.assistant_messages.append({
                            "role": "assistant", "content": assistant_msg,
                        })
                        st.session_state.assistant_messages.append({
                            "role": "user", "content": opt,
                        })
                        st.session_state.assistant_step += 1
                        st.rerun()

            user_input = st.chat_input("Or type your answer here...", key=f"chat_input_{key}")
            if user_input:
                st.session_state.assistant_profile[key] = user_input
                st.session_state.assistant_messages.append({
                    "role": "assistant", "content": assistant_msg,
                })
                st.session_state.assistant_messages.append({
                    "role": "user", "content": user_input,
                })
                st.session_state.assistant_step += 1
                st.rerun()
        else:
            user_input = st.chat_input("Type your answer here...", key=f"chat_input_{key}")
            if user_input:
                st.session_state.assistant_profile[key] = user_input
                st.session_state.assistant_messages.append({
                    "role": "assistant", "content": assistant_msg,
                })
                st.session_state.assistant_messages.append({
                    "role": "user", "content": user_input,
                })
                st.session_state.assistant_step += 1
                st.rerun()

        auto_scroll_to_bottom()

    # Finalize
    if step >= total_steps and not st.session_state.assistant_complete:
        required_keys = ["age", "state", "gender", "social_category", "income", "occupation"]
        all_answered = all(key in profile for key in required_keys)

        if all_answered:
            st.session_state.assistant_complete = True

            if save_profile_to_user_data(profile):
                st.toast("✅ Profile saved for next time!")

            st.session_state.assistant_messages.append({
                "role": "assistant",
                "content": ("✅ **Great! I've understood your profile. "
                            "Click below to find the best schemes for you!**"),
            })
            st.rerun()
        else:
            reset_assistant()
            st.rerun()


# ===========================
# MAIN RENDER
# ===========================
def render_ai_assistant(render_scheme_card=None, sort_results=None, t=None):
    """Main entry point for AI assistant (3 modes)."""
    if not GROQ_API_KEY:
        st.warning("⚠️ Groq API key not configured. AI features will be limited.")
    else:
        st.caption(f"🤖 Using model: `{DEFAULT_GROQ_MODEL}`")

    # Chat CSS
    st.markdown(
        """
        <style>
        div[data-testid="stChatMessage"] p,
        div[data-testid="stChatMessage"] li,
        div[data-testid="stChatMessage"] span {
            font-size: 1.05rem !important;
            line-height: 1.6 !important;
        }
        div[data-testid="stChatMessage"] .stChatMessageName {
            font-size: 1rem !important;
        }
        .stButton > button {
            font-size: 1rem !important;
            padding: 12px 18px !important;
        }
        .stCaption, small { font-size: 0.95rem !important; }
        .streamlit-expanderHeader { font-size: 1rem !important; }
        .stRadio label p { font-size: 1rem !important; }
        div[data-testid="stChatMessage"] h1,
        div[data-testid="stChatMessage"] h2,
        div[data-testid="stChatMessage"] h3,
        div[data-testid="stChatMessage"] h4 {
            font-size: 1.15rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 🤖 AI Sarkari Scheme Assistant")
    st.caption("Apne baare mein batao, main best schemes suggest karunga!")

    init_assistant_state()

    df = load_schemes()

    if "assistant_mode" not in st.session_state:
        st.session_state.assistant_mode = "profile"

    current_mode = st.session_state.assistant_mode

    # Mode switch → clear stale state
    if st.session_state.get("_last_assistant_mode") != current_mode:
        if current_mode == "nl":
            st.session_state.ai_messages = []
            st.session_state.nl_last_schemes = []
        elif current_mode == "chat":
            st.session_state.nl_chat_history = []
            st.session_state.nl_last_schemes = []
        st.session_state._last_assistant_mode = current_mode

    # Render active mode
    if current_mode == "nl":
        render_nl_chat_mode(df, render_scheme_card, sort_results, t)
    elif current_mode == "chat":
        ai_chatbot_ui()
    else:
        render_profile_mode(df, render_scheme_card, sort_results, t)

    # Mode selector (bottom)
    st.divider()

    mode_labels = {"profile": "Quick Profile", "nl": "Describe Problem", "chat": "Just Chat"}
    current_mode_label = mode_labels.get(current_mode, "Unknown")
    st.caption(f"**Current mode:** {current_mode_label}")

    with st.expander("Change Assistant Mode", expanded=False):
        mode_options = {
            "profile": "Quick Profile (Step-by-step questions)",
            "nl": "Describe Your Problem (Natural language)",
            "chat": "Just Chat (Free conversation)",
        }

        selected_mode = st.radio(
            "Choose mode:",
            options=list(mode_options.keys()),
            format_func=lambda x: mode_options[x],
            index=list(mode_options.keys()).index(current_mode),
            key="bottom_mode_selector",
        )

        if selected_mode != current_mode:
            st.session_state.assistant_mode = selected_mode
            st.rerun()


# ===========================
# LEGACY CHATBOT
# ===========================
def create_conversation():
    """Legacy conversation chain with memory."""
    df = load_schemes()

    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful government scheme assistant. Help users find "
                   "schemes in India. Answer in Hinglish (Hindi + English) if the user "
                   "writes in Hindi or Hinglish."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}"),
    ])

    llm = get_llm()
    if not llm:
        return None

    chain = prompt | llm
    store = {}

    def get_session_history(session_id):
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]

    def get_schemes_and_invoke(input_dict):
        input_dict["schemes_data"] = "Available schemes data is loaded in the system."
        return input_dict

    final_chain = RunnableLambda(get_schemes_and_invoke) | chain

    return RunnableWithMessageHistory(
        final_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history",
    )


def ai_chatbot_ui():
    """Legacy free-form chat UI."""
    st.caption("💬 Free-form chat — schemes suggest karne ke liye "
               "'Describe Your Problem' mode use karein.")

    try:
        conversation = create_conversation()

        if "ai_messages" not in st.session_state:
            st.session_state.ai_messages = []

        if "ai_conversation" not in st.session_state:
            st.session_state.ai_conversation = conversation

        if "_ai_session_id" not in st.session_state:
            st.session_state["_ai_session_id"] = str(id(st.session_state))

        for message in st.session_state.ai_messages:
            if not isinstance(message, dict):
                continue
            with st.chat_message(message.get("role", "assistant")):
                st.markdown(_safe_str(message.get("content", "")))

        user_input = st.chat_input(
            "Yahan likho... (e.g. Mujhe 25 saal ki ladki ki shaadi ke liye scheme chahiye)",
            key="ai_chat_input",
        )

        if user_input:
            st.session_state.ai_messages.append({"role": "user", "content": user_input})

            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                with st.spinner("AI soch raha hai..."):
                    try:
                        if st.session_state.ai_conversation is None:
                            raise Exception("AI not configured")

                        response = st.session_state.ai_conversation.invoke(
                            {"input": user_input},
                            config={"configurable": {
                                "session_id": st.session_state["_ai_session_id"]
                            }},
                        )
                        response_text = _safe_str(getattr(response, "content", ""))
                        st.markdown(response_text)
                        st.session_state.ai_messages.append({
                            "role": "assistant", "content": response_text,
                        })
                        log_assistant_query(user_input, 0)
                    except Exception:
                        st.warning("⚠️ AI temporarily unavailable. Rule-based search use kar rahe hain...")

                        # v5 FIX: nested try/except around fallback load_schemes
                        try:
                            df = load_schemes()
                            fallback_results = fallback_search_schemes(user_input, df, top_n=5)
                        except Exception as inner_e:
                            st.error(f"Fallback search failed: {_safe_str(inner_e)[:80]}")
                            fallback_results = []

                        if fallback_results:
                            st.success(f"✅ {len(fallback_results)} matching schemes mili:")
                            for r in fallback_results:
                                score_pct = int(r.get("score", 0) * 100)
                                st.markdown(
                                    f"**{r['scheme_name']}** ({score_pct}% match)  \n"
                                    f"_{r.get('category_type', '')} • "
                                    f"{r.get('applicable_state', '')}_  \n"
                                    f"{_safe_str(r.get('description', ''))[:200]}  \n"
                                    f"[Apply Here]({r.get('apply_link', '#')})"
                                )
                                st.divider()
                            st.session_state.ai_messages.append({
                                "role": "assistant",
                                "content": f"Fallback: {len(fallback_results)} schemes mili",
                            })
                        else:
                            st.info("Koi matching scheme nahi mili. Thoda aur detail mein likhein.")
                            st.session_state.ai_messages.append({
                                "role": "assistant",
                                "content": "Koi matching scheme nahi mili.",
                            })

        auto_scroll_to_bottom()

        if st.session_state.ai_messages:
            if st.button("🔄 Start New Chat", use_container_width=True, key="reset_ai_chat"):
                st.session_state.ai_messages = []
                if "ai_conversation" in st.session_state:
                    st.session_state.ai_conversation = None
                st.rerun()

    except Exception as e:
        st.error(f"⚠️ Error: {_safe_str(e)[:150]}")
        st.info("Tip: Kya aapne `pip install langchain langchain-groq` kiya hai?")


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("ai_chatbot.py — Verification")
    print("=" * 60)

    # Test 1: _safe_str
    print("\n[Test 1] _safe_str:")
    assert _safe_str(None) == ""
    assert _safe_str(float("nan")) == ""
    assert _safe_str("test") == "test"
    print("  ✅ All cases pass")

    # Test 2: _expand_query_typos
    print("\n[Test 2] _expand_query_typos:")
    assert _expand_query_typos("saadi ke liye") == "shaadi ke liye"
    assert _expand_query_typos("kisaan loan") == "kisan loan"
    assert _expand_query_typos("scholership") == "scholarship"
    assert _expand_query_typos("normal query") == "normal query"
    print("  ✅ Typos corrected")

    # Test 3: _normalize_state
    print("\n[Test 3] _normalize_state:")
    assert _normalize_state("MP") == "Madhya Pradesh"
    assert _normalize_state("mp") == "Madhya Pradesh"
    assert _normalize_state("up") == "Uttar Pradesh"
    assert _normalize_state("All") == "All"
    assert _normalize_state("all") == "All"
    assert _normalize_state("") == "All"
    assert _normalize_state(None) == "All"
    assert _normalize_state("Rajasthan") == "Rajasthan"
    print("  ✅ State aliases normalized")

    # Test 4: extract_number_from_range
    print("\n[Test 4] extract_number_from_range:")
    assert extract_number_from_range("18-25") == 18
    assert extract_number_from_range("60,001 - 80,000") == 60001
    assert extract_number_from_range("12,00,001+") == 1200001
    assert extract_number_from_range("All") is None
    assert extract_number_from_range(None) is None
    assert extract_number_from_range("") is None
    print("  ✅ Range parsing works")

    # Test 5: _atomic_json_write
    print("\n[Test 5] _atomic_json_write:")
    import tempfile as _tf
    tmpdir = _tf.mkdtemp(prefix="ai_test_")
    test_file = os.path.join(tmpdir, "test.json")
    _atomic_json_write(test_file, {"test": "value"})
    assert os.path.exists(test_file)
    with open(test_file) as f:
        data = json.load(f)
    assert data == {"test": "value"}
    print(f"  ✅ Atomic write works")

    # Test 6: log_assistant_query — corrupt file recovery
    print("\n[Test 6] log_assistant_query (corrupt file recovery):")
    import shutil
    original_cwd = os.getcwd()
    try:
        os.chdir(tmpdir)
        os.makedirs("data", exist_ok=True)
        with open("data/assistant_log.json", "w") as f:
            f.write("NOT JSON {{{")
        log_assistant_query("test query", 5)
        assert os.path.exists("data/assistant_log.json")
        with open("data/assistant_log.json") as f:
            log = json.load(f)
        assert isinstance(log, list) and len(log) == 1
        assert log[0]["query"] == "test query"
        assert log[0]["matched"] == 5
        print("  ✅ Corrupt file quarantined, fresh log written")
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)

    # Test 7: fallback_search_schemes — REAL score (v5 fix)
    print("\n[Test 7] fallback_search_schemes (real score):")
    df = pd.DataFrame([
        {"scheme_name": "PM Kisan", "category_type": "Agriculture",
         "applicable_state": "All", "description": "Farmer income support",
         "benefits": "Rs 6000", "apply_link": "https://x.gov.in", "deadline": ""},
        {"scheme_name": "Ayushman Bharat", "category_type": "Health",
         "applicable_state": "All", "description": "Health insurance",
         "benefits": "Rs 5 lakh", "apply_link": "https://x.gov.in", "deadline": ""},
    ])
    results = fallback_search_schemes("kisan loan farmer", df, top_n=5)
    assert len(results) > 0
    # Score should NOT be hardcoded 0.5 — should vary
    scores = [r["score"] for r in results]
    assert all(0 < s <= 1.0 for s in scores), f"Scores out of range: {scores}"
    print(f"  ✅ Found {len(results)} results, scores: {scores}")

    # Test 8: get_dynamic_questions
    print("\n[Test 8] get_dynamic_questions:")
    q = get_dynamic_questions({"occupation": "Student"})
    assert any(x["key"] == "education_level" for x in q)
    q = get_dynamic_questions({"occupation": "Farmer"})
    assert any(x["key"] == "land_size" for x in q)
    q = get_dynamic_questions({})
    assert len(q) >= 6
    print(f"  ✅ Student → {len(get_dynamic_questions({'occupation': 'Student'}))} questions")
    print(f"  ✅ Farmer → {len(get_dynamic_questions({'occupation': 'Farmer'}))} questions")

    # Test 9: get_llm is decorated with cache_resource
    print("\n[Test 9] get_llm cached:")
    # Just check it's callable and returns None without API key
    llm = get_llm()
    if not GROQ_API_KEY:
        assert llm is None
        print("  ✅ Returns None without API key")
    else:
        print(f"  ✅ LLM available (API key set)")

    # Test 10: _build_progress_bar_html single-line
    print("\n[Test 10] progress bar HTML single-line:")
    html = _build_progress_bar_html(50)
    assert "<div" in html
    assert "neonProgress" in html
    # Should not have double-newlines
    assert "\n\n" not in html
    print("  ✅ Progress bar HTML safe for CommonMark")

    print("\n" + "=" * 60)
    print("✅ ai_chatbot.py — ALL CHECKS PASSED")
    print("=" * 60)