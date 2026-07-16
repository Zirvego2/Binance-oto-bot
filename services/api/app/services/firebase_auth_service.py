"""Firebase Authentication -> yerel oturum donusumu."""

from __future__ import annotations

import asyncio
import logging
import secrets

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from firebase_admin import auth as firebase_auth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AdminSession
from shared.enums import ApprovalStatus, UserRole
from shared.membership import MEMBERSHIP_EXPIRED_MESSAGE, is_membership_active

from ..core.firebase import firebase_enabled
from ..core.security import generate_session_token, hash_password, hash_session_token
from .auth_service import verify_admin_credentials
from .firestore_customer_service import upsert_customer
from .firestore_migration_service import sync_tenant_essentials_to_firestore
from .profile_service import reconcile_customer_connections
from shared.customer_credentials import get_or_create_admin_profile

logger = logging.getLogger(__name__)


def _assert_customer_can_login(admin: Admin) -> None:
    if admin.role == UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform yoneticisi /admin/login adresinden giris yapmalidir.",
        )
    if admin.approval_status == ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabiniz henuz onaylanmadi. Yonetici onayindan sonra giris yapabilirsiniz.",
        )
    if admin.approval_status == ApprovalStatus.BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=admin.blocked_reason or "Hesabiniz engellenmistir.",
        )
    if not is_membership_active(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MEMBERSHIP_EXPIRED_MESSAGE,
        )


async def _background_migrate_to_firestore(firebase_uid: str) -> None:
    from ..core.database import db_session_scope

    try:
        async with db_session_scope() as session:
            await sync_tenant_essentials_to_firestore(session, firebase_uid)
    except Exception:
        logger.exception("Arka plan Firestore sync basarisiz (uid=%s)", firebase_uid)


def _ensure_firebase_user_sync(email: str, password: str, display_name: str | None) -> str:
    try:
        user = firebase_auth.get_user_by_email(email)
        firebase_auth.update_user(
            user.uid,
            password=password,
            display_name=display_name or user.display_name,
        )
        return user.uid
    except firebase_auth.UserNotFoundError:
        user = firebase_auth.create_user(
            email=email,
            password=password,
            display_name=display_name,
        )
        return user.uid


async def ensure_firebase_user(email: str, password: str, display_name: str | None) -> str:
    if not firebase_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Firebase yapilandirilmamis")
    return await asyncio.to_thread(_ensure_firebase_user_sync, email, password, display_name)


async def verify_firebase_id_token(id_token: str) -> firebase_auth.DecodedIdToken:
    if not firebase_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Firebase yapilandirilmamis")
    try:
        return firebase_auth.verify_id_token(id_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Firebase oturumu gecersiz") from exc


async def get_or_link_admin_from_firebase(
    session: AsyncSession,
    *,
    firebase_uid: str,
    email: str,
    display_name: str | None,
) -> Admin:
    email_norm = email.lower().strip()
    by_uid = await session.execute(select(Admin).where(Admin.firebase_uid == firebase_uid))
    admin = by_uid.scalar_one_or_none()
    if admin is not None:
        return admin

    by_email = await session.execute(select(Admin).where(Admin.email == email_norm))
    admin = by_email.scalar_one_or_none()
    if admin is not None:
        if admin.firebase_uid and admin.firebase_uid != firebase_uid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu e-posta baska bir Firebase hesabina bagli",
            )
        admin.firebase_uid = firebase_uid
        if display_name and not admin.full_name:
            admin.full_name = display_name.strip()
        await session.flush()
        return admin

    admin = Admin(
        email=email_norm,
        password_hash=hash_password(secrets.token_urlsafe(48)),
        full_name=display_name.strip() if display_name else None,
        firebase_uid=firebase_uid,
        role=UserRole.CUSTOMER.value,
        approval_status=ApprovalStatus.PENDING.value,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    return admin


async def create_session_for_admin(
    session: AsyncSession,
    admin: Admin,
    *,
    ip_address: str | None,
    user_agent: str | None,
    ttl_minutes: int = 480,
) -> str:
    now = datetime.now(timezone.utc)
    admin.last_login_at = now
    admin.last_login_ip = ip_address

    token = generate_session_token()
    admin_session = AdminSession(
        admin_id=admin.id,
        token_hash=hash_session_token(token),
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    session.add(admin_session)
    await session.commit()
    await session.refresh(admin)
    return token


async def sync_customer_to_firestore(
    session: AsyncSession,
    admin: Admin,
    settings,
    *,
    migrate_all: bool = True,
) -> None:
    if not admin.firebase_uid or not firebase_enabled():
        return

    connections_doc = await reconcile_customer_connections(session, admin, settings)
    await upsert_customer(
        admin.firebase_uid,
        email=admin.email,
        admin_id=admin.id,
        full_name=admin.full_name,
        connections=connections_doc,
        approval_status=admin.approval_status,
    )

    if migrate_all and admin.firebase_uid and admin.approval_status == ApprovalStatus.APPROVED.value:
        asyncio.create_task(_background_migrate_to_firestore(admin.firebase_uid))


async def authenticate_with_firebase_token(
    session: AsyncSession,
    id_token: str,
    settings,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[Admin, str]:
    decoded = await verify_firebase_id_token(id_token)
    firebase_uid = decoded["uid"]
    email = decoded.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Firebase hesabinda e-posta yok")

    admin = await get_or_link_admin_from_firebase(
        session,
        firebase_uid=firebase_uid,
        email=email,
        display_name=decoded.get("name"),
    )
    _assert_customer_can_login(admin)
    token = await create_session_for_admin(
        session,
        admin,
        ip_address=ip_address,
        user_agent=user_agent,
        ttl_minutes=settings.session_ttl_minutes,
    )
    await sync_customer_to_firestore(session, admin, settings, migrate_all=True)
    return admin, token


async def register_customer(
    session: AsyncSession,
    email: str,
    password: str,
    settings,
    *,
    full_name: str,
    phone: str,
    city: str,
    district: str,
) -> Admin:
    """Yeni musteri kaydi — oturum acmaz, onay bekler."""

    email_norm = email.lower().strip()
    result = await session.execute(select(Admin).where(Admin.email == email_norm))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kayitli. Giris yapin.")

    firebase_uid = await ensure_firebase_user(email_norm, password, full_name)
    admin = Admin(
        email=email_norm,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        phone=phone.strip(),
        city=city.strip(),
        district=district.strip(),
        firebase_uid=firebase_uid,
        role=UserRole.CUSTOMER.value,
        approval_status=ApprovalStatus.PENDING.value,
        is_active=True,
    )
    session.add(admin)
    await session.flush()
    await get_or_create_admin_profile(session, admin.id)
    await session.flush()
    await sync_customer_to_firestore(session, admin, settings, migrate_all=False)
    await session.commit()
    await session.refresh(admin)
    return admin


async def authenticate_customer_with_password(
    session: AsyncSession,
    email: str,
    password: str,
    settings,
    *,
    ip_address: str | None,
    user_agent: str | None,
    full_name: str | None = None,
    create_if_missing: bool = False,
) -> tuple[Admin, str]:
    """Mevcut musteri sifresi ile giris + Firebase kullanicisi otomatik olusturma/baglama."""

    if create_if_missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kayit icin /auth/customer-register endpointini kullanin.",
        )

    admin = await verify_admin_credentials(session, email, password)
    _assert_customer_can_login(admin)
    admin.firebase_uid = admin.firebase_uid or await ensure_firebase_user(
        admin.email, password, admin.full_name
    )
    await session.flush()

    token = await create_session_for_admin(
        session,
        admin,
        ip_address=ip_address,
        user_agent=user_agent,
        ttl_minutes=settings.session_ttl_minutes,
    )
    await sync_customer_to_firestore(session, admin, settings, migrate_all=True)
    return admin, token
