"""Cloud SQL / production DB uzerinde bootstrap admin hesaplarini olusturur."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, create_all_tables  # noqa: E402
from app.services.bootstrap_admin_service import ensure_bootstrap_admins  # noqa: E402


async def main() -> None:
    settings = get_settings()
    await create_all_tables()
    async with AsyncSessionLocal() as session:
        await ensure_bootstrap_admins(session, settings)
    print("Bootstrap tamamlandi:", settings.admin_email)


if __name__ == "__main__":
    asyncio.run(main())
