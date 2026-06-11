from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """LangGraph state for the MACE agentic counselor."""

    messages: Annotated[List[BaseMessage], add_messages]
    conversation_id: str
    intent: str
    route: str
    plan: List[str]
    plan_step: int
    user_profile: Dict[str, Any]
    booking_state: Dict[str, Any]
    sources: List[Dict[str, Any]]
    agent_metadata: Dict[str, Any]
    final_response: str
    rag_used: bool
