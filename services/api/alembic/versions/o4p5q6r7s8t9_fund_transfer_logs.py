"""Fon transfer log tablosu

Revision ID: o4p5q6r7s8t9
Revises: n3o4p5q6r7s8
Create Date: 2026-07-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o4p5q6r7s8t9"
down_revision = "n3o4p5q6r7s8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fund_transfer_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("customer_id", sa.String(length=36), nullable=False),
        sa.Column("platform_admin_id", sa.String(length=36), nullable=False),
        sa.Column("amount_usdt", sa.Numeric(18, 8), nullable=False),
        sa.Column("withdraw_fee_usdt", sa.Numeric(18, 8), nullable=True),
        sa.Column("futures_transferred_usdt", sa.Numeric(18, 8), nullable=True),
        sa.Column("spot_balance_before_usdt", sa.Numeric(18, 8), nullable=True),
        sa.Column("destination_address", sa.String(length=128), nullable=False),
        sa.Column("network", sa.String(length=32), nullable=False),
        sa.Column("binance_withdraw_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fund_transfer_logs_customer_id", "fund_transfer_logs", ["customer_id"], unique=False)
    op.create_index("ix_fund_transfer_logs_platform_admin_id", "fund_transfer_logs", ["platform_admin_id"], unique=False)
    op.create_index("ix_fund_transfer_logs_status", "fund_transfer_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fund_transfer_logs_status", table_name="fund_transfer_logs")
    op.drop_index("ix_fund_transfer_logs_platform_admin_id", table_name="fund_transfer_logs")
    op.drop_index("ix_fund_transfer_logs_customer_id", table_name="fund_transfer_logs")
    op.drop_table("fund_transfer_logs")
