"""initial schema

Revision ID: 23932e3a65a8
Revises:
Create Date: 2026-07-15 17:29:56.473923

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '23932e3a65a8'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "stock_master",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("name_ja", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("sector", sa.String(length=255), nullable=False, server_default=""),
    )

    op.create_table(
        "signal_summary",
        sa.Column("code", sa.String(length=16), primary_key=True),
        sa.Column("short_score", sa.Integer(), nullable=False),
        sa.Column("long_score", sa.Integer(), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Integer(), nullable=False),
        sa.Column("final_signal", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False, server_default=""),
    )

    op.create_table(
        "news_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("stock_code", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("cls", sa.String(length=16), nullable=False),
    )
    op.create_index("ix_news_item_stock_code", "news_item", ["stock_code"])

    op.create_table(
        "doc_item",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("stock_code", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=1024), nullable=False),
        sa.Column("cls", sa.String(length=16), nullable=False),
    )
    op.create_index("ix_doc_item_stock_code", "doc_item", ["stock_code"])

    op.create_table(
        "chart_data",
        sa.Column("stock_code", sa.String(length=16), primary_key=True),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column("prices", postgresql.JSONB(), nullable=False),
        sa.Column("ma5", postgresql.JSONB(), nullable=False),
        sa.Column("ma25", postgresql.JSONB(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("chart_data")
    op.drop_index("ix_doc_item_stock_code", table_name="doc_item")
    op.drop_table("doc_item")
    op.drop_index("ix_news_item_stock_code", table_name="news_item")
    op.drop_table("news_item")
    op.drop_table("signal_summary")
    op.drop_table("stock_master")
