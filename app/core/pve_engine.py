"""PvE engine: orchestrates the Beat Delaware single-player mode."""

import random

from app.config import settings
from app.core.engine import GameEngine, build_shadow_prompt
from app.core.logger import get_logger
from app.data.vaults import Vault, get_vault
from app.models.game import (
    DefenderSetup,
    GameMode,
    GamePhase,
    GameResult,
    Round,
)
from app.services.llm import LLMService

logger = get_logger(__name__)

TOTAL_VAULTS = 5


class PvEEngine(GameEngine):
    """Manages a Beat Delaware PvE game — player is always the attacker."""

    def __init__(self, llm: LLMService | None = None) -> None:
        super().__init__(llm)
        self.game.game_mode = GameMode.PVE
        self.game.max_rounds = TOTAL_VAULTS
        self._setup_vault(1)
        logger.info("PvE game initialized — Beat Delaware mode")

    @property
    def current_vault(self) -> Vault:
        return get_vault(self.game.vault_level)

    def _setup_vault(self, level: int) -> None:
        """Configure the game for a specific vault level, skipping FORTIFICATION."""
        vault = get_vault(level)
        self.game.vault_level = level

        # Pick a random password, avoiding previously used ones
        used = {
            r.defender_setup.password
            for r in self.game.rounds_history
            if r.defender_setup
        }
        available = [p for p in settings.password_pool if p not in used]
        self.game.secret_password = random.choice(available or settings.password_pool)

        # Set up defense with the curated prompt (no sanity check needed)
        self.game.round.defender_setup = DefenderSetup(
            password=self.game.secret_password,
            system_prompt=vault.system_prompt,
            sanity_passed=True,
        )
        self.game.phase = GamePhase.SIEGE
        logger.info(
            "Vault %d (%s) ready — difficulty: %s",
            level,
            vault.name,
            vault.difficulty,
        )

    def _finish_round(self) -> None:
        """Record stats and transition phase after a vault attempt ends.

        In PVE the computer (Delaware) never scores — only the player earns
        points for breaching vaults.
        """
        game = self.game
        result = game.round.result

        if result == GameResult.ATTACKER_WIN:
            cracked_on = game.round.cracked_on_turn or 1
            points = max(11 - cracked_on, 1)
            game.attacker_score += points
            logger.info("Vault %d breached! +%d pts to player", game.vault_level, points)

            if game.round_number < game.max_rounds:
                game.phase = GamePhase.INTERMISSION
            else:
                logger.info("Player beat all vaults!")
                game.phase = GamePhase.COMPLETED

        elif result == GameResult.DEFENDER_WIN:
            logger.info("Delaware's vault held on Level %d. Run over.", game.vault_level)
            game.phase = GamePhase.COMPLETED

    def next_round(self) -> None:
        """Advance to the next vault, skipping FORTIFICATION."""
        if self.game.phase != GamePhase.INTERMISSION:
            raise RuntimeError(f"Cannot start next round in phase: {self.game.phase}")

        # Archive completed round
        self.game.rounds_history.append(self.game.round)
        self.game.round_number += 1
        self.game.round = Round()

        # Jump straight to the next vault
        self._setup_vault(self.game.vault_level + 1)
        logger.info("Starting vault %d", self.game.vault_level)

if __name__ == "__main__":
    engine = PvEEngine()
    print("Assigned password:", engine.game.secret_password)