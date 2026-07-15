"""add news_updated_at to signal_summary

Revision ID: 39916044119f
Revises: 23932e3a65a8
Create Date: 2026-07-15 21:51:38.876831

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '39916044119f'
down_revision: Union[str, Sequence[str], None] = '23932e3a65a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "signal_summary",
        sa.Column("news_updated_at", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("signal_summary", "news_updated_at")
