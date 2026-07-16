"""Ilk kurulumda varsayilan admin/musteri hesaplarini olusturur (Cloud Run + yerel)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin
from shared.enums import ApprovalStatus, UserRole

from ..core.config import Settings
from ..core.security import hash_password
from shared.customer_credentials import get_or_create_admin_profile

logger = logging.getLogger(__name__)


async def _upsert_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    role: UserRole,
    full_name: str,
) -> Admin:
    email_norm = email.lower().strip()
    result = await session.execute(select(Admin).where(Admin.email == email_norm))
    admin = result.scalar_one_or_none()

    password_hash = hash_password(password)
    if admin is None:
        admin = Admin(
            email=email_norm,
            password_hash=password_hash,
            full_name=full_name,
            role=role.value,
            approval_status=ApprovalStatus.APPROVED.value,
            is_active=True,
        )
        session.add(admin)
        await session.flush()
        logger.info("Bootstrap admin olusturuldu: %s (role=%s)", email_norm, role.value)
    else:
        admin.password_hash = password_hash
        admin.role = role.value
        admin.approval_status = ApprovalStatus.APPROVED.value
        admin.is_active = True
        if full_name and not admin.full_name:
            admin.full_name = full_name
        await session.flush()
        logger.info("Bootstrap admin guncellendi: %s (role=%s)", email_norm, role.value)

    if role == UserRole.CUSTOMER:
        await get_or_create_admin_profile(session, admin.id)

    return admin


async def ensure_bootstrap_admins(session: AsyncSession, settings: Settings) -> None:
    """ADMIN_EMAIL musteri hesabini ve (varsa) platform admin hesabini hazirlar."""

    if settings.admin_email and settings.admin_password and len(settings.admin_password) >= 8:
        await _upsert_admin(
            session,
            email=settings.admin_email,
            password=settings.admin_password,
            role=UserRole.CUSTOMER,
            full_name="Demo Musteri",
        )

    platform_email = settings.platform_admin_email
    platform_password = settings.platform_admin_password
    if platform_email and platform_password and len(platform_password) >= 8:
        await _upsert_admin(
            session,
            email=platform_email,
            password=platform_password,
            role=UserRole.PLATFORM_ADMIN,
            full_name="Platform Yoneticisi",
        )

    await session.commit()
