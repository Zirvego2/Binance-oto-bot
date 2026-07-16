"""Firestore tenant veri deposu — musteri bazli koleksiyon CRUD."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from .schema import (
    CUSTOMERS_COLLECTION,
    DOC_CURRENT,
    DOC_DEFAULTS,
    PLATFORM_COLLECTION,
    SUBCOL_BOT_EVENTS,
    SUBCOL_ANALYSIS,
    SUBCOL_ORDERS,
    SUBCOL_POSITIONS,
    SUBCOL_RUNTIME,
    SUBCOL_SETTINGS,
    SUBCOL_SIGNALS,
    SUBCOL_SYMBOL_RULES,
    SUBCOL_TRADES,
    TENANT_INDEX_COLLECTION,
    TENANTS_COLLECTION,
)
from .serialization import serialize_value

logger = logging.getLogger(__name__)


def _require_client():
    from .bootstrap import firebase_enabled

    if not firebase_enabled():
        raise RuntimeError("Firebase baslatilmamis")
    from firebase_admin import firestore

    return firestore.client()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _tenant_ref(db, admin_id: str):
    return db.collection(TENANTS_COLLECTION).document(admin_id)


def _customer_ref(db, firebase_uid: str):
    return db.collection(CUSTOMERS_COLLECTION).document(firebase_uid)


# --- Customer profile ---


def _upsert_customer_sync(
    firebase_uid: str,
    *,
    email: str,
    admin_id: str,
    full_name: str | None,
    connections: dict[str, Any] | None = None,
    approval_status: str | None = None,
    bot_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db = _require_client()
    ref = _customer_ref(db, firebase_uid)
    snap = ref.get()
    now = _now()
    existing = snap.to_dict() if snap.exists else {}

    payload: dict[str, Any] = {
        "email": email.lower(),
        "adminId": admin_id,
        "fullName": full_name,
        "accountType": "customer",
        "updatedAt": now,
    }
    if not snap.exists:
        payload["createdAt"] = now
        payload["plan"] = "starter"
    else:
        payload["createdAt"] = existing.get("createdAt", now)
        payload["plan"] = existing.get("plan", "starter")

    if connections is not None:
        payload["connections"] = connections
    elif "connections" in existing:
        payload["connections"] = existing["connections"]

    if approval_status is not None:
        payload["approvalStatus"] = approval_status
    elif "approvalStatus" in existing:
        payload["approvalStatus"] = existing["approvalStatus"]

    if bot_settings is not None:
        payload["botSettings"] = bot_settings
        payload["botSettingsUpdatedAt"] = now

    ref.set(payload, merge=True)

    # tenantIndex — worker/API admin_id ile hizli lookup
    db.collection(TENANT_INDEX_COLLECTION).document(admin_id).set(
        {"firebaseUid": firebase_uid, "email": email.lower(), "updatedAt": now},
        merge=True,
    )
    payload["id"] = firebase_uid
    return payload


async def upsert_customer(
    firebase_uid: str,
    *,
    email: str,
    admin_id: str,
    full_name: str | None,
    connections: dict[str, Any] | None = None,
    approval_status: str | None = None,
    bot_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        _upsert_customer_sync,
        firebase_uid,
        email=email,
        admin_id=admin_id,
        full_name=full_name,
        connections=connections,
        approval_status=approval_status,
        bot_settings=bot_settings,
    )


def _get_customer_sync(firebase_uid: str) -> dict[str, Any] | None:
    db = _require_client()
    snap = _customer_ref(db, firebase_uid).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = snap.id
    return data


async def get_customer(firebase_uid: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_customer_sync, firebase_uid)


def _update_connections_sync(firebase_uid: str, connections: dict[str, Any]) -> dict[str, Any]:
    db = _require_client()
    ref = _customer_ref(db, firebase_uid)
    now = _now()
    ref.set({"connections": connections, "updatedAt": now}, merge=True)
    snap = ref.get()
    data = snap.to_dict() or {}
    data["id"] = firebase_uid
    return data


async def update_customer_connections(firebase_uid: str, connections: dict[str, Any]) -> dict[str, Any]:
    return await asyncio.to_thread(_update_connections_sync, firebase_uid, connections)


# --- Tenant settings / runtime (admin_id keyed) ---


def _upsert_tenant_doc_sync(admin_id: str, subcollection: str, doc_id: str, payload: dict[str, Any]) -> None:
    db = _require_client()
    now = _now()
    data = {k: serialize_value(v) for k, v in payload.items()}
    data["adminId"] = admin_id
    data["updatedAt"] = now
    _tenant_ref(db, admin_id).collection(subcollection).document(doc_id).set(data, merge=True)


async def upsert_tenant_settings(admin_id: str, settings: dict[str, Any]) -> None:
    await asyncio.to_thread(_upsert_tenant_doc_sync, admin_id, SUBCOL_SETTINGS, DOC_CURRENT, settings)


async def upsert_tenant_runtime(admin_id: str, runtime: dict[str, Any]) -> None:
    await asyncio.to_thread(_upsert_tenant_doc_sync, admin_id, SUBCOL_RUNTIME, DOC_CURRENT, runtime)


def _get_tenant_doc_sync(admin_id: str, subcollection: str, doc_id: str) -> dict[str, Any] | None:
    db = _require_client()
    snap = _tenant_ref(db, admin_id).collection(subcollection).document(doc_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    data["id"] = snap.id
    return data


async def get_tenant_settings(admin_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_tenant_doc_sync, admin_id, SUBCOL_SETTINGS, DOC_CURRENT)


async def get_tenant_runtime(admin_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_tenant_doc_sync, admin_id, SUBCOL_RUNTIME, DOC_CURRENT)


async def update_customer_bot_settings(firebase_uid: str, admin_id: str, bot_settings: dict[str, Any]) -> None:
    """Ayar kaydini hem tenant koleksiyonuna hem musteri profiline yazar."""

    def _write() -> None:
        db = _require_client()
        now = _now()
        serialized = {k: serialize_value(v) for k, v in bot_settings.items()}
        _tenant_ref(db, admin_id).collection(SUBCOL_SETTINGS).document(DOC_CURRENT).set(
            {**serialized, "adminId": admin_id, "updatedAt": now},
            merge=True,
        )
        _customer_ref(db, firebase_uid).set(
            {"botSettings": serialized, "botSettingsUpdatedAt": now, "updatedAt": now},
            merge=True,
        )

    await asyncio.to_thread(_write)


# --- Tenant entity collections (positions, trades, ...) ---


def _batch_upsert_sync(
    admin_id: str,
    subcollection: str,
    rows: list[dict[str, Any]],
    *,
    pk_name: str = "id",
    batch_size: int = 100,
) -> int:
    if not rows:
        return 0
    from google.api_core.exceptions import ResourceExhausted

    db = _require_client()
    parent = _tenant_ref(db, admin_id).collection(subcollection)
    written = 0
    batch = db.batch()
    batch_count = 0

    for row in rows:
        doc_id = str(row.get(pk_name) or row.get("id") or written)
        data = {k: serialize_value(v) for k, v in row.items()}
        data["adminId"] = admin_id
        batch.set(parent.document(doc_id), data, merge=True)
        batch_count += 1
        written += 1
        if batch_count >= batch_size:
            for attempt in range(5):
                try:
                    batch.commit()
                    break
                except ResourceExhausted:
                    if attempt == 4:
                        raise
                    time.sleep(2 ** (attempt + 1))
            batch = db.batch()
            batch_count = 0
            time.sleep(0.3)
    if batch_count:
        for attempt in range(5):
            try:
                batch.commit()
                break
            except ResourceExhausted:
                if attempt == 4:
                    raise
                time.sleep(2 ** (attempt + 1))
    return written


async def batch_upsert_positions(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_POSITIONS, rows)


async def batch_upsert_trades(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_TRADES, rows)


async def batch_upsert_orders(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_ORDERS, rows)


async def batch_upsert_symbol_rules(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_SYMBOL_RULES, rows, pk_name="symbol")


async def batch_upsert_analysis(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_ANALYSIS, rows)


async def batch_upsert_signals(admin_id: str, rows: list[dict[str, Any]]) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, SUBCOL_SIGNALS, rows)


async def upsert_tenant_entity(admin_id: str, subcollection: str, doc_id: str, payload: dict[str, Any]) -> None:
    await asyncio.to_thread(_upsert_tenant_doc_sync, admin_id, subcollection, doc_id, payload)


async def batch_upsert_collection(
    admin_id: str,
    subcollection: str,
    rows: list[dict[str, Any]],
    *,
    pk_name: str = "id",
) -> int:
    return await asyncio.to_thread(_batch_upsert_sync, admin_id, subcollection, rows, pk_name=pk_name)


def _delete_subcollection_sync(admin_id: str, subcollection: str, *, batch_size: int = 100) -> int:
    db = _require_client()
    col = _tenant_ref(db, admin_id).collection(subcollection)
    deleted = 0
    while True:
        docs = list(col.limit(batch_size).stream())
        if not docs:
            break
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()
        deleted += len(docs)
    return deleted


async def delete_tenant_subcollection(admin_id: str, subcollection: str) -> int:
    return await asyncio.to_thread(_delete_subcollection_sync, admin_id, subcollection)


def _delete_tenant_document_sync(admin_id: str) -> None:
    db = _require_client()
    for subcol in (
        SUBCOL_SETTINGS,
        SUBCOL_RUNTIME,
        SUBCOL_POSITIONS,
        SUBCOL_TRADES,
        SUBCOL_ORDERS,
        SUBCOL_SYMBOL_RULES,
        SUBCOL_ANALYSIS,
        SUBCOL_SIGNALS,
        SUBCOL_BOT_EVENTS,
        "strategy_signals",
    ):
        _delete_subcollection_sync(admin_id, subcol)
    _tenant_ref(db, admin_id).delete()
    db.collection(TENANT_INDEX_COLLECTION).document(admin_id).delete()


def _delete_customer_profile_sync(firebase_uid: str | None) -> None:
    if not firebase_uid:
        return
    db = _require_client()
    _customer_ref(db, firebase_uid).delete()


async def delete_customer_firestore_data(firebase_uid: str | None, admin_id: str) -> None:
    await asyncio.to_thread(_delete_tenant_document_sync, admin_id)
    await asyncio.to_thread(_delete_customer_profile_sync, firebase_uid)


def _list_tenant_admin_ids_sync() -> list[str]:
    db = _require_client()
    return [snap.id for snap in db.collection(TENANTS_COLLECTION).stream()]


async def list_tenant_admin_ids() -> list[str]:
    return await asyncio.to_thread(_list_tenant_admin_ids_sync)


# --- Platform defaults ---


def _upsert_platform_defaults_sync(
    general: dict[str, Any],
    position: dict[str, Any],
    impulse: dict[str, Any],
) -> None:
    db = _require_client()
    now = _now()
    db.collection(PLATFORM_COLLECTION).document(DOC_DEFAULTS).set(
        {
            "general": {k: serialize_value(v) for k, v in general.items()},
            "position": {k: serialize_value(v) for k, v in position.items()},
            "impulse": {k: serialize_value(v) for k, v in impulse.items()},
            "updatedAt": now,
        },
        merge=True,
    )


async def upsert_platform_defaults(
    general: dict[str, Any],
    position: dict[str, Any],
    impulse: dict[str, Any],
) -> None:
    await asyncio.to_thread(_upsert_platform_defaults_sync, general, position, impulse)


def _get_platform_defaults_sync() -> dict[str, Any] | None:
    db = _require_client()
    snap = db.collection(PLATFORM_COLLECTION).document(DOC_DEFAULTS).get()
    if not snap.exists:
        return None
    return snap.to_dict()


async def get_platform_defaults() -> dict[str, Any] | None:
    return await asyncio.to_thread(_get_platform_defaults_sync)


# --- Migration meta ---


async def mark_tenant_migrated(firebase_uid: str, admin_id: str, mode: str, stats: dict[str, int]) -> None:
    def _write() -> None:
        db = _require_client()
        now = _now()
        _customer_ref(db, firebase_uid).set(
            {
                "dataMigratedAt": now,
                "dataInFirebase": True,
                "migrationMode": mode,
                "migrationStats": stats,
                "updatedAt": now,
            },
            merge=True,
        )
        _tenant_ref(db, admin_id).set({"firebaseUid": firebase_uid, "migratedAt": now, "updatedAt": now}, merge=True)

    await asyncio.to_thread(_write)
