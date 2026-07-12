"""A visible log of what KafKaf actually did — every chat turn, skill call,
and autopilot cycle — following the exact storage pattern of
`core/memory/store.py` and `core/skills/store.py`. Full autonomy is only
trustworthy if it's observable: this is what `GET /audit` and `kafkaf
audit` read from."""

from contextlib import contextmanager

from kafkaf.core.config import settings
from kafkaf.core.db import connect as _connect_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT,
    summary TEXT NOT NULL,
    duration_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""
MAX_SUMMARY_CHARS = 300


@contextmanager
def _connect():
    with _connect_db(settings.db_path) as conn:
        yield conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(_SCHEMA)


def log_event(
    event_type: str, actor: str | None, summary: str, duration_ms: int | None = None
) -> int:
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS] + "... [truncated]"
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO audit_log (event_type, actor, summary, duration_ms) VALUES (?, ?, ?, ?)",
            (event_type, actor, summary, duration_ms),
        )
        return cursor.lastrowid


def recent_events(limit: int = 50, event_type: str | None = None) -> list[dict]:
    query = "SELECT id, event_type, actor, summary, duration_ms, created_at FROM audit_log"
    params: list = []
    if event_type:
        query += " WHERE event_type = ?"
        params.append(event_type)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": row[0],
            "event_type": row[1],
            "actor": row[2],
            "summary": row[3],
            "duration_ms": row[4],
            "created_at": row[5],
        }
        for row in rows
    ]
