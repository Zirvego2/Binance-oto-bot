"""enhanced decision engine schema

Revision ID: a1b2c3d4e5f6
Revises: 587112aae608
Create Date: 2026-07-11 12:30:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "587112aae608"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_regime_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("market_scope", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("trend_strength", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("volatility_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("breadth_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("risk_off_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("raw_metrics", sa.JSON(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_regime_snapshots")),
    )
    op.create_index(op.f("ix_market_regime_snapshots_market_scope"), "market_regime_snapshots", ["market_scope"])
    op.create_index(op.f("ix_market_regime_snapshots_symbol"), "market_regime_snapshots", ["symbol"])
    op.create_index(op.f("ix_market_regime_snapshots_regime"), "market_regime_snapshots", ["regime"])
    op.create_index(op.f("ix_market_regime_snapshots_created_at"), "market_regime_snapshots", ["created_at"])

    op.create_table(
        "strategy_regime_profiles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("min_signal_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("long_enabled", sa.Boolean(), nullable=False),
        sa.Column("short_enabled", sa.Boolean(), nullable=False),
        sa.Column("indicator_weights", sa.JSON(), nullable=False),
        sa.Column("risk_multiplier", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("max_leverage_override", sa.Integer(), nullable=True),
        sa.Column("max_open_positions_override", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strategy_regime_profiles")),
        sa.UniqueConstraint("regime", name=op.f("uq_strategy_regime_profiles_regime")),
    )

    op.create_table(
        "trade_candidate_rankings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("signal_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("risk_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("expected_reward_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("expected_loss_score", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("risk_reward_ratio", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("regime_alignment_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("symbol_profile_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("liquidity_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("correlation_penalty", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("final_opportunity_score", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trade_candidate_rankings")),
    )
    op.create_index(op.f("ix_trade_candidate_rankings_scan_id"), "trade_candidate_rankings", ["scan_id"])
    op.create_index(op.f("ix_trade_candidate_rankings_symbol"), "trade_candidate_rankings", ["symbol"])
    op.create_index(op.f("ix_trade_candidate_rankings_created_at"), "trade_candidate_rankings", ["created_at"])

    op.create_table(
        "symbol_performance_profiles",
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("losing_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("average_net_pnl", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("average_roi", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("profit_factor", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("expectancy", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("max_drawdown", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("average_holding_minutes", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("long_win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("short_win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("trend_regime_win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("sideways_regime_win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("high_volatility_win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("best_timeframe", sa.String(length=8), nullable=True),
        sa.Column("best_direction", sa.String(length=8), nullable=True),
        sa.Column("average_spread", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("average_slippage", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("average_funding_cost", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("confidence_level", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("last_calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("symbol", name=op.f("pk_symbol_performance_profiles")),
    )

    op.create_table(
        "symbol_strategy_statistics",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("regime", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("timeframe", sa.String(length=8), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("winning_trades", sa.Integer(), nullable=False),
        sa.Column("win_rate", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("average_net_pnl", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("confidence_level", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_symbol_strategy_statistics")),
    )
    op.create_index(op.f("ix_symbol_strategy_statistics_symbol"), "symbol_strategy_statistics", ["symbol"])

    op.create_table(
        "learning_analysis_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_trades", sa.Integer(), nullable=False),
        sa.Column("strategy_version", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learning_analysis_runs")),
    )
    op.create_index(op.f("ix_learning_analysis_runs_status"), "learning_analysis_runs", ["status"])

    op.create_table(
        "strategy_recommendations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("analysis_run_id", sa.String(length=36), nullable=False),
        sa.Column("recommendation_type", sa.String(length=64), nullable=False),
        sa.Column("target_scope", sa.String(length=64), nullable=False),
        sa.Column("target_symbol", sa.String(length=32), nullable=True),
        sa.Column("target_regime", sa.String(length=32), nullable=True),
        sa.Column("current_value", sa.JSON(), nullable=True),
        sa.Column("recommended_value", sa.JSON(), nullable=True),
        sa.Column("expected_impact", sa.String(length=512), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("approved_by", sa.String(length=36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strategy_recommendations")),
    )
    op.create_index(op.f("ix_strategy_recommendations_analysis_run_id"), "strategy_recommendations", ["analysis_run_id"])
    op.create_index(op.f("ix_strategy_recommendations_status"), "strategy_recommendations", ["status"])
    op.create_index(op.f("ix_strategy_recommendations_created_at"), "strategy_recommendations", ["created_at"])

    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("settings_snapshot", sa.JSON(), nullable=False),
        sa.Column("regime_profiles_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("active_in_paper", sa.Boolean(), nullable=False),
        sa.Column("active_in_demo", sa.Boolean(), nullable=False),
        sa.Column("active_in_live", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_strategy_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_strategy_versions_version")),
    )
    op.create_index(op.f("ix_strategy_versions_created_at"), "strategy_versions", ["created_at"])

    op.create_table(
        "shadow_decisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scan_id", sa.String(length=36), nullable=False),
        sa.Column("current_engine_decision", sa.String(length=16), nullable=True),
        sa.Column("enhanced_engine_decision", sa.String(length=16), nullable=True),
        sa.Column("current_selected_symbol", sa.String(length=32), nullable=True),
        sa.Column("enhanced_selected_symbol", sa.String(length=32), nullable=True),
        sa.Column("current_direction", sa.String(length=8), nullable=True),
        sa.Column("enhanced_direction", sa.String(length=8), nullable=True),
        sa.Column("current_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("enhanced_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("enhanced_risk_score", sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column("disagreement_reason", sa.String(length=512), nullable=True),
        sa.Column("hypothetical_entry_price", sa.Numeric(precision=24, scale=10), nullable=True),
        sa.Column("hypothetical_exit_price", sa.Numeric(precision=24, scale=10), nullable=True),
        sa.Column("hypothetical_pnl", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shadow_decisions")),
    )
    op.create_index(op.f("ix_shadow_decisions_scan_id"), "shadow_decisions", ["scan_id"])
    op.create_index(op.f("ix_shadow_decisions_created_at"), "shadow_decisions", ["created_at"])

    op.create_table(
        "ai_explanations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("signal_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("positive_factors", sa.JSON(), nullable=True),
        sa.Column("negative_factors", sa.JSON(), nullable=True),
        sa.Column("risk_level", sa.String(length=16), nullable=True),
        sa.Column("warnings", sa.JSON(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_explanations")),
        sa.UniqueConstraint("signal_id", name=op.f("uq_ai_explanations_signal_id")),
    )
    op.create_index(op.f("ix_ai_explanations_signal_id"), "ai_explanations", ["signal_id"])

    # bot_settings yeni kolonlar
    cols = [
        ("market_regime_enabled", sa.Boolean(), True),
        ("block_trades_in_risk_off", sa.Boolean(), True),
        ("min_regime_confidence", sa.Numeric(10, 4), 40),
        ("high_volatility_score_threshold", sa.Numeric(10, 4), 75),
        ("high_volatility_min_signal_score", sa.Numeric(10, 4), 65),
        ("unknown_regime_min_signal_score", sa.Numeric(10, 4), 60),
        ("max_allowed_risk_score", sa.Numeric(10, 4), 80),
        ("high_risk_min_signal_score", sa.Numeric(10, 4), 75),
        ("block_critical_risk", sa.Boolean(), True),
        ("risk_adjusted_leverage_enabled", sa.Boolean(), False),
        ("minimum_risk_reward_ratio", sa.Numeric(10, 4), 1.2),
        ("symbol_profile_enabled", sa.Boolean(), True),
        ("symbol_profile_shadow_mode", sa.Boolean(), True),
        ("symbol_profile_weight", sa.Numeric(10, 4), 0.3),
        ("minimum_profile_sample_size", sa.Integer(), 10),
        ("correlation_control_enabled", sa.Boolean(), True),
        ("correlation_lookback", sa.Integer(), 100),
        ("max_position_correlation", sa.Numeric(10, 4), 0.80),
        ("block_high_correlation_trades", sa.Boolean(), False),
        ("correlation_penalty_weight", sa.Numeric(10, 4), 1.0),
        ("btc_mtf_filter_enabled", sa.Boolean(), True),
        ("btc_block_against_trend", sa.Boolean(), False),
        ("enhanced_engine_enabled", sa.Boolean(), False),
        ("enhanced_engine_shadow_mode", sa.Boolean(), True),
        ("enhanced_engine_live_enabled", sa.Boolean(), False),
        ("shadow_mode_active", sa.Boolean(), True),
        ("opportunity_score_weights", sa.JSON(), None),
        ("ai_explanation_enabled", sa.Boolean(), True),
        ("ai_post_trade_report_enabled", sa.Boolean(), True),
        ("ai_timeout_seconds", sa.Integer(), 15),
        ("ai_daily_budget_usd", sa.Numeric(20, 8), 5),
        ("ai_model", sa.String(64), "gpt-4o-mini"),
        ("ai_data_retention_enabled", sa.Boolean(), True),
        ("active_strategy_version_id", sa.String(36), None),
    ]
    for name, col_type, default in cols:
        nullable = name == "active_strategy_version_id" or name == "opportunity_score_weights"
        kw: dict = {"nullable": nullable}
        if default is not None:
            if isinstance(default, bool):
                kw["server_default"] = sa.true() if default else sa.false()
            elif isinstance(default, str):
                kw["server_default"] = sa.text(f"'{default}'")
            else:
                kw["server_default"] = sa.text(str(default))
        op.add_column("bot_settings", sa.Column(name, col_type, **kw))

    op.add_column("strategy_signals", sa.Column("strategy_version_id", sa.String(36), nullable=True))
    op.add_column("strategy_signals", sa.Column("risk_score", sa.Numeric(10, 4), nullable=True))
    op.add_column("strategy_signals", sa.Column("regime_at_signal", sa.String(32), nullable=True))
    op.create_index(op.f("ix_strategy_signals_strategy_version_id"), "strategy_signals", ["strategy_version_id"])

    op.add_column("positions", sa.Column("strategy_version_id", sa.String(36), nullable=True))
    op.create_index(op.f("ix_positions_strategy_version_id"), "positions", ["strategy_version_id"])

    op.add_column("trades", sa.Column("strategy_version_id", sa.String(36), nullable=True))
    op.create_index(op.f("ix_trades_strategy_version_id"), "trades", ["strategy_version_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_trades_strategy_version_id"), table_name="trades")
    op.drop_column("trades", "strategy_version_id")
    op.drop_index(op.f("ix_positions_strategy_version_id"), table_name="positions")
    op.drop_column("positions", "strategy_version_id")
    op.drop_index(op.f("ix_strategy_signals_strategy_version_id"), table_name="strategy_signals")
    op.drop_column("strategy_signals", "regime_at_signal")
    op.drop_column("strategy_signals", "risk_score")
    op.drop_column("strategy_signals", "strategy_version_id")

    for name, _, _ in reversed([
        ("market_regime_enabled", sa.Boolean(), True),
        ("block_trades_in_risk_off", sa.Boolean(), True),
        ("min_regime_confidence", sa.Numeric(10, 4), 40),
        ("high_volatility_score_threshold", sa.Numeric(10, 4), 75),
        ("high_volatility_min_signal_score", sa.Numeric(10, 4), 65),
        ("unknown_regime_min_signal_score", sa.Numeric(10, 4), 60),
        ("max_allowed_risk_score", sa.Numeric(10, 4), 80),
        ("high_risk_min_signal_score", sa.Numeric(10, 4), 75),
        ("block_critical_risk", sa.Boolean(), True),
        ("risk_adjusted_leverage_enabled", sa.Boolean(), False),
        ("minimum_risk_reward_ratio", sa.Numeric(10, 4), 1.2),
        ("symbol_profile_enabled", sa.Boolean(), True),
        ("symbol_profile_shadow_mode", sa.Boolean(), True),
        ("symbol_profile_weight", sa.Numeric(10, 4), 0.3),
        ("minimum_profile_sample_size", sa.Integer(), 10),
        ("correlation_control_enabled", sa.Boolean(), True),
        ("correlation_lookback", sa.Integer(), 100),
        ("max_position_correlation", sa.Numeric(10, 4), 0.80),
        ("block_high_correlation_trades", sa.Boolean(), False),
        ("correlation_penalty_weight", sa.Numeric(10, 4), 1.0),
        ("btc_mtf_filter_enabled", sa.Boolean(), True),
        ("btc_block_against_trend", sa.Boolean(), False),
        ("enhanced_engine_enabled", sa.Boolean(), False),
        ("enhanced_engine_shadow_mode", sa.Boolean(), True),
        ("enhanced_engine_live_enabled", sa.Boolean(), False),
        ("shadow_mode_active", sa.Boolean(), True),
        ("opportunity_score_weights", sa.JSON(), None),
        ("ai_explanation_enabled", sa.Boolean(), True),
        ("ai_post_trade_report_enabled", sa.Boolean(), True),
        ("ai_timeout_seconds", sa.Integer(), 15),
        ("ai_daily_budget_usd", sa.Numeric(20, 8), 5),
        ("ai_model", sa.String(64), "gpt-4o-mini"),
        ("ai_data_retention_enabled", sa.Boolean(), True),
        ("active_strategy_version_id", sa.String(36), None),
    ]):
        op.drop_column("bot_settings", name)

    op.drop_table("ai_explanations")
    op.drop_table("shadow_decisions")
    op.drop_table("strategy_versions")
    op.drop_table("strategy_recommendations")
    op.drop_table("learning_analysis_runs")
    op.drop_table("symbol_strategy_statistics")
    op.drop_table("symbol_performance_profiles")
    op.drop_table("trade_candidate_rankings")
    op.drop_table("strategy_regime_profiles")
    op.drop_table("market_regime_snapshots")
