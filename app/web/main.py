"""FastAPI application for the AI CTF Duel hot-seat game."""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles

from app.services.leaderboard import init_db
from app.web.routes import arena, game, leaderboard, pve

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    expected_username = settings.app_username
    expected_password = settings.app_password

    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication is not configured on the server."
        )

    correct_username = secrets.compare_digest(credentials.username, expected_username)
    correct_password = secrets.compare_digest(credentials.password, expected_password)

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

app = FastAPI(
    title="AI CTF Duel",
    dependencies=[Depends(verify_credentials)],
    lifespan=lifespan,
)

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(game.router)
app.include_router(pve.router)
app.include_router(leaderboard.router)
app.include_router(arena.router)


@app.middleware("http")
async def no_cache_headers(request: Request, call_next):
    """Prevent browser caching so the back button can't leak defender info.

    Static assets (CSS, JS, images) are excluded so browsers can cache them.
    """
    response: Response = await call_next(request)
    if not request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    return response