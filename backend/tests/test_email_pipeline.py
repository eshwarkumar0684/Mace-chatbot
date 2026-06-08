"""Email pipeline tests — Resend production delivery."""

from unittest.mock import patch

from backend.email_service import (
    EMAIL_STATUS_FAILED,
    EMAIL_STATUS_SENT,
    build_confirmation_email,
    get_latest_email_log_for_booking,
    init_email_logs_table,
    is_test_sender,
    list_email_logs,
    retry_confirmation_email,
    send_confirmation_email,
    send_otp_email,
    send_reset_email,
)
from backend.auth_service import generate_otp, init_auth_tables, request_otp, verify_otp
from backend.agent.memory import get_booking, init_agent_tables, update_booking
from backend.agent.slots import generate_available_dates
from backend import chatbot


def _setup():
    init_agent_tables()
    init_email_logs_table()
    init_auth_tables()


def test_confirmation_template_includes_all_fields():
    subject, html, text = build_confirmation_email(
        name="Priya",
        email="priya@example.com",
        demo_date="2026-06-10",
        course_interest="AI & ML",
        booking_id=42,
    )
    assert "Priya" in text and "priya@example.com" in text
    assert "AI & ML" in text and "10 Jun 2026" in text
    assert "meet.google.com" not in text
    assert "#42" in text and "#42" in html
    assert "Date:" in text
    print("PASS template fields")


def test_send_confirmation_without_key_returns_failed():
    _setup()
    with patch("backend.email_service.settings") as mock_settings:
        mock_settings.RESEND_API_KEY = ""
        mock_settings.EMAIL_FROM = "noreply@example.com"
        result = send_confirmation_email(
            booking_id=99,
            recipient="student@example.com",
            name="Test Student",
            demo_date="2026-06-01",
            course_interest="AI & ML",
        )
    assert result["ok"] is False
    assert result["status"] == EMAIL_STATUS_FAILED
    print("PASS missing key")


def test_send_confirmation_to_student_email():
    _setup()
    with patch("backend.email_service.is_test_sender", return_value=False), patch(
        "backend.email_service._send_via_resend_with_retry",
        return_value=({"resend_id": "test-1", "provider_response": "resend_id=test-1", "full_response": {"id": "test-1"}, "delivery_status": "sent"}, 1),
    ) as send_mock:
        result = send_confirmation_email(
            booking_id=99,
            recipient="student@example.com",
            name="Test Student",
            demo_date="2026-06-01",
            course_interest="AI & ML",
        )
    assert result["ok"] is True
    assert result["status"] == EMAIL_STATUS_SENT
    assert result["recipient"] == "student@example.com"
    send_mock.assert_called_once()
    assert send_mock.call_args[0][0] == "student@example.com"
    log = get_latest_email_log_for_booking(99)
    assert log["recipient"] == "student@example.com"
    print("PASS sends to student email")


def test_test_sender_blocks_student_delivery():
    _setup()
    with patch("backend.email_service.is_test_sender", return_value=True):
        result = send_confirmation_email(
            booking_id=100,
            recipient="student@example.com",
            name="Test",
            demo_date="2026-06-01",
            course_interest="AI",
        )
    assert result["ok"] is False
    assert result.get("domain_verification_required") is True
    print("PASS test sender blocked")


def test_booking_succeeds_when_resend_fails():
    _setup()
    dates = generate_available_dates()
    date = dates[0]
    conv = chatbot.create_conversation("Email fail test")["id"]

    from backend.agent.booking_workflow import execute_demo_booking

    with patch("backend.email_service.is_test_sender", return_value=False), patch(
        "backend.email_service._send_via_resend_with_retry",
        side_effect=RuntimeError("Resend API down"),
    ):
        result = execute_demo_booking(
            conversation_id=conv,
            name="Fail Test",
            email="fail@example.com",
            phone="9999999999",
            course_interest="Data Science",
            demo_date=date,
        )

    assert result["ok"] is True
    assert result["email_status"] == EMAIL_STATUS_FAILED
    assert get_booking(result["booking_id"])["status"] == "confirmed"
    print("PASS booking survives email failure")


def test_retry_email():
    _setup()
    conv = chatbot.create_conversation("Retry test")["id"]
    dates = generate_available_dates()
    date = dates[0]

    from backend.agent.memory import reserve_booking

    booking_id = reserve_booking(
        conv, "Retry User", "retry@example.com", "8888888888", "General inquiry", date
    )
    update_booking(booking_id, status="confirmed")

    with patch("backend.email_service.is_test_sender", return_value=False), patch(
        "backend.email_service._send_via_resend_with_retry",
        return_value=({"resend_id": "test-123", "provider_response": "resend_id=test-123", "full_response": {"id": "test-123"}, "delivery_status": "sent"}, 1),
    ):
        result = retry_confirmation_email(booking_id)

    assert result["ok"] is True
    assert result["recipient"] == "retry@example.com"
    print("PASS retry")


if __name__ == "__main__":
    test_confirmation_template_includes_all_fields()
    test_send_confirmation_without_key_returns_failed()
    test_send_confirmation_to_student_email()
    test_test_sender_blocks_student_delivery()
    test_booking_succeeds_when_resend_fails()
    test_retry_email()
    print("All email pipeline tests passed.")
