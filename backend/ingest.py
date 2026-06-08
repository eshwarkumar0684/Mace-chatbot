import os
import glob
from typing import List
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    Docx2txtLoader
)
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from backend.config import settings
from backend.utils import logger

def load_single_document(file_path: str) -> List[Document]:
    """Load a single document based on its extension."""
    ext = os.path.splitext(file_path)[-1].lower()
    try:
        if ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
            return loader.load()
        elif ext == ".pdf":
            loader = PyPDFLoader(file_path)
            return loader.load()
        elif ext == ".docx":
            loader = Docx2txtLoader(file_path)
            return loader.load()
        elif ext == ".csv":
            loader = CSVLoader(file_path)
            return loader.load()
        else:
            logger.warning(f"Unsupported file type: {ext} for {file_path}")
            return []
    except Exception as e:
        logger.error(f"Error loading file {file_path}: {str(e)}")
        return []

def load_documents(data_dir: str) -> List[Document]:
    """Load all supported documents from the data directory."""
    documents = []
    # Support txt, pdf, docx, csv
    supported_extensions = ["*.txt", "*.pdf", "*.docx", "*.csv"]
    
    for ext in supported_extensions:
        files = glob.glob(os.path.join(data_dir, ext))
        for file in files:
            logger.info(f"Loading document: {file}")
            docs = load_single_document(file)
            documents.extend(docs)
            
    logger.info(f"Total documents loaded: {len(documents)}")
    return documents

def split_documents(documents: List[Document]) -> List[Document]:
    """Split documents into smaller chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True
    )
    chunks = splitter.split_documents(documents)
    logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks.")
    return chunks

def get_embeddings():
    """Load the sentence transformer embedding model."""
    logger.info(f"Initializing embedding model: {settings.EMBEDDING_MODEL}")
    return HuggingFaceEmbeddings(
        model_name=settings.EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'}, # Default to CPU for portability
        encode_kwargs={'normalize_embeddings': True}
    )

def rebuild_vector_db() -> bool:
    """Load, split, and store all documents into ChromaDB."""
    try:
        # Load documents
        data_dir = os.path.abspath(settings.DATA_DIR)
        logger.info(f"Reading documents from: {data_dir}")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.warning(f"Data directory created but was empty: {data_dir}")
            return False
            
        docs = load_documents(data_dir)
        if not docs:
            logger.warning("No documents found to ingest.")
            return False
            
        # Split documents
        chunks = split_documents(docs)
        if not chunks:
            logger.warning("No chunks created.")
            return False
            
        # Initialize embeddings
        embeddings = get_embeddings()
        
        # Build Vector Store
        chroma_dir = os.path.abspath(settings.CHROMA_DB_DIR)
        logger.info(f"Storing vector database in: {chroma_dir}")
        
        # Initialize vector store (this will overwrite/create the collection)
        # Chroma expects client or directory
        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=chroma_dir,
            collection_name="mace_academy",
        )
        # Chroma in recent versions persists automatically, but call persist if exists
        if hasattr(vector_db, "persist"):
            vector_db.persist()
            
        logger.info("ChromaDB vector database successfully rebuilt.")

        try:
            from backend.rag_pipeline import get_rag_pipeline

            get_rag_pipeline().reload()
        except Exception:
            pass

        return True
    except Exception as e:
        logger.error(f"Failed to rebuild Vector DB: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    import sys
    success = rebuild_vector_db()
    sys.exit(0 if success else 1)
