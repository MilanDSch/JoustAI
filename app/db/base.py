"""SQLAlchemy async engine and session factory.

Swap backends by changing DATABASE_URL in your .env:
  - SQLite  : sqlite+aiosqlite:///./leaderboard.db  (default)
  - Postgres: postgresql+asyncpg://user:pass@host/db
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


engine = create_async_engine(settings.database_url, echo=False)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables that don't exist yet."""
    from app.db import models as _models  # noqa: F401 – ensure models are registered

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """FastAPI dependency that yields a database session."""
    async with async_session() as session:
        yield session
