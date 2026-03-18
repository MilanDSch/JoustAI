"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LeaderboardEntry(Base):
    __tablename__ = "leaderboard"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    background: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False)
    highest_level: Mapped[int] = mapped_column(Integer, nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    

    def __repr__(self) -> str:
        return f"<LeaderboardEntry {self.name} lvl={self.highest_level}>"
