"""Analiz sonuclari ve islem sinyalleri (sartname bolum 15-18)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, PRICE_PRECISION, TimestampMixin, new_uuid


class AnalysisResult(Base, TimestampMixin):
    """Her tarama dongusunde her sembol icin uretilen aciklanabilir analiz kaydi."""

    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    mark_price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    ema_fast: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    ema_mid: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    ema_slow: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    rsi_value: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    atr_value: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    current_volume: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    avg_volume_20: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    volume_24h_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    spread_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    funding_rate_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)

    trend_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    ema_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    rsi_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    volume_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    volatility_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    spread_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    funding_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    open_interest_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)

    suggested_side: Mapped[str | None] = mapped_column(String(8), nullable=True)
    decision: Mapped[str] = mapped_column(String(48), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)


class StrategySignal(Base, TimestampMixin):
    """Islem acmaya yol acan (LONG/SHORT) somut sinyal. Her sinyal ile en fazla
    bir pozisyon acilir (sartname bolum 14)."""

    __tablename__ = "strategy_signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    analysis_result_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resulting_position_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    strategy_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)
    regime_at_signal: Mapped[str | None] = mapped_column(String(32), nullable=True)
