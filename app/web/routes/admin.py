"""Admin dashboard for leaderboard management."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.base import get_session
from app.services.leaderboard import delete_entry, get_all_entries, update_entry_event

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/web/templates")


@router.get("", response_class=HTMLResponse)
async def admin_page(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    entries = await get_all_entries(session)
    events = sorted({e["event"] for e in entries})
    return templates.TemplateResponse(request, "admin.html", {
        "entries": entries,
        "active_event": settings.active_event,
        "events": events,
    })


@router.post("/event")
async def update_event(new_event: str = Form(...)):
    settings.active_event = new_event
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/delete/{entry_id}")
async def delete_leaderboard_entry(
    entry_id: int,
    session: AsyncSession = Depends(get_session),
):
    await delete_entry(session, entry_id)
    return RedirectResponse(url="/admin", status_code=303)


@router.post("/reassign/{entry_id}")
async def reassign_entry(
    entry_id: int,
    new_event: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    await update_entry_event(session, entry_id, new_event)
    return RedirectResponse(url="/admin", status_code=303)
