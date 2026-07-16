"""Yeni pozisyon acilis/kapanis ve Telegram log olaylarini izler (polling)."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main(duration_sec: int = 900, interval_sec: int = 15) -> None:
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
        last_log_count = (await session.execute(select(func.count()).select_from(TelegramDeliveryLog))).scalar_one()
        seen_closed_ids: set[str] = set(
            (await session.execute(select(Position.id).where(Position.status == "CLOSED"))).scalars().all()
        )
        seen_open_ids: set[str] = set(
            (await session.execute(select(Position.id).where(Position.status == "OPEN"))).scalars().all()
        )
        print(f"BASLANGIC: telegram_log={last_log_count} open={len(seen_open_ids)} closed={len(seen_closed_ids)}", flush=True)

        deadline = time.time() + duration_sec
        while time.time() < deadline:
            await asyncio.sleep(interval_sec)
            await session.close()
            async with Session() as s2:
                new_count = (await s2.execute(select(func.count()).select_from(TelegramDeliveryLog))).scalar_one()
                if new_count != last_log_count:
                    logs = (
                        await s2.execute(
                            select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(new_count - last_log_count)
                        )
                    ).scalars().all()
                    for lg in logs:
                        admin = (await s2.execute(select(Admin).where(Admin.id == lg.admin_id))).scalar_one_or_none()
                        email = admin.email if admin else str(lg.admin_id)
                        print(
                            f"YENI_TELEGRAM_LOG: {lg.created_at} | {email} | {lg.message_type} | {lg.status} | "
                            f"{lg.skip_reason or '-'} | {lg.symbol or '-'} | err={lg.error_message or '-'}",
                            flush=True,
                        )
                    last_log_count = new_count

                open_ids = set(
                    (await s2.execute(select(Position.id).where(Position.status == "OPEN"))).scalars().all()
                )
                closed_ids = set(
                    (await s2.execute(select(Position.id).where(Position.status == "CLOSED"))).scalars().all()
                )
                newly_closed = closed_ids - seen_closed_ids
                newly_opened = open_ids - seen_open_ids
                for pid in newly_opened:
                    pos = (await s2.execute(select(Position).where(Position.id == pid))).scalar_one()
                    admin = (await s2.execute(select(Admin).where(Admin.id == pos.admin_id))).scalar_one_or_none()
                    email = admin.email if admin else str(pos.admin_id)
                    print(f"YENI_POZISYON_ACILDI: {pos.opened_at} | {email} | {pos.symbol}", flush=True)
                for pid in newly_closed:
                    pos = (await s2.execute(select(Position).where(Position.id == pid))).scalar_one()
                    admin = (await s2.execute(select(Admin).where(Admin.id == pos.admin_id))).scalar_one_or_none()
                    email = admin.email if admin else str(pos.admin_id)
                    print(f"YENI_POZISYON_KAPANDI: {pos.closed_at} | {email} | {pos.symbol}", flush=True)
                seen_open_ids = open_ids
                seen_closed_ids = closed_ids
        print("IZLEME_BITTI", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
