import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from backend import chatbot, ingest
from backend.config import settings
from backend.utils import logger, sanitize_error_message

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MACE AI Academy API starting on port %s", settings.PORT)
    yield
    logger.info("MACE AI Academy API shutting down")


app = FastAPI(
    title="MACE AI Academy RAG Chatbot API",
    description="RAG-based course guidance, conversations, and student leads.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    conversation_id: str


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str
    course_interest: str


class ConvCreate(BaseModel):
    title: str = "New Chat"


@app.get("/")
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health_check():
    db_ok = False
    vector_ok = False
    try:
        conn = chatbot.get_db_connection()
        conn.execute("SELECT 1")
        conn.close()
        db_ok = True
    except Exception as exc:
        logger.error("Health check DB failed: %s", exc)

    chroma_dir = os.path.abspath(settings.CHROMA_DB_DIR)
    vector_ok = os.path.isdir(chroma_dir) and bool(os.listdir(chroma_dir))

    return {
        "status": "healthy" if db_ok and vector_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "vector_store": "ready" if vector_ok else "empty",
        "groq_api": "configured" if bool(settings.GROQ_API_KEY) else "simulation",
        "model": settings.MODEL_NAME,
        "embedding_model": settings.EMBEDDING_MODEL,
    }


@app.get("/conversations")
def list_conversations():
    return chatbot.list_conversations()


@app.post("/conversations")
def new_conversation(data: ConvCreate):
    return chatbot.create_conversation(data.title)


@app.delete("/conversations/{conversation_id}")
def delete_chat(conversation_id: str):
    deleted = chatbot.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "Conversation deleted successfully."}


@app.get("/conversations/{conversation_id}/history")
def get_history(conversation_id: str):
    if not chatbot.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return chatbot.get_conversation_history(conversation_id)


@app.post("/chat")
def chat(data: ChatRequest):
    try:
        result = chatbot.orchestrate_chat(
            conversation_id=data.conversation_id,
            question=data.question,
        )
        return {
            "response": result["response"],
            "sources": result["sources"],
            "conversation_id": data.conversation_id,
        }
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        logger.error("Chat error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sanitize_error_message("Internal processing error."),
        )


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in (".pdf", ".txt", ".docx", ".csv"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported format. Use PDF, TXT, DOCX, or CSV.",
        )

    save_path = os.path.join(os.path.abspath(settings.DATA_DIR), os.path.basename(file.filename))
    try:
        content = await file.read()
        with open(save_path, "wb") as handle:
            handle.write(content)

        logger.info("Uploaded %s", file.filename)
        if not ingest.rebuild_vector_db():
            raise HTTPException(status_code=500, detail="Upload saved but indexing failed.")
        return {"message": f"Successfully uploaded and indexed {file.filename}."}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload and process file.")


@app.post("/reingest")
def reingest_all():
    logger.info("Manual re-ingest triggered")
    if not ingest.rebuild_vector_db():
        raise HTTPException(status_code=500, detail="Failed to rebuild vector database.")
    return {"message": "ChromaDB vector database successfully rebuilt."}


@app.post("/leads")
def submit_lead(data: LeadCreate):
    try:
        lead = chatbot.create_lead(data.name, data.email, data.phone, data.course_interest)
        return {"message": "Lead submitted successfully.", "lead": lead}
    except Exception as exc:
        logger.error("Lead save error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to record lead.")


@app.get("/admin/analytics")
def get_analytics():
    return chatbot.get_admin_analytics()
