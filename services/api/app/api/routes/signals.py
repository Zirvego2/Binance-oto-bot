from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AnalysisResult, StrategySignal
from shared.distributed_lock import LockNotAcquiredError
from shared.platform_signals import shared_admin_id_clause

from ...core.database import get_db
from ...schemas.signals import AnalysisResultOut, ExecuteSignalRequest, ExecuteSignalResponse, StrategySignalOut
from ...services.settings_service import get_or_create_bot_settings
from ...services.signal_trade_service import (
    SignalAlreadyConsumedError,
    SignalTradeSkippedError,
    execute_signal_manually,
)
from ..deps import get_current_admin, get_redis_dep, require_csrf

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[StrategySignalOut])
async def list_signals(
    symbol: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[StrategySignalOut]:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    query = (
        select(StrategySignal)
        .where(shared_admin_id_clause(StrategySignal.admin_id), StrategySignal.bot_mode == settings_row.mode)
        .order_by(StrategySignal.created_at.desc())
        .limit(limit)
    )
    if symbol:
        query = query.where(StrategySignal.symbol == symbol.upper())
    rows = (await session.execute(query)).scalars().all()
    return [StrategySignalOut.model_validate(r) for r in rows]


@router.get("/analysis", response_model=list[AnalysisResultOut])
async def list_analysis_results(
    symbol: str | None = None,
    limit: int = 100,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[AnalysisResultOut]:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    query = (
        select(AnalysisResult)
        .where(shared_admin_id_clause(AnalysisResult.admin_id), AnalysisResult.bot_mode == settings_row.mode)
        .order_by(AnalysisResult.analyzed_at.desc())
        .limit(limit)
    )
    if symbol:
        query = query.where(AnalysisResult.symbol == symbol.upper())
    rows = (await session.execute(query)).scalars().all()
    return [AnalysisResultOut.model_validate(r) for r in rows]


@router.post(
    "/{signal_id}/execute",
    response_model=ExecuteSignalResponse,
    dependencies=[Depends(require_csrf)],
)
async def execute_signal(
    signal_id: str,
    payload: ExecuteSignalRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    redis: Redis = Depends(get_redis_dep),
) -> ExecuteSignalResponse:
    client_ip = request.client.host if request.client else None
    try:
        result = await execute_signal_manually(
            session,
            redis,
            signal_id,
            admin.id,
            entry_mode=payload.entry_mode,
            ip_address=client_ip,
        )
    except SignalAlreadyConsumedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SignalTradeSkippedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LockNotAcquiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExecuteSignalResponse(
        signal_id=result.signal_id,
        status=result.status,
        position_id=result.position_id,
        order_id=result.order_id,
        message=result.message,
    )


@router.get("/{signal_id}", response_model=StrategySignalOut)
async def get_signal(
    signal_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> StrategySignalOut:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    result = await session.execute(
        select(StrategySignal).where(
            StrategySignal.id == signal_id,
            shared_admin_id_clause(StrategySignal.admin_id),
            StrategySignal.bot_mode == settings_row.mode,
        )
    )
    signal = result.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=404, detail="Sinyal bulunamadi")
    return StrategySignalOut.model_validate(signal)
