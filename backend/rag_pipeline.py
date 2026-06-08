import os
from typing import Any, Dict, List, Tuple

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from backend.config import settings
from backend.ingest import get_embeddings
from backend.prompts import CONVERSATIONAL_INSTRUCTIONS, RAG_CONTEXT_BLOCK, SYSTEM_PROMPT
from backend.utils import logger

MAX_HISTORY_TURNS = 12


class RAGPipeline:
    def __init__(self):
        self.embeddings = None
        self.vector_store = None
        self.llm = None
        self.initialized = False
        self._initialize_pipeline()

    def reload(self):
        self.initialized = False
        self.vector_store = None
        self._initialize_pipeline()

    def _initialize_pipeline(self):
        try:
            chroma_dir = os.path.abspath(settings.CHROMA_DB_DIR)

            if not os.path.exists(chroma_dir) or not os.listdir(chroma_dir):
                logger.warning(
                    "Vector DB folder %s is empty. Run: python -m backend.ingest",
                    chroma_dir,
                )

            self.embeddings = get_embeddings()

            self.vector_store = Chroma(
                persist_directory=chroma_dir,
                embedding_function=self.embeddings,
                collection_name="mace_academy",
            )

            if settings.GROQ_API_KEY:
                logger.info("Initializing Groq LLM with model: %s", settings.MODEL_NAME)
                self.llm = ChatGroq(
                    api_key=settings.GROQ_API_KEY,
                    model=settings.MODEL_NAME,
                    temperature=0.55,
                )
            else:
                logger.warning("GROQ_API_KEY not found. Running in simulation mode.")
                self.llm = None

            self.initialized = True
            logger.info("RAG Pipeline successfully initialized.")
        except Exception as e:
            logger.error("Error initializing RAG Pipeline: %s", e, exc_info=True)
            self.initialized = False

    def retrieve_context(self, query: str, k: int = 4) -> List[Tuple[Document, float]]:
        if not self.initialized or self.vector_store is None:
            self._initialize_pipeline()

        if self.vector_store is None:
            logger.error("ChromaDB vector store is not available.")
            return []

        try:
            results = self.vector_store.similarity_search_with_score(query, k=k)
            logger.info("Retrieved %d chunks for: %s", len(results), query[:80])
            return results
        except Exception as e:
            logger.error("Error searching ChromaDB: %s", e)
            return []

    def format_sources(self, results: List[Tuple[Document, float]]) -> List[Dict[str, Any]]:
        sources = []
        seen_contents = set()

        for doc, score in results:
            content = doc.page_content.strip()
            if content in seen_contents:
                continue
            seen_contents.add(content)

            source_file = doc.metadata.get("source", "Unknown Source")
            sources.append({
                "source": os.path.basename(source_file),
                "content": content,
                "score": float(score),
            })
        return sources

    def _build_messages(
        self,
        query: str,
        context_text: str,
        history: List[Dict[str, str]],
    ) -> List:
        system_content = SYSTEM_PROMPT + RAG_CONTEXT_BLOCK.format(context=context_text)
        messages: List = [SystemMessage(content=system_content)]

        for turn in history[-MAX_HISTORY_TURNS:]:
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            if turn.get("role") == "user":
                messages.append(HumanMessage(content=content))
            elif turn.get("role") == "assistant":
                messages.append(AIMessage(content=content))

        messages.append(
            HumanMessage(content=CONVERSATIONAL_INSTRUCTIONS.format(question=query))
        )
        return messages

    def generate_response(
        self, query: str, history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        if history is None:
            history = []

        results = self.retrieve_context(query)
        sources = self.format_sources(results)

        context_text = "\n\n".join(
            f"Source: {src['source']}\nContent: {src['content']}" for src in sources
        )
        if not context_text:
            context_text = "No relevant context found in MACE AI Academy knowledge base."

        if self.llm:
            try:
                messages = self._build_messages(query, context_text, history)
                logger.info("Sending conversational prompt (%d messages)...", len(messages))
                response = self.llm.invoke(messages)
                response_text = response.content
            except Exception as e:
                logger.error("Groq API call failed: %s", e)
                response_text = (
                    "I'm sorry — I had trouble reaching our AI service. "
                    "Please try again in a moment."
                )
        else:
            response_text = self._mock_rag_response(query, context_text, history)

        return {"response": response_text, "sources": sources}

    def _mock_rag_response(
        self, query: str, context: str, history: List[Dict[str, str]]
    ) -> str:
        if "no relevant context found" in context.lower() or not context.strip():
            return (
                "I don't have that detail in our materials right now. "
                "I'd be happy to tell you about our courses, fees, or placement support — what interests you most?"
            )

        greeting = ""
        if not history:
            greeting = "Hi! Thanks for reaching out to MACE AI Academy. "

        lines = context.split("\n")
        matching = [
            line.strip()
            for line in lines
            if line.strip()
            and any(
                term in line.lower()
                for term in ["fee", "duration", "course", "placement", "month", "inr"]
            )
        ][:6]

        raw = matching if matching else [context[:300]]
        bullets = "\n".join(f"- {line[:120].strip()}" for line in raw[:6] if line.strip())
        return (
            f"{greeting}Here's what I can share:\n\n{bullets}\n\n"
            "Want details on fees, syllabus, or placements?"
        )


_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    """Lazy singleton — avoids blocking uvicorn startup on embedding model load."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
