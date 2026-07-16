"""Ilk admin kullanicisini olusturan komut satiri scripti.

Kullanim:
    python scripts/create_admin.py
    python scripts/create_admin.py --email admin@example.com --password "GucluBirSifre123!"

Argumanlar verilmezse ``.env`` dosyasindaki ``ADMIN_EMAIL`` / ``ADMIN_PASSWORD``
degerleri kullanilir.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.config import get_settings  # noqa: E402
from app.core.database import AsyncSessionLocal, create_all_tables  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from shared.db import Admin  # noqa: E402
from shared.enums import ApprovalStatus, UserRole  # noqa: E402


async def create_admin(
    email: str,
    password: str,
    full_name: str | None = None,
    *,
    role: UserRole = UserRole.PLATFORM_ADMIN,
) -> None:
    await create_all_tables()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.email == email.lower()))
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.role = role.value
            existing.approval_status = ApprovalStatus.APPROVED.value
            existing.password_hash = hash_password(password)
            existing.full_name = full_name or existing.full_name
            existing.is_active = True
            await session.commit()
            print(f"Admin '{email}' guncellendi (role={role.value}).")
            return

        admin = Admin(
            email=email.lower(),
            password_hash=hash_password(password),
            full_name=full_name,
            role=role.value,
            approval_status=ApprovalStatus.APPROVED.value,
            is_active=True,
        )
        session.add(admin)
        await session.commit()
        print(f"Admin kullanicisi olusturuldu: {email} (role={role.value})")


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ilk admin kullanicisini olusturur")
    parser.add_argument("--email", default=settings.admin_email)
    parser.add_argument("--password", default=settings.admin_password)
    parser.add_argument("--full-name", default="Sistem Yoneticisi")
    parser.add_argument(
        "--role",
        default=UserRole.PLATFORM_ADMIN.value,
        choices=[UserRole.PLATFORM_ADMIN.value, UserRole.CUSTOMER.value],
        help="Kullanici rolu (platform_admin veya customer)",
    )
    args = parser.parse_args()

    if not args.email or not args.password:
        print("HATA: email ve sifre gerekli (ADMIN_EMAIL / ADMIN_PASSWORD veya --email / --password)")
        raise SystemExit(1)
    if len(args.password) < 8:
        print("HATA: sifre en az 8 karakter olmalidir")
        raise SystemExit(1)

    asyncio.run(create_admin(args.email, args.password, args.full_name, role=UserRole(args.role)))


if __name__ == "__main__":
    main()
