import os
from typing import Optional, Tuple

_manager_id = os.getenv("MANAGER_CHAT_ID")

USER_DIRECTORY = {
    "hila.ribalov@gmail.com": {"chat_id": 8621732852, "name": "הילה"},
    "dani@example.com": {"chat_id": 8621732852, "name": "דני"},
    "yossi@example.com": {"chat_id": 8621732852, "name": "יוסי"} #todo swich to ilays num
}

def get_chat_id_by_email(email: str) -> Optional[str]:
    """Retrieves the Telegram chat ID associated with a user's email."""
    normalized_email = email.strip().lower()
    user_info = USER_DIRECTORY.get(normalized_email)
    if user_info:
        return str(user_info["chat_id"])
    return None

def get_email_by_chat_id(chat_id: str) -> Optional[str]:
    """Resolves an incoming Telegram chat ID back to the user's email address."""
    chat_id_str = str(chat_id).strip()
    for email, info in USER_DIRECTORY.items():
        if info and str(info["chat_id"]) == chat_id_str:
            return email
    return None

def get_user_info_by_chat_id(chat_id: str) -> Optional[Tuple[str, str]]:
    """Returns the (email, name) associated with a chat_id."""
    chat_id_str = str(chat_id).strip()
    for email, info in USER_DIRECTORY.items():
        if info and str(info["chat_id"]) == chat_id_str:
            return email, info.get("name", "Unknown")
    return None

def get_manager_chat_id() -> str:
    return os.getenv("MANAGER_CHAT_ID", "")