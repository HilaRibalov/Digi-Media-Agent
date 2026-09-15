import operator
from typing import TypedDict, List, Optional, Annotated, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # event ditales
    event_id: Optional[str]
    event_name: Optional[str]
    event_date: Optional[str]
    attendees: Optional[List[str]]
    wakeup_reason: Optional[str]
    manager_raw_prompt: Optional[str]

    # location ditales and location approving ditales
    suggested_folder_path: Optional[str]
    approved_folder_path: Optional[str]
    folder_url: Optional[str]
    folder_approval_status: Optional[str]  
    user_feedback: Optional[str]

    #photo uploading ditales
    # [{"filename": "image.jpg", "uploader": "dan@team.com"}]
    uploaded_files: Annotated[List[Dict[str, str]], operator.add]
    missing_attendees: Optional[List[str]]
    reminder_count: Optional[int]
    max_reminders: Optional[int]

    # praperation for post uplader agent
    collection_phase_status: Optional[str]  # "running", "escalated", "finished"
    trigger_post_creation: Optional[bool]

    # The full conversation history maneged by LangGraph
    messages: Annotated[list[BaseMessage], add_messages]