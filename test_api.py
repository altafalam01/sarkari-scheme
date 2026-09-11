import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
model = os.getenv("GROQ_MODEL_NAME")

print(f"API Key: {api_key}")
print(f"Model: {model}")

if api_key and api_key.startswith("gsk_"):
    print("✅ API Key format is correct!")
else:
    print("❌ API Key format is wrong! It should start with 'gsk_'")