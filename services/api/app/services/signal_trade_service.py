"""Manuel sinyal isleme: admin panelden gelen sinyali pozisyona donusturur."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, StrategySignal, Symbol
from shared.distributed_lock import DistributedLock, LockNotAcquiredError
from shared.platform_signals import is_shared_signal_row
from shared.trade_overrides import MANUAL_TRADE_OVERRIDES
from shared.trading_risk import build_risk_context, evaluate_manual_trade_risk

from ..core.binance_client import get_binance_adapter, is_binance_configured
from ..core.worker_bridge import get_order_engine_module
from .audit_service import record_audit_log
from .position_sync_service import sync_positions_from_exchange

EntryMode = Literal["market", "limit", "settings"]

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
    "limit_entry_already_pending": "Bu sembol icin zaten bekleyen olta emri var",
    "limit_entry_max_pending_reached": "Maksimum bekleyen olta emri sayisina ulasildi",
    "leverage_not_confirmed": "Kaldirac borsada onaylanamadi",
    "leverage_or_margin_type_setup_failed": "Kaldirac veya marj tipi ayarlanamadi",
    "market_direction_filter_blocked": "Piyasa yonu filtresi engelledi",
}


class SignalAlreadyConsumedError(Exception):
    pass


class SignalTradeSkippedError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(SKIP_REASON_MESSAGES.get(reason, reason))


@dataclass(frozen=True, slots=True)
class ExecuteSignalResult:
    signal_id: str
    status: Literal["opened", "limit_pending"]
    position_id: str | None = None
    order_id: str | None = None
    message: str | None = None


def _resolve_entry_mode(settings_row: BotSettings, entry_mode: EntryMode) -> bool:
    if entry_mode == "market":
        return False
    if entry_mode == "limit":
        return True
    return bool(getattr(settings_row, "limit_entry_enabled", False))


async def execute_signal_manually(
    session: AsyncSession,
    redis: Redis,
    signal_id: str,
    admin_id: str | None,
    entry_mode: EntryMode = "market",
    ip_address: str | None = None,
) -> ExecuteSignalResult:
    result = await session.execute(select(StrategySignal).where(StrategySignal.id == signal_id))
    signal = result.scalar_one_or_none()
    if signal is None:
        raise ValueError("Sinyal bulunamadi")
    if admin_id and signal.admin_id and signal.admin_id != admin_id:
        raise ValueError("Bu sinyale erisim yetkiniz yok")
    shared = is_shared_signal_row(signal.admin_id)
    if not shared and signal.consumed:
        raise SignalAlreadyConsumedError("Bu sinyal zaten kullanildi")

    settings_result = await session.execute(select(BotSettings).where(BotSettings.admin_id == admin_id))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row is None:
        raise ValueError("Bot ayarlari bulunamadi")

    if signal.bot_mode != settings_row.mode:
        raise ValueError("Sinyal modu hesabinizla uyusmuyor")

    if not is_binance_configured(signal.bot_mode):
        raise ValueError("Binance baglantisi yapilandirilmamis")

    ctx = await build_risk_context(session, settings_row, signal.symbol)
    risk = evaluate_manual_trade_risk(settings_row, ctx, signal.side)
    if not risk.ok:
        raise SignalTradeSkippedError(risk.reason or "risk_check_failed")

    symbol_result = await session.execute(select(Symbol).where(Symbol.symbol == signal.symbol))
    symbol_row = symbol_result.scalar_one_or_none()
    if symbol_row is None:
        raise ValueError("Sembol bulunamadi")

    order_engine = get_order_engine_module()
    adapter = get_binance_adapter(signal.bot_mode)
    use_limit = _resolve_entry_mode(settings_row, entry_mode)
    open_reason = "MANUAL_SIGNAL"

    lock = DistributedLock(redis, f"trading_engine:{admin_id}", ttl_seconds=30)
    acquired = await lock.acquire(blocking_timeout_seconds=5.0)
    if not acquired:
        raise LockNotAcquiredError("Islem kilidi alinamadi; worker baska bir islem yapiyor olabilir")

    try:
        if use_limit:
            order = await order_engine.open_position_limit_entry(
                session,
                adapter,
                settings_row,
                symbol_row,
                signal.side,
                signal.id,
                open_reason,
                signal.total_score,
                MANUAL_TRADE_OVERRIDES,
            )
            if not shared:
                signal.consumed = True
                signal.consumed_at = datetime.now(timezone.utc)
            await session.commit()
            await record_audit_log(
                session,
                admin_id=admin_id,
                action="SIGNAL_EXECUTE_LIMIT",
                entity_type="strategy_signal",
                entity_id=signal.id,
                after_data={
                    "symbol": signal.symbol,
                    "side": signal.side,
                    "entry_mode": entry_mode,
                    "order_id": order.id,
                },
                ip_address=ip_address,
            )
            return ExecuteSignalResult(
                signal_id=signal.id,
                status="limit_pending",
                order_id=order.id,
                message="Olta limit emri gonderildi; dolum bekleniyor",
            )

        position = await order_engine.open_position_for_signal(
            session,
            adapter,
            settings_row,
            symbol_row,
            signal.side,
            signal.id,
            open_reason,
            signal.total_score,
            MANUAL_TRADE_OVERRIDES,
        )
        if not shared:
            signal.consumed = True
            signal.consumed_at = datetime.now(timezone.utc)
            signal.resulting_position_id = position.id
        await sync_positions_from_exchange(session, settings_row.mode)
        await session.refresh(position)
        await session.commit()
        await record_audit_log(
            session,
            admin_id=admin_id,
            action="SIGNAL_EXECUTE_MARKET",
            entity_type="strategy_signal",
            entity_id=signal.id,
            after_data={
                "symbol": signal.symbol,
                "side": signal.side,
                "entry_mode": entry_mode,
                "position_id": position.id,
            },
            ip_address=ip_address,
        )
        return ExecuteSignalResult(
            signal_id=signal.id,
            status="opened",
            position_id=position.id,
            message="Pozisyon acildi",
        )
    except order_engine.PositionOpenSkipped as exc:
        await session.rollback()
        raise SignalTradeSkippedError(exc.reason) from exc
    finally:
        await lock.release()
