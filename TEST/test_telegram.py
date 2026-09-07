import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("MANAGER_CHAT_ID")


def send_telegram_test():
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "שלום הילה! הבוט שלך מחובר ומבצעי בהצלחה 🎉"
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("✅ ההודעה נשלחה בהצלחה! בדקי את הטלגרם שלך.")
    else:
        print(f"❌ שגיאה בשליחה: {response.text}")


if __name__ == "__main__":
    send_telegram_test()