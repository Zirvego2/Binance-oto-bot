"""Trading entity degisikliklerini Firestore tenant koleksiyonlarina yansitir."""

from __future__ import annotations

import logging

from sqlalchemy.orm import DeclarativeBase

from .bootstrap import firebase_enabled
from .schema import SUBCOL_ANALYSIS, SUBCOL_ORDERS, SUBCOL_POSITIONS, SUBCOL_SIGNALS, SUBCOL_TRADES
from .serialization import serialize_model_row
from .tenant_repository import upsert_tenant_entity

logger = logging.getLogger(__name__)


async def sync_entity_to_firestore(
    admin_id: str | None,
    subcollection: str,
    row: DeclarativeBase,
    *,
    doc_id: str | None = None,
) -> None:
    if not firebase_enabled() or not admin_id:
        return
    try:
        payload = serialize_model_row(row)
        entity_id = doc_id or str(payload.get("id") or payload.get("symbol") or "unknown")
        await upsert_tenant_entity(admin_id, subcollection, entity_id, payload)
    except Exception:
        logger.warning("Firestore sync basarisiz (%s/%s)", admin_id, subcollection, exc_info=True)


async def sync_position_to_firestore(admin_id: str | None, row: DeclarativeBase) -> None:
    await sync_entity_to_firestore(admin_id, SUBCOL_POSITIONS, row)


async def sync_trade_to_firestore(admin_id: str | None, row: DeclarativeBase) -> None:
    await sync_entity_to_firestore(admin_id, SUBCOL_TRADES, row)


async def sync_order_to_firestore(admin_id: str | None, row: DeclarativeBase) -> None:
    await sync_entity_to_firestore(admin_id, SUBCOL_ORDERS, row)


async def sync_analysis_to_firestore(admin_id: str | None, row: DeclarativeBase) -> None:
    await sync_entity_to_firestore(admin_id, SUBCOL_ANALYSIS, row)


async def sync_signal_to_firestore(admin_id: str | None, row: DeclarativeBase) -> None:
    await sync_entity_to_firestore(admin_id, SUBCOL_SIGNALS, row)


async def sync_tenant_position_open(admin_id: str | None, position: DeclarativeBase) -> None:
    await sync_position_to_firestore(admin_id, position)


async def sync_tenant_position_closed(
    admin_id: str | None,
    position: DeclarativeBase,
    trade: DeclarativeBase | None = None,
) -> None:
    await sync_position_to_firestore(admin_id, position)
    if trade is not None:
        await sync_trade_to_firestore(admin_id, trade)
