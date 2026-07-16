"""Platform admin: musteri pozisyon listesi."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, Position
from shared.enums import UserRole

from ..schemas.common import PaginatedResponse
from ..schemas.trading import PositionOut


async def list_customer_positions_for_platform(
    session: AsyncSession,
    customer_id: str,
    *,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 25,
) -> PaginatedResponse[PositionOut]:
    customer = (
        await session.execute(
            select(Admin).where(Admin.id == customer_id, Admin.role == UserRole.CUSTOMER.value)
        )
    ).scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Musteri bulunamadi")

    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    base = select(Position).where(Position.admin_id == customer_id)
    count_query = select(func.count()).select_from(Position).where(Position.admin_id == customer_id)

    if status_filter:
        status_upper = status_filter.upper()
        base = base.where(Position.status == status_upper)
        count_query = count_query.where(Position.status == status_upper)

    total = (await session.execute(count_query)).scalar_one()
    rows = (
        await session.execute(
            base.order_by(Position.opened_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()
    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(
        items=[PositionOut.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
