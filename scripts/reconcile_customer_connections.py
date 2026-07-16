"""Firestore'daki musteri entegrasyonlarini SQL admin_profiles tablosuna aktarir."""

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

    from shared.db import Admin
    from shared.enums import UserRole
    from shared.firestore import init_firebase

    init_firebase(
        project_id=os.getenv("FIREBASE_PROJECT_ID", ""),
        service_account_path=os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", ""),
        service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        repo_root=ROOT,
    )

    from app.core.config import Settings
    from app.services.profile_service import reconcile_customer_connections

    settings = Settings()
    db_url = settings.database_url
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        admins = (
            await session.execute(
                select(Admin).where(
                    Admin.role == UserRole.CUSTOMER.value,
                    Admin.firebase_uid.is_not(None),
                )
            )
        ).scalars().all()
        for admin in admins:
            result = await reconcile_customer_connections(session, admin, settings)
            print(f"{admin.email}: sync={'firestore->sql' if result is None else 'sql->firestore'}")


if __name__ == "__main__":
    asyncio.run(main())
