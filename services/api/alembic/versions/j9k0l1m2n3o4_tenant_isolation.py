"""tenant isolation: daily stats, binance status, symbol rules

Revision ID: j9k0l1m2n3o4
Revises: i9j0k1l2m3n4
Create Date: 2026-07-13
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "j9k0l1m2n3o4"
down_revision = "i9j0k1l2m3n4"
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
    primary_id = _primary_customer_admin_id(connection) or "legacy"

    with op.batch_alter_table("daily_statistics") as batch_op:
        batch_op.add_column(sa.Column("admin_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_daily_statistics_admin_id", ["admin_id"], unique=False)

    connection.execute(
        sa.text("UPDATE daily_statistics SET admin_id = :aid WHERE admin_id IS NULL"),
        {"aid": primary_id},
    )

    # binance_connection_status: (admin_id, id) birlesik PK
    op.rename_table("binance_connection_status", "binance_connection_status_legacy")
    op.create_table(
        "binance_connection_status",
        sa.Column("admin_id", sa.String(length=36), primary_key=True),
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column("is_configured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("account_access_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("futures_account_usable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("trading_permission_ok", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("position_mode_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("multi_assets_mode_off_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_message", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    legacy = connection.execute(sa.text("SELECT * FROM binance_connection_status_legacy")).fetchall()
    for row in legacy:
        connection.execute(
            sa.text(
                """
                INSERT INTO binance_connection_status (
                    admin_id, id, is_configured, is_connected, account_access_ok,
                    futures_account_usable, trading_permission_ok, position_mode_verified,
                    multi_assets_mode_off_verified, last_success_at, last_error_at,
                    last_error_message, created_at, updated_at
                ) VALUES (
                    :admin_id, :id, :is_configured, :is_connected, :account_access_ok,
                    :futures_account_usable, :trading_permission_ok, :position_mode_verified,
                    :multi_assets_mode_off_verified, :last_success_at, :last_error_at,
                    :last_error_message, :created_at, :updated_at
                )
                """
            ),
            {
                "admin_id": primary_id,
                "id": row[0],
                "is_configured": row[1],
                "is_connected": row[2],
                "account_access_ok": row[3],
                "futures_account_usable": row[4],
                "trading_permission_ok": row[5],
                "position_mode_verified": row[6],
                "multi_assets_mode_off_verified": row[7],
                "last_success_at": row[8],
                "last_error_at": row[9],
                "last_error_message": row[10],
                "created_at": row[11],
                "updated_at": row[12],
            },
        )
    op.drop_table("binance_connection_status_legacy")

    # symbol_rules: sembol PK -> (admin_id, symbol) benzersiz yapisi
    op.rename_table("symbol_rules", "symbol_rules_legacy")
    op.create_table(
        "symbol_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("admin_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("in_analysis_list", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_blacklisted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blacklist_reason", sa.String(length=255), nullable=True),
        sa.Column("long_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("short_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_leverage_override", sa.Integer(), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_signal_id", sa.String(length=36), nullable=True),
        sa.Column("last_trade_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("admin_id", "symbol", name="uq_symbol_rules_admin_symbol"),
    )
    op.create_index("ix_symbol_rules_admin_id", "symbol_rules", ["admin_id"], unique=False)
    op.create_index("ix_symbol_rules_symbol", "symbol_rules", ["symbol"], unique=False)

    legacy_rules = connection.execute(sa.text("SELECT * FROM symbol_rules_legacy")).fetchall()
    for row in legacy_rules:
        connection.execute(
            sa.text(
                """
                INSERT INTO symbol_rules (
                    id, admin_id, symbol, in_analysis_list, is_blacklisted, blacklist_reason,
                    long_enabled, short_enabled, max_leverage_override, cooldown_until,
                    last_signal_id, last_trade_at, notes, created_at, updated_at
                ) VALUES (
                    :id, :admin_id, :symbol, :in_analysis_list, :is_blacklisted, :blacklist_reason,
                    :long_enabled, :short_enabled, :max_leverage_override, :cooldown_until,
                    :last_signal_id, :last_trade_at, :notes, :created_at, :updated_at
                )
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "admin_id": primary_id,
                "symbol": row[0],
                "in_analysis_list": row[1],
                "is_blacklisted": row[2],
                "blacklist_reason": row[3],
                "long_enabled": row[4],
                "short_enabled": row[5],
                "max_leverage_override": row[6],
                "cooldown_until": row[7],
                "last_signal_id": row[8],
                "last_trade_at": row[9],
                "notes": row[10],
                "created_at": row[11],
                "updated_at": row[12],
            },
        )
    op.drop_table("symbol_rules_legacy")


def downgrade() -> None:
    raise NotImplementedError("Tenant isolation migration geri alinamaz")
