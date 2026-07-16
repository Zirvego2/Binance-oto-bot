"""Ayni admin+symbol+mesaj_tipi icin kisa surede birden fazla Telegram
gonderimi olup olmadigini izler (mukerrer bildirim tespiti)."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main(duration_sec: int = 1200, interval_sec: int = 15) -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from shared.db import Admin, TelegramDeliveryLog

    async with Session() as session:
        start_row = (
            await session.execute(select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(1))
        ).scalar_one_or_none()
        cutoff = start_row.created_at if start_row else None
        print(f"BASLANGIC_CUTOFF: {cutoff}", flush=True)

        seen_ids: set[str] = set()
        if start_row:
            seen_ids.add(start_row.id)

        deadline = time.time() + duration_sec
        while time.time() < deadline:
            await asyncio.sleep(interval_sec)
            async with Session() as s2:
                query = select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.asc())
                if cutoff is not None:
                    query = query.where(TelegramDeliveryLog.created_at >= cutoff)
                logs = (await s2.execute(query)).scalars().all()
                new_logs = [lg for lg in logs if lg.id not in seen_ids]
                for lg in new_logs:
                    seen_ids.add(lg.id)
                    admin = (await s2.execute(select(Admin).where(Admin.id == lg.admin_id))).scalar_one_or_none()
                    email = admin.email if admin else str(lg.admin_id)
                    print(
                        f"YENI_LOG: {lg.created_at} | {email} | {lg.message_type} | {lg.status} | {lg.symbol or '-'}",
                        flush=True,
                    )

                grouped: dict[tuple, list] = defaultdict(list)
                for lg in logs:
                    if lg.message_type in ("position_opened", "position_closed") and lg.status == "sent":
                        grouped[(lg.admin_id, lg.symbol, lg.message_type)].append(lg)
                for key, items in grouped.items():
                    if len(items) < 2:
                        continue
                    items.sort(key=lambda x: x.created_at)
                    for i in range(1, len(items)):
                        delta = (items[i].created_at - items[i - 1].created_at).total_seconds()
                        if delta < 120:
                            print(
                                f"MUKERRER_TESPIT: admin={key[0]} symbol={key[1]} type={key[2]} "
                                f"t1={items[i-1].created_at} t2={items[i].created_at} delta={delta:.1f}s",
                                flush=True,
                            )
        print("IZLEME_BITTI", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
