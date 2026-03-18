"""Async leaderboard service backed by SQLAlchemy."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LeaderboardEntry


async def add_entry(
    session: AsyncSession,
    name: str,
    company: str | None,
    background: str | None,
    email: str,
    highest_level: int,
    total_turns: int,
    event: str = "default",
) -> int:
    """Insert a leaderboard entry and return its ID."""
    entry = LeaderboardEntry(
        name=name,
        company=company,
        background=background,
        email=email,
        highest_level=highest_level,
        total_turns=total_turns,
        event=event,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry.id


async def get_all_entries(session: AsyncSession) -> list[dict]:
    """Return all leaderboard entries across all events."""
    stmt = (
        select(LeaderboardEntry)
        .order_by(LeaderboardEntry.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "company": r.company,
            "background": r.background,
            "email": r.email,
            "highest_level": r.highest_level,
            "total_turns": r.total_turns,
            "event": r.event,
            "created_at": r.created_at,
        }
        for r in rows
    ]


async def delete_entry(session: AsyncSession, entry_id: int) -> bool:
    """Delete a leaderboard entry by ID. Returns True if found and deleted."""
    stmt = select(LeaderboardEntry).where(LeaderboardEntry.id == entry_id)
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is None:
        return False
    await session.delete(entry)
    await session.commit()
    return True


async def update_entry_event(session: AsyncSession, entry_id: int, new_event: str) -> bool:
    """Reassign a leaderboard entry to a different event. Returns True if found."""
    stmt = select(LeaderboardEntry).where(LeaderboardEntry.id == entry_id)
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is None:
        return False
    entry.event = new_event
    await session.commit()
    return True


async def get_top_entries(session: AsyncSession, limit: int = 10, event: str = "default") -> list[dict]:
    """Return top leaderboard entries for the given event, ordered by highest level DESC, then fewest turns ASC."""
    stmt = (
        select(LeaderboardEntry)
        .where(LeaderboardEntry.event == event)
        .order_by(
            LeaderboardEntry.highest_level.desc(),
            LeaderboardEntry.total_turns.asc(),
            LeaderboardEntry.created_at.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "name": r.name,
            "company": r.company,
            "background": r.background,
            "highest_level": r.highest_level,
            "total_turns": r.total_turns,
            "created_at": r.created_at,
        }
        for r in rows
    ]
