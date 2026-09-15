from fastapi import FastAPI, Request
import os
import requests
import uuid
import json
from langgraph.types import Command
from agent import app as graph_app
from user_directory import get_manager_chat_id, get_user_info_by_chat_id

app = FastAPI(title="Digi-Media-Agent Webhook Server")

# In-memory flag to track if we are waiting for feedback
manager_state = {"awaiting_feedback": False}

# Onboarding state for new users
ONBOARDING_STATE = {}

ACTIVE_THREAD_ID = "default_1"

def send_msg(chat_id, text):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)

def answer_callback(callback_query_id):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    requests.post(url, json={"callback_query_id": callback_query_id}, timeout=10)

@app.post("/webhook")
async def telegram_webhook(request: Request):
    global ACTIVE_THREAD_ID
    try:
        update = await request.json()
        print("Received update from Telegram:")
        print(update)
        
        manager_chat_id = get_manager_chat_id()
        config = {"configurable": {"thread_id": ACTIVE_THREAD_ID}}
        
        if "callback_query" in update:
            cb = update["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            if chat_id != str(manager_chat_id):
                return {"status": "ignored"}
                
            data = cb.get("data")
            cb_id = cb.get("id")
            answer_callback(cb_id)
            
            if data == "approve_folder":
                graph_app.update_state(config, {"user_feedback": ""})
                for _ in graph_app.stream(Command(resume=True), config):
                    pass
                send_msg(chat_id, "התיקייה אושרה בהצלחה! ממשיך ביצירתה.")
                
            elif data == "reject_folder":
                manager_state["awaiting_feedback"] = True
                send_msg(chat_id, "התיקייה נדחתה. אנא כתבי בהודעה הבאה מה התיקון הנדרש.")
                
            return {"status": "ok"}
            
        if "message" in update:
            msg = update["message"]
            chat_id = str(msg["chat"]["id"])
            text = msg.get("text", "")
            
            if chat_id == str(manager_chat_id):
                if text.strip() == "תזכורת יומית":
                    send_msg(chat_id, "יוזם בדיקת חוסרים ושליחת תזכורות לכל מי שטרם העלה תמונות...")
                    graph_app.invoke({"wakeup_reason": "daily_cron"}, config=config)
                    return {"status": "ok"}
                elif manager_state.get("awaiting_feedback") and text:
                    manager_state["awaiting_feedback"] = False
                    graph_app.update_state(config, {"user_feedback": text})
                    for _ in graph_app.stream(Command(resume=True), config):
                        pass
                    return {"status": "ok"}
                elif text.startswith("אירוע חדש:"):
                    ACTIVE_THREAD_ID = str(uuid.uuid4())
                    config = {"configurable": {"thread_id": ACTIVE_THREAD_ID}}
                    graph_app.update_state(config, {"manager_raw_prompt": text})
                    for _ in graph_app.stream(None, config):
                        pass
                    send_msg(chat_id, "קיבלתי! מתחיל לתכנן את האירוע...")
                    return {"status": "ok"}
            
            if text:
                user_info = get_user_info_by_chat_id(chat_id)
                if user_info:
                    # User is known, pass to LangGraph
                    email, name = user_info
                    formatted_message = f"[{name}/{email}]: {text}"
                    graph_app.invoke(
                        {"incoming_participant_messages": [formatted_message], "wakeup_reason": "message"},
                        config=config
                    )
                else:
                    # User is unknown, handle onboarding
                    if chat_id not in ONBOARDING_STATE:
                        ONBOARDING_STATE[chat_id] = {"state": "WAITING_FOR_NAME"}
                        send_msg(chat_id, "ברוך הבא! כדי שנוכל לקשר את התמונות שתעלה, איך קוראים לך?")
                    elif ONBOARDING_STATE[chat_id]["state"] == "WAITING_FOR_NAME":
                        ONBOARDING_STATE[chat_id]["name"] = text.strip()
                        ONBOARDING_STATE[chat_id]["state"] = "WAITING_FOR_EMAIL"
                        send_msg(chat_id, "נעים להכיר! מה כתובת המייל שלך (זו שמוגדרת בגוגל דרייב)?")
                    elif ONBOARDING_STATE[chat_id]["state"] == "WAITING_FOR_EMAIL":
                        email = text.strip().lower()
                        name = ONBOARDING_STATE[chat_id]["name"]
                        
                        try:
                            with open("users.json", "r", encoding="utf-8") as f:
                                users = json.load(f)
                        except FileNotFoundError:
                            users = {}
                        
                        users[email] = {"chat_id": int(chat_id), "name": name}
                        
                        with open("users.json", "w", encoding="utf-8") as f:
                            json.dump(users, f, ensure_ascii=False, indent=4)
                            
                        del ONBOARDING_STATE[chat_id]
                        send_msg(chat_id, "מעולה, נרשמת בהצלחה!")
                    
            return {"status": "ok"}

        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/health")
def health_check():
    return {"status": "active", "environment": os.getenv("ENVIRONMENT", "production")}
