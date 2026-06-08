"""Temporary slot locking — AVAILABLE / LOCKED / BOOKED with 5-minute holds."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.chatbot import get_db_connection
from backend.utils import logger

LOCK_DURATION_MINUTES = 5

STATUS_AVAILABLE = "AVAILABLE"
STATUS_LOCKED = "LOCKED"
STATUS_BOOKED = "BOOKED"


def _now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _expires_at_iso() -> str:
    return (datetime.now() + timedelta(minutes=LOCK_DURATION_MINUTES)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def init_slot_registry_table() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS demo_slot_registry (
        slot_datetime TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'AVAILABLE',
        locked_by TEXT,
        lock_expires_at TEXT,
        booking_id INTEGER,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_slot_registry_status
    ON demo_slot_registry(status)
    """)
    conn.commit()
    conn.close()


def sync_booked_slots_from_bookings() -> None:
    """Ensure confirmed bookings are reflected as BOOKED in the registry."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT slot_datetime, id FROM demo_bookings
        WHERE status IN ('confirmed', 'pending')
    """)
    for row in cursor.fetchall():
        cursor.execute(
            """
            INSERT INTO demo_slot_registry (slot_datetime, status, booking_id, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(slot_datetime) DO UPDATE SET
                status = excluded.status,
                booking_id = excluded.booking_id,
                locked_by = NULL,
                lock_expires_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            """,
            (row["slot_datetime"], STATUS_BOOKED, row["id"]),
        )
    conn.commit()
    conn.close()


def cleanup_expired_locks() -> int:
    """Release LOCKED slots whose lock_expires_at has passed. Returns count released."""
    now = _now_iso()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE demo_slot_registry
        SET status = ?, locked_by = NULL, lock_expires_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE status = ? AND lock_expires_at IS NOT NULL AND lock_expires_at < ?
        """,
        (STATUS_AVAILABLE, STATUS_LOCKED, now),
    )
    released = cursor.rowcount
    conn.commit()
    conn.close()
    if released:
        logger.info("Released %d expired demo slot lock(s)", released)
    return released


def get_slot_record(slot_datetime: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM demo_slot_registry WHERE slot_datetime = ?",
        (slot_datetime,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def _is_lock_active(record: Dict[str, Any], now: Optional[str] = None) -> bool:
    if record.get("status") != STATUS_LOCKED:
        return False
    expires = record.get("lock_expires_at")
    if not expires:
        return False
    now = now or _now_iso()
    return expires >= now


def is_slot_selectable(slot_datetime: str, conversation_id: Optional[str] = None) -> bool:
    cleanup_expired_locks()
    record = get_slot_record(slot_datetime)
    if not record:
        return True
    if record["status"] == STATUS_BOOKED:
        return False
    if record["status"] == STATUS_AVAILABLE:
        return True
    if record["status"] == STATUS_LOCKED:
        if conversation_id and record.get("locked_by") == conversation_id:
            return _is_lock_active(record)
        return not _is_lock_active(record)
    return False


def is_slot_blocked(slot_datetime: str, conversation_id: Optional[str] = None) -> bool:
    return not is_slot_selectable(slot_datetime, conversation_id)


def lock_slot(slot_datetime: str, conversation_id: str) -> Dict[str, Any]:
    """Lock a slot for conversation_id. Returns {ok, message, lock_expires_at}."""
    cleanup_expired_locks()
    conn = get_db_connection()
    cursor = conn.cursor()
    expires = _expires_at_iso()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        cursor.execute(
            "SELECT * FROM demo_slot_registry WHERE slot_datetime = ?",
            (slot_datetime,),
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                """
                INSERT INTO demo_slot_registry
                (slot_datetime, status, locked_by, lock_expires_at, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (slot_datetime, STATUS_LOCKED, conversation_id, expires),
            )
            conn.commit()
            return {
                "ok": True,
                "message": "Slot held for you for 5 minutes.",
                "lock_expires_at": expires,
                "status": STATUS_LOCKED,
            }

        record = dict(row)
        if record["status"] == STATUS_BOOKED:
            conn.rollback()
            return {
                "ok": False,
                "code": "slot_booked",
                "message": "This slot is already booked. Please choose another time.",
            }

        if record["status"] == STATUS_LOCKED:
            if record.get("locked_by") == conversation_id and _is_lock_active(record):
                cursor.execute(
                    """
                    UPDATE demo_slot_registry
                    SET lock_expires_at = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE slot_datetime = ?
                    """,
                    (expires, slot_datetime),
                )
                conn.commit()
                return {
                    "ok": True,
                    "message": "Slot hold extended for 5 minutes.",
                    "lock_expires_at": expires,
                    "status": STATUS_LOCKED,
                }
            if _is_lock_active(record):
                conn.rollback()
                return {
                    "ok": False,
                    "code": "slot_locked",
                    "message": (
                        "Someone else is booking this slot right now. "
                        "Please pick a different time — holds expire in a few minutes."
                    ),
                }
            # expired lock — take over below

        cursor.execute(
            """
            UPDATE demo_slot_registry
            SET status = ?, locked_by = ?, lock_expires_at = ?,
                booking_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE slot_datetime = ?
            """,
            (STATUS_LOCKED, conversation_id, expires, slot_datetime),
        )
        conn.commit()
        return {
            "ok": True,
            "message": "Slot held for you for 5 minutes.",
            "lock_expires_at": expires,
            "status": STATUS_LOCKED,
        }
    except Exception as exc:
        conn.rollback()
        logger.error("lock_slot failed: %s", exc, exc_info=True)
        return {"ok": False, "code": "lock_failed", "message": "Could not lock slot. Try again."}
    finally:
        conn.close()


def release_slot(slot_datetime: str, conversation_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE demo_slot_registry
        SET status = ?, locked_by = NULL, lock_expires_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE slot_datetime = ? AND status = ? AND locked_by = ?
        """,
        (STATUS_AVAILABLE, slot_datetime, STATUS_LOCKED, conversation_id),
    )
    released = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return released


def release_all_locks_for(conversation_id: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE demo_slot_registry
        SET status = ?, locked_by = NULL, lock_expires_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE status = ? AND locked_by = ?
        """,
        (STATUS_AVAILABLE, STATUS_LOCKED, conversation_id),
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def verify_lock_for_booking(slot_datetime: str, conversation_id: str) -> Dict[str, Any]:
    cleanup_expired_locks()
    record = get_slot_record(slot_datetime)
    if not record:
        return {"ok": False, "code": "no_lock", "message": "Please select a slot first — it was not held for you."}
    if record["status"] == STATUS_BOOKED:
        return {"ok": False, "code": "slot_booked", "message": "This slot is already booked."}
    if record["status"] != STATUS_LOCKED or record.get("locked_by") != conversation_id:
        return {
            "ok": False,
            "code": "no_lock",
            "message": (
                "Your hold on this slot expired or was taken. "
                "Select a time again — we reserve it for 5 minutes while you confirm."
            ),
        }
    if not _is_lock_active(record):
        release_slot(slot_datetime, conversation_id)
        return {
            "ok": False,
            "code": "lock_expired",
            "message": "Your 5-minute hold expired. Please select the slot again and confirm promptly.",
        }
    return {"ok": True, "lock_expires_at": record.get("lock_expires_at")}


def mark_slot_booked(slot_datetime: str, conversation_id: str, booking_id: int) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO demo_slot_registry
        (slot_datetime, status, locked_by, lock_expires_at, booking_id, updated_at)
        VALUES (?, ?, NULL, NULL, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(slot_datetime) DO UPDATE SET
            status = excluded.status,
            locked_by = NULL,
            lock_expires_at = NULL,
            booking_id = excluded.booking_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (slot_datetime, STATUS_BOOKED, booking_id),
    )
    conn.commit()
    conn.close()


def rollback_slot_to_available(slot_datetime: str) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE demo_slot_registry
        SET status = ?, locked_by = NULL, lock_expires_at = NULL,
            booking_id = NULL, updated_at = CURRENT_TIMESTAMP
        WHERE slot_datetime = ? AND status != ?
        """,
        (STATUS_AVAILABLE, slot_datetime, STATUS_BOOKED),
    )
    conn.commit()
    conn.close()


def list_slot_statuses(conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
    cleanup_expired_locks()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM demo_slot_registry ORDER BY slot_datetime")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    result = []
    for r in rows:
        status = r["status"]
        if status == STATUS_LOCKED and not _is_lock_active(r):
            status = STATUS_AVAILABLE
        result.append(
            {
                "slot_datetime": r["slot_datetime"],
                "status": status,
                "locked_by_you": conversation_id
                and r.get("locked_by") == conversation_id
                and status == STATUS_LOCKED,
            }
        )
    return result
