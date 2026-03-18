"""create leaderboard table

Revision ID: aefe2282fa4d
Revises:
Create Date: 2026-03-18 11:35:05.382629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aefe2282fa4d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "leaderboard",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("company", sa.String, nullable=True),
        sa.Column("email", sa.String, nullable=False),
        sa.Column("highest_level", sa.Integer, nullable=False),
        sa.Column("total_turns", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("leaderboard")
