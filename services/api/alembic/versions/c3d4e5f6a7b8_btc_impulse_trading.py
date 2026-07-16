"""BTC impuls islem ayarlari

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.add_column(sa.Column("impulse_mode", sa.String(16), nullable=True))
        batch_op.add_column(sa.Column("impulse_btc_min_change_pct", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_lookback_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_extreme_min_score", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_max_entries", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_margin_usdt", sa.Numeric(18, 8), nullable=True))
        batch_op.add_column(sa.Column("impulse_leverage", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_tp_roi_pct", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_sl_roi_pct", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_cooldown_minutes", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_top_n_scan", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_rsi_overbought", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_rsi_oversold", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_check_interval_seconds", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE bot_settings SET
            impulse_mode = COALESCE(impulse_mode, 'OFF'),
            impulse_btc_min_change_pct = COALESCE(impulse_btc_min_change_pct, 0.35),
            impulse_lookback_minutes = COALESCE(impulse_lookback_minutes, 3),
            impulse_extreme_min_score = COALESCE(impulse_extreme_min_score, 50),
            impulse_max_entries = COALESCE(impulse_max_entries, 3),
            impulse_margin_usdt = COALESCE(impulse_margin_usdt, 5),
            impulse_leverage = COALESCE(impulse_leverage, 8),
            impulse_tp_roi_pct = COALESCE(impulse_tp_roi_pct, 4),
            impulse_sl_roi_pct = COALESCE(impulse_sl_roi_pct, 20),
            impulse_cooldown_minutes = COALESCE(impulse_cooldown_minutes, 20),
            impulse_top_n_scan = COALESCE(impulse_top_n_scan, 25),
            impulse_rsi_overbought = COALESCE(impulse_rsi_overbought, 70),
            impulse_rsi_oversold = COALESCE(impulse_rsi_oversold, 30),
            impulse_check_interval_seconds = COALESCE(impulse_check_interval_seconds, 20)
        """
    )

    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.alter_column("impulse_mode", nullable=False)
        batch_op.alter_column("impulse_btc_min_change_pct", nullable=False)
        batch_op.alter_column("impulse_lookback_minutes", nullable=False)
        batch_op.alter_column("impulse_extreme_min_score", nullable=False)
        batch_op.alter_column("impulse_max_entries", nullable=False)
        batch_op.alter_column("impulse_margin_usdt", nullable=False)
        batch_op.alter_column("impulse_leverage", nullable=False)
        batch_op.alter_column("impulse_tp_roi_pct", nullable=False)
        batch_op.alter_column("impulse_sl_roi_pct", nullable=False)
        batch_op.alter_column("impulse_cooldown_minutes", nullable=False)
        batch_op.alter_column("impulse_top_n_scan", nullable=False)
        batch_op.alter_column("impulse_rsi_overbought", nullable=False)
        batch_op.alter_column("impulse_rsi_oversold", nullable=False)
        batch_op.alter_column("impulse_check_interval_seconds", nullable=False)

    with op.batch_alter_table("bot_runtime_status") as batch_op:
        batch_op.add_column(sa.Column("impulse_last_event_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("impulse_last_direction", sa.String(8), nullable=True))
        batch_op.add_column(sa.Column("impulse_last_btc_change_pct", sa.Numeric(10, 4), nullable=True))
        batch_op.add_column(sa.Column("impulse_last_opened_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("impulse_last_scan_at", sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE bot_runtime_status SET impulse_last_opened_count = 0 WHERE impulse_last_opened_count IS NULL")

    with op.batch_alter_table("bot_runtime_status") as batch_op:
        batch_op.alter_column("impulse_last_opened_count", nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("bot_runtime_status") as batch_op:
        batch_op.drop_column("impulse_last_scan_at")
        batch_op.drop_column("impulse_last_opened_count")
        batch_op.drop_column("impulse_last_btc_change_pct")
        batch_op.drop_column("impulse_last_direction")
        batch_op.drop_column("impulse_last_event_at")

    with op.batch_alter_table("bot_settings") as batch_op:
        batch_op.drop_column("impulse_check_interval_seconds")
        batch_op.drop_column("impulse_rsi_oversold")
        batch_op.drop_column("impulse_rsi_overbought")
        batch_op.drop_column("impulse_top_n_scan")
        batch_op.drop_column("impulse_cooldown_minutes")
        batch_op.drop_column("impulse_sl_roi_pct")
        batch_op.drop_column("impulse_tp_roi_pct")
        batch_op.drop_column("impulse_leverage")
        batch_op.drop_column("impulse_margin_usdt")
        batch_op.drop_column("impulse_max_entries")
        batch_op.drop_column("impulse_extreme_min_score")
        batch_op.drop_column("impulse_lookback_minutes")
        batch_op.drop_column("impulse_btc_min_change_pct")
        batch_op.drop_column("impulse_mode")
