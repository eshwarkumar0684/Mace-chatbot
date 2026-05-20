import json
import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from backend.config import settings
from backend.rag_pipeline import rag_pipeline
from backend.utils import logger

GUEST_USER_ID = "guest"


def _resolve_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    return url.replace("sqlite://", "", 1)


DB_PATH = _resolve_db_path()


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_guest_user(cursor) -> None:
    cursor.execute("SELECT id FROM users WHERE id = ?", (GUEST_USER_ID,))
    if cursor.fetchone():
        return
    cursor.execute(
        "INSERT INTO users (id, name, email, password_hash) VALUES (?, ?, ?, ?)",
        (GUEST_USER_ID, "Guest", "guest@mace.local", ""),
    )


def init_db():
    logger.info("Initializing database at: %s", DB_PATH)
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        sources TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        course_interest TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    _ensure_guest_user(cursor)
    conn.commit()
    conn.close()
    logger.info("Database schema successfully initialized.")


def create_conversation(title: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    conv_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
        (conv_id, GUEST_USER_ID, title),
    )
    conn.commit()
    conn.close()
    return {"id": conv_id, "title": title}


def list_conversations() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, created_at FROM conversations WHERE user_id = ? ORDER BY created_at DESC",
        (GUEST_USER_ID,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def conversation_exists(conversation_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,))
    found = cursor.fetchone() is not None
    conn.close()
    return found


def delete_conversation(conversation_id: str) -> bool:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    return rows_affected > 0


def add_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    sources_str = json.dumps(sources) if sources else None
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, sources) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, sources_str),
    )
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, sources, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC",
        (conversation_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        row_dict = dict(row)
        if row_dict["sources"]:
            row_dict["sources"] = json.loads(row_dict["sources"])
        history.append(row_dict)
    return history


def create_lead(name: str, email: str, phone: str, course_interest: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO leads (name, email, phone, course_interest) VALUES (?, ?, ?, ?)",
        (name, email, phone, course_interest),
    )
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": lead_id,
        "name": name,
        "email": email,
        "phone": phone,
        "course_interest": course_interest,
    }


def get_admin_analytics() -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM conversations")
    total_chats = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    total_messages = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM leads")
    total_leads = cursor.fetchone()[0]

    cursor.execute("SELECT course_interest, COUNT(*) as count FROM leads GROUP BY course_interest")
    leads_by_course = {row["course_interest"]: row["count"] for row in cursor.fetchall()}

    cursor.execute(
        "SELECT name, email, phone, course_interest, created_at FROM leads ORDER BY created_at DESC LIMIT 5"
    )
    recent_leads = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "stats": {
            "total_chats": total_chats,
            "total_messages": total_messages,
            "total_leads": total_leads,
        },
        "leads_by_course": leads_by_course,
        "recent_leads": recent_leads,
    }


def orchestrate_chat(conversation_id: str, question: str) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title FROM conversations WHERE id = ?",
        (conversation_id,),
    )
    conv = cursor.fetchone()
    conn.close()

    if not conv:
        raise ValueError("Conversation not found.")

    db_history = get_conversation_history(conversation_id)
    history_formatted = [{"role": msg["role"], "content": msg["content"]} for msg in db_history]

    result = rag_pipeline.generate_response(question, history_formatted)
    answer = result["response"]
    sources = result["sources"]

    add_message(conversation_id, "user", question)
    add_message(conversation_id, "assistant", answer, sources)

    if conv["title"] == "New Chat" and len(db_history) == 0:
        new_title = question[:30] + "..." if len(question) > 30 else question
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (new_title, conversation_id),
        )
        conn.commit()
        conn.close()

    return {"response": answer, "sources": sources}


init_db()
