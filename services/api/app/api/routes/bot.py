from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin

from ...core.config import Settings, get_settings
from ...core.database import get_db
from ...schemas.bot import (
    BotStatusOut,
    ChangeModeRequest,
    ChangeModeResponse,
    EmergencyStopRequest,
    EmergencyStopResponse,
)
from ...services.bot_control_service import change_mode, emergency_stop, get_bot_status, start_bot, stop_bot
from ..deps import get_current_admin, get_redis_dep, require_csrf

router = APIRouter(prefix="/bot", tags=["bot"])


@router.post("/start", response_model=BotStatusOut, dependencies=[Depends(require_csrf)])
async def start(
    request: Request, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BotStatusOut:
    ip = request.client.host if request.client else None
    await start_bot(session, admin, ip)
    status_data = await get_bot_status(session, admin.id)
    return BotStatusOut(**status_data)


@router.post("/stop", response_model=BotStatusOut, dependencies=[Depends(require_csrf)])
async def stop(
    request: Request, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BotStatusOut:
    ip = request.client.host if request.client else None
    await stop_bot(session, admin, ip)
    status_data = await get_bot_status(session, admin.id)
    return BotStatusOut(**status_data)


@router.post("/emergency-stop", response_model=EmergencyStopResponse, dependencies=[Depends(require_csrf)])
async def emergency_stop_endpoint(
    payload: EmergencyStopRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> EmergencyStopResponse:
    ip = request.client.host if request.client else None
    result = await emergency_stop(session, admin, payload.close_all_positions, payload.confirmation_text, ip)
    return EmergencyStopResponse(**result)


@router.get("/status", response_model=BotStatusOut)
async def status_endpoint(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BotStatusOut:
    status_data = await get_bot_status(session, admin.id)
    return BotStatusOut(**status_data)


@router.post("/change-mode", response_model=ChangeModeResponse, dependencies=[Depends(require_csrf)])
async def change_mode_endpoint(
    payload: ChangeModeRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
    app_settings: Settings = Depends(get_settings),
    redis: Redis = Depends(get_redis_dep),
) -> ChangeModeResponse:
    ip = request.client.host if request.client else None
    result = await change_mode(
        session, admin, payload.target_mode, payload.confirmation_text, payload.risk_ack, app_settings, redis, ip
    )
    return ChangeModeResponse(**result)
