"""telegram_delivery_logs tablosu

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-07-14
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "m2n3o4p5q6r7"
down_revision = "l1m2n3o4p5q6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_delivery_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_id", sa.String(length=36), nullable=True),
        sa.Column("message_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("skip_reason", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("chat_id_masked", sa.String(length=32), nullable=True),
        sa.Column("bot_id_masked", sa.String(length=32), nullable=True),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="worker"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_delivery_logs")),
    )
    op.create_index(op.f("ix_telegram_delivery_logs_admin_id"), "telegram_delivery_logs", ["admin_id"], unique=False)
    op.create_index(op.f("ix_telegram_delivery_logs_message_type"), "telegram_delivery_logs", ["message_type"], unique=False)
    op.create_index(op.f("ix_telegram_delivery_logs_status"), "telegram_delivery_logs", ["status"], unique=False)
    op.create_index(op.f("ix_telegram_delivery_logs_skip_reason"), "telegram_delivery_logs", ["skip_reason"], unique=False)
    op.create_index(op.f("ix_telegram_delivery_logs_symbol"), "telegram_delivery_logs", ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_delivery_logs_symbol"), table_name="telegram_delivery_logs")
    op.drop_index(op.f("ix_telegram_delivery_logs_skip_reason"), table_name="telegram_delivery_logs")
    op.drop_index(op.f("ix_telegram_delivery_logs_status"), table_name="telegram_delivery_logs")
    op.drop_index(op.f("ix_telegram_delivery_logs_message_type"), table_name="telegram_delivery_logs")
    op.drop_index(op.f("ix_telegram_delivery_logs_admin_id"), table_name="telegram_delivery_logs")
    op.drop_table("telegram_delivery_logs")
