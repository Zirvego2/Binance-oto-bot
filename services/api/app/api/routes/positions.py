from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, Position
from shared.distributed_lock import LockNotAcquiredError

from ...core.config import get_settings
from ...core.database import get_db
from ...schemas.common import PaginatedResponse
from ...schemas.trading import (
    AddLosingPositionsResponse,
    ClosePositionRequest,
    EmergencyCloseAllRequest,
    EmergencyCloseAllResponse,
    PositionOut,
    PositionSyncOut,
)
from ...services.position_add_service import (
    PositionAddFailedError,
    PositionAddLimitReachedError,
    add_to_losing_positions,
    add_to_position_manually,
)
from ...services.position_service import (
    PositionAlreadyClosedError,
    close_all_positions_emergency,
    close_position_manually,
)
from ...services.position_sync_service import sync_positions_from_exchange, sync_positions_if_live_open
from ...services.settings_service import get_or_create_bot_settings
from ..deps import get_current_admin, get_redis_dep, require_csrf

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=PaginatedResponse[PositionOut])
async def list_positions(
    status_filter: str | None = None,
    symbol: str | None = None,
    open_reason: str | None = None,
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> PaginatedResponse[PositionOut]:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    if status_filter and status_filter.upper() == "OPEN":
        await sync_positions_if_live_open(session, admin.id)

    query = select(Position).where(Position.bot_mode == settings_row.mode, Position.admin_id == admin.id)
    count_query = (
        select(func.count()).select_from(Position).where(Position.bot_mode == settings_row.mode, Position.admin_id == admin.id)
    )

    if status_filter:
        query = query.where(Position.status == status_filter.upper())
        count_query = count_query.where(Position.status == status_filter.upper())
    if symbol:
        query = query.where(Position.symbol == symbol.upper())
        count_query = count_query.where(Position.symbol == symbol.upper())
    if open_reason:
        query = query.where(Position.open_reason == open_reason)
        count_query = count_query.where(Position.open_reason == open_reason)

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Position.opened_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(query)).scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(
        items=[PositionOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,
        total_pages=total_pages,
    )


@router.post("/sync", response_model=PositionSyncOut, dependencies=[Depends(require_csrf)])
async def sync_positions_endpoint(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> PositionSyncOut:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    result = await sync_positions_from_exchange(session, admin.id, settings_row.mode, force=True)
    return PositionSyncOut(
        local_open_count=result.local_open_count,
        exchange_open_count=result.exchange_open_count,
        closed_ghosts=result.closed_ghosts,
        synced_at=result.synced_at,
        in_sync=result.local_open_count == result.exchange_open_count,
        skipped_throttle=result.skipped_throttle,
    )


@router.post("/emergency-close-all", response_model=EmergencyCloseAllResponse, dependencies=[Depends(require_csrf)])
async def emergency_close_all_endpoint(
    payload: EmergencyCloseAllRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> EmergencyCloseAllResponse:
    settings = get_settings()
    result = await close_all_positions_emergency(
        session,
        admin.id,
        payload.password,
        settings.emergency_close_password,
        request.client.host if request.client else None,
    )
    return EmergencyCloseAllResponse(**result)


@router.post("/add-losing", response_model=AddLosingPositionsResponse, dependencies=[Depends(require_csrf)])
async def add_losing_positions_endpoint(
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    redis: Redis = Depends(get_redis_dep),
) -> AddLosingPositionsResponse:
    try:
        result = await add_to_losing_positions(
            session,
            redis,
            admin.id,
            request.client.host if request.client else None,
        )
    except PositionAddLimitReachedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LockNotAcquiredError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AddLosingPositionsResponse(**result)


@router.get("/{position_id}", response_model=PositionOut)
async def get_position(
    position_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> PositionOut:
    result = await session.execute(
        select(Position).where(Position.id == position_id, Position.admin_id == admin.id)
    )
    position = result.scalar_one_or_none()
    if position is None:
        raise HTTPException(status_code=404, detail="Pozisyon bulunamadi")
    return PositionOut.model_validate(position)


@router.post("/{position_id}/close", response_model=PositionOut, dependencies=[Depends(require_csrf)])
async def close_position_endpoint(
    position_id: str,
    payload: ClosePositionRequest,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> PositionOut:
    try:
        position = await close_position_manually(session, position_id, admin.id, payload.reason or "MANUAL")
    except PositionAlreadyClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PositionOut.model_validate(position)


@router.post("/{position_id}/add", response_model=PositionOut, dependencies=[Depends(require_csrf)])
async def add_to_position_endpoint(
    position_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    redis: Redis = Depends(get_redis_dep),
) -> PositionOut:
    try:
        position = await add_to_position_manually(
            session,
            redis,
            position_id,
            admin.id,
            ip_address=request.client.host if request.client else None,
        )
    except PositionAlreadyClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PositionAddLimitReachedError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PositionAddFailedError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except LockNotAcquiredError as exc:
        raise HTTPException(
            status_code=409,
            detail="Bot su an baska islem yapiyor; birka saniye sonra tekrar deneyin",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PositionOut.model_validate(position)
