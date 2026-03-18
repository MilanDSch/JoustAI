"""PvE routes for the Beat Delaware single-player mode."""

from fastapi import APIRouter, Cookie, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logger import get_logger
from app.core.pve_engine import PvEEngine, TOTAL_VAULTS
from app.data.vaults import get_vault
from app.db.base import get_session as get_db_session
from app.models.game import GamePhase, GameResult
from app.services.leaderboard import add_entry
from app.web.sessions import create_pve_session, destroy_session, get_session

logger = get_logger(__name__)

router = APIRouter(prefix="/pve")
templates = Jinja2Templates(directory="app/web/templates")

PVE_PHASE_REDIRECTS = {
    GamePhase.SETUP: "/",
    GamePhase.FORTIFICATION: "/",
    GamePhase.SANITY_CHECK: "/",
    GamePhase.SIEGE: "/pve/siege",
    GamePhase.INTERMISSION: "/pve/intermission",
    GamePhase.COMPLETED: "/pve/results",
}


def _get_pve_engine(session_id: str | None) -> PvEEngine | None:
    """Get PvE engine from session cookie, or None."""
    if not session_id:
        return None
    engine = get_session(session_id)
    if engine and isinstance(engine, PvEEngine):
        return engine
    return None


def _phase_redirect(engine: PvEEngine, expected: GamePhase) -> RedirectResponse | None:
    if engine.game.phase != expected:
        target = PVE_PHASE_REDIRECTS.get(engine.game.phase, "/")
        return RedirectResponse(url=target, status_code=303)
    return None


def _round_context(engine: PvEEngine) -> dict:
    """Common round context for PvE templates."""
    game = engine.game
    vault = engine.current_vault
    return {
        "round_number": game.round_number,
        "max_rounds": game.max_rounds,
        "attacker_score": game.attacker_score,
        "attacker_label": game.attacker_label,
        "unlock_tier": game.unlock_tier,
        "is_pve": True,
        "url_prefix": "/pve",
        "vault_name": vault.name,
        "vault_difficulty": vault.difficulty,
        "vault_level": vault.level,
    }


# --- New Game ---

@router.post("/new")
async def new_pve_game():
    session_id, engine = create_pve_session()
    logger.info("PvE session created: %s", session_id)
    response = RedirectResponse(url="/pve/vault", status_code=303)
    response.set_cookie(
        key="joust_session",
        value=session_id,
        httponly=True,
        samesite="strict",
    )
    return response


# --- Vault Intro ---

@router.get("/vault", response_class=HTMLResponse)
async def vault_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.SIEGE)
    if redirect:
        return redirect

    vault = engine.current_vault
    return templates.TemplateResponse(request, "pve_vault.html", {
        "vault": vault,
        **_round_context(engine),
    })


# --- Siege ---

@router.get("/siege", response_class=HTMLResponse)
async def siege_page(
    request: Request,
    error: str | None = None,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase not in (GamePhase.SIEGE, GamePhase.COMPLETED, GamePhase.INTERMISSION):
        redirect = _phase_redirect(engine, GamePhase.SIEGE)
        if redirect:
            return redirect

    if engine.game.phase in (GamePhase.COMPLETED, GamePhase.INTERMISSION):
        target = PVE_PHASE_REDIRECTS[engine.game.phase]
        return RedirectResponse(url=target, status_code=303)

    return templates.TemplateResponse(request, "siege.html", {
        "turns": engine.game.round.turns,
        "turns_remaining": engine.game.turns_remaining,
        "game_over": engine.game.is_siege_over,
        "is_last_turn": engine.game.turns_remaining == 1,
        "error": error,
        **_round_context(engine),
    })


@router.post("/attack")
async def attack_submit(
    attacker_prompt: str = Form(...),
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(
            url=PVE_PHASE_REDIRECTS.get(engine.game.phase, "/"),
            status_code=303,
        )

    engine.attack(attacker_prompt)

    if engine.game.round.result is not None:
        target = PVE_PHASE_REDIRECTS[engine.game.phase]
        return RedirectResponse(url=target, status_code=303)

    return RedirectResponse(url="/pve/siege", status_code=303)


@router.post("/guess")
async def guess_submit(
    guess: str = Form(...),
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase != GamePhase.SIEGE:
        return RedirectResponse(
            url=PVE_PHASE_REDIRECTS.get(engine.game.phase, "/"),
            status_code=303,
        )

    engine.guess_password(guess)

    if engine.game.round.result is not None:
        target = PVE_PHASE_REDIRECTS[engine.game.phase]
        return RedirectResponse(url=target, status_code=303)

    return RedirectResponse(url="/pve/siege?error=incorrect_guess", status_code=303)


@router.post("/surrender")
async def surrender(joust_session: str | None = Cookie(default=None)):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    engine.surrender()
    target = PVE_PHASE_REDIRECTS[engine.game.phase]
    return RedirectResponse(url=target, status_code=303)


# --- Intermission ---

@router.get("/intermission", response_class=HTMLResponse)
async def intermission_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.INTERMISSION)
    if redirect:
        return redirect

    game = engine.game
    setup = game.round.defender_setup

    # Get next vault info for the intermission message
    next_vault = None
    if game.vault_level < game.max_rounds:
        next_vault = get_vault(game.vault_level + 1)

    return templates.TemplateResponse(request, "intermission.html", {
        "last_result": game.round.result.value if game.round.result else "draw",
        "password": setup.password if setup else "???",
        "total_turns": len(game.round.turns),
        "max_turns": game.max_turns,
        "next_vault": next_vault,
        **_round_context(engine),
    })


@router.post("/next-round")
async def next_round(joust_session: str | None = Cookie(default=None)):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    engine.next_round()
    return RedirectResponse(url="/pve/siege", status_code=303)


# --- Results ---

@router.get("/results", response_class=HTMLResponse)
async def results_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    redirect = _phase_redirect(engine, GamePhase.COMPLETED)
    if redirect:
        return redirect

    game = engine.game
    all_rounds = [*game.rounds_history, game.round]

    vaults_breached = sum(
        1 for r in all_rounds if r.result == GameResult.ATTACKER_WIN
    )

    highest_level = 0
    for i, r in enumerate(all_rounds, 1):
        if r.result == GameResult.ATTACKER_WIN:
            highest_level = i

    total_turns = sum(len(r.turns) for r in all_rounds)

    rounds_summary = []
    for i, r in enumerate(all_rounds, 1):
        vault = get_vault(i)
        rounds_summary.append({
            "number": i,
            "vault_name": vault.name,
            "vault_difficulty": vault.difficulty,
            "password": r.defender_setup.password if r.defender_setup else "???",
            "result": r.result.value if r.result else "draw",
            "total_turns": len(r.turns),
            "cracked_on_turn": r.cracked_on_turn,
        })

    return templates.TemplateResponse(request, "results.html", {
        "rounds_summary": rounds_summary,
        "max_turns": game.max_turns,
        "vaults_breached": vaults_breached,
        "highest_level": highest_level,
        "total_turns": total_turns,
        "total_vaults": TOTAL_VAULTS,
        "eligible_for_leaderboard": highest_level >= 1,
        **_round_context(engine),
    })


# --- Claim Score ---

@router.get("/claim", response_class=HTMLResponse)
async def claim_page(
    request: Request,
    joust_session: str | None = Cookie(default=None),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    if engine.game.phase != GamePhase.COMPLETED:
        return RedirectResponse(url="/", status_code=303)

    game = engine.game
    all_rounds = [*game.rounds_history, game.round]

    highest_level = 0
    for i, r in enumerate(all_rounds, 1):
        if r.result == GameResult.ATTACKER_WIN:
            highest_level = i

    total_turns = sum(len(r.turns) for r in all_rounds)

    if highest_level < 1:
        return RedirectResponse(url="/pve/results", status_code=303)

    return templates.TemplateResponse(request, "claim.html", {
        "highest_level": highest_level,
        "total_turns": total_turns,
        "total_vaults": TOTAL_VAULTS,
        **_round_context(engine),
    })


@router.post("/claim")
async def claim_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    company: str = Form(default=""),
    background: str = Form(default=""),
    joust_session: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    engine = _get_pve_engine(joust_session)
    if not engine:
        return RedirectResponse(url="/", status_code=303)

    game = engine.game
    all_rounds = [*game.rounds_history, game.round]

    # Recompute from session state (anti-tamper)
    highest_level = 0
    for i, r in enumerate(all_rounds, 1):
        if r.result == GameResult.ATTACKER_WIN:
            highest_level = i
    total_turns = sum(len(r.turns) for r in all_rounds)

    if highest_level < 1:
        return RedirectResponse(url="/pve/results", status_code=303)

    name = name.strip()
    email = email.strip()
    company = company.strip() or None
    background = background.strip() or None

    if not name or not email:
        return templates.TemplateResponse(request, "claim.html", {
            "highest_level": highest_level,
            "total_turns": total_turns,
            "error": "Name and email are required.",
            "name": name,
            "company": company or "",
            "background": background or "",
            "email": email,
            **_round_context(engine),
        })

    await add_entry(
        session=db,
        name=name,
        company=company,
        background=background,
        email=email,
        highest_level=highest_level,
        total_turns=total_turns,
        event=settings.active_event,
    )

    if joust_session:
        destroy_session(joust_session)
        logger.info("PvE session destroyed after claim: %s", joust_session)

    response = RedirectResponse(url="/leaderboard", status_code=303)
    response.delete_cookie("joust_session")
    return response


# --- Restart ---

@router.post("/restart")
async def restart_game(joust_session: str | None = Cookie(default=None)):
    if joust_session:
        destroy_session(joust_session)
        logger.info("PvE session destroyed: %s", joust_session)
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("joust_session")
    return response
