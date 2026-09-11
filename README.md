# 🇮🇳 Sarkari Scheme Finder

Ek simple chatbot-style tool jo user ke profile (age, income, gender, category, occupation) ke
hisaab se applicable Indian government schemes suggest karta hai.

## Problem
Bharat mein 500+ government schemes hain, lekin common aadmi ko pata nahi hota ki wo kaunsi
scheme ke liye eligible hai. Official websites confusing hain aur scattered information hoti hai.

## Solution
User apna basic profile daalta hai, aur ye tool rule-based matching se relevant schemes
dikhata hai — eligibility criteria, benefits, aur apply link ke saath.

## Tech Stack
- Python
- Pandas (data filtering/matching logic)
- Streamlit (chatbot UI)

## Project Structure
```
scheme-chatbot/
├── data/
│   └── schemes.csv       # 20 central govt schemes ka structured dataset
├── matcher.py             # matching logic (eligibility filtering)
├── app.py                  # Streamlit UI
├── requirements.txt
└── README.md
```

## How to Run Locally

1. Repo clone/download karo
2. Virtual environment banao (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```
3. Dependencies install karo:
   ```
   pip install -r requirements.txt
   ```
4. App run karo:
   ```
   streamlit run app.py
   ```
5. Browser mein automatically open ho jayega (`localhost:8501`)

## Current Scope (v1)
- 20 major central government schemes cover ki gayi hain
- Rule-based filtering (age, income, gender, social category, occupation)
- State-specific schemes abhi included nahi hain (future scope)

## Roadmap / Future Improvements
- [ ] State-specific schemes add karna
- [ ] Natural language query support (NLP se free text samajhna)
- [ ] Hindi/regional language interface
- [ ] Data ko myscheme.gov.in se automated scraping se update karna
- [ ] User feedback collection mechanism

## Disclaimer
Ye ek student project hai jo educational/portfolio purpose ke liye bana hai. Ye official
government advice nahi hai. Eligibility final confirm karne ke liye hamesha official
government website check karein.

## Data Source
Scheme details publicly available government sources (myscheme.gov.in, respective ministry
websites) se manually curate kiye gaye hain.
