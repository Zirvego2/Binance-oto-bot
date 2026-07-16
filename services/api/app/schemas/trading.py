from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PositionOut(BaseModel):
    id: str
    symbol: str
    side: str
    status: str
    bot_mode: str
    margin_type: str
    leverage: int
    margin_usdt: Decimal
    notional_usdt: Decimal
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal | None
    break_even_price: Decimal | None
    liquidation_price: Decimal | None
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None
    unrealized_pnl: Decimal
    roi_pct: Decimal
    margin_ratio_pct: Decimal | None
    funding_fee_usdt: Decimal
    protective_orders_ok: bool
    loss_add_count: int
    open_reason: str | None
    opened_at: datetime
    closed_at: datetime | None
    is_external: bool

    class Config:
        from_attributes = True


class OrderOut(BaseModel):
    id: str
    position_id: str | None
    symbol: str
    side: str
    order_type: str
    purpose: str
    reduce_only: bool
    quantity: Decimal
    price: Decimal | None
    avg_fill_price: Decimal | None
    filled_quantity: Decimal
    commission_usdt: Decimal
    client_order_id: str
    binance_order_id: str | None
    status: str
    retry_count: int
    last_error: str | None
    bot_mode: str
    submitted_at: datetime | None
    created_at: datetime
    filled_at: datetime | None
    canceled_at: datetime | None

    class Config:
        from_attributes = True


class TradeOut(BaseModel):
    id: str
    position_id: str
    symbol: str
    side: str
    bot_mode: str
    entry_price: Decimal
    exit_price: Decimal
    margin_usdt: Decimal
    leverage: int
    quantity: Decimal
    notional_usdt: Decimal
    gross_pnl_usdt: Decimal
    open_commission_usdt: Decimal
    close_commission_usdt: Decimal
    funding_fee_usdt: Decimal
    net_pnl_usdt: Decimal
    gross_roi_pct: Decimal
    net_roi_pct: Decimal
    open_reason: str | None
    close_reason: str
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None
    binance_order_id_open: str | None
    binance_order_id_close: str | None
    client_order_id_open: str | None
    client_order_id_close: str | None
    opened_at: datetime
    closed_at: datetime

    class Config:
        from_attributes = True


class TradePnlPeriodSummary(BaseModel):
    net_pnl_usdt: Decimal
    gross_pnl_usdt: Decimal
    trades_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal


class TradePnlSummaryOut(BaseModel):
    last_24h: TradePnlPeriodSummary
    last_7d: TradePnlPeriodSummary
    last_30d: TradePnlPeriodSummary


class ClosePositionRequest(BaseModel):
    reason: str = "MANUAL"


class EmergencyCloseAllRequest(BaseModel):
    password: str


class EmergencyCloseAllResponse(BaseModel):
    closed_positions: list[str]
    failed_positions: list[str]
    closed_count: int


class AddLosingPositionsResponse(BaseModel):
    added_positions: list[str]
    failed_positions: list[str]
    skipped_positions: list[str]
    added_count: int


class PositionSyncOut(BaseModel):
    local_open_count: int
    exchange_open_count: int
    closed_ghosts: list[str]
    synced_at: str
    in_sync: bool
    skipped_throttle: bool = False
