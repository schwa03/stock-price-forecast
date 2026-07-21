"""add macro_news_item table

Revision ID: a689735f9336
Revises: 2acd878b1839
Create Date: 2026-07-21 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a689735f9336'
down_revision: Union[str, Sequence[str], None] = '2acd878b1839'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "macro_news_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("cls", sa.String(length=16), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("macro_news_item")
