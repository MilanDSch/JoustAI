"""Game state models for AI CTF Duel."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class GamePhase(str, Enum):
    SETUP = "setup"
    FORTIFICATION = "fortification"
    SANITY_CHECK = "sanity_check"
    SIEGE = "siege"
    COMPLETED = "completed"


class GameResult(str, Enum):
    ATTACKER_WIN = "attacker_win"
    DEFENDER_WIN = "defender_win"
    DRAW = "draw"


class Turn(BaseModel):
    """A single attacker turn: their prompt and the AI's response."""

    turn_number: int
    attacker_prompt: str
    ai_response: str
    password_leaked: bool = False
    timestamp: datetime = Field(default_factory=datetime.now)


class DefenderSetup(BaseModel):
    """The defender's fortification: system prompt + secret password."""

    password: str
    system_prompt: str
    sanity_passed: bool = False


class Round(BaseModel):
    """A full round of play: one defender setup + attacker siege."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    defender_setup: DefenderSetup | None = None
    turns: list[Turn] = Field(default_factory=list)
    result: GameResult | None = None
    cracked_on_turn: int | None = None


class Game(BaseModel):
    """Top-level game state."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    phase: GamePhase = GamePhase.SETUP
    round: Round = Field(default_factory=Round)
    secret_password: str = ""
    max_turns: int = 5
    max_prompt_length: int = 2000
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def turns_remaining(self) -> int:
        return self.max_turns - len(self.round.turns)

    @property
    def is_siege_over(self) -> bool:
        if self.round.result is not None:
            return True
        return self.turns_remaining <= 0
