import os
import json
import datetime
from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from dotenv import load_dotenv

# Import the State and tools from the files we created
from state import AgentState
from tools import (
    create_drive_folder,
    check_drive_uploads,
    read_team_messages,
    send_team_message,
    notify_manager
)

# טעינת המשתנים מקובץ ה-.env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file!")

# LLM definition
llm = ChatGoogleGenerativeAI(
    model="gemini-flash-latest",
    #temperature=0,
    google_api_key=api_key
)
# Grouping the tools that the model is allowed to use
tools_list = [
    create_drive_folder,
    check_drive_uploads,
    read_team_messages,
    send_team_message,
    notify_manager
]

# Bind the tools to the LLM
llm_with_tools = llm.bind_tools(tools_list)

# Initialize the graph with our State
workflow = StateGraph(AgentState)


# ==========================================
# Nodes
# ==========================================

# 1
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

    # Safe extraction of the text, whether it arrives as a string or a list of blocks
    content = response.content
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict):
            suggested_path = content[0].get("text", "").strip()
        else:
            suggested_path = str(content[0]).strip()
    else:
        suggested_path = str(content).strip()

    print(f"[Node] The LLM suggested the path: {suggested_path}")

    return {
        "suggested_folder_path": suggested_path,
        "folder_approval_status": "pending",
        "user_feedback": "",  # <--- השורה הקריטית שנוספה: מנקה את הפידבק אחרי השימוש כדי למנוע לולאה אינסופית
        "messages": [SystemMessage(content=f"Suggested folder path: {suggested_path}")]
    }


# 2
def create_drive_space(state: AgentState):
    """Node: Creates the actual folder in Google Drive with error handling."""
    print("\n[Node] Executing 'create_drive_space'...")

    final_path = state.get("approved_folder_path") or state.get("suggested_folder_path")

    try:
        # Call the drive creation tool
        folder_url = create_drive_folder.invoke(final_path)
        print(f"[Node] Folder created successfully! URL: {folder_url}")

        return {
            "folder_url": folder_url,
            "folder_approval_status": "approved",
            "messages": [SystemMessage(content=f"Folder created at URL: {folder_url}")]
        }

    except Exception as e:
        # Graceful failure handling
        error_msg = f"Failed to create Google Drive folder at path '{final_path}': {str(e)}"
        print(f"[Node Error] {error_msg}")

        # Alert the manager immediately so they can fix permissions/quota
        notify_manager.invoke({
            "subject": "שגיאת מערכת: כשל ביצירת תיקיית Drive",
            "message": f"הסוכן נתקל בשגיאה ביצירת התיקייה בנתיב: {final_path}.\nפירוט השגיאה: {str(e)}\nהתהליך הופסק זמנית."
        })

        return {
            "collection_phase_status": "error",
            "messages": [SystemMessage(content=error_msg)]
        }


# 3
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


# 4
def evaluate_and_filter(state: AgentState):
    """Node: The Brain. Evaluates who is still missing based on files and messages."""
    print("\n[Node] Executing 'evaluate_and_filter'...")

    missing = state.get("missing_attendees", [])

    if not missing:
        print("[Node] No missing attendees left!")
        return {"collection_phase_status": "finished", "trigger_post_creation": True}

    last_system_msg = state["messages"][-1].content

    # UPDATED PROMPT: Strictly define when to remove someone from the list
    system_instruction = (
        "You are managing a missing attendees list for a media collection event. "
        f"Current missing attendees: {missing}\n\n"
        "Read the system update. Team messages will be in Hebrew. Remove an attendee from the missing list IF AND ONLY IF:\n"
        "1. The System Update explicitly shows a file was uploaded by them.\n"
        "2. They sent a message indicating they are EXEMPT (e.g., 'הייתי חולה', 'לא הייתי באירוע').\n"
        "CRITICAL: Do NOT remove them if they merely claim to have uploaded, but their name is NOT in the new files list.\n"
        "Return ONLY a valid JSON array of strings containing the updated missing attendees."
    )

    prompt_messages = [
        SystemMessage(content=system_instruction),
        HumanMessage(content=last_system_msg)
    ]

    response = llm.invoke(prompt_messages)

    # Safe extraction mechanism
    content = response.content
    if isinstance(content, list):
        if len(content) > 0 and isinstance(content[0], dict):
            raw_text = content[0].get("text", "")
        else:
            raw_text = str(content[0])
    else:
        raw_text = str(content)

    try:
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        updated_missing = json.loads(clean_text)

        if isinstance(updated_missing, dict):
            lists = [v for v in updated_missing.values() if isinstance(v, list)]
            updated_missing = lists[0] if lists else missing
        elif not isinstance(updated_missing, list):
            updated_missing = missing

    except Exception as e:
        print(f"[Error parsing JSON, keeping original list] {e}")
        updated_missing = missing

    print(f"[Node] Updated missing attendees list: {updated_missing}")

    status = "running"
    ready_for_post = False
    if len(updated_missing) == 0:
        status = "finished"
        ready_for_post = True
        ###############################################
        # Notify the manager immediately that media collection is 100% complete
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


# 5a
def reply_to_messages(state: AgentState):
    """Node: Handles ONLY replying to incoming messages without reminding."""
    print("\n[Node] Executing 'reply_to_messages'...")

    # UPDATED PROMPT: Cross-reference user claims with actual system files
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

    action_summary = []
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tool_call in response.tool_calls:
            if tool_call["name"] == "send_team_message":
                send_team_message.invoke(tool_call["args"])
                action_summary.append(f"Replied to {tool_call['args'].get('recipient')}")
    else:
        action_summary.append("No replies needed.")

    print(f"[Node] Reply summary: {action_summary}")

    return {"messages": [SystemMessage(content=f"Replies executed: {action_summary}")]}


# 5b
def send_reminders(state: AgentState):
    """Node: Handles initial requests and sending progressive reminders to missing attendees."""
    print("\n[Node] Executing 'send_reminders'...")

    missing = state.get("missing_attendees", [])
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    current_count = state.get("reminder_count", 0)
    folder_url = state.get("folder_url", "URL_NOT_FOUND")

    # Define tone and instructions dynamically based on reminder iteration
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

# 6
def escalate_to_human(state: AgentState):
    """Node: Escalates to the manager when a team member ignores max reminders."""
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
    """Router 1: Decides where the agent should start when it wakes up."""
    if state.get("folder_approval_status") == "approved":
        return "gather_updates"
    return "find_space_to_save"


def route_after_path_suggestion(state: AgentState) -> str:
    """Router 2: Handle human-in-the-loop feedback for folder path."""
    if state.get("user_feedback"):
        return "find_space_to_save"
    return "create_drive_space"


def route_after_drive_creation(state: AgentState) -> str:
    """Route to reminders if folder exists, or terminate if creation failed."""
    if state.get("collection_phase_status") == "error":
        return END
    return "send_reminders"


def route_after_reply(state: AgentState) -> str:
    """Router 3: The Main Decision Engine. Happens AFTER replying to messages."""

    # 1. אם הרשימה התרוקנה - סיימנו בהצלחה!
    if state.get("collection_phase_status") == "finished" or len(state.get("missing_attendees", [])) == 0:
        return END

    # 2. אם הבוט התעורר *רק* בגלל שמישהו שלח הודעה - הוא עונה וחוזר לישון (ללא תזכורות)
    if state.get("wakeup_reason") == "message":
        print("[Router] Woke up for message only. Going back to sleep without reminding.")
        return END

    # 3. מפה והלאה - הבוט התעורר מטיימר. נבדוק אם להסלים או לתזכר:
    if state.get("reminder_count", 0) >= 3:
        return "escalate_to_human"

    return "send_reminders"


# ==========================================
# Graph Compilation (The Blueprint)
# ==========================================

# 1. Add all nodes
workflow.add_node("find_space_to_save", find_space_to_save)
workflow.add_node("create_drive_space", create_drive_space)
workflow.add_node("gather_updates", gather_updates)
workflow.add_node("evaluate_and_filter", evaluate_and_filter)
workflow.add_node("reply_to_messages", reply_to_messages)
workflow.add_node("send_reminders", send_reminders)
workflow.add_node("escalate_to_human", escalate_to_human)

# 2. Define the flow (Edges)
workflow.add_conditional_edges(START, route_from_start)
workflow.add_conditional_edges("find_space_to_save", route_after_path_suggestion)

#workflow.add_edge("create_drive_space", "send_reminders")
workflow.add_conditional_edges("create_drive_space", route_after_drive_creation,
                               {"send_reminders": "send_reminders",END: END})
workflow.add_edge("gather_updates", "evaluate_and_filter")

# THE CRITICAL FIX: From the "Brain" node, ALWAYS proceed to reply to messages!
workflow.add_edge("evaluate_and_filter", "reply_to_messages")

# Only AFTER replying to messages, the main router decides what to do next (END / escalate / remind)
workflow.add_conditional_edges("reply_to_messages", route_after_reply)

# Terminal nodes always go to END
workflow.add_edge("send_reminders", END)
workflow.add_edge("escalate_to_human", END)

# 3. Compile
memory = MemorySaver()

app = workflow.compile(
    checkpointer=memory,
    interrupt_before=["create_drive_space"]
)

# Generate and print the Mermaid diagram syntax for the graph
#print("\n--- Mermaid Graph Visualization ---")
#print(app.get_graph().draw_mermaid())