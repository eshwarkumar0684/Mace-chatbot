import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from backend.agent.memory import get_memory, save_memory_snapshot
from backend.agent.prompts import AGENT_SYSTEM_PROMPT, INTENT_PROMPT, PLANNING_PROMPT
from backend.agent.state import AgentState
from backend.agent.tools.crm_tool import create_crm_tool
from backend.agent.tools.demo_tool import create_demo_tools
from backend.agent.tools.rag_tool import create_rag_tool, extract_sources_from_rag
from backend.config import settings
from backend.utils import logger

_graph = None
_checkpointer = MemorySaver()


def _get_llm() -> Optional[ChatGroq]:
    if not settings.GROQ_API_KEY:
        return None
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model=settings.MODEL_NAME,
        temperature=0.4,
    )


def _format_memory_context(user_profile: Dict[str, Any], booking_state: Dict[str, Any]) -> str:
    lines = []
    for key, val in user_profile.items():
        if val:
            lines.append(f"- {key}: {val}")
    if booking_state.get("status") != "idle":
        lines.append(f"- booking: {json.dumps(booking_state)}")
    return "\n".join(lines) if lines else "- No stored details yet."


def _parse_plan(raw: str) -> List[str]:
    raw = raw.strip()
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        plan = json.loads(raw[start:end])
        if isinstance(plan, list):
            return [str(s) for s in plan[:5]]
    except (ValueError, json.JSONDecodeError):
        pass
    return ["Understand request", "Use appropriate tools", "Respond to student"]


def load_memory_node(state: AgentState) -> Dict[str, Any]:
    mem = get_memory(state["conversation_id"])
    return {
        "user_profile": mem["user_profile"],
        "booking_state": mem["booking_state"],
    }


def understand_intent_node(state: AgentState) -> Dict[str, Any]:
    llm = _get_llm()
    question = _last_user_text(state)
    if not llm:
        intent = "book_demo" if "demo" in question.lower() or "book" in question.lower() else "course_inquiry"
        return {"intent": intent}

    prompt = INTENT_PROMPT.format(question=question)
    intent = llm.invoke([HumanMessage(content=prompt)]).content.strip().lower()
    for label in ("book_demo", "lead_capture", "course_inquiry", "general_chat"):
        if label in intent:
            return {"intent": label}
    return {"intent": "general_chat"}


def plan_tasks_node(state: AgentState) -> Dict[str, Any]:
    llm = _get_llm()
    question = _last_user_text(state)
    memory_ctx = _format_memory_context(state.get("user_profile", {}), state.get("booking_state", {}))
    history = _history_text(state)

    if not llm:
        if state.get("intent") == "book_demo":
            plan = [
                "Collect name, email, phone, course interest",
                "Check available demo slots",
                "Book selected slot",
                "Send confirmation",
            ]
        else:
            plan = ["Search knowledge base", "Answer with bullet points"]
        return {"plan": plan, "plan_step": 0}

    prompt = PLANNING_PROMPT.format(
        question=question,
        memory_context=memory_ctx,
        history=history,
    )
    raw = llm.invoke([HumanMessage(content=prompt)]).content
    plan = _parse_plan(raw)
    logger.info("Agent plan for %s: %s", state["conversation_id"], plan)
    return {"plan": plan, "plan_step": 0}


def agent_node(state: AgentState, tools: list) -> Dict[str, Any]:
    llm = _get_llm()
    question = _last_user_text(state)
    memory_ctx = _format_memory_context(state.get("user_profile", {}), state.get("booking_state", {}))
    plan_ctx = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(state.get("plan", [])))

    if not llm:
        return _fallback_agent_response(state, question)

    system = AGENT_SYSTEM_PROMPT.format(
        memory_context=memory_ctx,
        plan_context=plan_ctx or "1. Help the student",
    )
    llm_with_tools = llm.bind_tools(tools)
    messages = [SystemMessage(content=system), *state["messages"]]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


def save_memory_node(state: AgentState) -> Dict[str, Any]:
    save_memory_snapshot(
        state["conversation_id"],
        state.get("user_profile", {}),
        state.get("booking_state", {}),
    )
    final = _extract_final_response(state)
    sources = extract_sources_from_rag(_last_user_text(state))
    return {
        "final_response": final,
        "sources": sources,
        "agent_metadata": {
            "intent": state.get("intent"),
            "plan": state.get("plan"),
            "steps_executed": len(state.get("plan", [])),
        },
    }


def _last_user_text(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def _history_text(state: AgentState, limit: int = 4) -> str:
    lines = []
    for msg in state["messages"][-limit:]:
        role = "Student" if isinstance(msg, HumanMessage) else "Assistant"
        lines.append(f"{role}: {msg.content[:200]}")
    return "\n".join(lines) or "No prior messages."


def _extract_final_response(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            return msg.content
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "I'm here to help with MACE AI Academy courses and demo bookings."


def _fallback_agent_response(state: AgentState, question: str) -> Dict[str, Any]:
    from backend.rag_pipeline import get_rag_pipeline

    history = [
        {"role": "user" if isinstance(m, HumanMessage) else "assistant", "content": m.content}
        for m in state["messages"]
        if isinstance(m, (HumanMessage, AIMessage))
    ]
    result = get_rag_pipeline().generate_response(question, history)
    return {
        "messages": [AIMessage(content=result["response"])],
        "sources": result.get("sources", []),
        "final_response": result["response"],
    }


def build_agent_graph(history: List[Dict[str, str]], conversation_id: str):
    rag_tool = create_rag_tool(history)
    demo_tools = create_demo_tools(conversation_id)
    crm_tool = create_crm_tool(conversation_id)
    tools = [rag_tool, *demo_tools, crm_tool]

    def run_agent(state: AgentState):
        return agent_node(state, tools)

    graph = StateGraph(AgentState)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("understand_intent", understand_intent_node)
    graph.add_node("plan_tasks", plan_tasks_node)
    graph.add_node("agent", run_agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("save_memory", save_memory_node)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "understand_intent")
    graph.add_edge("understand_intent", "plan_tasks")
    graph.add_edge("plan_tasks", "agent")
    graph.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", "__end__": "save_memory"},
    )
    graph.add_edge("tools", "agent")

    return graph.compile(checkpointer=_checkpointer)


def get_agent_graph(history: List[Dict[str, str]], conversation_id: str):
    return build_agent_graph(history, conversation_id)
