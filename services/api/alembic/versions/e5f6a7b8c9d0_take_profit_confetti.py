"""take_profit_confetti_enabled kolonu

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.add_column(sa.Column("take_profit_confetti_enabled", sa.Boolean(), nullable=True))
    op.execute(
        "UPDATE bot_settings SET take_profit_confetti_enabled = TRUE "
        "WHERE take_profit_confetti_enabled IS NULL"
    )
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column("take_profit_confetti_enabled", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.drop_column("take_profit_confetti_enabled")
