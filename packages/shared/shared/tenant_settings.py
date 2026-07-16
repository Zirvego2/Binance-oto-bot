"""Musteri (tenant) bazli bot ayarlari ve calisma zamani yardimcilari."""

from __future__ import annotations

import copy

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, AdminProfile, BotRuntimeStatus, BotSettings, Symbol, SymbolRule
from shared.db.base import new_uuid
from shared.enums import ApprovalStatus, UserRole
from shared.membership import is_membership_active


async def get_bot_settings_for_admin(session: AsyncSession, admin_id: str) -> BotSettings | None:
    result = await session.execute(select(BotSettings).where(BotSettings.admin_id == admin_id))
    return result.scalar_one_or_none()


async def get_or_create_bot_settings(session: AsyncSession, admin_id: str) -> BotSettings:
    settings_row = await get_bot_settings_for_admin(session, admin_id)
    if settings_row is not None:
        return settings_row

    template = await session.execute(
        select(BotSettings).where(BotSettings.admin_id.is_not(None)).order_by(BotSettings.created_at.asc()).limit(1)
    )
    template_row = template.scalar_one_or_none()
    if template_row is None:
        template_row = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
        template_row = template_row.scalar_one_or_none()

    if template_row is not None:
        settings_row = BotSettings(id=new_uuid())
        for column in BotSettings.__table__.columns:
            name = column.name
            if name in ("id", "admin_id", "created_at", "updated_at", "updated_by_admin_id"):
                continue
            setattr(settings_row, name, copy.deepcopy(getattr(template_row, name)))
    else:
        settings_row = BotSettings(id=new_uuid())

    settings_row.admin_id = admin_id
    settings_row.bot_enabled = False
    session.add(settings_row)
    await session.flush()
    return settings_row


async def get_or_create_bot_runtime(session: AsyncSession, admin_id: str) -> BotRuntimeStatus:
    result = await session.execute(select(BotRuntimeStatus).where(BotRuntimeStatus.admin_id == admin_id))
    runtime = result.scalar_one_or_none()
    if runtime is not None:
        return runtime
    runtime = BotRuntimeStatus(id=new_uuid(), admin_id=admin_id, run_state="STOPPED")
    session.add(runtime)
    await session.flush()
    return runtime


async def seed_symbol_rules_for_tenant(session: AsyncSession, admin_id: str) -> int:
    """Yeni musteri icin sembol kurallarini varsayilanlarla olusturur."""
    existing = set(
        (await session.execute(select(SymbolRule.symbol).where(SymbolRule.admin_id == admin_id))).scalars().all()
    )
    symbols = (await session.execute(select(Symbol.symbol))).scalars().all()
    created = 0
    for symbol in symbols:
        if symbol in existing:
            continue
        session.add(
            SymbolRule(
                id=new_uuid(),
                admin_id=admin_id,
                symbol=symbol,
                in_analysis_list=True,
                is_blacklisted=False,
                long_enabled=True,
                short_enabled=True,
            )
        )
        created += 1
    if created:
        await session.flush()
    return created


async def provision_tenant_defaults(session: AsyncSession, admin_id: str) -> None:
    """Onaylanan musteri icin ayar satirlari olusturur ve Firestore tenant koleksiyonlarini hazirlar."""
    settings_row = await get_or_create_bot_settings(session, admin_id)
    runtime = await get_or_create_bot_runtime(session, admin_id)
    await seed_symbol_rules_for_tenant(session, admin_id)
    for env in ("paper", "demo", "live"):
        from shared.tenant_scope import get_or_create_connection_status

        await get_or_create_connection_status(session, admin_id, env)

    try:
        from shared.firestore import firebase_enabled, serialize_model_row, upsert_tenant_runtime, upsert_tenant_settings

        if firebase_enabled():
            await upsert_tenant_settings(admin_id, serialize_model_row(settings_row))
            await upsert_tenant_runtime(admin_id, serialize_model_row(runtime))
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Firestore tenant provision basarisiz (admin=%s)", admin_id, exc_info=True
        )


async def list_reconciliation_tenant_admins(
    session: AsyncSession,
    bot_mode: str,
    *,
    encryption_key: str = "",
    app_secret: str = "",
) -> list[Admin]:
    """Live/demo reconciliation icin Binance key'i olan onayli musteriler."""
    from shared.customer_credentials import admin_has_binance_credentials

    rows = (
        await session.execute(
            select(Admin)
            .where(Admin.role == UserRole.CUSTOMER.value)
            .where(Admin.approval_status == ApprovalStatus.APPROVED.value)
            .where(Admin.is_active.is_(True))
            .order_by(Admin.created_at.asc())
        )
    ).scalars().all()
    eligible: list[Admin] = []
    for admin in rows:
        if not is_membership_active(admin):
            continue
        settings_row = await get_bot_settings_for_admin(session, admin.id)
        if settings_row is None or settings_row.mode != bot_mode:
            continue
        if encryption_key and app_secret:
            has_keys = await admin_has_binance_credentials(
                session,
                admin,
                encryption_key=encryption_key,
                app_secret=app_secret,
            )
        else:
            profile = (
                await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
            ).scalar_one_or_none()
            has_keys = profile is not None and bool(profile.binance_api_key_enc)
        if not has_keys:
            continue
        eligible.append(admin)
    return eligible


async def list_active_tenant_admins(
    session: AsyncSession,
    *,
    encryption_key: str = "",
    app_secret: str = "",
) -> list[Admin]:
    """Onayli, aktif ve botu acik musterileri dondurur."""
    from shared.customer_credentials import admin_has_binance_credentials

    rows = (
        await session.execute(
            select(Admin)
            .where(Admin.role == UserRole.CUSTOMER.value)
            .where(Admin.approval_status == ApprovalStatus.APPROVED.value)
            .where(Admin.is_active.is_(True))
            .order_by(Admin.created_at.asc())
        )
    ).scalars().all()
    active: list[Admin] = []
    for admin in rows:
        if not is_membership_active(admin):
            continue
        settings_row = await get_bot_settings_for_admin(session, admin.id)
        if settings_row is None or not settings_row.bot_enabled:
            continue
        if encryption_key and app_secret:
            has_keys = await admin_has_binance_credentials(
                session,
                admin,
                encryption_key=encryption_key,
                app_secret=app_secret,
            )
        else:
            profile = (
                await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin.id))
            ).scalar_one_or_none()
            has_keys = profile is not None and bool(profile.binance_api_key_enc)
        if not has_keys:
            continue
        active.append(admin)
    return active
