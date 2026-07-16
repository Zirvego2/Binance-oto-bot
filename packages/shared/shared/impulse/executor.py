"""BTC impuls tarama ve toplu pozisyon acma."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.db import BotEvent, BotRuntimeStatus, BotSettings, Symbol
from shared.trade_overrides import TradeOpenOverrides, apply_trade_overrides
from shared.trading_risk import build_risk_context, evaluate_manual_trade_risk

from .detector import detect_btc_impulse
from .scanner import ImpulseCandidate, scan_extreme_candidates

logger = logging.getLogger("shared.impulse")


@dataclass(frozen=True, slots=True)
class ImpulseScanResult:
    btc_direction: str
    btc_change_pct: float
    counter_side: str | None
    candidates: list[ImpulseCandidate]
    cooldown_active: bool
    message: str


@dataclass(frozen=True, slots=True)
class ImpulseExecuteResult:
    opened: list[str]
    skipped: list[str]
    failed: list[str]
    btc_direction: str
    btc_change_pct: float


PositionOpener = Callable[..., Any]
PositionOpenSkipped = type[Any]


def impulse_overrides(settings_row: BotSettings) -> TradeOpenOverrides:
    leverage = settings_row.impulse_leverage if settings_row.impulse_leverage > 0 else settings_row.leverage
    return TradeOpenOverrides(
        margin_usdt=settings_row.impulse_margin_usdt,
        leverage=leverage,
        take_profit_roi_pct=settings_row.impulse_tp_roi_pct,
        stop_loss_roi_pct=settings_row.impulse_sl_roi_pct,
        bypass_market_direction_filter=True,
    )


async def _get_runtime(session: AsyncSession, admin_id: str | None) -> BotRuntimeStatus:
    from shared.tenant_settings import get_or_create_bot_runtime

    if not admin_id:
        result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.id == "default"))
        runtime = result.scalar_one_or_none()
        if runtime is None:
            runtime = BotRuntimeStatus(id="default")
            session.add(runtime)
            await session.flush()
        return runtime
    return await get_or_create_bot_runtime(session, admin_id)


def _cooldown_active(runtime: BotRuntimeStatus, settings_row: BotSettings) -> bool:
    if runtime.impulse_last_event_at is None:
        return False
    last = runtime.impulse_last_event_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    until = last + timedelta(minutes=settings_row.impulse_cooldown_minutes)
    return datetime.now(timezone.utc) < until


async def scan_impulse(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    *,
    manual_side: str | None = None,
    ignore_cooldown: bool = False,
) -> ImpulseScanResult:
    runtime = await _get_runtime(session, settings_row.admin_id)
    cooldown = _cooldown_active(runtime, settings_row)

    impulse = await detect_btc_impulse(
        adapter,
        min_change_pct=float(settings_row.impulse_btc_min_change_pct),
        lookback_minutes=settings_row.impulse_lookback_minutes,
    )

    direction = impulse.direction if manual_side is None else ("PUMP" if manual_side == "SHORT" else "DUMP")
    counter_side = manual_side
    if counter_side is None:
        counter_side = "SHORT" if impulse.direction == "PUMP" else "LONG" if impulse.direction == "DUMP" else None

    if manual_side is None and impulse.direction == "NONE":
        return ImpulseScanResult(
            btc_direction="NONE",
            btc_change_pct=impulse.change_pct,
            counter_side=None,
            candidates=[],
            cooldown_active=cooldown,
            message="BTC impuls esigi asilmadi",
        )

    if cooldown and not ignore_cooldown and manual_side is None:
        return ImpulseScanResult(
            btc_direction=impulse.direction,
            btc_change_pct=impulse.change_pct,
            counter_side=counter_side,
            candidates=[],
            cooldown_active=True,
            message="Impuls bekleme suresi aktif",
        )

    scan_direction = direction if manual_side else impulse.direction
    candidates = await scan_extreme_candidates(
        session, adapter, settings_row, scan_direction, force_side=manual_side
    )

    runtime.impulse_last_scan_at = datetime.now(timezone.utc)
    runtime.impulse_last_btc_change_pct = Decimal(str(round(impulse.change_pct, 4)))
    runtime.impulse_last_direction = impulse.direction if impulse.direction != "NONE" else direction
    await session.commit()

    msg = f"{len(candidates)} aday bulundu ({counter_side or '—'})"
    return ImpulseScanResult(
        btc_direction=impulse.direction if manual_side is None else direction,
        btc_change_pct=impulse.change_pct,
        counter_side=counter_side,
        candidates=candidates,
        cooldown_active=cooldown,
        message=msg,
    )


async def execute_impulse_candidates(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    candidates: list[ImpulseCandidate],
    *,
    open_position_fn: PositionOpener,
    position_open_skipped: PositionOpenSkipped,
    triggered_by: str = "manual",
    max_entries: int | None = None,
) -> ImpulseExecuteResult:
    if not settings_row.bot_enabled:
        return ImpulseExecuteResult([], [], ["bot_disabled"], "NONE", 0.0)

    limit = max_entries or settings_row.impulse_max_entries
    overrides = impulse_overrides(settings_row)
    effective_settings = apply_trade_overrides(settings_row, overrides)

    opened: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    impulse = await detect_btc_impulse(
        adapter,
        min_change_pct=float(settings_row.impulse_btc_min_change_pct),
        lookback_minutes=settings_row.impulse_lookback_minutes,
    )

    for candidate in candidates[:limit]:
        if len(opened) >= limit:
            break

        ctx = await build_risk_context(session, settings_row, candidate.symbol)
        risk = evaluate_manual_trade_risk(settings_row, ctx, candidate.side)
        if not risk.ok:
            skipped.append(f"{candidate.symbol}:{risk.reason}")
            continue

        symbol_result = await session.execute(select(Symbol).where(Symbol.symbol == candidate.symbol))
        symbol_row = symbol_result.scalar_one_or_none()
        if symbol_row is None:
            failed.append(f"{candidate.symbol}:symbol_not_found")
            continue

        try:
            await open_position_fn(
                session,
                adapter,
                effective_settings,
                symbol_row,
                candidate.side,
                None,
                "IMPULSE_COUNTER",
                Decimal(str(round(candidate.score, 2))),
                trade_overrides=overrides,
            )
            opened.append(f"{candidate.symbol}:{candidate.side}")
        except position_open_skipped as exc:
            reason = getattr(exc, "reason", str(exc))
            skipped.append(f"{candidate.symbol}:{reason}")
            await session.rollback()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Impuls pozisyon acilamadi: %s", candidate.symbol)
            failed.append(f"{candidate.symbol}:{exc}")
            await session.rollback()

    runtime = await _get_runtime(session, settings_row.admin_id)
    now = datetime.now(timezone.utc)
    runtime.impulse_last_event_at = now
    runtime.impulse_last_opened_count = len(opened)
    runtime.impulse_last_btc_change_pct = Decimal(str(round(impulse.change_pct, 4)))
    runtime.impulse_last_direction = impulse.direction if impulse.direction != "NONE" else runtime.impulse_last_direction

    session.add(
        BotEvent(
            event_type="IMPULSE_EXECUTE",
            message=f"Impuls islem ({triggered_by}): {len(opened)} acildi, {len(skipped)} atlandi",
            bot_mode=settings_row.mode,
            details={
                "triggered_by": triggered_by,
                "opened": opened,
                "skipped": skipped,
                "failed": failed,
                "btc_change_pct": str(impulse.change_pct),
            },
        )
    )
    await session.commit()

    return ImpulseExecuteResult(
        opened=opened,
        skipped=skipped,
        failed=failed,
        btc_direction=impulse.direction,
        btc_change_pct=impulse.change_pct,
    )
