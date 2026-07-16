"""Ortak platform sinyal/analiz kayitlarini Firestore'a yazar."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import DeclarativeBase

from .bootstrap import firebase_enabled
from .schema import DOC_SHARED, PLATFORM_COLLECTION, SUBCOL_ANALYSIS, SUBCOL_SIGNALS
from .serialization import serialize_model_row, serialize_value

logger = logging.getLogger(__name__)


def _upsert_platform_entity_sync(subcollection: str, doc_id: str, payload: dict) -> None:
    from .tenant_repository import _require_client

    db = _require_client()
    data = {k: serialize_value(v) for k, v in payload.items()}
    data["scope"] = "platform"
    data["updatedAt"] = datetime.now(timezone.utc)
    db.collection(PLATFORM_COLLECTION).document(DOC_SHARED).collection(subcollection).document(doc_id).set(
        data, merge=True
    )


async def sync_platform_analysis(row: DeclarativeBase) -> None:
    if not firebase_enabled():
        return
    try:
        payload = serialize_model_row(row)
        doc_id = str(payload.get("id") or "unknown")
        await asyncio.to_thread(_upsert_platform_entity_sync, SUBCOL_ANALYSIS, doc_id, payload)
    except Exception:
        logger.warning("Platform analiz Firestore sync basarisiz", exc_info=True)


async def sync_platform_signal(row: DeclarativeBase) -> None:
    if not firebase_enabled():
        return
    try:
        payload = serialize_model_row(row)
        doc_id = str(payload.get("id") or "unknown")
        await asyncio.to_thread(_upsert_platform_entity_sync, SUBCOL_SIGNALS, doc_id, payload)
    except Exception:
        logger.warning("Platform sinyal Firestore sync basarisiz", exc_info=True)
