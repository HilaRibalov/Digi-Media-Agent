from langchain_core.tools import tool
#mooking the tools activity for this version

@tool
def create_drive_folder(folder_path: str) -> str:
    """Creates a new Google Drive folder at the specified path and returns the folder URL."""
    print(f"\n[Tool Execution] Creating Drive folder at path: {folder_path}...")
    return f"https://drive.google.com/drive/folders/mock_folder_{folder_path.replace('/', '_')}"


# tools.py (Replace the existing check_drive_uploads function)

@tool
def check_drive_uploads(folder_url: str):
    """Checks for newly uploaded files in the Drive folder."""
    print(f"\n--- [SYSTEM MOCK: DRIVE] ---")
    user_input = input("Simulate a file upload (e.g. 'yossi@example.com'), or press Enter for no files: ")

    if user_input.strip():
        # Returns a mock file list showing who uploaded
        return [f"photo_from_{user_input.strip()}.jpg"]
    return []

# (בהנחה שזה מעוצב עם @tool, פשוט תחליפי את התוכן של הפונקציה)
@tool
def read_team_messages(event_id: str):
    """Fetches new messages from the team."""
    print("\n--- [SYSTEM MOCK] ---")
    user_msg = input(
        "Simulate an incoming message (e.g. 'dani@example.com: הייתי חולה'), or press Enter for no messages: ")

    if user_msg.strip():
        return [user_msg]
    return []

@tool
def send_team_message(recipient: str, message: str) -> str:
    """Sends a message (Email/WhatsApp/SMS) to a team member.
    Use this for reminders OR conversational replies (e.g., 'Feel better')."""
    print(f"\n[Tool Execution] Sending message to {recipient}:\n{message}")
    return f"Success: Message sent to {recipient}"

@tool
def notify_manager(subject: str, message: str) -> str:
    """Sends a direct notification to the manager via WhatsApp/Email.
    Use this to ask for folder path approval OR to escalate issues (e.g., max reminders reached)."""
    print(f"\n[Tool Execution] Manager Notification! Subject: {subject}\nMessage: {message}")
    return "Success: Manager notified"