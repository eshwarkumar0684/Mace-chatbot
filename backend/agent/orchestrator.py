from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.graph import get_agent_graph
from backend.agent.memory import init_agent_tables
from backend.utils import logger

_agent_initialized = False


def ensure_agent_ready() -> None:
    global _agent_initialized
    if not _agent_initialized:
        init_agent_tables()
        _agent_initialized = True


def run_agent(
    conversation_id: str,
    question: str,
    history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Run the LangGraph agent and return response + sources + metadata."""
    ensure_agent_ready()

    messages = []
    for turn in history[-12:]:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        if turn.get("role") == "user":
            messages.append(HumanMessage(content=content))
        elif turn.get("role") == "assistant":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=question))

    initial_state = {
        "messages": messages,
        "conversation_id": conversation_id,
        "intent": "",
        "plan": [],
        "plan_step": 0,
        "user_profile": {},
        "booking_state": {"status": "idle", "date": None, "booking_id": None},
        "sources": [],
        "agent_metadata": {},
        "final_response": "",
    }

    graph = get_agent_graph(history, conversation_id)
    config = {"configurable": {"thread_id": conversation_id}}

    try:
        result = graph.invoke(initial_state, config=config)
    except Exception as exc:
        logger.error("Agent graph failed: %s", exc, exc_info=True)
        from backend.rag_pipeline import get_rag_pipeline

        fallback = get_rag_pipeline().generate_response(question, history)
        return {
            "response": fallback["response"],
            "sources": fallback.get("sources", []),
            "agent_metadata": {"fallback": True, "error": str(exc)},
        }

    response = result.get("final_response") or _extract_response(result)
    sources = result.get("sources") or []

    return {
        "response": response,
        "sources": sources,
        "agent_metadata": result.get("agent_metadata", {}),
    }


def _extract_response(result: Dict[str, Any]) -> str:
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "How can I help you with MACE AI Academy today?"
