from __future__ import annotations

from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance import BinanceAdapterConfig, BinanceFuturesAdapter, build_adapter
from shared.customer_credentials import (
    bootstrap_profile_from_environment,
    environment_credentials_from_settings,
    get_admin_profile,
    get_or_create_admin_profile,
    mask_api_key,
    profile_binance_credentials,
    profile_openai_credentials,
    profile_telegram_credentials,
)
from shared.enums import UserRole
from shared.db import Admin
from shared.db.models_profile import AdminProfile
from shared.secrets_crypto import encrypt_secret
from shared.telegram_discovery import discover_telegram_chat_id as fetch_telegram_chat_id

from ..core.config import Settings
from ..core.firebase import firebase_enabled
from ..schemas.profile import ProfileConnectionsOut, ProfileConnectionsSummary, ProfileConnectionsUpdate, ProfileOut
from .firestore_customer_service import get_customer, update_customer_connections, upsert_customer

PROFILE_UNLOCK_PREFIX = "profile_unlock:"


def _unlock_key(admin_id: str) -> str:
    return f"{PROFILE_UNLOCK_PREFIX}{admin_id}"


async def is_profile_unlocked(redis: Redis, admin_id: str) -> bool:
    return bool(await redis.get(_unlock_key(admin_id)))


async def unlock_profile(redis: Redis, admin_id: str, ttl_seconds: int) -> None:
    await redis.set(_unlock_key(admin_id), "1", ex=ttl_seconds)


async def lock_profile(redis: Redis, admin_id: str) -> None:
    await redis.delete(_unlock_key(admin_id))


async def verify_profile_password(password: str, settings: Settings) -> bool:
    return password == settings.profile_access_password


def _env_credentials(settings: Settings):
    return environment_credentials_from_settings(settings)


def _env_fallback_for_admin(admin: Admin, settings: Settings):
    """SaaS musterileri icin .env anahtarlari kullanilmaz."""
    if admin.role == UserRole.CUSTOMER.value:
        return None
    return _env_credentials(settings)


def _profile_has_stored_secrets(profile: AdminProfile) -> bool:
    return bool(
        profile.binance_api_key_enc
        or profile.binance_api_secret_enc
        or profile.telegram_bot_token_enc
        or profile.openai_api_key_enc
    )


def _connections_document_from_profile(profile: AdminProfile) -> dict[str, Any]:
    if not _profile_has_stored_secrets(profile):
        return {}
    return {
        "binanceApiKeyEnc": profile.binance_api_key_enc,
        "binanceApiSecretEnc": profile.binance_api_secret_enc,
        "telegramBotTokenEnc": profile.telegram_bot_token_enc,
        "telegramChatId": profile.telegram_chat_id,
        "telegramNotificationsEnabled": profile.telegram_notifications_enabled,
        "openaiApiKeyEnc": profile.openai_api_key_enc,
    }


def _connections_has_stored_secrets(connections: dict[str, Any]) -> bool:
    return bool(
        connections.get("binanceApiKeyEnc")
        or connections.get("binanceApiSecretEnc")
        or connections.get("telegramBotTokenEnc")
        or connections.get("openaiApiKeyEnc")
    )


def _apply_connections_document_to_profile(profile: AdminProfile, connections: dict[str, Any]) -> None:
    profile.binance_api_key_enc = connections.get("binanceApiKeyEnc")
    profile.binance_api_secret_enc = connections.get("binanceApiSecretEnc")
    profile.telegram_bot_token_enc = connections.get("telegramBotTokenEnc")
    profile.telegram_chat_id = connections.get("telegramChatId")
    profile.telegram_notifications_enabled = bool(connections.get("telegramNotificationsEnabled"))
    profile.openai_api_key_enc = connections.get("openaiApiKeyEnc")


async def _get_customer_profile(session: AsyncSession, admin_id: str) -> AdminProfile:
    """Musteri profili — .env bootstrap YAPMAZ."""
    return await get_or_create_admin_profile(session, admin_id)


def _uses_firestore(admin: Admin) -> bool:
    return bool(admin.firebase_uid and firebase_enabled())


async def _ensure_sql_profile_ready(session: AsyncSession, admin: Admin, settings: Settings) -> AdminProfile:
    """Yalnizca legacy (platform) hesaplar icin .env bootstrap; musteriler bos profil."""
    profile = await get_or_create_admin_profile(session, admin.id)
    if admin.role == UserRole.CUSTOMER.value:
        return profile
    env = _env_credentials(settings)
    return await bootstrap_profile_from_environment(
        session,
        admin.id,
        env,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
    )


async def profile_document_from_sql(session: AsyncSession, admin: Admin, settings: Settings) -> dict[str, Any]:
    profile = await _get_customer_profile(session, admin.id)
    return _connections_document_from_profile(profile)


async def reconcile_customer_connections(
    session: AsyncSession,
    admin: Admin,
    settings: Settings,
) -> dict[str, Any] | None:
    """SQL ve Firestore baglanti dokumanlarini hizalar.

    Donus:
      - dict: Firestore'a yazilacak connections
      - None: mevcut Firestore connections korunur (bos SQL ile silinmez)
    """
    if not _uses_firestore(admin):
        return None

    sql_profile = await _get_customer_profile(session, admin.id)
    sql_doc = _connections_document_from_profile(sql_profile)
    sql_has = _connections_has_stored_secrets(sql_doc)

    customer = await get_customer(admin.firebase_uid)  # type: ignore[arg-type]
    firestore_conn = dict((customer or {}).get("connections") or {})
    firestore_has = _connections_has_stored_secrets(firestore_conn)

    if sql_has:
        if not firestore_has or firestore_conn != sql_doc:
            return sql_doc
        return None

    if firestore_has:
        _apply_connections_document_to_profile(sql_profile, firestore_conn)
        await session.commit()
        return None

    return None


def _profile_from_firestore_connections(connections: dict[str, Any] | None) -> AdminProfile | None:
    if not connections:
        return None
    profile = AdminProfile(admin_id="firestore")
    profile.binance_api_key_enc = connections.get("binanceApiKeyEnc")
    profile.binance_api_secret_enc = connections.get("binanceApiSecretEnc")
    profile.telegram_bot_token_enc = connections.get("telegramBotTokenEnc")
    profile.telegram_chat_id = connections.get("telegramChatId")
    profile.telegram_notifications_enabled = bool(connections.get("telegramNotificationsEnabled"))
    profile.openai_api_key_enc = connections.get("openaiApiKeyEnc")
    return profile


async def _resolve_profile_record(session: AsyncSession, admin: Admin, settings: Settings) -> AdminProfile:
    if _uses_firestore(admin):
        customer = await get_customer(admin.firebase_uid)  # type: ignore[arg-type]
        firestore_profile = _profile_from_firestore_connections((customer or {}).get("connections"))
        if firestore_profile is not None and _profile_has_stored_secrets(firestore_profile):
            return firestore_profile
    if admin.role == UserRole.CUSTOMER.value:
        return await _get_customer_profile(session, admin.id)
    return await _ensure_sql_profile_ready(session, admin, settings)


async def resolve_admin_profile_for_credentials(
    session: AsyncSession,
    admin_id: str,
    settings: Settings,
) -> tuple[Admin, AdminProfile] | None:
    """Firestore + SQL profil kaynagini birlestirerek entegrasyon anahtarlarini cozer."""

    from sqlalchemy import select

    admin = (await session.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if admin is None:
        return None
    profile = await _resolve_profile_record(session, admin, settings)
    return admin, profile


def _telegram_allow_env_fallback(admin: Admin) -> bool:
    return admin.role != UserRole.CUSTOMER.value


def _build_connections_summary(profile: AdminProfile, settings: Settings, *, admin: Admin) -> ProfileConnectionsSummary:
    env = _env_fallback_for_admin(admin, settings)
    binance = profile_binance_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    telegram = profile_telegram_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
        allow_env_fallback=_telegram_allow_env_fallback(admin),
    )
    openai = profile_openai_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    source_prefix = "firebase" if profile.admin_id == "firestore" else None
    return ProfileConnectionsSummary(
        binance_configured=bool(binance),
        binance_source=source_prefix or (binance.source if binance else None),
        telegram_configured=bool(telegram.bot_token and telegram.chat_id),
        telegram_source=source_prefix or telegram.source,
        openai_configured=bool(openai),
        openai_source=source_prefix or (openai.source if openai else None),
    )


async def build_profile_out(
    session: AsyncSession,
    admin: Admin,
    settings: Settings,
    *,
    unlocked: bool,
) -> ProfileOut:
    profile = await _resolve_profile_record(session, admin, settings)
    return ProfileOut(
        id=admin.id,
        email=admin.email,
        full_name=admin.full_name,
        last_login_at=admin.last_login_at,
        connections_unlocked=unlocked,
        connections_summary=_build_connections_summary(profile, settings, admin=admin),
        firebase_uid=admin.firebase_uid,
        account_type="customer" if admin.firebase_uid else "legacy",
    )


async def get_connections_out(session: AsyncSession, admin: Admin, settings: Settings) -> ProfileConnectionsOut:
    profile = await _resolve_profile_record(session, admin, settings)
    env = _env_fallback_for_admin(admin, settings)
    binance = profile_binance_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    telegram = profile_telegram_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
        allow_env_fallback=_telegram_allow_env_fallback(admin),
    )
    openai = profile_openai_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    is_firebase = profile.admin_id == "firestore"
    return ProfileConnectionsOut(
        binance_api_key_masked=mask_api_key(binance.api_key if binance else None),
        binance_api_secret_set=bool(binance and binance.api_secret),
        binance_configured=bool(binance),
        binance_source="firebase" if is_firebase and binance else (binance.source if binance else None),
        telegram_bot_token_masked=mask_api_key(telegram.bot_token if telegram.bot_token else None),
        telegram_chat_id=telegram.chat_id or None,
        telegram_notifications_enabled=telegram.enabled,
        telegram_configured=bool(telegram.bot_token and telegram.chat_id),
        telegram_source="firebase" if is_firebase and telegram.bot_token else telegram.source,
        openai_api_key_masked=mask_api_key(openai.api_key if openai else None),
        openai_configured=bool(openai),
        openai_source="firebase" if is_firebase and openai else (openai.source if openai else None),
    )


async def update_connections(
    session: AsyncSession,
    admin: Admin,
    settings: Settings,
    payload: ProfileConnectionsUpdate,
) -> ProfileConnectionsOut:
    if _uses_firestore(admin):
        customer = await get_customer(admin.firebase_uid)  # type: ignore[arg-type]
        connections = dict((customer or {}).get("connections") or {})
        if not connections:
            connections = await profile_document_from_sql(session, admin, settings)

        if payload.binance_api_key is not None:
            value = payload.binance_api_key.strip()
            connections["binanceApiKeyEnc"] = (
                encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
                if value
                else None
            )
        if payload.binance_api_secret is not None:
            value = payload.binance_api_secret.strip()
            connections["binanceApiSecretEnc"] = (
                encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
                if value
                else None
            )
        if payload.telegram_bot_token is not None:
            value = payload.telegram_bot_token.strip()
            connections["telegramBotTokenEnc"] = (
                encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
                if value
                else None
            )
        if payload.telegram_chat_id is not None:
            connections["telegramChatId"] = payload.telegram_chat_id.strip() or None
        if payload.telegram_notifications_enabled is not None:
            connections["telegramNotificationsEnabled"] = payload.telegram_notifications_enabled
        elif admin.role == UserRole.CUSTOMER.value:
            has_token = bool(connections.get("telegramBotTokenEnc"))
            has_chat = bool(connections.get("telegramChatId"))
            if has_token and has_chat:
                connections["telegramNotificationsEnabled"] = True
        if payload.openai_api_key is not None:
            value = payload.openai_api_key.strip()
            connections["openaiApiKeyEnc"] = (
                encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
                if value
                else None
            )

        # Worker ve login sync SQL'den okuyor; once SQL'e yaz, sonra Firestore.
        sql_profile = await get_or_create_admin_profile(session, admin.id)
        _apply_connections_document_to_profile(sql_profile, connections)
        await session.commit()

        await update_customer_connections(admin.firebase_uid, connections)  # type: ignore[arg-type]
        await upsert_customer(
            admin.firebase_uid,  # type: ignore[arg-type]
            email=admin.email,
            admin_id=admin.id,
            full_name=admin.full_name,
            connections=connections,
        )
        return await get_connections_out(session, admin, settings)

    profile = await get_or_create_admin_profile(session, admin.id)
    if payload.binance_api_key is not None:
        value = payload.binance_api_key.strip()
        profile.binance_api_key_enc = (
            encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
            if value
            else None
        )
    if payload.binance_api_secret is not None:
        value = payload.binance_api_secret.strip()
        profile.binance_api_secret_enc = (
            encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
            if value
            else None
        )
    if payload.telegram_bot_token is not None:
        value = payload.telegram_bot_token.strip()
        profile.telegram_bot_token_enc = (
            encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
            if value
            else None
        )
    if payload.telegram_chat_id is not None:
        profile.telegram_chat_id = payload.telegram_chat_id.strip() or None
    if payload.telegram_notifications_enabled is not None:
        profile.telegram_notifications_enabled = payload.telegram_notifications_enabled
    elif admin.role == UserRole.CUSTOMER.value and profile.telegram_bot_token_enc and profile.telegram_chat_id:
        profile.telegram_notifications_enabled = True
    if payload.openai_api_key is not None:
        value = payload.openai_api_key.strip()
        profile.openai_api_key_enc = (
            encrypt_secret(value, encryption_key=settings.app_encryption_key, app_secret=settings.app_secret)
            if value
            else None
        )

    await session.commit()
    await session.refresh(profile)
    return await get_connections_out(session, admin, settings)


async def test_binance_connection(session: AsyncSession, admin: Admin, settings: Settings, binance_env: str) -> tuple[bool, str]:
    profile = await _resolve_profile_record(session, admin, settings)
    env = _env_fallback_for_admin(admin, settings)
    creds = profile_binance_credentials(
        profile,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    if binance_env == "paper":
        return True, "Paper modda Binance API anahtari gerekmez."
    if creds is None:
        return False, "Binance API anahtari tanimli degil. Profilinizden girin."

    config = BinanceAdapterConfig(
        binance_env=binance_env,
        live_base_url=settings.binance_futures_base_url,
        live_api_key=creds.api_key,
        live_api_secret=creds.api_secret,
        demo_base_url=settings.binance_demo_base_url,
        demo_api_key=creds.api_key,
        demo_api_secret=creds.api_secret,
        paper_market_base_url=settings.binance_futures_base_url,
        paper_start_balance_usdt=Decimal(settings.paper_start_balance_usdt),
        paper_taker_commission_rate=Decimal(settings.paper_taker_commission_rate),
    )
    adapter: BinanceFuturesAdapter = build_adapter(config)
    try:
        result = await adapter.test_connection()
        if result.is_connected and result.account_access_ok:
            source = "firebase" if profile.admin_id == "firestore" else creds.source
            return True, f"Binance baglantisi basarili ({source})."
        return False, result.error_message or "Binance baglantisi basarisiz."
    except Exception as exc:  # noqa: BLE001
        return False, f"Binance baglantisi basarisiz: {exc}"


async def test_telegram_connection(session: AsyncSession, admin: Admin, settings: Settings) -> tuple[bool, str]:
    from shared.telegram_delivery import deliver_test_notification

    return await deliver_test_notification(session, settings, admin.id, source="api")


async def discover_telegram_chat_id_for_profile(
    session: AsyncSession,
    admin: Admin,
    settings: Settings,
    *,
    bot_token_override: str | None = None,
) -> tuple[bool, str | None, str]:
    profile = await _resolve_profile_record(session, admin, settings)
    env = _env_fallback_for_admin(admin, settings)

    token = (bot_token_override or "").strip()
    if not token:
        telegram = profile_telegram_credentials(
            profile,
            encryption_key=settings.app_encryption_key,
            app_secret=settings.app_secret,
            env=env,
        )
        token = (telegram.bot_token or "").strip()

    if not token:
        return False, None, "Once bot token girin veya kaydedin."

    result = await fetch_telegram_chat_id(token)
    return result.ok, result.chat_id, result.message
