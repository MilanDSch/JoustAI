"""add event to leaderboard

Revision ID: c3f8a1e92d07
Revises: 27b9cfbcc4ab
Create Date: 2026-03-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f8a1e92d07'
down_revision: Union[str, Sequence[str], None] = '27b9cfbcc4ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('leaderboard', sa.Column('event', sa.String(), nullable=False, server_default='default'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('leaderboard', 'event')
