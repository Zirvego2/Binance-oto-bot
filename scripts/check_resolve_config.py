"""Her aktif musteri icin _resolve_customer_config'in hatasiz calistigini dogrular."""

from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))
sys.path.insert(0, str(ROOT / "services" / "worker"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    import os

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from shared.db import Admin, BotSettings
    from shared.telegram_delivery import _resolve_customer_config

    sys.path.insert(0, str(ROOT / "services" / "worker"))
    from worker.config import get_worker_settings  # type: ignore

    settings = get_worker_settings()

    async with Session() as session:
        active_admin_ids = (
            await session.execute(
                select(BotSettings.admin_id).where(
                    BotSettings.bot_enabled.is_(True), BotSettings.admin_id.is_not(None)
                )
            )
        ).scalars().all()
        for admin_id in active_admin_ids:
            admin = (await session.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
            email = admin.email if admin else admin_id
            try:
                cfg, skip_reason = await _resolve_customer_config(session, settings, admin_id)
                ready = cfg is not None and cfg.bot_token and cfg.chat_id and cfg.enabled
                print(f"{email}: OK skip_reason={skip_reason} ready={ready}")
            except Exception:
                print(f"{email}: EXCEPTION!")
                traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
