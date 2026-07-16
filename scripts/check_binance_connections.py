"""Musteri Binance baglanti durumunu kontrol eder."""

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
    from shared.customer_credentials import profile_binance_credentials, resolve_admin_profile_record
    from shared.db import Admin, AdminProfile, BotSettings

    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    settings = get_settings()

    async with Session() as session:
        admins = (await session.execute(select(Admin))).scalars().all()
        for admin in admins:
            profile = await resolve_admin_profile_record(
                session,
                admin,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
            )
            creds = profile_binance_credentials(
                profile,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
            )
            has_creds = bool(creds and creds.api_key and creds.api_secret)
            sql_profile = (
                await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
            ).scalar_one_or_none()
            sql_has = bool(
                sql_profile
                and sql_profile.binance_api_key_enc
                and sql_profile.binance_api_secret_enc
            )
            bot_settings = (
                await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
            ).scalar_one_or_none()
            bot_enabled = bot_settings.bot_enabled if bot_settings else False
            print(
                f"{admin.email}: creds_ready={has_creds} sql_enc={sql_has} "
                f"bot_enabled={bot_enabled} firebase_uid={admin.firebase_uid or '-'}"
            )


if __name__ == "__main__":
    asyncio.run(main())
