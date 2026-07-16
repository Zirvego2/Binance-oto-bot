from __future__ import annotations



from fastapi import APIRouter, Depends

from sqlalchemy import func, select

from sqlalchemy.ext.asyncio import AsyncSession



from shared.db import AuditLog, BotEvent, RiskEvent, TelegramDeliveryLog



from ...core.database import get_db

from ...schemas.common import PaginatedResponse

from ...schemas.logs import AuditLogOut, BotEventOut, RiskEventOut, TelegramDeliveryLogOut

from ..deps import require_platform_admin



router = APIRouter(tags=["logs"])





@router.get("/logs", response_model=PaginatedResponse[BotEventOut])

async def list_logs(

    event_type: str | None = None,

    page: int = 1,

    page_size: int = 50,

    session: AsyncSession = Depends(get_db),

    _admin=Depends(require_platform_admin),

) -> PaginatedResponse[BotEventOut]:

    query = select(BotEvent)

    count_query = select(func.count()).select_from(BotEvent)

    if event_type:

        query = query.where(BotEvent.event_type == event_type)

        count_query = count_query.where(BotEvent.event_type == event_type)

    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(BotEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    rows = (await session.execute(query)).scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(

        items=[BotEventOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,

        total_pages=total_pages,

    )





@router.get("/audit-logs", response_model=PaginatedResponse[AuditLogOut])

async def list_audit_logs(

    page: int = 1,

    page_size: int = 50,

    session: AsyncSession = Depends(get_db),

    _admin=Depends(require_platform_admin),

) -> PaginatedResponse[AuditLogOut]:

    query = select(AuditLog)

    count_query = select(func.count()).select_from(AuditLog)

    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    rows = (await session.execute(query)).scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(

        items=[AuditLogOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,

        total_pages=total_pages,

    )





@router.get("/risk-events", response_model=PaginatedResponse[RiskEventOut])

async def list_risk_events(

    severity: str | None = None,

    page: int = 1,

    page_size: int = 50,

    session: AsyncSession = Depends(get_db),

    _admin=Depends(require_platform_admin),

) -> PaginatedResponse[RiskEventOut]:

    query = select(RiskEvent)

    count_query = select(func.count()).select_from(RiskEvent)

    if severity:

        query = query.where(RiskEvent.severity == severity.upper())

        count_query = count_query.where(RiskEvent.severity == severity.upper())

    total = (await session.execute(count_query)).scalar_one()

    query = query.order_by(RiskEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

    rows = (await session.execute(query)).scalars().all()

    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(

        items=[RiskEventOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,

        total_pages=total_pages,

    )





@router.get("/telegram-delivery-logs", response_model=PaginatedResponse[TelegramDeliveryLogOut])

async def list_telegram_delivery_logs(

    admin_id: str | None = None,

    status: str | None = None,

    message_type: str | None = None,

    page: int = 1,

    page_size: int = 50,

    session: AsyncSession = Depends(get_db),

    _admin=Depends(require_platform_admin),

) -> PaginatedResponse[TelegramDeliveryLogOut]:

    query = select(TelegramDeliveryLog)

    count_query = select(func.count()).select_from(TelegramDeliveryLog)

    if admin_id:

        query = query.where(TelegramDeliveryLog.admin_id == admin_id)

        count_query = count_query.where(TelegramDeliveryLog.admin_id == admin_id)

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

        items=[TelegramDeliveryLogOut.model_validate(r) for r in rows],

        total=total,

        page=page,

        page_size=page_size,

        total_pages=total_pages,

    )

