"""Telegram bildirim mesaj formatlari."""

from datetime import datetime, timezone
from decimal import Decimal

from shared.telegram_notifier import (
    TelegramConfig,
    format_position_closed_message,
    format_position_opened_message,
)


def test_format_position_opened_message():
    text = format_position_opened_message(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=Decimal("95000"),
        quantity=Decimal("0.005"),
        margin_usdt=Decimal("5"),
        leverage=7,
        stop_loss_price=Decimal("94000"),
        take_profit_price=Decimal("96500"),
        bot_mode="live",
        open_reason="SIGNAL",
    )
    assert "POZISYON ACILDI" in text
    assert "BTCUSDT" in text
    assert "LONG" in text
    assert "$95,000.00" in text


def test_format_position_closed_handles_naive_opened_at():
    text = format_position_closed_message(
        symbol="ETHUSDT",
        side="LONG",
        entry_price=Decimal("3000"),
        exit_price=Decimal("3100"),
        net_pnl_usdt=Decimal("1.15"),
        net_roi_pct=Decimal("23"),
        close_reason="TAKE_PROFIT",
        bot_mode="live",
        opened_at=datetime(2026, 1, 1, 10, 0),
        closed_at=datetime(2026, 1, 1, 12, 15, tzinfo=timezone.utc),
    )
    assert "KAR" in text
    assert "2 sa" in text


def test_format_position_closed_profit():
    text = format_position_closed_message(
        symbol="ETHUSDT",
        side="LONG",
        entry_price=Decimal("3000"),
        exit_price=Decimal("3100"),
        net_pnl_usdt=Decimal("1.15"),
        net_roi_pct=Decimal("23"),
        close_reason="TAKE_PROFIT",
        bot_mode="live",
        opened_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        closed_at=datetime(2026, 1, 1, 12, 15, tzinfo=timezone.utc),
    )
    assert "KAR" in text
    assert "+1.15 USDT" in text
    assert "Kar Al" in text


def test_format_position_closed_loss():
    text = format_position_closed_message(
        symbol="SOLUSDT",
        side="SHORT",
        entry_price=Decimal("150"),
        exit_price=Decimal("155"),
        net_pnl_usdt=Decimal("-0.85"),
        net_roi_pct=Decimal("-17"),
        close_reason="STOP_LOSS",
        bot_mode="live",
    )
    assert "ZARAR" in text
    assert "-0.85 USDT" in text


def test_telegram_config_from_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_NOTIFICATIONS_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999")
    cfg = TelegramConfig.from_env()
    assert cfg.is_ready is True

    monkeypatch.setenv("TELEGRAM_NOTIFICATIONS_ENABLED", "false")
    cfg = TelegramConfig.from_env()
    assert cfg.is_ready is False


def test_telegram_config_reads_env_file(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_NOTIFICATIONS_ENABLED", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_NOTIFICATIONS_ENABLED=true\n"
        "TELEGRAM_BOT_TOKEN=456:xyz\n"
        "TELEGRAM_CHAT_ID=111\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cfg = TelegramConfig.from_env()
    assert cfg.is_ready is True
    assert cfg.chat_id == "111"
