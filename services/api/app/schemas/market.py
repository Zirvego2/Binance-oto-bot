from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SymbolOut(BaseModel):
    symbol: str
    status: str
    contract_type: str
    price_tick_size: Decimal
    lot_step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    last_price: Decimal | None
    mark_price: Decimal | None
    funding_rate: Decimal | None
    volume_24h_usdt: Decimal | None
    spread_pct: Decimal | None
    in_analysis_list: bool
    is_blacklisted: bool
    blacklist_reason: str | None
    long_enabled: bool
    short_enabled: bool
    max_leverage_override: int | None
    last_signal_id: str | None
    last_trade_at: datetime | None
    required_min_margin_at_3x: Decimal | None


class SymbolUpdateRequest(BaseModel):
    in_analysis_list: bool | None = None
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = None
    long_enabled: bool | None = None
    short_enabled: bool | None = None
    max_leverage_override: int | None = None
    notes: str | None = None


class TimeframeAnalysisOut(BaseModel):
    interval: str
    price: float
    ema_fast: float
    ema_mid: float
    ema_slow: float
    rsi: float
    change_1h_pct: float
    change_4h_pct: float
    trend: str
    momentum: str


class MarketRegimeOut(BaseModel):
    symbol: str
    direction: str
    confidence: float
    btc_price: float
    change_1h_pct: float
    change_4h_pct: float
    primary: TimeframeAnalysisOut
    confirm: TimeframeAnalysisOut
    long_score: float
    short_score: float
    reason: str
    recommendation: str
    components: dict[str, float]
    analyzed_at: datetime
    primary_interval: str
    confirm_interval: str


class TickerMoverOut(BaseModel):
    symbol: str
    last_price: float
    change_pct: float
    quote_volume_usdt: float


class BtcQuickOut(BaseModel):
    symbol: str
    last_price: float
    change_24h_pct: float
    mark_price: float
    funding_rate_pct: float
    quote_volume_24h_usdt: float


class OrderBookPressureOut(BaseModel):
    symbol: str
    bid_qty: float
    ask_qty: float
    bid_pct: float
    ask_pct: float
    bias: str


class MarketOverviewOut(BaseModel):
    analyzed_at: datetime
    universe_count: int
    rising_count: int
    falling_count: int
    flat_count: int
    rising_pct: float
    falling_pct: float
    flat_pct: float
    sentiment: str
    sentiment_score: float
    buy_pressure_pct: float
    sell_pressure_pct: float
    avg_change_pct: float
    median_change_pct: float
    total_volume_24h_usdt: float
    btc: BtcQuickOut
    order_book_pressure: OrderBookPressureOut | None = None
    bot_regime_direction: str | None = None
    market_direction_filter_enabled: bool = False
    top_gainers: list[TickerMoverOut]
    top_losers: list[TickerMoverOut]
    top_volume: list[TickerMoverOut]


class MarketAiResearchOut(BaseModel):
    executive_summary: str
    market_outlook: str
    confidence_pct: int
    btc_analysis: str
    altcoin_implications: str
    key_observations: list[str]
    risk_factors: list[str]
    opportunities: list[str]
    time_horizon: str
    analyst_note: str
    disclaimer: str
    status: str
    model: str | None = None
    cached: bool = False
    generated_at: datetime | None = None
