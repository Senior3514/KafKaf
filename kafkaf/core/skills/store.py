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

-- A paused ReAct loop turn, waiting on a live human approve/deny click
-- before a requires_approval skill (run_code, browser_automate) actually
-- runs. conversation_json is the full message list up to and including
-- the assistant's ACTION-bearing reply — resuming appends the decision's
-- OBSERVATION and continues the same loop from iterations_used.
CREATE TABLE IF NOT EXISTS skill_approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    user_message TEXT NOT NULL,
    brain_spec TEXT,
    skill_name TEXT NOT NULL,
    skill_arg TEXT NOT NULL,
    conversation_json TEXT NOT NULL,
    iterations_used INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    decided_at TEXT
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


_APPROVAL_COLUMNS = (
    "id, session_id, user_message, brain_spec, skill_name, skill_arg, "
    "conversation_json, iterations_used, status, created_at, decided_at"
)


def _approval_row_to_dict(row) -> dict:
    return {
        "id": row[0],
        "session_id": row[1],
        "user_message": row[2],
        "brain_spec": row[3],
        "skill_name": row[4],
        "skill_arg": row[5],
        "conversation_json": row[6],
        "iterations_used": row[7],
        "status": row[8],
        "created_at": row[9],
        "decided_at": row[10],
    }


def add_approval(
    session_id: str,
    user_message: str,
    brain_spec: str | None,
    skill_name: str,
    skill_arg: str,
    conversation_json: str,
    iterations_used: int,
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO skill_approvals "
            "(session_id, user_message, brain_spec, skill_name, skill_arg, "
            "conversation_json, iterations_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, user_message, brain_spec, skill_name, skill_arg, conversation_json, iterations_used),
        )
        return cursor.lastrowid


def get_approval(approval_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_APPROVAL_COLUMNS} FROM skill_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
    return _approval_row_to_dict(row) if row else None


def list_approvals(status: str | None = "pending") -> list[dict]:
    query = f"SELECT {_APPROVAL_COLUMNS} FROM skill_approvals"
    params: list = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY id DESC"
    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_approval_row_to_dict(row) for row in rows]


def claim_approval(approval_id: int, decision: str) -> dict | None:
    """Atomically transition a pending approval to 'approved'/'denied'.
    Returns the full pre-decision row on success, None if it was already
    decided or doesn't exist — the caller must not execute the skill
    unless this returns non-None, which is what makes a double-click or a
    second tab race safe (only one caller ever wins the UPDATE)."""
    with _connect() as conn:
        row = conn.execute(
            f"SELECT {_APPROVAL_COLUMNS} FROM skill_approvals WHERE id = ?", (approval_id,)
        ).fetchone()
        if row is None:
            return None
        cursor = conn.execute(
            "UPDATE skill_approvals SET status = ?, decided_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND status = 'pending'",
            (decision, approval_id),
        )
        if cursor.rowcount == 0:
            return None
        return _approval_row_to_dict(row)
