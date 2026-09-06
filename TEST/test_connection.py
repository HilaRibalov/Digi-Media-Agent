import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# טעינת המפתח מקובץ ה-.env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file!")
else:
    print("Found API Key, testing connection to Gemini...")

    # אתחול המודל
    llm = ChatGoogleGenerativeAI(
        model="gemini-flash-latest",
        google_api_key=api_key,
    )

    # שליחת שאלה קצרה
    response = llm.invoke("Say 'Connection successful!' in Hebrew and English.")
    print("\nResponse from Gemini:")
    print(response.content)