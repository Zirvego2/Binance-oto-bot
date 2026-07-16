"""SQL BotSettings satirina Firestore ayarlarini uygular (Firestore = kaynak)."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings
from shared.firestore import firebase_enabled, get_tenant_settings

logger = logging.getLogger(__name__)

# BotSettings'te guncellenebilir alanlar (id/admin_id/timestamp haric)
_SKIP_FIELDS = frozenset({"id", "admin_id", "created_at", "updated_at", "updated_by_admin_id"})


def _parse_firestore_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "timestamp"):
        return value  # Firestore Timestamp
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _coerce_column_value(column, raw: Any) -> Any:
    if raw is None:
        return None
    col_type = type(column.type).__name__
    if col_type in ("Numeric", "DECIMAL"):
        return Decimal(str(raw))
    if col_type in ("Integer", "BIGINT", "SMALLINT"):
        return int(raw)
    if col_type in ("Boolean",):
        return bool(raw)
    return raw


async def hydrate_bot_settings_from_firestore(
    session: AsyncSession,
    settings_row: BotSettings,
    admin_id: str,
) -> BotSettings:
    """Firestore'daki ayarlar SQL'den yeniyse SQL satirina yansitir."""
    if not firebase_enabled():
        return settings_row

    fs_data = await get_tenant_settings(admin_id)
    if not fs_data:
        return settings_row

    fs_updated = _parse_firestore_timestamp(fs_data.get("updatedAt"))
    sql_updated = settings_row.updated_at
    if fs_updated and sql_updated:
        if fs_updated.tzinfo is None:
            fs_updated = fs_updated.replace(tzinfo=sql_updated.tzinfo)
        if sql_updated.tzinfo and fs_updated <= sql_updated:
            return settings_row

    changed = False
    for column in settings_row.__table__.columns:
        name = column.name
        if name in _SKIP_FIELDS or name not in fs_data:
            continue
        new_val = _coerce_column_value(column, fs_data[name])
        if getattr(settings_row, name) != new_val:
            setattr(settings_row, name, new_val)
            changed = True

    if changed:
        await session.commit()
        await session.refresh(settings_row)
        logger.debug("BotSettings Firestore'dan guncellendi (admin=%s)", admin_id)
    return settings_row
