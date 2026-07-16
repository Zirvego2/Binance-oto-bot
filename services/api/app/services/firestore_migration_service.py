"""SQL musteri verisini Firestore tenant koleksiyonlarina aktarir (admin_id bazli)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from shared.db import (
    Admin,
    AdminProfile,
    AlgoOrder,
    AuditLog,
    BinanceConnectionStatus,
    BotEvent,
    BotRuntimeStatus,
    BotSettings,
    AnalysisResult,
    DailyStatistic,
    FundingRecord,
    Order,
    OrderFill,
    PnlRecord,
    Position,
    ReconciliationRun,
    RiskEvent,
    StrategySignal,
    SymbolRule,
    SystemHealth,
    Trade,
)
from shared.firestore import (
    batch_upsert_analysis,
    batch_upsert_orders,
    batch_upsert_positions,
    batch_upsert_signals,
    batch_upsert_symbol_rules,
    batch_upsert_trades,
    mark_tenant_migrated,
    serialize_model_row,
    upsert_tenant_runtime,
    upsert_tenant_settings,
)

logger = logging.getLogger(__name__)

# (Firestore alt koleksiyon, model, admin_id kolonu var mi)
TENANT_COLLECTIONS: list[tuple[str, type[DeclarativeBase], bool]] = [
    ("positions", Position, True),
    ("orders", Order, True),
    ("algo_orders", AlgoOrder, True),
    ("order_fills", OrderFill, True),
    ("trades", Trade, True),
    ("symbolRules", SymbolRule, True),
    ("analysis", AnalysisResult, True),
    ("signals", StrategySignal, True),
    ("bot_events", BotEvent, False),
    ("audit_logs", AuditLog, False),
    ("risk_events", RiskEvent, False),
    ("daily_statistics", DailyStatistic, True),
    ("reconciliation_runs", ReconciliationRun, False),
    ("pnl_records", PnlRecord, False),
    ("funding_records", FundingRecord, False),
]

SINGLE_DOC_MODELS: list[tuple[type[DeclarativeBase], bool]] = [
    (BotSettings, True),
    (BotRuntimeStatus, True),
    (BinanceConnectionStatus, True),
    (AdminProfile, True),
]

PRIORITY_BATCH = {"positions", "orders", "trades", "symbolRules", "algo_orders", "order_fills", "analysis", "signals"}
HEAVY_BATCH: set[str] = {"analysis"}


def _get_pk_name(model: type[DeclarativeBase]) -> str:
    pks = [c.name for c in model.__table__.columns if c.primary_key]  # type: ignore[attr-defined]
    return pks[0] if pks else "id"


async def _fetch_tenant_rows(
    session: AsyncSession,
    model: type[DeclarativeBase],
    admin_id: str,
    *,
    has_admin_id: bool,
) -> list[dict[str, Any]]:
    if has_admin_id:
        rows = (await session.execute(select(model).where(model.admin_id == admin_id))).scalars().all()  # type: ignore[attr-defined]
    else:
        rows = (await session.execute(select(model))).scalars().all()
    return [serialize_model_row(row) for row in rows]


async def sync_tenant_essentials_to_firestore(session: AsyncSession, firebase_uid: str) -> None:
    """Giris/kayit sonrasi: profil + ayar + runtime (hafif sync, Blaze-friendly)."""
    admin_row = (
        await session.execute(select(Admin).where(Admin.firebase_uid == firebase_uid))
    ).scalar_one_or_none()
    if admin_row is None:
        return
    admin_id = admin_row.id

    settings_row = (
        await session.execute(select(BotSettings).where(BotSettings.admin_id == admin_id))
    ).scalar_one_or_none()
    runtime_row = (
        await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin_id))
    ).scalar_one_or_none()

    from shared.firestore.tenant_repository import update_customer_bot_settings

    if settings_row is not None:
        payload = serialize_model_row(settings_row)
        await update_customer_bot_settings(firebase_uid, admin_id, payload)
        await upsert_tenant_settings(admin_id, payload)
    if runtime_row is not None:
        await upsert_tenant_runtime(admin_id, serialize_model_row(runtime_row))


async def migrate_sql_to_firestore(
    session: AsyncSession,
    firebase_uid: str,
    *,
    mode: str = "priority",
) -> dict[str, int]:
    """Musterinin SQL verisini tenants/{adminId}/... koleksiyonlarina kopyalar."""

    admin_row = (
        await session.execute(select(Admin).where(Admin.firebase_uid == firebase_uid))
    ).scalar_one_or_none()
    if admin_row is None:
        raise ValueError(f"Firebase UID icin Admin bulunamadi: {firebase_uid}")
    admin_id = admin_row.id

    stats: dict[str, int] = {}

    for model, has_admin_id in SINGLE_DOC_MODELS:
        name = model.__tablename__
        if has_admin_id:
            row = (
                await session.execute(select(model).where(model.admin_id == admin_id))  # type: ignore[attr-defined]
            ).scalar_one_or_none()
        else:
            row = (await session.execute(select(model))).scalar_one_or_none()
        if row is None:
            stats[name] = 0
            continue
        payload = serialize_model_row(row)
        if model is BotSettings:
            await upsert_tenant_settings(admin_id, payload)
        elif model is BotRuntimeStatus:
            await upsert_tenant_runtime(admin_id, payload)
        else:
            from shared.firestore.tenant_repository import upsert_tenant_entity

            await upsert_tenant_entity(admin_id, name, payload.get("id", "current"), payload)
        stats[name] = 1

    for collection_name, model, has_admin_id in TENANT_COLLECTIONS:
        if mode == "priority" and collection_name not in PRIORITY_BATCH and collection_name not in {
            "bot_events",
            "audit_logs",
            "risk_events",
            "daily_statistics",
            "reconciliation_runs",
            "pnl_records",
            "funding_records",
        }:
            continue
        if mode == "heavy" and collection_name not in HEAVY_BATCH:
            continue

        serialized = await _fetch_tenant_rows(session, model, admin_id, has_admin_id=has_admin_id)
        pk_name = _get_pk_name(model)
        count = 0
        if collection_name == "positions":
            count = await batch_upsert_positions(admin_id, serialized)
        elif collection_name == "trades":
            count = await batch_upsert_trades(admin_id, serialized)
        elif collection_name == "orders" or collection_name == "algo_orders" or collection_name == "order_fills":
            count = await batch_upsert_orders(admin_id, serialized)
        elif collection_name == "symbolRules":
            count = await batch_upsert_symbol_rules(admin_id, serialized)
        elif collection_name == "analysis":
            count = await batch_upsert_analysis(admin_id, serialized)
        elif collection_name == "signals":
            count = await batch_upsert_signals(admin_id, serialized)
        else:
            from shared.firestore import batch_upsert_collection

            count = await batch_upsert_collection(admin_id, collection_name, serialized, pk_name=pk_name)
        stats[collection_name] = count

    await mark_tenant_migrated(firebase_uid, admin_id, mode, stats)
    logger.info("Firestore migration tamamlandi (admin=%s, uid=%s, mode=%s)", admin_id, firebase_uid, mode)
    return stats
