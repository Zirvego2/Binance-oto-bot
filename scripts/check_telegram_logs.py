"""Telegram delivery log ve son pozisyon hareketlerini kontrol eder."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
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

    from shared.db import Admin, Position, TelegramDeliveryLog

    async with Session() as session:
        total = (await session.execute(select(func.count()).select_from(TelegramDeliveryLog))).scalar_one()
        print("Toplam telegram log:", total)
        print()

        logs = (
            await session.execute(
                select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(30)
            )
        ).scalars().all()
        print("=== SON 30 TELEGRAM LOG ===")
        for lg in logs:
            admin = (await session.execute(select(Admin).where(Admin.id == lg.admin_id))).scalar_one_or_none()
            email = admin.email if admin else str(lg.admin_id)
            reason = lg.skip_reason or "-"
            symbol = lg.symbol or "-"
            err = lg.error_message or "-"
            print(f"{lg.created_at} | {email} | {lg.message_type} | {lg.status} | {reason} | {symbol} | err={err}")

        print()
        print("=== SON 6 SAATTE ACILAN POZISYONLAR ===")
        cutoff = datetime.now(timezone.utc) - timedelta(hours=6)
        positions = (
            await session.execute(
                select(Position).where(Position.opened_at >= cutoff).order_by(Position.opened_at.desc())
            )
        ).scalars().all()
        for pos in positions:
            admin = (await session.execute(select(Admin).where(Admin.id == pos.admin_id))).scalar_one_or_none()
            email = admin.email if admin else str(pos.admin_id)
            print(f"{pos.opened_at} | {email} | {pos.symbol} | {pos.status} | closed={pos.closed_at}")

        if not positions:
            print("  (son 6 saatte pozisyon yok)")


if __name__ == "__main__":
    asyncio.run(main())
