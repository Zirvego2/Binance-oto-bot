"""muzaffer@gmail.com Binance credential diagnostic."""

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
    from shared.masking import mask_value

    settings = get_settings()
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./trading_bot.db")
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == "muzaffer@gmail.com"))).scalar_one_or_none()
        if admin is None:
            print("Admin not found")
            return

        bot = (await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))).scalar_one_or_none()
        sql_profile = (
            await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
        ).scalar_one_or_none()

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

        print(f"admin_id={admin.id}")
        print(f"firebase_uid={getattr(admin, 'firebase_uid', None)}")
        print(f"mode={bot.mode if bot else '?'}")
        print(f"profile_admin_id={profile.admin_id}")
        print(f"credential_source={creds.source if creds else None}")
        if creds:
            print(f"api_key_masked={mask_value(creds.api_key)}")
            print(f"api_key_len={len(creds.api_key)}")
            print(f"api_secret_len={len(creds.api_secret)}")
        print(f"sql_profile_has_key={bool(sql_profile and sql_profile.binance_api_key_enc)}")
        print(f"resolved_profile_has_key={bool(profile.binance_api_key_enc)}")

        # Raw ping + signed call with explicit error detail
        if creds:
            from shared.binance.rest_client import BinanceRestClient

            client = BinanceRestClient(
                base_url=settings.binance_futures_base_url,
                api_key=creds.api_key,
                api_secret=creds.api_secret,
            )
            try:
                await client.sync_server_time()
                print("server_time_sync=OK")
            except Exception as exc:
                print(f"server_time_sync=FAIL {exc}")

            try:
                data = await client.signed_get("/fapi/v2/account")
                print(f"account=OK balance={data.get('totalWalletBalance')}")
            except Exception as exc:
                print(f"account=FAIL {exc}")

            try:
                data = await client.signed_get("/fapi/v1/apiTradingStatus")
                print(f"trading_status={data}")
            except Exception as exc:
                print(f"trading_status=FAIL {exc}")


if __name__ == "__main__":
    asyncio.run(main())
