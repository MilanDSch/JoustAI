"""In-memory session store mapping session IDs to BaseEngine instances."""

import uuid

from app.core.engine import BaseEngine
from app.core.pve_engine import PvEEngine
from app.core.pvp_engine import PvPEngine

_sessions: dict[str, BaseEngine] = {}


def create_session() -> tuple[str, PvPEngine]:
    """Create a new PvP game session and return (session_id, engine)."""
    session_id = uuid.uuid4().hex
    engine = PvPEngine()
    _sessions[session_id] = engine
    return session_id, engine


def create_pve_session() -> tuple[str, PvEEngine]:
    """Create a new PvE (Beat Delaware) session and return (session_id, engine)."""
    session_id = uuid.uuid4().hex
    engine = PvEEngine()
    _sessions[session_id] = engine
    return session_id, engine


def get_session(session_id: str) -> BaseEngine | None:
    """Retrieve an existing game session, or None if not found."""
    return _sessions.get(session_id)


def destroy_session(session_id: str) -> None:
    """Remove a game session."""
    _sessions.pop(session_id, None)
