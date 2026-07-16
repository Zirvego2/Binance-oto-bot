"""Telegram Bot API ile islem bildirimleri (pozisyon acilis / kapanis / K-Z)."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"
DEFAULT_TIMEOUT_SEC = 10.0
TELEGRAM_MAX_ATTEMPTS = 3
TELEGRAM_RETRY_DELAYS_SEC = (0.5, 1.5, 3.0)

_ENV_FILE_KEYS = (
    "TELEGRAM_NOTIFICATIONS_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return values
    except OSError:
        return values
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key not in _ENV_FILE_KEYS:
            continue
        value = value.strip().strip('"').strip("'")
        values[key] = value
    return values


def _env_file_candidates() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    cwd = Path.cwd()
    return [
        cwd / ".env",
        cwd.parent.parent / ".env",
        repo_root / ".env",
    ]


def _load_telegram_env() -> dict[str, str]:
    """Ortam degiskeni + proje .env dosyasini birlestirir (ilk bulunan .env)."""
    file_values: dict[str, str] = {}
    seen: set[Path] = set()
    for candidate in _env_file_candidates():
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if not resolved.is_file():
            continue
        file_values = _parse_env_file(resolved)
        break

    merged = dict(file_values)
    for key in _ENV_FILE_KEYS:
        env_val = os.getenv(key)
        if env_val is not None and env_val.strip():
            merged[key] = env_val.strip()
    return merged


def _env_get(values: dict[str, str], key: str, default: str = "") -> str:
    return values.get(key, default).strip()


@dataclass(frozen=True, slots=True)
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str

    @classmethod
    def from_env(cls) -> TelegramConfig:
        env = _load_telegram_env()
        enabled_raw = _env_get(env, "TELEGRAM_NOTIFICATIONS_ENABLED", "false").lower()
        return cls(
            enabled=enabled_raw in ("1", "true", "yes", "on"),
            bot_token=_env_get(env, "TELEGRAM_BOT_TOKEN"),
            chat_id=_env_get(env, "TELEGRAM_CHAT_ID"),
        )

    @property
    def is_ready(self) -> bool:
        return self.enabled and bool(self.bot_token) and bool(self.chat_id)


CLOSE_REASON_LABELS = {
    "TAKE_PROFIT": "Kar Al (TP)",
    "STOP_LOSS": "Zarar Durdur (SL)",
    "TRAILING_STOP": "Trailing Stop",
    "MANUAL": "Manuel Kapatma",
    "EMERGENCY_STOP": "Acil Kapatma",
    "LIQUIDATION": "Likidasyon",
    "RECONCILIATION": "Mutabakat",
    "UNKNOWN": "Bilinmiyor",
}


def _d(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _fmt_price(value: Decimal | float) -> str:
    num = float(value)
    if num >= 1000:
        return f"${num:,.2f}"
    if num >= 1:
        return f"${num:.4f}"
    return f"${num:.6f}"


def _fmt_usdt(value: Decimal | float) -> str:
    num = float(value)
    sign = "+" if num >= 0 else ""
    return f"{sign}{num:.2f} USDT"


def _fmt_pct(value: Decimal | float) -> str:
    num = float(value)
    sign = "+" if num >= 0 else ""
    return f"{sign}{num:.2f}%"


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_duration(opened_at: datetime | None, closed_at: datetime | None) -> str:
    start = _ensure_utc(opened_at)
    end = _ensure_utc(closed_at)
    if start is None or end is None:
        return "-"
    total_sec = max(0, int((end - start).total_seconds()))
    hours, rem = divmod(total_sec, 3600)
    mins, secs = divmod(rem, 60)
    if hours:
        return f"{hours} sa {mins} dk"
    if mins:
        return f"{mins} dk {secs} sn"
    return f"{secs} sn"


def format_position_opened_message(
    *,
    symbol: str,
    side: str,
    entry_price: Decimal | float,
    quantity: Decimal | float,
    margin_usdt: Decimal | float,
    leverage: int,
    stop_loss_price: Decimal | float | None = None,
    take_profit_price: Decimal | float | None = None,
    bot_mode: str,
    open_reason: str | None = None,
) -> str:
    side_label = "LONG (Alis)" if side.upper() == "LONG" else "SHORT (Satis)"
    lines = [
        "🟢 POZISYON ACILDI",
        "",
        f"Sembol: {symbol}",
        f"Yon: {side_label}",
        f"Giris: {_fmt_price(_d(entry_price))}",
        f"Miktar: {_d(quantity)}",
        f"Marjin: {_d(margin_usdt):.2f} USDT",
        f"Kaldirac: {leverage}x",
    ]
    if stop_loss_price is not None:
        lines.append(f"Stop Loss: {_fmt_price(_d(stop_loss_price))}")
    if take_profit_price is not None:
        lines.append(f"Take Profit: {_fmt_price(_d(take_profit_price))}")
    if open_reason:
        lines.append(f"Sebep: {open_reason}")
    lines.append(f"Mod: {bot_mode}")
    return "\n".join(lines)


def format_position_closed_message(
    *,
    symbol: str,
    side: str,
    entry_price: Decimal | float,
    exit_price: Decimal | float,
    net_pnl_usdt: Decimal | float,
    net_roi_pct: Decimal | float,
    close_reason: str,
    bot_mode: str,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
) -> str:
    pnl = _d(net_pnl_usdt)
    is_profit = pnl >= 0
    header = "✅ POZISYON KAPANDI — KAR" if is_profit else "❌ POZISYON KAPANDI — ZARAR"
    side_label = "LONG" if side.upper() == "LONG" else "SHORT"
    reason_label = CLOSE_REASON_LABELS.get(close_reason.upper(), close_reason)

    lines = [
        header,
        "",
        f"Sembol: {symbol}",
        f"Yon: {side_label}",
        f"Giris: {_fmt_price(_d(entry_price))} → Cikis: {_fmt_price(_d(exit_price))}",
        f"Net K/Z: {_fmt_usdt(pnl)} ({_fmt_pct(net_roi_pct)} ROI)",
        f"Sebep: {reason_label}",
        f"Sure: {_fmt_duration(opened_at, closed_at)}",
        f"Mod: {bot_mode}",
    ]
    return "\n".join(lines)


async def send_telegram_message(config: TelegramConfig, text: str) -> dict[str, Any]:
    if not config.is_ready:
        raise ValueError("telegram_not_configured")

    url = TELEGRAM_API_BASE.format(token=config.bot_token)
    payload = {
        "chat_id": config.chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }

    last_exc: Exception | None = None
    for attempt in range(TELEGRAM_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SEC) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                if not data.get("ok"):
                    raise RuntimeError(data.get("description", "telegram_send_failed"))
                return data
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code >= 500 and attempt < TELEGRAM_MAX_ATTEMPTS - 1:
                await asyncio.sleep(TELEGRAM_RETRY_DELAYS_SEC[attempt])
                continue
            raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            if attempt < TELEGRAM_MAX_ATTEMPTS - 1:
                logger.warning(
                    "Telegram gonderimi basarisiz (deneme %s/%s): %s",
                    attempt + 1,
                    TELEGRAM_MAX_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(TELEGRAM_RETRY_DELAYS_SEC[attempt])
                continue
            raise

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("telegram_send_failed")


async def send_test_notification(config: TelegramConfig | None = None) -> None:
    cfg = config or TelegramConfig.from_env()
    await send_telegram_message(
        cfg,
        "🔔 Binance Futures Bot\n\nTelegram bildirimleri basariyla baglandi.\nIslem acilis/kapanis mesajlari bu kanala gelecek.",
    )


async def notify_position_opened(
    *,
    symbol: str,
    side: str,
    entry_price: Decimal | float,
    quantity: Decimal | float,
    margin_usdt: Decimal | float,
    leverage: int,
    stop_loss_price: Decimal | float | None = None,
    take_profit_price: Decimal | float | None = None,
    bot_mode: str,
    open_reason: str | None = None,
    config: TelegramConfig | None = None,
) -> None:
    if config is None or not config.bot_token or not config.chat_id or not config.enabled:
        return
    text = format_position_opened_message(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        quantity=quantity,
        margin_usdt=margin_usdt,
        leverage=leverage,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        bot_mode=bot_mode,
        open_reason=open_reason,
    )
    await send_telegram_message(config, text)


async def notify_position_closed(
    *,
    symbol: str,
    side: str,
    entry_price: Decimal | float,
    exit_price: Decimal | float,
    net_pnl_usdt: Decimal | float,
    net_roi_pct: Decimal | float,
    close_reason: str,
    bot_mode: str,
    opened_at: datetime | None = None,
    closed_at: datetime | None = None,
    config: TelegramConfig | None = None,
) -> None:
    if config is None or not config.bot_token or not config.chat_id or not config.enabled:
        return
    text = format_position_closed_message(
        symbol=symbol,
        side=side,
        entry_price=entry_price,
        exit_price=exit_price,
        net_pnl_usdt=net_pnl_usdt,
        net_roi_pct=net_roi_pct,
        close_reason=close_reason,
        bot_mode=bot_mode,
        opened_at=opened_at,
        closed_at=closed_at,
    )
    await send_telegram_message(config, text)


async def _run_safe(coro) -> None:
    try:
        await coro
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram bildirimi gonderilemedi: %s", exc)


def schedule_telegram_notification(coro) -> None:
    """Islem akisini bloklamadan arka planda Telegram gonder."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_run_safe(coro))
