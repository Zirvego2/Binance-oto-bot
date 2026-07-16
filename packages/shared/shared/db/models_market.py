"""Sembol (coin) exchange bilgileri ve admin tarafindan yonetilen kurallar."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, PRICE_PRECISION, QTY_PRECISION, RATE_PRECISION, TimestampMixin, new_uuid


class Symbol(Base, TimestampMixin):
    """Binance exchangeInfo + guncel piyasa verisi cache'i."""

    __tablename__ = "symbols"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    base_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    margin_asset: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(24), nullable=False)

    price_tick_size: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    lot_step_size: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    market_lot_step_size: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    min_qty: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), default=Decimal("0"))
    max_qty: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), default=Decimal("0"))
    min_notional: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("5"))

    last_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    funding_rate: Mapped[Decimal | None] = mapped_column(Numeric(*RATE_PRECISION), nullable=True)
    volume_24h_usdt: Mapped[Decimal | None] = mapped_column(Numeric(*MONEY_PRECISION), nullable=True)
    open_interest: Mapped[Decimal | None] = mapped_column(Numeric(*QTY_PRECISION), nullable=True)
    spread_pct: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)

    market_data_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SymbolRule(Base, TimestampMixin):
    """Musteri bazli sembol kurallari (sartname bolum 22)."""

    __tablename__ = "symbol_rules"
    __table_args__ = (UniqueConstraint("admin_id", "symbol", name="uq_symbol_rules_admin_symbol"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    in_analysis_list: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blacklist_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    long_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    short_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_leverage_override: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_trade_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
