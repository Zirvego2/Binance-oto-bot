"""Bot ayarlari servisi (sartname bolum 2 & 22)."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, BotRuntimeStatus, BotSettings
from shared.default_bot_settings import (
    DEFAULT_GENERAL_SETTINGS,
    DEFAULT_IMPULSE_SETTINGS,
    DEFAULT_POSITION_SETTINGS,
    SettingsResetScope,
    defaults_for_scope,
)
from shared.tenant_settings import get_or_create_bot_settings as _get_or_create_tenant_settings

from ..core.config import get_settings
from shared.firestore import firebase_enabled, serialize_model_row
from shared.firestore.tenant_repository import update_customer_bot_settings as fs_update_bot_settings
from .audit_service import record_audit_log


async def get_or_create_bot_settings(session: AsyncSession, admin_id: str) -> BotSettings:
    return await _get_or_create_tenant_settings(session, admin_id)


async def sync_bot_settings_to_firebase(session: AsyncSession, admin_id: str, settings_row: BotSettings) -> None:
    if not firebase_enabled():
        return
    admin = (await session.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if admin is None or not admin.firebase_uid:
        return
    payload = serialize_model_row(settings_row)
    await fs_update_bot_settings(admin.firebase_uid, admin_id, payload)
    from shared.firestore import upsert_tenant_runtime

    runtime = (
        await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin_id))
    ).scalar_one_or_none()
    if runtime is not None:
        await upsert_tenant_runtime(admin_id, serialize_model_row(runtime))


async def update_bot_settings(
    session: AsyncSession, admin_id: str, updates: dict[str, Any], ip_address: str | None
) -> BotSettings:
    settings_row = await get_or_create_bot_settings(session, admin_id)
    app_settings = get_settings()

    before = {c.name: str(getattr(settings_row, c.name)) for c in settings_row.__table__.columns}

    if "leverage" in updates and updates["leverage"] is not None:
        requested_leverage = int(updates["leverage"])
        env_max = app_settings.max_allowed_leverage
        db_max = settings_row.max_allowed_leverage
        effective_max = min(env_max, db_max)
        if requested_leverage < 1 or requested_leverage > effective_max:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Kaldirac 1 ile {effective_max}x arasinda olmalidir (env sinir: {env_max}x)",
            )

    if "rsi_long_min" in updates and "rsi_long_max" in updates:
        if updates["rsi_long_min"] is not None and updates["rsi_long_max"] is not None:
            if updates["rsi_long_min"] >= updates["rsi_long_max"]:
                raise HTTPException(status_code=400, detail="RSI LONG min degeri max degerinden kucuk olmalidir")

    trigger = updates.get("loss_add_trigger_roi_pct", getattr(settings_row, "loss_add_trigger_roi_pct", None))
    stop_loss = updates.get("stop_loss_roi_pct", settings_row.stop_loss_roi_pct)
    if trigger is not None and stop_loss is not None and trigger >= stop_loss:
        raise HTTPException(
            status_code=400,
            detail="Zarar ekleme esigi (-%25 gibi), stop-loss seviyesinden (-%50) kucuk olmalidir",
        )

    for field, value in updates.items():
        if value is not None:
            setattr(settings_row, field, value)

    settings_row.updated_by_admin_id = admin_id
    await session.commit()
    await session.refresh(settings_row)

    after = {c.name: str(getattr(settings_row, c.name)) for c in settings_row.__table__.columns}
    await record_audit_log(
        session,
        admin_id=admin_id,
        action="UPDATE_SETTINGS",
        entity_type="bot_settings",
        entity_id=admin_id,
        before_data=before,
        after_data=after,
        ip_address=ip_address,
    )
    await sync_bot_settings_to_firebase(session, admin_id, settings_row)
    return settings_row


async def reset_settings_to_defaults(
    session: AsyncSession,
    admin_id: str,
    scope: SettingsResetScope,
    ip_address: str | None,
) -> BotSettings:
    updates = defaults_for_scope(scope)
    settings_row = await update_bot_settings(session, admin_id, updates, ip_address)
    await record_audit_log(
        session,
        admin_id=admin_id,
        action="RESET_SETTINGS_DEFAULTS",
        entity_type="bot_settings",
        entity_id=admin_id,
        after_data={"scope": scope},
        ip_address=ip_address,
    )
    return settings_row


def get_default_settings_by_scope(scope: SettingsResetScope) -> dict[str, object]:
    return defaults_for_scope(scope)


def get_all_panel_defaults() -> dict[str, dict[str, object]]:
    return {
        "general": dict(DEFAULT_GENERAL_SETTINGS),
        "position": dict(DEFAULT_POSITION_SETTINGS),
        "impulse": dict(DEFAULT_IMPULSE_SETTINGS),
    }
