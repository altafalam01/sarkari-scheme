"""
Simple Explain Module
- Generates easy-to-understand explanation for schemes
- Uses Groq AI when API key is available
- Falls back to simple text when API key is not available
"""

import os
from dotenv import load_dotenv
import streamlit as st

# Try to load langchain_groq (optional)
try:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ===========================
# AI-BASED EXPLANATION
# ===========================
def explain_scheme_ai(scheme_name, description, benefits, lang_choice, category_type, applicable_state, apply_link, deadline, eligible, score):
    """
    Generate explanation using Groq AI.
    """
    if not GROQ_API_KEY:
        return None  # Fallback to simple text
    
    if not HAS_GROQ:
        return None  # Fallback to simple text
    
    try:
        llm = ChatGroq(
            temperature=0.7,
            groq_api_key=GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile"
        )
        
        # Language-based prompt
        if lang_choice == "हिंदी":
            system_prompt = "आप एक सहायक हैं। सरकारी योजनाओं को सरल हिंदी में समझाएं। 2-3 वाक्यों में रखें।"
        elif lang_choice == "मराठी":
            system_prompt = "तुम्ही एक सहाय्यक आहात. सरकारी योजना सोप्या मराठीत समजावून सांगा. 2-3 वाक्यांत ठेवा."
        elif lang_choice == "தமிழ்":
            system_prompt = "நீங்கள் ஒரு உதவியாளர். அரசாங்க திட்டங்களை எளிய தமிழில் விளக்குங்கள். 2-3 வாக்கியங்களில் வைக்கவும்."
        else:
            system_prompt = "You are a helpful assistant. Explain government schemes in simple English. Keep it concise (2-3 sentences)."
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Scheme: {scheme_name}\nCategory: {category_type}\nDescription: {description}\nBenefits: {benefits}\nState: {applicable_state}\n\nExplain this scheme in simple words for a common person.")
        ])
        
        chain = prompt | llm
        response = chain.invoke({
            "scheme_name": scheme_name,
            "description": description,
            "benefits": benefits,
            "category_type": category_type,
            "applicable_state": applicable_state,
        })
        
        return response.content
    except Exception as e:
        return f"❌ Error: {e}"

# ===========================
# SIMPLE TEXT EXPLANATION (Fallback)
# ===========================
def explain_scheme_text(scheme_name, description, benefits, lang_choice, category_type, applicable_state, apply_link, deadline, eligible, score):
    """
    Generate simple text explanation without AI.
    """
    if lang_choice == "हिंदी":
        return f"**{scheme_name}** एक {category_type} योजना है। इसका मुख्य उद्देश्य है: {description}। इसमें आपको ये लाभ मिलते हैं: {benefits}। आप {applicable_state} से आवेदन कर सकते हैं।"
    elif lang_choice == "मराठी":
        return f"**{scheme_name}** ही एक {category_type} योजना आहे. याचा मुख्य उद्देश्य आहे: {description}. यामध्ये तुम्हाला हे लाभ मिळतात: {benefits}. तुम्ही {applicable_state} मधून अर्ज करू शकता."
    elif lang_choice == "தமிழ்":
        return f"**{scheme_name}** என்பது ஒரு {category_type} திட்டம். இதன் முக்கிய நோக்கம்: {description}. இதில் உங்களுக்கு இந்த பலன்கள் கிடைக்கும்: {benefits}. நீங்கள் {applicable_state} இலிருந்து விண்ணப்பிக்கலாம்."
    else:
        return f"**{scheme_name}** is a {category_type} scheme. Its main objective is: {description}. You get these benefits: {benefits}. You can apply from {applicable_state}."

# ===========================
# MAIN EXPLAIN FUNCTION
# ===========================
def explain_scheme(scheme_name, description, benefits, lang_choice, category_type, applicable_state, apply_link, deadline, eligible, score):
    """
    Main function to generate explanation.
    Uses AI if available, otherwise falls back to simple text.
    """
    # Try AI first
    ai_response = explain_scheme_ai(
        scheme_name=scheme_name,
        description=description,
        benefits=benefits,
        lang_choice=lang_choice,
        category_type=category_type,
        applicable_state=applicable_state,
        apply_link=apply_link,
        deadline=deadline,
        eligible=eligible,
        score=score
    )
    
    # If AI response is valid, use it
    if ai_response and "❌" not in ai_response:
        return ai_response
    
    # Otherwise, fall back to simple text
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
        score=score
    )