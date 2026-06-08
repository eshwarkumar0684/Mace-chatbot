"""Demo booking workflow — date-only, no slot locks."""

from typing import Any, Dict

from backend.agent.email_service import (
    EMAIL_STATUS_FAILED,
    EMAIL_STATUS_SENT,
    email_delivery_summary,
    get_latest_email_log_for_booking,
    send_confirmation_email,
)
from backend.agent.memory import (
    find_booking_by_email_and_date,
    find_confirmed_booking,
    get_booking,
    reserve_booking,
    set_memory,
    update_booking,
)
from backend.agent.slots import (
    format_date_display,
    normalize_demo_date,
    pick_alternative_dates,
)
from backend.chatbot import create_lead
from backend.utils import logger


def _duplicate_message(demo_date: str, email: str) -> Dict[str, Any]:
    display = format_date_display(demo_date)
    alternatives = pick_alternative_dates(exclude=demo_date)
    alt_lines = "\n".join(f"- {format_date_display(d)}" for d in alternatives[:5])
    msg = (
        f"You already have a demo booked for **{display}** with **{email}**.\n\n"
        f"Please choose a different date."
    )
    if alt_lines:
        msg += f"\n\n**Other available dates:**\n{alt_lines}"
    return {
        "ok": False,
        "code": "duplicate_booking",
        "message": msg,
        "alternatives": alternatives,
    }


def _success_message(
    name: str,
    course_interest: str,
    demo_date: str,
    email_result: Dict[str, Any],
    booking_id: int,
) -> str:
    display = format_date_display(demo_date)
    email_line = email_delivery_summary(email_result)
    lines = [
        "Your demo is confirmed!",
        "",
        f"Name: {name}",
        f"Course: {course_interest}",
        f"Date: {display}",
        f"Reference: #{booking_id}",
    ]
    if email_result.get("status") != EMAIL_STATUS_SENT:
        lines.extend(["", f"Email confirmation: {email_line}"])
    return "\n".join(lines)


def _existing_booking_message(booking: Dict[str, Any], email_result: Dict[str, Any]) -> str:
    display = format_date_display(booking["slot_datetime"])
    email_line = email_delivery_summary(email_result)
    return (
        f"You already have a demo booked for **{display}**.\n\n"
        f"- **Course:** {booking['course_interest']}\n"
        f"- **Email confirmation:** {email_line}\n"
        f"- **Reference:** #{booking['id']}"
    )


def _dispatch_confirmation_email(
    booking_id: int,
    email: str,
    name: str,
    demo_date: str,
    course_interest: str,
) -> Dict[str, Any]:
    logger.info(
        "Sending confirmation email booking=%s recipient=%s date=%s",
        booking_id,
        email,
        demo_date,
    )
    try:
        result = send_confirmation_email(
            booking_id=booking_id,
            recipient=email,
            name=name,
            demo_date=demo_date,
            course_interest=course_interest,
        )
        logger.info(
            "Email result booking=%s status=%s log=%s ok=%s",
            booking_id,
            result.get("status"),
            result.get("log_id"),
            result.get("ok"),
        )
        return result
    except Exception as exc:
        logger.error(
            "Unexpected email error booking=%s recipient=%s: %s",
            booking_id,
            email,
            exc,
            exc_info=True,
        )
        return {
            "ok": False,
            "status": EMAIL_STATUS_FAILED,
            "log_id": None,
            "message": str(exc),
            "recipient": email,
        }


def _email_status_for_booking(booking_id: int) -> str:
    log = get_latest_email_log_for_booking(booking_id)
    if not log:
        return EMAIL_STATUS_FAILED
    return log.get("status") or EMAIL_STATUS_FAILED


def execute_demo_booking(
    conversation_id: str,
    name: str,
    email: str,
    phone: str,
    course_interest: str,
    demo_date: str,
    slot_datetime: str | None = None,
) -> Dict[str, Any]:
    """Book a demo for a single date (YYYY-MM-DD). slot_datetime accepted as legacy alias."""
    raw_date = demo_date or slot_datetime or ""
    date = normalize_demo_date(raw_date)

    existing = find_confirmed_booking(conversation_id, date)
    if existing:
        email_status = _email_status_for_booking(existing["id"])
        latest_log = get_latest_email_log_for_booking(existing["id"])
        email_result = {
            "status": email_status,
            "recipient": existing["email"],
            "ok": email_status == EMAIL_STATUS_SENT,
        }
        if email_status != EMAIL_STATUS_SENT:
            email_result = _dispatch_confirmation_email(
                booking_id=existing["id"],
                email=existing["email"],
                name=existing["name"],
                demo_date=existing["slot_datetime"],
                course_interest=existing["course_interest"],
            )
            email_status = email_result.get("status", email_status)
        return {
            "ok": True,
            "message": _existing_booking_message(existing, email_result),
            "booking_id": existing["id"],
            "email_status": email_status,
            "email_log_id": latest_log.get("id") if latest_log else None,
            "email_delivery": {
                "status": email_status,
                "recipient": existing["email"],
                "pending": email_status != EMAIL_STATUS_SENT,
                "message": email_result.get("message"),
            },
        }

    duplicate = find_booking_by_email_and_date(email, date)
    if duplicate:
        return _duplicate_message(date, email)

    booking_id = reserve_booking(
        conversation_id, name, email, phone, course_interest, date
    )
    if booking_id is None:
        return _duplicate_message(date, email)

    update_booking(booking_id, status="confirmed")

    try:
        lead = create_lead(name, email, phone, course_interest)
        update_booking(booking_id, crm_lead_id=lead["id"])
    except Exception as exc:
        logger.warning("CRM save failed for booking %s: %s", booking_id, exc)

    booking = get_booking(booking_id) or {}
    recipient = booking.get("email") or email
    email_result = _dispatch_confirmation_email(
        booking_id=booking_id,
        email=recipient,
        name=name,
        demo_date=date,
        course_interest=course_interest,
    )
    email_status = email_result.get("status", EMAIL_STATUS_FAILED)

    booking_state = {
        "status": "confirmed",
        "date": date,
        "booking_id": booking_id,
        "email_status": email_status,
    }
    set_memory(conversation_id, "name", name)
    set_memory(conversation_id, "email", email)
    set_memory(conversation_id, "phone", phone)
    set_memory(conversation_id, "course_interest", course_interest)
    set_memory(conversation_id, "booking_state", booking_state)

    return {
        "ok": True,
        "message": _success_message(
            name, course_interest, date, email_result, booking_id
        ),
        "booking_id": booking_id,
        "email_status": email_status,
        "email_log_id": email_result.get("log_id"),
        "email_delivery": {
            "status": email_status,
            "recipient": email_result.get("recipient", recipient),
            "pending": email_status != EMAIL_STATUS_SENT,
            "resend_id": email_result.get("resend_id"),
            "domain_verification_required": email_result.get("domain_verification_required", False),
            "message": email_result.get("message"),
        },
    }
