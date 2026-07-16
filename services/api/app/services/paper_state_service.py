"""PAPER modu icin musteri bazli hesap/pozisyon/emir goruntuleme servisi."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import AlgoOrder, Order, Position, Trade

from ..schemas.binance import BinanceAccountBalanceOut, BinanceAccountInfoOut, BinanceOrderOut, BinancePositionOut
from .settings_service import get_or_create_bot_settings


async def _realized_pnl_sum(session: AsyncSession, admin_id: str) -> Decimal:
    result = await session.execute(
        select(func.coalesce(func.sum(Trade.net_pnl_usdt), 0)).where(
            Trade.bot_mode == "paper",
            Trade.admin_id == admin_id,
        )
    )
    return Decimal(str(result.scalar_one()))


async def _open_paper_positions(session: AsyncSession, admin_id: str) -> list[Position]:
    result = await session.execute(
        select(Position).where(
            Position.bot_mode == "paper",
            Position.status == "OPEN",
            Position.admin_id == admin_id,
        )
    )
    return list(result.scalars().all())


async def get_paper_account_info(session: AsyncSession, admin_id: str) -> BinanceAccountInfoOut:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    realized_pnl = await _realized_pnl_sum(session, admin_id)
    wallet_balance = settings_row.paper_start_balance_usdt + realized_pnl

    open_positions = await _open_paper_positions(session, admin_id)
    total_unrealized_pnl = sum((p.unrealized_pnl for p in open_positions), Decimal("0"))
    locked_margin = sum((p.margin_usdt for p in open_positions), Decimal("0"))

    return BinanceAccountInfoOut(
        total_wallet_balance=wallet_balance,
        total_unrealized_pnl=total_unrealized_pnl,
        total_margin_balance=wallet_balance + total_unrealized_pnl,
        available_balance=wallet_balance - locked_margin,
        can_trade=True,
        multi_assets_margin=False,
    )


async def get_paper_balances(session: AsyncSession, admin_id: str) -> list[BinanceAccountBalanceOut]:
    info = await get_paper_account_info(session, admin_id)
    return [
        BinanceAccountBalanceOut(
            asset="USDT",
            wallet_balance=info.total_wallet_balance,
            available_balance=info.available_balance,
            unrealized_pnl=info.total_unrealized_pnl,
        )
    ]


async def get_paper_open_positions(session: AsyncSession, admin_id: str) -> list[BinancePositionOut]:
    positions = await _open_paper_positions(session, admin_id)
    return [
        BinancePositionOut(
            symbol=p.symbol,
            position_side=p.side,
            quantity=p.quantity,
            entry_price=p.entry_price,
            mark_price=p.mark_price or p.entry_price,
            unrealized_pnl=p.unrealized_pnl,
            leverage=p.leverage,
            margin_type=p.margin_type,
            liquidation_price=p.liquidation_price or Decimal("0"),
        )
        for p in positions
    ]


async def get_paper_open_orders(session: AsyncSession, admin_id: str) -> list[BinanceOrderOut]:
    result = await session.execute(
        select(Order).where(
            Order.bot_mode == "paper",
            Order.admin_id == admin_id,
            Order.status.in_(["PENDING", "SUBMITTING", "SUBMITTED", "NEW"]),
        )
    )
    return [
        BinanceOrderOut(
            symbol=o.symbol,
            binance_order_id=o.binance_order_id or "",
            client_order_id=o.client_order_id,
            side=o.side,
            order_type=o.order_type,
            status=o.status,
            price=o.price or Decimal("0"),
            orig_qty=o.quantity,
            executed_qty=o.filled_quantity,
        )
        for o in result.scalars().all()
    ]


async def get_paper_open_algo_orders(session: AsyncSession, admin_id: str) -> list[BinanceOrderOut]:
    result = await session.execute(
        select(AlgoOrder).where(
            AlgoOrder.bot_mode == "paper",
            AlgoOrder.admin_id == admin_id,
            AlgoOrder.status.in_(["PENDING", "SUBMITTED", "NEW"]),
        )
    )
    return [
        BinanceOrderOut(
            symbol=a.symbol,
            binance_order_id=a.binance_order_id or "",
            client_order_id=a.client_algo_id,
            side=a.side,
            order_type=a.order_type,
            status=a.status,
            price=a.trigger_price,
            orig_qty=Decimal("0"),
            executed_qty=Decimal("0"),
        )
        for a in result.scalars().all()
    ]
