import json
from typing import Any, Dict, List, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from backend.agent.intent import classify_intent, route_for_intent
from backend.agent.memory import get_memory, save_memory_snapshot
from backend.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    DEFAULT_INTENT_RULES,
    GREETING_RESPONSE,
    INTENT_RULES,
    PLANNING_PROMPT,
)
from backend.prompts import NO_KB_RESPONSE
from backend.agent.state import AgentState
from backend.agent.tools.crm_tool import create_crm_tool
from backend.agent.tools.demo_tool import create_demo_tools
from backend.config import settings
from backend.rag_pipeline import get_rag_pipeline
from backend.utils import logger

_checkpointer = MemorySaver()


def _get_llm() -> ChatGroq | None:
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


def _parse_plan(raw: str, intent: str) -> List[str]:
    raw = raw.strip()
    try:
        start = raw.index("[")
        end = raw.rindex("]") + 1
        plan = json.loads(raw[start:end])
        if isinstance(plan, list):
            return [str(s) for s in plan[:5]]
    except (ValueError, json.JSONDecodeError):
        pass

    if intent == "book_demo":
        return [
            "Collect name, email, phone, course interest",
            "Check available demo dates",
            "Book selected slot",
            "Confirm booking",
        ]
    if intent == "lead_capture":
        return [
            "Confirm enrollment interest",
            "Collect name, email, phone, course interest",
            "Save lead to CRM",
        ]
    return ["Search knowledge base", "Answer using retrieved documents only"]


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


def _messages_to_history(messages: List) -> List[Dict[str, str]]:
    history = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage) and msg.content:
            history.append({"role": "assistant", "content": msg.content})
    return history


def _extract_final_response(state: AgentState) -> str:
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and msg.content and not getattr(msg, "tool_calls", None):
            return msg.content
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return "I'm here to help with MACE AI Academy courses and demo bookings."


def load_memory_node(state: AgentState) -> Dict[str, Any]:
    mem = get_memory(state["conversation_id"])
    return {
        "user_profile": mem["user_profile"],
        "booking_state": mem["booking_state"],
    }


def understand_intent_node(state: AgentState) -> Dict[str, Any]:
    question = _last_user_text(state)
    llm = _get_llm()
    intent = classify_intent(question, llm)
    route = route_for_intent(intent)
    logger.info(
        "Routing: conversation=%s query=%r intent=%s route=%s",
        state["conversation_id"],
        question[:120],
        intent,
        route,
    )
    return {"intent": intent, "route": route}


def plan_tasks_node(state: AgentState) -> Dict[str, Any]:
    llm = _get_llm()
    question = _last_user_text(state)
    intent = state.get("intent", "course_inquiry")
    memory_ctx = _format_memory_context(state.get("user_profile", {}), state.get("booking_state", {}))
    history = _history_text(state)

    if not llm:
        plan = _parse_plan("", intent)
        return {"plan": plan, "plan_step": 0}

    prompt = PLANNING_PROMPT.format(
        intent=intent,
        question=question,
        memory_context=memory_ctx,
        history=history,
    )
    raw = llm.invoke([HumanMessage(content=prompt)]).content
    plan = _parse_plan(raw, intent)
    logger.info("Agent plan (%s) for %s: %s", intent, state["conversation_id"], plan)
    return {"plan": plan, "plan_step": 0}


def rag_retrieval_node(state: AgentState) -> Dict[str, Any]:
    question = _last_user_text(state)
    history = _messages_to_history(state["messages"][:-1])
    pipeline = get_rag_pipeline()
    k = settings.RAG_TOP_K

    results = pipeline.retrieve_context(question, k=k)
    sources = pipeline.format_sources(results)
    scores = [src["score"] for src in sources]

    logger.info(
        "RAG route: conversation=%s intent=%s query=%r retrieved=%d scores=%s",
        state["conversation_id"],
        state.get("intent"),
        question[:120],
        len(sources),
        scores,
    )

    if not sources:
        return {
            "messages": [AIMessage(content=NO_KB_RESPONSE)],
            "final_response": NO_KB_RESPONSE,
            "sources": [],
            "rag_used": True,
        }

    result = pipeline.generate_response(question, history, k=k, pre_results=results)
    return {
        "messages": [AIMessage(content=result["response"])],
        "final_response": result["response"],
        "sources": result.get("sources", sources),
        "rag_used": True,
    }


def greeting_response_node(state: AgentState) -> Dict[str, Any]:
    return {
        "messages": [AIMessage(content=GREETING_RESPONSE)],
        "final_response": GREETING_RESPONSE,
        "sources": [],
        "rag_used": False,
    }


def _workflow_agent_node(state: AgentState, tools: list, intent: str) -> Dict[str, Any]:
    llm = _get_llm()
    question = _last_user_text(state)
    memory_ctx = _format_memory_context(state.get("user_profile", {}), state.get("booking_state", {}))
    plan_ctx = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(state.get("plan", [])))

    if not llm:
        return _fallback_agent_response(state, question)

    intent_rules = INTENT_RULES.get(intent, DEFAULT_INTENT_RULES)
    system = AGENT_SYSTEM_PROMPT.format(
        intent=intent,
        intent_rules=intent_rules,
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
    final = state.get("final_response") or _extract_final_response(state)
    sources = state.get("sources") or []

    logger.info(
        "Chat complete: conversation=%s intent=%s route=%s retrieved=%d response_chars=%d",
        state["conversation_id"],
        state.get("intent"),
        state.get("route"),
        len(sources),
        len(final),
    )

    return {
        "final_response": final,
        "sources": sources,
        "agent_metadata": {
            "intent": state.get("intent"),
            "route": state.get("route"),
            "plan": state.get("plan"),
            "retrieved_document_count": len(sources),
            "similarity_scores": [src.get("score") for src in sources],
            "rag_used": state.get("rag_used", False),
        },
    }


def _fallback_agent_response(state: AgentState, question: str) -> Dict[str, Any]:
    history = _messages_to_history(state["messages"])
    result = get_rag_pipeline().generate_response(question, history)
    return {
        "messages": [AIMessage(content=result["response"])],
        "sources": result.get("sources", []),
        "final_response": result["response"],
        "rag_used": True,
    }


def _route_after_intent(state: AgentState) -> Literal["rag_retrieval", "greeting_response", "plan_tasks"]:
    route = state.get("route") or route_for_intent(state.get("intent", "course_inquiry"))
    if route == "rag_retrieval":
        return "rag_retrieval"
    if route == "greeting_response":
        return "greeting_response"
    return "plan_tasks"


def _route_after_plan(state: AgentState) -> Literal["demo_agent", "lead_agent"]:
    if state.get("intent") == "book_demo":
        return "demo_agent"
    return "lead_agent"


def build_agent_graph(history: List[Dict[str, str]], conversation_id: str):
    demo_tools = create_demo_tools(conversation_id)
    crm_tool = create_crm_tool(conversation_id)

    def demo_agent(state: AgentState):
        return _workflow_agent_node(state, demo_tools, "book_demo")

    def lead_agent(state: AgentState):
        return _workflow_agent_node(state, [crm_tool], "lead_capture")

    demo_tool_node = ToolNode(demo_tools)
    lead_tool_node = ToolNode([crm_tool])

    graph = StateGraph(AgentState)
    graph.add_node("load_memory", load_memory_node)
    graph.add_node("understand_intent", understand_intent_node)
    graph.add_node("rag_retrieval", rag_retrieval_node)
    graph.add_node("greeting_response", greeting_response_node)
    graph.add_node("plan_tasks", plan_tasks_node)
    graph.add_node("demo_agent", demo_agent)
    graph.add_node("lead_agent", lead_agent)
    graph.add_node("demo_tools", demo_tool_node)
    graph.add_node("lead_tools", lead_tool_node)
    graph.add_node("save_memory", save_memory_node)

    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "understand_intent")
    graph.add_conditional_edges(
        "understand_intent",
        _route_after_intent,
        {
            "rag_retrieval": "rag_retrieval",
            "greeting_response": "greeting_response",
            "plan_tasks": "plan_tasks",
        },
    )
    graph.add_edge("rag_retrieval", "save_memory")
    graph.add_edge("greeting_response", "save_memory")

    graph.add_conditional_edges(
        "plan_tasks",
        _route_after_plan,
        {"demo_agent": "demo_agent", "lead_agent": "lead_agent"},
    )
    graph.add_conditional_edges(
        "demo_agent",
        tools_condition,
        {"tools": "demo_tools", "__end__": "save_memory"},
    )
    graph.add_conditional_edges(
        "lead_agent",
        tools_condition,
        {"tools": "lead_tools", "__end__": "save_memory"},
    )
    graph.add_edge("demo_tools", "demo_agent")
    graph.add_edge("lead_tools", "lead_agent")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=_checkpointer)


def get_agent_graph(history: List[Dict[str, str]], conversation_id: str):
    return build_agent_graph(history, conversation_id)
