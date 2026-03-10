"""In-memory session store mapping session IDs to GameEngine instances."""

import uuid

from app.core.engine import GameEngine

_sessions: dict[str, GameEngine] = {}


def create_session() -> tuple[str, GameEngine]:
    """Create a new game session and return (session_id, engine)."""
    session_id = uuid.uuid4().hex
    engine = GameEngine()
    _sessions[session_id] = engine
    return session_id, engine


def get_session(session_id: str) -> GameEngine | None:
    """Retrieve an existing game session, or None if not found."""
    return _sessions.get(session_id)


def destroy_session(session_id: str) -> None:
    """Remove a game session."""
    _sessions.pop(session_id, None)
