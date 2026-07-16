from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import SystemHealth

from ...core.config import Settings, get_settings
from ...core.database import get_db
from ...schemas.system import ComponentHealthOut, HealthOut, SystemStatusOut, TelegramTestOut
from ..deps import get_current_admin, get_redis_dep, require_csrf
from shared.customer_credentials import environment_credentials_from_settings
from shared.telegram_delivery import deliver_test_notification

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
async def health(app_settings: Settings = Depends(get_settings)) -> HealthOut:
    """Kimlik dogrulama gerektirmeyen basit canlilik kontrolu (docker healthcheck icin)."""

    return HealthOut(status="ok", app_env=app_settings.app_env)


@router.get("/system/status", response_model=SystemStatusOut)
async def system_status(
    session: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis_dep),
    admin=Depends(get_current_admin),
) -> SystemStatusOut:
    components: list[ComponentHealthOut] = []

    try:
        await session.execute(text("SELECT 1"))
        components.append(ComponentHealthOut(component="postgresql", status="HEALTHY", message=None, checked_at=datetime.now(timezone.utc)))
    except Exception as exc:
        components.append(ComponentHealthOut(component="postgresql", status="UNHEALTHY", message=str(exc), checked_at=datetime.now(timezone.utc)))

    try:
        await redis.ping()
        components.append(ComponentHealthOut(component="redis", status="HEALTHY", message=None, checked_at=datetime.now(timezone.utc)))
    except Exception as exc:
        components.append(ComponentHealthOut(component="redis", status="UNHEALTHY", message=str(exc), checked_at=datetime.now(timezone.utc)))

    db_rows = (await session.execute(select(SystemHealth))).scalars().all()
    for row in db_rows:
        components.append(
            ComponentHealthOut(component=row.id, status=row.status, message=row.message, checked_at=row.checked_at)
        )

    overall = "HEALTHY"
    if any(c.status == "UNHEALTHY" for c in components):
        overall = "UNHEALTHY"
    elif any(c.status == "DEGRADED" for c in components):
        overall = "DEGRADED"

    return SystemStatusOut(overall_status=overall, components=components)


@router.post("/system/telegram-test", response_model=TelegramTestOut, dependencies=[Depends(require_csrf)])
async def telegram_test(
    admin=Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
    app_settings: Settings = Depends(get_settings),
) -> TelegramTestOut:
    ok, message = await deliver_test_notification(session, app_settings, admin.id, source="api")
    if ok:
        return TelegramTestOut(ok=True, configured=True, message=message)
    return TelegramTestOut(
        ok=False,
        configured=message != "Telegram yapilandirilmamis. Profil sayfasindan kendi bot token ve chat ID'nizi girin.",
        message=message,
    )
