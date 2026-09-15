import os
from typing import Optional

# Base directory mapping email addresses to Telegram chat IDs.
# For testing, we dynamically map the mock attendees to your MANAGER_CHAT_ID
# so all simulated member messages reach your Telegram account.
_manager_id = os.getenv("MANAGER_CHAT_ID")

USER_DIRECTORY = {
    "dani@example.com": 8621732852,
    "yossi@example.com": 8621732852 #todo swich to ilays num
}


def get_chat_id_by_email(email: str) -> Optional[str]:
    """Retrieves the Telegram chat ID associated with a user's email."""
    normalized_email = email.strip().lower()
    return USER_DIRECTORY.get(normalized_email)


def get_email_by_chat_id(chat_id: str) -> Optional[str]:
    """Resolves an incoming Telegram chat ID back to the user's email address."""
    chat_id_str = str(chat_id).strip()
    for email, registered_id in USER_DIRECTORY.items():
        if registered_id and str(registered_id) == chat_id_str:
            return email
    return None

def get_manager_chat_id() -> str:
    return os.getenv("MANAGER_CHAT_ID", "")