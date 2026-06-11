import os
from typing import Any, Dict, List, Tuple

from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from backend.config import settings
from backend.ingest import get_embeddings
from backend.kb_processor import detect_course_filter, detect_section_filter, expand_query
from backend.prompts import (
    CONVERSATIONAL_INSTRUCTIONS,
    NO_KB_RESPONSE,
    RAG_CONTEXT_BLOCK,
    SYSTEM_PROMPT,
)
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
                collection_name=settings.CHROMA_COLLECTION_NAME,
            )

            try:
                doc_count = self.vector_store._collection.count()
                if doc_count == 0:
                    logger.warning(
                        "Vector store collection '%s' is empty. Run: python -m backend.ingest",
                        settings.CHROMA_COLLECTION_NAME,
                    )
                else:
                    logger.info(
                        "Vector store ready: collection=%s documents=%d",
                        settings.CHROMA_COLLECTION_NAME,
                        doc_count,
                    )
            except Exception:
                pass

            if settings.GROQ_API_KEY:
                logger.info("Initializing Groq LLM with model: %s", settings.MODEL_NAME)
                self.llm = ChatGroq(
                    api_key=settings.GROQ_API_KEY,
                    model=settings.MODEL_NAME,
                    temperature=0.15,
                )
            else:
                logger.warning("GROQ_API_KEY not found. Running in simulation mode.")
                self.llm = None

            self.initialized = True
            logger.info("RAG Pipeline successfully initialized.")
        except Exception as e:
            logger.error("Error initializing RAG Pipeline: %s", e, exc_info=True)
            self.initialized = False

    def _search(
        self,
        query: str,
        k: int,
        metadata_filter: Dict[str, str] | None = None,
    ) -> List[Tuple[Document, float]]:
        if metadata_filter:
            return self.vector_store.similarity_search_with_score(
                query,
                k=k,
                filter=metadata_filter,
            )
        return self.vector_store.similarity_search_with_score(query, k=k)

    def _merge_results(
        self,
        *result_sets: List[Tuple[Document, float]],
    ) -> List[Tuple[Document, float]]:
        merged: Dict[str, Tuple[Document, float]] = {}
        for results in result_sets:
            for doc, score in results:
                key = doc.page_content.strip()
                if key not in merged or score < merged[key][1]:
                    merged[key] = (doc, score)
        return sorted(merged.values(), key=lambda item: item[1])

    def retrieve_context(self, query: str, k: int | None = None) -> List[Tuple[Document, float]]:
        if k is None:
            k = settings.RAG_TOP_K

        if not self.initialized or self.vector_store is None:
            self._initialize_pipeline()

        if self.vector_store is None:
            logger.error("ChromaDB vector store is not available.")
            return []

        try:
            expanded_query = expand_query(query)
            course_id = detect_course_filter(query)
            section_filter = detect_section_filter(query)
            fetch_k = max(settings.RAG_FETCH_K, k * 2)

            result_sets: List[List[Tuple[Document, float]]] = []
            if course_id:
                logger.info("RAG course filter detected: %s", course_id)
                result_sets.append(
                    self._search(
                        expanded_query,
                        k=fetch_k,
                        metadata_filter={"course_id": course_id},
                    )
                )
            elif section_filter:
                logger.info("RAG section filter detected: %s", section_filter)
                result_sets.append(
                    self._search(expanded_query, k=fetch_k, metadata_filter=section_filter)
                )

            result_sets.append(self._search(expanded_query, k=fetch_k))
            merged = self._merge_results(*result_sets)

            relevant = [
                (doc, score)
                for doc, score in merged
                if float(score) <= settings.RAG_SCORE_THRESHOLD
            ]
            if not relevant:
                relevant = merged[:k]
            else:
                relevant = relevant[:k]

            scores = [float(score) for _, score in relevant]
            logger.info(
                "RAG retrieve: query=%r expanded=%r course_filter=%s chunks=%d top_k=%d scores=%s",
                query[:120],
                expanded_query[:160],
                course_id,
                len(relevant),
                k,
                scores,
            )
            for idx, (doc, score) in enumerate(relevant, start=1):
                source = doc.metadata.get("source", "unknown")
                course = doc.metadata.get("course_name") or doc.metadata.get("section_type", "")
                logger.info(
                    "RAG chunk %d: source=%s course=%s score=%.4f preview=%r",
                    idx,
                    os.path.basename(str(source)),
                    course,
                    float(score),
                    doc.page_content[:120],
                )
            return relevant
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

            source_file = doc.metadata.get("source", settings.KNOWLEDGE_BASE_FILE)
            sources.append({
                "source": os.path.basename(source_file),
                "content": content,
                "score": float(score),
                "course": doc.metadata.get("course_name") or doc.metadata.get("section_title", ""),
                "course_id": doc.metadata.get("course_id", ""),
                "section_type": doc.metadata.get("section_type", ""),
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
        self,
        query: str,
        history: List[Dict[str, str]] | None = None,
        k: int | None = None,
        pre_results: List[Tuple[Document, float]] | None = None,
    ) -> Dict[str, Any]:
        if history is None:
            history = []

        results = pre_results if pre_results is not None else self.retrieve_context(query, k=k)
        sources = self.format_sources(results)

        if not sources:
            logger.info("RAG generate: no relevant context for query=%r", query[:120])
            return {"response": NO_KB_RESPONSE, "sources": []}

        context_text = "\n\n".join(
            f"Source: {src['source']} | Section: {src.get('course') or src.get('section_type', 'general')}\n"
            f"Content: {src['content']}"
            for src in sources
        )

        if self.llm:
            try:
                messages = self._build_messages(query, context_text, history)
                logger.info("Sending conversational prompt (%d messages)...", len(messages))
                response = self.llm.invoke(messages)
                response_text = response.content.strip()
                if not response_text:
                    response_text = NO_KB_RESPONSE
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
        if not context.strip():
            return NO_KB_RESPONSE

        lines = [line.strip() for line in context.split("\n") if line.strip()]
        bullets = "\n".join(f"- {line[:140]}" for line in lines[:6])
        return bullets or NO_KB_RESPONSE


_pipeline: RAGPipeline | None = None


def get_rag_pipeline() -> RAGPipeline:
    """Lazy singleton — avoids blocking uvicorn startup on embedding model load."""
    global _pipeline
    if _pipeline is None:
        _pipeline = RAGPipeline()
    return _pipeline
