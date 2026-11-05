"""طبقة قاعدة البيانات (SQLite): المستخدمون، المحادثات، الرسائل، والتذاكر."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).with_name("tickets.db")

STATUS_AI = "مكتملة بالذكاء الاصطناعي"
STATUS_ESCALATED = "مصعدة لموظف بشري"
STATUS_PROGRESS = "قيد المعالجة"
STATUS_CLOSED = "مغلقة"
STATUSES = [STATUS_AI, STATUS_ESCALATED, STATUS_PROGRESS, STATUS_CLOSED]
DEPARTMENTS = ["دعم فني", "فواتير ومدفوعات", "الحساب والأمان", "استفسار عام", "شكوى"]
PRIORITIES = ["منخفضة", "متوسطة", "عالية"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_query TEXT, ai_response TEXT, department TEXT, priority TEXT,
    status TEXT DEFAULT 'مكتملة بالذكاء الاصطناعي'
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until REAL NOT NULL DEFAULT 0,
    created_at TEXT, last_login TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL, created_at TEXT, updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id, updated_at);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL, content TEXT NOT NULL,
    department TEXT, priority TEXT, ticket_id INTEGER,
    created_at TEXT, ts REAL
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        # ترقية قاعدة البيانات القديمة دون فقد أي بيانات
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(tickets)")}
        for col, ddl in (("created_at", "TEXT"), ("user_id", "INTEGER"), ("conversation_id", "INTEGER")):
            if col not in cols:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} {ddl}")


# ───────────────────────── المحادثات والرسائل ─────────────────────────
def create_conversation(user_id: int, title: str) -> int:
    t = now()
    with db() as c:
        return c.execute(
            "INSERT INTO conversations (user_id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (user_id, title, t, t),
        ).lastrowid


def list_conversations(user_id: int, limit: int = 50) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT id, title, updated_at FROM conversations WHERE user_id=? "
            "ORDER BY updated_at DESC, id DESC LIMIT ?", (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(user_id: int, conv_id: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id)).fetchone()
    return dict(row) if row else None


def delete_conversation(user_id: int, conv_id: int) -> None:
    with db() as c:
        c.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conv_id, user_id))


def delete_all_conversations(user_id: int) -> None:
    with db() as c:
        c.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))


def add_message(conv_id: int, role: str, content: str, department: str | None = None,
                priority: str | None = None, ticket_id: int | None = None) -> int:
    with db() as c:
        mid = c.execute(
            "INSERT INTO messages (conversation_id, role, content, department, priority, ticket_id, created_at, ts)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (conv_id, role, content, department, priority, ticket_id, now(), time.time()),
        ).lastrowid
        c.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now(), conv_id))
    return mid


def get_messages(conv_id: int) -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (conv_id,)).fetchall()
    return [
        {
            "id": r["id"], "role": r["role"], "content": r["content"], "ticket_id": r["ticket_id"],
            "created_at": r["created_at"],
            "meta": {"department": r["department"], "priority": r["priority"]} if r["role"] == "assistant" else None,
        }
        for r in rows
    ]


def delete_message(msg_id: int) -> None:
    with db() as c:
        c.execute("DELETE FROM messages WHERE id=?", (msg_id,))


def count_recent_user_messages(user_id: int, seconds: int) -> int:
    with db() as c:
        return c.execute(
            "SELECT COUNT(*) FROM messages m JOIN conversations v ON v.id = m.conversation_id "
            "WHERE v.user_id=? AND m.role='user' AND m.ts>?", (user_id, time.time() - seconds),
        ).fetchone()[0]


# ───────────────────────── التذاكر ─────────────────────────
def save_ticket(user_id: int, conv_id: int, query: str, reply: str, dept: str, priority: str, status: str) -> int:
    with db() as c:
        return c.execute(
            "INSERT INTO tickets (user_query, ai_response, department, priority, status, created_at, user_id, conversation_id)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (query, reply, dept, priority, status, now(), user_id, conv_id),
        ).lastrowid


def get_ticket_status(ticket_id: int) -> str | None:
    with db() as c:
        row = c.execute("SELECT status FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    return row["status"] if row else None


def escalate_ticket(ticket_id: int, user_id: int) -> None:
    with db() as c:
        c.execute(
            "UPDATE tickets SET status=?, priority='عالية' WHERE id=? AND user_id=?",
            (STATUS_ESCALATED, ticket_id, user_id),
        )


# ───────────────────────── الإدارة ─────────────────────────
def all_tickets(limit: int = 5000) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT t.id, t.created_at, COALESCE(u.email, '—') AS user_email, t.department, t.priority, "
            "t.status, t.user_query, t.ai_response FROM tickets t LEFT JOIN users u ON u.id = t.user_id "
            "ORDER BY t.id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_ticket_status(ticket_id: int, status: str) -> None:
    if status not in STATUSES:
        raise ValueError("حالة غير صالحة")
    with db() as c:
        c.execute("UPDATE tickets SET status=? WHERE id=?", (status, ticket_id))


def overview_stats() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    with db() as c:
        one = lambda sql, *a: c.execute(sql, a).fetchone()[0]  # noqa: E731
        return {
            "users": one("SELECT COUNT(*) FROM users WHERE role='user'"),
            "conversations": one("SELECT COUNT(*) FROM conversations"),
            "tickets": one("SELECT COUNT(*) FROM tickets"),
            "today": one("SELECT COUNT(*) FROM tickets WHERE substr(created_at,1,10)=?", today),
            "escalated": one("SELECT COUNT(*) FROM tickets WHERE status=?", STATUS_ESCALATED),
            "closed": one("SELECT COUNT(*) FROM tickets WHERE status=?", STATUS_CLOSED),
        }


def count_by(column: str) -> dict[str, int]:
    if column not in {"department", "priority", "status"}:
        raise ValueError(column)
    with db() as c:
        rows = c.execute(f"SELECT {column} AS k, COUNT(*) AS n FROM tickets GROUP BY {column}").fetchall()
    return {r["k"] or "—": r["n"] for r in rows}


def tickets_per_day(days: int = 14) -> dict[str, int]:
    with db() as c:
        rows = c.execute(
            "SELECT substr(created_at,1,10) AS d, COUNT(*) AS n FROM tickets "
            "WHERE created_at IS NOT NULL GROUP BY d ORDER BY d DESC LIMIT ?", (days,),
        ).fetchall()
    return {r["d"]: r["n"] for r in rows}


def admin_conversations(limit: int = 500) -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT v.id, v.title, v.updated_at, u.email, u.name, "
            "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id = v.id) AS messages "
            "FROM conversations v JOIN users u ON u.id = v.user_id "
            "ORDER BY v.updated_at DESC, v.id DESC LIMIT ?", (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def all_users() -> list[dict]:
    with db() as c:
        rows = c.execute(
            "SELECT u.id, u.name, u.email, u.role, u.is_active, u.created_at, u.last_login, "
            "(SELECT COUNT(*) FROM conversations v WHERE v.user_id = u.id) AS conversations "
            "FROM users u ORDER BY u.id"
        ).fetchall()
    return [dict(r) for r in rows]