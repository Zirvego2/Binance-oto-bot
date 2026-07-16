"""limit_entry_max_pending kolonu

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.add_column(sa.Column("limit_entry_max_pending", sa.Integer(), nullable=True))
    op.execute("UPDATE bot_settings SET limit_entry_max_pending = 3 WHERE limit_entry_max_pending IS NULL")
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column("limit_entry_max_pending", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.drop_column("limit_entry_max_pending")
