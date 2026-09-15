import os
import requests
from langchain_core.tools import tool
from user_directory import get_chat_id_by_email, get_manager_chat_id

import google.auth
from googleapiclient.discovery import build

def _get_drive_service():
    credentials, project = google.auth.default(scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=credentials)

# Internal helper function to dispatch messages via Telegram Bot API
def _send_telegram_message(chat_id: str, text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or not chat_id:
        print("[Telegram Error] Missing TELEGRAM_BOT_TOKEN or chat_id in environment.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"[Telegram API Error] Failed to send message: {e}")
        return False

@tool
def get_drive_categories(main_parent_id: str) -> dict:
    """Gets available folder categories in the parent drive folder."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env != "production":
        return {"אירועים כלליים": "mock_id_1", "תוכניות": "mock_id_2"}
        
    try:
        service = _get_drive_service()
        query = f"'{main_parent_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'"
        results = service.files().list(q=query, fields="nextPageToken, files(id, name)").execute()
        items = results.get('files', [])
        return {item['name']: item['id'] for item in items}
    except Exception as e:
        print(f"[Drive API Error] {e}")
        return {}


@tool
def create_drive_folder(folder_name: str, parent_id: str) -> str:
    """Creates a new Google Drive folder and returns the folder URL."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env != "production":
        print(f"\n[Tool Execution] Creating Drive folder '{folder_name}' in '{parent_id}'...")
        return f"https://drive.google.com/drive/folders/mock_folder_{folder_name.replace(' ', '_')}"
        
    try:
        service = _get_drive_service()
        file_metadata = {
            'name': folder_name,
            'parents': [parent_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = service.files().create(body=file_metadata, fields='id, webViewLink').execute()
        return file.get('webViewLink')
    except Exception as e:
        print(f"[Drive API Error] {e}")
        raise

@tool
def check_drive_uploads(folder_url_or_id: str) -> list:
    """Checks for newly uploaded files in the Drive folder."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env != "production":
        # Only prompt for file uploads if explicitly requested via the simulation menu
        if os.getenv("MOCK_PROMPT_TYPE") != "upload":
            return []
        print("\n--- [SYSTEM MOCK: DRIVE] ---")
        user_input = input("Simulate a file upload (e.g. 'yossi@example.com'), or press Enter for no files: ")
        if user_input.strip():
            return [f"photo_from_{user_input.strip()}.jpg"]
        return []

    try:
        folder_id = folder_url_or_id.split("/")[-1] if "/" in folder_url_or_id else folder_url_or_id
        service = _get_drive_service()
        query = f"'{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(lastModifyingUser)").execute()
        items = results.get('files', [])
        uploaders = set()
        for item in items:
            user = item.get('lastModifyingUser', {})
            email = user.get('emailAddress')
            if email:
                uploaders.add(email)
        return list(uploaders)
    except Exception as e:
        print(f"[Drive API Error] {e}")
        return []

@tool
def read_team_messages(event_id: str) -> list:
    """Fetches new messages from the team members."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        # In production, participant messages are injected directly into state via webhook
        return []

    # Only prompt for incoming messages if explicitly requested via the simulation menu
    if os.getenv("MOCK_PROMPT_TYPE") != "chat":
        return []

    print("\n--- [SYSTEM MOCK: TELEGRAM] ---")
    user_msg = input("Simulate an incoming message (e.g. 'dani@example.com: הייתי חולה'), or press Enter for no messages: ")

    if user_msg.strip():
        return [user_msg]
    return []

@tool
def send_team_message(recipient: str, message: str) -> str:
    """Sends a direct message to a team member.
    Used for dispatching reminders or conversational replies."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        target_chat_id = get_chat_id_by_email(recipient)
        if not target_chat_id:
            print(f"\n[Production Tool Error] No Telegram chat ID found for recipient: {recipient}")
            return f"Error: Recipient {recipient} is not registered in user directory."

        telegram_payload = f"[Message to {recipient}]:\n\n{message}"
        success = _send_telegram_message(target_chat_id, telegram_payload)

        if success:
            print(f"\n[Production Tool] Sent live Telegram message destined for {recipient}.")
            return f"Success: Message delivered to {recipient} via Telegram."
        else:
            return f"Error: Failed to deliver message to {recipient} via Telegram."
    else:
        print(f"\n[Tool Execution] Sending message to {recipient}:\n{message}")
        return f"Success: Message sent to {recipient}"

@tool
def notify_manager(subject: str, message: str) -> str:
    """Sends a direct notification to the manager.
    Used to request folder path approval or escalate issues."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        target_chat_id = get_manager_chat_id()
        if not target_chat_id:
            print("\n[Production Tool Error] No manager chat ID configured.")
            return "Error: Manager chat ID missing."

        telegram_payload = f" [MANAGER NOTIFICATION]\nSubject: {subject}\n\n{message}"
        success = _send_telegram_message(target_chat_id, telegram_payload)

        if success:
            print(f"\n[Production Tool] Sent live manager alert to Telegram.")
            return "Success: Manager notified via Telegram."
        else:
            return "Error: Failed to notify manager via Telegram."
    else:
        print(f"\n[Tool Execution] Manager Notification! Subject: {subject}\nMessage: {message}")
        return "Success: Manager notified"

def request_folder_approval(category_name: str, folder_name: str) -> None:
    """Sends a Telegram message to the manager with an Inline Keyboard for folder approval."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    msg_text = f"אני מציע ליצור את התיקייה '{folder_name}' תחת הקטגוריה '{category_name}'"
    
    if env == "production":
        manager_chat_id = get_manager_chat_id()
        if not manager_chat_id:
            print("\n[Production Tool Error] No manager chat ID configured.")
            return

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": manager_chat_id,
            "text": msg_text,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "אשרי תיקייה", "callback_data": "approve_folder"},
                        {"text": "דחי והזיני תיקון", "callback_data": "reject_folder"}
                    ]
                ]
            }
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print("\n[Production Tool] Sent folder approval request to manager.")
        except requests.RequestException as e:
            print(f"[Telegram API Error] Failed to send approval request: {e}")
    else:
        print(f"\n[Tool Execution] Manager Approval Request: {msg_text}")
