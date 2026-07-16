"""Musteri profilinden veya ortam degiskenlerinden baglanti bilgilerini cozer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db.models_profile import AdminProfile
from .masking import mask_value
from .secrets_crypto import decrypt_secret, encrypt_secret
from .telegram_notifier import _load_telegram_env


@dataclass(frozen=True, slots=True)
class EnvironmentCredentials:
    binance_api_key: str
    binance_api_secret: str
    telegram_notifications_enabled: bool
    telegram_bot_token: str
    telegram_chat_id: str
    openai_api_key: str


@dataclass(frozen=True, slots=True)
class ResolvedBinanceCredentials:
    api_key: str
    api_secret: str
    source: str  # profile | env


@dataclass(frozen=True, slots=True)
class ResolvedTelegramCredentials:
    enabled: bool
    bot_token: str
    chat_id: str
    source: str  # profile | env


@dataclass(frozen=True, slots=True)
class ResolvedOpenAiCredentials:
    api_key: str
    source: str  # profile | env


class CredentialSettingsSource(Protocol):
    binance_api_key: str
    binance_api_secret: str
    openai_api_key: str


def environment_credentials_from_settings(settings: CredentialSettingsSource) -> EnvironmentCredentials:
    telegram_env = _load_telegram_env()
    enabled_raw = telegram_env.get("TELEGRAM_NOTIFICATIONS_ENABLED", "false").strip().lower()
    return EnvironmentCredentials(
        binance_api_key=(settings.binance_api_key or "").strip(),
        binance_api_secret=(settings.binance_api_secret or "").strip(),
        telegram_notifications_enabled=enabled_raw in ("1", "true", "yes", "on"),
        telegram_bot_token=telegram_env.get("TELEGRAM_BOT_TOKEN", "").strip(),
        telegram_chat_id=telegram_env.get("TELEGRAM_CHAT_ID", "").strip(),
        openai_api_key=(settings.openai_api_key or "").strip(),
    )


def _env_binance_credentials(env: EnvironmentCredentials | None) -> ResolvedBinanceCredentials | None:
    if env is None or not env.binance_api_key or not env.binance_api_secret:
        return None
    return ResolvedBinanceCredentials(api_key=env.binance_api_key, api_secret=env.binance_api_secret, source="env")


def _env_telegram_credentials(env: EnvironmentCredentials | None) -> ResolvedTelegramCredentials:
    if env is None:
        return ResolvedTelegramCredentials(enabled=False, bot_token="", chat_id="", source="env")
    return ResolvedTelegramCredentials(
        enabled=env.telegram_notifications_enabled,
        bot_token=env.telegram_bot_token,
        chat_id=env.telegram_chat_id,
        source="env",
    )


def _env_openai_credentials(env: EnvironmentCredentials | None) -> ResolvedOpenAiCredentials | None:
    if env is None or not env.openai_api_key:
        return None
    return ResolvedOpenAiCredentials(api_key=env.openai_api_key, source="env")


def _decrypt_field(value: str | None, *, encryption_key: str, app_secret: str) -> str:
    if not value:
        return ""
    try:
        return decrypt_secret(value, encryption_key=encryption_key, app_secret=app_secret)
    except ValueError:
        return ""


def _profile_has_stored_secrets(profile: AdminProfile) -> bool:
    return bool(
        profile.binance_api_key_enc
        or profile.binance_api_secret_enc
        or profile.telegram_bot_token_enc
        or profile.openai_api_key_enc
    )


def profile_from_firestore_connections(connections: dict[str, Any] | None) -> AdminProfile | None:
    if not connections:
        return None
    profile = AdminProfile(admin_id="firestore")
    profile.binance_api_key_enc = connections.get("binanceApiKeyEnc")
    profile.binance_api_secret_enc = connections.get("binanceApiSecretEnc")
    profile.telegram_bot_token_enc = connections.get("telegramBotTokenEnc")
    profile.telegram_chat_id = connections.get("telegramChatId")
    if profile.telegram_chat_id is not None:
        profile.telegram_chat_id = str(profile.telegram_chat_id)
    profile.telegram_notifications_enabled = bool(connections.get("telegramNotificationsEnabled"))
    profile.openai_api_key_enc = connections.get("openaiApiKeyEnc")
    return profile


async def resolve_admin_profile_record(
    session: AsyncSession,
    admin,
    *,
    encryption_key: str,
    app_secret: str,
) -> AdminProfile:
    """Firebase musterileri icin Firestore + SQL profil kaynaklarini birlestirir."""

    if getattr(admin, "firebase_uid", None):
        try:
            from shared.firestore.bootstrap import firebase_enabled
            from shared.firestore.tenant_repository import get_customer

            if firebase_enabled():
                customer = await get_customer(admin.firebase_uid)
                firestore_profile = profile_from_firestore_connections((customer or {}).get("connections"))
                if firestore_profile is not None and _profile_has_stored_secrets(firestore_profile):
                    return firestore_profile
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "Firestore profil okunamadi (admin=%s)", getattr(admin, "id", "?"), exc_info=True
            )
    return await get_or_create_admin_profile(session, admin.id)


async def admin_has_binance_credentials(
    session: AsyncSession,
    admin,
    *,
    encryption_key: str,
    app_secret: str,
) -> bool:
    profile = await resolve_admin_profile_record(
        session,
        admin,
        encryption_key=encryption_key,
        app_secret=app_secret,
    )
    creds = profile_binance_credentials(
        profile,
        encryption_key=encryption_key,
        app_secret=app_secret,
        env=None,
    )
    return creds is not None


async def get_admin_profile(session: AsyncSession, admin_id: str) -> AdminProfile | None:
    result = await session.execute(select(AdminProfile).where(AdminProfile.admin_id == admin_id))
    return result.scalar_one_or_none()


async def get_or_create_admin_profile(session: AsyncSession, admin_id: str) -> AdminProfile:
    profile = await get_admin_profile(session, admin_id)
    if profile is not None:
        return profile
    profile = AdminProfile(admin_id=admin_id)
    session.add(profile)
    await session.flush()
    return profile


async def get_primary_admin_profile(session: AsyncSession) -> AdminProfile | None:
    result = await session.execute(select(AdminProfile).order_by(AdminProfile.created_at.asc()).limit(1))
    return result.scalar_one_or_none()


async def bootstrap_profile_from_environment(
    session: AsyncSession,
    admin_id: str,
    env: EnvironmentCredentials,
    *,
    encryption_key: str,
    app_secret: str,
) -> AdminProfile:
    """Profil bosken mevcut .env / sunucu ayarlarini musteri profiline tek seferlik aktarir."""

    profile = await get_or_create_admin_profile(session, admin_id)
    if _profile_has_stored_secrets(profile):
        return profile

    changed = False
    if env.binance_api_key and env.binance_api_secret:
        profile.binance_api_key_enc = encrypt_secret(
            env.binance_api_key, encryption_key=encryption_key, app_secret=app_secret
        )
        profile.binance_api_secret_enc = encrypt_secret(
            env.binance_api_secret, encryption_key=encryption_key, app_secret=app_secret
        )
        changed = True

    if env.telegram_bot_token and env.telegram_chat_id:
        profile.telegram_bot_token_enc = encrypt_secret(
            env.telegram_bot_token, encryption_key=encryption_key, app_secret=app_secret
        )
        profile.telegram_chat_id = env.telegram_chat_id
        profile.telegram_notifications_enabled = env.telegram_notifications_enabled
        changed = True

    if env.openai_api_key:
        profile.openai_api_key_enc = encrypt_secret(
            env.openai_api_key, encryption_key=encryption_key, app_secret=app_secret
        )
        changed = True

    if changed:
        await session.commit()
        await session.refresh(profile)
    return profile


def profile_binance_credentials(
    profile: AdminProfile | None,
    *,
    encryption_key: str,
    app_secret: str,
    env: EnvironmentCredentials | None = None,
) -> ResolvedBinanceCredentials | None:
    if profile is not None:
        key = _decrypt_field(profile.binance_api_key_enc, encryption_key=encryption_key, app_secret=app_secret)
        secret = _decrypt_field(profile.binance_api_secret_enc, encryption_key=encryption_key, app_secret=app_secret)
        if key and secret:
            return ResolvedBinanceCredentials(api_key=key, api_secret=secret, source="profile")
    return _env_binance_credentials(env)


def _empty_telegram_credentials() -> ResolvedTelegramCredentials:
    return ResolvedTelegramCredentials(enabled=False, bot_token="", chat_id="", source="profile")


def profile_telegram_credentials(
    profile: AdminProfile | None,
    *,
    encryption_key: str,
    app_secret: str,
    env: EnvironmentCredentials | None = None,
    allow_env_fallback: bool = True,
) -> ResolvedTelegramCredentials:
    if profile is not None:
        token = _decrypt_field(profile.telegram_bot_token_enc, encryption_key=encryption_key, app_secret=app_secret)
        chat_id = str(profile.telegram_chat_id or "").strip()
        if token and chat_id:
            return ResolvedTelegramCredentials(
                enabled=profile.telegram_notifications_enabled,
                bot_token=token,
                chat_id=chat_id,
                source="profile",
            )
    if allow_env_fallback:
        return _env_telegram_credentials(env)
    return _empty_telegram_credentials()


async def resolve_telegram_config_for_admin(
    session: AsyncSession,
    admin_id: str | None,
    *,
    encryption_key: str,
    app_secret: str,
    env: EnvironmentCredentials | None = None,
):
    """Musteri profilinden (Firestore/SQL) Telegram bildirim yapilandirmasi cozer.

    Musteri hesaplari yalnizca kendi profillerindeki bot token + chat ID kullanir;
    .env TELEGRAM_* degerlerine dusmez.
    """

    from shared.db import Admin
    from shared.enums import UserRole
    from shared.telegram_notifier import TelegramConfig

    if admin_id:
        admin = (await session.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
        if admin is not None:
            is_customer = admin.role == UserRole.CUSTOMER.value
            profile = await resolve_admin_profile_record(
                session,
                admin,
                encryption_key=encryption_key,
                app_secret=app_secret,
            )
            env_for_admin = None if is_customer else env
            telegram = profile_telegram_credentials(
                profile,
                encryption_key=encryption_key,
                app_secret=app_secret,
                env=env_for_admin,
                allow_env_fallback=not is_customer,
            )
            if telegram.bot_token and telegram.chat_id:
                # Musteri bot token + chat ID kaydettiyse bildirimler acik sayilir.
                enabled = telegram.enabled or is_customer
                return TelegramConfig(
                    enabled=enabled,
                    bot_token=telegram.bot_token,
                    chat_id=telegram.chat_id,
                )
            return None

    telegram = profile_telegram_credentials(
        None,
        encryption_key=encryption_key,
        app_secret=app_secret,
        env=env,
        allow_env_fallback=True,
    )
    if telegram.bot_token and telegram.chat_id:
        return TelegramConfig(
            enabled=telegram.enabled,
            bot_token=telegram.bot_token,
            chat_id=telegram.chat_id,
        )
    return TelegramConfig.from_env()


def profile_openai_credentials(
    profile: AdminProfile | None,
    *,
    encryption_key: str,
    app_secret: str,
    env: EnvironmentCredentials | None = None,
) -> ResolvedOpenAiCredentials | None:
    if profile is not None:
        key = _decrypt_field(profile.openai_api_key_enc, encryption_key=encryption_key, app_secret=app_secret)
        if key:
            return ResolvedOpenAiCredentials(api_key=key, source="profile")
    return _env_openai_credentials(env)


def mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    return mask_value(value)
