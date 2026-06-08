import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field

from backend import chatbot
from backend.agent.memory import get_memory, list_bookings_for_conversation
from backend.agent.email_service import (
    get_latest_email_log_for_booking,
    get_resend_status,
    is_resend_configured,
    list_email_logs,
    log_resend_configuration,
    retry_confirmation_email,
    send_test_email,
)
from backend.auth_service import init_auth_tables, request_otp, request_password_reset, verify_otp
from backend.agent.orchestrator import ensure_agent_ready
from backend.agent.slots import build_date_options, generate_available_dates
from backend.config import settings
from backend.utils import logger, sanitize_error_message

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MACE AI Academy API starting on port %s", settings.PORT)
    ensure_agent_ready()
    init_auth_tables()
    log_resend_configuration()
    yield
    logger.info("MACE AI Academy API shutting down")


app = FastAPI(
    title="MACE AI Academy Agentic Chatbot API",
    description="LangGraph agent with RAG, demo booking, calendar, email, and CRM tools.",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS: wide open in dev (CORS_ALLOW_ALL) fixes LAN IP + mixed localhost issues from the browser.
if settings.CORS_ALLOW_ALL:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
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
        "agent": "langgraph",
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
            "agent_metadata": result.get("agent_metadata", {}),
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
        from backend import ingest

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
    from backend import ingest

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


@app.get("/agent/status")
def agent_status():
    email_info = get_resend_status()
    return {
        "mode": "agentic",
        "framework": "langgraph",
        "tools": [
            "rag_retriever",
            "check_demo_slots",
            "book_demo_session",
            "save_lead_to_crm",
            "calendar",
            "email",
        ],
        "groq_configured": bool(settings.GROQ_API_KEY),
        "calendar_mode": "google" if settings.GOOGLE_CALENDAR_ENABLED else "simulation",
        "email_mode": "resend" if email_info.get("production_ready") else (
            "test_sender_blocked" if email_info.get("test_sender_mode") else "not_configured"
        ),
        "resend_configured": is_resend_configured(),
        "production_ready": email_info.get("production_ready"),
        "test_sender_mode": email_info.get("test_sender_mode"),
        "domain_verification_required": email_info.get("domain_verification_required"),
        "email_sender": email_info.get("sender"),
        "resend_api_key_set": email_info.get("api_key_set"),
    }


@app.get("/agent/memory/{conversation_id}")
def get_agent_memory(conversation_id: str):
    if not chatbot.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return get_memory(conversation_id)


@app.get("/demo/dates")
def demo_dates():
    dates = generate_available_dates()
    options = build_date_options(dates)
    return {"dates": options}


@app.get("/demo/slots")
def demo_slots_legacy():
    """Legacy alias — returns date values only."""
    dates = generate_available_dates()
    return {"slots": dates, "dates": build_date_options(dates)}


@app.get("/demo/bookings/{conversation_id}")
def demo_bookings(conversation_id: str):
    if not chatbot.conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"bookings": list_bookings_for_conversation(conversation_id)}


class DemoBookRequest(BaseModel):
    conversation_id: str
    name: str
    email: EmailStr
    phone: str
    course_interest: str
    demo_date: str | None = None
    slot_datetime: str | None = None


@app.post("/demo/book")
def book_demo_api(data: DemoBookRequest):
    from backend.agent.booking_workflow import execute_demo_booking
    from backend.agent.slots import normalize_demo_date, pick_alternative_dates

    selected = data.demo_date or data.slot_datetime
    if not selected:
        raise HTTPException(status_code=400, detail="demo_date is required.")

    try:
        result = execute_demo_booking(
            conversation_id=data.conversation_id,
            name=data.name,
            email=data.email,
            phone=data.phone,
            course_interest=data.course_interest,
            demo_date=selected,
        )
        if not result.get("ok"):
            date = normalize_demo_date(selected)
            alts = result.get("alternatives") or pick_alternative_dates(exclude=date)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": result.get("message", "Date unavailable."),
                    "code": result.get("code", "duplicate_booking"),
                    "alternatives": alts,
                },
            )
        return {
            "message": result["message"],
            "booking_id": result.get("booking_id"),
            "email_status": result.get("email_status"),
            "email_log_id": result.get("email_log_id"),
            "email_delivery": result.get("email_delivery"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Demo book API error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Demo booking failed.")


@app.get("/demo/bookings/id/{booking_id}/email")
def get_booking_email_status(booking_id: int):
    from backend.agent.memory import get_booking

    booking = get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    log = get_latest_email_log_for_booking(booking_id)
    return {
        "booking_id": booking_id,
        "recipient": booking["email"],
        "email_status": log.get("status") if log else "none",
        "email_log": log,
    }


@app.post("/demo/bookings/id/{booking_id}/retry-email")
def retry_booking_email(booking_id: int):
    from backend.agent.memory import get_booking

    booking = get_booking(booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found.")
    if booking.get("status") != "confirmed":
        raise HTTPException(status_code=400, detail="Only confirmed bookings can receive email.")

    result = retry_confirmation_email(booking_id)
    if not result.get("ok") and result.get("status") == "failed":
        raise HTTPException(
            status_code=502,
            detail={
                "message": result.get("message", "Email delivery failed."),
                "email_status": result.get("status"),
                "email_log_id": result.get("log_id"),
            },
        )
    return {
        "ok": True,
        "message": result.get("message", "Email sent."),
        "email_status": result.get("status"),
        "email_log_id": result.get("log_id"),
        "recipient": result.get("recipient"),
    }


class TestEmailRequest(BaseModel):
    to: EmailStr


@app.get("/demo/email/status")
def demo_email_status():
    """Resend configuration and domain readiness check."""
    return get_resend_status()


@app.post("/demo/email/test")
def demo_email_test(data: TestEmailRequest):
    """Send a test email to validate Resend delivery to the given inbox."""
    logger.info("Test email endpoint called for recipient=%s", data.to)
    result = send_test_email(data.to)
    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail={
                "message": result.get("message", "Test email failed."),
                "recipient": result.get("recipient"),
                "sender": result.get("sender"),
                "resend_error": result.get("resend_error"),
                "resend_config": result.get("resend_config"),
            },
        )
    return {
        "ok": True,
        "message": f"Test email sent to {result.get('recipient')}.",
        "recipient": result.get("recipient"),
        "sender": result.get("sender"),
        "resend_id": result.get("resend_id"),
        "delivery_status": result.get("delivery_status"),
        "resend_response": result.get("resend_response"),
        "resend_config": result.get("resend_config"),
    }


@app.get("/demo/email/logs")
def demo_email_logs(status: str | None = None, limit: int = 50):
    """Admin view of email delivery attempts (filter by status=failed)."""
    logs = list_email_logs(status=status, limit=min(limit, 200))
    failed = sum(1 for row in logs if row.get("status") == "failed")
    return {
        "logs": logs,
        "count": len(logs),
        "failed_count": failed,
        "resend_configured": is_resend_configured(),
    }


class SendOtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    reset_base_url: str = "http://localhost:3000"


@app.post("/auth/send-otp")
def send_otp(data: SendOtpRequest):
    try:
        result = request_otp(data.email)
        if not result.get("ok"):
            raise HTTPException(status_code=502, detail=result.get("message", "Failed to send OTP."))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Send OTP error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send verification code.")


@app.post("/auth/verify-otp")
def verify_otp_code(data: VerifyOtpRequest):
    result = verify_otp(data.email, data.otp)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("message", "Invalid code."))
    return result


@app.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest):
    try:
        result = request_password_reset(data.email, data.reset_base_url)
        if not result.get("ok"):
            raise HTTPException(
                status_code=502,
                detail=result.get("message", "Failed to send reset email."),
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Forgot password error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send password reset email.")
