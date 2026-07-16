"""PnL kayitlari, funding kayitlari ve gunluk istatistikler (sartname bolum 27)."""

from __future__ import annotations

from datetime import date as date_type, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, RATE_PRECISION, TimestampMixin, new_uuid


class PnlRecord(Base, TimestampMixin):
    __tablename__ = "pnl_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    trade_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    record_type: Mapped[str] = mapped_column(String(24), nullable=False)  # REALIZED|COMMISSION|FUNDING
    amount_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FundingRecord(Base, TimestampMixin):
    __tablename__ = "funding_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    funding_rate: Mapped[Decimal] = mapped_column(Numeric(*RATE_PRECISION), nullable=False)
    funding_fee_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    funding_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class DailyStatistic(Base, TimestampMixin):
    __tablename__ = "daily_statistics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    stat_date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    trades_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))

    gross_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    net_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    total_commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    total_funding_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    consecutive_losses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_loss_limit_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
