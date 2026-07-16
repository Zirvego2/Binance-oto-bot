from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class DashboardOut(BaseModel):
    bot_enabled: bool
    run_state: str
    mode: str
    binance_connected: bool
    futures_connected: bool
    worker_connected: bool
    worker_heartbeat_at: datetime | None = None
    worker_stale_seconds: int | None = None
    websocket_connected: bool

    total_futures_balance_usdt: Decimal
    wallet_balance_usdt: Decimal
    available_usdt: Decimal
    used_margin_usdt: Decimal
    open_positions_count: int

    daily_realized_pnl_usdt: Decimal
    daily_unrealized_pnl_usdt: Decimal
    total_net_pnl_usdt: Decimal

    today_trades_count: int
    winning_trades_count: int
    losing_trades_count: int
    win_rate_pct: Decimal

    total_commission_usdt: Decimal
    total_funding_usdt: Decimal

    last_analysis_at: datetime | None
    last_signal_at: datetime | None
    last_order_at: datetime | None
    last_error_at: datetime | None
    last_error_message: str | None

    bot_uptime_seconds: int | None

    usdt_try_rate: Decimal | None = None


class DashboardStatisticsOut(BaseModel):
    stat_date: str
    trades_count: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: Decimal
    gross_pnl_usdt: Decimal
    net_pnl_usdt: Decimal
    total_commission_usdt: Decimal
    total_funding_usdt: Decimal


class DashboardRealtimeOut(DashboardOut):
    server_time: datetime
