"""Telegram delivery log durum ozeti (sent/skipped/failed)."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from shared.db import TelegramDeliveryLog

    async with Session() as session:
        rows = (
            await session.execute(
                select(TelegramDeliveryLog.status, func.count()).group_by(TelegramDeliveryLog.status)
            )
        ).all()
        print("Durum ozeti:", rows)

        non_sent = (
            await session.execute(
                select(TelegramDeliveryLog)
                .where(TelegramDeliveryLog.status != "sent")
                .order_by(TelegramDeliveryLog.created_at.desc())
                .limit(15)
            )
        ).scalars().all()
        for row in non_sent:
            print(row.created_at, row.admin_id, row.message_type, row.status, row.skip_reason, row.error_message)


if __name__ == "__main__":
    asyncio.run(main())
