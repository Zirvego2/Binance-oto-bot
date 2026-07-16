from __future__ import annotations



from fastapi import APIRouter, Depends, HTTPException, status

from redis.asyncio import Redis

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession



from shared.db import Admin, TelegramDeliveryLog



from ...core.config import Settings, get_settings

from ...core.database import get_db

from ...schemas.common import PaginatedResponse
from ...schemas.profile import (

    ProfileConnectionsOut,

    ProfileConnectionsUpdate,

    ProfileFullNameUpdate,

    ProfileOut,

    ProfileTestResult,

    ProfileUnlockRequest,

    ProfileUnlockResponse,

    TelegramDiscoverChatIdRequest,

    TelegramDiscoverChatIdResponse,

    ProfileTelegramDeliveryLogOut,

)

from ...services.audit_service import record_audit_log

from ...services.profile_service import (

    build_profile_out,

    get_connections_out,

    is_profile_unlocked,

    lock_profile,

    test_binance_connection,

    test_telegram_connection,

    discover_telegram_chat_id_for_profile,

    unlock_profile,

    update_connections,

    verify_profile_password,

)

from ...services.settings_service import get_or_create_bot_settings

from ..deps import get_current_admin, get_redis_dep, require_csrf, require_profile_unlock



router = APIRouter(prefix="/profile", tags=["profile"])





@router.get("", response_model=ProfileOut)

async def get_profile(

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    redis: Redis = Depends(get_redis_dep),

    settings: Settings = Depends(get_settings),

) -> ProfileOut:

    unlocked = await is_profile_unlocked(redis, admin.id)

    return await build_profile_out(session, admin, settings, unlocked=unlocked)





@router.put("/full-name", response_model=ProfileOut, dependencies=[Depends(require_csrf)])

async def update_full_name(

    payload: ProfileFullNameUpdate,

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    redis: Redis = Depends(get_redis_dep),

    settings: Settings = Depends(get_settings),

) -> ProfileOut:

    admin.full_name = payload.full_name.strip() if payload.full_name else None

    await session.commit()

    await session.refresh(admin)

    unlocked = await is_profile_unlocked(redis, admin.id)

    return await build_profile_out(session, admin, settings, unlocked=unlocked)





@router.post("/unlock", response_model=ProfileUnlockResponse, dependencies=[Depends(require_csrf)])

async def unlock_connections(

    payload: ProfileUnlockRequest,

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    redis: Redis = Depends(get_redis_dep),

    settings: Settings = Depends(get_settings),

) -> ProfileUnlockResponse:

    if not await verify_profile_password(payload.password, settings):

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Profil sifresi hatali")

    ttl = settings.profile_unlock_ttl_minutes * 60

    await unlock_profile(redis, admin.id, ttl)

    await record_audit_log(

        session,

        admin_id=admin.id,

        action="PROFILE_UNLOCK",

        entity_type="admin_profile",

        entity_id=admin.id,

    )

    return ProfileUnlockResponse(ok=True, connections_unlocked=True, expires_in_seconds=ttl)





@router.post("/lock", dependencies=[Depends(require_csrf)])

async def lock_connections(

    admin: Admin = Depends(get_current_admin),

    redis: Redis = Depends(get_redis_dep),

) -> dict[str, bool]:

    await lock_profile(redis, admin.id)

    return {"ok": True}





@router.get("/connections", response_model=ProfileConnectionsOut)

async def get_connections(

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    settings: Settings = Depends(get_settings),

    _: None = Depends(require_profile_unlock),

) -> ProfileConnectionsOut:

    return await get_connections_out(session, admin, settings)





@router.put("/connections", response_model=ProfileConnectionsOut, dependencies=[Depends(require_csrf)])

async def save_connections(

    payload: ProfileConnectionsUpdate,

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    settings: Settings = Depends(get_settings),

    _: None = Depends(require_profile_unlock),

) -> ProfileConnectionsOut:

    result = await update_connections(session, admin, settings, payload)

    from ...core.binance_client import invalidate_binance_adapter_cache



    invalidate_binance_adapter_cache(admin.id)

    await record_audit_log(

        session,

        admin_id=admin.id,

        action="PROFILE_CONNECTIONS_UPDATE",

        entity_type="admin_profile",

        entity_id=admin.id,

    )

    return result





@router.post("/test/binance", response_model=ProfileTestResult, dependencies=[Depends(require_csrf)])

async def test_binance(

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    settings: Settings = Depends(get_settings),

    _: None = Depends(require_profile_unlock),

) -> ProfileTestResult:

    bot_settings = await get_or_create_bot_settings(session, admin.id)

    ok, message = await test_binance_connection(session, admin, settings, bot_settings.mode)

    return ProfileTestResult(ok=ok, message=message)





@router.post("/test/telegram", response_model=ProfileTestResult, dependencies=[Depends(require_csrf)])

async def test_telegram(

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    settings: Settings = Depends(get_settings),

    _: None = Depends(require_profile_unlock),

) -> ProfileTestResult:

    ok, message = await test_telegram_connection(session, admin, settings)

    return ProfileTestResult(ok=ok, message=message)





@router.post("/telegram/discover-chat-id", response_model=TelegramDiscoverChatIdResponse, dependencies=[Depends(require_csrf)])

async def discover_telegram_chat_id(

    payload: TelegramDiscoverChatIdRequest,

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

    settings: Settings = Depends(get_settings),

    _: None = Depends(require_profile_unlock),

) -> TelegramDiscoverChatIdResponse:

    ok, chat_id, message = await discover_telegram_chat_id_for_profile(

        session,

        admin,

        settings,

        bot_token_override=payload.telegram_bot_token,

    )

    return TelegramDiscoverChatIdResponse(ok=ok, chat_id=chat_id, message=message)





@router.get("/telegram-logs", response_model=PaginatedResponse[ProfileTelegramDeliveryLogOut])

async def list_my_telegram_logs(

    status: str | None = None,

    message_type: str | None = None,

    page: int = 1,

    page_size: int = 50,

    admin: Admin = Depends(get_current_admin),

    session: AsyncSession = Depends(get_db),

) -> PaginatedResponse[ProfileTelegramDeliveryLogOut]:

    query = select(TelegramDeliveryLog).where(TelegramDeliveryLog.admin_id == admin.id)

    count_query = select(func.count()).select_from(TelegramDeliveryLog).where(TelegramDeliveryLog.admin_id == admin.id)

    if status:

        query = query.where(TelegramDeliveryLog.status == status.lower())

        count_query = count_query.where(TelegramDeliveryLog.status == status.lower())

    if message_type:

        query = query.where(TelegramDeliveryLog.message_type == message_type)

        count_query = count_query.where(TelegramDeliveryLog.message_type == message_type)

    total = (await session.execute(count_query)).scalar_one()

    query = (

        query.order_by(TelegramDeliveryLog.created_at.desc())

        .offset((page - 1) * page_size)

        .limit(page_size)

    )

    rows = (await session.execute(query)).scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(

        items=[ProfileTelegramDeliveryLogOut.model_validate(r) for r in rows],

        total=total,

        page=page,

        page_size=page_size,

        total_pages=total_pages,

    )

