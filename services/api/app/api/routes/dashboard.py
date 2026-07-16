from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, DailyStatistic

from ...core.database import get_db
from ...schemas.dashboard import DashboardOut, DashboardRealtimeOut, DashboardStatisticsOut
from ...services.dashboard_service import build_dashboard
from ..deps import get_current_admin

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardOut)
async def get_dashboard(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> DashboardOut:
    data = await build_dashboard(session, admin.id)
    return DashboardOut(**data)


@router.get("/statistics", response_model=list[DashboardStatisticsOut])
async def get_statistics(
    days: int = 30, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> list[DashboardStatisticsOut]:
    result = await session.execute(
        select(DailyStatistic)
        .where(DailyStatistic.admin_id == admin.id)
        .order_by(DailyStatistic.stat_date.desc())
        .limit(days)
    )
    rows = result.scalars().all()
    return [
        DashboardStatisticsOut(
            stat_date=str(row.stat_date),
            trades_count=row.trades_count,
            winning_trades=row.winning_trades,
            losing_trades=row.losing_trades,
            win_rate_pct=row.win_rate_pct,
            gross_pnl_usdt=row.gross_pnl_usdt,
            net_pnl_usdt=row.net_pnl_usdt,
            total_commission_usdt=row.total_commission_usdt,
            total_funding_usdt=row.total_funding_usdt,
        )
        for row in rows
    ]


@router.get("/realtime", response_model=DashboardRealtimeOut)
async def get_realtime(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> DashboardRealtimeOut:
    data = await build_dashboard(session, admin.id)
    return DashboardRealtimeOut(**data, server_time=datetime.now(timezone.utc))
