"""Standalone leaderboard route for the Big Board display."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.pve_engine import TOTAL_VAULTS
from app.db.base import get_session
from app.services.leaderboard import get_top_entries

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/leaderboard", response_class=HTMLResponse)
async def leaderboard_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    event = settings.active_event
    entries = await get_top_entries(session, limit=10, event=event)
    return templates.TemplateResponse(request, "leaderboard.html", {
        "entries": entries,
        "total_vaults": TOTAL_VAULTS,
        "active_event": event,
    })
