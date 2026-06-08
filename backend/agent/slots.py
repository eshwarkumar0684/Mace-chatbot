"""Demo date generation and formatting (date-only booking)."""

from datetime import datetime, timedelta
from typing import List, Optional


def normalize_demo_date(value: str) -> str:
    """Normalize to YYYY-MM-DD."""
    raw = (value or "").strip().replace("T", " ").split(" ")[0]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


# Backward-compatible alias used by DB column slot_datetime
normalize_slot_datetime = normalize_demo_date


def format_date_display(demo_date: str) -> str:
    """e.g. Tue, 09 Jun 2026"""
    try:
        dt = datetime.strptime(normalize_demo_date(demo_date), "%Y-%m-%d")
        return dt.strftime("%a, %d %b %Y")
    except ValueError:
        return demo_date


format_slot_display = format_date_display


def generate_available_dates(
    days_ahead: int = 21,
    max_dates: int = 20,
) -> List[str]:
    """Return upcoming weekday dates (YYYY-MM-DD), excluding past/today."""
    dates: List[str] = []
    now = datetime.now()
    for day_offset in range(1, days_ahead + 1):
        day = now + timedelta(days=day_offset)
        if day.weekday() >= 5:
            continue
        dates.append(day.strftime("%Y-%m-%d"))
        if len(dates) >= max_dates:
            break
    return dates


def generate_available_slots(**kwargs) -> List[str]:
    """Alias for legacy callers — returns dates only."""
    return generate_available_dates(**kwargs)


def pick_alternative_dates(
    exclude: Optional[str] = None,
    count: int = 5,
) -> List[str]:
    exclude_norm = normalize_demo_date(exclude) if exclude else None
    alts = [d for d in generate_available_dates() if d != exclude_norm]
    return alts[:count]


pick_alternative_slots = pick_alternative_dates


def build_date_options(dates: Optional[List[str]] = None) -> List[dict]:
    items = dates if dates is not None else generate_available_dates()
    return [{"value": d, "label": format_date_display(d)} for d in items]
