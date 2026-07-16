from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin
from shared.default_bot_settings import SettingsResetScope

from ...core.database import get_db
from ...schemas.settings import BotSettingsOut, BotSettingsUpdate, PanelDefaultsOut
from ...services.settings_service import (
    get_all_panel_defaults,
    get_default_settings_by_scope,
    get_or_create_bot_settings,
    reset_settings_to_defaults,
    update_bot_settings,
)
from ..deps import get_current_admin, require_csrf

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=BotSettingsOut)
async def get_settings_endpoint(
    session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)
) -> BotSettingsOut:
    settings_row = await get_or_create_bot_settings(session, admin.id)
    return BotSettingsOut.model_validate(settings_row)


@router.put("", response_model=BotSettingsOut, dependencies=[Depends(require_csrf)])
async def update_settings_endpoint(
    payload: BotSettingsUpdate,
    request: Request,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> BotSettingsOut:
    updates = payload.model_dump(exclude_unset=True)
    client_ip = request.client.host if request.client else None
    settings_row = await update_bot_settings(session, admin.id, updates, client_ip)
    return BotSettingsOut.model_validate(settings_row)


@router.get("/defaults", response_model=PanelDefaultsOut)
async def get_default_settings_endpoint(
    scope: SettingsResetScope = Query(default="all"),
    _admin: Admin = Depends(get_current_admin),
) -> PanelDefaultsOut:
    if scope == "all":
        all_defaults = get_all_panel_defaults()
        return PanelDefaultsOut(
            general=_serialize_defaults(all_defaults["general"]),
            position=_serialize_defaults(all_defaults["position"]),
            impulse=_serialize_defaults(all_defaults["impulse"]),
        )
    return PanelDefaultsOut(**{scope: _serialize_defaults(get_default_settings_by_scope(scope))})


def _serialize_defaults(defaults: dict[str, object]) -> dict[str, str | int | bool]:
    out: dict[str, str | int | bool] = {}
    for key, value in defaults.items():
        if isinstance(value, bool):
            out[key] = value
        elif isinstance(value, int):
            out[key] = value
        else:
            out[key] = str(value)
    return out


@router.post("/reset-defaults", response_model=BotSettingsOut, dependencies=[Depends(require_csrf)])
async def reset_settings_to_defaults_endpoint(
    request: Request,
    scope: SettingsResetScope = Query(default="general"),
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> BotSettingsOut:
    client_ip = request.client.host if request.client else None
    settings_row = await reset_settings_to_defaults(session, admin.id, scope, client_ip)
    return BotSettingsOut.model_validate(settings_row)
