from fastapi import FastAPI, Request
import os
import requests
from langgraph.types import Command
from agent import app as graph_app
from user_directory import get_manager_chat_id

app = FastAPI(title="Digi-Media-Agent Webhook Server")

# In-memory flag to track if we are waiting for feedback
manager_state = {"awaiting_feedback": False}

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
    try:
        update = await request.json()
        print("Received update from Telegram:")
        print(update)
        
        manager_chat_id = get_manager_chat_id()
        config = {"configurable": {"thread_id": "demo_event_1"}}
        
        if "callback_query" in update:
            cb = update["callback_query"]
            chat_id = str(cb["message"]["chat"]["id"])
            if chat_id != str(manager_chat_id):
                return {"status": "ignored"}
                
            data = cb.get("data")
            cb_id = cb.get("id")
            answer_callback(cb_id)
            
            if data == "approve_folder":
                state = graph_app.get_state(config)
                current_path = state.values.get("suggested_folder_path")
                
                graph_app.update_state(config, {"approved_folder_path": current_path, "user_feedback": ""})
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
            if chat_id != str(manager_chat_id):
                return {"status": "ignored"}
                
            text = msg.get("text", "")
            
            if manager_state.get("awaiting_feedback") and text:
                manager_state["awaiting_feedback"] = False
                
                graph_app.update_state(config, {"user_feedback": text})
                for _ in graph_app.stream(Command(resume=True), config):
                    pass
                    
            return {"status": "ok"}

        return {"status": "ok"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/health")
def health_check():
    return {"status": "active", "environment": os.getenv("ENVIRONMENT", "production")}
