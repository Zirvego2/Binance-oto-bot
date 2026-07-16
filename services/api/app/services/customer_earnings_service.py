"""Platform admin: musteri kazanc ozetleri (gunluk / haftalik / aylik)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, BotSettings, Position, Trade
from shared.enums import UserRole
from shared.timezone_utils import period_starts as local_period_starts

from ..schemas.platform_admin import (
    CustomerEarningsDetailOut,
    CustomerEarningsOut,
    CustomerEarningsPeriodOut,
    PlatformEarningsSummaryOut,
)

ZERO = Decimal("0")


async def _aggregate_trades_by_admin(session: AsyncSession, since: datetime) -> dict[str, dict]:
    winning_case = case((Trade.net_pnl_usdt > 0, 1), else_=0)
    losing_case = case((Trade.net_pnl_usdt < 0, 1), else_=0)

    rows = (
        await session.execute(
            select(
                Trade.admin_id,
                func.count(Trade.id),
                func.coalesce(func.sum(Trade.net_pnl_usdt), 0),
                func.coalesce(func.sum(Trade.gross_pnl_usdt), 0),
                func.coalesce(func.sum(winning_case), 0),
                func.coalesce(func.sum(losing_case), 0),
            )
            .where(Trade.admin_id.is_not(None), Trade.closed_at >= since)
            .group_by(Trade.admin_id)
        )
    ).all()

    out: dict[str, dict] = {}
    for admin_id, count, net_pnl, gross_pnl, winning, losing in rows:
        if not admin_id:
            continue
        trades_count = int(count or 0)
        winning_trades = int(winning or 0)
        losing_trades = int(losing or 0)
        win_rate = (Decimal(winning_trades) / Decimal(trades_count) * 100) if trades_count else ZERO
        out[admin_id] = {
            "net_pnl_usdt": Decimal(str(net_pnl or 0)),
            "gross_pnl_usdt": Decimal(str(gross_pnl or 0)),
            "trades_count": trades_count,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate_pct": win_rate,
        }
    return out


def _empty_period() -> CustomerEarningsPeriodOut:
    return CustomerEarningsPeriodOut(
        net_pnl_usdt=ZERO,
        gross_pnl_usdt=ZERO,
        trades_count=0,
        winning_trades=0,
        losing_trades=0,
        win_rate_pct=ZERO,
    )


def _to_period(data: dict | None) -> CustomerEarningsPeriodOut:
    if not data:
        return _empty_period()
    return CustomerEarningsPeriodOut(**data)


async def get_customer_earnings_report(session: AsyncSession) -> PlatformEarningsSummaryOut:
    now = datetime.now(timezone.utc)
    starts = local_period_starts(now)

    daily_map = await _aggregate_trades_by_admin(session, starts["daily"])
    weekly_map = await _aggregate_trades_by_admin(session, starts["weekly"])
    monthly_map = await _aggregate_trades_by_admin(session, starts["monthly"])

    customers = (
        await session.execute(select(Admin).where(Admin.role == UserRole.CUSTOMER.value).order_by(Admin.email))
    ).scalars().all()

    rows: list[CustomerEarningsOut] = []
    daily_total = weekly_total = monthly_total = ZERO

    for customer in customers:
        daily = _to_period(daily_map.get(customer.id))
        weekly = _to_period(weekly_map.get(customer.id))
        monthly = _to_period(monthly_map.get(customer.id))

        daily_total += daily.net_pnl_usdt
        weekly_total += weekly.net_pnl_usdt
        monthly_total += monthly.net_pnl_usdt

        rows.append(
            CustomerEarningsOut(
                customer_id=customer.id,
                email=customer.email,
                full_name=customer.full_name,
                approval_status=customer.approval_status,
                daily=daily,
                weekly=weekly,
                monthly=monthly,
            )
        )

    rows.sort(key=lambda r: r.monthly.net_pnl_usdt, reverse=True)

    return PlatformEarningsSummaryOut(
        daily_total_net_pnl_usdt=daily_total,
        weekly_total_net_pnl_usdt=weekly_total,
        monthly_total_net_pnl_usdt=monthly_total,
        customer_count=len(rows),
        customers=rows,
        generated_at=now,
    )


async def _aggregate_trades_for_admin(
    session: AsyncSession,
    admin_id: str,
    since: datetime | None = None,
) -> dict:
    winning_case = case((Trade.net_pnl_usdt > 0, 1), else_=0)
    losing_case = case((Trade.net_pnl_usdt < 0, 1), else_=0)

    query = (
        select(
            func.count(Trade.id),
            func.coalesce(func.sum(Trade.net_pnl_usdt), 0),
            func.coalesce(func.sum(Trade.gross_pnl_usdt), 0),
            func.coalesce(func.sum(winning_case), 0),
            func.coalesce(func.sum(losing_case), 0),
        )
        .where(Trade.admin_id == admin_id)
    )
    if since is not None:
        query = query.where(Trade.closed_at >= since)

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


async def get_customer_earnings_detail(session: AsyncSession, customer_id: str) -> CustomerEarningsDetailOut:
    from fastapi import HTTPException, status

    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    settings_row = (
        await session.execute(select(BotSettings).where(BotSettings.admin_id == customer_id))
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    starts = local_period_starts(now)

    daily = _to_period(await _aggregate_trades_for_admin(session, customer_id, starts["daily"]))
    weekly = _to_period(await _aggregate_trades_for_admin(session, customer_id, starts["weekly"]))
    monthly = _to_period(await _aggregate_trades_for_admin(session, customer_id, starts["monthly"]))
    lifetime = _to_period(await _aggregate_trades_for_admin(session, customer_id))

    open_stats = (
        await session.execute(
            select(
                func.count(Position.id),
                func.coalesce(func.sum(Position.unrealized_pnl), 0),
            ).where(Position.admin_id == customer_id, Position.status == "OPEN")
        )
    ).one()
    open_positions_count = int(open_stats[0] or 0)
    total_unrealized_pnl_usdt = Decimal(str(open_stats[1] or 0))

    return CustomerEarningsDetailOut(
        customer_id=customer.id,
        email=customer.email,
        full_name=customer.full_name,
        approval_status=customer.approval_status,
        bot_mode=settings_row.mode if settings_row else None,
        bot_enabled=bool(settings_row and settings_row.bot_enabled),
        open_positions_count=open_positions_count,
        total_unrealized_pnl_usdt=total_unrealized_pnl_usdt,
        daily=daily,
        weekly=weekly,
        monthly=monthly,
        lifetime=lifetime,
        generated_at=now,
    )
