"""Ortak FastAPI dependency'leri."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AdminSession
from shared.enums import ApprovalStatus, UserRole
from shared.membership import MEMBERSHIP_EXPIRED_MESSAGE, is_membership_active

from ..core.config import Settings, get_settings
from ..core.database import get_db
from ..core.redis import get_redis
from ..core.security import hash_session_token


def _requires_customer_approval(path: str) -> bool:
    if path.startswith("/api/v1/platform"):
        return False
    if path.startswith("/api/v1/auth"):
        return False
    return True


def _assert_customer_access(admin: Admin, path: str) -> None:
    if not _requires_customer_approval(path):
        return
    if admin.role == UserRole.PLATFORM_ADMIN.value:
        return
    if admin.approval_status == ApprovalStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hesabiniz henuz onaylanmadi. Yonetici onayindan sonra panele erisebilirsiniz.",
        )
    if admin.approval_status == ApprovalStatus.BLOCKED.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=admin.blocked_reason or "Hesabiniz engellenmistir. Destek ile iletisime gecin.",
        )
    if not is_membership_active(admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=MEMBERSHIP_EXPIRED_MESSAGE,
        )


async def get_current_admin(
    request: Request,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Admin:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum bulunamadi")

    token_hash = hash_session_token(token)
    result = await session.execute(select(AdminSession).where(AdminSession.token_hash == token_hash))
    admin_session = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if (
        admin_session is None
        or admin_session.revoked_at is not None
        or admin_session.expires_at.replace(tzinfo=timezone.utc) < now
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum gecersiz veya suresi dolmus")

    admin_result = await session.execute(select(Admin).where(Admin.id == admin_session.admin_id))
    admin = admin_result.scalar_one_or_none()
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Hesap aktif degil")

    _assert_customer_access(admin, request.url.path)
    request.state.admin = admin
    request.state.admin_session = admin_session
    return admin


async def require_platform_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    if admin.role != UserRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform yonetici yetkisi gerekli")
    return admin


def require_csrf(request: Request, settings: Settings = Depends(get_settings)) -> None:
    """Durum degistiren (POST/PUT/PATCH/DELETE) istekler icin double-submit CSRF kontrolu."""

    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    cookie_token = request.cookies.get("csrf_token")
    header_token = request.headers.get("x-csrf-token")
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF dogrulamasi basarisiz")


async def get_redis_dep() -> Redis:
    return get_redis()


async def require_profile_unlock(
    request: Request,
    admin: Admin = Depends(get_current_admin),
    redis: Redis = Depends(get_redis_dep),
) -> None:
    from ..services.profile_service import is_profile_unlocked

    if not await is_profile_unlocked(redis, admin.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Baglanti ayarlarini gormek icin profil sifresi ile dogrulama gerekli",
        )
