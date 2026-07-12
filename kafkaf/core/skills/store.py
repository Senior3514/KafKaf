from contextlib import contextmanager

from kafkaf.core.config import settings
from kafkaf.core.db import connect as _connect_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    done INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _connect():
    with _connect_db(settings.db_path) as conn:
        yield conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def add_reminder(text: str) -> int:
    with _connect() as conn:
        cursor = conn.execute("INSERT INTO reminders (text) VALUES (?)", (text,))
        return cursor.lastrowid


def list_reminders(include_done: bool = False) -> list[dict]:
    query = "SELECT id, text, done FROM reminders"
    if not include_done:
        query += " WHERE done = 0"
    query += " ORDER BY id"
    with _connect() as conn:
        rows = conn.execute(query).fetchall()
    return [{"id": row[0], "text": row[1], "done": bool(row[2])} for row in rows]


def complete_reminder(reminder_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("UPDATE reminders SET done = 1 WHERE id = ?", (reminder_id,))
        return cursor.rowcount > 0
