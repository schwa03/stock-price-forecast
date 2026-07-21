"""add fundamentals table

Revision ID: e31900ba78e0
Revises: a689735f9336
Create Date: 2026-07-21 13:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e31900ba78e0'
down_revision: Union[str, Sequence[str], None] = 'a689735f9336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "fundamentals",
        sa.Column("stock_code", sa.String(length=16), primary_key=True),
        sa.Column("per", sa.Float(), nullable=True),
        sa.Column("pbr", sa.Float(), nullable=True),
        sa.Column("dividend_yield", sa.Float(), nullable=True),
        sa.Column("earnings_growth", sa.Float(), nullable=True),
        sa.Column("updated_at", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("fundamentals")
