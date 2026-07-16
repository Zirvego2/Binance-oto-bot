"""Canli Binance API baglantisini test eder."""

from __future__ import annotations

import asyncio
import os
import sys
import traceback
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

    from app.core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin
    from shared.db import Admin, BotSettings

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        for email in ("admin@example.com", "muzaffer@gmail.com", "erhan-004@hotmail.com"):
            admin = (await session.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none()
            if admin is None:
                continue
            settings_row = (
                await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
            ).scalar_one_or_none()
            mode = settings_row.mode if settings_row else "live"
            configured = await is_binance_configured_for_admin(session, admin.id, mode)
            print(f"--- {email} mode={mode} configured={configured}")
            if not configured:
                continue
            try:
                adapter = await get_binance_adapter_for_admin(session, admin.id, mode)
                info = await adapter.get_account_info()
                print(f"  OK balance={info.total_wallet_balance}")
            except Exception as exc:
                print(f"  FAIL: {type(exc).__name__}: {exc}")
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
