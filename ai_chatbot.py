"""
AI Chatbot - Smart Assistant with Profile Questions
Complete version with all 7 smart features:
  1. Dynamic Follow-up Questions (Smart Branching)
  2. Natural Language Chat Mode (AI-Powered)
  3. AI-Generated Personalized Suggestions
  4. Progress Bar (Multi-Step Wizard)
  5. Save Profile to User Data
  6. Quick Reply Suggestions
  7. Assistant Analytics (Logging)
"""

import os
import re
import json
import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime
from langchain_groq import ChatGroq
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
from matcher import match_schemes, load_schemes
from translations import get_text

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


# ===========================
# AUTO-SCROLL HELPER (Modern Chat Style)
# ===========================
def auto_scroll_to_bottom():
    """Har rerun par page ko smoothly bottom par scroll karta hai,
    bilkul modern chat apps (ChatGPT/WhatsApp) ki tarah."""
    components.html(
        """
        <script>
            // Parent window ko access karo
            const parentDoc = window.parent.document;
            
            // Scroll function
            function scrollToBottom() {
                // Sabse pehle chat input dhoondho (jahan user type karta hai)
                const chatInput = parentDoc.querySelector('.stChatFloatingInputContainer');
                
                // Agar chat input mil gaya, to uske upar wale container par scroll karo
                if (chatInput) {
                    chatInput.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'end' 
                    });
                } else {
                    // Fallback: poore page ko bottom tak scroll karo
                    const mainContainer = parentDoc.querySelector('.main') || parentDoc.querySelector('section.main');
                    if (mainContainer) {
                        mainContainer.scrollTo({
                            top: mainContainer.scrollHeight,
                            behavior: 'smooth'
                        });
                    } else {
                        // Aur bhi fallback - window scroll
                        window.parent.scrollTo({
                            top: parentDoc.body.scrollHeight,
                            behavior: 'smooth'
                        });
                    }
                }
            }
            
            // Thoda delay de kar scroll karo (Streamlit DOM render hone ke baad)
            setTimeout(scrollToBottom, 300);
        </script>
        """,
        height=0,
    )


# ===========================
# DYNAMIC PROFILE QUESTIONS
# ===========================
def get_dynamic_questions(profile):
    """Get questions based on previously answered questions (smart branching)."""
    
    questions = [
        {
            "key": "age",
            "question": "What is your age?",
            "options": ["18-25", "26-35", "36-45", "46-55", "56-65", "65+"],
            "type": "single"
        },
        {
            "key": "state",
            "question": "Which state do you belong to?",
            "options": ["All", "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa",
                        "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand",
                        "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab",
                        "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal"],
            "type": "single"
        },
        {
            "key": "gender",
            "question": "What is your gender?",
            "options": ["All", "Male", "Female"],
            "type": "single"
        },
        {
            "key": "social_category",
            "question": "What is your social category?",
            "options": ["All", "General", "SC", "ST", "OBC", "Minority"],
            "type": "single"
        },
        {
            "key": "income",
            "question": "What is your annual family income? (in ₹)",
            "options": [
                "0 - 60,000",
                "60,001 - 80,000",
                "80,001 - 1,00,000",
                "1,00,001 - 1,20,000",
                "1,20,001 - 2,00,000",
                "2,00,001 - 3,00,000",
                "3,00,001 - 5,00,000",
                "5,00,001 - 8,00,000",
                "8,00,001 - 12,00,000",
                "12,00,001+"
            ],
            "type": "single"
        },
        {
            "key": "occupation",
            "question": "What is your occupation?",
            "options": ["Student", "Farmer", "Self-employed/Small business", "Unorganised worker", 
                       "Entrepreneur", "Senior citizen", "Unemployed youth", "Salaried employee", "Housewife"],
            "type": "single"
        }
    ]
    
    # ✅ Smart branching: Add follow-up questions based on occupation
    occupation = str(profile.get("occupation", "")).lower()
    gender = str(profile.get("gender", "")).lower()
    age = profile.get("age", 0)
    
    # Age range se integer nikaalne ka helper
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
            "type": "single"
        })
        questions.append({
            "key": "institute_type",
            "question": "What type of institute are you studying in?",
            "options": ["Government", "Private", "Not studying"],
            "type": "single"
        })
    
    elif "farmer" in occupation:
        questions.append({
            "key": "land_size",
            "question": "How much agricultural land do you own?",
            "options": ["No land", "Less than 1 acre", "1-2 acres", "2-5 acres", "More than 5 acres"],
            "type": "single"
        })
        questions.append({
            "key": "crop_type",
            "question": "What type of crops do you grow?",
            "options": ["Food grains", "Vegetables", "Fruits", "Cash crops", "Mixed"],
            "type": "single"
        })
    
    elif "female" in gender or "housewife" in occupation:
        questions.append({
            "key": "marital_status",
            "question": "What is your marital status?",
            "options": ["Unmarried", "Married", "Widow", "Divorced"],
            "type": "single"
        })
        questions.append({
            "key": "has_children",
            "question": "Do you have children?",
            "options": ["No", "Yes - 1 child", "Yes - 2 children", "Yes - 3+ children"],
            "type": "single"
        })
    
    elif "senior" in occupation or age_int >= 60:
        questions.append({
            "key": "has_pension",
            "question": "Do you receive any pension?",
            "options": ["No", "Yes - Government", "Yes - Private"],
            "type": "single"
        })
    
    elif "unemployed" in occupation or "youth" in occupation:
        questions.append({
            "key": "looking_for",
            "question": "What are you looking for?",
            "options": ["Job", "Skill Training", "Business Loan", "Education"],
            "type": "single"
        })
    
    elif "business" in occupation or "entrepreneur" in occupation:
        questions.append({
            "key": "business_type",
            "question": "What type of business?",
            "options": ["Manufacturing", "Retail/Shop", "Service", "Online", "Agriculture"],
            "type": "single"
        })
        questions.append({
            "key": "business_stage",
            "question": "What stage is your business at?",
            "options": ["Idea", "Starting up", "Running", "Expanding"],
            "type": "single"
        })
    
    # ✅ General question
    questions.append({
        "key": "special_needs",
        "question": "Do you have any special category?",
        "options": ["None", "Divyang (Disabled)", "Widow", "Orphan", "Ex-serviceman"],
        "type": "single"
    })
    
    return questions


# ===========================
# SESSION STATE INIT
# ===========================
def init_assistant_state():
    """Initialize assistant session state."""
    if "assistant_profile" not in st.session_state:
        st.session_state.assistant_profile = {}
    if "assistant_step" not in st.session_state:
        st.session_state.assistant_step = 0
    if "assistant_messages" not in st.session_state:
        st.session_state.assistant_messages = []
    if "assistant_results" not in st.session_state:
        st.session_state.assistant_results = []
    if "assistant_complete" not in st.session_state:
        st.session_state.assistant_complete = False
    if "assistant_mode" not in st.session_state:
        st.session_state.assistant_mode = "profile"
    if "nl_chat_history" not in st.session_state:
        st.session_state.nl_chat_history = []


def reset_assistant():
    """Reset assistant state."""
    st.session_state.assistant_profile = {}
    st.session_state.assistant_step = 0
    st.session_state.assistant_messages = []
    st.session_state.assistant_results = []
    st.session_state.assistant_complete = False
    st.session_state.nl_chat_history = []


# ===========================
# HELPER: CONVERT RANGE TO NUMBER
# ===========================
def extract_number_from_range(value):
    """Range string (jaise '18-25' ya '60,001 - 80,000') se ek number nikaalta hai.
    Matching ke liye lower bound use karte hain, aur '65+' ke liye 65,
    aur '12,00,001+' ke liye 1200001 return karta hai."""
    if value is None or value in ["All", ""]:
        return None
    
    val_str = str(value).strip()
    
    # Comma hatao
    val_str = val_str.replace(",", "")
    
    # "65+" jaisa case
    if val_str.endswith("+"):
        try:
            return int(val_str.replace("+", "").strip())
        except ValueError:
            return None
    
    # "18-25" jaisa case - lower bound
    if "-" in val_str:
        try:
            lower = val_str.split("-")[0].strip()
            return int(lower)
        except (ValueError, IndexError):
            return None
    
    # Plain number
    try:
        return int(val_str)
    except ValueError:
        return None


# ===========================
# FEATURE 7: ASSISTANT ANALYTICS
# ===========================
def log_assistant_query(query, matched_count, profile=None):
    """Log assistant queries for analytics."""
    try:
        log_file = "data/assistant_log.json"
        os.makedirs("data", exist_ok=True)
        
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                log = json.load(f)
        else:
            log = []
        
        log.append({
            "query": query,
            "matched": matched_count,
            "profile": profile,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 500 entries
        log = log[-500:]
        
        with open(log_file, "w") as f:
            json.dump(log, f, indent=2)
    except Exception:
        pass


# ===========================
# FEATURE 5: SAVE PROFILE
# ===========================
def save_profile_to_user_data(profile):
    """Save user profile to data/user_profile.json."""
    try:
        # Age aur income ko number mein convert karo
        age_val = extract_number_from_range(profile.get("age", 25))
        income_val = extract_number_from_range(profile.get("income", 200000))
        
        profile_to_save = {
            "age": age_val if age_val is not None else 25,
            "income": income_val if income_val is not None else 200000,
            "state": profile.get("state", "All"),
            "gender": profile.get("gender", "All"),
            "occupation": profile.get("occupation", "All"),
            "social_category": profile.get("social_category", "All"),
        }
        
        os.makedirs("data", exist_ok=True)
        with open("data/user_profile.json", "w") as f:
            json.dump(profile_to_save, f, indent=2)
        
        return True
    except Exception:
        return False


# ===========================
# FEATURE 3: AI RECOMMENDATION
# ===========================
def generate_ai_recommendation(profile, matched_schemes):
    """Generate personalized AI recommendation based on profile."""
    llm = get_llm()
    if not llm or not matched_schemes:
        return None
    
    top_schemes = [r["scheme_name"] for r in matched_schemes[:5]]
    
    prompt = f"""
    User Profile:
    - Age: {profile.get('age')}
    - Gender: {profile.get('gender')}
    - State: {profile.get('state')}
    - Occupation: {profile.get('occupation')}
    - Income: ₹{profile.get('income')}
    
    Top Matching Schemes:
    {chr(10).join(f"- {s}" for s in top_schemes)}
    
    Generate a personalized 2-3 line recommendation in Hinglish (Hindi + English mix) 
    for this user. Mention their profile and why these schemes suit them.
    Keep it friendly and helpful.
    """
    
    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception:
        return None


# ===========================
# FEATURE 2: NL SMART QUERY PROCESSOR
# ===========================
def process_smart_query(query, df):
    """Process user query using AI to extract intent and find schemes."""
    
    llm = get_llm()
    if not llm:
        return {
            "message": "⚠️ AI not available. Please configure GROQ_API_KEY.",
            "schemes": []
        }
    
    extraction_prompt = f"""
    User query: "{query}"
    
    Extract structured information from this query. Return ONLY valid JSON (no markdown, no explanation):
    {{
        "age": <number or null>,
        "gender": "<Male/Female/All>",
        "state": "<state name or 'All'>",
        "occupation": "<Student/Farmer/etc or 'All'>",
        "income": <number or null>,
        "category": "<SC/ST/OBC/General/Minority or 'All'>",
        "keywords": ["keyword1", "keyword2"],
        "intent": "<scheme type or purpose>"
    }}
    """
    
    try:
        response = llm.invoke(extraction_prompt)
        content = response.content.strip()
        # Clean up markdown code blocks
        content = content.replace("```json", "").replace("```", "").strip()
        intent = json.loads(content)
    except Exception:
        intent = {
            "keywords": query.split()[:5], 
            "intent": "general",
            "gender": "All",
            "state": "All",
            "occupation": "All",
            "category": "All"
        }
    
    # Match schemes based on extracted intent
    try:
        matched = match_schemes(
            df,
            age=intent.get("age") or 25,
            gender=intent.get("gender", "All"),
            social_category=intent.get("category", "All"),
            occupation=intent.get("occupation", "All"),
            state=intent.get("state", "All"),
            annual_income=intent.get("income"),
            only_eligible=False
        )
    except Exception:
        matched = []
    
    if matched:
        response_msg = f"""
        ✅ **Maine {len(matched)} schemes aapke liye dhundhi hain!**
        
        Aapki query: *"{query}"*
        
        Top recommendations neeche di gayi hain. 👇
        """
    else:
        response_msg = f"""
        ❌ **Sorry, koi matching scheme nahi mili.**
        
        Kya aap thoda aur detail mein bata sakte hain?
        - Aapki age?
        - Aap kahan rehte hain?
        - Aapki zaroorat kya hai?
        """
    
    return {
        "message": response_msg,
        "schemes": matched[:5]
    }


# ===========================
# FEATURE 6: QUICK SUGGESTIONS
# ===========================
def render_quick_suggestions():
    """Show quick reply suggestions for NL mode."""
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
                st.rerun()


# ===========================
# NL CHAT MODE RENDER
# ===========================
def render_nl_chat_mode(df, render_scheme_card, sort_results, t):
    """Natural language chat mode - user describes problem in own words."""
    
    st.markdown("#### 💬 Apni samasya batayein")
    st.caption("Aap Hindi, English, ya Hinglish mein likh sakte hain")
    
    # Display chat history
    for msg in st.session_state.nl_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # ✅ Quick suggestions (only if no history)
    if not st.session_state.nl_chat_history:
        render_quick_suggestions()
    
    # Chat input
    user_query = st.chat_input(
        "Apni zaroorat likhein... (e.g. 'Mujhe 25 saal ki ladki ki shaadi ke liye paisa chahiye')",
        key="nl_chat_input"
    )
    
    if user_query:
        # Add user message
        st.session_state.nl_chat_history.append({"role": "user", "content": user_query})
        
        with st.chat_message("user"):
            st.markdown(user_query)
        
        # Process with AI
        with st.chat_message("assistant"):
            with st.spinner("🤖 AI soch raha hai..."):
                try:
                    response = process_smart_query(user_query, df)
                    st.markdown(response["message"])
                    
                    # ✅ Log for analytics
                    log_assistant_query(user_query, len(response["schemes"]))
                    
                    # Save to history
                    st.session_state.nl_chat_history.append({
                        "role": "assistant",
                        "content": response["message"]
                    })
                    
                    # Show schemes
                    if response["schemes"]:
                        st.markdown("---")
                        st.markdown("### 🎯 Recommended Schemes:")
                        if render_scheme_card and t:
                            for r in response["schemes"]:
                                render_scheme_card(r, t, "ai_chat", "English")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Reset chat button
    if st.session_state.nl_chat_history:
        if st.button("🔄 Start New Chat", use_container_width=True, key="reset_nl_chat"):
            st.session_state.nl_chat_history = []
            st.rerun()


# ===========================
# PROFILE MODE RENDER (Existing + Improvements)
# ===========================
def render_profile_mode(df, render_scheme_card, sort_results, t):
    """Profile-based mode with dynamic questions."""
    
    # Initialize session state
    init_assistant_state()
    
    # ✅ Get DYNAMIC questions based on current profile
    dynamic_questions = get_dynamic_questions(st.session_state.assistant_profile)
    
    step = st.session_state.assistant_step
    profile = st.session_state.assistant_profile
    total_steps = len(dynamic_questions)
    
    # ✅ PROFESSIONAL RIGHT-SIDE VERTICAL PROGRESS BAR
    # Only show when steps are NOT complete
    progress_value = min(step / total_steps, 1.0) if total_steps > 0 else 0
    progress_pct = int(progress_value * 100)
    
    # Hide progress bar when all steps are complete
    if not st.session_state.assistant_complete and step < total_steps:
        st.markdown(f"""
        <div style="
            position: fixed;
            top: 50%;
            right: 20px;
            transform: translateY(-50%);
            width: 10px;
            height: 50vh;
            z-index: 9999;
            background: rgba(11, 20, 26, 0.10);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border-radius: 10px;
            border: 1px solid rgba(0, 229, 255, 0.10);
            box-shadow: 
                0 4px 20px rgba(0, 0, 0, 0.1),
                inset 0 0 10px rgba(255, 255, 255, 0.02);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        ">
            <div style="
                width: 100%;
                height: {progress_pct}%;
                background: linear-gradient(180deg, #EC4899 0%, #A855F7 50%, #00E5FF 100%);
                background-size: 100% 200%;
                border-radius: 10px;
                box-shadow: 
                    0 0 15px rgba(0, 229, 255, 0.5),
                    0 0 30px rgba(168, 85, 247, 0.3);
                animation: neonProgress 3s ease infinite;
                transition: height 0.6s cubic-bezier(0.4, 0, 0.2, 1);
                position: relative;
            ">
                <div style="
                    position: absolute;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    background: linear-gradient(180deg, transparent, rgba(255,255,255,0.3), transparent);
                    animation: shimmerProgress 2.5s ease-in-out infinite;
                "></div>
            </div>
        </div>
        
        <style>
        @keyframes neonProgress {{
            0%, 100% {{ background-position: 50% 0%; }}
            50% {{ background-position: 50% 100%; }}
        }}
        @keyframes shimmerProgress {{
            0% {{ transform: translateY(-100%); }}
            100% {{ transform: translateY(100%); }}
        }}
        </style>
        """, unsafe_allow_html=True)
    
    # Show conversation history
    for msg in st.session_state.assistant_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # --- If profile is complete, show results ---
    if st.session_state.assistant_complete:
        st.info(f"""
        📋 **Your Profile:**
        - Age: {profile.get('age', 'Not set')}
        - State: {profile.get('state', 'Not set')}
        - Gender: {profile.get('gender', 'Not set')}
        - Category: {profile.get('social_category', 'Not set')}
        - Income: ₹{profile.get('income', 'Not set')}
        - Occupation: {profile.get('occupation', 'Not set')}
        """)
        
        # Search schemes
        if st.button("🔍 Search Schemes Now", type="primary", use_container_width=True, key="search_schemes_btn"):
            with st.spinner("🔍 Searching matching schemes..."):
                # Age aur Income ko number mein convert karo matching ke liye
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
                    only_eligible=False
                )
                st.session_state.assistant_results = results
                st.rerun()
        
        # Show results
        if st.session_state.assistant_results:
            eligible_count = sum(1 for r in st.session_state.assistant_results if r["eligible"])
            
            # ✅ FEATURE 3: AI RECOMMENDATION
            with st.spinner("🤖 AI aapke liye recommendation bana raha hai..."):
                recommendation = generate_ai_recommendation(
                    profile,
                    st.session_state.assistant_results
                )
            
            if recommendation:
                st.info(f"🤖 **AI Recommendation:**\n\n{recommendation}")
            
            st.success(f"✅ Found {len(st.session_state.assistant_results)} schemes ({eligible_count} eligible)")
            
            # Use passed functions
            if render_scheme_card and sort_results and t:
                for r in st.session_state.assistant_results[:8]:
                    render_scheme_card(r, t, "assistant", "English")
            else:
                st.warning("Scheme card rendering functions not provided.")
        
        # Reset button
        if st.button("🔄 Start Over", use_container_width=True, key="reset_assistant_btn"):
            reset_assistant()
            st.rerun()
        
        # ✅ Auto-scroll to bottom (results ke baad)
        auto_scroll_to_bottom()
        return
    
    # --- Not complete - ask next question ---
    if step < total_steps:
        current_q = dynamic_questions[step]
        key = current_q["key"]
        question = current_q["question"]
        options = current_q.get("options", [])
        
        assistant_msg = f"📝 **{question}**"
        
        # Check if already answered
        if key in profile and profile[key] is not None:
            st.chat_message("assistant").markdown(assistant_msg)
            st.chat_message("user").markdown(f"✅ {profile[key]}")
            
            if st.session_state.assistant_step < total_steps:
                st.session_state.assistant_step += 1
                st.rerun()
            return
        
        # Show question
        st.chat_message("assistant").markdown(assistant_msg)
        
        # Show options as buttons
        if options:
            st.markdown("**Choose from options:**")
            cols = st.columns(min(len(options), 4))
            for i, opt in enumerate(options):
                col_idx = i % 4
                with cols[col_idx]:
                    if st.button(opt, key=f"{key}_{opt}_btn", use_container_width=True):
                        st.session_state.assistant_profile[key] = opt
                        st.session_state.assistant_messages.append({"role": "assistant", "content": assistant_msg})
                        st.session_state.assistant_messages.append({"role": "user", "content": opt})
                        st.session_state.assistant_step += 1
                        st.rerun()
            
            # Manual input
            user_input = st.chat_input("Or type your answer here...", key=f"chat_input_{key}")
            if user_input:
                st.session_state.assistant_profile[key] = user_input
                st.session_state.assistant_messages.append({"role": "assistant", "content": assistant_msg})
                st.session_state.assistant_messages.append({"role": "user", "content": user_input})
                st.session_state.assistant_step += 1
                st.rerun()
        else:
            user_input = st.chat_input("Type your answer here...", key=f"chat_input_{key}")
            if user_input:
                st.session_state.assistant_profile[key] = user_input
                st.session_state.assistant_messages.append({"role": "assistant", "content": assistant_msg})
                st.session_state.assistant_messages.append({"role": "user", "content": user_input})
                st.session_state.assistant_step += 1
                st.rerun()
        
        # ✅ Auto-scroll to bottom (next question ke baad)
        auto_scroll_to_bottom()
    
    # --- After all questions ---
    if step >= total_steps and not st.session_state.assistant_complete:
        required_keys = ["age", "state", "gender", "social_category", "income", "occupation"]
        all_answered = all(key in profile for key in required_keys)
        
        if all_answered:
            st.session_state.assistant_complete = True
            
            # ✅ FEATURE 5: SAVE PROFILE
            if save_profile_to_user_data(profile):
                st.toast("✅ Profile saved for next time!")
            
            st.session_state.assistant_messages.append({
                "role": "assistant",
                "content": "✅ **Great! I've understood your profile. Click below to find the best schemes for you!**"
            })
            st.rerun()
        else:
            reset_assistant()
            st.rerun()


# ===========================
# MAIN ASSISTANT RENDER
# ===========================
def render_ai_assistant(render_scheme_card=None, sort_results=None, t=None):
    """
    Render the AI Assistant with all smart features.
    Mode selector is in an expander at the BOTTOM (modern pattern).
    """
    
    if not GROQ_API_KEY:
        st.warning("⚠️ Groq API key not configured. AI features will be limited.")

    # ✅ CSS to increase text size in Assistant mode
    st.markdown("""
    <style>
    /* Chat messages text size */
    div[data-testid="stChatMessage"] p,
    div[data-testid="stChatMessage"] li,
    div[data-testid="stChatMessage"] span {
        font-size: 1.05rem !important;
        line-height: 1.6 !important;
    }
    
    /* Chat message name (role) */
    div[data-testid="stChatMessage"] .stChatMessageName {
        font-size: 1rem !important;
    }
    
    /* Buttons text size */
    .stButton > button {
        font-size: 1rem !important;
        padding: 12px 18px !important;
    }
    
    /* Caption / small text */
    .stCaption, small {
        font-size: 0.95rem !important;
    }
    
    /* Expander header */
    .streamlit-expanderHeader {
        font-size: 1rem !important;
    }
    
    /* Radio buttons text */
    .stRadio label p {
        font-size: 1rem !important;
    }
    
    /* Markdown headings inside assistant */
    div[data-testid="stChatMessage"] h1,
    div[data-testid="stChatMessage"] h2,
    div[data-testid="stChatMessage"] h3,
    div[data-testid="stChatMessage"] h4 {
        font-size: 1.15rem !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🤖 AI Sarkari Scheme Assistant")
    st.caption("Apne baare mein batao, main best schemes suggest karunga!")
    
    # Initialize session state
    init_assistant_state()
    
    # Load schemes data
    df = load_schemes()
    
    # ✅ Get current mode from session_state (default: profile)
    if "assistant_mode" not in st.session_state:
        st.session_state.assistant_mode = "profile"
    
    current_mode = st.session_state.assistant_mode
    
    # ✅ RENDER CONTENT BASED ON MODE
    if current_mode == "nl":
        render_nl_chat_mode(df, render_scheme_card, sort_results, t)
    elif current_mode == "chat":
        ai_chatbot_ui()
    else:
        render_profile_mode(df, render_scheme_card, sort_results, t)
    
    # ✅ MODE SELECTOR AT BOTTOM (in expander - modern pattern)
    st.divider()
    
    # Show current mode badge
    mode_labels = {
        "profile": "Quick Profile",
        "nl": "Describe Problem",
        "chat": "Just Chat"
    }
    
    current_mode_label = mode_labels.get(current_mode, "Unknown")
    st.caption(f"**Current mode:** {current_mode_label}")
    
    with st.expander("Change Assistant Mode", expanded=False):
        mode_options = {
            "profile": "Quick Profile (Step-by-step questions)",
            "nl": "Describe Your Problem (Natural language)",
            "chat": "Just Chat (Free conversation)"
        }
        
        selected_mode = st.radio(
            "Choose mode:",
            options=list(mode_options.keys()),
            format_func=lambda x: mode_options[x],
            index=list(mode_options.keys()).index(current_mode),
            key="bottom_mode_selector"
        )
        
        if selected_mode != current_mode:
            st.session_state.assistant_mode = selected_mode
            st.rerun()

# ===========================
# LEGACY CHATBOT (Fallback)
# ===========================
def get_llm():
    """Returns configured LLM instance."""
    if not GROQ_API_KEY:
        return None
    try:
        llm = ChatGroq(
            temperature=0.7,
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile"
        )
        return llm
    except Exception:
        return None


def create_conversation():
    """Creates a conversation chain with memory."""
    df = load_schemes()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful government scheme assistant. Help users find schemes in India. Answer in Hinglish (Hindi + English) if the user writes in Hindi or Hinglish."),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{input}")
    ])
    
    llm = get_llm()
    if not llm:
        return None
    
    chain = prompt | llm
    
    store = {}
    
    def get_session_history(session_id: str):
        if session_id not in store:
            store[session_id] = ChatMessageHistory()
        return store[session_id]
    
    def get_schemes_and_invoke(input_dict):
        user_query = input_dict["input"]
        schemes_text = "Available schemes data is loaded in the system."
        input_dict["schemes_data"] = schemes_text
        return input_dict
    
    final_chain = RunnableLambda(get_schemes_and_invoke) | chain
    
    conversation = RunnableWithMessageHistory(
        final_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="history"
    )
    
    return conversation


def ai_chatbot_ui():
    """Legacy AI Chatbot UI (fallback for free-form chat)."""
    st.markdown("### 🤖 AI Sarkari Scheme Assistant")
    st.caption("Apni samasya likhein, AI aapki madad karega!")

    try:
        conversation = create_conversation()

        if "ai_messages" not in st.session_state:
            st.session_state.ai_messages = []

        if "ai_conversation" not in st.session_state:
            st.session_state.ai_conversation = conversation

        if "_ai_session_id" not in st.session_state:
            st.session_state["_ai_session_id"] = str(id(st.session_state))

        for message in st.session_state.ai_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        user_input = st.chat_input(
            "Yahan likho... (e.g. Mujhe 25 saal ki ladki ki shaadi ke liye scheme chahiye)",
            key="ai_chat_input"
        )

        if user_input:
            st.session_state.ai_messages.append({"role": "user", "content": user_input})

            with st.chat_message("user"):
                st.markdown(user_input)

            with st.chat_message("assistant"):
                with st.spinner("AI soch raha hai..."):
                    try:
                        response = st.session_state.ai_conversation.invoke(
                            {"input": user_input},
                            config={"configurable": {"session_id": st.session_state["_ai_session_id"]}}
                        )

                        response_text = response.content

                        st.markdown(response_text)
                        st.session_state.ai_messages.append({"role": "assistant", "content": response_text})
                        
                        # Log for analytics
                        log_assistant_query(user_input, 0)
                    except Exception as e:
                        error_msg = f"Error: {str(e)}. Kya aapne Groq API key sahi daali hai?"
                        st.error(error_msg)
                        st.session_state.ai_messages.append({"role": "assistant", "content": error_msg})
        
        # ✅ Auto-scroll to bottom (har chat message ke baad)
        auto_scroll_to_bottom()
        
        # Reset button
        if st.session_state.ai_messages:
            if st.button("🔄 Start New Chat", use_container_width=True, key="reset_ai_chat"):
                st.session_state.ai_messages = []
                st.rerun()
                
    except Exception as e:
        st.error(f"⚠️ Error: {str(e)}")
        st.info("Tip: Kya aapne `pip install langchain langchain-groq` kiya hai?")