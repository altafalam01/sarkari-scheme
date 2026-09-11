"""
FAQ content - bilingual list of (question, answer) pairs.
"""

FAQ_DATA = {
    "English": [
        ("How do I verify my eligibility for a scheme?",
         "This app gives you a quick, guided estimate based on the info you enter "
         "(age, income, state, category, etc.). It is NOT an official verification. "
         "Before applying, always confirm the exact eligibility criteria on the "
         "scheme's official government website — the Apply link on every scheme "
         "card takes you there."),
        ("Is this an official government app?",
         "No. This is an independent student project built to help people quickly "
         "browse government schemes. It is not affiliated with, endorsed by, or "
         "connected to any government department."),
        ("How accurate is the scheme data?",
         "The scheme details (eligibility, benefits, links) were compiled manually "
         "and are not scraped or verified against a live government database. "
         "Treat this as a helpful starting point, not a final source of truth."),
        ("What documents do I need to apply?",
         "Each scheme card has a 'Documents Required' section with commonly needed "
         "documents for that category (like Aadhaar Card, income certificate, etc). "
         "This is general guidance, not a verified per-scheme list — always check "
         "the official site for the exact requirements."),
        ("What's the difference between 'Eligibility Check' and 'Search Schemes'?",
         "'Eligibility Check' asks for your profile (age, income, state, etc.) and "
         "shows every scheme with a clear ELIGIBLE / NOT ELIGIBLE badge. "
         "'Search Schemes' lets you type what you're looking for in plain words "
         "(like 'scholarship for my daughter') and finds the most relevant matches — "
         "it does not check your personal eligibility."),
        ("How do Favorites work?",
         "Tap the star icon on any scheme card to save it. All saved schemes appear "
         "under the 'Favorites' section in the sidebar so you can find them again "
         "quickly."),
        ("Will Reminders send me a notification?",
         "No. This app only runs when you open it yourself — it cannot send push "
         "notifications to your phone or computer. A reminder you set will simply "
         "be visible in the 'Reminders' section the next time you open the app."),
        ("Can I use this app in Hindi?",
         "Yes. Use the language dropdown at the top of the sidebar to switch between "
         "English and Hindi. Note that the underlying scheme data (descriptions, "
         "benefits) stays in English since that's how it was originally compiled."),
        ("Does this work on my phone?",
         "Yes, the layout adjusts for smaller screens. If you're running the app "
         "on your computer, your phone needs to be on the same Wi-Fi/hotspot network "
         "to open it using your computer's local network address."),
        ("How does voice search work?",
         "Tap the microphone icon in 'Search Schemes' mode and speak your query. "
         "It uses your browser's built-in speech recognition, so it works best in "
         "Chrome or Edge, needs microphone permission, and needs an internet "
         "connection."),
    ],
    "हिंदी": [
        ("मैं किसी योजना के लिए अपनी पात्रता कैसे जांचूं?",
         "यह ऐप आपकी दी गई जानकारी (आयु, आय, राज्य, श्रेणी आदि) के आधार पर एक त्वरित, "
         "मार्गदर्शक अनुमान देता है। यह आधिकारिक सत्यापन नहीं है। आवेदन करने से पहले, हमेशा "
         "योजना की आधिकारिक सरकारी वेबसाइट पर सटीक पात्रता मानदंड की पुष्टि करें — हर "
         "योजना कार्ड पर दिया गया 'आवेदन करें' लिंक आपको वहां ले जाता है।"),
        ("क्या यह एक आधिकारिक सरकारी ऐप है?",
         "नहीं। यह लोगों को सरकारी योजनाओं को जल्दी देखने में मदद करने के लिए बनाया गया एक "
         "स्वतंत्र छात्र प्रोजेक्ट है। यह किसी भी सरकारी विभाग से संबद्ध, अनुमोदित या जुड़ा हुआ नहीं है।"),
        ("योजना का डेटा कितना सटीक है?",
         "योजना का विवरण (पात्रता, लाभ, लिंक) मैन्युअल रूप से तैयार किया गया है और इसे किसी "
         "लाइव सरकारी डेटाबेस से स्क्रैप या सत्यापित नहीं किया गया है। इसे एक सहायक शुरुआती "
         "बिंदु मानें, अंतिम स्रोत नहीं।"),
        ("आवेदन करने के लिए मुझे कौन से दस्तावेज़ चाहिए?",
         "हर योजना कार्ड में 'आवश्यक दस्तावेज़' सेक्शन है जिसमें उस श्रेणी के लिए सामान्यतः "
         "जरूरी दस्तावेज़ (जैसे आधार कार्ड, आय प्रमाण पत्र) दिए गए हैं। यह सामान्य मार्गदर्शन है, "
         "सत्यापित सूची नहीं — सटीक जरूरतों के लिए हमेशा आधिकारिक वेबसाइट देखें।"),
        ("'पात्रता जांच' और 'योजनाएं खोजें' में क्या अंतर है?",
         "'पात्रता जांच' आपकी प्रोफाइल (आयु, आय, राज्य आदि) पूछता है और हर योजना को साफ "
         "'पात्र / अपात्र' बैज के साथ दिखाता है। 'योजनाएं खोजें' में आप सामान्य भाषा में लिख "
         "सकते हैं (जैसे 'बेटी की पढ़ाई के लिए छात्रवृत्ति') और सबसे प्रासंगिक योजनाएं मिलती हैं — "
         "यह आपकी व्यक्तिगत पात्रता जांच नहीं करता।"),
        ("पसंदीदा (Favorites) कैसे काम करता है?",
         "किसी भी योजना कार्ड पर स्टार आइकन दबाकर उसे सेव करें। सभी सेव की गई योजनाएं साइडबार "
         "के 'पसंदीदा' सेक्शन में दिखेंगी ताकि आप उन्हें दोबारा आसानी से खोज सकें।"),
        ("क्या रिमाइंडर मुझे notification भेजेगा?",
         "नहीं। यह ऐप तभी चलता है जब आप इसे खुद खोलते हैं — यह आपके फोन या कंप्यूटर पर push "
         "notification नहीं भेज सकता। आपका सेट किया गया रिमाइंडर अगली बार ऐप खोलने पर "
         "'रिमाइंडर' सेक्शन में दिख जाएगा।"),
        ("क्या मैं इस ऐप को हिंदी में उपयोग कर सकता हूं?",
         "हां। साइडबार के ऊपर भाषा ड्रॉपडाउन से अंग्रेज़ी और हिंदी के बीच स्विच करें। ध्यान दें "
         "कि योजना का मूल डेटा (विवरण, लाभ) अंग्रेज़ी में ही रहेगा क्योंकि यह मूल रूप से उसी "
         "भाषा में तैयार किया गया था।"),
        ("क्या यह मेरे फोन पर काम करेगा?",
         "हां, छोटी स्क्रीन के लिए लेआउट अपने आप एडजस्ट हो जाता है। अगर ऐप कंप्यूटर पर चल रही "
         "है, तो उसे अपने कंप्यूटर के लोकल नेटवर्क एड्रेस से खोलने के लिए फोन को उसी Wi-Fi/हॉटस्पॉट "
         "पर होना चाहिए।"),
        ("वॉइस सर्च कैसे काम करता है?",
         "'योजनाएं खोजें' मोड में माइक्रोफ़ोन आइकन दबाएं और अपना सवाल बोलें। यह आपके ब्राउज़र "
         "की बिल्ट-इन स्पीच रिकग्निशन का उपयोग करता है, इसलिए यह Chrome या Edge में सबसे "
         "अच्छा काम करता है, माइक्रोफ़ोन की अनुमति चाहिए, और इंटरनेट कनेक्शन आवश्यक है।"),
    ],
}


def get_faqs(lang):
    return FAQ_DATA.get(lang, FAQ_DATA["English"])