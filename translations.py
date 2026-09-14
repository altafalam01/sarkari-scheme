"""
translations.py — UI text translations for English and Hindi.

FIXES (v4):
  - v10 "My Documents" feature ke liye 25+ nayi keys add ki (both languages):
      mode_documents, docs_page_title, docs_page_caption, docs_form_heading,
      docs_form_hint, docs_save_btn, docs_saved_msg, docs_clear_btn,
      docs_cleared_msg, docs_empty_warning, docs_copy_section, docs_copy_hint,
      docs_bookmarklet_section, docs_bookmarklet_hint, docs_step_1..4,
      docs_drag_here, docs_bookmarklet_warning, docs_regenerate_hint,
      docs_no_bookmarklet
  - Self-test ab in naye keys ko bhi check karta hai.
  - v3, v2 ke saare fixes intact.

FIXES (v3, inherited):
  - "Alerts & Reminders" merge ke saare keys intact
  - "mode_reminders" key retained (backward compat)
"""

TRANSLATIONS = {
    "English": {
        # ===========================
        # Basic Info
        # ===========================
        "title": "Sarkari Scheme",
        "subtitle": "Find government schemes you're eligible for",
        "disclaimer": "This tool is for guidance only.",

        # ===========================
        # Form Fields
        # ===========================
        "age": "Age",
        "gender": "Gender",
        "occupation": "Occupation",
        "income": "Annual Family Income (Rs)",
        "category": "Social Category",
        "state": "State",
        "scheme_category": "Scheme Category (optional filter)",
        "only_eligible": "Show only eligible schemes",
        "search_btn": "Find Schemes",

        # ===========================
        # Result Labels
        # ===========================
        "all": "All",
        "total_shown": "Total Shown",
        "eligible_label": "Eligible",
        "not_eligible_label": "Not Eligible",
        "no_results": "No schemes matched your profile.",
        "what_is": "What is it",
        "benefit": "Benefit",
        "eligibility_breakdown": "Eligibility Breakdown",
        "apply_btn": "Apply Here",
        "eligible_badge": "ELIGIBLE",
        "not_eligible_badge": "NOT ELIGIBLE",
        "hint": "Fill your profile in the sidebar and press 'Find Schemes'.",

        # ===========================
        # Sidebar / Navigation
        # ===========================
        "language_label": "Language / भाषा",
        "mode_label": "Search Mode",
        "mode_form": "Eligibility Check",
        "mode_nl": "Search Schemes",
        "mode_favorites": "Favorites",
        "mode_reminders": "Reminders",          # kept for backward-compat redirect
        "mode_history": "Search History",
        "mode_faq": "FAQ",
        "mode_csc": "CSC Locator",
        "mode_dashboard": "Dashboard",
        "mode_settings": "Settings",
        "mode_notifications": "Alerts & Reminders",   # v8: renamed (merged page)
        "mode_admin": "Admin Panel",
        "mode_assistant": "AI Assistant",
        "mode_voice_assistant": "Voice Assistant",
        "mode_documents": "My Documents",        # v10: NEW

        # ===========================
        # My Documents (v10 Bookmarklet Auto-Fill)
        # ===========================
        "docs_page_title": "My Documents Vault",
        "docs_page_caption": "Apna personal data ek baar bharein — phir kisi bhi govt site par auto-fill karein",
        "docs_form_heading": "📋 Personal Information",
        "docs_form_hint": "Ye data sirf aapke computer par save hota hai. Kisi server par nahi jaata.",
        "docs_save_btn": "💾 Save Documents",
        "docs_saved_msg": "✅ Documents saved successfully!",
        "docs_clear_btn": "🗑️ Clear All Documents",
        "docs_cleared_msg": "🗑️ All documents cleared",
        "docs_empty_warning": "⚠️ Pehle upar form bhar ke Save karein, phir bookmarklet generate hoga",
        "docs_copy_section": "📄 Copy Buttons",
        "docs_copy_hint": "Kabhi-kabhi bookmarklet kaam nahi karta (CSP block). Aise waqt mein ye buttons use karein:",
        "docs_bookmarklet_section": "⚡ Bookmarklet (Auto-Fill)",
        "docs_bookmarklet_hint": "Ye ek chhota JavaScript hai. Ise bookmarks bar mein drag karke rakhein. Kisi bhi govt site par form fill karte waqt click karein — ek floating panel khulega jisme har field ka button hoga.",
        "docs_step_1": "1️⃣ Neeche wale button ko apne browser ke bookmarks bar mein DRAG karein (click nahi, drag)",
        "docs_step_2": "2️⃣ Bookmarks bar dikhana hai to Ctrl+Shift+B dabayein (Chrome/Edge)",
        "docs_step_3": "3️⃣ Kisi bhi govt site par form kholo, aur uska input box pehle click karo (cursor wahan rakh do)",
        "docs_step_4": "4️⃣ Bookmarks bar mein '⚡ Fill Form' par click karo — panel khulega, phir field button dabao",
        "docs_drag_here": "⚡ Fill Form — Drag this to Bookmarks Bar",
        "docs_bookmarklet_warning": "⚠️ Bookmarklet mein aapka data base64-encoded hai (plain text nahi). Lekin ye aapke browser ke bookmarks mein save hota hai — apna browser/profile kisi ke saath share na karein.",
        "docs_regenerate_hint": "🔄 Agar aapne upar data update kiya hai, to yahan bookmarklet dobara drag karein (purana delete karke)",
        "docs_no_bookmarklet": "Bookmarklet generate karne ke liye pehle upar data save karein.",

        # ===========================
        # Alerts & Reminders (v8 merged page)
        # ===========================
        "alerts_page_title": "Alerts & Reminders",
        "alerts_page_caption": "Your reminders + favorite-scheme deadlines",
        "alerts_tab_reminders": "⏰ My Reminders",
        "alerts_tab_deadlines": "⭐ Deadline Alerts",
        "alerts_tab_all": "📋 All Alerts",
        "alerts_no_items": "No reminders or deadline alerts yet. Favorite some schemes or set reminders.",
        "alerts_urgent_count": "{count} urgent items",
        "alerts_load_more": "Load More Reminders",

        # ===========================
        # Natural Language Search
        # ===========================
        "nl_placeholder": "e.g. I need a scholarship for my daughter's education",
        "nl_search_btn": "Search",
        "nl_matches_found": "schemes found",
        "nl_no_results": "No matching schemes found.",
        "nl_note": "This search only shows relevant schemes.",
        "nl_hint": "Type what you're looking for and press Search.",
        "suggestions_label": "Suggestions:",

        # ===========================
        # History
        # ===========================
        "history_title": "Your Past Searches",
        "history_empty": "No searches yet.",
        "history_clear_btn": "Clear All History",
        "history_cleared_msg": "History cleared.",
        "history_form_summary": "Eligibility Check — Age {age}, {state}",
        "history_nl_summary": "Searched: \"{query}\"",

        # ===========================
        # Theme & Sorting
        # ===========================
        "theme_label": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "sort_label": "Sort By",
        "sort_default_form": "Eligibility (default)",
        "sort_default_nl": "Best Match (default)",
        "sort_name": "Name (A-Z)",
        "sort_category": "Category",
        "sort_state": "State",

        # ===========================
        # Share & PDF
        # ===========================
        "pdf_download_btn": "Download PDF Report",
        "share_label": "Share",
        "share_copy_label": "Or copy this message:",
        "share_app_btn": "Share this App",
        "app_share_message": "Check out this app to find government schemes!",

        # ===========================
        # Favorites
        # ===========================
        "favorites_title": "Your Favorite Schemes",
        "favorites_empty": "No favorites yet.",
        "fav_add_tooltip": "Add to Favorites",
        "fav_remove_tooltip": "Remove from Favorites",
        "fav_added_toast": "⭐ Added to Favorites",
        "fav_removed_toast": "Removed from Favorites",

        # ===========================
        # Documents
        # ===========================
        "documents_required_label": "Documents Required",
        "documents_disclaimer": "General guidance.",

        # ===========================
        # Reminders
        # ===========================
        "reminder_label": "Reminder",
        "set_reminder_label": "Set a reminder date",
        "reminder_note_placeholder": "Optional note",
        "save_reminder_btn": "Save Reminder",
        "remove_reminder_btn": "Remove Reminder",
        "reminder_saved_msg": "Reminder saved.",
        "reminder_saved_toast": "⏰ Reminder Saved",
        "reminder_removed_toast": "🗑️ Reminder Removed",
        "reminder_date_warning": "Please pick a date before saving a reminder.",
        "reminder_overdue": "Overdue",
        "reminder_today": "Due today",
        "reminder_due_soon": "Due in {days} days",
        "reminder_upcoming": "Due in {days} days",
        "reminders_title": "Your Scheme Reminders",
        "reminders_empty": "No reminders set yet.",
        "reminders_disclaimer": "This app can't send push notifications.",

        # ===========================
        # FAQ
        # ===========================
        "faq_title": "Frequently Asked Questions",

        # ===========================
        # CSC Locator
        # ===========================
        "csc_title": "CSC Center Locator",
        "csc_subtitle": "Find Common Service Centres near you",
        "csc_state_label": "Select State",
        "csc_search_label": "Search by district or address",
        "csc_search_placeholder": "e.g. Bhopal, MP Nagar...",
        "csc_results_found": "CSC centers found",
        "csc_address_label": "Address",
        "csc_district_label": "District",
        "csc_phone_label": "Phone",
        "csc_no_results": "No CSC centers found.",

        # ===========================
        # Voice Assistant
        # ===========================
        "voice_listening": "Listening...",
        "voice_not_supported": "Voice search not supported in this browser.",
        "voice_error": "Error:",
        "voice_hint": "Tap the microphone and speak your query",
        "listening_text": "Listening...",
        "not_supported_text": "Voice search not supported in this browser. Please use Chrome or Edge.",
        "error_text": "Error:",

        # ===========================
        # Explain Simply
        # ===========================
        "explain_simply_label": "Explain Simply",
        "explain_simply_btn": "Get Simple Explanation",
        "explain_simply_loading": "Simplifying...",
        "listen_btn": "Listen",
        "explain_simple_title": "Simplified Explanation",
        "explain_generating": "⏳ Generating simple explanation...",
        "explain_success": "✅ Explanation generated!",
        "explain_error": "Error:",

        # ===========================
        # Quick Actions
        # ===========================
        "quick_actions_title": "Quick Actions",
        "quick_actions_caption": "Choose what you need",
        "qa_find_schemes_title": "Find Schemes",
        "qa_find_schemes_desc": "Search schemes by eligibility",
        "qa_smart_search_title": "Smart Search",
        "qa_smart_search_desc": "Search in your own words",
        "qa_ai_assistant_title": "AI Assistant",
        "qa_ai_assistant_desc": "Chat directly with AI",

        # ===========================
        # Settings Page
        # ===========================
        "settings_title": "Settings",
        "settings_my_profile": "👤 My Profile",
        "settings_save_profile": "💾 Save Profile",
        "settings_profile_saved": "Profile saved!",
        "settings_notifications": "Notifications",
        "settings_email_alerts": "Email Alerts",
        "settings_sms_alerts": "SMS Alerts",
        "settings_reminder_days": "Reminder Days Before Deadline",
        "settings_save_settings": "💾 Save Settings",
        "settings_settings_saved": "Settings saved!",
        "settings_accessibility": "♿ Accessibility",
        "settings_font_size": "Font Size",
        "settings_apply_font": "Apply Font Size",
        "settings_high_contrast": "High Contrast Mode",
        "settings_data_management": "🗑️ Data Management",
        "settings_clear_data": "Clear All Data",
        "settings_data_cleared": "All data cleared!",
        "settings_use_sidebar": "⚙️ Use the panel on the left sidebar to update your profile, notifications, and accessibility settings.",

        # ===========================
        # Notification Center (legacy — kept for backward compat)
        # ===========================
        "notif_title": "Notification Center",
        "notif_reminders": "⏰ Reminders",
        "notif_no_reminders": "No reminders set yet.",
        "notif_favorites_deadlines": "⭐ Favorites with Deadlines",
        "notif_deadline_expired": "Deadline expired on",
        "notif_due_in_days": "Due in {days} days",

        # ===========================
        # Dashboard
        # ===========================
        "dashboard_title": "Dashboard",
        "dashboard_total_schemes": "Total Schemes",
        "dashboard_states": "States",
        "dashboard_categories": "Categories",
        "dashboard_applications": "Applications",

        # ===========================
        # Application Status
        # ===========================
        "app_status_label": "Application Status",
        "app_status_update": "Update Status",
        "app_status_save": "Save Status",
        "app_status_not_applied": "Not Applied",
        "app_status_applied": "Applied",
        "app_status_pending": "Pending",
        "app_status_rejected": "Rejected",
        "app_copy_link": "📋 Copy Official Site Link",
        "app_official_site": "Official Site",
        "app_apply_here": "Apply Here",
        "app_status_updated_toast": "✅ Status Updated",

        # ===========================
        # Results
        # ===========================
        "clear_results_btn": "🧹 Clear Results",
        "load_more_btn": "📱 Load More Results",
        "searching_spinner": "🔍 Searching schemes...",

        # ===========================
        # Status Chips
        # ===========================
        "chip_applied": "✅ Applied",
        "chip_pending": "⏳ Pending",
        "chip_rejected": "❌ Rejected",
    },

    "हिंदी": {
        # ===========================
        # Basic Info
        # ===========================
        "title": "सरकारी योजना",
        "subtitle": "अपनी योग्यता के अनुसार सरकारी योजनाएं खोजें",
        "disclaimer": "यह टूल केवल मार्गदर्शन के लिए है।",

        # ===========================
        # Form Fields
        # ===========================
        "age": "आयु",
        "gender": "लिंग",
        "occupation": "व्यवसाय",
        "income": "वार्षिक पारिवारिक आय (₹)",
        "category": "सामाजिक श्रेणी",
        "state": "राज्य",
        "scheme_category": "योजना श्रेणी (वैकल्पिक फ़िल्टर)",
        "only_eligible": "केवल पात्र योजनाएं दिखाएं",
        "search_btn": "योजनाएं खोजें",

        # ===========================
        # Result Labels
        # ===========================
        "all": "सभी",
        "total_shown": "कुल योजनाएं",
        "eligible_label": "पात्र",
        "not_eligible_label": "अपात्र",
        "no_results": "आपकी प्रोफाइल से कोई योजना मेल नहीं खाई।",
        "what_is": "यह क्या है",
        "benefit": "लाभ",
        "eligibility_breakdown": "पात्रता विवरण",
        "apply_btn": "यहां आवेदन करें",
        "eligible_badge": "पात्र",
        "not_eligible_badge": "अपात्र",
        "hint": "शुरू करने के लिए साइडबार में अपनी प्रोफाइल भरें।",

        # ===========================
        # Sidebar / Navigation
        # ===========================
        "language_label": "Language / भाषा",
        "mode_label": "खोज का तरीका",
        "mode_form": "पात्रता जांच",
        "mode_nl": "योजनाएं खोजें",
        "mode_favorites": "पसंदीदा",
        "mode_reminders": "रिमाइंडर",           # backward-compat redirect ke liye
        "mode_history": "खोज इतिहास",
        "mode_faq": "सामान्य प्रश्न",
        "mode_csc": "सीएससी लोकेटर",
        "mode_dashboard": "डैशबोर्ड",
        "mode_settings": "सेटिंग्स",
        "mode_notifications": "अलर्ट और रिमाइंडर",   # v8: renamed (merged)
        "mode_admin": "एडमिन पैनल",
        "mode_assistant": "AI सहायक",
        "mode_voice_assistant": "वॉइस सहायक",
        "mode_documents": "मेरे दस्तावेज़",       # v10: NEW

        # ===========================
        # My Documents (v10 Bookmarklet Auto-Fill)
        # ===========================
        "docs_page_title": "मेरे दस्तावेज़ वॉल्ट",
        "docs_page_caption": "अपना व्यक्तिगत डेटा एक बार भरें — फिर किसी भी सरकारी साइट पर ऑटो-फिल करें",
        "docs_form_heading": "📋 व्यक्तिगत जानकारी",
        "docs_form_hint": "यह डेटा केवल आपके कंप्यूटर पर सेव होता है। किसी सर्वर पर नहीं जाता।",
        "docs_save_btn": "💾 दस्तावेज़ सेव करें",
        "docs_saved_msg": "✅ दस्तावेज़ सफलतापूर्वक सेव हो गए!",
        "docs_clear_btn": "🗑️ सारे दस्तावेज़ हटाएं",
        "docs_cleared_msg": "🗑️ सारे दस्तावेज़ हटा दिए गए",
        "docs_empty_warning": "⚠️ पहले ऊपर फॉर्म भर के Save करें, फिर bookmarklet जनरेट होगा",
        "docs_copy_section": "📄 कॉपी बटन",
        "docs_copy_hint": "कभी-कभी bookmarklet काम नहीं करता (CSP ब्लॉक)। ऐसे समय में ये बटन उपयोग करें:",
        "docs_bookmarklet_section": "⚡ Bookmarklet (ऑटो-फिल)",
        "docs_bookmarklet_hint": "यह एक छोटा JavaScript है। इसे bookmarks bar में drag करके रखें। किसी भी सरकारी साइट पर फॉर्म भरते समय क्लिक करें — एक floating panel खुलेगा जिसमें हर फ़ील्ड का बटन होगा।",
        "docs_step_1": "1️⃣ नीचे वाले बटन को अपने browser के bookmarks bar में DRAG करें (click नहीं, drag)",
        "docs_step_2": "2️⃣ Bookmarks bar दिखाने के लिए Ctrl+Shift+B दबाएं (Chrome/Edge)",
        "docs_step_3": "3️⃣ किसी भी सरकारी साइट पर फॉर्म खोलें, और उसके input box पर पहले click करें (cursor वहीं रखें)",
        "docs_step_4": "4️⃣ Bookmarks bar में '⚡ Fill Form' पर click करें — panel खुलेगा, फिर फ़ील्ड बटन दबाएं",
        "docs_drag_here": "⚡ Fill Form — इसे Bookmarks Bar में Drag करें",
        "docs_bookmarklet_warning": "⚠️ Bookmarklet में आपका डेटा base64-encoded है (plain text नहीं)। लेकिन यह आपके browser के bookmarks में सेव होता है — अपना browser/profile किसी के साथ शेयर न करें।",
        "docs_regenerate_hint": "🔄 अगर आपने ऊपर डेटा अपडेट किया है, तो यहां bookmarklet दोबारा drag करें (पुराना delete करके)",
        "docs_no_bookmarklet": "Bookmarklet जनरेट करने के लिए पहले ऊपर डेटा save करें।",

        # ===========================
        # Alerts & Reminders (v8 merged page)
        # ===========================
        "alerts_page_title": "अलर्ट और रिमाइंडर",
        "alerts_page_caption": "आपके रिमाइंडर + पसंदीदा योजनाओं की डेडलाइन",
        "alerts_tab_reminders": "⏰ मेरे रिमाइंडर",
        "alerts_tab_deadlines": "⭐ डेडलाइन अलर्ट",
        "alerts_tab_all": "📋 सभी अलर्ट",
        "alerts_no_items": "अभी तक कोई रिमाइंडर या डेडलाइन अलर्ट नहीं है। योजनाओं को पसंदीदा बनाएं या रिमाइंडर सेट करें।",
        "alerts_urgent_count": "{count} अत्यावश्यक",
        "alerts_load_more": "और रिमाइंडर लोड करें",

        # ===========================
        # Natural Language Search
        # ===========================
        "nl_placeholder": "जैसे: मुझे अपनी बेटी की पढ़ाई के लिए छात्रवृत्ति चाहिए",
        "nl_search_btn": "खोजें",
        "nl_matches_found": "योजनाएं मिलीं",
        "nl_no_results": "कोई मेल खाती योजना नहीं मिली।",
        "nl_note": "यह खोज केवल संबंधित योजनाएं दिखाती है।",
        "nl_hint": "ऊपर अपनी जरूरत लिखें और खोजें दबाएं।",
        "suggestions_label": "सुझाव:",

        # ===========================
        # History
        # ===========================
        "history_title": "आपकी पिछली खोजें",
        "history_empty": "अभी तक कोई खोज नहीं हुई।",
        "history_clear_btn": "पूरा इतिहास हटाएं",
        "history_cleared_msg": "इतिहास हटा दिया गया।",
        "history_form_summary": "पात्रता जांच — आयु {age}, {state}",
        "history_nl_summary": "खोजा गया: \"{query}\"",

        # ===========================
        # Theme & Sorting
        # ===========================
        "theme_label": "थीम",
        "theme_dark": "डार्क",
        "theme_light": "लाइट",
        "sort_label": "इस हिसाब से क्रमबद्ध करें",
        "sort_default_form": "पात्रता (डिफ़ॉल्ट)",
        "sort_default_nl": "सर्वश्रेष्ठ मेल (डिफ़ॉल्ट)",
        "sort_name": "नाम (A-Z)",
        "sort_category": "श्रेणी",
        "sort_state": "राज्य",

        # ===========================
        # Share & PDF
        # ===========================
        "pdf_download_btn": "पीडीएफ रिपोर्ट डाउनलोड करें",
        "share_label": "शेयर करें",
        "share_copy_label": "या यह संदेश कॉपी करें:",
        "share_app_btn": "ऐप शेयर करें",
        "app_share_message": "यह ऐप देखें — सरकारी योजनाएं खोजने के लिए!",

        # ===========================
        # Favorites
        # ===========================
        "favorites_title": "आपकी पसंदीदा योजनाएं",
        "favorites_empty": "अभी तक कोई पसंदीदा नहीं।",
        "fav_add_tooltip": "पसंदीदा में जोड़ें",
        "fav_remove_tooltip": "पसंदीदा से हटाएं",
        "fav_added_toast": "⭐ पसंदीदा में जोड़ा गया",
        "fav_removed_toast": "पसंदीदा से हटाया गया",

        # ===========================
        # Documents
        # ===========================
        "documents_required_label": "आवश्यक दस्तावेज़",
        "documents_disclaimer": "सामान्य मार्गदर्शन।",

        # ===========================
        # Reminders
        # ===========================
        "reminder_label": "रिमाइंडर",
        "set_reminder_label": "रिमाइंडर तारीख सेट करें",
        "reminder_note_placeholder": "वैकल्पिक नोट",
        "save_reminder_btn": "रिमाइंडर सेव करें",
        "remove_reminder_btn": "रिमाइंडर हटाएं",
        "reminder_saved_msg": "रिमाइंडर सेव हो गया।",
        "reminder_saved_toast": "⏰ रिमाइंडर सेव हो गया",
        "reminder_removed_toast": "🗑️ रिमाइंडर हटा दिया गया",
        "reminder_date_warning": "रिमाइंडर सेव करने से पहले तारीख चुनें।",
        "reminder_overdue": "तारीख निकल चुकी है",
        "reminder_today": "आज आखिरी दिन है",
        "reminder_due_soon": "{days} दिन बाकी हैं",
        "reminder_upcoming": "{days} दिन बाकी हैं",
        "reminders_title": "आपके योजना रिमाइंडर",
        "reminders_empty": "अभी तक कोई रिमाइंडर सेट नहीं है।",
        "reminders_disclaimer": "यह ऐप push notification नहीं भेज सकता।",

        # ===========================
        # FAQ
        # ===========================
        "faq_title": "अक्सर पूछे जाने वाले प्रश्न",

        # ===========================
        # CSC Locator
        # ===========================
        "csc_title": "सीएससी केंद्र लोकेटर",
        "csc_subtitle": "योजना आवेदन के लिए अपने पास के सीएससी केंद्र खोजें",
        "csc_state_label": "राज्य चुनें",
        "csc_search_label": "जिला या पते से खोजें",
        "csc_search_placeholder": "जैसे: भोपाल, एमपी नगर...",
        "csc_results_found": "सीएससी केंद्र मिले",
        "csc_address_label": "पता",
        "csc_district_label": "जिला",
        "csc_phone_label": "फोन",
        "csc_no_results": "कोई सीएससी केंद्र नहीं मिला।",

        # ===========================
        # Voice Assistant
        # ===========================
        "voice_listening": "सुन रहा हूं...",
        "voice_not_supported": "इस ब्राउज़र में वॉइस सर्च समर्थित नहीं है।",
        "voice_error": "त्रुटि:",
        "voice_hint": "माइक्रोफ़ोन दबाएं और अपना सवाल बोलें",
        "listening_text": "सुन रहा हूं...",
        "not_supported_text": "इस ब्राउज़र में वॉइस सर्च समर्थित नहीं है। कृपया Chrome या Edge उपयोग करें।",
        "error_text": "त्रुटि:",

        # ===========================
        # Explain Simply
        # ===========================
        "explain_simply_label": "सरल भाषा में समझाएं",
        "explain_simply_btn": "सरल भाषा में समझाएं",
        "explain_simply_loading": "समझा रहा हूं...",
        "listen_btn": "सुनें",
        "explain_simple_title": "सरल व्याख्या",
        "explain_generating": "⏳ सरल व्याख्या बना रहे हैं...",
        "explain_success": "✅ व्याख्या तैयार!",
        "explain_error": "त्रुटि:",

        # ===========================
        # Quick Actions
        # ===========================
        "quick_actions_title": "त्वरित कार्य",
        "quick_actions_caption": "जो आपको चाहिए वह चुनें",
        "qa_find_schemes_title": "योजनाएं खोजें",
        "qa_find_schemes_desc": "पात्रता के अनुसार योजनाएं खोजें",
        "qa_smart_search_title": "स्मार्ट खोज",
        "qa_smart_search_desc": "अपने शब्दों में खोजें",
        "qa_ai_assistant_title": "AI सहायक",
        "qa_ai_assistant_desc": "AI से सीधे बात करें",

        # ===========================
        # Settings Page
        # ===========================
        "settings_title": "सेटिंग्स",
        "settings_my_profile": "👤 मेरी प्रोफाइल",
        "settings_save_profile": "💾 प्रोफाइल सेव करें",
        "settings_profile_saved": "प्रोफाइल सेव हो गई!",
        "settings_notifications": "सूचनाएं",
        "settings_email_alerts": "ईमेल अलर्ट",
        "settings_sms_alerts": "एसएमएस अलर्ट",
        "settings_reminder_days": "डेडलाइन से पहले रिमाइंडर दिन",
        "settings_save_settings": "💾 सेटिंग्स सेव करें",
        "settings_settings_saved": "सेटिंग्स सेव हो गईं!",
        "settings_accessibility": "♿ एक्सेसिबिलिटी",
        "settings_font_size": "फ़ॉन्ट साइज़",
        "settings_apply_font": "फ़ॉन्ट साइज़ लागू करें",
        "settings_high_contrast": "हाई कंट्रास्ट मोड",
        "settings_data_management": "🗑️ डेटा प्रबंधन",
        "settings_clear_data": "सारा डेटा हटाएं",
        "settings_data_cleared": "सारा डेटा हटा दिया गया!",
        "settings_use_sidebar": "⚙️ अपनी प्रोफाइल, सूचनाएं और एक्सेसिबिलिटी सेटिंग्स अपडेट करने के लिए बाएं साइडबार का उपयोग करें।",

        # ===========================
        # Notification Center (legacy)
        # ===========================
        "notif_title": "सूचना केंद्र",
        "notif_reminders": "⏰ रिमाइंडर",
        "notif_no_reminders": "अभी तक कोई रिमाइंडर सेट नहीं है।",
        "notif_favorites_deadlines": "⭐ डेडलाइन वाले पसंदीदा",
        "notif_deadline_expired": "डेडलाइन समाप्त हो गई",
        "notif_due_in_days": "{days} दिनों में देय",

        # ===========================
        # Dashboard
        # ===========================
        "dashboard_title": "डैशबोर्ड",
        "dashboard_total_schemes": "कुल योजनाएं",
        "dashboard_states": "राज्य",
        "dashboard_categories": "श्रेणियां",
        "dashboard_applications": "आवेदन",

        # ===========================
        # Application Status
        # ===========================
        "app_status_label": "आवेदन स्थिति",
        "app_status_update": "स्थिति अपडेट करें",
        "app_status_save": "स्थिति सेव करें",
        "app_status_not_applied": "आवेदन नहीं किया",
        "app_status_applied": "आवेदन किया",
        "app_status_pending": "लंबित",
        "app_status_rejected": "अस्वीकृत",
        "app_copy_link": "📋 आधिकारिक साइट लिंक कॉपी करें",
        "app_official_site": "आधिकारिक साइट",
        "app_apply_here": "यहां आवेदन करें",
        "app_status_updated_toast": "✅ स्थिति अपडेट हो गई",

        # ===========================
        # Results
        # ===========================
        "clear_results_btn": "🧹 परिणाम साफ़ करें",
        "load_more_btn": "📱 और परिणाम लोड करें",
        "searching_spinner": "🔍 योजनाएं खोज रहे हैं...",

        # ===========================
        # Status Chips
        # ===========================
        "chip_applied": "✅ आवेदन किया",
        "chip_pending": "⏳ लंबित",
        "chip_rejected": "❌ अस्वीकृत",
    }
}


# ===========================
# PUBLIC API
# ===========================
def get_text(lang):
    """
    Diye gaye language ke liye translation dictionary deta hai.
    - Unknown language → English fallback
    - Safe: agar kabhi language key missing ho to bhi crash nahi karta
    """
    if lang in TRANSLATIONS:
        return TRANSLATIONS[lang]
    return TRANSLATIONS["English"]


def get_all_keys(lang="English"):
    """Ek language ke saare keys return karta hai (verification scripts ke liye)."""
    return set(TRANSLATIONS.get(lang, TRANSLATIONS["English"]).keys())


def find_missing_keys(source_lang="English", target_lang="हिंदी"):
    """
    Do languages ke beech missing keys dhundhta hai.
    Returns: dict {"missing_in_target": set, "missing_in_source": set}
    """
    source_keys = get_all_keys(source_lang)
    target_keys = get_all_keys(target_lang)
    return {
        "missing_in_target": source_keys - target_keys,
        "missing_in_source": target_keys - source_keys,
    }


# ===========================
# SELF-TEST — verification
# ===========================
if __name__ == "__main__":
    print("=" * 60)
    print("translations.py — Verification (v4)")
    print("=" * 60)

    # 1. Both languages present
    assert "English" in TRANSLATIONS
    assert "हिंदी" in TRANSLATIONS
    print(f"✅ Languages: {list(TRANSLATIONS.keys())}")

    # 2. Key count
    en_count = len(TRANSLATIONS["English"])
    hi_count = len(TRANSLATIONS["हिंदी"])
    print(f"✅ Key counts — English: {en_count}, Hindi: {hi_count}")

    # 3. Cross-language consistency
    missing = find_missing_keys()
    if missing["missing_in_target"]:
        print(f"❌ Missing in Hindi: {missing['missing_in_target']}")
    if missing["missing_in_source"]:
        print(f"❌ Missing in English: {missing['missing_in_source']}")
    if not missing["missing_in_target"] and not missing["missing_in_source"]:
        print("✅ Both languages have identical keys")

    # 4. get_text fallback
    assert get_text("Klingon") == TRANSLATIONS["English"]
    print("✅ get_text() fallback works for unknown language")

    # 5. Voice keys present
    for key in ["listening_text", "not_supported_text", "error_text"]:
        assert key in TRANSLATIONS["English"], f"Missing in English: {key}"
        assert key in TRANSLATIONS["हिंदी"], f"Missing in Hindi: {key}"
    print("✅ Voice input keys present in both languages")

    # 6. Alerts merge keys present (v8)
    alerts_keys = [
        "alerts_page_title", "alerts_page_caption",
        "alerts_tab_reminders", "alerts_tab_deadlines", "alerts_tab_all",
        "alerts_no_items", "alerts_urgent_count", "alerts_load_more",
    ]
    for key in alerts_keys:
        assert key in TRANSLATIONS["English"], f"Missing in English: {key}"
        assert key in TRANSLATIONS["हिंदी"], f"Missing in Hindi: {key}"
    print(f"✅ All {len(alerts_keys)} Alerts-merge keys present in both languages")

    # 7. NEW v10: Documents Vault keys present
    docs_keys = [
        "mode_documents",
        "docs_page_title", "docs_page_caption",
        "docs_form_heading", "docs_form_hint",
        "docs_save_btn", "docs_saved_msg",
        "docs_clear_btn", "docs_cleared_msg",
        "docs_empty_warning",
        "docs_copy_section", "docs_copy_hint",
        "docs_bookmarklet_section", "docs_bookmarklet_hint",
        "docs_step_1", "docs_step_2", "docs_step_3", "docs_step_4",
        "docs_drag_here", "docs_bookmarklet_warning",
        "docs_regenerate_hint", "docs_no_bookmarklet",
    ]
    for key in docs_keys:
        assert key in TRANSLATIONS["English"], f"Missing in English: {key}"
        assert key in TRANSLATIONS["हिंदी"], f"Missing in Hindi: {key}"
    print(f"✅ All {len(docs_keys)} Documents-Vault keys present in both languages")

    # 8. Backward-compat: mode_reminders still present
    assert "mode_reminders" in TRANSLATIONS["English"]
    assert "mode_reminders" in TRANSLATIONS["हिंदी"]
    print("✅ mode_reminders key retained (backward compat)")

    # 9. Specific keys used by app.py
    required_keys = [
        "title", "subtitle", "disclaimer", "age", "gender", "occupation",
        "income", "category", "state", "scheme_category", "only_eligible",
        "search_btn", "all", "total_shown", "eligible_label", "not_eligible_label",
        "no_results", "what_is", "benefit", "eligibility_breakdown",
        "eligible_badge", "not_eligible_badge", "hint", "mode_form", "mode_nl",
        "mode_favorites", "mode_history", "mode_faq", "mode_csc",
        "mode_dashboard", "mode_settings", "mode_notifications", "mode_admin",
        "mode_assistant", "mode_voice_assistant", "mode_documents",
        "theme_label", "theme_dark", "theme_light",
        "sort_label", "sort_default_form", "sort_default_nl",
        "sort_name", "sort_category", "sort_state", "nl_placeholder",
        "nl_search_btn", "nl_matches_found", "nl_no_results", "nl_note",
        "nl_hint", "suggestions_label", "favorites_title", "favorites_empty",
        "reminders_title", "reminders_empty", "reminders_disclaimer",
        "history_title", "history_empty", "history_clear_btn",
        "faq_title", "csc_title", "settings_title", "app_copy_link",
        "app_official_site", "app_apply_here", "pdf_download_btn",
        "share_label", "share_copy_label", "share_app_btn", "app_share_message",
        "documents_required_label", "documents_disclaimer", "reminder_label",
        "set_reminder_label", "reminder_note_placeholder", "save_reminder_btn",
        "remove_reminder_btn", "reminder_saved_toast", "reminder_removed_toast",
        "clear_results_btn", "load_more_btn", "searching_spinner",
        "chip_applied", "chip_pending", "chip_rejected", "app_status_label",
        "app_status_update", "app_status_save", "app_status_updated_toast",
        "fav_add_tooltip", "fav_remove_tooltip", "fav_added_toast", "fav_removed_toast",
        "explain_simply_label", "explain_simply_btn", "explain_generating",
        "explain_success", "explain_error", "listen_btn", "explain_simple_title",
        "quick_actions_title", "quick_actions_caption", "qa_find_schemes_title",
        "qa_find_schemes_desc", "qa_smart_search_title", "qa_smart_search_desc",
        "qa_ai_assistant_title", "qa_ai_assistant_desc",
        # v8 alerts keys
        "alerts_page_title", "alerts_page_caption",
        "alerts_tab_reminders", "alerts_tab_deadlines", "alerts_tab_all",
        "alerts_no_items", "alerts_urgent_count", "alerts_load_more",
        # v10 documents keys
        *docs_keys,
    ]
    missing_required = []
    for key in required_keys:
        if key not in TRANSLATIONS["English"]:
            missing_required.append(f"EN:{key}")
        if key not in TRANSLATIONS["हिंदी"]:
            missing_required.append(f"HI:{key}")
    if missing_required:
        print(f"❌ Missing required keys: {missing_required}")
    else:
        print(f"✅ All {len(required_keys)} app-critical keys present in both languages")

    print("=" * 60)
    print("✅ translations.py v4 — ALL CHECKS PASSED")
    print("=" * 60)