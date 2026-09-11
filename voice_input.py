"""
Voice input - browser ke built-in Speech Recognition API use karta hai.
"""

import streamlit.components.v1 as components


def voice_search_widget(lang_code="en-IN", key_suffix="default",
                         listening_text="Listening...",
                         not_supported_text="Voice search not supported in this browser.",
                         error_text="Error:"):
    html_code = f"""
    <div style="display:flex; align-items:center; gap:10px; font-family:sans-serif;">
        <button id="mic-btn-{key_suffix}" title="Voice Search" style="
            background-color:#FF9933; color:white; border:none; border-radius:50%;
            width:42px; height:42px; font-size:18px; cursor:pointer; flex-shrink:0;">
            &#127908;
        </button>
        <span id="mic-status-{key_suffix}" style="color:#999; font-size:13px;"></span>
    </div>
    <script>
    (function() {{
        const btn = document.getElementById("mic-btn-{key_suffix}");
        const status = document.getElementById("mic-status-{key_suffix}");
        btn.addEventListener("click", function() {{
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            if (!SpeechRecognition) {{
                status.innerText = "{not_supported_text}";
                return;
            }}
            const recognition = new SpeechRecognition();
            recognition.lang = "{lang_code}";
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;
            status.innerText = "{listening_text}";
            recognition.start();

            recognition.onresult = function(event) {{
                const text = event.results[0][0].transcript;
                status.innerText = text;
                const url = new URL(window.parent.location.href);
                url.searchParams.set("voice_query", text);
                window.parent.location.href = url.toString();
            }};
            recognition.onerror = function(event) {{
                status.innerText = "{error_text} " + event.error;
            }};
        }});
    }})();
    </script>
    """
    components.html(html_code, height=55)