from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class BinanceStatusOut(BaseModel):
    environment: str
    is_configured: bool
    is_connected: bool
    account_access_ok: bool
    futures_account_usable: bool
    trading_permission_ok: bool
    position_mode_verified: bool
    multi_assets_mode_off_verified: bool
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None
    not_configured_message: str | None = None

    class Config:
        from_attributes = True


class BinanceAccountBalanceOut(BaseModel):
    asset: str
    wallet_balance: Decimal
    available_balance: Decimal
    unrealized_pnl: Decimal


class BinanceAccountInfoOut(BaseModel):
    total_wallet_balance: Decimal
    total_unrealized_pnl: Decimal
    total_margin_balance: Decimal
    available_balance: Decimal
    can_trade: bool
    multi_assets_margin: bool


class BinancePositionOut(BaseModel):
    symbol: str
    position_side: str
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    margin_type: str
    liquidation_price: Decimal


class BinanceOrderOut(BaseModel):
    symbol: str
    binance_order_id: str
    client_order_id: str
    side: str
    order_type: str
    status: str
    price: Decimal
    orig_qty: Decimal
    executed_qty: Decimal


class ReconciliationRunOut(BaseModel):
    id: str
    triggered_by: str
    status: str
    mismatches_found: int
    external_positions_found: int
    entered_safe_mode: bool
    ran_at: datetime

    class Config:
        from_attributes = True
