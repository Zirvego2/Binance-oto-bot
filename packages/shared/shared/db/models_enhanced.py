"""Gelismis karar motoru veritabani modelleri."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, TimestampMixin, new_uuid


class MarketRegimeSnapshot(Base):
    __tablename__ = "market_regime_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    market_scope: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    regime: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    trend_strength: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    volatility_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    breadth_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    risk_off_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    raw_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasons: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class StrategyRegimeProfile(Base, TimestampMixin):
    __tablename__ = "strategy_regime_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    regime: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("60"))
    long_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    short_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    indicator_weights: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_multiplier: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("1"))
    max_leverage_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_open_positions_override: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TradeCandidateRanking(Base):
    __tablename__ = "trade_candidate_rankings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    risk_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    expected_reward_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    expected_loss_score: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    regime_alignment_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    symbol_profile_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    liquidity_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    correlation_penalty: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    final_opportunity_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class SymbolPerformanceProfile(Base):
    __tablename__ = "symbol_performance_profiles"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    average_net_pnl: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    average_roi: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    profit_factor: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    expectancy: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    average_holding_minutes: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    long_win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    short_win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    trend_regime_win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    sideways_regime_win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    high_volatility_win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    best_timeframe: Mapped[str | None] = mapped_column(String(8), nullable=True)
    best_direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    average_spread: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    average_slippage: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    average_funding_cost: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    last_calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SymbolStrategyStatistic(Base):
    __tablename__ = "symbol_strategy_statistics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    regime: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    average_net_pnl: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    confidence_level: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LearningAnalysisRun(Base):
    __tablename__ = "learning_analysis_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    strategy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StrategyRecommendation(Base):
    __tablename__ = "strategy_recommendations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    analysis_run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    recommendation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    target_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_regime: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recommended_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_impact: Mapped[str | None] = mapped_column(String(512), nullable=True)
    confidence: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("50"))
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False, index=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    regime_profiles_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(24), default="MANUAL", nullable=False)
    active_in_paper: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_in_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_in_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ShadowDecision(Base):
    __tablename__ = "shadow_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    scan_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    current_engine_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    enhanced_engine_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    current_selected_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    enhanced_selected_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    current_direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    enhanced_direction: Mapped[str | None] = mapped_column(String(8), nullable=True)
    current_score: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)
    enhanced_score: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)
    enhanced_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)
    disagreement_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    hypothetical_entry_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    hypothetical_exit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 10), nullable=True)
    hypothetical_pnl: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiExplanation(Base):
    __tablename__ = "ai_explanations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    signal_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    positive_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    negative_factors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
