"""Arena routes for multi-screen PvP (each player on their own device)."""

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.engine import SHADOW_PROMPT_INTRO, SHADOW_PROMPT_OUTRO
from app.core.logger import get_logger
from app.models.game import AttackerPowerUp, DefenderPowerUp, GamePhase, GameResult
from app.web.rooms import (
    PlayerRole,
    Room,
    bump_version,
    create_room,
    destroy_room,
    get_room,
    get_room_by_token,
    join_room,
)

logger = get_logger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


# ── Helpers ──────────────────────────────────────────────


def _get_room_and_role(token: str | None) -> tuple[Room, PlayerRole] | None:
    """Resolve arena cookie to room + role."""
    if not token:
        return None
    return get_room_by_token(token)


def _require_role(
    token: str | None,
    required: PlayerRole,
) -> tuple[Room, PlayerRole] | None:
    """Get room if token matches required role, else None."""
    result = _get_room_and_role(token)
    if result is None:
        return None
    room, role = result
    if role != required:
        return None
    return result


def _round_context(engine) -> dict:
    """Common round context for templates (mirrors game.py)."""
    game = engine.game
    return {
        "round_number": game.round_number,
        "max_rounds": game.max_rounds,
        "defender_score": game.defender_score,
        "attacker_score": game.attacker_score,
        "defender_label": game.defender_label,
        "attacker_label": game.attacker_label,
        "unlock_tier": game.unlock_tier,
    }


def _arena_cookie(response: RedirectResponse, token: str) -> RedirectResponse:
    """Set the joust_arena cookie on a response."""
    response.set_cookie(
        key="joust_arena",
        value=token,
        httponly=True,
        samesite="strict",
    )
    return response


# ── Room creation / joining ──────────────────────────────


@router.post("/arena/new")
async def arena_new():
    """Defender creates a new arena room."""
    code, defender_token, room = create_room()
    room.engine.game.phase = GamePhase.FORTIFICATION
    logger.info("Arena room created: %s", code)
    response = RedirectResponse(url=f"/arena/{code}/lobby", status_code=303)
    return _arena_cookie(response, defender_token)


@router.get("/arena/{code}/lobby", response_class=HTMLResponse)
async def arena_lobby(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Defender's lobby -- shows room code, waits for attacker."""
    result = _require_role(joust_arena, PlayerRole.DEFENDER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(request, "arena_lobby.html", {
        "room_code": room.code,
        "attacker_joined": room.attacker_token is not None,
    })


@router.post("/arena/join")
async def arena_join(room_code: str = Form(...)):
    """Attacker joins an existing arena room."""
    result = join_room(room_code)
    if result is None:
        # Room not found or full -- redirect back to start
        return RedirectResponse(url="/?error=room_not_found", status_code=303)
    attacker_token, room = result
    logger.info("Attacker joined arena room: %s", room.code)
    response = RedirectResponse(
        url=f"/arena/{room.code}/waiting", status_code=303
    )
    return _arena_cookie(response, attacker_token)


# ── Status polling endpoint ─────────────────────────────


@router.get("/arena/{code}/status")
async def arena_status(code: str):
    """Lightweight JSON endpoint for polling."""
    room = get_room(code)
    if room is None:
        return JSONResponse({"error": "room_not_found"}, status_code=404)
    game = room.engine.game
    return JSONResponse({
        "phase": game.phase.value,
        "phase_version": room.phase_version,
        "round_number": game.round_number,
        "defender_score": game.defender_score,
        "attacker_score": game.attacker_score,
        "turns_count": len(game.round.turns),
        "attacker_joined": room.attacker_token is not None,
    })


# ── Defender: fortification ─────────────────────────────


@router.get("/arena/{code}/defend", response_class=HTMLResponse)
async def arena_defend_page(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Defender writes their system prompt."""
    result = _require_role(joust_arena, PlayerRole.DEFENDER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.FORTIFICATION:
        return RedirectResponse(
            url=f"/arena/{room.code}/defend-wait", status_code=303
        )

    password = engine.game.secret_password
    return templates.TemplateResponse(request, "defend.html", {
        "errors": [],
        "system_prompt": "",
        "max_prompt_length": engine.game.max_prompt_length,
        "secret_password": password,
        "shadow_intro": SHADOW_PROMPT_INTRO.replace("secret_password", password),
        "shadow_outro": SHADOW_PROMPT_OUTRO,
        "url_prefix": f"/arena/{room.code}",
        **_round_context(engine),
    })


@router.post("/arena/{code}/defend", response_class=HTMLResponse)
async def arena_defend_submit(
    request: Request,
    code: str,
    system_prompt: str = Form(...),
    defender_power_up: str = Form("none"),
    banned_word_1: str = Form(""),
    banned_word_2: str = Form(""),
    banned_word_3: str = Form(""),
    decoy_password: str = Form(""),
    joust_arena: str | None = Cookie(default=None),
):
    """Defender submits their system prompt."""
    result = _require_role(joust_arena, PlayerRole.DEFENDER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.FORTIFICATION:
        return RedirectResponse(
            url=f"/arena/{room.code}/defend-wait", status_code=303
        )

    password = engine.game.secret_password
    errors: list[str] = []

    def _defend_context(extra_errors: list[str] | None = None):
        return {
            "errors": extra_errors or errors,
            "system_prompt": system_prompt,
            "max_prompt_length": engine.game.max_prompt_length,
            "secret_password": password,
            "shadow_intro": SHADOW_PROMPT_INTRO.replace("secret_password", password),
            "shadow_outro": SHADOW_PROMPT_OUTRO,
            "url_prefix": f"/arena/{room.code}",
            **_round_context(engine),
        }

    # Parse power-up
    power_up = DefenderPowerUp.NONE
    banned_words: list[str] = []
    decoy = ""
    if engine.game.unlock_tier >= 3:
        try:
            power_up = DefenderPowerUp(defender_power_up)
        except ValueError:
            power_up = DefenderPowerUp.NONE
        banned_words = [
            w for w in [banned_word_1.strip(), banned_word_2.strip(), banned_word_3.strip()] if w
        ]
        decoy = decoy_password.strip()

    try:
        sanity_result = engine.setup_defense(
            system_prompt,
            power_up=power_up,
            banned_words=banned_words,
            decoy_password=decoy,
        )
    except ValueError as e:
        logger.warning("Arena defense setup rejected: %s", e)
        errors.append(str(e))
        return templates.TemplateResponse(request, "defend.html", _defend_context())

    if not sanity_result.passed:
        errors.append("Sanity check failed -- your prompt is too restrictive.")
        for failure in sanity_result.failures:
            errors.append(failure)
        return templates.TemplateResponse(request, "defend.html", _defend_context())

    # Sanity passed -- phase is now SIEGE
    bump_version(room)
    return RedirectResponse(
        url=f"/arena/{room.code}/defend-wait", status_code=303
    )


# ── Defender: waiting during siege ──────────────────────


@router.get("/arena/{code}/defend-wait", response_class=HTMLResponse)
async def arena_defend_wait(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Defender waits while attacker plays the siege."""
    result = _require_role(joust_arena, PlayerRole.DEFENDER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    phase = engine.game.phase

    # If game moved past siege, redirect
    if phase == GamePhase.INTERMISSION:
        return RedirectResponse(
            url=f"/arena/{room.code}/intermission", status_code=303
        )
    if phase == GamePhase.COMPLETED:
        return RedirectResponse(
            url=f"/arena/{room.code}/results", status_code=303
        )

    return templates.TemplateResponse(request, "arena_defend_wait.html", {
        "room_code": room.code,
        **_round_context(engine),
    })


# ── Attacker: waiting for defender ──────────────────────


@router.get("/arena/{code}/waiting", response_class=HTMLResponse)
async def arena_waiting(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Attacker waits for defender to finish fortification."""
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    # If already in siege, redirect directly
    if engine.game.phase == GamePhase.SIEGE:
        return RedirectResponse(
            url=f"/arena/{room.code}/siege", status_code=303
        )

    return templates.TemplateResponse(request, "arena_waiting.html", {
        "room_code": room.code,
        **_round_context(engine),
    })


# ── Attacker: siege ─────────────────────────────────────


@router.get("/arena/{code}/siege", response_class=HTMLResponse)
async def arena_siege_page(
    request: Request,
    code: str,
    error: str | None = None,
    joust_arena: str | None = Cookie(default=None),
):
    """Siege page for the attacker."""
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    phase = engine.game.phase

    if phase == GamePhase.INTERMISSION:
        return RedirectResponse(
            url=f"/arena/{room.code}/intermission", status_code=303
        )
    if phase == GamePhase.COMPLETED:
        return RedirectResponse(
            url=f"/arena/{room.code}/results", status_code=303
        )
    if phase != GamePhase.SIEGE:
        return RedirectResponse(
            url=f"/arena/{room.code}/waiting", status_code=303
        )

    game_round = engine.game.round
    setup = game_round.defender_setup

    attacker_pu = game_round.attacker_power_up
    prompt_peek = None
    if attacker_pu == AttackerPowerUp.SPYS_WHISPER and setup:
        prompt_peek = setup.system_prompt[:75]
    defender_pu_label = None
    if attacker_pu == AttackerPowerUp.ORACLES_ECHO and setup:
        defender_pu_label = {
            "none": "No Artifact",
            "rune_of_silence": "Rune of Silence",
            "mad_kings_decree": "Mad King's Decree",
            "decoy_cipher": "Decoy Cipher",
        }.get(setup.defender_power_up.value, "Unknown")

    return templates.TemplateResponse(request, "siege.html", {
        "turns": game_round.turns,
        "turns_remaining": engine.game.turns_remaining,
        "game_over": engine.game.is_siege_over,
        "is_last_turn": engine.game.turns_remaining == 1,
        "error": error,
        "attacker_power_up": attacker_pu.value,
        "attacker_power_up_used": game_round.attacker_power_up_used,
        "prompt_peek": prompt_peek,
        "defender_pu_label": defender_pu_label,
        "defender_power_up": setup.defender_power_up.value if setup else "none",
        "url_prefix": f"/arena/{room.code}",
        **_round_context(engine),
    })


@router.post("/arena/{code}/attack")
async def arena_attack_submit(
    code: str,
    attacker_prompt: str = Form(...),
    joust_arena: str | None = Cookie(default=None),
):
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(url=f"/arena/{room.code}/waiting", status_code=303)

    engine.attack(attacker_prompt)
    bump_version(room)

    if engine.game.round.result is not None:
        phase = engine.game.phase
        if phase == GamePhase.INTERMISSION:
            return RedirectResponse(
                url=f"/arena/{room.code}/intermission", status_code=303
            )
        if phase == GamePhase.COMPLETED:
            return RedirectResponse(
                url=f"/arena/{room.code}/results", status_code=303
            )

    return RedirectResponse(url=f"/arena/{room.code}/siege", status_code=303)


@router.post("/arena/{code}/guess")
async def arena_guess_submit(
    code: str,
    guess: str = Form(...),
    joust_arena: str | None = Cookie(default=None),
):
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(url=f"/arena/{room.code}/waiting", status_code=303)

    engine.guess_password(guess)
    bump_version(room)

    if engine.game.round.result is not None:
        phase = engine.game.phase
        if phase == GamePhase.INTERMISSION:
            return RedirectResponse(
                url=f"/arena/{room.code}/intermission", status_code=303
            )
        if phase == GamePhase.COMPLETED:
            return RedirectResponse(
                url=f"/arena/{room.code}/results", status_code=303
            )

    return RedirectResponse(
        url=f"/arena/{room.code}/siege?error=incorrect_guess", status_code=303
    )


@router.post("/arena/{code}/attacker-power-up")
async def arena_attacker_power_up(
    code: str,
    power_up: str = Form(...),
    joust_arena: str | None = Cookie(default=None),
):
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(url=f"/arena/{room.code}/waiting", status_code=303)

    try:
        parsed = AttackerPowerUp(power_up)
        engine.activate_attacker_power_up(parsed)
        bump_version(room)
    except (ValueError, RuntimeError) as e:
        logger.warning("Arena attacker power-up rejected: %s", e)
        return RedirectResponse(
            url=f"/arena/{room.code}/siege?error=power_up_failed", status_code=303
        )

    return RedirectResponse(url=f"/arena/{room.code}/siege", status_code=303)


@router.post("/arena/{code}/surrender")
async def arena_surrender(
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    result = _require_role(joust_arena, PlayerRole.ATTACKER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    room.engine.surrender()
    bump_version(room)

    phase = room.engine.game.phase
    if phase == GamePhase.INTERMISSION:
        return RedirectResponse(
            url=f"/arena/{room.code}/intermission", status_code=303
        )
    return RedirectResponse(
        url=f"/arena/{room.code}/results", status_code=303
    )


# ── Intermission ────────────────────────────────────────


@router.get("/arena/{code}/intermission", response_class=HTMLResponse)
async def arena_intermission(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Both players see the round results."""
    info = _get_room_and_role(joust_arena)
    if not info:
        return RedirectResponse(url="/", status_code=303)
    room, role = info
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.INTERMISSION:
        if engine.game.phase == GamePhase.COMPLETED:
            return RedirectResponse(
                url=f"/arena/{room.code}/results", status_code=303
            )
        # Redirect to appropriate page based on role
        if role == PlayerRole.DEFENDER:
            return RedirectResponse(
                url=f"/arena/{room.code}/defend", status_code=303
            )
        return RedirectResponse(
            url=f"/arena/{room.code}/waiting", status_code=303
        )

    game = engine.game
    setup = game.round.defender_setup

    return templates.TemplateResponse(request, "intermission.html", {
        "last_result": game.round.result.value if game.round.result else "draw",
        "password": setup.password if setup else "???",
        "total_turns": len(game.round.turns),
        "max_turns": game.max_turns,
        "url_prefix": f"/arena/{room.code}",
        "is_arena": True,
        "arena_role": role.value,
        "room_code": room.code,
        **_round_context(engine),
    })


@router.post("/arena/{code}/next-round")
async def arena_next_round(
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Defender starts the next round."""
    result = _require_role(joust_arena, PlayerRole.DEFENDER)
    if not result:
        return RedirectResponse(url="/", status_code=303)
    room, _ = result
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    room.engine.next_round()
    bump_version(room)
    return RedirectResponse(
        url=f"/arena/{room.code}/defend", status_code=303
    )


# ── Results ─────────────────────────────────────────────


@router.get("/arena/{code}/results", response_class=HTMLResponse)
async def arena_results(
    request: Request,
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Final results page for both players."""
    info = _get_room_and_role(joust_arena)
    if not info:
        return RedirectResponse(url="/", status_code=303)
    room, _ = info
    if room.code != code.upper():
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    if engine.game.phase != GamePhase.COMPLETED:
        return RedirectResponse(url=f"/arena/{room.code}/lobby", status_code=303)

    game = engine.game
    all_rounds = [*game.rounds_history, game.round]
    overall_winner = (
        "Defender (Player 1)" if game.defender_score > game.attacker_score
        else "Attacker (Player 2)" if game.attacker_score > game.defender_score
        else "draw"
    )

    rounds_summary = []
    for i, r in enumerate(all_rounds, 1):
        if r.result == GameResult.DEFENDER_WIN:
            points = 10
            points_to = "Defender (Player 1)"
        elif r.result == GameResult.ATTACKER_WIN:
            points = max(11 - (r.cracked_on_turn or 1), 1)
            points_to = "Attacker (Player 2)"
        else:
            points = 0
            points_to = None

        rounds_summary.append({
            "number": i,
            "password": r.defender_setup.password if r.defender_setup else "???",
            "result": r.result.value if r.result else "draw",
            "total_turns": len(r.turns),
            "cracked_on_turn": r.cracked_on_turn,
            "points_awarded": points,
            "points_to": points_to,
        })

    return templates.TemplateResponse(request, "results.html", {
        "overall_winner": overall_winner,
        "rounds_summary": rounds_summary,
        "max_turns": game.max_turns,
        "url_prefix": f"/arena/{room.code}",
        **_round_context(engine),
    })


@router.post("/arena/{code}/restart")
async def arena_restart(
    code: str,
    joust_arena: str | None = Cookie(default=None),
):
    """Destroy the arena room and return to start."""
    info = _get_room_and_role(joust_arena)
    if info:
        room, _ = info
        destroy_room(room.code)
        logger.info("Arena room destroyed: %s", room.code)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("joust_arena")
    return response


# ── Spectator ───────────────────────────────────────────


@router.get("/arena/{code}/spectate", response_class=HTMLResponse)
async def arena_spectate(
    request: Request,
    code: str,
):
    """Read-only spectator/scoreboard view."""
    room = get_room(code)
    if room is None:
        return RedirectResponse(url="/", status_code=303)

    engine = room.engine
    game = engine.game
    phase = game.phase

    # Current round chat transcript (hide password during active siege)
    current_turns = game.round.turns
    setup = game.round.defender_setup
    current_password = None
    if phase not in (GamePhase.SIEGE, GamePhase.FORTIFICATION, GamePhase.SANITY_CHECK):
        current_password = setup.password if setup else None

    # Completed rounds history
    rounds_history = []
    for i, r in enumerate(game.rounds_history, 1):
        if r.result == GameResult.DEFENDER_WIN:
            result_label = "Defender Wins"
        elif r.result == GameResult.ATTACKER_WIN:
            result_label = "Attacker Wins"
        else:
            result_label = "Draw"

        rounds_history.append({
            "number": i,
            "password": r.defender_setup.password if r.defender_setup else "???",
            "result": r.result.value if r.result else "draw",
            "result_label": result_label,
            "total_turns": len(r.turns),
            "cracked_on_turn": r.cracked_on_turn,
        })

    # Phase display label
    phase_labels = {
        GamePhase.SETUP: "Preparing",
        GamePhase.FORTIFICATION: "Defender Fortifying",
        GamePhase.SANITY_CHECK: "Sanity Check",
        GamePhase.SIEGE: "Siege in Progress",
        GamePhase.INTERMISSION: "Round Complete",
        GamePhase.COMPLETED: "Match Over",
    }

    return templates.TemplateResponse(request, "arena_spectate.html", {
        "room_code": room.code,
        "phase": phase.value,
        "phase_label": phase_labels.get(phase, "Unknown"),
        "current_turns": current_turns,
        "current_password": current_password,
        "rounds_history": rounds_history,
        "attacker_joined": room.attacker_token is not None,
        **_round_context(engine),
    })
