"""customer profile fields and tenant admin_id

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def _primary_customer_admin_id(connection) -> str | None:
    row = connection.execute(
        sa.text(
            "SELECT id FROM admins WHERE role = 'customer' AND approval_status = 'approved' "
            "ORDER BY created_at ASC LIMIT 1"
        )
    ).fetchone()
    if row:
        return row[0]
    row = connection.execute(sa.text("SELECT id FROM admins ORDER BY created_at ASC LIMIT 1")).fetchone()
    return row[0] if row else None


def upgrade() -> None:
    with op.batch_alter_table("admins") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("district", sa.String(length=64), nullable=True))

    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_bot_settings_admin_id", ["admin_id"], unique=True)

    with op.batch_alter_table("bot_runtime_status") as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_bot_runtime_status_admin_id", ["admin_id"], unique=True)

    for table in ("positions", "orders", "trades"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("admin_id", sa.String(length=36), nullable=True))
            batch_op.create_index(f"ix_{table}_admin_id", ["admin_id"], unique=False)

    connection = op.get_bind()
    primary_id = _primary_customer_admin_id(connection)
    if primary_id:
        connection.execute(
            sa.text("UPDATE bot_settings SET admin_id = :aid WHERE admin_id IS NULL"),
            {"aid": primary_id},
        )
        connection.execute(
            sa.text("UPDATE bot_runtime_status SET admin_id = :aid WHERE admin_id IS NULL"),
            {"aid": primary_id},
        )
        for table in ("positions", "orders", "trades"):
            connection.execute(
                sa.text(f"UPDATE {table} SET admin_id = :aid WHERE admin_id IS NULL"),
                {"aid": primary_id},
            )


def downgrade() -> None:
    for table in ("trades", "orders", "positions"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_admin_id")
            batch_op.drop_column("admin_id")

    with op.batch_alter_table("bot_runtime_status") as batch_op:
        batch_op.drop_index("ix_bot_runtime_status_admin_id")
        batch_op.drop_column("admin_id")

    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.drop_index("ix_bot_settings_admin_id")
        batch_op.drop_column("admin_id")

    with op.batch_alter_table("admins") as batch_op:
        batch_op.drop_column("district")
        batch_op.drop_column("city")
        batch_op.drop_column("phone")
