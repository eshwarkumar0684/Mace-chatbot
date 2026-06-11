"""Intent classification for routing chat queries."""

import re
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from backend.agent.prompts import INTENT_PROMPT
from backend.utils import logger

INTENT_LABELS = ("course_inquiry", "book_demo", "lead_capture", "general_chat")

ENROLLMENT_PHRASES = (
    "i want to join",
    "want to join",
    "enroll me",
    "register me",
    "sign me up",
    "i am interested in this course",
    "i'm interested in this course",
    "im interested in this course",
    "contact me",
    "want to enroll",
    "would like to enroll",
    "like to enroll",
    "please enroll",
    "take admission",
)

DEMO_PHRASES = (
    "book a demo",
    "book demo",
    "schedule a demo",
    "schedule demo",
    "demo booking",
    "free demo",
    "book a free demo",
    "demo session",
    "arrange a demo",
)

INFO_PHRASES = (
    "what course",
    "which course",
    "courses do",
    "courses does",
    "tell me about",
    "course fee",
    "course fees",
    "what is the fee",
    "what are the fees",
    "what is the duration",
    "course duration",
    "how long",
    "syllabus",
    "placement",
    "what does mace",
    "what is ai",
    "what are",
    "what is",
    "who is",
    "how much",
    "fee structure",
    "program details",
    "academy provide",
    "offer",
    "generative ai",
)

PURE_GREETINGS = {
    "hi",
    "hello",
    "hey",
    "hola",
    "good morning",
    "good afternoon",
    "good evening",
    "howdy",
    "hi there",
    "hello there",
    "hey there",
    "greetings",
}


def is_pure_greeting(question: str) -> bool:
    normalized = re.sub(r"\s+", " ", question.lower().strip().rstrip("!.?"))
    if normalized in PURE_GREETINGS:
        return True
    if len(normalized.split()) <= 5 and normalized.startswith(("hi ", "hello ", "hey ")):
        return not any(phrase in normalized for phrase in INFO_PHRASES + DEMO_PHRASES + ENROLLMENT_PHRASES)
    return False


def _keyword_intent(question: str) -> Optional[str]:
    q = question.lower().strip()

    if any(phrase in q for phrase in ENROLLMENT_PHRASES):
        return "lead_capture"

    if any(phrase in q for phrase in DEMO_PHRASES):
        return "book_demo"

    if is_pure_greeting(question):
        return "general_chat"

    if any(phrase in q for phrase in INFO_PHRASES):
        return "course_inquiry"

    if q.endswith("?"):
        return "course_inquiry"

    return None


def _llm_intent(question: str, llm: ChatGroq) -> str:
    prompt = INTENT_PROMPT.format(question=question)
    raw = llm.invoke([HumanMessage(content=prompt)]).content.strip().lower()
    for label in INTENT_LABELS:
        if label in raw:
            return label
    return "course_inquiry"


def classify_intent(question: str, llm: Optional[ChatGroq] = None) -> str:
    """Classify user message into a routing intent (keyword rules first, then LLM)."""
    keyword_intent = _keyword_intent(question)
    if keyword_intent:
        logger.info("Intent detected (keyword): %s for query=%r", keyword_intent, question[:120])
        return keyword_intent

    if not llm:
        intent = "book_demo" if any(p in question.lower() for p in DEMO_PHRASES) else "course_inquiry"
        logger.info("Intent detected (fallback): %s for query=%r", intent, question[:120])
        return intent

    intent = _llm_intent(question, llm)
    logger.info("Intent detected (llm): %s for query=%r", intent, question[:120])
    return intent


def route_for_intent(intent: str) -> str:
    """Map intent to graph route name."""
    if intent == "course_inquiry":
        return "rag_retrieval"
    if intent == "general_chat":
        return "greeting_response"
    if intent == "book_demo":
        return "demo_workflow"
    if intent == "lead_capture":
        return "lead_workflow"
    return "rag_retrieval"
