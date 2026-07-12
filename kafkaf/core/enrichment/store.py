from contextlib import contextmanager

from kafkaf.core.config import settings
from kafkaf.core.db import connect as _connect_db

_SCHEMA = """
CREATE TABLE IF NOT EXISTS corpus_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,
    teacher_name TEXT,
    topic TEXT NOT NULL,
    prompt TEXT NOT NULL,
    completion TEXT NOT NULL,
    training_run_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS training_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    num_examples INTEGER NOT NULL,
    steps INTEGER NOT NULL,
    loss_start REAL,
    loss_end REAL,
    checkpoint_path TEXT NOT NULL,
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


def save_example(
    source_type: str,
    topic: str,
    prompt: str,
    completion: str,
    teacher_name: str | None = None,
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO corpus_examples (source_type, teacher_name, topic, prompt, completion) "
            "VALUES (?, ?, ?, ?, ?)",
            (source_type, teacher_name, topic, prompt, completion),
        )
        return cursor.lastrowid


def get_unused_examples(limit: int | None = None) -> list[dict]:
    query = (
        "SELECT id, topic, prompt, completion FROM corpus_examples "
        "WHERE training_run_id IS NULL ORDER BY id"
    )
    params: tuple = ()
    if limit is not None:
        query += " LIMIT ?"
        params = (limit,)

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {"id": row[0], "topic": row[1], "prompt": row[2], "completion": row[3]} for row in rows
    ]


def search_examples(query: str, limit: int = 5) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, topic, prompt, completion FROM corpus_examples "
            "WHERE topic LIKE ? OR completion LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", f"%{query}%", limit),
        ).fetchall()
    return [
        {"id": row[0], "topic": row[1], "prompt": row[2], "completion": row[3]} for row in rows
    ]


def mark_examples_trained(example_ids: list[int], run_id: int) -> None:
    with _connect() as conn:
        conn.executemany(
            "UPDATE corpus_examples SET training_run_id = ? WHERE id = ?",
            [(run_id, example_id) for example_id in example_ids],
        )


def count_examples() -> dict:
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM corpus_examples").fetchone()[0]
        unused = conn.execute(
            "SELECT COUNT(*) FROM corpus_examples WHERE training_run_id IS NULL"
        ).fetchone()[0]
    return {"total": total, "unused": unused}


def save_training_run(
    num_examples: int,
    steps: int,
    loss_start: float | None,
    loss_end: float | None,
    checkpoint_path: str,
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO training_runs "
            "(num_examples, steps, loss_start, loss_end, checkpoint_path) "
            "VALUES (?, ?, ?, ?, ?)",
            (num_examples, steps, loss_start, loss_end, checkpoint_path),
        )
        return cursor.lastrowid


def get_latest_training_run() -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, num_examples, steps, loss_start, loss_end, checkpoint_path, created_at "
            "FROM training_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "num_examples": row[1],
        "steps": row[2],
        "loss_start": row[3],
        "loss_end": row[4],
        "checkpoint_path": row[5],
        "created_at": row[6],
    }
