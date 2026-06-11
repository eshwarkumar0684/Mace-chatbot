import os
import shutil
from typing import List

from langchain_community.document_loaders import (
    CSVLoader,
    Docx2txtLoader,
    PyPDFLoader,
    TextLoader,
)
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from backend.config import settings
from backend.kb_processor import (
    SUPPLEMENTAL_FILE_META,
    chunk_knowledge_base,
    chunk_supplemental_document,
)
from backend.utils import logger


def load_single_document(file_path: str) -> List[Document]:
    """Load a single document based on its extension."""
    ext = os.path.splitext(file_path)[-1].lower()
    try:
        if ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
            return loader.load()
        if ext == ".pdf":
            loader = PyPDFLoader(file_path)
            return loader.load()
        if ext == ".docx":
            loader = Docx2txtLoader(file_path)
            return loader.load()
        if ext == ".csv":
            loader = CSVLoader(file_path)
            return loader.load()
        logger.warning("Unsupported file type: %s for %s", ext, file_path)
        return []
    except Exception as e:
        logger.error("Error loading file %s: %s", file_path, e)
        return []


def load_primary_knowledge_base(data_dir: str) -> List[Document]:
    """Load and chunk the canonical MACE knowledge base document."""
    kb_path = os.path.join(data_dir, settings.KNOWLEDGE_BASE_FILE)
    if not os.path.isfile(kb_path):
        logger.error("Primary knowledge base not found: %s", kb_path)
        return []

    logger.info("Loading primary knowledge base: %s", kb_path)
    raw_docs = load_single_document(kb_path)
    if not raw_docs:
        return []

    raw_text = raw_docs[0].page_content
    chunks = chunk_knowledge_base(raw_text)
    for chunk in chunks:
        chunk.metadata["source"] = settings.KNOWLEDGE_BASE_FILE
    return chunks


def load_supplementary_documents(data_dir: str) -> List[Document]:
    """Load FAQ and course prospectus files that complement the primary KB docx."""
    chunks: List[Document] = []
    for filename in sorted(SUPPLEMENTAL_FILE_META):
        file_path = os.path.join(data_dir, filename)
        if not os.path.isfile(file_path):
            logger.warning("Supplemental knowledge file missing: %s", file_path)
            continue

        raw_docs = load_single_document(file_path)
        if not raw_docs:
            continue

        file_chunks = chunk_supplemental_document(filename, raw_docs[0].page_content)
        chunks.extend(file_chunks)
        logger.info("Loaded supplemental file %s (%d chunks)", filename, len(file_chunks))

    return chunks


def get_embeddings():
    """Load the sentence transformer embedding model."""
    logger.info("Initializing embedding model: %s", settings.EMBEDDING_MODEL)
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _reset_chroma_store(chroma_dir: str) -> None:
    if os.path.isdir(chroma_dir):
        shutil.rmtree(chroma_dir)
        logger.info("Removed existing vector store at %s", chroma_dir)
    os.makedirs(chroma_dir, exist_ok=True)


def rebuild_vector_db() -> bool:
    """Load, chunk, and store the primary knowledge base into ChromaDB."""
    try:
        data_dir = os.path.abspath(settings.DATA_DIR)
        logger.info("Reading knowledge base from: %s", data_dir)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

        chunks = load_primary_knowledge_base(data_dir)
        supplemental = load_supplementary_documents(data_dir)
        chunks.extend(supplemental)
        if not chunks:
            logger.warning("No knowledge base chunks created.")
            return False
        logger.info(
            "Prepared %d total chunks (primary + %d supplemental)",
            len(chunks),
            len(supplemental),
        )

        embeddings = get_embeddings()
        chroma_dir = os.path.abspath(settings.CHROMA_DB_DIR)
        _reset_chroma_store(chroma_dir)
        logger.info("Storing %d chunks in vector database: %s", len(chunks), chroma_dir)

        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=chroma_dir,
            collection_name=settings.CHROMA_COLLECTION_NAME,
        )
        if hasattr(vector_db, "persist"):
            vector_db.persist()

        course_ids = sorted({c.metadata.get("course_id", "") for c in chunks if c.metadata.get("course_id")})
        logger.info(
            "ChromaDB rebuilt successfully. chunks=%d courses=%s",
            len(chunks),
            course_ids,
        )

        try:
            from backend.rag_pipeline import get_rag_pipeline

            get_rag_pipeline().reload()
        except Exception:
            pass

        return True
    except Exception as e:
        logger.error("Failed to rebuild Vector DB: %s", e, exc_info=True)
        return False


if __name__ == "__main__":
    import sys

    success = rebuild_vector_db()
    sys.exit(0 if success else 1)
