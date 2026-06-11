from typing import Any, Dict, List

from langchain_core.tools import tool

from backend.config import settings
from backend.prompts import NO_KB_RESPONSE
from backend.rag_pipeline import get_rag_pipeline
from backend.utils import logger


def create_rag_tool(history: List[Dict[str, str]]):
    @tool
    def rag_retriever(question: str) -> str:
        """Search MACE AI Academy knowledge base and answer course FAQs (fees, duration, syllabus, placements)."""
        pipeline = get_rag_pipeline()
        k = settings.RAG_TOP_K
        results = pipeline.retrieve_context(question, k=k)
        sources = pipeline.format_sources(results)

        if not sources:
            return NO_KB_RESPONSE

        lines = []
        for src in sources[:k]:
            lines.append(f"[{src['source']}] {src['content'][:400]}")

        context = "\n\n".join(lines)
        if pipeline.llm:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
            from backend.prompts import RAG_CONTEXT_BLOCK, SYSTEM_PROMPT

            system = SYSTEM_PROMPT + RAG_CONTEXT_BLOCK.format(context=context)
            history_messages = []
            for m in history[-6:]:
                if m["role"] == "user":
                    history_messages.append(HumanMessage(content=m["content"]))
                else:
                    history_messages.append(AIMessage(content=m["content"]))
            messages = [
                SystemMessage(content=system),
                *history_messages,
                HumanMessage(content=f"Answer concisely in bullets: {question}"),
            ]
            response = pipeline.llm.invoke(messages)
            answer = response.content
        else:
            answer = context[:800]

        logger.info(
            "RAG tool answer: query=%r chunks=%d scores=%s",
            question[:120],
            len(sources),
            [src["score"] for src in sources],
        )
        return answer

    return rag_retriever


def extract_sources_from_rag(question: str) -> List[Dict[str, Any]]:
    pipeline = get_rag_pipeline()
    results = pipeline.retrieve_context(question, k=settings.RAG_TOP_K)
    return pipeline.format_sources(results)
