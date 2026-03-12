"""Game state models for AI CTF Duel."""

from datetime import datetime
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field


class GameMode(str, Enum):
    PVP = "pvp"
    PVE = "pve"


class GamePhase(str, Enum):
    SETUP = "setup"
    FORTIFICATION = "fortification"
    SANITY_CHECK = "sanity_check"
    SIEGE = "siege"
    INTERMISSION = "intermission"
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
    game_mode: GameMode = GameMode.PVP
    phase: GamePhase = GamePhase.SETUP
    round: Round = Field(default_factory=Round)
    rounds_history: list[Round] = Field(default_factory=list)
    round_number: int = 1
    max_rounds: int = 4
    defender_score: int = 0
    attacker_score: int = 0
    secret_password: str = ""
    max_turns: int = 3
    max_prompt_length: int = 2000
    vault_level: int = 0
    created_at: datetime = Field(default_factory=datetime.now)

    @property
    def turns_remaining(self) -> int:
        return self.max_turns - len(self.round.turns)

    @property
    def is_siege_over(self) -> bool:
        if self.round.result is not None:
            return True
        return self.turns_remaining <= 0

    @property
    def is_match_over(self) -> bool:
        return self.phase == GamePhase.COMPLETED

    @property
    def match_score(self) -> dict[str, int]:
        return {"defender": self.defender_score, "attacker": self.attacker_score}

    @property
    def defender_label(self) -> str:
        if self.game_mode == GameMode.PVE:
            return "Delaware"
        return "Player 1"

    @property
    def attacker_label(self) -> str:
        if self.game_mode == GameMode.PVE:
            return "You"
        return "Player 2"

    @property
    def is_pve(self) -> bool:
        return self.game_mode == GameMode.PVE

    @property
    def is_optional_round(self) -> bool:
        """Round 4 is the optional Chaos Round (PvP only)."""
        if self.game_mode == GameMode.PVE:
            return False
        return self.round_number == 4

    @property
    def unlock_tier(self) -> int:
        """0 = raw (R1), 1 = attacker guide (R2), 2 = defender guide+templates (R3), 3 = power-ups (R4).
        In PvE, attacker guide is available from round 1."""
        if self.game_mode == GameMode.PVE:
            return min(self.round_number, 3)
        if self.round_number <= 1:
            return 0
        elif self.round_number == 2:
            return 1
        elif self.round_number == 3:
            return 2
        return 3
