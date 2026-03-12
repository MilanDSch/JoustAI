"""Standalone leaderboard route for the Big Board display."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.leaderboard import get_top_entries

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(request: Request):
    entries = get_top_entries(limit=10)
    return templates.TemplateResponse(request, "leaderboard.html", {
        "entries": entries,
    })
