"""API servisi icin musteri bazli Binance adapter erisimi."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceAdapterConfig, BinanceFuturesAdapter, build_adapter
from shared.customer_credentials import (
    ResolvedBinanceCredentials,
    environment_credentials_from_settings,
    profile_binance_credentials,
)

from .config import Settings, get_settings

_adapter_cache: dict[tuple[str, str], BinanceFuturesAdapter] = {}


def _settings() -> Settings:
    return get_settings()


async def resolve_binance_credentials_for_admin(
    session: AsyncSession,
    admin_id: str,
    settings: Settings | None = None,
) -> ResolvedBinanceCredentials | None:
    settings_obj = settings or _settings()
    from shared.enums import UserRole

    from ..services.profile_service import resolve_admin_profile_for_credentials

    resolved = await resolve_admin_profile_for_credentials(session, admin_id, settings_obj)
    if resolved is None:
        return None
    admin, profile = resolved
    env = None
    if admin.role != UserRole.CUSTOMER.value:
        env = environment_credentials_from_settings(settings_obj)
    creds = profile_binance_credentials(
        profile,
        encryption_key=settings_obj.app_encryption_key,
        app_secret=settings_obj.app_secret,
        env=env,
    )
    if creds and creds.api_key and creds.api_secret:
        return creds
    return None


def _build_config(binance_env: str, creds: ResolvedBinanceCredentials | None) -> BinanceAdapterConfig:
    settings = _settings()
    api_key = creds.api_key if creds else ""
    api_secret = creds.api_secret if creds else ""
    return BinanceAdapterConfig(
        binance_env=binance_env,
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


async def get_binance_adapter_for_admin(
    session: AsyncSession,
    admin_id: str,
    binance_env: str,
) -> BinanceFuturesAdapter:
    cache_key = (admin_id, binance_env)
    if cache_key not in _adapter_cache:
        creds = await resolve_binance_credentials_for_admin(session, admin_id)
        _adapter_cache[cache_key] = build_adapter(_build_config(binance_env, creds))
    return _adapter_cache[cache_key]


async def is_binance_configured_for_admin(session: AsyncSession, admin_id: str, binance_env: str) -> bool:
    if binance_env == "paper":
        return True
    creds = await resolve_binance_credentials_for_admin(session, admin_id)
    return bool(creds and creds.api_key and creds.api_secret)


def invalidate_binance_adapter_cache(admin_id: str | None = None) -> None:
    if admin_id is None:
        _adapter_cache.clear()
        return
    keys = [key for key in _adapter_cache if key[0] == admin_id]
    for key in keys:
        del _adapter_cache[key]


# Geriye uyumluluk (platform ic islemleri icin kullanilmamali)
async def refresh_binance_credentials_cache(session: AsyncSession, settings: Settings | None = None) -> None:
    invalidate_binance_adapter_cache()


def get_binance_adapter(binance_env: str) -> BinanceFuturesAdapter:
    """@deprecated Musteri bazli get_binance_adapter_for_admin kullanin."""
    settings = _settings()
    cache_key = ("legacy", binance_env)
    if cache_key not in _adapter_cache:
        env = environment_credentials_from_settings(settings)
        creds = profile_binance_credentials(
            None,
            encryption_key=settings.app_encryption_key,
            app_secret=settings.app_secret,
            env=env,
        )
        _adapter_cache[cache_key] = build_adapter(_build_config(binance_env, creds))
    return _adapter_cache[cache_key]


def is_binance_configured(binance_env: str) -> bool:
    if binance_env == "paper":
        return True
    settings = _settings()
    env = environment_credentials_from_settings(settings)
    creds = profile_binance_credentials(
        None,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    return bool(creds and creds.api_key and creds.api_secret)
