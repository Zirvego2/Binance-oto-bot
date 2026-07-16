"""Musteri bazli Telegram bildirim sistemi denetimi."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared"))
sys.path.insert(0, str(ROOT / "services" / "worker"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


async def main() -> None:
    from shared.firestore import get_customer, init_firebase
    from sqlalchemy import func, select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker

    init_firebase(
        project_id=os.getenv("FIREBASE_PROJECT_ID", ""),
        service_account_path=os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", ""),
        service_account_json=os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", ""),
        repo_root=ROOT,
    )

    from shared.customer_credentials import (
        profile_telegram_credentials,
        resolve_admin_profile_record,
        resolve_telegram_config_for_admin,
    )
    from shared.db import Admin, AdminProfile, BotSettings, TelegramDeliveryLog
    from shared.enums import ApprovalStatus, UserRole
    from shared.telegram_delivery import deliver_test_notification
    from shared.tenant_settings import list_active_tenant_admins
    from worker.config import WorkerSettings

    settings = WorkerSettings()
    env_chat = os.getenv("TELEGRAM_CHAT_ID", "")

    db_url = settings.database_url
    if db_url.startswith("sqlite:///"):
        db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    engine = create_async_engine(db_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=== TELEGRAM SISTEM ANALIZI ===")
    print(f"ENV chat: {env_chat or '(bos)'}")
    print()

    issues: list[str] = []

    async with Session() as session:
        tenants = await list_active_tenant_admins(
            session,
            encryption_key=settings.app_encryption_key,
            app_secret=settings.app_secret,
        )
        tenant_emails = {t.email for t in tenants}
        print("Aktif musteriler (worker):", sorted(tenant_emails))
        print()

        customers = (
            await session.execute(
                select(Admin).where(
                    Admin.role == UserRole.CUSTOMER.value,
                    Admin.approval_status == ApprovalStatus.APPROVED.value,
                )
            )
        ).scalars().all()

        for admin in customers:
            cfg = await resolve_telegram_config_for_admin(
                session,
                admin.id,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
                env=None,
            )
            profile = await resolve_admin_profile_record(
                session,
                admin,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
            )
            tg = profile_telegram_credentials(
                profile,
                encryption_key=settings.app_encryption_key,
                app_secret=settings.app_secret,
                env=None,
                allow_env_fallback=False,
            )
            customer_doc = await get_customer(admin.firebase_uid) if admin.firebase_uid else None
            fs = (customer_doc or {}).get("connections") or {}
            sql = (
                await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
            ).scalar_one_or_none()
            bs = (
                await session.execute(select(BotSettings).where(BotSettings.admin_id == admin.id))
            ).scalar_one_or_none()

            ready = cfg.is_ready if cfg else False
            chat = tg.chat_id if tg else ""
            bot_id = tg.bot_token.split(":")[0] if tg and tg.bot_token and ":" in tg.bot_token else "?"
            source = "firestore" if profile.admin_id == "firestore" else "sql"

            print(f"[{admin.email}]")
            print(f"  worker_aktif={admin.email in tenant_emails} bot_enabled={bool(bs and bs.bot_enabled)} telegram_ready={ready}")
            print(f"  kaynak={source} bot_id={bot_id} chat_son4={chat[-4:] if chat else '-'}")
            print(f"  firestore_tg={bool(fs.get('telegramBotTokenEnc'))} sql_tg={bool(sql and sql.telegram_bot_token_enc)}")

            if not ready:
                issues.append(f"{admin.email}: Telegram yapilandirilmamis")
            elif chat == env_chat and env_chat:
                issues.append(f"{admin.email}: .env ile ayni chat — demo/platform botu kullaniyor olabilir")
            if admin.email in tenant_emails and not ready:
                issues.append(f"{admin.email}: Bot acik ama Telegram yok — pozisyon mesaji gitmez")

        print()
        print("=== SON 10 TELEGRAM LOG ===")
        logs = (
            await session.execute(
                select(TelegramDeliveryLog).order_by(TelegramDeliveryLog.created_at.desc()).limit(10)
            )
        ).scalars().all()
        if not logs:
            print("  (henuz log yok)")
        for lg in logs:
            adm = (
                await session.execute(select(Admin).where(Admin.id == lg.admin_id))
            ).scalar_one_or_none()
            email = adm.email if adm else str(lg.admin_id)
            reason = lg.skip_reason or "-"
            sym = lg.symbol or "-"
            print(f"  {email} | {lg.message_type} | {lg.status} | {reason} | {sym}")

        sent = (
            await session.execute(
                select(func.count()).select_from(TelegramDeliveryLog).where(TelegramDeliveryLog.status == "sent")
            )
        ).scalar_one()
        skipped = (
            await session.execute(
                select(func.count()).select_from(TelegramDeliveryLog).where(TelegramDeliveryLog.status == "skipped")
            )
        ).scalar_one()
        failed = (
            await session.execute(
                select(func.count()).select_from(TelegramDeliveryLog).where(TelegramDeliveryLog.status == "failed")
            )
        ).scalar_one()
        print()
        print(f"Log ozet: sent={sent} skipped={skipped} failed={failed}")

        print()
        print("=== CANLI TEST ===")
        for email in ("erhan-004@hotmail.com", "admin@example.com", "muzaffer@gmail.com"):
            admin = (await session.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none()
            if admin is None:
                continue
            ok, msg = await deliver_test_notification(session, settings, admin.id, source="audit")
            await session.commit()
            status = "OK" if ok else "FAIL"
            print(f"  {email}: {status} — {msg}")

        print()
        if issues:
            print("=== TESPIT EDILEN NOKTALAR ===")
            for item in issues:
                print(f"  ! {item}")
        else:
            print("=== KRITIK SORUN YOK ===")


if __name__ == "__main__":
    asyncio.run(main())
