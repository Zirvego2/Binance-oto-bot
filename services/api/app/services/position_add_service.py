"""Manuel pozisyon ekleme (DCA) servisi."""

from __future__ import annotations

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, Position, Symbol
from shared.distributed_lock import DistributedLock, LockNotAcquiredError

from ..core.binance_client import get_binance_adapter, is_binance_configured
from ..core.worker_bridge import get_order_engine_module
from .audit_service import record_audit_log
from .position_service import PositionAlreadyClosedError


class PositionAddLimitReachedError(Exception):
    pass


class PositionAddFailedError(Exception):
    pass


async def add_to_position_manually(
    session: AsyncSession,
    redis: Redis,
    position_id: str,
    admin_id: str | None,
    ip_address: str | None = None,
) -> Position:
    result = await session.execute(select(Position).where(Position.id == position_id))
    position = result.scalar_one_or_none()
    if position is None:
        raise ValueError("Pozisyon bulunamadi")

    if position.status != "OPEN":
        raise PositionAlreadyClosedError("Pozisyon acik degil")

    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row is None:
        raise ValueError("Bot ayarlari bulunamadi")

    max_adds = int(getattr(settings_row, "loss_add_max_count", 0))
    current_adds = int(getattr(position, "loss_add_count", 0) or 0)
    if max_adds <= 0:
        raise PositionAddLimitReachedError("Pozisyon ekleme devre disi (maks. ekleme 0)")
    if current_adds >= max_adds:
        raise PositionAddLimitReachedError(f"Maksimum ekleme sayisina ulasildi ({max_adds})")

    if not is_binance_configured(position.bot_mode):
        raise ValueError("Binance baglantisi yapilandirilmamis")

    symbol_result = await session.execute(select(Symbol).where(Symbol.symbol == position.symbol))
    symbol_row = symbol_result.scalar_one_or_none()
    if symbol_row is None:
        raise ValueError("Sembol bulunamadi")

    order_engine = get_order_engine_module()
    adapter = get_binance_adapter(position.bot_mode)

    lock = DistributedLock(redis, "trading_engine", ttl_seconds=45)
    acquired = await lock.acquire(blocking_timeout_seconds=20.0)
    if not acquired:
        raise LockNotAcquiredError("Islem kilidi alinamadi; baska bir islem suruyor olabilir")

    try:
        added = await order_engine.add_to_position_on_loss(
            session,
            adapter,
            settings_row,
            position,
            symbol_row,
            purpose="MANUAL_ADD",
            event_note="manuel",
        )
        if not added:
            await session.rollback()
            raise PositionAddFailedError(
                "Ekleme emri gonderilemedi veya SL/TP guncellenemedi (koruyucu emirler yenilenemedi)"
            )

        await session.commit()
        await session.refresh(position)

        await record_audit_log(
            session,
            admin_id=admin_id,
            action="MANUAL_POSITION_ADD",
            entity_type="position",
            entity_id=position.id,
            after_data={
                "symbol": position.symbol,
                "side": position.side,
                "loss_add_count": position.loss_add_count,
                "entry_price": str(position.entry_price),
                "quantity": str(position.quantity),
            },
            ip_address=ip_address,
        )
        await session.commit()
        return position
    except Exception:
        await session.rollback()
        raise
    finally:
        await lock.release()


async def add_to_losing_positions(
    session: AsyncSession,
    redis: Redis,
    admin_id: str | None,
    ip_address: str | None = None,
) -> dict:
    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings_row = settings_result.scalar_one_or_none()
    if settings_row is None:
        raise ValueError("Bot ayarlari bulunamadi")

    max_adds = int(getattr(settings_row, "loss_add_max_count", 0))
    if max_adds <= 0:
        raise PositionAddLimitReachedError("Pozisyon ekleme devre disi (maks. ekleme 0)")

    result = await session.execute(
        select(Position).where(
            Position.status == "OPEN",
            Position.bot_mode == settings_row.mode,
            Position.roi_pct < 0,
        )
    )
    losing_positions = result.scalars().all()

    added_positions: list[str] = []
    failed_positions: list[str] = []
    skipped_positions: list[str] = []

    for position in losing_positions:
        current_adds = int(getattr(position, "loss_add_count", 0) or 0)
        if current_adds >= max_adds:
            skipped_positions.append(position.symbol)
            continue
        try:
            await add_to_position_manually(session, redis, position.id, admin_id, ip_address)
            added_positions.append(position.symbol)
        except PositionAddLimitReachedError:
            skipped_positions.append(position.symbol)
        except Exception:
            failed_positions.append(position.symbol)

    await record_audit_log(
        session,
        admin_id=admin_id,
        action="ADD_LOSING_POSITIONS",
        entity_type="position",
        after_data={"added": added_positions, "failed": failed_positions, "skipped": skipped_positions},
        ip_address=ip_address,
    )
    await session.commit()

    return {
        "added_positions": added_positions,
        "failed_positions": failed_positions,
        "skipped_positions": skipped_positions,
        "added_count": len(added_positions),
    }
