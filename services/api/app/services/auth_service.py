"""Authentication is mantigi: giris, cikis, hesap kilitleme (sartname bolum 22)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AdminSession
from shared.enums import ApprovalStatus, UserRole

from ..core.security import generate_session_token, hash_session_token, verify_password

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


async def verify_admin_credentials(
    session: AsyncSession, email: str, password: str
) -> Admin:
    """Sifre dogrulaması yapar; oturum olusturmaz."""

    result = await session.execute(select(Admin).where(Admin.email == email.lower()))
    admin = result.scalar_one_or_none()

    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya sifre hatali"
    )

    if admin is None:
        raise generic_error

    now = datetime.now(timezone.utc)
    if admin.locked_until is not None and admin.locked_until.replace(tzinfo=timezone.utc) > now:
        remaining = int((admin.locked_until.replace(tzinfo=timezone.utc) - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Hesap gecici olarak kilitli. Yaklasik {remaining} dakika sonra tekrar deneyin.",
        )

    if not admin.is_active:
        raise generic_error

    if not verify_password(password, admin.password_hash):
        admin.failed_login_count += 1
        if admin.failed_login_count >= MAX_FAILED_ATTEMPTS:
            admin.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            admin.failed_login_count = 0
        await session.commit()
        raise generic_error

    admin.failed_login_count = 0
    admin.locked_until = None
    await session.flush()
    return admin


async def authenticate_admin(
    session: AsyncSession, email: str, password: str, ip_address: str | None, user_agent: str | None
) -> tuple[Admin, str]:
    result = await session.execute(select(Admin).where(Admin.email == email.lower()))
    admin = result.scalar_one_or_none()

    generic_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya sifre hatali"
    )

    if admin is None:
        raise generic_error

    now = datetime.now(timezone.utc)
    if admin.locked_until is not None and admin.locked_until.replace(tzinfo=timezone.utc) > now:
        remaining = int((admin.locked_until.replace(tzinfo=timezone.utc) - now).total_seconds() // 60) + 1
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Hesap gecici olarak kilitli. Yaklasik {remaining} dakika sonra tekrar deneyin.",
        )

    if not admin.is_active:
        raise generic_error

    if admin.role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Musteri girisi /login sayfasindan yapilmalidir.",
        )

    if not verify_password(password, admin.password_hash):
        admin.failed_login_count += 1
        if admin.failed_login_count >= MAX_FAILED_ATTEMPTS:
            admin.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            admin.failed_login_count = 0
        await session.commit()
        raise generic_error

    admin.failed_login_count = 0
    admin.locked_until = None
    admin.last_login_at = now
    admin.last_login_ip = ip_address

    token = generate_session_token()
    admin_session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_session_token(token),
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=now + timedelta(minutes=480),
    )
    session.add(admin_session)
    await session.commit()

    return admin, token


async def revoke_session(session: AsyncSession, token: str) -> None:
    token_hash = hash_session_token(token)
    result = await session.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))
    admin_session = result.scalar_one_or_none()
    if admin_session is not None and admin_session.revoked_at is None:
        admin_session.revoked_at = datetime.now(timezone.utc)
        await session.commit()
