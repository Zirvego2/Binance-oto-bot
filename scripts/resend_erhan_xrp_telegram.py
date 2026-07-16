"""Erhan XRPUSDT acilis Telegram bildirimini yeniden gonder."""

from __future__ import annotations

import asyncio
import os
import sys
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

    from app.core.config import get_settings
    from shared.db import Admin, Position
    from shared.telegram_delivery import deliver_position_opened_notification

    settings = get_settings()
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == "erhan-004@hotmail.com"))).scalar_one_or_none()
        if admin is None:
            print("Admin not found")
            return

        position = (
            await session.execute(
                select(Position)
                .where(Position.admin_id == admin.id, Position.symbol == "XRPUSDT", Position.status == "OPEN")
                .order_by(Position.opened_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if position is None:
            print("Open XRPUSDT position not found")
            return

        status = await deliver_position_opened_notification(
            session,
            settings,
            admin.id,
            source="manual_resend",
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            quantity=position.quantity,
            margin_usdt=position.margin_usdt,
            leverage=position.leverage,
            stop_loss_price=position.stop_loss_price,
            take_profit_price=position.take_profit_price,
            bot_mode="live",
            open_reason=position.open_reason,
        )
        await session.commit()
        print(f"Resend status={status} symbol={position.symbol} opened_at={position.opened_at}")


if __name__ == "__main__":
    asyncio.run(main())
