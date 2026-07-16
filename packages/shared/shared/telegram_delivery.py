"""Musteri bazli Telegram bildirim gonderimi + veritabani loglama."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .customer_credentials import environment_credentials_from_settings, resolve_telegram_config_for_admin
from .db import TelegramDeliveryLog
from .masking import mask_value
from .telegram_notifier import TelegramConfig, send_telegram_message

logger = logging.getLogger(__name__)

STATUS_SENT = "sent"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"

SKIP_NO_ADMIN = "no_admin_id"
SKIP_NO_CONFIG = "no_telegram_config"
SKIP_NO_BOT_TOKEN = "no_bot_token"
SKIP_NO_CHAT_ID = "no_chat_id"
SKIP_DISABLED = "notifications_disabled"
SKIP_DUPLICATE = "duplicate_recent"

DEDUP_WINDOW_SECONDS = 120
POSITION_MESSAGE_TYPES = frozenset({"position_opened", "position_closed"})

SKIP_REASON_MESSAGES = {
    SKIP_NO_ADMIN: "Musteri kimligi bulunamadi.",
    SKIP_NO_CONFIG: "Telegram yapilandirilmamis. Profilden bot token ve chat ID girin.",
    SKIP_NO_BOT_TOKEN: "Telegram bot token kayitli degil.",
    SKIP_NO_CHAT_ID: "Telegram chat ID kayitli degil.",
    SKIP_DISABLED: "Telegram bildirimleri kapali. Profilden acin.",
    SKIP_DUPLICATE: "Ayni bildirim kisa sure once gonderildi.",
    "telegram_api_error": "Telegram API hatasi. Bot token ve chat ID dogrulayin.",
}


def _is_duplicate_delivery(
    recent_logs: list[TelegramDeliveryLog],
    *,
    message_type: str,
    symbol: str | None,
    details: dict[str, Any] | None,
) -> bool:
    """Ayni pozisyon/sembol icin kisa pencerede tekrar gonderimi tespit eder."""

    if message_type not in POSITION_MESSAGE_TYPES:
        return False

    position_id = str((details or {}).get("position_id") or "").strip()
    for entry in recent_logs:
        if entry.message_type != message_type:
            continue
        entry_details = entry.details or {}
        entry_position_id = str(entry_details.get("position_id") or "").strip()
        if position_id and entry_position_id:
            if position_id == entry_position_id:
                return True
            continue
        if symbol and entry.symbol == symbol:
            return True
    return False


async def _find_recent_sent_logs(
    session: AsyncSession,
    *,
    admin_id: str,
    message_type: str,
    symbol: str | None,
) -> list[TelegramDeliveryLog]:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=DEDUP_WINDOW_SECONDS)
    query = (
        select(TelegramDeliveryLog)
        .where(
            TelegramDeliveryLog.admin_id == admin_id,
            TelegramDeliveryLog.message_type == message_type,
            TelegramDeliveryLog.status == STATUS_SENT,
            TelegramDeliveryLog.created_at >= cutoff,
        )
        .order_by(TelegramDeliveryLog.created_at.desc())
        .limit(20)
    )
    if symbol:
        query = query.where(TelegramDeliveryLog.symbol == symbol)
    return list((await session.execute(query)).scalars().all())


def mask_bot_id(token: str | None) -> str | None:
    if not token:
        return None
    if ":" in token:
        return token.split(":", 1)[0]
    return mask_value(token)


def mask_chat_id(chat_id: str | None) -> str | None:
    if not chat_id:
        return None
    return mask_value(str(chat_id))


async def record_telegram_delivery(
    session: AsyncSession,
    *,
    admin_id: str | None,
    message_type: str,
    status: str,
    skip_reason: str | None = None,
    symbol: str | None = None,
    chat_id: str | None = None,
    bot_token: str | None = None,
    error_message: str | None = None,
    source: str = "worker",
    details: dict[str, Any] | None = None,
) -> None:
    entry = TelegramDeliveryLog(
        admin_id=admin_id,
        message_type=message_type,
        status=status,
        skip_reason=skip_reason,
        symbol=symbol,
        chat_id_masked=mask_chat_id(chat_id),
        bot_id_masked=mask_bot_id(bot_token),
        error_message=(error_message or "")[:512] or None,
        source=source,
        details=details,
    )
    session.add(entry)
    try:
        await session.flush()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram log kaydi yazilamadi (admin=%s): %s", admin_id, exc)

    log_msg = (
        f"Telegram {message_type} admin={admin_id} status={status}"
        f"{f' reason={skip_reason}' if skip_reason else ''}"
        f"{f' symbol={symbol}' if symbol else ''}"
        f"{f' bot={entry.bot_id_masked}' if entry.bot_id_masked else ''}"
        f"{f' chat={entry.chat_id_masked}' if entry.chat_id_masked else ''}"
        f"{f' err={error_message}' if error_message else ''}"
    )
    if status == STATUS_SENT:
        logger.info(log_msg)
    elif status == STATUS_SKIPPED:
        logger.warning(log_msg)
    else:
        logger.error(log_msg)


async def _resolve_customer_config(session: AsyncSession, settings, admin_id: str | None) -> tuple[TelegramConfig | None, str | None]:
    if not admin_id:
        return None, SKIP_NO_ADMIN

    env = environment_credentials_from_settings(settings)
    cfg = await resolve_telegram_config_for_admin(
        session,
        admin_id,
        encryption_key=settings.app_encryption_key,
        app_secret=settings.app_secret,
        env=env,
    )
    if cfg is None:
        return None, SKIP_NO_CONFIG
    if not cfg.bot_token:
        return cfg, SKIP_NO_BOT_TOKEN
    if not cfg.chat_id:
        return cfg, SKIP_NO_CHAT_ID
    if not cfg.enabled:
        return cfg, SKIP_DISABLED
    return cfg, None


async def deliver_telegram_message(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    *,
    message_type: str,
    text: str,
    source: str = "worker",
    symbol: str | None = None,
    details: dict[str, Any] | None = None,
) -> tuple[str, str | None, str | None]:
    """Donus: (status, skip_reason, error_message)"""

    cfg, skip_reason = await _resolve_customer_config(session, settings, admin_id)
    if skip_reason:
        await record_telegram_delivery(
            session,
            admin_id=admin_id,
            message_type=message_type,
            status=STATUS_SKIPPED,
            skip_reason=skip_reason,
            symbol=symbol,
            chat_id=cfg.chat_id if cfg else None,
            bot_token=cfg.bot_token if cfg else None,
            source=source,
            details=details,
        )
        return STATUS_SKIPPED, skip_reason, None

    assert cfg is not None

    if admin_id and message_type in POSITION_MESSAGE_TYPES:
        recent_logs = await _find_recent_sent_logs(
            session,
            admin_id=admin_id,
            message_type=message_type,
            symbol=symbol,
        )
        if _is_duplicate_delivery(
            recent_logs,
            message_type=message_type,
            symbol=symbol,
            details=details,
        ):
            await record_telegram_delivery(
                session,
                admin_id=admin_id,
                message_type=message_type,
                status=STATUS_SKIPPED,
                skip_reason=SKIP_DUPLICATE,
                symbol=symbol,
                chat_id=cfg.chat_id,
                bot_token=cfg.bot_token,
                source=source,
                details=details,
            )
            return STATUS_SKIPPED, SKIP_DUPLICATE, None

    try:
        await send_telegram_message(cfg, text)
    except Exception as exc:  # noqa: BLE001
        err = str(exc) or repr(exc)
        await record_telegram_delivery(
            session,
            admin_id=admin_id,
            message_type=message_type,
            status=STATUS_FAILED,
            skip_reason="telegram_api_error",
            symbol=symbol,
            chat_id=cfg.chat_id,
            bot_token=cfg.bot_token,
            error_message=err,
            source=source,
            details=details,
        )
        return STATUS_FAILED, "telegram_api_error", err

    await record_telegram_delivery(
        session,
        admin_id=admin_id,
        message_type=message_type,
        status=STATUS_SENT,
        symbol=symbol,
        chat_id=cfg.chat_id,
        bot_token=cfg.bot_token,
        source=source,
        details=details,
    )
    return STATUS_SENT, None, None


async def deliver_position_opened_notification(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    *,
    source: str = "worker",
    **fields,
) -> str:
    from .telegram_notifier import format_position_opened_message

    symbol = fields.get("symbol")
    text = format_position_opened_message(**fields)
    details = {k: str(v) for k, v in fields.items() if v is not None}
    status, _, _ = await deliver_telegram_message(
        session,
        settings,
        admin_id,
        message_type="position_opened",
        text=text,
        source=source,
        symbol=symbol,
        details=details,
    )
    return status


async def deliver_position_closed_notification(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    *,
    source: str = "worker",
    **fields,
) -> str:
    from .telegram_notifier import format_position_closed_message

    symbol = fields.get("symbol")
    text = format_position_closed_message(**fields)
    details = {
        k: (v.isoformat() if hasattr(v, "isoformat") else str(v))
        for k, v in fields.items()
        if v is not None
    }
    status, _, _ = await deliver_telegram_message(
        session,
        settings,
        admin_id,
        message_type="position_closed",
        text=text,
        source=source,
        symbol=symbol,
        details=details,
    )
    return status


async def deliver_test_notification(
    session: AsyncSession,
    settings,
    admin_id: str | None,
    *,
    source: str = "api",
) -> tuple[bool, str]:
    text = (
        "🔔 Binance Futures Bot\n\n"
        "Telegram bildirimleri basariyla baglandi.\n"
        "Islem acilis/kapanis mesajlari bu kanala gelecek."
    )
    status, skip_reason, error_message = await deliver_telegram_message(
        session,
        settings,
        admin_id,
        message_type="test",
        text=text,
        source=source,
    )
    if status == STATUS_SENT:
        return True, "Test mesaji kendi Telegram botunuza gonderildi."
    if status == STATUS_SKIPPED:
        return False, SKIP_REASON_MESSAGES.get(skip_reason or SKIP_NO_CONFIG, "Telegram yapilandirilmamis.")
    return False, error_message or SKIP_REASON_MESSAGES.get("telegram_api_error", "Telegram gonderimi basarisiz.")
