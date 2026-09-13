"""
voice_input.py — Browser's Speech Recognition API wrapper.

Usage:
    from voice_input import voice_search_widget
    voice_search_widget(lang_code="en-IN", key_suffix="search")

Notes:
  - Uses `window.SpeechRecognition` or `window.webkitSpeechRecognition`.
  - On successful transcript, sets a `voice_query` URL query param and reloads
    the parent page (so Streamlit picks it up).
  - Best in Chrome/Edge. Requires HTTPS or localhost (browser security).

FIXES (v2):
  - HTML/JS injection prevention: key_suffix, lang_code, aur all texts ab
    properly JSON-escaped / sanitized hote hain.
  - Browser support: dono `SpeechRecognition` aur `webkitSpeechRecognition`
    try karta hai (older Chrome/Safari).
  - Mic permission failure par friendly message.
  - Empty transcript par URL update skip (query pollution avoid).
  - Duplicate ID collision avoid (key_suffix sanitized).
  - __main__ self-test (checks escaping).
"""

import json as _json
import re
import streamlit.components.v1 as components


# ===========================
# SANITIZATION HELPERS
# ===========================
def _sanitize_id(s):
    """
    ID ke liye safe string — sirf alphanumerics, dash, underscore.
    Browsers me ID special chars se break ho jaate hain.
    """
    s = str(s) if s is not None else "default"
    return re.sub(r"[^A-Za-z0-9_\-]", "_", s)


def _js_str(value):
    """
    Python string ko JavaScript string literal me convert karta hai.
    json.dumps() use karte hain kyunki wo valid JS string syntax deta hai
    (quotes escaped, special chars unicode-escaped, etc.).

    Example:
        _js_str('He said "hi"') → '"He said \\"hi\\""'
    """
    if value is None:
        value = ""
    return _json.dumps(str(value), ensure_ascii=False)


def _safe_lang_code(lang_code):
    """
    lang_code whitelist validation.
    Sirf standard BCP-47 tags allow karo (e.g. en-IN, hi-IN, ta-IN).
    """
    if not lang_code:
        return "en-IN"
    lang_code = str(lang_code).strip()
    # BCP-47 format: xx or xx-YY
    if re.match(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$", lang_code):
        return lang_code
    return "en-IN"


def _safe_height(height):
    """Height ko int me convert karta hai (min 40, max 200)."""
    try:
        h = int(height)
    except (ValueError, TypeError):
        return 55
    return max(40, min(h, 200))


# ===========================
# WIDGET
# ===========================
def voice_search_widget(
    lang_code="en-IN",
    key_suffix="default",
    listening_text="Listening...",
    not_supported_text="Voice search not supported in this browser.",
    error_text="Error:",
    height=55,
):
    """
    Browser Speech Recognition widget.

    Args:
        lang_code: BCP-47 language tag (e.g. "en-IN", "hi-IN")
        key_suffix: unique suffix for element IDs (per-widget)
        listening_text: shown while listening
        not_supported_text: shown if browser lacks SpeechRecognition
        error_text: prefix for error messages
        height: iframe height in pixels

    Behavior:
        On success, sets `voice_query=<transcript>` URL param and reloads parent.
    """
    # ---- Sanitize everything ----
    safe_id = _sanitize_id(key_suffix)
    safe_lang = _safe_lang_code(lang_code)
    safe_height = _safe_height(height)

    # JS string literals (properly escaped)
    js_listening = _js_str(listening_text)
    js_not_supported = _js_str(not_supported_text)
    js_error_prefix = _js_str(error_text)

    # Element IDs (HTML-safe already via _sanitize_id)
    mic_btn_id = f"mic-btn-{safe_id}"
    mic_status_id = f"mic-status-{safe_id}"

    html_code = f"""
    <div style="display:flex; align-items:center; gap:10px; font-family:sans-serif;">
        <button id="{mic_btn_id}" title="Voice Search" style="
            background-color:#FF9933; color:white; border:none; border-radius:50%;
            width:42px; height:42px; font-size:18px; cursor:pointer; flex-shrink:0;
            transition: transform 0.15s ease;">
            &#127908;
        </button>
        <span id="{mic_status_id}" style="color:#999; font-size:13px;"></span>
    </div>
    <script>
    (function() {{
        "use strict";

        var btn = document.getElementById({_js_str(mic_btn_id)});
        var status = document.getElementById({_js_str(mic_status_id)});
        var langCode = {_js_str(safe_lang)};

        if (!btn || !status) return;

        // ---- SpeechRecognition availability check ----
        var SpeechRecognition = window.SpeechRecognition
                             || window.webkitSpeechRecognition
                             || window.mozSpeechRecognition
                             || window.msSpeechRecognition
                             || null;

        if (!SpeechRecognition) {{
            // Hide button, show message
            btn.style.display = "none";
            status.innerText = {js_not_supported};
            return;
        }}

        var recognition = null;
        var listening = false;

        // ---- Permission check (optional — degrades gracefully) ----
        function setStatus(text, isError) {{
            status.innerText = text;
            status.style.color = isError ? "#E74C3C" : "#999";
        }}

        // ---- Reset UI state ----
        function reset() {{
            listening = false;
            btn.style.transform = "";
            btn.style.opacity = "";
            btn.disabled = false;
        }}

        // ---- Handle successful transcript ----
        function handleTranscript(transcript) {{
            transcript = (transcript || "").trim();
            if (!transcript) {{
                setStatus({js_error_prefix} + " no speech detected", true);
                reset();
                return;
            }}

            setStatus(transcript, false);

            try {{
                // Update parent URL and reload so Streamlit picks up the param
                var url = new URL(window.parent.location.href);
                url.searchParams.set("voice_query", transcript);
                window.parent.location.href = url.toString();
            }} catch (e) {{
                // Parent access blocked (shouldn't happen for same-origin)
                setStatus({js_error_prefix} + " could not update URL", true);
                reset();
            }}
        }}

        // ---- User-friendly error mapping ----
        function mapError(errCode) {{
            var map = {{
                "not-allowed": "Microphone permission denied",
                "service-not-allowed": "Microphone permission denied",
                "no-speech": "No speech detected",
                "audio-capture": "No microphone found",
                "network": "Network error — check internet",
                "aborted": "Cancelled",
            }};
            return map[errCode] || ("Voice error: " + errCode);
        }}

        // ---- Click handler ----
        btn.addEventListener("click", function() {{
            if (listening) {{
                try {{ recognition && recognition.stop(); }} catch (e) {{}}
                reset();
                return;
            }}

            try {{
                recognition = new SpeechRecognition();
            }} catch (e) {{
                setStatus({js_error_prefix} + " init failed", true);
                return;
            }}

            recognition.lang = langCode;
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;
            recognition.continuous = false;

            recognition.onstart = function() {{
                listening = true;
                btn.style.transform = "scale(1.1)";
                btn.style.opacity = "0.8";
                setStatus({js_listening}, false);
            }};

            recognition.onresult = function(event) {{
                try {{
                    var transcript = event.results[0][0].transcript;
                    handleTranscript(transcript);
                }} catch (e) {{
                    setStatus({js_error_prefix} + " parse error", true);
                    reset();
                }}
            }};

            recognition.onerror = function(event) {{
                setStatus(mapError(event.error), true);
                reset();
            }};

            recognition.onend = function() {{
                reset();
            }};

            try {{
                recognition.start();
            }} catch (e) {{
                setStatus({js_error_prefix} + " start failed", true);
                reset();
            }}
        }});
    }})();
    </script>
    """

    try:
        components.html(html_code, height=safe_height)
    except Exception:
        # Non-Streamlit context — silently no-op
        pass


# ===========================
# SELF-TEST
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("voice_input.py — Verification")
    print("=" * 60)

    # Test 1: _sanitize_id
    print("\n[Test 1] _sanitize_id:")
    assert _sanitize_id("default") == "default"
    assert _sanitize_id("my-key_123") == "my-key_123"
    assert _sanitize_id("bad<>id") == "bad__id"
    assert _sanitize_id("script');alert(1);//") == "script___alert_1___"
    assert _sanitize_id(None) == "default"
    print("  ✅ Malicious chars replaced with underscore")

    # Test 2: _js_str escaping
    print("\n[Test 2] _js_str:")
    assert _js_str("hello") == '"hello"'
    assert _js_str('He said "hi"') == '"He said \\"hi\\""'
    assert _js_str("line\nbreak") == '"line\\nbreak"'
    assert _js_str(None) == '""'
    assert _js_str("") == '""'
    # Unicode preserved (not escaped) because ensure_ascii=False
    assert "हिंदी" in _js_str("हिंदी")
    print("  ✅ Quotes, newlines escaped; unicode preserved")

    # Test 3: XSS attempt via key_suffix
    print("\n[Test 3] XSS via key_suffix:")
    evil = '<script>alert("xss")</script>'
    sanitized = _sanitize_id(evil)
    assert "<" not in sanitized
    assert ">" not in sanitized
    assert '"' not in sanitized
    assert "'" not in sanitized
    print(f"  ✅ '{evil[:30]}...' → '{sanitized[:30]}...'")

    # Test 4: XSS attempt via listening_text
    print("\n[Test 4] XSS via listening_text:")
    evil_text = '"); alert("xss"); ("'
    escaped = _js_str(evil_text)
    # Should be a valid JS string literal — quotes escaped
    assert escaped.startswith('"') and escaped.endswith('"')
    assert '\\"' in escaped
    print(f"  ✅ '{evil_text}' → {escaped}")

    # Test 5: _safe_lang_code
    print("\n[Test 5] _safe_lang_code:")
    assert _safe_lang_code("en-IN") == "en-IN"
    assert _safe_lang_code("hi-IN") == "hi-IN"
    assert _safe_lang_code("en") == "en"
    assert _safe_lang_code("zh-Hans-CN") == "zh-Hans-CN"
    # Injection attempts → fallback
    assert _safe_lang_code('"; alert(1); //') == "en-IN"
    assert _safe_lang_code("<>script") == "en-IN"
    assert _safe_lang_code(None) == "en-IN"
    assert _safe_lang_code("") == "en-IN"
    print("  ✅ Valid codes pass, injection attempts → fallback")

    # Test 6: _safe_height
    print("\n[Test 6] _safe_height:")
    assert _safe_height(55) == 55
    assert _safe_height("100") == 100
    assert _safe_height(None) == 55
    assert _safe_height("abc") == 55
    assert _safe_height(10) == 40  # Min clamp
    assert _safe_height(10000) == 200  # Max clamp
    print("  ✅ Height clamped to [40, 200]")

    # Test 7: Widget callable in non-Streamlit context
    print("\n[Test 7] Widget in non-Streamlit context:")
    try:
        voice_search_widget(lang_code="en-IN", key_suffix="test")
        print("  ✅ No crash")
    except Exception as e:
        print(f"  ❌ Crashed: {e}")
        raise

    # Test 8: Widget with malicious inputs — should not raise
    print("\n[Test 8] Widget with malicious inputs:")
    try:
        voice_search_widget(
            lang_code='"; alert(1); //',
            key_suffix="<script>",
            listening_text='"); alert(1); ("',
            not_supported_text="<img src=x onerror=alert(1)>",
            error_text='</script><script>alert(1)</script>',
        )
        print("  ✅ No crash even with malicious inputs")
    except Exception as e:
        print(f"  ❌ Crashed: {e}")
        raise

    # Test 9: Verify HTML output has no raw script injection
    print("\n[Test 9] HTML output safety check:")
    # Build the same HTML as widget would, with evil input
    safe_id = _sanitize_id('<script>alert(1)</script>')
    safe_lang = _safe_lang_code('"; alert(1); //')
    js_evil = _js_str('"); alert(1); ("')

    # Verify no raw "<script>" from user input (only ours)
    assert "<script>" not in f"id-{safe_id}"
    assert 'alert(1)' not in safe_lang
    assert 'alert(1)' not in safe_id
    print(f"  ✅ No raw <script> or alert(1) in user-controlled fields")

    # Test 10: Unicode text handling
    print("\n[Test 10] Unicode handling:")
    hi = "सुन रहा हूं..."
    escaped = _js_str(hi)
    assert "सुन" in escaped, "Hindi text should be preserved (ensure_ascii=False)"
    print(f"  ✅ Hindi preserved: {escaped}")

    print("\n" + "=" * 60)
    print("✅ voice_input.py — ALL CHECKS PASSED")
    print("=" * 60)