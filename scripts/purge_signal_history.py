"""Analiz ve sinyal gecmisini SQLite + Firestore'dan temizler.

Kullanim:
  python scripts/purge_signal_history.py              # onay sor
  python scripts/purge_signal_history.py --yes        # onaysiz calistir
  python scripts/purge_signal_history.py --sql-only   # sadece SQLite
  python scripts/purge_signal_history.py --firebase-only
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from dotenv import load_dotenv
from sqlalchemy import delete, func, select

load_dotenv(ROOT / ".env")

from app.core.config import get_settings
from app.core.database import db_session_scope
from app.core.firebase import init_firebase
from shared.db import Admin, AiExplanation, AnalysisResult, StrategySignal
from shared.firestore import delete_tenant_subcollection, firebase_enabled, list_tenant_admin_ids
from shared.firestore.schema import SUBCOL_ANALYSIS, SUBCOL_SIGNALS


async def _count_sql(session) -> dict[str, int]:
    return {
        "analysis_results": (await session.execute(select(func.count()).select_from(AnalysisResult))).scalar() or 0,
        "strategy_signals": (await session.execute(select(func.count()).select_from(StrategySignal))).scalar() or 0,
        "ai_explanations": (await session.execute(select(func.count()).select_from(AiExplanation))).scalar() or 0,
    }


async def _purge_sql(session) -> dict[str, int]:
    before = await _count_sql(session)
    await session.execute(delete(AiExplanation))
    await session.execute(delete(StrategySignal))
    await session.execute(delete(AnalysisResult))
    await session.commit()
    return before


async def _purge_firestore(admin_ids: list[str]) -> dict[str, int]:
    stats = {"analysis": 0, "signals": 0, "legacy_strategy_signals": 0}
    for admin_id in admin_ids:
        stats["analysis"] += await delete_tenant_subcollection(admin_id, SUBCOL_ANALYSIS)
        stats["signals"] += await delete_tenant_subcollection(admin_id, SUBCOL_SIGNALS)
        stats["legacy_strategy_signals"] += await delete_tenant_subcollection(admin_id, "strategy_signals")
    return stats


async def main(*, yes: bool, sql_only: bool, firebase_only: bool) -> None:
    settings = get_settings()
    init_firebase(settings)

    async with db_session_scope() as session:
        before = await _count_sql(session)
        admins = (await session.execute(select(Admin))).scalars().all()
        admin_ids = [a.id for a in admins]

    print("Silinecek SQLite kayitlari:")
    for name, count in before.items():
        print(f"  {name}: {count}")
    print(f"Musteri sayisi: {len(admin_ids)}")

    if not yes:
        answer = input("\nDevam etmek icin 'EVET' yazin: ").strip()
        if answer != "EVET":
            print("Iptal edildi.")
            return

    if not firebase_only:
        async with db_session_scope() as session:
            purged = await _purge_sql(session)
        print("\nSQLite temizlendi:")
        for name, count in purged.items():
            print(f"  {name}: {count} silindi")

    if not sql_only and firebase_enabled():
        firestore_admin_ids = await list_tenant_admin_ids()
        merged_ids = sorted(set(admin_ids) | set(firestore_admin_ids))
        stats = await _purge_firestore(merged_ids)
        print("\nFirestore temizlendi:")
        for name, count in stats.items():
            print(f"  {name}: {count} silindi")
    elif not sql_only:
        print("\nFirebase devre disi — Firestore temizligi atlandi.")

    print("\nTamam. Yeni analiz/sinyaller tenants/{adminId}/analysis ve /signals altina yazilacak.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analiz ve sinyal gecmisini temizle")
    parser.add_argument("--yes", action="store_true", help="Onay sormadan calistir")
    parser.add_argument("--sql-only", action="store_true", help="Sadece SQLite temizle")
    parser.add_argument("--firebase-only", action="store_true", help="Sadece Firestore temizle")
    args = parser.parse_args()
    asyncio.run(main(yes=args.yes, sql_only=args.sql_only, firebase_only=args.firebase_only))
