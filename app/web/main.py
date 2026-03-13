"""FastAPI application for the AI CTF Duel hot-seat game."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from app.services.leaderboard import init_db
from app.web.routes import game, leaderboard, pve

app = FastAPI(title="AI CTF Duel")

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(game.router)
app.include_router(pve.router)
app.include_router(leaderboard.router)


@app.on_event("startup")
async def startup():
    init_db()


@app.middleware("http")
async def no_cache_headers(request: Request, call_next):
    """Prevent browser caching so the back button can't leak defender info."""
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response
