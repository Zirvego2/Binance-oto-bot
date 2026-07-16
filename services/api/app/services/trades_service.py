from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Trade

from .settings_service import get_or_create_bot_settings

ZERO = Decimal("0")


async def _aggregate_period(
    session: AsyncSession,
    *,
    admin_id: str,
    bot_mode: str,
    since: datetime,
    symbol: str | None = None,
) -> dict:
    winning_case = case((Trade.net_pnl_usdt > 0, 1), else_=0)
    losing_case = case((Trade.net_pnl_usdt < 0, 1), else_=0)

    query = select(
        func.count(Trade.id),
        func.coalesce(func.sum(Trade.net_pnl_usdt), 0),
        func.coalesce(func.sum(Trade.gross_pnl_usdt), 0),
        func.coalesce(func.sum(winning_case), 0),
        func.coalesce(func.sum(losing_case), 0),
    ).where(
        Trade.bot_mode == bot_mode,
        Trade.admin_id == admin_id,
        Trade.closed_at >= since,
    )

    if symbol:
        query = query.where(Trade.symbol == symbol.upper())

    count, net_pnl, gross_pnl, winning, losing = (await session.execute(query)).one()
    trades_count = int(count or 0)
    winning_trades = int(winning or 0)
    losing_trades = int(losing or 0)
    win_rate = (Decimal(winning_trades) / Decimal(trades_count) * 100) if trades_count else ZERO

    return {
        "net_pnl_usdt": Decimal(str(net_pnl or 0)),
        "gross_pnl_usdt": Decimal(str(gross_pnl or 0)),
        "trades_count": trades_count,
        "winning_trades": winning_trades,
        "losing_trades": losing_trades,
        "win_rate_pct": win_rate,
    }


async def build_trades_pnl_summary(
    session: AsyncSession, admin_id: str, *, symbol: str | None = None
) -> dict:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    now = datetime.now(timezone.utc)
    periods = {
        "last_24h": now - timedelta(hours=24),
        "last_7d": now - timedelta(days=7),
        "last_30d": now - timedelta(days=30),
    }
    result: dict[str, dict] = {}
    for key, since in periods.items():
        result[key] = await _aggregate_period(
            session,
            admin_id=admin_id,
            bot_mode=settings_row.mode,
            since=since,
            symbol=symbol,
        )
    return result


async def delete_trade_for_platform(
    session: AsyncSession,
    trade_id: str,
    *,
    acting_admin_id: str,
    ip_address: str | None = None,
) -> Trade | None:
    result = await session.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if trade is None:
        return None

    await _delete_trade_record(session, trade, acting_admin_id=acting_admin_id, ip_address=ip_address)
    return trade


async def _delete_trade_record(
    session: AsyncSession,
    trade: Trade,
    *,
    acting_admin_id: str,
    ip_address: str | None = None,
) -> None:
    from .audit_service import record_audit_log

    await record_audit_log(
        session,
        admin_id=acting_admin_id,
        action="DELETE_TRADE",
        entity_type="trade",
        entity_id=trade.id,
        before_data={
            "symbol": trade.symbol,
            "side": trade.side,
            "owner_admin_id": trade.admin_id,
            "net_pnl_usdt": str(trade.net_pnl_usdt),
            "closed_at": trade.closed_at.isoformat(),
        },
        ip_address=ip_address,
    )

    await session.delete(trade)
    await session.commit()
