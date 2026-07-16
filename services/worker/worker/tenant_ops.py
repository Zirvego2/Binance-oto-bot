"""Worker icin musteri bazli Binance adapter olusturma."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceAdapterConfig, BinanceFuturesAdapter, build_adapter
from shared.customer_credentials import (
    environment_credentials_from_settings,
    profile_binance_credentials,
    resolve_admin_profile_record,
)
from shared.db import Admin
from shared.telegram_delivery import (
    deliver_position_closed_notification,
    deliver_position_opened_notification,
)

logger = __import__("logging").getLogger("worker.tenant_ops")


def build_adapter_config(settings, bot_mode: str, api_key: str, api_secret: str) -> BinanceAdapterConfig:
    return BinanceAdapterConfig(
        binance_env=bot_mode,
        live_base_url=settings.binance_futures_base_url,
        live_api_key=api_key,
        live_api_secret=api_secret,
        demo_base_url=settings.binance_demo_base_url,
        demo_api_key=api_key,
        demo_api_secret=api_secret,
        paper_market_base_url=settings.binance_futures_base_url,
        paper_start_balance_usdt=Decimal(settings.paper_start_balance_usdt),
        paper_taker_commission_rate=Decimal(settings.paper_taker_commission_rate),
    )


async def build_adapter_for_admin(session: AsyncSession, settings, admin_id: str, bot_mode: str) -> BinanceFuturesAdapter:
    admin = (await session.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if admin is None:
        raise RuntimeError(f"Musteri bulunamadi: {admin_id}")
    profile = await resolve_admin_profile_record(
        session,
        admin,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
    )
    creds = profile_binance_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=None,
    )
    if creds is None or not creds.api_key or not creds.api_secret:
        raise RuntimeError(f"Musteri {admin_id} icin Binance API anahtari tanimli degil")
    api_key = creds.api_key
    api_secret = creds.api_secret
    return build_adapter(build_adapter_config(settings, bot_mode, api_key, api_secret))


async def send_position_opened_notification(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    **fields,
) -> None:
    await deliver_position_opened_notification(
        session,
        settings,
        admin_id,
        source="worker",
        **fields,
    )


async def send_position_closed_notification(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    **fields,
) -> None:
    await deliver_position_closed_notification(
        session,
        settings,
        admin_id,
        source="worker",
        **fields,
    )
