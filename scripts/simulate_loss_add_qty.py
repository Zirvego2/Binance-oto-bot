"""UNIUSDT ve ETHUSDT icin zarar ekleme miktarini simule eder."""

from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))
sys.path.insert(0, str(ROOT / "services" / "api"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.binance_client import get_binance_adapter_for_admin
    from shared.db import Admin, BotSettings, Symbol
    from shared.position_sizing import PositionSizingInputs, calculate_position_size

    sys.path.insert(0, str(ROOT / "services" / "worker"))
    from worker.symbol_filters import build_symbol_filters

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        admin = (
            await session.execute(select(Admin).where(Admin.email == "erhan-004@hotmail.com"))
        ).scalar_one()
        settings = (
            await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
        ).scalar_one()
        adapter = await get_binance_adapter_for_admin(session, admin.id, settings.mode)
        balances = await adapter.get_account_balance()
        usdt = next((b for b in balances if b.asset == "USDT"), None)
        available = usdt.available_balance if usdt else Decimal("0")
        print(f"available_balance={available}")

        for symbol_name in ("UNIUSDT", "ETHUSDT", "HYPEUSDT"):
            symbol_row = (
                await session.execute(select(Symbol).where(Symbol.symbol == symbol_name))
            ).scalar_one_or_none()
            if symbol_row is None:
                print(f"{symbol_name}: symbol row yok")
                continue
            filters = build_symbol_filters(symbol_row)
            mark = await adapter.get_mark_price(symbol_name)
            sizing = calculate_position_size(
                PositionSizingInputs(
                    margin_usdt=settings.margin_per_trade_usdt,
                    leverage=Decimal(settings.leverage),
                    price=mark.mark_price,
                    filters=filters,
                    available_balance_usdt=available,
                )
            )
            qty_str = str(sizing.quantity)
            print(
                f"{symbol_name}: price={mark.mark_price} ok={sizing.ok} reason={sizing.reason} "
                f"qty={sizing.quantity!r} str_qty={qty_str!r} step={filters.market_lot_step_size}"
            )


if __name__ == "__main__":
    asyncio.run(main())
