from kafkaf.core.config import settings
from kafkaf.core.db import connect as _connect_db
from contextlib import contextmanager

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _connect():
    with _connect_db(settings.db_path) as conn:
        yield conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(_SCHEMA)


def save_message(session_id: str, role: str, content: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_history(session_id: str, limit: int = 20) -> list[dict[str, str]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]
