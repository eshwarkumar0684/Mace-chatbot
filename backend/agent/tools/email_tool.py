"""Email tool — delegates to email_service for Resend delivery."""

from backend.email_service import (
    build_confirmation_email,
    is_resend_configured,
    retry_confirmation_email,
    send_confirmation_email,
    send_otp_email,
    send_reset_email,
)

# Backward-compatible alias
is_smtp_configured = is_resend_configured

__all__ = [
    "build_confirmation_email",
    "is_resend_configured",
    "is_smtp_configured",
    "retry_confirmation_email",
    "send_confirmation_email",
    "send_otp_email",
    "send_reset_email",
]
