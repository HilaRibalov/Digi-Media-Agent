import os
from langchain_core.tools import tool

# Mocking the tools activity for the local simulation environment

@tool
def create_drive_folder(folder_path: str) -> str:
    """Creates a new Google Drive folder at the specified path and returns the folder URL."""
    print(f"\n[Tool Execution] Creating Drive folder at path: {folder_path}...")
    return f"https://drive.google.com/drive/folders/mock_folder_{folder_path.replace('/', '_')}"


@tool
def check_drive_uploads(folder_url: str) -> list:
    """Checks for newly uploaded files in the Drive folder."""
    # Only prompt for file uploads if explicitly requested via the simulation menu
    if os.getenv("MOCK_PROMPT_TYPE") != "upload":
        return []

    print("\n--- [SYSTEM MOCK: DRIVE] ---")
    user_input = input("Simulate a file upload (e.g. 'yossi@example.com'), or press Enter for no files: ")

    if user_input.strip():
        # Return a mock file list showing the uploader's identity
        return [f"photo_from_{user_input.strip()}.jpg"]
    return []


@tool
def read_team_messages(event_id: str) -> list:
    """Fetches new messages from the team members."""
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
    print(f"\n[Tool Execution] Sending message to {recipient}:\n{message}")
    return f"Success: Message sent to {recipient}"


@tool
def notify_manager(subject: str, message: str) -> str:
    """Sends a direct notification to the manager.
    Used to request folder path approval or escalate issues."""
    print(f"\n[Tool Execution] Manager Notification! Subject: {subject}\nMessage: {message}")
    return "Success: Manager notified"