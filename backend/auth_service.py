"""Authentication helpers — OTP generation/verification and password reset tokens."""

from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from backend.chatbot import get_db_connection
from backend.email_service import (
    RESET_LINK_EXPIRY_MINUTES,
    send_otp_email,
    send_reset_email,
)
from backend.utils import logger

OTP_EXPIRY_MINUTES = 5
OTP_LENGTH = 6


def init_auth_tables() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auth_otps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        otp_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        verified INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auth_reset_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_auth_otps_email ON auth_otps(email)
    """)
    conn.commit()
    conn.close()


def generate_otp(length: int = OTP_LENGTH) -> str:
    """Generate numeric OTP — unchanged generation logic, separate from email delivery."""
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _expires_at_iso(minutes: int) -> str:
    return (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")


def request_otp(email: str) -> Dict[str, Any]:
    """Generate OTP, store hash, send via Resend."""
    email = email.strip().lower()
    otp = generate_otp()
    otp_hash = _hash_value(otp)
    expires = _expires_at_iso(OTP_EXPIRY_MINUTES)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO auth_otps (email, otp_hash, expires_at)
        VALUES (?, ?, ?)
        """,
        (email, otp_hash, expires),
    )
    conn.commit()
    conn.close()

    logger.info("OTP generated for %s (expires %s)", email, expires)
    email_result = send_otp_email(email, otp)
    return {
        "ok": email_result.get("ok", False),
        "message": "Verification code sent." if email_result.get("ok") else email_result.get("message"),
        "email_status": email_result.get("status"),
        "email_log_id": email_result.get("log_id"),
    }


def verify_otp(email: str, otp: str) -> Dict[str, Any]:
    email = email.strip().lower()
    otp_hash = _hash_value(otp.strip())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM auth_otps
        WHERE email = ? AND otp_hash = ? AND verified = 0 AND expires_at >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (email, otp_hash, now),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "message": "Invalid or expired verification code."}

    cursor.execute("UPDATE auth_otps SET verified = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Email verified successfully."}


def request_password_reset(email: str, base_url: str = "http://localhost:3000") -> Dict[str, Any]:
    """Generate reset token and send reset link email."""
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    token_hash = _hash_value(token)
    expires = _expires_at_iso(RESET_LINK_EXPIRY_MINUTES)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO auth_reset_tokens (email, token_hash, expires_at)
        VALUES (?, ?, ?)
        """,
        (email, token_hash, expires),
    )
    conn.commit()
    conn.close()

    reset_link = f"{base_url.rstrip('/')}/reset-password?token={token}&email={email}"
    logger.info("Password reset token generated for %s", email)
    email_result = send_reset_email(email, reset_link)
    return {
        "ok": email_result.get("ok", False),
        "message": "Password reset link sent." if email_result.get("ok") else email_result.get("message"),
        "email_status": email_result.get("status"),
        "email_log_id": email_result.get("log_id"),
    }


def validate_reset_token(email: str, token: str) -> bool:
    email = email.strip().lower()
    token_hash = _hash_value(token.strip())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM auth_reset_tokens
        WHERE email = ? AND token_hash = ? AND used = 0 AND expires_at >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (email, token_hash, now),
    )
    row = cursor.fetchone()
    conn.close()
    return row is not None


def consume_reset_token(email: str, token: str) -> bool:
    email = email.strip().lower()
    token_hash = _hash_value(token.strip())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id FROM auth_reset_tokens
        WHERE email = ? AND token_hash = ? AND used = 0 AND expires_at >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (email, token_hash, now),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    cursor.execute("UPDATE auth_reset_tokens SET used = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return True
