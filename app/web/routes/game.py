"""Game routes for the hot-seat web interface."""

from fastapi import APIRouter, Cookie, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.engine import SHADOW_PROMPT_INTRO, SHADOW_PROMPT_OUTRO
from app.core.logger import get_logger
from app.models.game import GamePhase, GameResult
from app.web.sessions import create_session, destroy_session, get_session

logger = get_logger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

PHASE_REDIRECTS = {
    GamePhase.SETUP: "/",
    GamePhase.FORTIFICATION: "/game/defend",
    GamePhase.SANITY_CHECK: "/game/defend",
    GamePhase.SIEGE: "/game/siege",
    GamePhase.COMPLETED: "/game/results",
}


def _get_engine(session_id: str | None):
    """Get engine from session cookie, or None."""
    if not session_id:
        return None
    return get_session(session_id)


def _phase_redirect(engine, expected: GamePhase) -> RedirectResponse | None:
    """If engine phase doesn't match expected, return a redirect."""
    if engine.game.phase != expected:
        target = PHASE_REDIRECTS.get(engine.game.phase, "/")
        return RedirectResponse(url=target, status_code=303)
    return None


# --- Start ---

@router.get("/", response_class=HTMLResponse)
async def start_page(request: Request):
    return templates.TemplateResponse(request, "start.html")


@router.post("/game/new")
async def new_game():
    session_id, engine = create_session()
    engine.game.phase = GamePhase.FORTIFICATION
    logger.info("Session created: %s", session_id)
    response = RedirectResponse(url="/game/defend", status_code=303)
    response.set_cookie(
        key="joust_session",
        value=session_id,
        httponly=True,
        samesite="strict",
    )
    return response


# --- Defender ---

@router.get("/game/defend", response_class=HTMLResponse)
async def defend_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.FORTIFICATION)
    if redirect:
        return redirect

    password = engine.game.secret_password
    return templates.TemplateResponse(request, "defend.html", {
        "errors": [],
        "system_prompt": "",
        "max_prompt_length": engine.game.max_prompt_length,
        "secret_password": password,
        "shadow_intro": SHADOW_PROMPT_INTRO.replace("{secret_password}", password),
        "shadow_outro": SHADOW_PROMPT_OUTRO,
    })


@router.post("/game/defend", response_class=HTMLResponse)
async def defend_submit(
    request: Request,
    system_prompt: str = Form(...),
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.FORTIFICATION)
    if redirect:
        return redirect

    password = engine.game.secret_password
    errors: list[str] = []

    if not system_prompt.strip():
        logger.warning("Bad request: empty system prompt submitted")

    def _defend_context(extra_errors: list[str] | None = None):
        return {
            "errors": extra_errors or errors,
            "system_prompt": system_prompt,
            "max_prompt_length": engine.game.max_prompt_length,
            "secret_password": password,
            "shadow_intro": SHADOW_PROMPT_INTRO.replace("{secret_password}", password),
            "shadow_outro": SHADOW_PROMPT_OUTRO,
        }

    try:
        sanity_result = engine.setup_defense(system_prompt)
    except ValueError as e:
        logger.warning("Defense setup rejected: %s", e)
        errors.append(str(e))
        return templates.TemplateResponse(request, "defend.html", _defend_context())

    if not sanity_result.passed:
        errors.append("Sanity check failed — your prompt is too restrictive.")
        for failure in sanity_result.failures:
            errors.append(failure)
        return templates.TemplateResponse(request, "defend.html", _defend_context())

    # Sanity passed — phase is now SIEGE
    return RedirectResponse(url="/game/handoff", status_code=303)


# --- Handoff ---

@router.get("/game/handoff", response_class=HTMLResponse)
async def handoff_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.SIEGE)
    if redirect:
        return redirect

    return templates.TemplateResponse(request, "handoff.html")


@router.post("/game/handoff")
async def handoff_confirm(joust_session: str | None = Cookie(default=None)):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/game/siege", status_code=303)


# --- Siege ---

@router.get("/game/siege", response_class=HTMLResponse)
async def siege_page(
    request: Request,
    error: str | None = None,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    # Allow viewing siege page when completed (will show game_over state)
    if engine.game.phase not in (GamePhase.SIEGE, GamePhase.COMPLETED):
        redirect = _phase_redirect(engine, GamePhase.SIEGE)
        if redirect:
            return redirect

    # If completed, redirect to results
    if engine.game.phase == GamePhase.COMPLETED:
        return RedirectResponse(url="/game/results", status_code=303)

    return templates.TemplateResponse(request, "siege.html", {
        "turns": engine.game.round.turns,
        "turns_remaining": engine.game.turns_remaining,
        "game_over": engine.game.is_siege_over,
        "error": error,
    })


@router.post("/game/attack")
async def attack_submit(
    attacker_prompt: str = Form(...),
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(
            url=PHASE_REDIRECTS.get(engine.game.phase, "/"),
            status_code=303,
        )
    
    engine.attack(attacker_prompt)

    if engine.game.phase == GamePhase.COMPLETED:
        return RedirectResponse(url="/game/results", status_code=303)

    return RedirectResponse(url="/game/siege", status_code=303)


@router.post("/game/guess")
async def guess_submit(
    guess: str = Form(...),
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(
            url=PHASE_REDIRECTS.get(engine.game.phase, "/"),
            status_code=303,
        )

    engine.guess_password(guess)

    if engine.game.phase == GamePhase.COMPLETED:
        return RedirectResponse(url="/game/results", status_code=303)

    # Wrong guess but game continues
    return RedirectResponse(url="/game/siege?error=incorrect_guess", status_code=303)


@router.post("/game/surrender")
async def surrender(joust_session: str | None = Cookie(default=None)):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    engine.surrender()
    return RedirectResponse(url="/game/results", status_code=303)


# --- Results ---

@router.get("/game/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.COMPLETED)
    if redirect:
        return redirect

    game = engine.game
    setup = game.round.defender_setup

    return templates.TemplateResponse(request, "results.html", {
        "result": game.round.result.value if game.round.result else "draw",
        "password": setup.password if setup else "???",
        "cracked_on_turn": game.round.cracked_on_turn,
        "total_turns": len(game.round.turns),
        "max_turns": game.max_turns,
        "turns": game.round.turns,
    })


@router.post("/game/restart")
async def restart_game(joust_session: str | None = Cookie(default=None)):
    if joust_session:
        destroy_session(joust_session)
        logger.info("Session destroyed: %s", joust_session)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("joust_session")
    return response
