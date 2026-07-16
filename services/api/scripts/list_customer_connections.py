"""Musteri Binance ve Telegram baglanti bilgilerini listeler (platform admin).

Kullanim:
    docker compose exec api python scripts/list_customer_connections.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from shared.customer_credentials import profile_binance_credentials, profile_telegram_credentials
from shared.db import Admin
from shared.db.models_profile import AdminProfile
from shared.enums import UserRole


async def main() -> None:
    settings = get_settings()
    rows: list[dict] = []

    async with AsyncSessionLocal() as session:
        admins = (
            await session.execute(
                select(Admin).where(Admin.role == UserRole.CUSTOMER.value).order_by(Admin.email)
            )
        ).scalars().all()

        for admin in admins:
            profile = (
                await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
            ).scalar_one_or_none()

            binance = profile_binance_credentials(
                profile,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
                env=None,
            )
            telegram = profile_telegram_credentials(
                profile,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
                env=None,
                allow_env_fallback=False,
            )

            rows.append(
                {
                    "email": admin.email,
                    "full_name": admin.full_name,
                    "approval_status": admin.approval_status,
                    "binance": {
                        "configured": binance is not None,
                        "source": binance.source if binance else None,
                        "api_key": binance.api_key if binance else None,
                        "api_secret": binance.api_secret if binance else None,
                    },
                    "telegram": {
                        "configured": bool(telegram.bot_token and telegram.chat_id),
                        "enabled": telegram.enabled,
                        "source": telegram.source if telegram.bot_token else None,
                        "bot_token": telegram.bot_token or None,
                        "chat_id": telegram.chat_id or None,
                    },
                }
            )

    if not rows:
        print("Kayitli musteri bulunamadi.")
        return

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
