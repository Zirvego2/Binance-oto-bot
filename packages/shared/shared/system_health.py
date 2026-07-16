"""SystemHealth tablosuna bilesen durumu yazar."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .db import SystemHealth, utcnow


async def upsert_system_health(
    session: AsyncSession,
    component_id: str,
    status: str,
    message: str | None = None,
) -> None:
    now = utcnow()
    row = await session.get(SystemHealth, component_id)
    if row is None:
        session.add(
            SystemHealth(
                id=component_id,
                status=status,
                message=message,
                checked_at=now,
            )
        )
    else:
        row.status = status
        row.message = message
        row.checked_at = now
