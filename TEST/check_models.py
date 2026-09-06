import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

print("Checking ALL available Gemini models for your API key...\n")
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
response = requests.get(url)

if response.status_code == 200:
    models = response.json().get("models", [])
    print("Available Gemini models:")
    for model in models:
        name = model["name"].replace("models/", "")
        if "gemini" in name.lower():
            print(f"- {name}")
else:
    print(f"API Error: {response.status_code} - {response.text}")
