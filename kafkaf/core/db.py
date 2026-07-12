import sqlite3
from contextlib import contextmanager


@contextmanager
def connect(db_path: str):
    """A sqlite3 connection with a busy timeout, shared by memory/store.py and
    enrichment/store.py — both may be opened by separate processes (the FastAPI
    backend and the MCP server) against the same file."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
