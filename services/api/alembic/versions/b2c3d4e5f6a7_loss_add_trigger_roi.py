"""loss_add_trigger_roi_pct kolonu

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-11
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.add_column(
            sa.Column("loss_add_trigger_roi_pct", sa.Numeric(precision=10, scale=4), nullable=True)
        )
    op.execute(
        "UPDATE bot_settings SET loss_add_trigger_roi_pct = 25 WHERE loss_add_trigger_roi_pct IS NULL"
    )
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column("loss_add_trigger_roi_pct", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.drop_column("loss_add_trigger_roi_pct")
