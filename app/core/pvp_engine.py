"""PvP engine: orchestrates the Player-vs-Player game mode."""

import random

from app.config import settings
from app.core.engine import ATTACKER_BASE_POINTS, DEFENDER_WIN_POINTS, BaseEngine, build_shadow_prompt
from app.core.logger import get_logger
from app.models.game import (
    AttackerPowerUp,
    DefenderPowerUp,
    DefenderSetup,
    GamePhase,
    GameResult,
    Round,
)
from app.services.llm import LLMService
from app.services.sanity import SanityResult, run_sanity_check

logger = get_logger(__name__)


class PvPEngine(BaseEngine):
    """Manages a PvP game — two players alternate between defender and attacker."""

    def setup_defense(
        self,
        system_prompt: str,
        power_up: DefenderPowerUp = DefenderPowerUp.NONE,
        banned_words: list[str] | None = None,
        decoy_password: str = "",
    ) -> SanityResult:
        """Defender submits their system prompt and optional power-up.

        The password is auto-assigned at init time.

        Returns:
            SanityResult with details on pass/fail.

        Raises:
            ValueError: If prompt exceeds character limit, is empty, or power-up
                        payload is invalid.
        """
        system_prompt = system_prompt.strip()
        password = self.game.secret_password

        if not system_prompt:
            raise ValueError("System prompt cannot be empty.")
        if len(system_prompt) > self.game.max_prompt_length:
            raise ValueError(
                f"System prompt exceeds {self.game.max_prompt_length} character limit "
                f"(yours: {len(system_prompt)})."
            )

        # Validate power-up payloads
        clean_banned: list[str] = []
        if power_up == DefenderPowerUp.RUNE_OF_SILENCE:
            raw = banned_words or []
            clean_banned = [w.strip() for w in raw if w.strip()]
            if not clean_banned:
                raise ValueError("Rune of Silence requires at least one banned word.")
            if len(clean_banned) > 3:
                raise ValueError("Rune of Silence allows a maximum of 3 banned words.")
            for w in clean_banned:
                if len(w) > 30:
                    raise ValueError(f"Banned word '{w[:10]}...' exceeds 30 characters.")
        elif power_up == DefenderPowerUp.DECOY_CIPHER:
            decoy_password = decoy_password.strip()
            if not decoy_password:
                raise ValueError("Decoy Cipher requires a fake password.")
            if decoy_password.strip().lower() == password.strip().lower():
                raise ValueError("Decoy password must differ from the real password.")

        # Sanity check (skipped for Mad King's Decree)
        if power_up == DefenderPowerUp.MAD_KINGS_DECREE:
            sanity_result = SanityResult(
                passed=True,
                total_questions=0,
                passed_questions=0,
                failures=[],
            )
            logger.info("Mad King's Decree: sanity check bypassed")
        else:
            self.game.phase = GamePhase.SANITY_CHECK
            enveloped = build_shadow_prompt(system_prompt, password)
            sanity_result = run_sanity_check(self.llm, enveloped)

        self.game.round.defender_setup = DefenderSetup(
            password=password,
            system_prompt=system_prompt,
            sanity_passed=sanity_result.passed,
            defender_power_up=power_up,
            banned_words=clean_banned,
            decoy_password=decoy_password if power_up == DefenderPowerUp.DECOY_CIPHER else "",
        )

        if sanity_result.passed:
            self.game.phase = GamePhase.SIEGE
            logger.info("Defense setup passed sanity check")
        else:
            self.game.phase = GamePhase.FORTIFICATION
            logger.warning(
                "Defense setup failed sanity check: %s", sanity_result.failures
            )
        return sanity_result

    def _finish_round(self) -> None:
        """Award points and transition phase after a round ends."""
        game = self.game
        result = game.round.result

        # Award points (static roles: Player 1 = Defender, Player 2 = Attacker)
        if result == GameResult.DEFENDER_WIN:
            game.defender_score += DEFENDER_WIN_POINTS
            logger.info("Awarded %d pts to Defender (Player 1)", DEFENDER_WIN_POINTS)
        elif result == GameResult.ATTACKER_WIN:
            cracked_on = game.round.cracked_on_turn or 1
            points = max(ATTACKER_BASE_POINTS - cracked_on, 1)
            game.attacker_score += points
            logger.info("Awarded %d pts to Attacker (Player 2)", points)

        # Transition phase
        if game.round_number < game.max_rounds:
            game.phase = GamePhase.INTERMISSION
        else:
            game.phase = GamePhase.COMPLETED

    def next_round(self) -> None:
        """Advance to the next round: archive current round, reset state."""
        if self.game.phase != GamePhase.INTERMISSION:
            raise RuntimeError(f"Cannot start next round in phase: {self.game.phase}")

        # Reset Time Thief bonus before archiving
        if self.game.round.attacker_power_up == AttackerPowerUp.TIME_THIEF:
            self.game.max_turns -= 2
            logger.info("Time Thief reset: max_turns back to %d", self.game.max_turns)

        # Archive completed round
        self.game.rounds_history.append(self.game.round)
        self.game.round_number += 1

        # Pick a new password, avoiding previously used ones
        used = {r.defender_setup.password for r in self.game.rounds_history if r.defender_setup}
        available = [p for p in settings.password_pool if p not in used]
        self.game.secret_password = random.choice(available or settings.password_pool)

        # Fresh round
        self.game.round = Round()
        self.game.phase = GamePhase.FORTIFICATION
        logger.info("Starting round %d (new password assigned)", self.game.round_number)
