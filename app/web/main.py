"""FastAPI application for the AI CTF Duel hot-seat game."""

from fastapi import FastAPI, Request
from fastapi.responses import Response

from app.web.routes import game, pve

app = FastAPI(title="AI CTF Duel")
app.include_router(game.router)
app.include_router(pve.router)


@app.middleware("http")
async def no_cache_headers(request: Request, call_next):
    """Prevent browser caching so the back button can't leak defender info."""
    response: Response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    return response
