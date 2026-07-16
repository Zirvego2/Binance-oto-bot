"""Platform admin: tum musterilerin islem gecmisi."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, Trade
from shared.enums import UserRole

from ..schemas.common import PaginatedResponse
from ..schemas.platform_admin import AdminTradeOut
from ..schemas.trading import TradeOut


def _trade_to_admin_out(trade: Trade, email: str | None, full_name: str | None) -> AdminTradeOut:
    base = TradeOut.model_validate(trade)
    return AdminTradeOut(
        **base.model_dump(),
        customer_id=trade.admin_id,
        customer_email=email,
        customer_full_name=full_name,
    )


async def list_platform_trades(
    session: AsyncSession,
    *,
    symbol: str | None = None,
    side: str | None = None,
    bot_mode: str | None = None,
    customer_id: str | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "closed_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> PaginatedResponse[AdminTradeOut]:
    base_filters = [Admin.role == UserRole.CUSTOMER.value]

    if symbol:
        base_filters.append(Trade.symbol == symbol.upper())
    if side:
        base_filters.append(Trade.side == side.upper())
    if bot_mode:
        base_filters.append(Trade.bot_mode == bot_mode.lower())
    if customer_id:
        base_filters.append(Trade.admin_id == customer_id)
    if search:
        term = f"%{search.strip().lower()}%"
        base_filters.append(
            or_(
                func.lower(Admin.email).like(term),
                func.lower(func.coalesce(Admin.full_name, "")).like(term),
            )
        )
    if date_from:
        base_filters.append(Trade.closed_at >= date_from)
    if date_to:
        base_filters.append(Trade.closed_at <= date_to)

    count_query = (
        select(func.count())
        .select_from(Trade)
        .join(Admin, Trade.admin_id == Admin.id)
        .where(*base_filters)
    )
    total = (await session.execute(count_query)).scalar_one()

    sort_column = {
        "closed_at": Trade.closed_at,
        "opened_at": Trade.opened_at,
        "net_pnl_usdt": Trade.net_pnl_usdt,
    }.get(sort_by, Trade.closed_at)
    order = sort_column.desc() if sort_dir == "desc" else sort_column.asc()

    query = (
        select(Trade, Admin.email, Admin.full_name)
        .join(Admin, Trade.admin_id == Admin.id)
        .where(*base_filters)
        .order_by(order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await session.execute(query)).all()
    items = [_trade_to_admin_out(trade, email, full_name) for trade, email, full_name in rows]
    total_pages = max(1, (total + page_size - 1) // page_size)

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
