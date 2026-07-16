"""Audit log kayit servisi (sartname bolum 22 & 28)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import AuditLog
from shared.masking import mask_sensitive_dict


async def record_audit_log(
    session: AsyncSession,
    *,
    admin_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before_data: dict[str, Any] | None = None,
    after_data: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    entry = AuditLog(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_data=mask_sensitive_dict(before_data) if before_data else None,
        after_data=mask_sensitive_dict(after_data) if after_data else None,
        ip_address=ip_address,
    )
    session.add(entry)
    await session.commit()
