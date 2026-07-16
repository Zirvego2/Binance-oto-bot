"""firebase_uid kolonu

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.add_column(sa.Column("firebase_uid", sa.String(length=128), nullable=True))
        batch_op.create_index("ix_admins_firebase_uid", ["firebase_uid"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.drop_index("ix_admins_firebase_uid")
        batch_op.drop_column("firebase_uid")
