"""algo_orders admin_id tenant column

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-07-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "l1m2n3o4p5q6"
down_revision = "k0l1m2n3o4p5"
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
    connection = op.get_bind()
    primary_id = _primary_customer_admin_id(connection)

    with op.batch_alter_table("algo_orders") as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_algo_orders_admin_id", ["admin_id"], unique=False)

    if primary_id:
        connection.execute(
            sa.text(
                """
                UPDATE algo_orders
                SET admin_id = (
                    SELECT p.admin_id FROM positions p WHERE p.id = algo_orders.position_id LIMIT 1
                )
                WHERE admin_id IS NULL
                """
            )
        )
        connection.execute(
            sa.text("UPDATE algo_orders SET admin_id = :aid WHERE admin_id IS NULL"),
            {"aid": primary_id},
        )


def downgrade() -> None:
    with op.batch_alter_table("algo_orders") as batch_op:
        batch_op.drop_index("ix_algo_orders_admin_id")
        batch_op.drop_column("admin_id")
