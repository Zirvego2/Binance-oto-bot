"""Dashboard verilerini veritabanindan derleyen servis (sartname bolum 22 & 24)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import (
    BotRuntimeStatus,
    DailyStatistic,
    Position,
    Trade,
)

from shared.tenant_settings import get_or_create_bot_runtime
from shared.timezone_utils import local_today

from .paper_state_service import get_paper_account_info
from .settings_service import get_or_create_bot_settings
from ..core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin

ZERO = Decimal("0")
WORKER_STALE_SECONDS = 90
USDT_TRY_CACHE_SECONDS = 60
_usdt_try_cache: tuple[Decimal, float] | None = None


async def _fetch_usdt_try_rate() -> Decimal | None:
    """Binance spot USDTTRY kurunu dondurur (60 sn onbellek)."""
    global _usdt_try_cache
    now = time.monotonic()
    if _usdt_try_cache is not None and now < _usdt_try_cache[1]:
        return _usdt_try_cache[0]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "USDTTRY"},
            )
            response.raise_for_status()
            rate = Decimal(str(response.json()["price"]))
            _usdt_try_cache = (rate, now + USDT_TRY_CACHE_SECONDS)
            return rate
    except Exception:
        if _usdt_try_cache is not None:
            return _usdt_try_cache[0]
        return None


def _worker_health(runtime: BotRuntimeStatus | None) -> dict:
    if runtime is None or runtime.worker_heartbeat_at is None:
        return {
            "worker_connected": False,
            "worker_heartbeat_at": None,
            "worker_stale_seconds": None,
        }
    heartbeat = runtime.worker_heartbeat_at
    if heartbeat.tzinfo is None:
        heartbeat = heartbeat.replace(tzinfo=timezone.utc)
    stale_seconds = int((datetime.now(timezone.utc) - heartbeat).total_seconds())
    return {
        "worker_connected": stale_seconds < WORKER_STALE_SECONDS,
        "worker_heartbeat_at": runtime.worker_heartbeat_at,
        "worker_stale_seconds": stale_seconds,
    }


async def build_dashboard(session: AsyncSession, admin_id: str) -> dict:
    settings_row = await get_or_create_bot_settings(session, admin_id)

    runtime = await get_or_create_bot_runtime(session, admin_id)

    open_positions_result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == settings_row.mode,
            Position.admin_id == admin_id,
        )
    )
    open_positions = open_positions_result.scalars().all()

    today = local_today()
    today_stat_result = await session.execute(
        select(DailyStatistic).where(
            DailyStatistic.stat_date == today,
            DailyStatistic.bot_mode == settings_row.mode,
            DailyStatistic.admin_id == admin_id,
        )
    )
    today_stat = today_stat_result.scalar_one_or_none()

    total_net_pnl_result = await session.execute(
        select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(
            Trade.bot_mode == settings_row.mode,
            Trade.admin_id == admin_id,
        )
    )
    total_net_pnl = Decimal(str(total_net_pnl_result.scalar_one() or 0))

    total_commission_result = await session.execute(
        select(
            func.coalesce(func.sum(Trade.open_commission_usdt + Trade.close_commission_usdt), 0)
        ).where(Trade.bot_mode == settings_row.mode, Trade.admin_id == admin_id)
    )
    total_commission = Decimal(str(total_commission_result.scalar_one() or 0))

    total_funding_result = await session.execute(
        select(func.coalesce(func.sum(Trade.funding_fee_usdt), 0)).where(
            Trade.bot_mode == settings_row.mode,
            Trade.admin_id == admin_id,
        )
    )
    total_funding = Decimal(str(total_funding_result.scalar_one() or 0))

    daily_unrealized = sum((p.unrealized_pnl for p in open_positions), ZERO)
    used_margin = sum((p.margin_usdt for p in open_positions), ZERO)

    total_futures_balance = ZERO
    total_wallet_balance = ZERO
    available_balance = ZERO
    binance_connected = settings_row.mode == "paper"
    futures_connected = settings_row.mode == "paper"
    if settings_row.mode == "paper":
        paper_info = await get_paper_account_info(session, admin_id)
        total_wallet_balance = paper_info.total_wallet_balance
        total_futures_balance = paper_info.total_margin_balance
        available_balance = paper_info.available_balance
    elif settings_row.mode in ("live", "demo") and await is_binance_configured_for_admin(
        session, admin_id, settings_row.mode
    ):
        try:
            adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
            account = await adapter.get_account_info()
            total_wallet_balance = account.total_wallet_balance
            total_futures_balance = account.total_margin_balance
            available_balance = account.available_balance
            binance_connected = True
            futures_connected = True
            if not open_positions and account.total_unrealized_pnl != ZERO:
                daily_unrealized = account.total_unrealized_pnl
        except Exception:
            binance_connected = False
            futures_connected = False

    uptime_seconds = None
    if runtime and runtime.started_at and runtime.run_state == "RUNNING":
        started = runtime.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        uptime_seconds = int((datetime.now(timezone.utc) - started).total_seconds())

    winning = today_stat.winning_trades if today_stat else 0
    losing = today_stat.losing_trades if today_stat else 0
    trades_count = today_stat.trades_count if today_stat else 0
    win_rate = today_stat.win_rate_pct if today_stat else ZERO
    worker = _worker_health(runtime)
    usdt_try_rate = await _fetch_usdt_try_rate()

    return {
        "bot_enabled": settings_row.bot_enabled,
        "run_state": runtime.run_state if runtime else "STOPPED",
        "mode": settings_row.mode,
        "binance_connected": binance_connected,
        "futures_connected": futures_connected,
        "worker_connected": worker["worker_connected"],
        "worker_heartbeat_at": worker["worker_heartbeat_at"],
        "worker_stale_seconds": worker["worker_stale_seconds"],
        "websocket_connected": worker["worker_connected"],
        "total_futures_balance_usdt": total_futures_balance,
        "wallet_balance_usdt": total_wallet_balance,
        "available_usdt": available_balance,
        "used_margin_usdt": used_margin,
        "open_positions_count": len(open_positions),
        "daily_realized_pnl_usdt": Decimal(str(today_stat.net_pnl_usdt if today_stat else 0)),
        "daily_unrealized_pnl_usdt": daily_unrealized,
        "total_net_pnl_usdt": total_net_pnl,
        "today_trades_count": trades_count,
        "winning_trades_count": winning,
        "losing_trades_count": losing,
        "win_rate_pct": win_rate,
        "total_commission_usdt": total_commission,
        "total_funding_usdt": total_funding,
        "last_analysis_at": runtime.last_scan_at if runtime else None,
        "last_signal_at": runtime.last_signal_at if runtime else None,
        "last_order_at": runtime.last_order_at if runtime else None,
        "last_error_at": runtime.last_error_at if runtime else None,
        "last_error_message": runtime.last_error_message if runtime else None,
        "bot_uptime_seconds": uptime_seconds,
        "usdt_try_rate": usdt_try_rate,
    }
