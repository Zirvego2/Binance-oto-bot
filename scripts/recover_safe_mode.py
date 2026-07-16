"""SAFE_MODE: hayalet pozisyonlari kapat, reconciliation calistir, botu RUNNING yap."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from sqlalchemy import select  # noqa: E402

from app.core.database import AsyncSessionLocal, create_all_tables  # noqa: E402
from app.services.position_sync_service import sync_positions_from_exchange  # noqa: E402
from app.services.reconciliation_service import run_and_persist_reconciliation  # noqa: E402
from app.services.settings_service import get_or_create_bot_settings  # noqa: E402
from shared.db import Admin, BotRuntimeStatus  # noqa: E402


async def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@example.com"
    await create_all_tables()

    async with AsyncSessionLocal() as session:
        admin = (await session.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none()
        if admin is None:
            raise SystemExit(f"Admin bulunamadi: {email}")

        settings = await get_or_create_bot_settings(session, admin.id)
        runtime_before = (
            await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin.id))
        ).scalar_one_or_none()
        print("Once:", runtime_before.run_state if runtime_before else None, runtime_before.safe_mode_reason if runtime_before else None)

        sync = await sync_positions_from_exchange(session, admin.id, settings.mode, force=True, full=True)
        print("Senkron:", sync)

        run = await run_and_persist_reconciliation(session, admin.id, settings.mode, triggered_by="manual_recovery")
        print("Reconciliation:", run.status, "mismatches=", run.mismatches_found, "safe_mode=", run.entered_safe_mode)

        runtime_after = (
            await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin.id))
        ).scalar_one_or_none()
        print("Sonra:", runtime_after.run_state if runtime_after else None, runtime_after.safe_mode_reason if runtime_after else None)


if __name__ == "__main__":
    asyncio.run(main())
