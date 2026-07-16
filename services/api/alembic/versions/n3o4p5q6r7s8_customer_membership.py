"""Musteri uyelik alanlari ve mevcut musterilere 5 yil tanimi

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-07-15
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from alembic import op

revision = "n3o4p5q6r7s8"
down_revision = "m2n3o4p5q6r7"
branch_labels = None
depends_on = None

LEGACY_DAYS = 5 * 365


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.add_column(sa.Column("membership_plan", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("membership_starts_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("membership_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_admins_membership_expires_at", ["membership_expires_at"], unique=False)

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT id, approved_at, created_at
            FROM admins
            WHERE role = 'customer'
              AND approval_status = 'approved'
              AND membership_expires_at IS NULL
            """
        )
    ).fetchall()

    now = datetime.now(timezone.utc)
    for row in rows:
        anchor = row.approved_at or row.created_at or now
        if isinstance(anchor, str):
            anchor = datetime.fromisoformat(anchor.replace("Z", "+00:00"))
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        expires_at = anchor + timedelta(days=LEGACY_DAYS)
        bind.execute(
            sa.text(
                """
                UPDATE admins
                SET membership_plan = :plan,
                    membership_starts_at = :starts_at,
                    membership_expires_at = :expires_at
                WHERE id = :admin_id
                """
            ),
            {
                "plan": "legacy_5y",
                "starts_at": anchor,
                "expires_at": expires_at,
                "admin_id": row.id,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.drop_index("ix_admins_membership_expires_at")
        batch_op.drop_column("membership_expires_at")
        batch_op.drop_column("membership_starts_at")
        batch_op.drop_column("membership_plan")
