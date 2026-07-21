"""drop unused risk_score column

Revision ID: 51a6951ce71f
Revises: e31900ba78e0
Create Date: 2026-07-21 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '51a6951ce71f'
down_revision: Union[str, Sequence[str], None] = 'e31900ba78e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # risk_scoreは実装当初から常に固定値(50または0)しか書き込まれておらず、
    # フロントエンドでも一切表示に使われていなかった旧プロトタイプの残骸。
    # 全ファイル監査（2026-07-21）で発見し削除する。
    op.drop_column("signal_summary", "risk_score")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "signal_summary",
        sa.Column("risk_score", sa.Integer(), nullable=False, server_default="50"),
    )
