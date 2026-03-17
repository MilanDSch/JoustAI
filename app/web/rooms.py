"""In-memory room store for multi-screen arena PvP."""

import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from app.core.pvp_engine import PvPEngine

ROOM_TTL_SECONDS = 3600  # 1 hour
MAX_ROOMS = 50

# Medieval-themed room codes, easy to read aloud
_ROOM_WORDS = [
    "DRAGON", "CASTLE", "KNIGHT", "SHIELD", "THRONE",
    "FALCON", "BANNER", "ARCHER", "MYSTIC", "ORACLE",
    "RAVEN", "FORGE", "CROWN", "QUEST", "BLADE",
    "STORM", "TOWER", "FROST", "EMBER", "SHADOW",
    "IRON", "STONE", "FLAME", "WOLF", "GRAIL",
    "VIPER", "SIEGE", "LANCE", "HELM", "DAGGER",
]


class PlayerRole(str, Enum):
    DEFENDER = "defender"
    ATTACKER = "attacker"


@dataclass
class Room:
    code: str
    engine: PvPEngine
    defender_token: str
    attacker_token: str | None = None
    created: float = field(default_factory=time.monotonic)
    phase_version: int = 0


_rooms: dict[str, Room] = {}
_tokens: dict[str, tuple[str, PlayerRole]] = {}


def _cleanup_expired() -> None:
    """Remove rooms older than ROOM_TTL_SECONDS."""
    now = time.monotonic()
    expired = [
        code for code, room in _rooms.items()
        if now - room.created > ROOM_TTL_SECONDS
    ]
    for code in expired:
        _destroy_room_internal(code)


def _evict_if_full() -> None:
    """If at capacity, remove the oldest room."""
    if len(_rooms) >= MAX_ROOMS:
        oldest = min(_rooms, key=lambda c: _rooms[c].created)
        _destroy_room_internal(oldest)


def _generate_code() -> str:
    """Generate a unique room code."""
    available = [w for w in _ROOM_WORDS if w not in _rooms]
    if available:
        return random.choice(available)
    # Fallback: random 6-char alphanumeric
    while True:
        code = uuid.uuid4().hex[:6].upper()
        if code not in _rooms:
            return code


def _destroy_room_internal(code: str) -> None:
    """Remove a room and its token mappings."""
    room = _rooms.pop(code, None)
    if room:
        _tokens.pop(room.defender_token, None)
        if room.attacker_token:
            _tokens.pop(room.attacker_token, None)


def create_room() -> tuple[str, str, Room]:
    """Create a new arena room. Returns (room_code, defender_token, room)."""
    _cleanup_expired()
    _evict_if_full()
    code = _generate_code()
    defender_token = uuid.uuid4().hex
    engine = PvPEngine()
    room = Room(code=code, engine=engine, defender_token=defender_token)
    _rooms[code] = room
    _tokens[defender_token] = (code, PlayerRole.DEFENDER)
    return code, defender_token, room


def join_room(code: str) -> tuple[str, Room] | None:
    """Join an existing room as attacker. Returns (attacker_token, room) or None."""
    code = code.strip().upper()
    room = _rooms.get(code)
    if room is None:
        return None
    if room.attacker_token is not None:
        return None  # Room is full
    attacker_token = uuid.uuid4().hex
    room.attacker_token = attacker_token
    _tokens[attacker_token] = (code, PlayerRole.ATTACKER)
    bump_version(room)
    return attacker_token, room


def get_room(code: str) -> Room | None:
    """Retrieve a room by code, or None if expired/not found."""
    code = code.strip().upper()
    room = _rooms.get(code)
    if room is None:
        return None
    if time.monotonic() - room.created > ROOM_TTL_SECONDS:
        _destroy_room_internal(code)
        return None
    return room


def get_room_by_token(token: str) -> tuple[Room, PlayerRole] | None:
    """Look up room and role from a player token."""
    entry = _tokens.get(token)
    if entry is None:
        return None
    code, role = entry
    room = get_room(code)
    if room is None:
        _tokens.pop(token, None)
        return None
    return room, role


def bump_version(room: Room) -> None:
    """Increment phase_version to signal state change to polling clients."""
    room.phase_version += 1


def destroy_room(code: str) -> None:
    """Public API to remove a room."""
    _destroy_room_internal(code.strip().upper())
