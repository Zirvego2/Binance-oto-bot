"""admin role and approval status

Revision ID: h8i9j0k1l2m3
Revises: g7b8c9d0e1f2
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h8i9j0k1l2m3"
down_revision = "g7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=32), nullable=False, server_default="customer"))
        batch_op.add_column(
            sa.Column("approval_status", sa.String(length=32), nullable=False, server_default="approved")
        )
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("approved_by_admin_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("blocked_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch_op.create_index("ix_admins_role", ["role"], unique=False)
        batch_op.create_index("ix_admins_approval_status", ["approval_status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.drop_index("ix_admins_approval_status")
        batch_op.drop_index("ix_admins_role")
        batch_op.drop_column("notes")
        batch_op.drop_column("blocked_reason")
        batch_op.drop_column("approved_by_admin_id")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approval_status")
        batch_op.drop_column("role")
