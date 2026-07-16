from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, Order

from ...core.binance_client import get_binance_adapter_for_admin
from ...core.database import get_db
from ...schemas.common import PaginatedResponse
from ...schemas.trading import OrderOut
from ...services.settings_service import get_or_create_bot_settings
from ..deps import get_current_admin

router = APIRouter(prefix="/orders", tags=["orders"])


@router.get("", response_model=PaginatedResponse[OrderOut])
async def list_orders(
    symbol: str | None = None,
    status_filter: str | None = None,
    order_type: str | None = None,
    purpose: str | None = None,
    active_only: bool = False,
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> PaginatedResponse[OrderOut]:
    query = select(Order).where(Order.admin_id == admin.id)
    count_query = select(func.count()).select_from(Order).where(Order.admin_id == admin.id)
    if symbol:
        query = query.where(Order.symbol == symbol.upper())
        count_query = count_query.where(Order.symbol == symbol.upper())
    if active_only:
        active_statuses = ("PENDING", "NEW", "SUBMITTING")
        query = query.where(Order.status.in_(active_statuses))
        count_query = count_query.where(Order.status.in_(active_statuses))
    elif status_filter:
        query = query.where(Order.status == status_filter.upper())
        count_query = count_query.where(Order.status == status_filter.upper())
    if order_type:
        query = query.where(Order.order_type == order_type.upper())
        count_query = count_query.where(Order.order_type == order_type.upper())
    if purpose:
        query = query.where(Order.purpose == purpose.upper())
        count_query = count_query.where(Order.purpose == purpose.upper())

    total = (await session.execute(count_query)).scalar_one()
    query = query.order_by(Order.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(query)).scalars().all()
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(
        items=[OrderOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{order_id}", response_model=OrderOut)
async def get_order(
    order_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> OrderOut:
    result = await session.execute(
        select(Order).where(Order.id == order_id, Order.admin_id == admin.id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Emir bulunamadi")
    return OrderOut.model_validate(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
async def cancel_limit_order(
    order_id: str,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> OrderOut:
    result = await session.execute(
        select(Order).where(Order.id == order_id, Order.admin_id == admin.id)
    )
    order = result.scalar_one_or_none()
    if order is None:
        raise HTTPException(status_code=404, detail="Emir bulunamadi")
    if order.status not in ("PENDING", "SUBMITTING", "NEW"):
        raise HTTPException(status_code=400, detail="Bu emir zaten tamamlanmis veya iptal edilmis")
    if order.purpose != "OPEN" or order.order_type != "LIMIT":
        raise HTTPException(status_code=400, detail="Sadece bekleyen olta (LIMIT OPEN) emirleri iptal edilebilir")

    settings_row = await get_or_create_bot_settings(session, admin.id)
    mode = settings_row.mode

    try:
        adapter = await get_binance_adapter_for_admin(session, admin.id, mode)
        await adapter.cancel_order(order.symbol, order.client_order_id)
    except Exception:  # noqa: BLE001
        pass

    order.status = "CANCELED"
    order.canceled_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(order)
    return OrderOut.model_validate(order)
