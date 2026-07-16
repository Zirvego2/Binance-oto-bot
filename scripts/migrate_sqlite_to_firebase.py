"""SQLite (trading_bot.db) verisini Firestore'a aktarir.

Kullanim:
  python scripts/migrate_sqlite_to_firebase.py           # oncelikli (~6-7k kayit)
  python scripts/migrate_sqlite_to_firebase.py --full     # tum tablolar (kotayi asabilir)
  python scripts/migrate_sqlite_to_firebase.py --heavy    # buyuk analiz tablolari
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import db_session_scope
from app.core.firebase import init_firebase
from app.services.firestore_migration_service import migrate_sql_to_firestore
from shared.db import Admin


async def main(mode: str) -> None:
    settings = get_settings()
    init_firebase(settings)
    if not settings.firebase_project_id:
        print("HATA: FIREBASE_PROJECT_ID tanimli degil")
        sys.exit(1)

    async with db_session_scope() as session:
        admin = (await session.execute(select(Admin).order_by(Admin.created_at.asc()).limit(1))).scalar_one_or_none()
        if admin is None:
            print("HATA: SQLite'da admin kaydi yok")
            sys.exit(1)
        if not admin.firebase_uid:
            print(f"UYARI: {admin.email} icin firebase_uid yok. Once /login ile giris yapin.")
            sys.exit(1)

        print(f"Migrasyon basliyor: mode={mode}, admin={admin.email}, uid={admin.firebase_uid}")
        try:
            stats = await migrate_sql_to_firestore(session, admin.firebase_uid, mode=mode)
        except Exception as exc:  # noqa: BLE001
            print(f"HATA: {exc}")
            print("Firebase Spark gunluk yazma kotasi (20.000) dolmus olabilir. Yarin tekrar deneyin veya Blaze plana gecin.")
            sys.exit(1)

        total = sum(stats.values())
        print(f"Tamamlandi. Toplam {total} kayit aktarildi.")
        for name, count in sorted(stats.items()):
            if count:
                print(f"  {name}: {count}")
        print(f"Firestore: customers/{admin.firebase_uid}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true", help="Tum tablolar (70k+ kayit)")
    parser.add_argument("--heavy", action="store_true", help="Buyuk analiz tablolari")
    args = parser.parse_args()
    mode = "full" if args.full else "heavy" if args.heavy else "priority"
    asyncio.run(main(mode))
