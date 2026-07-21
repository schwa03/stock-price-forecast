"""add backtest_result table

Revision ID: 2acd878b1839
Revises: 39916044119f
Create Date: 2026-07-18 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2acd878b1839'
down_revision: Union[str, Sequence[str], None] = '39916044119f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "backtest_result",
        sa.Column("stock_code", sa.String(length=16), primary_key=True),
        sa.Column("trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_return", sa.Float(), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(length=32), nullable=False, server_default=""),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("backtest_result")
