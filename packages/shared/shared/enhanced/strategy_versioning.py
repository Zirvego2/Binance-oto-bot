"""Strateji versiyonlama ve geri alma."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, StrategyRegimeProfile, StrategyVersion


def _settings_to_dict(settings: BotSettings) -> dict[str, Any]:
    skip = {"created_at", "updated_at", "updated_by_admin_id"}
    out: dict[str, Any] = {}
    for col in BotSettings.__table__.columns:
        if col.name in skip:
            continue
        val = getattr(settings, col.name)
        if isinstance(val, Decimal):
            out[col.name] = str(val)
        else:
            out[col.name] = val
    return out


async def create_strategy_version(
    session: AsyncSession,
    settings: BotSettings,
    *,
    name: str,
    description: str | None = None,
    created_by: str | None = None,
    source: str = "MANUAL",
) -> StrategyVersion:
    profiles_result = await session.execute(select(StrategyRegimeProfile))
    profiles = profiles_result.scalars().all()
    profile_snap = {
        p.regime: {
            "indicator_weights": p.indicator_weights,
            "min_signal_score": str(p.min_signal_score),
            "risk_multiplier": str(p.risk_multiplier),
        }
        for p in profiles
    }
    version_str = f"v-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    sv = StrategyVersion(
        id=str(uuid.uuid4()),
        version=version_str,
        name=name,
        description=description,
        settings_snapshot=_settings_to_dict(settings),
        regime_profiles_snapshot=profile_snap,
        created_by=created_by,
        source=source,
        active_in_paper=True,
        created_at=datetime.now(timezone.utc),
    )
    session.add(sv)
    settings.active_strategy_version_id = sv.id
    await session.flush()
    return sv


async def activate_strategy_version(
    session: AsyncSession,
    version_id: str,
    *,
    mode: str,
    admin_id: str,
    confirmation_text: str | None = None,
) -> StrategyVersion:
    result = await session.execute(select(StrategyVersion).where(StrategyVersion.id == version_id))
    sv = result.scalar_one_or_none()
    if sv is None:
        raise ValueError("strategy_version_not_found")

    if mode == "live":
        if confirmation_text != "CANLI STRATEJİYİ DEĞİŞTİR":
            raise ValueError("live_strategy_confirmation_required")
        from shared.enhanced.live_activation import validate_live_enhanced_activation

        settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
        settings = settings_result.scalar_one()
        await validate_live_enhanced_activation(session, settings)

    await session.execute(
        update(StrategyVersion).values(
            active_in_paper=False, active_in_demo=False, active_in_live=False
        )
    )
    if mode == "paper":
        sv.active_in_paper = True
    elif mode == "demo":
        sv.active_in_demo = True
    elif mode == "live":
        sv.active_in_live = True
    else:
        raise ValueError("invalid_mode")

    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings = settings_result.scalar_one()
    settings.active_strategy_version_id = sv.id
    settings.updated_by_admin_id = admin_id
    await session.flush()
    return sv


async def rollback_strategy_version(session: AsyncSession, version_id: str) -> StrategyVersion:
    result = await session.execute(select(StrategyVersion).where(StrategyVersion.id == version_id))
    sv = result.scalar_one_or_none()
    if sv is None:
        raise ValueError("strategy_version_not_found")
    snap = sv.settings_snapshot or {}
    settings_result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
    settings = settings_result.scalar_one()
    skip = {"id", "created_at", "updated_at", "updated_by_admin_id"}
    for key, val in snap.items():
        if key in skip or not hasattr(settings, key):
            continue
        if isinstance(getattr(settings, key), Decimal) and val is not None and not isinstance(val, bool):
            setattr(settings, key, Decimal(str(val)))
        else:
            setattr(settings, key, val)
    settings.active_strategy_version_id = sv.id
    await session.flush()
    return sv
