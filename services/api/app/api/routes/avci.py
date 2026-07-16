"""Avcı — basit yukselen/dusen coin avcisi."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin
from shared.distributed_lock import LockNotAcquiredError

from ...core.database import get_db
from ...schemas.avci import AvciChartOut, AvciOpenOut, AvciOpenRequest, AvciScanOut
from ...services.avci_service import (
    AvciOpenSkippedError,
    fetch_avci_chart,
    open_avci_position,
    scan_avci_coins,
)
from ..deps import get_current_admin, get_redis_dep, require_csrf

router = APIRouter(prefix="/avci", tags=["avci"])


@router.get("/scan", response_model=AvciScanOut)
async def avci_scan(
    limit: int = Query(default=15, ge=5, le=30),
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> AvciScanOut:
    result = await scan_avci_coins(session, admin.id, limit=limit)
    return AvciScanOut(
        analyzed_at=result.analyzed_at,
        top_gainers=result.top_gainers,
        top_losers=result.top_losers,
        limit=result.limit,
    )


@router.get("/chart", response_model=AvciChartOut)
async def avci_chart(
    symbol: str = Query(min_length=5, max_length=32),
    hours: int = Query(default=1, ge=1, le=24),
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> AvciChartOut:
    result = await fetch_avci_chart(session, admin.id, symbol, hours=hours)
    return AvciChartOut(
        symbol=result.symbol,
        interval=result.interval,
        hours=result.hours,
        change_pct=result.change_pct,
        last_price=result.last_price,
        klines=result.klines,
    )


@router.post("/open", response_model=AvciOpenOut)
async def avci_open(
    payload: AvciOpenRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
    admin=Depends(get_current_admin),
    _csrf=Depends(require_csrf),
) -> AvciOpenOut:
    ip = request.client.host if request.client else None
    try:
        result = await open_avci_position(
            session,
            redis,
            symbol=payload.symbol,
            side=payload.side,
            admin_id=admin.id,
            ip_address=ip,
        )
    except AvciOpenSkippedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LockNotAcquiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return AvciOpenOut(**result)
