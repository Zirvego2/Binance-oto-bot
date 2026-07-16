"""Binance adapter katmaninin dondurdugu standart veri yapilari.

Bu tipler, PAPER / DEMO / LIVE adapterlerinin tumunde AYNI sekle sahiptir;
uygulamanin ust katmanlari (worker, api) hangi adapter kullanildigini bilmeden
bu tipler uzerinden calisir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ServerTime:
    server_time_ms: int


@dataclass(frozen=True, slots=True)
class AccountBalance:
    asset: str
    wallet_balance: Decimal
    available_balance: Decimal
    unrealized_pnl: Decimal


@dataclass(frozen=True, slots=True)
class AccountInfo:
    total_wallet_balance: Decimal
    total_unrealized_pnl: Decimal
    total_margin_balance: Decimal
    available_balance: Decimal
    total_maint_margin: Decimal
    can_trade: bool
    multi_assets_margin: bool


@dataclass(frozen=True, slots=True)
class ExchangePosition:
    symbol: str
    position_side: str  # BOTH | LONG | SHORT
    quantity: Decimal  # isaretli: LONG icin pozitif, SHORT icin negatif
    entry_price: Decimal
    mark_price: Decimal
    unrealized_pnl: Decimal
    leverage: int
    margin_type: str
    liquidation_price: Decimal
    isolated_margin: Decimal


@dataclass(frozen=True, slots=True)
class ExchangeOrder:
    symbol: str
    binance_order_id: str
    client_order_id: str
    side: str
    order_type: str
    status: str
    price: Decimal
    orig_qty: Decimal
    executed_qty: Decimal
    avg_price: Decimal
    reduce_only: bool
    close_position: bool
    stop_price: Decimal | None
    working_type: str | None
    time_ms: int


@dataclass(frozen=True, slots=True)
class OrderFillInfo:
    binance_trade_id: str
    price: Decimal
    quantity: Decimal
    commission: Decimal
    commission_asset: str
    time_ms: int


@dataclass(frozen=True, slots=True)
class IncomeRecord:
    symbol: str | None
    income_type: str  # REALIZED_PNL | COMMISSION | FUNDING_FEE
    income: Decimal
    asset: str
    time_ms: int


@dataclass(frozen=True, slots=True)
class LeverageBracket:
    bracket: int
    initial_leverage: int
    notional_cap: Decimal
    notional_floor: Decimal
    maint_margin_ratio: Decimal


@dataclass(frozen=True, slots=True)
class LeverageChangeResult:
    symbol: str
    leverage: int
    max_notional_value: Decimal


@dataclass(frozen=True, slots=True)
class MarginTypeChangeResult:
    symbol: str
    margin_type: str
    already_set: bool


@dataclass(frozen=True, slots=True)
class MarkPriceTick:
    symbol: str
    mark_price: Decimal
    index_price: Decimal
    funding_rate: Decimal
    next_funding_time_ms: int
    time_ms: int


@dataclass(frozen=True, slots=True)
class BookTicker:
    symbol: str
    bid_price: Decimal
    bid_qty: Decimal
    ask_price: Decimal
    ask_qty: Decimal
    time_ms: int


@dataclass(frozen=True, slots=True)
class Kline:
    open_time_ms: int
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    close_time_ms: int
    quote_volume: Decimal
    is_closed: bool


@dataclass(frozen=True, slots=True)
class Ticker24h:
    symbol: str
    quote_volume: Decimal
    price_change_percent: Decimal
    last_price: Decimal


@dataclass(frozen=True, slots=True)
class OpenInterest:
    symbol: str
    open_interest: Decimal
    time_ms: int


@dataclass(frozen=True, slots=True)
class ConnectionTestResult:
    is_configured: bool
    is_connected: bool
    account_access_ok: bool
    futures_account_usable: bool
    trading_permission_ok: bool
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class PlaceOrderRequest:
    symbol: str
    side: str  # BUY | SELL
    quantity: Decimal
    client_order_id: str
    reduce_only: bool = False
    position_side: str = "BOTH"
    price: Decimal | None = None  # LIMIT emirler icin; None → MARKET


@dataclass(frozen=True, slots=True)
class PlaceAlgoOrderRequest:
    symbol: str
    side: str
    order_type: str  # STOP_MARKET | TAKE_PROFIT_MARKET | TRAILING_STOP_MARKET
    stop_price: Decimal
    client_algo_id: str
    working_type: str = "MARK_PRICE"
    close_position: bool = True
    position_side: str = "BOTH"
    callback_rate_pct: Decimal | None = None
