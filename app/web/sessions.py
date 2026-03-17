"""In-memory session store mapping session IDs to BaseEngine instances."""

import time
import uuid

from app.core.engine import BaseEngine
from app.core.pve_engine import PvEEngine
from app.core.pvp_engine import PvPEngine

SESSION_TTL_SECONDS = 3600  # 1 hour
MAX_SESSIONS = 200

_sessions: dict[str, tuple[BaseEngine, float]] = {}


def _cleanup_expired() -> None:
    """Remove sessions older than SESSION_TTL_SECONDS."""
    now = time.monotonic()
    expired = [
        sid for sid, (_, created) in _sessions.items()
        if now - created > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _sessions.pop(sid, None)


def _evict_if_full() -> None:
    """If at capacity, remove the oldest session."""
    if len(_sessions) >= MAX_SESSIONS:
        oldest = min(_sessions, key=lambda sid: _sessions[sid][1])
        _sessions.pop(oldest, None)


def create_session() -> tuple[str, PvPEngine]:
    """Create a new PvP game session and return (session_id, engine)."""
    _cleanup_expired()
    _evict_if_full()
    session_id = uuid.uuid4().hex
    engine = PvPEngine()
    _sessions[session_id] = (engine, time.monotonic())
    return session_id, engine


def create_pve_session() -> tuple[str, PvEEngine]:
    """Create a new PvE (Beat Delaware) session and return (session_id, engine)."""
    _cleanup_expired()
    _evict_if_full()
    session_id = uuid.uuid4().hex
    engine = PvEEngine()
    _sessions[session_id] = (engine, time.monotonic())
    return session_id, engine


def get_session(session_id: str) -> BaseEngine | None:
    """Retrieve an existing game session, or None if expired/not found."""
    entry = _sessions.get(session_id)
    if entry is None:
        return None
    engine, created = entry
    if time.monotonic() - created > SESSION_TTL_SECONDS:
        _sessions.pop(session_id, None)
        return None
    return engine


def destroy_session(session_id: str) -> None:
    """Remove a game session."""
    _sessions.pop(session_id, None)
