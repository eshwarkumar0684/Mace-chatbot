"""Production email delivery via Resend API."""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

import resend
from resend.exceptions import ResendError

from backend.chatbot import get_db_connection
from backend.config import BACKEND_DIR, PROJECT_ROOT, settings
from backend.utils import logger

EMAIL_STATUS_PENDING = "pending"
EMAIL_STATUS_SENT = "sent"
EMAIL_STATUS_FAILED = "failed"

PROVIDER_RESEND = "resend"

OTP_EXPIRY_MINUTES = 5
RESET_LINK_EXPIRY_MINUTES = 30
MAX_SEND_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 1.0

_ENV_ROOT = PROJECT_ROOT / ".env"
_ENV_BACKEND = BACKEND_DIR / ".env"
TEST_SENDER_DOMAIN = "resend.dev"


def normalize_recipient(email: str) -> str:
    return (email or "").strip().lower()


def is_valid_recipient(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", normalize_recipient(email)))


def resolve_sender_address() -> str:
    raw = (settings.EMAIL_FROM or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("EMAIL_FROM is not set in .env")
    if "<" in raw and ">" in raw:
        return raw
    if "@" in raw:
        return raw
    raise ValueError(f"EMAIL_FROM is invalid: {raw!r}")


def is_test_sender() -> bool:
    """True when using Resend's shared test sender (cannot deliver to arbitrary inboxes)."""
    sender = resolve_sender_address().lower()
    return TEST_SENDER_DOMAIN in sender


def validate_resend_api_key(key: str) -> Tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "RESEND_API_KEY is empty"
    if not key.startswith("re_"):
        return False, "RESEND_API_KEY must start with 're_'"
    if len(key) < 20:
        return False, "RESEND_API_KEY looks too short"
    return True, ""


def is_resend_configured() -> bool:
    key_ok, _ = validate_resend_api_key(settings.RESEND_API_KEY or "")
    try:
        sender_ok = "@" in resolve_sender_address()
    except ValueError:
        sender_ok = False
    return bool(key_ok and sender_ok)


is_smtp_configured = is_resend_configured


def mask_api_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return "re_****"
    return f"{key[:7]}...{key[-4:]}"


def get_resend_status() -> Dict[str, Any]:
    key = (settings.RESEND_API_KEY or "").strip()
    key_ok, key_err = validate_resend_api_key(key)
    try:
        sender = resolve_sender_address()
        sender_error = None
    except ValueError as exc:
        sender = settings.EMAIL_FROM or ""
        sender_error = str(exc)

    test_sender = is_test_sender() if not sender_error else False
    env_sources = []
    if _ENV_ROOT.is_file():
        env_sources.append(str(_ENV_ROOT))
    if _ENV_BACKEND.is_file():
        env_sources.append(str(_ENV_BACKEND))

    production_ready = is_resend_configured() and not test_sender

    return {
        "configured": is_resend_configured(),
        "production_ready": production_ready,
        "api_key_set": bool(key),
        "api_key_valid_format": key_ok,
        "api_key_validation_error": key_err if not key_ok else None,
        "api_key_masked": mask_api_key(key),
        "sender": sender,
        "sender_error": sender_error,
        "test_sender_mode": test_sender,
        "domain_verification_required": test_sender,
        "env_files": env_sources,
    }


def log_resend_configuration() -> Dict[str, Any]:
    status = get_resend_status()
    logger.info(
        "Resend config: configured=%s production_ready=%s api_key=%s EMAIL_FROM=%s "
        "test_sender=%s env_files=%s",
        status["configured"],
        status["production_ready"],
        status["api_key_masked"],
        status["sender"],
        status["test_sender_mode"],
        status["env_files"] or ["(process env only)"],
    )
    if not status["api_key_set"]:
        logger.warning("RESEND_API_KEY missing — add to %s", _ENV_ROOT)
    elif not status["api_key_valid_format"]:
        logger.warning("RESEND_API_KEY invalid: %s", status["api_key_validation_error"])
    if status.get("sender_error"):
        logger.warning("EMAIL_FROM invalid: %s", status["sender_error"])
    if status["test_sender_mode"]:
        logger.warning(
            "EMAIL_FROM uses Resend test sender (%s). Students will NOT receive mail. "
            "Verify your domain at https://resend.com/domains and set "
            "EMAIL_FROM=MACE AI Academy <noreply@yourdomain.com>",
            status["sender"],
        )
    elif status["production_ready"]:
        logger.info("Resend production mode — emails deliver to student inboxes.")
    return status


def _configure_resend() -> None:
    key = (settings.RESEND_API_KEY or "").strip()
    key_ok, err = validate_resend_api_key(key)
    if not key_ok:
        raise ValueError(err)
    resend.api_key = key


def parse_resend_error(exc: BaseException) -> str:
    if isinstance(exc, ResendError):
        return str(exc.message) if getattr(exc, "message", None) else str(exc)
    return str(exc)


def format_resend_error(exc: BaseException) -> Dict[str, Any]:
    if isinstance(exc, ResendError):
        return {
            "type": type(exc).__name__,
            "message": str(getattr(exc, "message", None) or exc),
            "code": getattr(exc, "code", None),
            "error_type": getattr(exc, "error_type", None),
            "suggested_action": getattr(exc, "suggested_action", None),
        }
    return {"type": type(exc).__name__, "message": str(exc)}


def is_domain_verification_error(message: str) -> bool:
    lowered = message.lower()
    return (
        "only send testing emails" in lowered
        or "verify a domain" in lowered
        or "domain is not verified" in lowered
        or ("domain" in lowered and "not verified" in lowered)
    )


def friendly_delivery_error(message: str) -> str:
    if is_domain_verification_error(message):
        return (
            "Email could not be delivered. Verify your domain at resend.com/domains and set "
            "EMAIL_FROM to an address on that domain (e.g. noreply@yourdomain.com). "
            "The Resend test sender onboarding@resend.dev cannot email students."
        )
    return message


def init_email_logs_table() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        provider TEXT,
        provider_response TEXT,
        attempts INTEGER DEFAULT 0,
        last_error TEXT,
        email_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_logs_booking ON email_logs(booking_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_logs_status ON email_logs(status)")
    try:
        cursor.execute("ALTER TABLE email_logs ADD COLUMN email_type TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()


def create_email_log(
    *,
    booking_id: Optional[int],
    recipient: str,
    subject: str,
    body: str,
    status: str = EMAIL_STATUS_PENDING,
    provider: Optional[str] = None,
    provider_response: Optional[str] = None,
    last_error: Optional[str] = None,
    email_type: Optional[str] = None,
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO email_logs
        (booking_id, recipient, subject, body, status, provider, provider_response,
         attempts, last_error, email_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            booking_id,
            normalize_recipient(recipient),
            subject,
            body,
            status,
            provider,
            provider_response,
            last_error,
            email_type,
        ),
    )
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def update_email_log(log_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = []
    values = []
    for key, value in fields.items():
        if key == "updated_at":
            columns.append("updated_at = CURRENT_TIMESTAMP")
        else:
            columns.append(f"{key} = ?")
            values.append(value)
    if "updated_at" not in fields:
        columns.append("updated_at = CURRENT_TIMESTAMP")
    values.append(log_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE email_logs SET {', '.join(columns)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_email_log(log_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM email_logs WHERE id = ?", (log_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_latest_email_log_for_booking(booking_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM email_logs WHERE booking_id = ? ORDER BY id DESC LIMIT 1",
        (booking_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_email_logs(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute(
            "SELECT * FROM email_logs WHERE status = ? ORDER BY id DESC LIMIT ?",
            (status, limit),
        )
    else:
        cursor.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def _send_via_resend_once(
    recipient: str,
    subject: str,
    html: str,
    text: str,
) -> Dict[str, Any]:
    _configure_resend()
    sender = resolve_sender_address()
    params: resend.Emails.SendParams = {
        "from": sender,
        "to": [recipient],
        "subject": subject,
        "html": html,
        "text": text,
    }
    logger.info(
        "Resend API request sender=%s recipient=%s subject=%s payload=%s",
        sender,
        recipient,
        subject,
        {"from": sender, "to": [recipient], "subject": subject},
    )
    try:
        response = resend.Emails.send(params)
    except ResendError as exc:
        err = format_resend_error(exc)
        logger.error(
            "Resend API error sender=%s recipient=%s error=%s",
            sender,
            recipient,
            err,
        )
        raise

    if isinstance(response, dict):
        response_id = response.get("id", "")
        logger.info(
            "Resend API response sender=%s recipient=%s status=sent id=%s full=%s",
            sender,
            recipient,
            response_id,
            response,
        )
    else:
        response_id = getattr(response, "id", None) or str(response)
        logger.info(
            "Resend API response sender=%s recipient=%s status=sent id=%s",
            sender,
            recipient,
            response_id,
        )
        response = {"id": response_id}

    if not response_id:
        raise RuntimeError(f"Resend returned no message id: {response!r}")

    return {
        "resend_id": response_id,
        "provider_response": f"resend_id={response_id}",
        "full_response": response if isinstance(response, dict) else {"id": response_id},
        "delivery_status": EMAIL_STATUS_SENT,
    }


def _send_via_resend_with_retry(
    recipient: str,
    subject: str,
    html: str,
    text: str,
) -> Tuple[Dict[str, Any], int]:
    last_exc: Optional[BaseException] = None
    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        try:
            result = _send_via_resend_once(recipient, subject, html, text)
            return result, attempt
        except ResendError as exc:
            last_exc = exc
            err_msg = parse_resend_error(exc)
            logger.warning(
                "Resend attempt %d/%d failed recipient=%s error=%s details=%s",
                attempt,
                MAX_SEND_ATTEMPTS,
                recipient,
                err_msg,
                format_resend_error(exc),
            )
            if is_domain_verification_error(err_msg):
                raise
            if attempt < MAX_SEND_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Resend attempt %d/%d error for %s: %s",
                attempt,
                MAX_SEND_ATTEMPTS,
                recipient,
                exc,
            )
            if attempt < MAX_SEND_ATTEMPTS:
                time.sleep(RETRY_DELAY_SECONDS * attempt)
    raise last_exc or RuntimeError("Resend send failed")


def _deliver_email(
    *,
    recipient: str,
    subject: str,
    html: str,
    text: str,
    log_id: Optional[int] = None,
    booking_id: Optional[int] = None,
    email_type: Optional[str] = None,
) -> Dict[str, Any]:
    student_email = normalize_recipient(recipient)
    logger.info(
        "Email delivery start type=%s booking=%s student_email=%s",
        email_type,
        booking_id,
        student_email,
    )

    if not is_valid_recipient(student_email):
        msg = f"Invalid recipient email: {student_email!r}"
        logger.error(msg)
        if log_id:
            update_email_log(log_id, status=EMAIL_STATUS_FAILED, last_error=msg, attempts=1)
        return {"ok": False, "status": EMAIL_STATUS_FAILED, "message": msg, "log_id": log_id}

    if log_id is None:
        log_id = create_email_log(
            booking_id=booking_id,
            recipient=student_email,
            subject=subject,
            body=text,
            status=EMAIL_STATUS_PENDING,
            email_type=email_type,
        )

    key_ok, key_err = validate_resend_api_key(settings.RESEND_API_KEY or "")
    if not key_ok:
        update_email_log(log_id, status=EMAIL_STATUS_FAILED, attempts=1, last_error=key_err)
        return {
            "ok": False,
            "status": EMAIL_STATUS_FAILED,
            "recipient": student_email,
            "log_id": log_id,
            "message": key_err,
        }

    if is_test_sender():
        msg = (
            "Cannot deliver to students while EMAIL_FROM uses onboarding@resend.dev. "
            "Verify your domain at resend.com/domains and set EMAIL_FROM to "
            "noreply@yourdomain.com"
        )
        logger.error("Blocked send to %s: %s", student_email, msg)
        update_email_log(log_id, status=EMAIL_STATUS_FAILED, attempts=1, last_error=msg)
        return {
            "ok": False,
            "status": EMAIL_STATUS_FAILED,
            "recipient": student_email,
            "log_id": log_id,
            "message": msg,
            "domain_verification_required": True,
        }

    sender = resolve_sender_address()
    logger.info(
        "Delivering email sender=%s recipient=%s booking=%s type=%s",
        sender,
        student_email,
        booking_id,
        email_type,
    )

    try:
        send_result, attempts_used = _send_via_resend_with_retry(
            student_email, subject, html, text
        )
        provider_response = send_result["provider_response"]
        resend_id = send_result["resend_id"]
        update_email_log(
            log_id,
            status=EMAIL_STATUS_SENT,
            provider=PROVIDER_RESEND,
            provider_response=provider_response,
            attempts=attempts_used,
            last_error=None,
        )
        logger.info(
            "Email delivered sender=%s recipient=%s booking=%s resend_id=%s "
            "delivery_status=%s attempts=%d full_response=%s",
            sender,
            student_email,
            booking_id,
            resend_id,
            EMAIL_STATUS_SENT,
            attempts_used,
            send_result.get("full_response"),
        )
        return {
            "ok": True,
            "status": EMAIL_STATUS_SENT,
            "recipient": student_email,
            "sender": sender,
            "log_id": log_id,
            "provider": PROVIDER_RESEND,
            "resend_id": resend_id,
            "delivery_status": EMAIL_STATUS_SENT,
            "resend_response": send_result.get("full_response"),
            "attempts": attempts_used,
            "message": f"Confirmation email sent to {student_email}.",
        }
    except Exception as exc:
        raw_err = parse_resend_error(exc)
        err_msg = friendly_delivery_error(raw_err)
        err_details = format_resend_error(exc)
        log = get_email_log(log_id)
        attempts = (log.get("attempts") or 0) + MAX_SEND_ATTEMPTS
        update_email_log(
            log_id,
            status=EMAIL_STATUS_FAILED,
            provider=PROVIDER_RESEND,
            attempts=attempts,
            last_error=raw_err,
        )
        logger.error(
            "Email delivery failed sender=%s recipient=%s booking=%s error=%s details=%s",
            sender,
            student_email,
            booking_id,
            raw_err,
            err_details,
            exc_info=True,
        )
        return {
            "ok": False,
            "status": EMAIL_STATUS_FAILED,
            "recipient": student_email,
            "sender": sender,
            "log_id": log_id,
            "message": err_msg,
            "resend_error": err_details,
            "domain_verification_required": is_domain_verification_error(raw_err),
        }


def send_test_email(to_email: str) -> Dict[str, Any]:
    """Send a test email to validate Resend configuration and delivery."""
    recipient = normalize_recipient(to_email)
    sender = resolve_sender_address()
    status = get_resend_status()

    logger.info(
        "Test email requested sender=%s recipient=%s production_ready=%s",
        sender,
        recipient,
        status.get("production_ready"),
    )

    subject = "MACE AI Academy — Resend delivery test"
    text = (
        f"This is a test email from MACE AI Academy chatbot.\n\n"
        f"Sender: {sender}\n"
        f"Recipient: {recipient}\n"
        f"If you received this, Resend delivery is working."
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;">
      <h2>Resend Delivery Test</h2>
      <p>This confirms email delivery is working.</p>
      <ul>
        <li><strong>Sender:</strong> {sender}</li>
        <li><strong>Recipient:</strong> {recipient}</li>
      </ul>
    </div>
    """

    result = _deliver_email(
        recipient=recipient,
        subject=subject,
        html=html,
        text=text,
        email_type="test",
    )
    result["resend_config"] = status
    return result


def build_confirmation_email(
    name: str,
    email: str,
    demo_date: str,
    course_interest: str,
    booking_id: Optional[int] = None,
    slot_datetime: str | None = None,
    meet_link: str | None = None,
) -> tuple[str, str, str]:
    from backend.agent.slots import format_date_display, normalize_demo_date

    date_value = normalize_demo_date(demo_date or slot_datetime or "")
    date_label = format_date_display(date_value)
    ref = f"#{booking_id}" if booking_id else "pending"
    subject = f"MACE AI Academy — Demo confirmed ({date_label})"
    text = f"""Hi {name},

Your free demo session is confirmed!

Booking reference: {ref}
Name: {name}
Email: {email}
Course: {course_interest}
Date: {date_label}

We look forward to speaking with you!

— MACE AI Academy Counselor Team
"""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; color: #1a1a2e;">
      <h2 style="color: #2563eb;">Demo Confirmed!</h2>
      <p>Hi {name},</p>
      <p>Your free demo session for <strong>{course_interest}</strong> is confirmed.</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        <tr><td style="padding:8px 0;color:#666;">Reference</td><td><strong>{ref}</strong></td></tr>
        <tr><td style="padding:8px 0;color:#666;">Name</td><td>{name}</td></tr>
        <tr><td style="padding:8px 0;color:#666;">Email</td><td>{email}</td></tr>
        <tr><td style="padding:8px 0;color:#666;">Course</td><td>{course_interest}</td></tr>
        <tr><td style="padding:8px 0;color:#666;">Date</td><td>{date_label}</td></tr>
      </table>
      <p>— MACE AI Academy Counselor Team</p>
    </div>
    """
    return subject, html, text


def send_confirmation_email(
    *,
    booking_id: Optional[int],
    recipient: str,
    name: str,
    course_interest: str,
    demo_date: str | None = None,
    slot_datetime: str | None = None,
    meet_link: str | None = None,
    log_id: Optional[int] = None,
) -> Dict[str, Any]:
    student_email = normalize_recipient(recipient)
    date_value = demo_date or slot_datetime or ""
    logger.info(
        "send_confirmation_email booking=%s student=%s name=%s date=%s",
        booking_id,
        student_email,
        name,
        date_value,
    )
    subject, html, text = build_confirmation_email(
        name=name,
        email=student_email,
        demo_date=date_value,
        course_interest=course_interest,
        booking_id=booking_id,
    )
    if log_id is None:
        log_id = create_email_log(
            booking_id=booking_id,
            recipient=student_email,
            subject=subject,
            body=text,
            status=EMAIL_STATUS_PENDING,
            email_type="demo_confirmation",
        )
    return _deliver_email(
        recipient=student_email,
        subject=subject,
        html=html,
        text=text,
        log_id=log_id,
        booking_id=booking_id,
        email_type="demo_confirmation",
    )


def retry_confirmation_email(booking_id: int) -> Dict[str, Any]:
    from backend.agent.memory import get_booking

    booking = get_booking(booking_id)
    if not booking:
        return {"ok": False, "message": "Booking not found."}

    recipient = normalize_recipient(booking["email"])
    logger.info("Retry confirmation email booking=%s student=%s", booking_id, recipient)
    return send_confirmation_email(
        booking_id=booking_id,
        recipient=recipient,
        name=booking["name"],
        demo_date=booking["slot_datetime"],
        course_interest=booking["course_interest"],
    )


def send_otp_email(to_email: str, otp: str) -> Dict[str, Any]:
    subject = "MACE Verification"
    text = (
        f"Your MACE verification code is: {otp}\n\n"
        f"This code expires in {OTP_EXPIRY_MINUTES} minutes."
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;">
      <h2>MACE Verification</h2>
      <p style="font-size:32px;font-weight:bold;letter-spacing:6px;color:#2563eb;">{otp}</p>
      <p>Expires in {OTP_EXPIRY_MINUTES} minutes.</p>
    </div>
    """
    return _deliver_email(
        recipient=to_email, subject=subject, html=html, text=text, email_type="otp"
    )


def send_reset_email(to_email: str, reset_link: str) -> Dict[str, Any]:
    subject = "Password Reset"
    text = f"Reset your password: {reset_link}\nExpires in {RESET_LINK_EXPIRY_MINUTES} minutes."
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;">
      <h2>Password Reset</h2>
      <p><a href="{reset_link}">Reset Password</a></p>
      <p>Expires in {RESET_LINK_EXPIRY_MINUTES} minutes.</p>
    </div>
    """
    return _deliver_email(
        recipient=to_email, subject=subject, html=html, text=text, email_type="password_reset"
    )


def email_delivery_summary(result: Dict[str, Any]) -> str:
    status = result.get("status", EMAIL_STATUS_PENDING)
    if status == EMAIL_STATUS_SENT:
        recipient = result.get("recipient") or "your inbox"
        return f"sent to {recipient}"
    if status == EMAIL_STATUS_FAILED:
        if result.get("domain_verification_required"):
            return (
                "could not send — verify your domain at resend.com/domains "
                "and update EMAIL_FROM in .env"
            )
        err = (result.get("message") or "").lower()
        if "resend_api_key" in err or ("empty" in err and "key" in err):
            return "email not configured — set RESEND_API_KEY in .env"
        return "could not send confirmation — tap Retry or contact support"
    return "sending confirmation"
