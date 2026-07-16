"""Firestore musteri profili — shared katman uzerinden."""

from __future__ import annotations

from typing import Any

from shared.firestore.tenant_repository import (
    get_customer,
    update_customer_bot_settings as _update_bot_settings,
    update_customer_connections,
    upsert_customer,
)

CUSTOMERS_COLLECTION = "customers"

__all__ = [
    "CUSTOMERS_COLLECTION",
    "get_customer",
    "update_customer_bot_settings",
    "update_customer_connections",
    "upsert_customer",
]


async def update_customer_bot_settings(firebase_uid: str, bot_settings: dict[str, Any]) -> None:
    """Geriye uyumluluk: admin_id bot_settings icinde veya ayri arguman."""
    admin_id = bot_settings.get("admin_id") or bot_settings.get("adminId")
    if not admin_id:
        raise ValueError("bot_settings icinde admin_id zorunlu")
    await _update_bot_settings(firebase_uid, str(admin_id), bot_settings)
