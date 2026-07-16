"""Pozisyon, emir, algo emir, doldurma (fill) ve islem (trade) tablolari."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, PRICE_PRECISION, QTY_PRECISION, TimestampMixin, new_uuid


class Position(Base, TimestampMixin):
    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG | SHORT
    binance_position_side: Mapped[str] = mapped_column(String(8), default="BOTH", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="OPEN", nullable=False, index=True)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    margin_type: Mapped[str] = mapped_column(String(16), default="ISOLATED", nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    margin_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    notional_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)

    entry_price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    mark_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    break_even_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    liquidation_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    exit_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)

    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0"))
    margin_ratio_pct: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)

    open_commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    close_commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    funding_fee_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))

    protective_orders_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stop_loss_algo_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    take_profit_algo_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    signal_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    strategy_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    open_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    close_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    loss_add_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    open_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    close_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # BUY | SELL
    order_type: Mapped[str] = mapped_column(String(24), nullable=False)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)  # OPEN | CLOSE | MANUAL_CLOSE | EMERGENCY_CLOSE
    reduce_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    avg_fill_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    filled_quantity: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), default=Decimal("0"))
    commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))

    client_order_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    binance_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False, index=True)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AlgoOrder(Base, TimestampMixin):
    """STOP_MARKET / TAKE_PROFIT_MARKET / TRAILING_STOP_MARKET koruyucu emirler."""

    __tablename__ = "algo_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(24), nullable=False)  # STOP_LOSS | TAKE_PROFIT | TRAILING_STOP
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(24), nullable=False)
    trigger_price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    working_type: Mapped[str] = mapped_column(String(16), default="MARK_PRICE", nullable=False)
    close_position: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    client_algo_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
    binance_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False, index=True)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrderFill(Base, TimestampMixin):
    __tablename__ = "order_fills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    order_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    binance_trade_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    commission_asset: Mapped[str] = mapped_column(String(16), default="USDT", nullable=False)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Trade(Base, TimestampMixin):
    """Tamamlanmis (acilis+kapanis) islem gecmisi kaydi."""

    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    position_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True, unique=True)
    strategy_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    bot_mode: Mapped[str] = mapped_column(String(16), nullable=False)

    entry_price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(Numeric(*PRICE_PRECISION), nullable=False)
    margin_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    leverage: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(*QTY_PRECISION), nullable=False)
    notional_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)

    gross_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    open_commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    close_commission_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    funding_fee_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("0"))
    net_pnl_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), nullable=False)
    gross_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)
    net_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), nullable=False)

    open_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    close_reason: Mapped[str] = mapped_column(String(32), nullable=False)
    stop_loss_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)
    take_profit_price: Mapped[Decimal | None] = mapped_column(Numeric(*PRICE_PRECISION), nullable=True)

    binance_order_id_open: Mapped[str | None] = mapped_column(String(64), nullable=True)
    binance_order_id_close: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_order_id_open: Mapped[str | None] = mapped_column(String(36), nullable=True)
    client_order_id_close: Mapped[str | None] = mapped_column(String(36), nullable=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
