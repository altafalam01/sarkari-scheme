"""
voice_assistant.py - Voice Assistant v14 FINAL (st.audio_input + auto-retry)
Layout: Top heading → Filters → Results → Fixed bottom bar
"""

import io
import os
import re
import time
import asyncio
import threading
import tempfile
import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import pandas as pd

# --- Language Codes ---
_GTTS_LANG_CODES = {"English": "en", "हिंदी": "hi", "मराठी": "mr", "தமிழ்": "ta"}

_GTTS_AVAILABLE = True
try:
    from gtts import gTTS
except Exception:
    _GTTS_AVAILABLE = False

_EDGE_TTS_AVAILABLE = True
try:
    import edge_tts
except Exception:
    _EDGE_TTS_AVAILABLE = False

_SR_AVAILABLE = True
try:
    import speech_recognition as sr
except Exception:
    _SR_AVAILABLE = False

_NOISE_REDUCE_AVAILABLE = True
try:
    import noisereduce as nr
    from scipy.io import wavfile
except Exception:
    _NOISE_REDUCE_AVAILABLE = False


# ===========================
# CACHED LLM
# ===========================
@st.cache_resource(show_spinner=False)
def _get_cached_llm():
    try:
        from langchain_groq import ChatGroq
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        return ChatGroq(
            temperature=0.7,
            groq_api_key=api_key,
            model_name="llama-3.3-70b-versatile"
        )
    except Exception:
        return None


# ===========================
# AUTO-SCROLL
# ===========================
def _scroll_to_results():
    components.html("""
    <script>
        setTimeout(function() {
            var parentDoc = window.parent.document;
            var resultsHeader = parentDoc.querySelector('.results-header');
            if (resultsHeader) {
                resultsHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 600);
    </script>
    """, height=0)


# ===========================
# EDGE TTS
# ===========================
def _generate_edge_audio_with_rate(text: str, voice: str, rate_str: str, timeout: int = 30):
    result = {"data": None, "error": None}
    def _worker():
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            async def _gen():
                comm = edge_tts.Communicate(text, voice, rate=rate_str)
                buf = io.BytesIO()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                buf.seek(0)
                return buf.read()
            result["data"] = loop.run_until_complete(_gen())
        except Exception as e:
            result["error"] = e
        finally:
            if loop is not None:
                try:
                    loop.close()
                except Exception:
                    pass
    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout)
    if thread.is_alive():
        return None, TimeoutError(f"Edge TTS {timeout}s timeout")
    return result["data"], result["error"]


# ===========================
# GENERATE AUDIO
# ===========================
def generate_audio_bytes(text: str, lang_choice: str = "English",
                          speed: float = 1.0, voice_gender: str = "Female"):
    if not text or not text.strip():
        return None, "Empty text"
    text = re.sub(r'[\U0001F000-\U0001FAFF\u2600-\u27BF]', '', text)
    text = re.sub(r'[★☆⭐📅📊📋📝🎯✅❌⚠️🔥🚨•●○■□▪▫→←↑↓↔“”"\'`‘’]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if lang_choice in ["हिंदी", "मराठी"]:
        text = re.sub(r'[^\u0900-\u097F\w\s,.\-?!।]', '', text)
    elif lang_choice == "தமிழ்":
        text = re.sub(r'[^\u0B80-\u0BFF\w\s,.\-?!।]', '', text)
    if not text:
        return None, "No readable text"
    if len(text) > 1500:
        text = text[:1497] + "..."
    if _EDGE_TTS_AVAILABLE:
        voice_map = {
            "English": {"Female": "en-IN-NeerjaNeural", "Male": "en-IN-PrabhatNeural"},
            "हिंदी": {"Female": "hi-IN-SwaraNeural", "Male": "hi-IN-MadhurNeural"},
            "मराठी": {"Female": "mr-IN-AarohiNeural", "Male": "mr-IN-ManoharNeural"},
            "தமிழ்": {"Female": "ta-IN-PallaviNeural", "Male": "ta-IN-ValluvarNeural"},
        }
        lang_voices = voice_map.get(lang_choice, voice_map["English"])
        voice = lang_voices.get(voice_gender, lang_voices["Female"])
        rate_pct = int((speed - 1.0) * 100)
        rate_str = f"{rate_pct:+d}%"
        audio_bytes, error = _generate_edge_audio_with_rate(text, voice, rate_str, timeout=30)
        if not error and audio_bytes and len(audio_bytes) > 0:
            return audio_bytes, None
    if _GTTS_AVAILABLE:
        lang_code = _GTTS_LANG_CODES.get(lang_choice, "en")
        tlds_to_try = ["co.in", "com"] if lang_choice in ["हिंदी", "मराठी", "தமிழ்"] else ["co.in", "com"]
        for tld in tlds_to_try:
            try:
                tts = gTTS(text=text[:500], lang=lang_code, tld=tld, slow=False)
                buf = io.BytesIO()
                tts.write_to_fp(buf)
                buf.seek(0)
                audio_bytes = buf.read()
                if audio_bytes and len(audio_bytes) > 0:
                    return audio_bytes, None
            except Exception:
                continue
    return None, "Audio generate nahi ho paya"


def speak_text(text: str, lang_choice: str = "English", speed: float = 1.0,
                voice_gender: str = "Female") -> None:
    audio_bytes, error = generate_audio_bytes(text, lang_choice, speed, voice_gender)
    if error:
        st.error(error)
        return
    if audio_bytes:
        st.audio(audio_bytes, format="audio/mp3", autoplay=True)


def build_scheme_text_for_reading(scheme_data: dict, lang_choice: str = "English") -> str:
    field_labels = {
        "English": {"scheme": "Scheme", "category": "Category", "state": "Applicable State",
                    "description": "What is it", "benefits": "Benefits"},
        "हिंदी": {"scheme": "योजना", "category": "श्रेणी", "state": "लागू राज्य",
                  "description": "यह क्या है", "benefits": "लाभ"},
        "मराठी": {"scheme": "योजना", "category": "श्रेणी", "state": "लागू राज्य",
                  "description": "हे काय आहे", "benefits": "लाभ"},
        "தமிழ்": {"scheme": "திட்டம்", "category": "வகை", "state": "பொருந்தும் மாநிலம்",
                  "description": "இது என்ன", "benefits": "நன்மைகள்"},
    }
    labels = field_labels.get(lang_choice, field_labels["English"])
    parts = []
    if scheme_data.get("scheme_name"):
        parts.append(f"{labels['scheme']}: {scheme_data['scheme_name']}")
    if scheme_data.get("category_type"):
        parts.append(f"{labels['category']}: {scheme_data['category_type']}")
    if scheme_data.get("applicable_state") and scheme_data["applicable_state"] != "All":
        parts.append(f"{labels['state']}: {scheme_data['applicable_state']}")
    if scheme_data.get("description"):
        parts.append(f"{labels['description']}: {scheme_data['description']}")
    if scheme_data.get("benefits"):
        parts.append(f"{labels['benefits']}: {scheme_data['benefits']}")
    return re.sub(r'\s+', ' ', ". ".join(parts))


def read_scheme_details(scheme_data: dict, lang_choice: str = "English"):
    text = build_scheme_text_for_reading(scheme_data, lang_choice)
    speed = st.session_state.get("voice_speed", 1.0)
    gender = st.session_state.get("voice_gender", "Female")
    speak_text(text, lang_choice, speed, gender)


# ===========================
# NOISE CANCELLATION
# ===========================
def reduce_noise(audio_bytes: bytes) -> bytes:
    if not _NOISE_REDUCE_AVAILABLE:
        return audio_bytes
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in_path = tmp_in.name
        sample_rate, data = wavfile.read(tmp_in_path)
        if len(data.shape) > 1:
            data = data.mean(axis=1).astype(data.dtype)
        reduced_noise = nr.reduce_noise(y=data, sr=sample_rate, stationary=False)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_out:
            tmp_out_path = tmp_out.name
        wavfile.write(tmp_out_path, sample_rate, reduced_noise.astype(np.int16))
        with open(tmp_out_path, "rb") as f:
            cleaned_bytes = f.read()
        try:
            os.remove(tmp_in_path)
            os.remove(tmp_out_path)
        except OSError:
            pass
        return cleaned_bytes
    except Exception:
        return audio_bytes


# ===========================
# TRANSCRIPTION
# ===========================
def _transcribe_audio(audio_bytes: bytes, lang_choice: str, apply_noise_reduction: bool = False) -> str:
    if not _SR_AVAILABLE:
        raise RuntimeError("Voice recognition not available.")
    if apply_noise_reduction and _NOISE_REDUCE_AVAILABLE:
        try:
            audio_bytes = reduce_noise(audio_bytes)
        except Exception:
            pass
    recognizer = sr.Recognizer()
    sr_lang = {"English": "en-IN", "हिंदी": "hi-IN", "मराठी": "mr-IN", "தமிழ்": "ta-IN"}.get(lang_choice, "en-IN")
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with sr.AudioFile(tmp_path) as source:
            audio_data = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio_data, language=sr_lang)
        except sr.UnknownValueError:
            raise RuntimeError("Awaaz samajh nahi aayi. Kripya saaf bolein.")
        except sr.RequestError as e:
            raise RuntimeError(f"Speech recognition error: {e}")
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass


# ===========================
# FOLLOW-UP QUESTIONS
# ===========================
def generate_follow_up_questions(transcript: str, lang_choice: str = "English"):
    try:
        llm = _get_cached_llm()
        if llm is None:
            return []
        if lang_choice == "हिंदी":
            prompt = f"""User ka sawaal: "{transcript}"

Sarkari yojana ke liye 3 short follow-up questions banao (Hindi mein, Roman script).
Har question alag line par, numbering ke saath (1., 2., 3.).
Sirf questions return karo."""
        else:
            prompt = f"""User's question: "{transcript}"

Generate 3 short follow-up questions for a government scheme search.
Each on a new line, numbered (1., 2., 3.).
Return ONLY questions."""
        response = llm.invoke(prompt)
        content = response.content.strip()
        questions = []
        for line in content.split("\n"):
            line = line.strip()
            line = re.sub(r'^\d+\.\s*', '', line)
            if line and len(line) > 10 and len(line) < 200:
                questions.append(line)
        return questions[:3]
    except Exception:
        return []


# ===========================
# AI RE-RANKING
# ===========================
def _ai_rerank_schemes(transcript: str, results: list, lang_choice: str = "English"):
    if not results or len(results) < 2:
        return results
    try:
        llm = _get_cached_llm()
        if llm is None:
            return results
        top_results = results[:25]
        scheme_list = "\n".join([
            f"{i+1}. {r.get('scheme_name', '')} | {r.get('category_type', '')} | {str(r.get('description', ''))[:80]}"
            for i, r in enumerate(top_results)
        ])
        prompt = f"""User query: "{transcript}"

Available schemes:
{scheme_list}

Task: Identify the TOP 5 most relevant schemes for this user's query.
Consider the user's INTENT, not just keyword matches.

Return ONLY the numbers (1-25) of top 5 most relevant schemes, comma-separated.
Example output: 3, 7, 12, 1, 15

If NONE are relevant, return: NONE"""
        response = llm.invoke(prompt)
        content = response.content.strip()
        if "NONE" in content.upper():
            return results
        numbers = []
        for num_str in re.findall(r'\d+', content):
            try:
                num = int(num_str)
                if 1 <= num <= len(top_results):
                    numbers.append(num - 1)
            except ValueError:
                continue
        if not numbers:
            return results
        ai_selected = []
        for i in numbers:
            if i < len(top_results):
                ai_selected.append(top_results[i])
        ai_selected_names = {r.get("scheme_name") for r in ai_selected}
        rest = [r for r in results if r.get("scheme_name") not in ai_selected_names]
        return ai_selected + rest
    except Exception:
        return results


# ===========================
# CSS — v14 (Error-Proof)
# ===========================
def _inject_voice_ui_css():
    st.markdown("""
    <style>
    .transcript-card {
        background: linear-gradient(135deg, rgba(0, 229, 255, 0.08), rgba(168, 85, 247, 0.05));
        border-left: 4px solid #00E5FF;
        border-radius: 12px;
        padding: 14px 20px;
        margin: 10px 0;
    }
    .transcript-card .label {
        color: #8696A0;
        font-size: 0.7rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .transcript-card .text {
        color: #FAFAFA;
        font-size: 1rem;
        font-weight: 500;
    }

    .filters-card {
        background: linear-gradient(135deg, rgba(15, 20, 35, 0.6), rgba(11, 20, 26, 0.8));
        border: 1px solid rgba(168, 85, 247, 0.2);
        border-radius: 14px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .filters-card .filters-title {
        color: #A855F7;
        font-size: 0.7rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 700;
        margin: 0;
    }

    .results-header {
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 20px 0 14px 0;
        scroll-margin-top: 100px;
    }
    .results-header .count-badge {
        background: linear-gradient(135deg, #00E5FF, #A855F7);
        color: #0b141a;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.8rem;
    }
    .results-header .title {
        color: #FAFAFA;
        font-size: 1rem;
        font-weight: 600;
    }
    .results-header .ai-badge {
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.3), rgba(236, 72, 153, 0.2));
        color: #EC4899;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.7rem;
        border: 1px solid rgba(236, 72, 153, 0.4);
    }

    .followup-card {
        padding: 14px 18px;
        margin: 12px 0;
        background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(236, 72, 153, 0.05));
        border-left: 4px solid #A855F7;
        border-radius: 10px;
    }
    .followup-card .followup-title {
        color: #A855F7;
        font-size: 0.7rem;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .followup-item {
        padding: 8px 12px;
        margin: 4px 0;
        background: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        color: #E9EDEF;
        font-size: 0.85rem;
    }

    .continuous-banner {
        padding: 12px 18px;
        margin: 12px 0;
        background: linear-gradient(135deg, rgba(0, 255, 136, 0.1), rgba(0, 229, 255, 0.05));
        border-left: 4px solid #00FF88;
        border-radius: 10px;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .continuous-banner .pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #00FF88;
        box-shadow: 0 0 12px #00FF88;
        animation: pulseContinuous 1.5s ease-in-out infinite;
    }
    .continuous-banner .banner-text {
        color: #00FF88;
        font-weight: 600;
        font-size: 0.85rem;
    }
    @keyframes pulseContinuous {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(1.3); }
    }

    .ready-banner {
        padding: 12px 20px;
        margin: 10px 0;
        background: linear-gradient(135deg, rgba(0, 229, 255, 0.12), rgba(168, 85, 247, 0.08));
        border: 2px dashed rgba(0, 229, 255, 0.5);
        border-radius: 12px;
        text-align: center;
    }
    .ready-banner .ready-title {
        color: #00E5FF;
        font-size: 0.9rem;
        font-weight: 700;
        margin: 0 0 2px 0;
    }
    .ready-banner .ready-hint {
        color: #8696A0;
        font-size: 0.75rem;
        margin: 0;
    }

    [data-testid="stExpander"] {
        border: 1px solid rgba(0, 229, 255, 0.12) !important;
        border-radius: 12px !important;
        background: rgba(15, 20, 35, 0.5) !important;
    }
    [data-testid="stExpander"] summary {
        font-weight: 500 !important;
        color: #B0B0D0 !important;
        font-size: 0.85rem !important;
    }

    /* ============================================
       ✅ STICKY BOTTOM BAR — v14
       ============================================ */
    .st-key-sticky_recording_bar {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100vw !important;
        z-index: 999999 !important;
        background: linear-gradient(180deg,
            rgba(11, 20, 26, 0.96) 0%,
            rgba(11, 20, 26, 1) 100%) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border-top: 1px solid rgba(0, 229, 255, 0.25) !important;
        box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.55) !important;
        padding: 14px 24px 16px 24px !important;
        margin: 0 !important;
        box-sizing: border-box !important;
    }

    @media (min-width: 992px) {
        .st-key-sticky_recording_bar {
            padding-left: 356px !important;
        }
    }

    .st-key-sticky_recording_bar > div,
    .st-key-sticky_recording_bar > div > div {
        background: transparent !important;
    }

    .st-key-sticky_recording_bar div[data-testid="stHorizontalBlock"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 12px !important;
        width: 100% !important;
        max-width: 720px !important;
        margin: 0 auto !important;
        flex-wrap: nowrap !important;
    }

    .st-key-sticky_recording_bar div[data-testid="column"] {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
    }

    .st-key-sticky_recording_bar div[data-testid="column"]:first-child {
        justify-content: center !important;
        flex: 1 1 auto !important;
        max-width: 580px !important;
        min-width: 0 !important;
    }

    /* ============================================
       ✅ AUDIO INPUT — Pill shape
       ============================================ */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] {
        width: 100% !important;
        max-width: 580px !important;
        margin: 0 auto !important;
        position: relative !important;
    }

    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] > label {
        display: none !important;
    }

    /* Pill container */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] > div:first-child {
        background: rgba(20, 30, 50, 0.92) !important;
        border: 1px solid rgba(0, 229, 255, 0.3) !important;
        border-radius: 26px !important;
        padding: 4px 16px 4px 4px !important;
        min-height: 50px !important;
        height: 50px !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        gap: 12px !important;
        box-shadow: 0 4px 20px rgba(0, 229, 255, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
        overflow: hidden !important;
        transition: all 0.25s ease !important;
    }

    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] > div:first-child:hover {
        border-color: rgba(0, 229, 255, 0.5) !important;
    }

    /* Recording state */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(button[data-testid*="Stop"]) > div:first-child,
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(audio) > div:first-child {
        border-color: rgba(255, 71, 87, 0.75) !important;
        box-shadow: 0 0 28px rgba(255, 71, 87, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
    }

    /* Mic button */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button {
        background: linear-gradient(135deg, #00E5FF, #A855F7) !important;
        border: none !important;
        border-radius: 50% !important;
        width: 40px !important;
        height: 40px !important;
        min-width: 40px !important;
        min-height: 40px !important;
        margin: 0 !important;
        padding: 0 !important;
        color: #0b141a !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 0 14px rgba(0, 229, 255, 0.55) !important;
        flex-shrink: 0 !important;
        transition: all 0.18s ease !important;
    }

    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button:hover {
        transform: scale(1.06) !important;
        box-shadow: 0 0 22px rgba(0, 229, 255, 0.8) !important;
    }

    /* Force SVG visible */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button svg {
        display: block !important;
        visibility: visible !important;
        width: 18px !important;
        height: 18px !important;
        fill: #0b141a !important;
        color: #0b141a !important;
    }

    /* Recording mic */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(button[data-testid*="Stop"]) button,
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(audio) button {
        background: linear-gradient(135deg, #FF4757, #EC4899) !important;
        animation: pulseRecording 1.2s ease-in-out infinite !important;
    }

    @keyframes pulseRecording {
        0%, 100% { box-shadow: 0 0 14px rgba(255, 71, 87, 0.55); }
        50% { box-shadow: 0 0 26px rgba(255, 71, 87, 1); }
    }

    /* Hide audio playback */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] audio {
        display: none !important;
    }

    /* ============================================
       ✅ HIDE ERROR MESSAGE — VERY STRONG v14
       ============================================ */
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [role="alert"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-testid*="error"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-testid*="Error"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-baseweb="notification"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-testid*="Notification"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] .stAlert,
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [class*="stAlert"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [class*="Notification"],
    .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [class*="Error"] {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
        max-height: 0 !important;
        min-height: 0 !important;
        overflow: hidden !important;
        opacity: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
        border: none !important;
        position: absolute !important;
        left: -99999px !important;
        pointer-events: none !important;
        font-size: 0 !important;
    }

    /* ============================================
       ⚙️ and 🔄 buttons
       ============================================ */
    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(2),
    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(3) {
        flex: 0 0 52px !important;
        max-width: 52px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(2) div[data-testid="stPopover"] > div > button,
    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(3) .stButton > button {
        height: 50px !important;
        min-height: 50px !important;
        width: 50px !important;
        min-width: 50px !important;
        padding: 0 !important;
        font-size: 1.15rem !important;
        line-height: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        border-radius: 14px !important;
        background: rgba(20, 30, 50, 0.9) !important;
        border: 1px solid rgba(0, 229, 255, 0.3) !important;
        color: #00E5FF !important;
        box-shadow: 0 3px 12px rgba(0, 229, 255, 0.12) !important;
        transition: all 0.18s ease !important;
    }

    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(2) div[data-testid="stPopover"] > div > button:hover,
    .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(3) .stButton > button:hover {
        background: rgba(0, 229, 255, 0.15) !important;
        border-color: rgba(0, 229, 255, 0.6) !important;
        transform: translateY(-2px) !important;
    }

    .st-key-sticky_recording_bar .stButton > button:focus,
    .st-key-sticky_recording_bar .stButton > button:focus-visible,
    .st-key-sticky_recording_bar div[data-testid="stPopover"] > div > button:focus {
        outline: none !important;
    }

    /* Mobile */
    @media (max-width: 640px) {
        .st-key-sticky_recording_bar {
            padding: 10px 12px 12px 12px !important;
        }
        .st-key-sticky_recording_bar div[data-testid="column"]:first-child {
            flex: 1 1 auto !important;
            max-width: none !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] {
            max-width: none !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)


# ===========================
# FILTER APPLICATION
# ===========================
def _apply_filters(results, state_filter, category_filter, occupation_filter,
                    income_filter, only_eligible_filter):
    filtered = results
    if state_filter and state_filter != "All":
        filtered = [r for r in filtered if r.get("applicable_state") == "All" or r.get("applicable_state") == state_filter]
    if category_filter and category_filter != "All":
        filtered = [r for r in filtered if category_filter.lower() in str(r.get("category_type", "")).lower()]
    if occupation_filter and occupation_filter != "All":
        filtered = [r for r in filtered if occupation_filter.lower() in str(r.get("occupation", "All")).lower() or r.get("occupation", "All") == "All"]
    if income_filter and income_filter > 0:
        def income_ok(r):
            max_income = r.get("max_annual_income", "")
            if not max_income or pd.isna(max_income):
                return True
            try:
                return float(max_income) >= income_filter
            except (ValueError, TypeError):
                return True
        filtered = [r for r in filtered if income_ok(r)]
    if only_eligible_filter:
        filtered = [r for r in filtered if r.get("eligible", True)]
    return filtered


# ===========================
# PROCESS VOICE QUERY
# ===========================
def _process_voice_query(voice_query, df, t, lang_choice, search_schemes_fn, sort_results_fn,
                          history_module, state_filter, category_filter, occupation_filter,
                          income_filter, only_eligible_filter):
    st.session_state.voice_transcript = voice_query
    st.session_state.ready_for_next = False

    with st.spinner("Schemes dhoondh rahe hain..."):
        results = search_schemes_fn(df, voice_query, top_n=50)
        results = sort_results_fn(results, t["sort_default_nl"], t)

    with st.spinner("AI results ko re-rank kar raha hai..."):
        reranked = _ai_rerank_schemes(voice_query, results, lang_choice)
        st.session_state.voice_results = reranked
        st.session_state.ai_reranked = True

    with st.spinner("Filters apply kar rahe hain..."):
        filtered = _apply_filters(reranked, state_filter, category_filter,
                                    occupation_filter, income_filter, only_eligible_filter)
        st.session_state.voice_filtered_results = filtered
        history_module.save_entry({"mode": "voice", "query": voice_query, "total": len(filtered)})
        st.session_state.voice_history.append({
            "query": voice_query,
            "results": len(filtered),
            "timestamp": time.strftime("%d-%m-%Y %H:%M")
        })

    with st.spinner("Smart questions generate kar rahe hain..."):
        st.session_state.followup_questions = generate_follow_up_questions(voice_query, lang_choice)
        st.session_state.followup_for_query = voice_query

    if st.session_state.auto_speak and filtered:
        result_count = len(filtered)
        if lang_choice == "हिंदी":
            summary = f"मुझे {result_count} योजनाएं मिलीं। टॉप पांच योजनाएं हैं: "
        elif lang_choice == "English":
            summary = f"I found {result_count} schemes. Top five are: "
        else:
            summary = f"{result_count} schemes found. "
        top_5_names = [r.get("scheme_name", "") for r in filtered[:5] if r.get("scheme_name")]
        if top_5_names:
            summary += ", ".join(top_5_names) + "."
        audio_bytes, error = generate_audio_bytes(summary, lang_choice,
                                                    st.session_state.voice_speed,
                                                    st.session_state.voice_gender)
        if audio_bytes:
            st.session_state.pending_audio = audio_bytes

    st.session_state.scroll_to_results = True


# ===========================
# MAIN RENDER
# ===========================
def render_voice_assistant(df, t, lang_choice, search_schemes_fn, sort_results_fn, render_scheme_card_fn, history_module):
    """Voice Assistant v14 — Error-proof with auto-retry."""

    _inject_voice_ui_css()

    # =========================================================
    # ✅ Session state (v14: added audio_attempt for retry)
    # =========================================================
    defaults = {
        "voice_transcript": "", "voice_results": [], "voice_filtered_results": [],
        "voice_history": [], "auto_speak": True, "noise_reduction_enabled": False,
        "last_audio_hash": None, "pending_audio": None, "voice_speed": 1.0,
        "voice_gender": "Female", "continuous_mode": False, "voice_round": 0,
        "followup_questions": [], "followup_for_query": "", "ai_reranked": False,
        "ready_for_next": False, "scroll_to_results": False,
        "audio_attempt": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    if st.session_state.scroll_to_results:
        _scroll_to_results()
        st.session_state.scroll_to_results = False

    if st.session_state.pending_audio:
        try:
            st.audio(st.session_state.pending_audio, format="audio/mp3", autoplay=True)
        except Exception:
            pass
        st.session_state.pending_audio = None

    if st.session_state.ready_for_next:
        st.markdown("""
        <div class="ready-banner">
            <p class="ready-title">🎤 Naya Sawaal Poochne Ke Liye Tayyar</p>
            <p class="ready-hint">Neeche mic dabayein aur apna sawaal bolein</p>
        </div>
        """, unsafe_allow_html=True)

    # HEADING
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
        <div style="
            width: 40px; height: 40px; border-radius: 12px;
            background: linear-gradient(135deg, #00E5FF, #A855F7);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
            box-shadow: 0 4px 15px rgba(0, 229, 255, 0.3);
        ">🎤</div>
        <div>
            <div style="font-size: 1.4rem; font-weight: 700; color: #FAFAFA; letter-spacing: -0.3px;">Voice Assistant</div>
            <div style="font-size: 0.8rem; color: #8696A0; margin-top: 2px;">Speak your requirement — use filters to narrow down results.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # FILTERS
    st.markdown('<div class="filters-card"><p class="filters-title">Results Filters</p></div>', unsafe_allow_html=True)

    try:
        all_states = sorted([s for s in df["applicable_state"].dropna().unique() if s and s != "All"])
        all_categories = sorted([c for c in df["category_type"].dropna().unique() if c])
        all_occupations = sorted([o for o in df["occupation"].dropna().unique() if o and o != "All"])
    except Exception:
        all_states = ["Madhya Pradesh", "Uttar Pradesh", "Bihar", "Maharashtra"]
        all_categories = ["Agriculture", "Health", "Education", "Housing", "Business/Loan"]
        all_occupations = ["Farmer", "Student", "Entrepreneur", "Unemployed Youth"]

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        state_filter = st.selectbox("State", ["All"] + all_states, index=0, key="voice_filter_state")
        category_filter = st.selectbox("Category", ["All"] + all_categories, index=0, key="voice_filter_category")
    with fcol2:
        occupation_filter = st.selectbox("Occupation", ["All"] + all_occupations, index=0, key="voice_filter_occupation")
        income_filter = st.number_input("Max Annual Income (₹)", min_value=0, value=0, step=50000, key="voice_filter_income")

    only_eligible_filter = st.checkbox("Only Eligible Schemes", value=False, key="voice_filter_only_eligible")

    if st.button("Clear Filters", key="voice_clear_filters"):
        st.session_state.voice_filter_state = "All"
        st.session_state.voice_filter_category = "All"
        st.session_state.voice_filter_occupation = "All"
        st.session_state.voice_filter_income = 0
        st.session_state.voice_filter_only_eligible = False
        st.rerun()

    st.markdown('<div style="margin: 8px 0;"></div>', unsafe_allow_html=True)

    # Action buttons
    if st.session_state.voice_results:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Re-apply Filters", use_container_width=True, key="voice_apply_filters_btn"):
                filtered = _apply_filters(st.session_state.voice_results, state_filter, category_filter, occupation_filter, income_filter, only_eligible_filter)
                st.session_state.voice_filtered_results = filtered
                st.session_state.scroll_to_results = True
                st.rerun()
        with col2:
            if st.button("Clear Results", use_container_width=True, key="voice_clear_btn"):
                st.session_state.voice_round += 1
                st.session_state.audio_attempt = 0
                st.session_state.voice_transcript = ""
                st.session_state.voice_results = []
                st.session_state.voice_filtered_results = []
                st.session_state.followup_questions = []
                st.session_state.last_audio_hash = None
                st.session_state.pending_audio = None
                st.session_state.ai_reranked = False
                st.session_state.ready_for_next = False
                st.rerun()

    # TRANSCRIPT
    if st.session_state.voice_transcript:
        st.markdown(f"""
        <div class="transcript-card">
            <div class="label">Aapka Sawaal</div>
            <div class="text">{st.session_state.voice_transcript}</div>
        </div>
        """, unsafe_allow_html=True)

    # FOLLOW-UPS
    if (st.session_state.followup_questions and st.session_state.followup_for_query == st.session_state.voice_transcript):
        questions_html = "".join([f'<div class="followup-item">▸ {q}</div>' for q in st.session_state.followup_questions])
        st.markdown(f"""
        <div class="followup-card">
            <div class="followup-title">Smart Follow-up Questions</div>
            {questions_html}
        </div>
        """, unsafe_allow_html=True)
        if st.button("Refresh Questions", key="refresh_followups"):
            with st.spinner("Naye questions generate kar rahe hain..."):
                st.session_state.followup_questions = generate_follow_up_questions(st.session_state.voice_transcript, lang_choice)
                st.rerun()

    # RESULTS
    display_results = st.session_state.voice_filtered_results or st.session_state.voice_results

    if display_results:
        count = len(display_results)
        active_filters = []
        if state_filter != "All": active_filters.append(f"State: {state_filter}")
        if category_filter != "All": active_filters.append(f"Category: {category_filter}")
        if occupation_filter != "All": active_filters.append(f"Occupation: {occupation_filter}")
        if income_filter > 0: active_filters.append(f"Income ≤ ₹{income_filter:,}")
        if only_eligible_filter: active_filters.append("Only Eligible")
        if active_filters:
            st.caption(f"Active filters: {' | '.join(active_filters)}")

        ai_badge = '<span class="ai-badge">AI-RANKED</span>' if st.session_state.get("ai_reranked") else ''
        st.markdown(f"""
        <div class="results-header">
            <span class="count-badge">{count}</span>
            <span class="title">schemes mili</span>
            {ai_badge}
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Listen Top 5", use_container_width=True, key="speak_top5_btn"):
                top_5 = [r.get("scheme_name", "") for r in display_results[:5]]
                if top_5:
                    summary = "टॉप पांच योजनाएं: " if lang_choice == "हिंदी" else "Top five schemes: "
                    summary += ", ".join(top_5) + "."
                    audio_bytes, error = generate_audio_bytes(summary, lang_choice, st.session_state.voice_speed, st.session_state.voice_gender)
                    if audio_bytes:
                        st.session_state.pending_audio = audio_bytes
                        st.rerun()
                    elif error:
                        st.error(error)
        with col_b:
            if st.button("Listen All", use_container_width=True, key="speak_all_btn"):
                all_names = [r.get("scheme_name", "") for r in display_results]
                if all_names:
                    summary = f"कुल {len(all_names)} योजनाएं: " if lang_choice == "हिंदी" else f"Total {len(all_names)} schemes: "
                    summary += ", ".join(all_names) + "."
                    audio_bytes, error = generate_audio_bytes(summary, lang_choice, st.session_state.voice_speed, st.session_state.voice_gender)
                    if audio_bytes:
                        st.session_state.pending_audio = audio_bytes
                        st.rerun()
                    elif error:
                        st.error(error)

        if st.session_state.continuous_mode:
            st.markdown("""
            <div class="continuous-banner">
                <span class="pulse-dot"></span>
                <span class="banner-text">Continuous Mode ON — "Ask Next Question" dabakar naya sawaal poochein</span>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Ask Next Question", use_container_width=True, key=f"continuous_next_btn_round_{st.session_state.voice_round}", type="primary"):
                st.session_state.voice_round += 1
                st.session_state.audio_attempt = 0
                st.session_state.voice_transcript = ""
                st.session_state.voice_results = []
                st.session_state.voice_filtered_results = []
                st.session_state.followup_questions = []
                st.session_state.followup_for_query = ""
                st.session_state.last_audio_hash = None
                st.session_state.pending_audio = None
                st.session_state.ai_reranked = False
                st.session_state.ready_for_next = True
                st.toast("Ready! Neeche mic dabakar naya sawaal poochein.", icon="🎤")
                st.rerun()

        st.write("")
        for r in display_results:
            render_scheme_card_fn(r, t, key_prefix="voice", lang_choice=lang_choice)

    elif st.session_state.voice_transcript:
        st.info("Koi scheme nahi mili. Filters change karein ya alag sawaal poochhein.")

    # HISTORY
    if st.session_state.voice_history:
        with st.expander(f"Voice Search History ({len(st.session_state.voice_history)})", expanded=False):
            for item in reversed(st.session_state.voice_history[-10:]):
                st.markdown(
                    f'<div style="padding:10px 14px; margin:5px 0; background:rgba(0,229,255,0.05); '
                    f'border-left:3px solid #00E5FF; border-radius:8px;">'
                    f'<p style="margin:0; color:#8696A0; font-size:0.7rem;">{item["timestamp"]}</p>'
                    f'<p style="margin:5px 0 0 0; color:#FAFAFA; font-size:0.9rem; font-weight:500;">{item["query"]}</p>'
                    f'<p style="margin:3px 0 0 0; color:#6B7A8F; font-size:0.75rem;">{item["results"]} schemes</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )
            if st.button("Clear History", key="clear_voice_history_btn"):
                st.session_state.voice_history = []
                st.rerun()

    # SPACER
    st.markdown('<div style="height: 110px;"></div>', unsafe_allow_html=True)

    # =========================================================
    # STICKY BOTTOM RECORDING BAR — v14 with retry key
    # =========================================================
    recording_bar = st.container(key="sticky_recording_bar")

    with recording_bar:
        rec_col1, rec_col2, rec_col3 = st.columns([7, 1, 1], gap="small")

        with rec_col1:
            current_round = st.session_state.get("voice_round", 0)
            # ✅ FIX: Include audio_attempt in key so widget resets on error
            attempt = st.session_state.get("audio_attempt", 0)
            audio_value = st.audio_input(
                "🎤 Recording",
                key=f"voice_audio_input_{current_round}_{attempt}",
                label_visibility="collapsed"
            )

        with rec_col2:
            with st.popover("⚙️", help="Voice Settings"):
                st.markdown("##### ⚙️ Voice Settings")
                st.session_state.noise_reduction_enabled = st.checkbox(
                    "🔇 Noise Reduction",
                    value=st.session_state.noise_reduction_enabled,
                    key="nr_popover"
                )
                st.session_state.auto_speak = st.checkbox(
                    "🔊 Auto Voice Response",
                    value=st.session_state.auto_speak,
                    key="as_popover"
                )
                st.divider()
                st.session_state.voice_speed = st.slider(
                    "🎚️ Voice Speed",
                    min_value=0.5, max_value=2.0,
                    value=st.session_state.voice_speed, step=0.1,
                    key="vs_popover"
                )
                st.session_state.voice_gender = st.selectbox(
                    "🎭 Voice Type",
                    ["Female", "Male"],
                    index=0 if st.session_state.voice_gender == "Female" else 1,
                    key="vg_popover"
                )
                st.divider()
                st.session_state.continuous_mode = st.checkbox(
                    "🔄 Continuous Mode",
                    value=st.session_state.continuous_mode,
                    key="cm_popover"
                )

        with rec_col3:
            if st.button("🔄", help="Reset", key="reset_btn_bottom"):
                st.session_state.voice_round += 1
                st.session_state.audio_attempt = 0
                st.session_state.voice_transcript = ""
                st.session_state.voice_results = []
                st.session_state.voice_filtered_results = []
                st.session_state.followup_questions = []
                st.session_state.followup_for_query = ""
                st.session_state.last_audio_hash = None
                st.session_state.pending_audio = None
                st.session_state.ai_reranked = False
                st.session_state.ready_for_next = False
                st.rerun()

    # =========================================================
    # PROCESS AUDIO — v14 with auto-retry
    # =========================================================
    if audio_value is not None:
        try:
            audio_bytes_temp = audio_value.read()
            audio_value.seek(0)
            audio_hash = hash(audio_bytes_temp)
        except Exception:
            # Corrupted audio — reset and try again
            st.session_state.audio_attempt = st.session_state.get("audio_attempt", 0) + 1
            st.session_state.last_audio_hash = None
            audio_hash = None
            audio_bytes_temp = None

        # Skip if same recording already processed
        if audio_hash is not None and audio_hash == st.session_state.last_audio_hash:
            audio_hash = None

        if audio_hash is not None:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Sun rahe hain aur text mein badal rahe hain..."):
                try:
                    transcript = _transcribe_audio(
                        audio_bytes_temp,
                        lang_choice,
                        apply_noise_reduction=st.session_state.noise_reduction_enabled
                    )
                    if transcript and transcript.strip():
                        _process_voice_query(
                            transcript.strip(), df, t, lang_choice,
                            search_schemes_fn, sort_results_fn, history_module,
                            state_filter, category_filter, occupation_filter,
                            income_filter, only_eligible_filter
                        )
                    # ✅ Success: reset attempt counter
                    st.session_state.audio_attempt = 0
                    st.rerun()
                except RuntimeError as e:
                    # ✅ Voice recognition failed — reset audio input, show warning
                    st.session_state.audio_attempt = st.session_state.get("audio_attempt", 0) + 1
                    st.session_state.last_audio_hash = None
                    st.warning(f"🎤 {str(e)}")
                    st.rerun()
                except Exception as e:
                    # ✅ Any unexpected error — reset audio input
                    st.session_state.audio_attempt = st.session_state.get("audio_attempt", 0) + 1
                    st.session_state.last_audio_hash = None
                    st.error(f"⚠️ Voice error. Please try again.")
                    st.rerun()