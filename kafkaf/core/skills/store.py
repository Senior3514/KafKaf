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

CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    skill_arg TEXT NOT NULL DEFAULT '',
    run_at TEXT NOT NULL,          -- ISO-8601 UTC; sorts and compares as a plain string
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


def add_schedule(skill_name: str, skill_arg: str, run_at: str) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO schedules (skill_name, skill_arg, run_at) VALUES (?, ?, ?)",
            (skill_name, skill_arg, run_at),
        )
        return cursor.lastrowid


def list_schedules(include_done: bool = False) -> list[dict]:
    query = "SELECT id, skill_name, skill_arg, run_at, done FROM schedules"
    if not include_done:
        query += " WHERE done = 0"
    query += " ORDER BY run_at, id"
    with _connect() as conn:
        rows = conn.execute(query).fetchall()
    return [
        {"id": r[0], "skill_name": r[1], "skill_arg": r[2], "run_at": r[3], "done": bool(r[4])}
        for r in rows
    ]


def due_schedules(now_iso: str) -> list[dict]:
    """Not-yet-run schedules whose run_at has arrived. ISO-8601 UTC strings
    compare lexicographically in time order, so a plain string <= works."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, skill_name, skill_arg, run_at FROM schedules "
            "WHERE done = 0 AND run_at <= ? ORDER BY run_at, id",
            (now_iso,),
        ).fetchall()
    return [{"id": r[0], "skill_name": r[1], "skill_arg": r[2], "run_at": r[3]} for r in rows]


def complete_schedule(schedule_id: int) -> bool:
    with _connect() as conn:
        cursor = conn.execute("UPDATE schedules SET done = 1 WHERE id = ?", (schedule_id,))
        return cursor.rowcount > 0
