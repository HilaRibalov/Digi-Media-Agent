import os
import json
import datetime
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# Import state schema and custom tool implementations
from state import AgentState
from tools import (
    create_drive_folder,
    check_drive_uploads,
    read_team_messages,
    send_team_message,
    notify_manager,
    request_folder_approval
)

# Load environment configuration
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file!")

# Initialize LLM client
llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    google_api_key=api_key
)

# Register external tools available to the model
tools_list = [
    create_drive_folder,
    check_drive_uploads,
    read_team_messages,
    send_team_message,
    notify_manager
]

# Bind tools to the model instance
llm_with_tools = llm.bind_tools(tools_list)

# Initialize the state graph with the unified AgentState schema
workflow = StateGraph(AgentState)


# ==========================================
# Graph Nodes
# ==========================================

def find_space_to_save(state: AgentState):
    """Node: Analyzes event details and suggests a Google Drive folder path."""
    print("\n[Node] Executing 'find_space_to_save'...")

    event_name = state.get("event_name", "Unknown_Event")
    event_date = state.get("event_date", "Unknown_Date")
    user_feedback = state.get("user_feedback")

    system_instruction = (
        "You are an assistant organizing Google Drive folders. "
        "Suggest a logical folder path based on the event name and date. "
        "Use the exact format: הפרויקטים שלי/הלל דיגיטל/בן גוריון/תשפז/אירועים/Event_Name - Event_Date\n"
        "Do NOT include a separate year folder (like /2026/).\n"
        "Return ONLY the path string, without markdown or extra text."
    )

    if user_feedback:
        system_instruction += f"\n\nCRITICAL: The manager rejected the previous path with this feedback: '{user_feedback}'. Adjust the path accordingly."

    prompt_messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=f"Event Name: {event_name}\nEvent Date: {event_date}")
    ]

    response = llm.invoke(prompt_messages)

    # Safe extraction of text content regardless of response format
    content = response.content
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict):
            suggested_path = content[0].get("text", "").strip()
        else:
            suggested_path = str(content[0]).strip()
    else:
        suggested_path = str(content).strip()

    print(f"[Node] The LLM suggested the path: {suggested_path}")
    
    # Request manager approval for the suggested path
    request_folder_approval(suggested_path)

    return {
        "suggested_folder_path": suggested_path,
        "folder_approval_status": "pending",
        "user_feedback": "",  # Clear feedback post-consumption to prevent recursive loops
        "messages": [SystemMessage(content=f"Suggested folder path: {suggested_path}")]
    }


def create_drive_space(state: AgentState):
    """Node: Creates the actual folder in Google Drive with error handling."""
    print("\n[Node] Executing 'create_drive_space'...")

    final_path = state.get("approved_folder_path") or state.get("suggested_folder_path")

    try:
        # Execute Google Drive folder provisioning
        folder_url = create_drive_folder.invoke(final_path)
        print(f"[Node] Folder created successfully! URL: {folder_url}")

        return {
            "folder_url": folder_url,
            "folder_approval_status": "approved",
            "messages": [SystemMessage(content=f"Folder created at URL: {folder_url}")]
        }

    except Exception as e:
        # Handle third-party API failures and notify administration
        error_msg = f"Failed to create Google Drive folder at path '{final_path}': {str(e)}"
        print(f"[Node Error] {error_msg}")

        notify_manager.invoke({
            "subject": "שגיאת מערכת: כשל ביצירת תיקיית Drive",
            "message": f"הסוכן נתקל בשגיאה ביצירת התיקייה בנתיב: {final_path}.\nפירוט השגיאה: {str(e)}\nהתהליך הופסק זמנית."
        })

        return {
            "collection_phase_status": "error",
            "messages": [SystemMessage(content=error_msg)]
        }


def gather_updates(state: AgentState):
    """Node: Uses tools to fetch Drive uploads and incoming team messages."""
    print("\n[Node] Executing 'gather_updates'...")

    folder_url = state.get("folder_url", "")
    event_id = state.get("event_id", "Unknown_ID")

    new_files = check_drive_uploads.invoke(folder_url)
    incoming_messages = read_team_messages.invoke(event_id)

    system_msg_content = (
        f"System Update - Gathered Data:\n"
        f"New files found: {new_files}\n"
        f"New messages received: {incoming_messages}"
    )

    print(f"[Node] Found {len(new_files)} new files and {len(incoming_messages)} new messages.")

    return {
        "uploaded_files": new_files,
        "messages": [SystemMessage(content=system_msg_content)]
    }


def evaluate_and_filter(state: AgentState):
    """Node: The Brain. Evaluates who is still missing based on files and messages."""
    print("\n[Node] Executing 'evaluate_and_filter'...")

    missing = state.get("missing_attendees", [])

    # Bypass LLM invocation if the list is already empty to save time and API costs
    if not missing:
        print("[Node] No missing attendees left!")
        return {"collection_phase_status": "finished", "trigger_post_creation": True}

    last_system_msg = state["messages"][-1].content

    # Instruction defining strict logical criteria for attendance list updates.
    # CRITICAL FIX: Expanded exemption criteria to include lack of media.
    system_instruction = (
        "You are managing a missing attendees list for a media collection event. "
        f"Current missing attendees: {missing}\n\n"
        "Read the system update. Team messages will be in Hebrew. Remove an attendee from the missing list IF AND ONLY IF:\n"
        "1. The System Update explicitly shows a file was uploaded by them.\n"
        "2. They sent a message indicating they are EXEMPT or CANNOT PROVIDE MEDIA (e.g., 'הייתי חולה', 'לא הייתי באירוע', 'אין לי תמונות', 'שכחתי לצלם').\n"
        "CRITICAL: Do NOT remove them if they merely claim to have uploaded, but their name is NOT in the new files list.\n"
        "Return ONLY a valid JSON array of strings containing the updated missing attendees."
    )

    prompt_messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=last_system_msg)
    ]

    response = llm.invoke(prompt_messages)

    # Safe extraction of structured output from LLM response
    content = response.content
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict):
            raw_text = content[0].get("text", "")
        else:
            raw_text = str(content[0])
    else:
        raw_text = str(content)

    # Robust JSON parsing block.
    try:
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        updated_missing = json.loads(clean_text)

        # Ensure the output format strictly remains a list of strings
        if isinstance(updated_missing, dict):
            lists = [v for v in updated_missing.values() if isinstance(v, list)]
            updated_missing = lists[0] if lists else missing
        elif not isinstance(updated_missing, list):
            updated_missing = missing

    except Exception as e:
        print(f"[Error parsing JSON, keeping original list] {e}")
        updated_missing = missing

    print(f"[Node] Updated missing attendees list: {updated_missing}")

    # Determine collection status based on the updated list length
    status = "running"
    ready_for_post = False
    if len(updated_missing) == 0:
        status = "finished"
        ready_for_post = True

        # Trigger manager completion notification immediately upon finishing the task
        event_title = state.get("event_name", "אירוע ללא שם")
        notify_manager.invoke({
            "subject": f"איסוף המדיה הושלם: {event_title}",
            "message": f"כל המשתתפים העלו תמונות או קיבלו פטור עבור האירוע '{event_title}'. התיקייה מוכנה!"
        })

    return {
        "missing_attendees": updated_missing,
        "collection_phase_status": status,
        "trigger_post_creation": ready_for_post,
        "messages": [SystemMessage(content=f"Brain evaluation complete. Still missing: {updated_missing}")]
    }


def reply_to_messages(state: AgentState):
    """Node: Handles replying to incoming messages without issuing general reminders."""
    print("\n[Node] Executing 'reply_to_messages'...")

    # Contextual instruction: Ensures the agent provides accurate support by cross-referencing user claims.
    system_instruction = (
        "You are a polite assistant managing team communications.\n"
        "Your ONLY task is to read recent incoming messages in the system update and reply to them.\n"
        "CRITICAL VERIFICATION: If a user claims they uploaded a file, you MUST check the 'New files found' section in the context. "
        "If their file is NOT there, politely inform them that the system hasn't received it yet and ask them to check the link. "
        "If their file IS there, thank them.\n"
        "Use the 'send_team_message' tool to reply politely.\n"
        "CRITICAL: You must write all your replies in Hebrew (עברית).\n"
        "DO NOT send general reminders here."
    )

    recent_context = "\n".join([m.content for m in state["messages"][-2:]])

    prompt_messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=f"Context from recent steps:\n{recent_context}")
    ]

    response = llm_with_tools.invoke(prompt_messages)

    # Track actions taken by the LLM for logging and debugging
    action_summary = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "send_team_message":
                send_team_message.invoke(tool_call["args"])
                action_summary.append(f"Replied to {tool_call['args'].get('recipient')}")
    else:
        action_summary.append("No replies needed.")

    # Removed the redundant 'Reply summary' print statement for a cleaner CLI output.

    return {"messages": [SystemMessage(content=f"Replies executed: {action_summary}")]}


def send_reminders(state: AgentState):
    """Node: Dispatches initial requests and progressive reminders to missing attendees."""
    print("\n[Node] Executing 'send_reminders'...")

    missing = state.get("missing_attendees", [])
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    current_count = state.get("reminder_count", 0)
    folder_url = state.get("folder_url", "URL_NOT_FOUND")

    # Determine progressive escalation tone based on reminder round count
    if current_count == 0:
        tone_instruction = (
            "This is the FIRST outreach. Send a warm, friendly invitation to upload media. "
            "Let them know you are here to help if they run into technical issues uploading to Drive, "
            "and if you can't solve it, they can reach out to Hila."
        )
    elif current_count == 1:
        tone_instruction = (
            "This is the SECOND reminder. Be slightly more direct and urgent. "
            "Gently remind them that the team is waiting for their files to complete the event gallery. "
            "Remind them to reach out if they have technical trouble, or contact Hila directly."
        )
    else:
        tone_instruction = (
            "This is the THIRD (and final automated) reminder. Be firm, professional, and urgent. "
            "Emphasize that this is the last call before the task escalates to management. "
            "Offer technical support or direct them to Hila immediately."
        )

    system_instruction = (
        "You are a polite, human-like coordinator managing team media collection.\n"
        f"Currently missing attendees: {missing}\n"
        f"Google Drive Folder URL: {folder_url}\n"
        f"Tone guidelines: {tone_instruction}\n"
        "Use the 'send_team_message' tool to message each missing attendee individually.\n"
        "CRITICAL: Vary the phrasing slightly for each person so it feels like a real conversation, not a mass broadcast.\n"
        "CRITICAL: You MUST include the Google Drive Folder URL.\n"
        "CRITICAL: Write all messages in Hebrew (עברית)."
    )

    recent_context = "\n".join([m.content for m in state["messages"][-2:]])
    prompt_messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=f"Context from recent steps:\n{recent_context}")
    ]

    response = llm_with_tools.invoke(prompt_messages)

    action_summary = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "send_team_message":
                send_team_message.invoke(tool_call["args"])
                action_summary.append(f"Messaged {tool_call['args'].get('recipient')}")
    else:
        action_summary.append("No messages sent.")

    print(f"[Node] Messaging summary: {action_summary}")

    return {
        "reminder_count": current_count + 1,
        "messages": [SystemMessage(content=f"Messages executed at {current_time}: {action_summary}")]
    }


def escalate_to_human(state: AgentState):
    """Node: Escalates to the manager when attendees remain unresponsive past the reminder threshold."""
    print("\n[Node] Executing 'escalate_to_human'...")

    missing = state.get("missing_attendees", [])

    subject = "הסלמה: איסוף מדיה לאירוע"
    message = f"חברי הצוות הבאים לא העלו קבצים למרות מספר תזכורות: {missing}. הופסקו התזכורות האוטומטיות עבורם, נדרשת התערבותך."

    notify_manager.invoke({"subject": subject, "message": message})

    return {
        "collection_phase_status": "escalated",
        "messages": [SystemMessage(content=f"Escalation triggered for: {missing}")]
    }


# ==========================================
# Routers (Conditional Edges)
# ==========================================

def route_from_start(state: AgentState) -> str:
    """Router 1: Determines entry node based on folder approval state."""
    if state.get("folder_approval_status") == "approved":
        return "gather_updates"
    return "find_space_to_save"


def route_after_path_suggestion(state: AgentState) -> str:
    """Router 2: Evaluates whether manager requested path revisions."""
    if state.get("user_feedback"):
        return "find_space_to_save"
    return "create_drive_space"


def route_after_drive_creation(state: AgentState) -> str:
    """Router 3: Verifies successful Drive folder creation before sending reminders."""
    if state.get("collection_phase_status") == "error":
        return END
    return "send_reminders"


def route_after_reply(state: AgentState) -> str:
    """Router 4: Evaluates completion status, wakeup triggers, and reminder thresholds."""
    # Terminate workflow if collection completed
    if state.get("collection_phase_status") == "finished" or len(state.get("missing_attendees", [])) == 0:
        return END

    # Message-only wakeups return to sleep without dispatching reminders
    if state.get("wakeup_reason") == "message":
        print("[Router] Woke up for message only. Going back to sleep without reminding.")
        return END

    # Timer wakeup: evaluate whether to escalate or dispatch reminder round
    if state.get("reminder_count", 0) >= 3:
        return "escalate_to_human"

    return "send_reminders"


# ==========================================
# Graph Compilation
# ==========================================

# Register nodes
workflow.add_node("find_space_to_save", find_space_to_save)
workflow.add_node("create_drive_space", create_drive_space)
workflow.add_node("gather_updates", gather_updates)
workflow.add_node("evaluate_and_filter", evaluate_and_filter)
workflow.add_node("reply_to_messages", reply_to_messages)
workflow.add_node("send_reminders", send_reminders)
workflow.add_node("escalate_to_human", escalate_to_human)

# Connect graph edges and conditional routing
workflow.add_conditional_edges(START, route_from_start)
workflow.add_conditional_edges("find_space_to_save", route_after_path_suggestion)

workflow.add_conditional_edges(
    "create_drive_space",
    route_after_drive_creation,
    {"send_reminders": "send_reminders", END: END}
)

workflow.add_edge("gather_updates", "evaluate_and_filter")
workflow.add_edge("evaluate_and_filter", "reply_to_messages")

# Evaluate routing decisions post message reply handling
workflow.add_conditional_edges("reply_to_messages", route_after_reply)

# Terminal edges
workflow.add_edge("send_reminders", END)
workflow.add_edge("escalate_to_human", END)

# Compile graph with state checkpointing and interrupt configuration
memory = MemorySaver()

app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["create_drive_space"]
)