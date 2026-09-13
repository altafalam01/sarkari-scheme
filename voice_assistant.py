"""
voice_assistant.py — Voice Assistant v23.

v23 FIXES:
  - `@st.cache_resource` decorator REMOVED from `_get_cached_llm()`.
    Ye wahi bug tha jo ai_chatbot.py aur simple_explain.py mein tha —
    decorator Streamlit ke cache system ke saath conflict karta tha aur
    pehli call pe app hang kar deta tha. Ab har call pe naya ChatGroq
    instance banta hai (fast — sirf object creation, koi network call nahi).

v22 FIXES (inherited):
  - Edge TTS timeout 30s → 5s (2 jagah). Ye "Listen" button ka 30-second
    hang fix karta hai.
  - `_get_cached_llm()` ke timeout bhi 20s → 8s.

v21 FIXES (inherited):
  - BUG #1: `audio_attempt` dead variable REMOVED entirely.
  - BUG #2: `voice_round` ab error paths pe bhi increment hota hai.
  - BUG #3: `_cleanup_audio_widgets()` simplify.
  - BUG #4: Session state mein audio widget keys accumulate nahi honge.
  - BUG #5: MutationObserver infinite loop fix.
  - BUG #6: Edge TTS timeout ab asyncio.wait_for se enforced.
  - BUG #14: Audio format conversion via pydub.
  - BUG #16: LLM init failure ab printed/logged.
  - BUG #19: Marathi/Tamil summary translations added.
  - BUG #20: voice_history capped at 50 entries.

Depends on: streamlit, numpy, pandas, dotenv, and optionally:
  gTTS, edge-tts, SpeechRecognition, noisereduce, pydub
"""

import io
import os
import re
import time
import asyncio
import threading
import tempfile
import warnings

import streamlit as st
import streamlit.components.v1 as components
import numpy as np
import pandas as pd
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message=".*components\\.v1\\.html.*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()

DEFAULT_GROQ_MODEL = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-20b")


# ===========================
# OPTIONAL DEPENDENCIES
# ===========================
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

_PYDUB_AVAILABLE = True
try:
    from pydub import AudioSegment
except Exception:
    _PYDUB_AVAILABLE = False


# ===========================
# HELPERS
# ===========================
def _safe_str(value, default=""):
    if value is None:
        return default
    try:
        if value != value:
            return default
    except Exception:
        pass
    if isinstance(value, str) and not value.strip():
        return default
    return str(value)


def _safe_float(value, default=None):
    if value is None:
        return default
    try:
        if value != value:
            return default
    except Exception:
        pass
    if isinstance(value, str) and not value.strip():
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_remove(path):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


# ===========================
# LLM FACTORY (v23: no caching)
# ===========================
def _get_cached_llm():
    """
    ChatGroq instance return karta hai.

    v23 FIX: @st.cache_resource decorator hataa diya. Ye decorator
    Streamlit ke cache system ke saath conflict karta tha aur pehli
    call pe app hang kar deta tha — same bug jo ai_chatbot.py aur
    simple_explain.py mein tha.

    Ab har call pe naya ChatGroq instance banta hai — bahut fast
    operation hai (sirf object creation, koi network call nahi).
    ChatGroq internally connection pooling handle karta hai, isliye
    har call pe naya object banane se performance pe asar nahi padta.

    Function ka naam `_get_cached_llm` hi rakha taaki existing callers
    na tootein (legacy naam hai, lekin ab caching nahi hoti).
    """
    try:
        from langchain_groq import ChatGroq
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        return ChatGroq(
            temperature=0.7,
            groq_api_key=api_key,
            model_name=DEFAULT_GROQ_MODEL,
            timeout=8,  # v22: 20 → 8 (hang duration kam)
        )
    except Exception as e:
        print(f"[voice_assistant] LLM init failed: {type(e).__name__}: {e}")
        return None


# ===========================
# AUTO-SCROLL
# ===========================
def _scroll_to_results():
    try:
        components.html(
            "<script>"
            "setTimeout(function() {"
            "  try {"
            "    var pd = window.parent.document;"
            "    var rh = pd.querySelector('.results-header');"
            "    if (rh) rh.scrollIntoView({behavior:'smooth',block:'start'});"
            "  } catch(e) {}"
            "}, 600);"
            "</script>",
            height=0,
        )
    except Exception:
        pass


# ===========================
# STICKY BAR FORCE FIX (v21 — infinite loop fix)
# ===========================
def _force_sticky_bar():
    js = """
    <script>
    (function() {
        var applied = false;
        var scheduled = false;

        function findStickyBar() {
            var parentDoc = window.parent.document;
            var direct = parentDoc.querySelector('[class*="st-key-sticky_recording_bar"]');
            if (direct) return direct;

            var audioInputs = parentDoc.querySelectorAll('[data-testid="stAudioInput"]');
            if (!audioInputs.length) return null;

            var bar = null;
            audioInputs.forEach(function(input) {
                var el = input;
                for (var i = 0; i < 12; i++) {
                    if (!el.parentElement) break;
                    el = el.parentElement;
                    if (el.querySelector && el.querySelector('[data-testid="column"]')) {
                        if (el.querySelector('[data-testid="stAudioInput"]')) {
                            bar = el;
                            break;
                        }
                    }
                }
            });
            return bar;
        }

        function getSidebarWidth() {
            try {
                var parentDoc = window.parent.document;
                var sidebar = parentDoc.querySelector('section[data-testid="stSidebar"]');
                if (!sidebar) return 0;
                var style = window.parent.getComputedStyle(sidebar);
                if (style.display === 'none' || style.visibility === 'hidden') return 0;
                var w = sidebar.getBoundingClientRect().width;
                return (w > 100) ? w : 0;
            } catch(e) {
                return 0;
            }
        }

        function applySticky() {
            if (applied) return;
            try {
                var bar = findStickyBar();
                if (!bar) return;

                var sidebarWidth = getSidebarWidth();

                bar.style.setProperty('position', 'fixed', 'important');
                bar.style.setProperty('bottom', '0', 'important');
                bar.style.setProperty('left', sidebarWidth + 'px', 'important');
                bar.style.setProperty('right', '0', 'important');
                bar.style.setProperty('width', 'auto', 'important');
                bar.style.setProperty('z-index', '999999', 'important');
                bar.style.setProperty('background',
                    'linear-gradient(180deg, rgba(11,20,26,0.96) 0%, rgba(11,20,26,1) 100%)',
                    'important');
                bar.style.setProperty('backdrop-filter', 'blur(20px)', 'important');
                bar.style.setProperty('-webkit-backdrop-filter', 'blur(20px)', 'important');
                bar.style.setProperty('border-top', '1px solid rgba(0,229,255,0.25)', 'important');
                bar.style.setProperty('box-shadow', '0 -8px 32px rgba(0,0,0,0.55)', 'important');
                bar.style.setProperty('padding', '14px 24px 16px 24px', 'important');
                bar.style.setProperty('box-sizing', 'border-box', 'important');
                bar.style.setProperty('margin', '0', 'important');

                bar.dataset.stickyApplied = "1";
                applied = true;
            } catch (e) {
                console.log('[sticky-bar] error:', e);
            }
        }

        function scheduleApply() {
            if (scheduled) return;
            scheduled = true;
            setTimeout(function() {
                scheduled = false;
                applySticky();
            }, 50);
        }

        setTimeout(applySticky, 100);
        setTimeout(applySticky, 300);
        setTimeout(applySticky, 600);
        setTimeout(applySticky, 1000);
        setTimeout(applySticky, 2000);
        setTimeout(applySticky, 3500);

        try {
            var observer = new MutationObserver(function() {
                applied = false;
                scheduleApply();
            });
            observer.observe(window.parent.document.body, {
                childList: true, subtree: true,
                attributes: true, attributeFilter: ['style', 'class']
            });
        } catch(e) {}

        try {
            window.parent.addEventListener('resize', function() {
                applied = false;
                scheduleApply();
            });
        } catch(e) {}
    })();
    </script>
    """
    try:
        components.html(js, height=0)
    except Exception:
        pass


# ===========================
# EDGE TTS (v22: default timeout 5s)
# ===========================
def _generate_edge_audio_with_rate(text, voice, rate_str, timeout=5):
    """
    v22: default timeout 30 → 5. asyncio.wait_for se hard timeout enforced
    — thread background mein bhatakta nahi.
    """
    result = {"data": None, "error": None}

    def _worker():
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def _collect():
                comm = edge_tts.Communicate(text, voice, rate=rate_str)
                buf = io.BytesIO()
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        buf.write(chunk["data"])
                buf.seek(0)
                return buf.read()

            async def _gen_with_timeout():
                inner_timeout = max(1, timeout - 1)
                return await asyncio.wait_for(_collect(), timeout=inner_timeout)

            data = loop.run_until_complete(_gen_with_timeout())
            result["data"] = data
        except asyncio.TimeoutError:
            result["error"] = TimeoutError(f"Edge TTS {timeout}s timeout")
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
    thread.join(timeout=timeout + 2)

    if thread.is_alive():
        return None, TimeoutError(f"Edge TTS hard timeout")

    return result["data"], result["error"]


# ===========================
# AUDIO GENERATION
# ===========================
_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "\U00002300-\U000023FF"
    "\U000025A0-\U000025FF"
    "]+",
    flags=re.UNICODE,
)
_PUNCT_PATTERN = re.compile(r'[★☆⭐📅📊📋📝🎯✅❌⚠️🔥🚨•●○■□▪▫→←↑↓↔“”"\'`‘’]+')


def _clean_text_for_tts(text, lang_choice):
    if not text:
        return ""
    text = _EMOJI_PATTERN.sub("", text)
    text = _PUNCT_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if lang_choice in ["हिंदी", "मराठी"]:
        text = re.sub(r"[^\u0900-\u097F\w\s,.\-?!।]", "", text)
    elif lang_choice == "தமிழ்":
        text = re.sub(r"[^\u0B80-\u0BFF\w\s,.\-?!।]", "", text)
    return text.strip()


def generate_audio_bytes(text, lang_choice="English", speed=1.0, voice_gender="Female"):
    text = _clean_text_for_tts(text, lang_choice)
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

        # v22: timeout 30 → 5
        audio_bytes, error = _generate_edge_audio_with_rate(text, voice, rate_str, timeout=5)
        if not error and audio_bytes and len(audio_bytes) > 0:
            return audio_bytes, None

    if _GTTS_AVAILABLE:
        lang_code = _GTTS_LANG_CODES.get(lang_choice, "en")
        for tld in ["co.in", "com"]:
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


def speak_text(text, lang_choice="English", speed=1.0, voice_gender="Female"):
    audio_bytes, error = generate_audio_bytes(text, lang_choice, speed, voice_gender)
    if error:
        st.error(error)
        return
    if audio_bytes:
        try:
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)
        except Exception:
            pass


def build_scheme_text_for_reading(scheme_data, lang_choice="English"):
    if not isinstance(scheme_data, dict):
        return ""
    field_labels = {
        "English": {"scheme": "Scheme", "category": "Category",
                    "state": "Applicable State", "description": "What is it",
                    "benefits": "Benefits"},
        "हिंदी": {"scheme": "योजना", "category": "श्रेणी",
                  "state": "लागू राज्य", "description": "यह क्या है",
                  "benefits": "लाभ"},
        "मराठी": {"scheme": "योजना", "category": "श्रेणी",
                  "state": "लागू राज्य", "description": "हे काय आहे",
                  "benefits": "लाभ"},
        "தமிழ்": {"scheme": "திட்டம்", "category": "வகை",
                  "state": "பொருந்தும் மாநிலம்", "description": "இது என்ன",
                  "benefits": "நன்மைகள்"},
    }
    labels = field_labels.get(lang_choice, field_labels["English"])
    parts = []
    scheme_name = _safe_str(scheme_data.get("scheme_name"))
    if scheme_name:
        parts.append(f"{labels['scheme']}: {scheme_name}")
    category = _safe_str(scheme_data.get("category_type"))
    if category:
        parts.append(f"{labels['category']}: {category}")
    state = _safe_str(scheme_data.get("applicable_state"))
    if state and state != "All":
        parts.append(f"{labels['state']}: {state}")
    description = _safe_str(scheme_data.get("description"))
    if description:
        parts.append(f"{labels['description']}: {description}")
    benefits = _safe_str(scheme_data.get("benefits"))
    if benefits:
        parts.append(f"{labels['benefits']}: {benefits}")
    return re.sub(r"\s+", " ", ". ".join(parts))


def read_scheme_details(scheme_data, lang_choice="English"):
    text = build_scheme_text_for_reading(scheme_data, lang_choice)
    speed = st.session_state.get("voice_speed", 1.0)
    gender = st.session_state.get("voice_gender", "Female")
    speak_text(text, lang_choice, speed, gender)


# ===========================
# NOISE REDUCTION
# ===========================
def reduce_noise(audio_bytes):
    if not _NOISE_REDUCE_AVAILABLE:
        return audio_bytes
    tmp_in = None
    tmp_out = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_in = f.name
        sample_rate, data = wavfile.read(tmp_in)
        if len(data.shape) > 1:
            data = data.mean(axis=1).astype(data.dtype)
        reduced = nr.reduce_noise(y=data, sr=sample_rate, stationary=False)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_out = f.name
        wavfile.write(tmp_out, sample_rate, reduced.astype(np.int16))
        with open(tmp_out, "rb") as f:
            cleaned = f.read()
        return cleaned
    except Exception:
        return audio_bytes
    finally:
        _safe_remove(tmp_in)
        _safe_remove(tmp_out)


# ===========================
# AUDIO → WAV CONVERSION (v21 — browser format fix)
# ===========================
def _convert_to_wav(audio_bytes):
    if not _PYDUB_AVAILABLE:
        return audio_bytes
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
        wav_buf = io.BytesIO()
        audio.export(wav_buf, format="wav")
        wav_buf.seek(0)
        return wav_buf.read()
    except Exception as e:
        print(f"[voice_assistant] WAV conversion failed: {type(e).__name__}: {e}")
        return audio_bytes


# ===========================
# TRANSCRIPTION
# ===========================
def _transcribe_audio(audio_bytes, lang_choice, apply_noise_reduction=False):
    if not _SR_AVAILABLE:
        raise RuntimeError("Voice recognition not available (install SpeechRecognition)")

    audio_bytes = _convert_to_wav(audio_bytes)

    if apply_noise_reduction and _NOISE_REDUCE_AVAILABLE:
        try:
            audio_bytes = reduce_noise(audio_bytes)
        except Exception:
            pass

    recognizer = sr.Recognizer()
    sr_lang = {
        "English": "en-IN", "हिंदी": "hi-IN",
        "मराठी": "mr-IN", "தமிழ்": "ta-IN",
    }.get(lang_choice, "en-IN")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        with sr.AudioFile(tmp_path) as source:
            audio_data = recognizer.record(source)
        try:
            return recognizer.recognize_google(audio_data, language=sr_lang)
        except sr.UnknownValueError:
            raise RuntimeError("Awaaz samajh nahi aayi. Kripya saaf bolein.")
        except sr.RequestError as e:
            raise RuntimeError(f"Speech recognition service error: {_safe_str(e)[:80]}")
    finally:
        _safe_remove(tmp_path)


# ===========================
# FOLLOW-UP QUESTIONS
# ===========================
def generate_follow_up_questions(transcript, lang_choice="English"):
    try:
        llm = _get_cached_llm()
        if llm is None:
            return []
        if lang_choice == "हिंदी":
            prompt = (
                f'User ka sawaal: "{transcript}"\n\n'
                "Sarkari yojana ke liye 3 short follow-up questions banao "
                "(Hindi mein, Roman script).\n"
                "Har question alag line par, numbering ke saath (1., 2., 3.).\n"
                "Sirf questions return karo."
            )
        else:
            prompt = (
                f'User\'s question: "{transcript}"\n\n'
                "Generate 3 short follow-up questions for a government scheme search.\n"
                "Each on a new line, numbered (1., 2., 3.).\n"
                "Return ONLY questions."
            )
        response = llm.invoke(prompt)
        content = _safe_str(getattr(response, "content", "")).strip()
        questions = []
        for line in content.split("\n"):
            line = re.sub(r"^\d+\.\s*", "", line.strip())
            if 10 < len(line) < 200:
                questions.append(line)
        return questions[:3]
    except Exception:
        return []


# ===========================
# AI RE-RANKING
# ===========================
def _ai_rerank_schemes(transcript, results, lang_choice="English"):
    if not results or len(results) < 2:
        return results
    try:
        llm = _get_cached_llm()
        if llm is None:
            return results
        top_results = results[:25]
        scheme_list = "\n".join([
            f"{i+1}. {_safe_str(r.get('scheme_name', ''))} | "
            f"{_safe_str(r.get('category_type', ''))} | "
            f"{_safe_str(r.get('description', ''))[:80]}"
            for i, r in enumerate(top_results)
        ])
        prompt = (
            f'User query: "{transcript}"\n\n'
            f"Available schemes:\n{scheme_list}\n\n"
            "Task: Identify the TOP 5 most relevant schemes for this user's query.\n"
            "Consider the user's INTENT, not just keyword matches.\n\n"
            "Return ONLY the numbers (1-25) of top 5 most relevant schemes, "
            "comma-separated.\n"
            "Example output: 3, 7, 12, 1, 15\n\n"
            "If NONE are relevant, return: NONE"
        )
        response = llm.invoke(prompt)
        content = _safe_str(getattr(response, "content", "")).strip()
        if "NONE" in content.upper():
            return results
        seen_idx = set()
        ai_selected = []
        for num_str in re.findall(r"\d+", content):
            try:
                num = int(num_str)
            except ValueError:
                continue
            if 1 <= num <= len(top_results):
                idx = num - 1
                if idx not in seen_idx:
                    seen_idx.add(idx)
                    ai_selected.append(top_results[idx])
            if len(ai_selected) >= 5:
                break
        if not ai_selected:
            return results
        ai_selected_names = {r.get("scheme_name") for r in ai_selected}
        rest = [r for r in results if r.get("scheme_name") not in ai_selected_names]
        return ai_selected + rest
    except Exception:
        return results


# ===========================
# CSS INJECTION
# ===========================
def _inject_voice_ui_css():
    if st.session_state.get("_voice_css_injected"):
        return
    st.session_state["_voice_css_injected"] = True
    st.markdown(
        """
        <style>
        .transcript-card {
            background: linear-gradient(135deg, rgba(0, 229, 255, 0.08), rgba(168, 85, 247, 0.05));
            border-left: 4px solid #00E5FF; border-radius: 12px;
            padding: 14px 20px; margin: 10px 0;
        }
        .transcript-card .label {
            color: #8696A0; font-size: 0.7rem; letter-spacing: 1.5px;
            text-transform: uppercase; font-weight: 600; margin-bottom: 4px;
        }
        .transcript-card .text { color: #FAFAFA; font-size: 1rem; font-weight: 500; }

        .filters-card {
            background: linear-gradient(135deg, rgba(15, 20, 35, 0.6), rgba(11, 20, 26, 0.8));
            border: 1px solid rgba(168, 85, 247, 0.2);
            border-radius: 14px; padding: 16px 20px; margin-bottom: 12px;
        }
        .filters-card .filters-title {
            color: #A855F7; font-size: 0.7rem; letter-spacing: 1.5px;
            text-transform: uppercase; font-weight: 700; margin: 0;
        }

        .results-header {
            display: flex; align-items: center; gap: 10px;
            margin: 20px 0 14px 0; scroll-margin-top: 100px;
        }
        .results-header .count-badge {
            background: linear-gradient(135deg, #00E5FF, #A855F7);
            color: #0b141a; padding: 4px 12px; border-radius: 20px;
            font-weight: 700; font-size: 0.8rem;
        }
        .results-header .title { color: #FAFAFA; font-size: 1rem; font-weight: 600; }
        .results-header .ai-badge {
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.3), rgba(236, 72, 153, 0.2));
            color: #EC4899; padding: 4px 10px; border-radius: 20px;
            font-weight: 700; font-size: 0.7rem;
            border: 1px solid rgba(236, 72, 153, 0.4);
        }

        .followup-card {
            padding: 14px 18px; margin: 12px 0;
            background: linear-gradient(135deg, rgba(168, 85, 247, 0.1), rgba(236, 72, 153, 0.05));
            border-left: 4px solid #A855F7; border-radius: 10px;
        }
        .followup-card .followup-title {
            color: #A855F7; font-size: 0.7rem; letter-spacing: 1.5px;
            text-transform: uppercase; font-weight: 700; margin-bottom: 8px;
        }
        .followup-item {
            padding: 8px 12px; margin: 4px 0;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 8px; color: #E9EDEF; font-size: 0.85rem;
        }

        .continuous-banner {
            padding: 12px 18px; margin: 12px 0;
            background: linear-gradient(135deg, rgba(0, 255, 136, 0.1), rgba(0, 229, 255, 0.05));
            border-left: 4px solid #00FF88; border-radius: 10px;
            display: flex; align-items: center; gap: 12px;
        }
        .continuous-banner .pulse-dot {
            display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            background: #00FF88; box-shadow: 0 0 12px #00FF88;
            animation: pulseContinuous 1.5s ease-in-out infinite;
        }
        .continuous-banner .banner-text {
            color: #00FF88; font-weight: 600; font-size: 0.85rem;
        }
        @keyframes pulseContinuous {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
        }

        .ready-banner {
            padding: 12px 20px; margin: 10px 0;
            background: linear-gradient(135deg, rgba(0, 229, 255, 0.12), rgba(168, 85, 247, 0.08));
            border: 2px dashed rgba(0, 229, 255, 0.5);
            border-radius: 12px; text-align: center;
        }
        .ready-banner .ready-title {
            color: #00E5FF; font-size: 0.9rem; font-weight: 700; margin: 0 0 2px 0;
        }
        .ready-banner .ready-hint {
            color: #8696A0; font-size: 0.75rem; margin: 0;
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

        .st-key-sticky_recording_bar {
            position: fixed !important;
            bottom: 0 !important;
            right: 0 !important;
            left: 21rem !important;
            width: auto !important;
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
        @media (max-width: 992px) {
            .st-key-sticky_recording_bar { left: 0 !important; }
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

        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] {
            width: 100% !important;
            max-width: 580px !important;
            margin: 0 auto !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] > label {
            display: none !important;
        }
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
            box-shadow: 0 4px 20px rgba(0, 229, 255, 0.1),
                        inset 0 1px 0 rgba(255, 255, 255, 0.04) !important;
            overflow: hidden !important;
            transition: all 0.25s ease !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] > div:first-child:hover {
            border-color: rgba(0, 229, 255, 0.5) !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(button[data-testid*="Stop"]) > div:first-child,
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(audio) > div:first-child {
            border-color: rgba(255, 71, 87, 0.75) !important;
            box-shadow: 0 0 28px rgba(255, 71, 87, 0.4),
                        inset 0 1px 0 rgba(255, 255, 255, 0.06) !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button {
            background: linear-gradient(135deg, #00E5FF, #A855F7) !important;
            border: none !important;
            border-radius: 50% !important;
            width: 40px !important; height: 40px !important;
            min-width: 40px !important; min-height: 40px !important;
            margin: 0 !important; padding: 0 !important;
            color: #0b141a !important;
            display: flex !important; align-items: center !important;
            justify-content: center !important;
            box-shadow: 0 0 14px rgba(0, 229, 255, 0.55) !important;
            flex-shrink: 0 !important;
            transition: all 0.18s ease !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button:hover {
            transform: scale(1.06) !important;
            box-shadow: 0 0 22px rgba(0, 229, 255, 0.8) !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] button svg {
            display: block !important;
            visibility: visible !important;
            width: 18px !important; height: 18px !important;
            fill: #0b141a !important; color: #0b141a !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(button[data-testid*="Stop"]) button,
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"]:has(audio) button {
            background: linear-gradient(135deg, #FF4757, #EC4899) !important;
            animation: pulseRecording 1.2s ease-in-out infinite !important;
        }
        @keyframes pulseRecording {
            0%, 100% { box-shadow: 0 0 14px rgba(255, 71, 87, 0.55); }
            50% { box-shadow: 0 0 26px rgba(255, 71, 87, 1); }
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] audio {
            display: none !important;
        }
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [role="alert"],
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-testid*="error"],
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] [data-baseweb="notification"],
        .st-key-sticky_recording_bar div[data-testid="stAudioInput"] .stAlert {
            display: none !important;
            height: 0 !important;
            overflow: hidden !important;
            position: absolute !important;
            left: -99999px !important;
            pointer-events: none !important;
        }
        .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(2),
        .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(3) {
            flex: 0 0 52px !important;
            max-width: 52px !important;
        }
        .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(2) div[data-testid="stPopover"] > div > button,
        .st-key-sticky_recording_bar div[data-testid="column"]:nth-child(3) .stButton > button {
            height: 50px !important; min-height: 50px !important;
            width: 50px !important; min-width: 50px !important;
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
        .st-key-sticky_recording_bar .stButton > button:focus-visible {
            outline: none !important;
        }

        .st-key-sticky_recording_bar .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #00E5FF, #A855F7) !important;
            color: #0b141a !important;
            border: none !important;
            border-radius: 26px !important;
            height: 50px !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            box-shadow: 0 0 20px rgba(0, 229, 255, 0.5) !important;
            transition: all 0.2s ease !important;
        }
        .st-key-sticky_recording_bar .stButton > button[kind="primary"]:hover {
            transform: scale(1.02) !important;
            box-shadow: 0 0 30px rgba(0, 229, 255, 0.8) !important;
        }

        @media (max-width: 640px) {
            .st-key-sticky_recording_bar {
                padding: 10px 12px 12px 12px !important;
                left: 0 !important;
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
        """,
        unsafe_allow_html=True,
    )


# ===========================
# FILTERS
# ===========================
def _apply_filters(results, state_filter, category_filter, occupation_filter,
                    income_filter, only_eligible_filter):
    filtered = results or []
    if state_filter and state_filter != "All":
        filtered = [
            r for r in filtered
            if _safe_str(r.get("applicable_state", "All")) in ("All", state_filter)
        ]
    if category_filter and category_filter != "All":
        cf = category_filter.lower()
        filtered = [
            r for r in filtered
            if cf in _safe_str(r.get("category_type", "")).lower()
        ]
    if occupation_filter and occupation_filter != "All":
        of = occupation_filter.lower()
        filtered = [
            r for r in filtered
            if _safe_str(r.get("occupation", "All")) == "All"
            or of in _safe_str(r.get("occupation", "")).lower()
        ]
    if income_filter and income_filter > 0:
        def _income_ok(r):
            max_income = _safe_float(r.get("max_annual_income"))
            if max_income is None:
                return True
            return max_income >= income_filter
        filtered = [r for r in filtered if _income_ok(r)]
    if only_eligible_filter:
        filtered = [r for r in filtered if r.get("eligible", True)]
    return filtered


# ===========================
# VOICE QUERY PROCESSING
# ===========================
def _process_voice_query(voice_query, df, t, lang_choice,
                          search_schemes_fn, sort_results_fn, history_module,
                          state_filter, category_filter, occupation_filter,
                          income_filter, only_eligible_filter):
    st.session_state.voice_transcript = voice_query
    st.session_state.ready_for_next = False

    with st.spinner("Schemes dhoondh rahe hain..."):
        try:
            results = search_schemes_fn(df, voice_query, top_n=50)
            results = sort_results_fn(
                results, t.get("sort_default_nl", "Best Match (default)"), t
            )
        except Exception as e:
            st.error(f"Search error: {_safe_str(e)[:120]}")
            results = []

    with st.spinner("AI results ko re-rank kar raha hai..."):
        reranked = _ai_rerank_schemes(voice_query, results, lang_choice)
        st.session_state.voice_results = reranked
        st.session_state.ai_reranked = True

    with st.spinner("Filters apply kar rahe hain..."):
        filtered = _apply_filters(reranked, state_filter, category_filter,
                                    occupation_filter, income_filter, only_eligible_filter)
        st.session_state.voice_filtered_results = filtered
        try:
            history_module.save_entry({
                "mode": "voice", "query": voice_query, "total": len(filtered)
            })
        except Exception:
            pass
        try:
            st.session_state.voice_history.append({
                "query": voice_query,
                "results": len(filtered),
                "timestamp": time.strftime("%d-%m-%Y %H:%M"),
            })
            if len(st.session_state.voice_history) > 50:
                st.session_state.voice_history = st.session_state.voice_history[-50:]
        except Exception:
            pass

    with st.spinner("Smart questions generate kar rahe hain..."):
        try:
            st.session_state.followup_questions = generate_follow_up_questions(
                voice_query, lang_choice
            )
            st.session_state.followup_for_query = voice_query
        except Exception:
            st.session_state.followup_questions = []
            st.session_state.followup_for_query = ""

    if st.session_state.auto_speak and filtered:
        try:
            summary = _build_top5_summary(filtered, lang_choice)
            audio_bytes, error = generate_audio_bytes(
                summary, lang_choice,
                st.session_state.voice_speed,
                st.session_state.voice_gender,
            )
            if audio_bytes:
                st.session_state.pending_audio = audio_bytes
        except Exception:
            pass

    st.session_state.scroll_to_results = True


def _build_top5_summary(filtered, lang_choice):
    result_count = len(filtered)

    if lang_choice == "हिंदी":
        summary = f"मुझे {result_count} योजनाएं मिलीं। टॉप पांच योजनाएं हैं: "
    elif lang_choice == "मराठी":
        summary = f"मला {result_count} योजना सापडल्या. टॉप पाच योजना आहेत: "
    elif lang_choice == "தமிழ்":
        summary = f"எனக்கு {result_count} திட்டங்கள் கிடைத்தன. சிறந்த ஐந்து: "
    else:
        summary = f"I found {result_count} schemes. Top five are: "

    top_5_names = [_safe_str(r.get("scheme_name", "")) for r in filtered[:5]]
    top_5_names = [n for n in top_5_names if n]
    if top_5_names:
        summary += ", ".join(top_5_names) + "."
    return summary


# ===========================
# STATE MANAGEMENT
# ===========================
def _init_voice_state():
    defaults = {
        "voice_transcript": "",
        "voice_results": [],
        "voice_filtered_results": [],
        "voice_history": [],
        "auto_speak": True,
        "noise_reduction_enabled": False,
        "last_audio_hash": None,
        "pending_audio": None,
        "voice_speed": 1.0,
        "voice_gender": "Female",
        "continuous_mode": False,
        "voice_round": 0,
        "followup_questions": [],
        "followup_for_query": "",
        "ai_reranked": False,
        "ready_for_next": False,
        "scroll_to_results": False,
        "show_audio_widget": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_voice_session(full_reset=False):
    st.session_state.voice_round += 1
    st.session_state.voice_transcript = ""
    st.session_state.voice_results = []
    st.session_state.voice_filtered_results = []
    st.session_state.followup_questions = []
    st.session_state.followup_for_query = ""
    st.session_state.last_audio_hash = None
    st.session_state.pending_audio = None
    st.session_state.ai_reranked = False
    st.session_state.ready_for_next = False
    st.session_state.show_audio_widget = False

    if full_reset:
        st.session_state.voice_history = []


# ===========================
# MAIN RENDER
# ===========================
def render_voice_assistant(df, t, lang_choice, search_schemes_fn,
                            sort_results_fn, render_scheme_card_fn,
                            history_module):
    """Voice Assistant v23 — main entry point."""

    _inject_voice_ui_css()
    _force_sticky_bar()
    _init_voice_state()

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
        st.markdown(
            '<div class="ready-banner">'
            '<p class="ready-title">🎤 Naya Sawaal Poochne Ke Liye Tayyar</p>'
            '<p class="ready-hint">Neeche mic dabayein aur apna sawaal bolein</p>'
            '</div>',
            unsafe_allow_html=True,
        )

    heading_html = (
        '<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;">'
        '<div style="width:40px;height:40px;border-radius:12px;'
        'background:linear-gradient(135deg,#00E5FF,#A855F7);'
        'display:flex;align-items:center;justify-content:center;'
        'font-size:1.2rem;'
        'box-shadow:0 4px 15px rgba(0,229,255,0.3);">🎤</div>'
        '<div>'
        '<div style="font-size:1.4rem;font-weight:700;color:#FAFAFA;'
        'letter-spacing:-0.3px;">Voice Assistant</div>'
        '<div style="font-size:0.8rem;color:#8696A0;margin-top:2px;">'
        'Speak your requirement — use filters to narrow down results.</div>'
        '</div>'
        '</div>'
    )
    st.markdown(heading_html, unsafe_allow_html=True)

    has_results = bool(st.session_state.voice_results)

    if has_results:
        st.markdown(
            '<div class="filters-card"><p class="filters-title">Results Filters</p></div>',
            unsafe_allow_html=True,
        )

    try:
        all_states = sorted([
            s for s in df["applicable_state"].dropna().unique()
            if s and s != "All"
        ])
        all_categories = sorted([
            c for c in df["category_type"].dropna().unique() if c
        ])
        all_occupations = sorted([
            o for o in df["occupation"].dropna().unique()
            if o and o != "All"
        ])
    except Exception:
        all_states = ["Madhya Pradesh", "Uttar Pradesh", "Bihar", "Maharashtra"]
        all_categories = ["Agriculture", "Health", "Education", "Housing", "Business/Loan"]
        all_occupations = ["Farmer", "Student", "Entrepreneur", "Unemployed Youth"]

    fcol1, fcol2 = st.columns(2)
    with fcol1:
        state_filter = st.selectbox("State", ["All"] + all_states, index=0,
                                     key="voice_filter_state")
        category_filter = st.selectbox("Category", ["All"] + all_categories, index=0,
                                        key="voice_filter_category")
    with fcol2:
        occupation_filter = st.selectbox("Occupation", ["All"] + all_occupations,
                                          index=0, key="voice_filter_occupation")
        income_filter = st.number_input(
            "Max Annual Income (₹)", min_value=0, value=0, step=50000,
            key="voice_filter_income",
        )

    only_eligible_filter = st.checkbox(
        "Only Eligible Schemes", value=False, key="voice_filter_only_eligible"
    )

    if st.button("Clear Filters", key="voice_clear_filters"):
        st.session_state.voice_filter_state = "All"
        st.session_state.voice_filter_category = "All"
        st.session_state.voice_filter_occupation = "All"
        st.session_state.voice_filter_income = 0
        st.session_state.voice_filter_only_eligible = False
        st.rerun()

    st.markdown('<div style="margin: 8px 0;"></div>', unsafe_allow_html=True)

    if has_results:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Re-apply Filters", use_container_width=True,
                         key="voice_apply_filters_btn"):
                filtered = _apply_filters(
                    st.session_state.voice_results,
                    state_filter, category_filter, occupation_filter,
                    income_filter, only_eligible_filter,
                )
                st.session_state.voice_filtered_results = filtered
                st.session_state.scroll_to_results = True
                st.rerun()
        with col2:
            if st.button("Clear Results", use_container_width=True, key="voice_clear_btn"):
                _reset_voice_session(full_reset=False)
                st.rerun()

    if st.session_state.voice_transcript:
        import html as _html
        transcript_safe = _safe_str(st.session_state.voice_transcript)
        st.markdown(
            '<div class="transcript-card">'
            '<div class="label">Aapka Sawaal</div>'
            f'<div class="text">{_html.escape(transcript_safe)}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    if (st.session_state.followup_questions
            and st.session_state.followup_for_query == st.session_state.voice_transcript):
        import html as _html
        questions_html = "".join([
            f'<div class="followup-item">▸ {_html.escape(_safe_str(q))}</div>'
            for q in st.session_state.followup_questions
        ])
        st.markdown(
            '<div class="followup-card">'
            '<div class="followup-title">Smart Follow-up Questions</div>'
            f'{questions_html}'
            '</div>',
            unsafe_allow_html=True,
        )
        if st.button("Refresh Questions", key="refresh_followups"):
            with st.spinner("Naye questions generate kar rahe hain..."):
                st.session_state.followup_questions = generate_follow_up_questions(
                    st.session_state.voice_transcript, lang_choice
                )
                st.rerun()

    display_results = (
        st.session_state.voice_filtered_results
        or st.session_state.voice_results
    )

    if display_results:
        count = len(display_results)
        active_filters = []
        if state_filter != "All":
            active_filters.append(f"State: {state_filter}")
        if category_filter != "All":
            active_filters.append(f"Category: {category_filter}")
        if occupation_filter != "All":
            active_filters.append(f"Occupation: {occupation_filter}")
        if income_filter > 0:
            active_filters.append(f"Income ≤ ₹{income_filter:,}")
        if only_eligible_filter:
            active_filters.append("Only Eligible")
        if active_filters:
            st.caption(f"Active filters: {' | '.join(active_filters)}")

        ai_badge = (
            '<span class="ai-badge">AI-RANKED</span>'
            if st.session_state.get("ai_reranked") else ''
        )
        st.markdown(
            '<div class="results-header">'
            f'<span class="count-badge">{count}</span>'
            '<span class="title">schemes mili</span>'
            f'{ai_badge}'
            '</div>',
            unsafe_allow_html=True,
        )

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Listen Top 5", use_container_width=True, key="speak_top5_btn"):
                top_5 = [
                    _safe_str(r.get("scheme_name", ""))
                    for r in display_results[:5]
                ]
                top_5 = [n for n in top_5 if n]
                if top_5:
                    if lang_choice == "हिंदी":
                        summary = "टॉप पांच योजनाएं: " + ", ".join(top_5) + "."
                    else:
                        summary = "Top five schemes: " + ", ".join(top_5) + "."
                    audio_bytes, error = generate_audio_bytes(
                        summary, lang_choice,
                        st.session_state.voice_speed,
                        st.session_state.voice_gender,
                    )
                    if audio_bytes:
                        st.session_state.pending_audio = audio_bytes
                        st.rerun()
                    elif error:
                        st.error(error)
        with col_b:
            if st.button("Listen All", use_container_width=True, key="speak_all_btn"):
                all_names = [
                    _safe_str(r.get("scheme_name", ""))
                    for r in display_results
                ]
                all_names = [n for n in all_names if n]
                if all_names:
                    if lang_choice == "हिंदी":
                        summary = f"कुल {len(all_names)} योजनाएं: " + ", ".join(all_names) + "."
                    else:
                        summary = f"Total {len(all_names)} schemes: " + ", ".join(all_names) + "."
                    audio_bytes, error = generate_audio_bytes(
                        summary, lang_choice,
                        st.session_state.voice_speed,
                        st.session_state.voice_gender,
                    )
                    if audio_bytes:
                        st.session_state.pending_audio = audio_bytes
                        st.rerun()
                    elif error:
                        st.error(error)

        if st.session_state.continuous_mode:
            st.markdown(
                '<div class="continuous-banner">'
                '<span class="pulse-dot"></span>'
                '<span class="banner-text">Continuous Mode ON — "Ask Next Question" '
                'dabakar naya sawaal poochein</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "Ask Next Question", use_container_width=True,
                key=f"continuous_next_btn_round_{st.session_state.voice_round}",
                type="primary",
            ):
                _reset_voice_session(full_reset=False)
                st.session_state.ready_for_next = True
                st.toast("Ready! Neeche mic dabakar naya sawaal poochein.", icon="🎤")
                st.rerun()

        st.write("")
        for r in display_results:
            try:
                render_scheme_card_fn(r, t, key_prefix="voice", lang_choice=lang_choice)
            except Exception as e:
                st.warning(f"Could not render a scheme card: {_safe_str(e)[:80]}")

    elif st.session_state.voice_transcript:
        st.info("Koi scheme nahi mili. Filters change karein ya alag sawaal poochhein.")

    if st.session_state.voice_history:
        with st.expander(f"Voice Search History ({len(st.session_state.voice_history)})",
                         expanded=False):
            import html as _html
            for item in reversed(st.session_state.voice_history[-10:]):
                q = _html.escape(_safe_str(item.get("query", "")))
                ts = _html.escape(_safe_str(item.get("timestamp", "")))
                n = item.get("results", 0)
                st.markdown(
                    '<div style="padding:10px 14px; margin:5px 0; '
                    'background:rgba(0,229,255,0.05); '
                    'border-left:3px solid #00E5FF; border-radius:8px;">'
                    f'<p style="margin:0; color:#8696A0; font-size:0.7rem;">{ts}</p>'
                    f'<p style="margin:5px 0 0 0; color:#FAFAFA; font-size:0.9rem; '
                    f'font-weight:500;">{q}</p>'
                    f'<p style="margin:3px 0 0 0; color:#6B7A8F; font-size:0.75rem;">'
                    f'{n} schemes</p>'
                    '</div>',
                    unsafe_allow_html=True,
                )
            if st.button("Clear History", key="clear_voice_history_btn"):
                st.session_state.voice_history = []
                st.rerun()

    st.markdown(
        '<div style="height: 140px;"></div>',
        unsafe_allow_html=True,
    )

    # =========================================================
    # STICKY BOTTOM RECORDING BAR — v21 Toggle Approach
    # =========================================================
    try:
        recording_bar = st.container(key="sticky_recording_bar")
    except Exception:
        recording_bar = st.container()

    audio_value = None
    with recording_bar:
        rec_col1, rec_col2, rec_col3 = st.columns([7, 1, 1], gap="small")

        with rec_col1:
            if not st.session_state.get("show_audio_widget", False):
                if st.button(
                    "🎤 Tap to Record",
                    key=f"start_rec_{st.session_state.voice_round}",
                    use_container_width=True,
                    type="primary",
                ):
                    st.session_state.show_audio_widget = True
                    st.rerun()
                audio_value = None
            else:
                current_round = st.session_state.get("voice_round", 0)
                try:
                    audio_value = st.audio_input(
                        "🎤 Recording",
                        key=f"voice_audio_r{current_round}",
                        label_visibility="collapsed",
                    )
                except Exception:
                    audio_value = None

        with rec_col2:
            with st.popover("⚙️", help="Voice Settings"):
                st.markdown("##### ⚙️ Voice Settings")
                st.session_state.noise_reduction_enabled = st.checkbox(
                    "🔇 Noise Reduction",
                    value=st.session_state.noise_reduction_enabled,
                    key="nr_popover",
                )
                st.session_state.auto_speak = st.checkbox(
                    "🔊 Auto Voice Response",
                    value=st.session_state.auto_speak,
                    key="as_popover",
                )
                st.divider()
                st.session_state.voice_speed = st.slider(
                    "🎚️ Voice Speed",
                    min_value=0.5, max_value=2.0,
                    value=st.session_state.voice_speed,
                    step=0.1, key="vs_popover",
                )
                st.session_state.voice_gender = st.selectbox(
                    "🎭 Voice Type",
                    ["Female", "Male"],
                    index=0 if st.session_state.voice_gender == "Female" else 1,
                    key="vg_popover",
                )
                st.divider()
                st.session_state.continuous_mode = st.checkbox(
                    "🔄 Continuous Mode",
                    value=st.session_state.continuous_mode,
                    key="cm_popover",
                )

        with rec_col3:
            if st.button("🔄", help="Reset", key="reset_btn_bottom"):
                _reset_voice_session(full_reset=False)
                st.rerun()

    # =========================================================
    # PROCESS AUDIO
    # =========================================================
    if audio_value is not None:
        audio_bytes_temp = None
        audio_hash = None
        try:
            audio_bytes_temp = audio_value.read()
            audio_value.seek(0)
            audio_hash = hash(audio_bytes_temp)
        except Exception:
            st.session_state.show_audio_widget = False
            st.session_state.voice_round += 1
            st.session_state.last_audio_hash = None
            audio_hash = None

        if audio_hash is not None and audio_hash == st.session_state.last_audio_hash:
            audio_hash = None

        if audio_hash is not None:
            st.session_state.last_audio_hash = audio_hash
            with st.spinner("Sun rahe hain aur text mein badal rahe hain..."):
                try:
                    transcript = _transcribe_audio(
                        audio_bytes_temp,
                        lang_choice,
                        apply_noise_reduction=st.session_state.noise_reduction_enabled,
                    )
                    if transcript and transcript.strip():
                        _process_voice_query(
                            transcript.strip(), df, t, lang_choice,
                            search_schemes_fn, sort_results_fn, history_module,
                            state_filter, category_filter, occupation_filter,
                            income_filter, only_eligible_filter,
                        )

                    st.session_state.show_audio_widget = False
                    st.session_state.voice_round += 1
                    st.session_state.last_audio_hash = None
                    st.rerun()

                except RuntimeError as e:
                    st.session_state.show_audio_widget = False
                    st.session_state.voice_round += 1
                    st.session_state.last_audio_hash = None
                    st.warning(f"🎤 {_safe_str(e)}")
                    st.rerun()

                except Exception as e:
                    st.session_state.show_audio_widget = False
                    st.session_state.voice_round += 1
                    st.session_state.last_audio_hash = None
                    st.error("⚠️ Voice error. Please try again.")
                    print(f"[voice_assistant] Processing failed: {type(e).__name__}: {e}")
                    st.rerun()


# ===========================
# SELF-TEST
# ===========================
def _run_self_tests():
    print("=" * 60)
    print("voice_assistant.py — v23 Verification")
    print("=" * 60)

    print("\n[Test 1] _safe_str:")
    assert _safe_str(None) == ""
    assert _safe_str(float("nan")) == ""
    assert _safe_str("test") == "test"
    print("  ✅ All cases pass")

    print("\n[Test 2] _safe_float:")
    assert _safe_float(None) is None
    assert _safe_float("") is None
    assert _safe_float("   ") is None
    assert _safe_float("abc") is None
    assert _safe_float("123.5") == 123.5
    assert _safe_float(50000) == 50000
    print("  ✅ Empty string returns None (not crash)")

    print("\n[Test 3] _clean_text_for_tts:")
    dirty = "PM Kisan ✅ Yojana 🎉 ₹6000"
    clean = _clean_text_for_tts(dirty, "English")
    assert "✅" not in clean and "🎉" not in clean
    print(f"  ✅ '{dirty}' → '{clean}'")

    print("\n[Test 4] _build_top5_summary (all languages):")
    filtered = [
        {"scheme_name": "Scheme A"},
        {"scheme_name": "Scheme B"},
        {"scheme_name": "Scheme C"},
    ]
    s_en = _build_top5_summary(filtered, "English")
    s_hi = _build_top5_summary(filtered, "हिंदी")
    s_mr = _build_top5_summary(filtered, "मराठी")
    s_ta = _build_top5_summary(filtered, "தமிழ்")
    assert "3 schemes" in s_en
    assert "3 योजनाएं" in s_hi
    assert "3 योजना" in s_mr
    assert "3 திட்டங்கள்" in s_ta
    print("  ✅ All 4 languages supported")

    print("\n[Test 5] _apply_filters:")
    results = [
        {"scheme_name": "A", "applicable_state": "All", "category_type": "Health",
         "occupation": "All", "max_annual_income": ""},
        {"scheme_name": "B", "applicable_state": "All", "category_type": "Health",
         "occupation": "All", "max_annual_income": "100000"},
        {"scheme_name": "C", "applicable_state": "All", "category_type": "Education",
         "occupation": "All", "max_annual_income": None},
    ]
    filtered = _apply_filters(results, "All", "All", "All", 50000, False)
    assert len(filtered) == 3
    print("  ✅ Empty-string income handled")

    print("\n[Test 6] State filter:")
    results = [
        {"scheme_name": "A", "applicable_state": "All"},
        {"scheme_name": "B", "applicable_state": "Madhya Pradesh"},
        {"scheme_name": "C", "applicable_state": "Uttar Pradesh"},
    ]
    filtered = _apply_filters(results, "Madhya Pradesh", "All", "All", 0, False)
    assert len(filtered) == 2
    print(f"  ✅ Filter keeps 'All' + MP: {len(filtered)} results")

    print("\n[Test 7] Dead variables removed:")
    import inspect
    src = inspect.getsource(__import__(__name__))
    assert "audio_attempt" not in src, "audio_attempt should be removed (dead var)"
    print("  ✅ 'audio_attempt' dead variable removed")

    print("\n[Test 8] v22 timeout check:")
    assert "timeout=5" in src, "timeout=5 should be present in v22"
    print("  ✅ timeout=5 found in source")

    print("\n[Test 9] v23 — _get_cached_llm NOT decorated with @st.cache_resource:")
    llm_src = inspect.getsource(_get_cached_llm)
    first_line = llm_src.split("\n")[0].strip()
    assert not first_line.startswith("@st.cache_resource"), \
        f"_get_cached_llm still has @st.cache_resource decorator: {first_line}"
    print("  ✅ _get_cached_llm() decorator-free (v23 fix intact)")

    print("\n[Test 10] Optional dependencies:")
    print(f"  gTTS:              {_GTTS_AVAILABLE}")
    print(f"  edge-tts:          {_EDGE_TTS_AVAILABLE}")
    print(f"  SpeechRecognition: {_SR_AVAILABLE}")
    print(f"  noisereduce:       {_NOISE_REDUCE_AVAILABLE}")
    print(f"  pydub:             {_PYDUB_AVAILABLE}")
    print(f"  GROQ_MODEL:        {DEFAULT_GROQ_MODEL}")

    print("\n[Test 11] _convert_to_wav helper exists:")
    assert callable(_convert_to_wav)
    out = _convert_to_wav(b"garbage")
    assert out == b"garbage"
    print("  ✅ Conversion graceful on failure")

    print("\n[Test 12] _get_cached_llm returns None without API key:")
    # Temporarily remove API key to verify behavior
    old_key = os.environ.pop("GROQ_API_KEY", None)
    try:
        result = _get_cached_llm()
        assert result is None
        print("  ✅ Returns None without API key")
    finally:
        if old_key is not None:
            os.environ["GROQ_API_KEY"] = old_key

    print("\n" + "=" * 60)
    print("✅ voice_assistant.py v23 — ALL CHECKS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    _run_self_tests()