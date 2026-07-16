"""Telegram getUpdates ile chat ID kesfi."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

DEFAULT_TIMEOUT_SEC = 12.0


@dataclass(frozen=True, slots=True)
class TelegramChatDiscoveryResult:
    ok: bool
    chat_id: str | None
    message: str


def _chat_from_update(update: dict) -> dict | None:
    for key in ("message", "edited_message", "channel_post", "my_chat_member", "chat_member"):
        payload = update.get(key)
        if isinstance(payload, dict) and isinstance(payload.get("chat"), dict):
            return payload["chat"]
    return None


async def discover_telegram_chat_id(bot_token: str) -> TelegramChatDiscoveryResult:
    token = bot_token.strip()
    if not token:
        return TelegramChatDiscoveryResult(False, None, "Bot token bos.")

    base = f"https://api.telegram.org/bot{token}"
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SEC) as client:
            await client.post(f"{base}/deleteWebhook")
            response = await client.get(f"{base}/getUpdates", params={"limit": 25})
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        return TelegramChatDiscoveryResult(False, None, f"Telegram API ulasilamadi: {exc}")
    except Exception as exc:  # noqa: BLE001
        return TelegramChatDiscoveryResult(False, None, f"Telegram istegi basarisiz: {exc}")

    if not payload.get("ok"):
        description = str(payload.get("description") or "Telegram API hatasi")
        return TelegramChatDiscoveryResult(False, None, description)

    updates = payload.get("result") or []
    if not updates:
        return TelegramChatDiscoveryResult(
            False,
            None,
            "Bot henuz mesaj almamis. Telegram'da bota /start yazin, sonra tekrar deneyin.",
        )

    for update in reversed(updates):
        chat = _chat_from_update(update)
        if chat is None:
            continue
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        chat_type = str(chat.get("type") or "unknown")
        label = chat.get("title") or chat.get("first_name") or chat.get("username") or ""
        suffix = f" ({label})" if label else ""
        return TelegramChatDiscoveryResult(
            True,
            str(chat_id),
            f"Chat ID bulundu: {chat_type}{suffix}",
        )

    return TelegramChatDiscoveryResult(False, None, "Guncelleme var ama chat ID okunamadi.")
