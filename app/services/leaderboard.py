"""SQLite-backed leaderboard storage for PvE mode."""

import sqlite3
import threading
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parents[2] / "leaderboard.db"
_write_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the leaderboard table if it does not exist."""
    conn = _connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leaderboard (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                company TEXT,
                email TEXT NOT NULL,
                highest_level INTEGER NOT NULL,
                total_turns INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def add_entry(
    name: str,
    company: str | None,
    email: str,
    highest_level: int,
    total_turns: int,
) -> int:
    """Insert a leaderboard entry and return its ID."""
    with _write_lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                INSERT INTO leaderboard (name, company, email, highest_level, total_turns)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, company, email, highest_level, total_turns),
            )
            conn.commit()
            return cursor.lastrowid  # type: ignore[return-value]
        finally:
            conn.close()


def get_top_entries(limit: int = 10) -> list[dict]:
    """Return top leaderboard entries ordered by highest level DESC, then fewest turns ASC."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT name, company, highest_level, total_turns, created_at
            FROM leaderboard
            ORDER BY highest_level DESC, total_turns ASC, created_at ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
