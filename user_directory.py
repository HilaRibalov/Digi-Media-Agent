import os
import json
from typing import Optional, Tuple

def _load_users():
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env != "production":
        # Return mock users for testing
        return {
            "hila.ribalov@gmail.com": {"chat_id": 8621732852, "name": "הילה"},
            "eden.kerzer@gmail.com": {"chat_id": 7860079501 , "name": "עדן"},
            "Kerenr@hillelisrael.org": {"chat_id": 8060866350 , "name": "הילה"},
            "dani@example.com": {"chat_id": 8621732852, "name": "דני"},
            "yossi@example.com": {"chat_id": 8621732852, "name": "יוסי"}
        }

    try:
        from db_client import db
        docs = db.collection("users").stream()
        users = {}
        for doc in docs:
            users[doc.id] = doc.to_dict()
        return users
    except Exception as e:
        print(f"Error loading from Firestore: {e}")
        return {}

def get_chat_id_by_email(email: str) -> Optional[str]:
    """Retrieves the Telegram chat ID associated with a user's email."""
    normalized_email = email.strip().lower()
    users = _load_users()
    user_info = users.get(normalized_email)
    if user_info:
        return str(user_info["chat_id"])
    return None

def get_email_by_chat_id(chat_id: str) -> Optional[str]:
    """Resolves an incoming Telegram chat ID back to the user's email address."""
    chat_id_str = str(chat_id).strip()
    users = _load_users()
    for email, info in users.items():
        if info and str(info["chat_id"]) == chat_id_str:
            return email
    return None

def get_user_info_by_chat_id(chat_id: str) -> Optional[Tuple[str, str]]:
    """Returns the (email, name) associated with a chat_id."""
    chat_id_str = str(chat_id).strip()
    users = _load_users()
    for email, info in users.items():
        if info and str(info["chat_id"]) == chat_id_str:
            return email, info.get("name", "Unknown")
    return None

def get_manager_chat_id() -> str:
    return os.getenv("MANAGER_CHAT_ID", "")