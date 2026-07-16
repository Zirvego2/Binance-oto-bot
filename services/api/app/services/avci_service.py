"""Avcı — en cok yukselen/dusen coin taramasi ve tek tik pozisyon acma."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Symbol, SymbolRule
from shared.distributed_lock import DistributedLock, LockNotAcquiredError
from shared.market_breadth import compute_market_breadth
from shared.trade_overrides import MANUAL_TRADE_OVERRIDES
from shared.trading_risk import build_risk_context, evaluate_manual_trade_risk

from ..core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin
from ..core.worker_bridge import get_order_engine_module
from .audit_service import record_audit_log
from .position_sync_service import sync_positions_from_exchange
from .settings_service import get_or_create_bot_settings

SKIP_REASON_MESSAGES: dict[str, str] = {
    "bot_disabled": "Bot kapali — once botu acin",
    "symbol_blacklisted": "Sembol kara listede",
    "post_trade_cooldown_active": "Sembol icin bekleme suresi aktif",
    "daily_max_loss_reached": "Gunluk zarar limiti doldu",
    "max_consecutive_losses_reached": "Ust uste kayip limiti doldu",
    "max_open_positions_reached": "Maksimum acik pozisyon sayisina ulasildi",
    "max_open_positions_per_symbol_reached": "Bu sembol icin pozisyon limiti doldu",
    "long_disabled": "LONG islemler devre disi",
    "short_disabled": "SHORT islemler devre disi",
    "leverage_exceeds_max_allowed": "Kaldirac izin verilen maksimumu asiyor",
    "leverage_not_confirmed": "Kaldirac borsada onaylanamadi",
    "leverage_or_margin_type_setup_failed": "Kaldirac veya marj tipi ayarlanamadi",
    "market_direction_filter_blocked": "Piyasa yonu filtresi engelledi",
    "liquidation_distance_too_small": "Likidasyon mesafesi yetersiz",
    "protective_order_placement_failed": "Koruyucu emirler yerlestirilemedi",
}


class AvciOpenSkippedError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(SKIP_REASON_MESSAGES.get(reason, reason))


@dataclass(frozen=True, slots=True)
class AvciScanResult:
    analyzed_at: datetime
    top_gainers: list[dict]
    top_losers: list[dict]
    limit: int


@dataclass(frozen=True, slots=True)
class AvciChartResult:
    symbol: str
    interval: str
    hours: int
    change_pct: float
    last_price: float
    klines: list[dict]


CHART_HOURS_ALLOWED = frozenset({1, 4, 6, 12, 24})
CHART_RESOLUTION_BY_HOURS: dict[int, tuple[str, int]] = {
    1: ("1m", 60),
    4: ("5m", 48),
    6: ("5m", 72),
    12: ("15m", 48),
    24: ("15m", 96),
}


def _resolve_chart_params(hours: int) -> tuple[str, int]:
    if hours not in CHART_HOURS_ALLOWED:
        raise HTTPException(status_code=400, detail="Gecersiz saat araligi")
    return CHART_RESOLUTION_BY_HOURS[hours]


def _coin_dict(m) -> dict:
    return {
        "symbol": m.symbol,
        "last_price": m.last_price,
        "change_pct": m.change_pct,
        "quote_volume_usdt": m.quote_volume_usdt,
    }


async def _blocked_symbols(session: AsyncSession, admin_id: str) -> set[str]:
    result = await session.execute(
        select(SymbolRule).where(SymbolRule.admin_id == admin_id, SymbolRule.is_blacklisted == True)  # noqa: E712
    )
    return {r.symbol for r in result.scalars().all()}


async def scan_avci_coins(
    session: AsyncSession,
    admin_id: str,
    *,
    limit: int = 15,
) -> AvciScanResult:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    if not await is_binance_configured_for_admin(session, admin_id, settings_row.mode):
        raise HTTPException(status_code=400, detail="Binance baglantisi yapilandirilmamis")

    adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
    try:
        tickers = await adapter.get_24h_tickers()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Piyasa verisi alinamadi: {exc}") from exc

    min_vol = float(settings_row.min_24h_volume_usdt)
    blocked = await _blocked_symbols(session, admin_id)

    eligible = [
        t
        for t in tickers
        if t.symbol.endswith("USDT")
        and not t.symbol.endswith("USDCUSDT")
        and float(t.quote_volume) >= min_vol
        and t.symbol not in blocked
    ]

    snap = compute_market_breadth(eligible, top_n=limit)

    return AvciScanResult(
        analyzed_at=snap.analyzed_at,
        top_gainers=[_coin_dict(m) for m in snap.top_gainers],
        top_losers=[_coin_dict(m) for m in snap.top_losers],
        limit=limit,
    )


async def open_avci_position(
    session: AsyncSession,
    redis: Redis,
    *,
    symbol: str,
    side: Literal["LONG", "SHORT"],
    admin_id: str | None,
    ip_address: str | None = None,
) -> dict:
    symbol = symbol.upper().strip()
    settings_row = await get_or_create_bot_settings(session, admin_id or "")

    if not settings_row.bot_enabled:
        raise AvciOpenSkippedError("bot_disabled")

    if not admin_id or not await is_binance_configured_for_admin(session, admin_id, settings_row.mode):
        raise HTTPException(status_code=400, detail="Binance baglantisi yapilandirilmamis")

    ctx = await build_risk_context(session, settings_row, symbol)
    risk = evaluate_manual_trade_risk(settings_row, ctx, side)
    if not risk.ok:
        raise AvciOpenSkippedError(risk.reason or "risk_check_failed")

    symbol_result = await session.execute(select(Symbol).where(Symbol.symbol == symbol))
    symbol_row = symbol_result.scalar_one_or_none()
    if symbol_row is None:
        raise HTTPException(status_code=404, detail="Sembol bulunamadi")

    order_engine = get_order_engine_module()
    adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
    lock = DistributedLock(redis, f"trading_engine:{admin_id}", ttl_seconds=30)
    acquired = await lock.acquire(blocking_timeout_seconds=10.0)
    if not acquired:
        raise LockNotAcquiredError("Islem kilidi alinamadi; baska bir islem suruyor olabilir")

    try:
        position = await order_engine.open_position_for_signal(
            session,
            adapter,
            settings_row,
            symbol_row,
            side,
            None,
            "AVCI_MANUAL",
            None,
            MANUAL_TRADE_OVERRIDES,
        )
        await sync_positions_from_exchange(session, admin_id, settings_row.mode)
        await session.refresh(position)
        await record_audit_log(
            session,
            admin_id=admin_id,
            action="AVCI_OPEN",
            entity_type="position",
            entity_id=position.id,
            after_data={"symbol": symbol, "side": side, "status": position.status},
            ip_address=ip_address,
        )
        if position.status == "CLOSED":
            msg = f"{symbol} {side} acildi; borsada {position.close_reason or 'hemen'} kapandi"
        else:
            msg = f"{symbol} {side} pozisyon acildi (Binance'de aktif)"
        return {
            "symbol": symbol,
            "side": side,
            "position_id": position.id,
            "message": msg,
            "status": position.status,
        }
    except order_engine.PositionOpenSkipped as exc:
        await session.rollback()
        raise AvciOpenSkippedError(exc.reason) from exc
    finally:
        await lock.release()


async def fetch_avci_chart(
    session: AsyncSession,
    admin_id: str,
    symbol: str,
    *,
    hours: int = 1,
) -> AvciChartResult:
    symbol = symbol.upper().strip()
    interval, limit = _resolve_chart_params(hours)
    settings_row = await get_or_create_bot_settings(session, admin_id)
    if not await is_binance_configured_for_admin(session, admin_id, settings_row.mode):
        raise HTTPException(status_code=400, detail="Binance baglantisi yapilandirilmamis")

    adapter = await get_binance_adapter_for_admin(session, admin_id, settings_row.mode)
    try:
        klines = await adapter.get_klines(symbol, interval, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Grafik verisi alinamadi: {exc}") from exc

    if not klines:
        raise HTTPException(status_code=404, detail="Grafik verisi bulunamadi")

    rows: list[dict] = []
    for k in klines:
        rows.append(
            {
                "time": datetime.fromtimestamp(k.open_time_ms / 1000, tz=UTC),
                "open": float(k.open),
                "high": float(k.high),
                "low": float(k.low),
                "close": float(k.close),
                "volume": float(k.volume),
            }
        )

    first_close = rows[0]["close"]
    last_close = rows[-1]["close"]
    change_pct = ((last_close - first_close) / first_close * 100.0) if first_close > 0 else 0.0

    return AvciChartResult(
        symbol=symbol,
        interval=interval,
        hours=hours,
        change_pct=round(change_pct, 3),
        last_price=last_close,
        klines=rows,
    )
