from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, Trade

from ...core.database import get_db
from ...schemas.common import PaginatedResponse
from ...schemas.trading import TradeOut, TradePnlSummaryOut
from ..deps import get_current_admin
from ...services.trades_service import build_trades_pnl_summary

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("/pnl-summary", response_model=TradePnlSummaryOut)
async def get_trades_pnl_summary(
    symbol: str | None = None,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> TradePnlSummaryOut:
    data = await build_trades_pnl_summary(session, admin.id, symbol=symbol)
    return TradePnlSummaryOut(**data)


@router.get("", response_model=PaginatedResponse[TradeOut])
async def list_trades(
    symbol: str | None = None,
    side: str | None = None,
    bot_mode: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: str = "closed_at",
    sort_dir: str = "desc",
    page: int = 1,
    page_size: int = 25,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> PaginatedResponse[TradeOut]:
    query = select(Trade).where(Trade.admin_id == admin.id)
    count_query = select(func.count()).select_from(Trade).where(Trade.admin_id == admin.id)

    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
        count_query = count_query.where(Trade.symbol == symbol.upper())
    if side:
        query = query.where(Trade.side == side.upper())
        count_query = count_query.where(Trade.side == side.upper())
    if bot_mode:
        query = query.where(Trade.bot_mode == bot_mode.lower())
        count_query = count_query.where(Trade.bot_mode == bot_mode.lower())
    if date_from:
        query = query.where(Trade.closed_at >= date_from)
        count_query = count_query.where(Trade.closed_at >= date_from)
    if date_to:
        query = query.where(Trade.closed_at <= date_to)
        count_query = count_query.where(Trade.closed_at <= date_to)

    sort_column = {"closed_at": Trade.closed_at, "opened_at": Trade.opened_at, "net_pnl_usdt": Trade.net_pnl_usdt}.get(
        sort_by, Trade.closed_at
    )
    query = query.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())

    total = (await session.execute(count_query)).scalar_one()
    query = query.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(query)).scalars().all()
    total_pages = max(1, (total + page_size - 1) // page_size)
    return PaginatedResponse(
        items=[TradeOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(
    trade_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> TradeOut:
    result = await session.execute(
        select(Trade).where(Trade.id == trade_id, Trade.admin_id == admin.id)
    )
    trade = result.scalar_one_or_none()
    if trade is None:
        raise HTTPException(status_code=404, detail="Islem bulunamadi")
    return TradeOut.model_validate(trade)
