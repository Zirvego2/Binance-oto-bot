"""Binance baglanti durumu servisi (musteri bazli)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceApiError, BinanceConnectionError, BinanceNotConfiguredError
from shared.db import BinanceConnectionStatus
from shared.tenant_scope import get_or_create_connection_status

from ..core.binance_client import get_binance_adapter_for_admin, is_binance_configured_for_admin


async def get_or_create_status_row(
    session: AsyncSession, admin_id: str, environment: str
) -> BinanceConnectionStatus:
    row = await get_or_create_connection_status(session, admin_id, environment)
    if not row.is_configured:
        row.is_configured = await is_binance_configured_for_admin(session, admin_id, environment)
    return row


async def test_connection_and_persist(
    session: AsyncSession, admin_id: str, environment: str
) -> BinanceConnectionStatus:
    row = await get_or_create_status_row(session, admin_id, environment)
    now = datetime.now(timezone.utc)

    if not await is_binance_configured_for_admin(session, admin_id, environment):
        row.is_configured = False
        row.is_connected = False
        row.account_access_ok = False
        row.futures_account_usable = False
        row.trading_permission_ok = False
        row.last_error_at = now
        row.last_error_message = "Binance API bilgileri henuz eklenmedi"
        await session.commit()
        return row

    adapter = await get_binance_adapter_for_admin(session, admin_id, environment)
    try:
        result = await adapter.test_connection()
        row.is_configured = result.is_configured
        row.is_connected = result.is_connected
        row.account_access_ok = result.account_access_ok
        row.futures_account_usable = result.futures_account_usable
        row.trading_permission_ok = result.trading_permission_ok
        if result.is_connected and result.account_access_ok:
            row.last_success_at = now
            row.last_error_message = None
        else:
            row.last_error_at = now
            row.last_error_message = result.error_message

        if environment != "paper" and result.is_connected and result.account_access_ok:
            try:
                position_mode = await adapter.get_position_mode()
                row.position_mode_verified = position_mode == "ONE_WAY"
                multi_assets = await adapter.get_multi_assets_mode()
                row.multi_assets_mode_off_verified = multi_assets is False
            except (BinanceApiError, BinanceConnectionError):
                pass
        else:
            row.position_mode_verified = True
            row.multi_assets_mode_off_verified = True
    except BinanceNotConfiguredError as exc:
        row.is_configured = False
        row.is_connected = False
        row.last_error_at = now
        row.last_error_message = str(exc)
    except (BinanceApiError, BinanceConnectionError) as exc:
        row.is_connected = False
        row.last_error_at = now
        row.last_error_message = str(exc)

    await session.commit()
    await session.refresh(row)
    return row
