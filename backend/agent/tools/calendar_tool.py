import uuid
from typing import Optional

from backend.agent.tools.base import with_retry
from backend.config import settings
from backend.utils import logger


@with_retry(max_attempts=2, delay_seconds=1.0)
def create_calendar_event(
    title: str,
    start_datetime: str,
    attendee_email: str,
    duration_minutes: int = 45,
) -> dict:
    """
    Create a Google Calendar event with Meet link.
    Uses Google Calendar API when configured; otherwise simulates locally.
    """
    if settings.GOOGLE_CALENDAR_ENABLED and settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        try:
            return _create_google_event(title, start_datetime, attendee_email, duration_minutes)
        except Exception as exc:
            logger.error("Google Calendar failed: %s", exc)
            raise

    event_id = f"sim-{uuid.uuid4().hex[:12]}"
    meet_link = f"https://meet.google.com/mace-{uuid.uuid4().hex[:3]}-{uuid.uuid4().hex[:4]}"
    logger.info(
        "Simulated calendar event %s for %s at %s",
        event_id,
        attendee_email,
        start_datetime,
    )
    return {
        "event_id": event_id,
        "meet_link": meet_link,
        "title": title,
        "start": start_datetime,
        "mode": "simulation",
    }


def _create_google_event(
    title: str,
    start_datetime: str,
    attendee_email: str,
    duration_minutes: int,
) -> dict:
    """Google Calendar integration stub — extend with google-api-python-client."""
    raise NotImplementedError(
        "Configure GOOGLE_SERVICE_ACCOUNT_JSON and install google-api-python-client for live calendar."
    )


def delete_calendar_event(event_id: str) -> None:
    if event_id.startswith("sim-"):
        logger.info("Simulated calendar delete: %s", event_id)
        return
    if settings.GOOGLE_CALENDAR_ENABLED:
        logger.info("Would delete Google event: %s", event_id)
