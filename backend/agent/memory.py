import json
from typing import Any, Dict, List, Optional

from backend.chatbot import get_db_connection
from backend.utils import logger


def init_agent_tables() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS agent_memory (
        conversation_id TEXT NOT NULL,
        memory_key TEXT NOT NULL,
        memory_value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (conversation_id, memory_key)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS demo_bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        course_interest TEXT NOT NULL,
        slot_datetime TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        calendar_event_id TEXT,
        meet_link TEXT,
        crm_lead_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS email_outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER DEFAULT 0,
        last_error TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

    from backend.email_service import init_email_logs_table

    init_email_logs_table()
    logger.info("Agent memory tables initialized.")


def get_memory(conversation_id: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT memory_key, memory_value FROM agent_memory WHERE conversation_id = ?",
        (conversation_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    profile: Dict[str, Any] = {
        "name": None,
        "email": None,
        "phone": None,
        "course_interest": None,
    }
    booking_state: Dict[str, Any] = {
        "status": "idle",
        "date": None,
        "booking_id": None,
    }

    for row in rows:
        key = row["memory_key"]
        try:
            value = json.loads(row["memory_value"])
        except (json.JSONDecodeError, TypeError):
            value = row["memory_value"]
        if key in profile:
            profile[key] = value
        elif key == "booking_state":
            booking_state = value if isinstance(value, dict) else booking_state

    return {"user_profile": profile, "booking_state": booking_state}


def set_memory(conversation_id: str, key: str, value: Any) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO agent_memory (conversation_id, memory_key, memory_value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(conversation_id, memory_key) DO UPDATE SET
            memory_value = excluded.memory_value,
            updated_at = CURRENT_TIMESTAMP
        """,
        (conversation_id, key, json.dumps(value)),
    )
    conn.commit()
    conn.close()


def save_memory_snapshot(
    conversation_id: str,
    user_profile: Dict[str, Any],
    booking_state: Dict[str, Any],
) -> None:
    for key in ("name", "email", "phone", "course_interest"):
        if user_profile.get(key):
            set_memory(conversation_id, key, user_profile[key])
    set_memory(conversation_id, "booking_state", booking_state)


def get_booking(booking_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM demo_bookings WHERE id = ?", (booking_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_booking(
    conversation_id: str,
    name: str,
    email: str,
    phone: str,
    course_interest: str,
    slot_datetime: str,
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO demo_bookings
        (conversation_id, name, email, phone, course_interest, slot_datetime, status)
        VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (conversation_id, name, email, phone, course_interest, slot_datetime),
    )
    booking_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return booking_id


def update_booking(booking_id: int, **fields: Any) -> None:
    if not fields:
        return
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [booking_id]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE demo_bookings SET {columns} WHERE id = ?", values)
    conn.commit()
    conn.close()


def cancel_booking(booking_id: int) -> None:
    update_booking(booking_id, status="cancelled")


def find_confirmed_booking(conversation_id: str, demo_date: str) -> Optional[Dict[str, Any]]:
    from backend.agent.slots import normalize_demo_date

    normalized = normalize_demo_date(demo_date)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM demo_bookings
        WHERE conversation_id = ? AND slot_datetime = ? AND status = 'confirmed'
        ORDER BY id DESC LIMIT 1
        """,
        (conversation_id, normalized),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def find_booking_by_email_and_date(email: str, demo_date: str) -> Optional[Dict[str, Any]]:
    from backend.agent.slots import normalize_demo_date

    normalized = normalize_demo_date(demo_date)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM demo_bookings
        WHERE LOWER(email) = LOWER(?) AND slot_datetime = ?
          AND status IN ('pending', 'confirmed')
        ORDER BY id DESC LIMIT 1
        """,
        (email.strip(), normalized),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def reserve_booking(
    conversation_id: str,
    name: str,
    email: str,
    phone: str,
    course_interest: str,
    demo_date: str,
) -> Optional[int]:
    """Create a pending booking; returns None if this email already booked that date."""
    from backend.agent.slots import normalize_demo_date

    normalized = normalize_demo_date(demo_date)
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")

        cursor.execute(
            """
            SELECT 1 FROM demo_bookings
            WHERE LOWER(email) = LOWER(?) AND slot_datetime = ?
              AND status IN ('pending', 'confirmed')
            """,
            (email.strip(), normalized),
        )
        if cursor.fetchone():
            conn.rollback()
            return None

        cursor.execute(
            """
            INSERT INTO demo_bookings
            (conversation_id, name, email, phone, course_interest, slot_datetime, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (conversation_id, name, email, phone, course_interest, normalized),
        )
        booking_id = cursor.lastrowid
        conn.commit()
        return booking_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_bookings_for_conversation(conversation_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM demo_bookings WHERE conversation_id = ? ORDER BY created_at DESC",
        (conversation_id,),
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows
