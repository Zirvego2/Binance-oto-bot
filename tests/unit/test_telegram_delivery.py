"""Telegram bildirim deduplication mantigi."""

from datetime import datetime, timezone

from shared import telegram_delivery as td
from shared.db import TelegramDeliveryLog
from shared.telegram_delivery import _is_duplicate_delivery


class _FakeSession:
    """format_*_message fonksiyonlarina position_id sizmasini test etmek icin
    gercek DB gerektirmeyen minimal sahte oturum."""

    def __init__(self) -> None:
        self.added: list[TelegramDeliveryLog] = []

    def add(self, obj: TelegramDeliveryLog) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass


def _log(message_type: str, symbol: str, *, position_id: str | None = None) -> TelegramDeliveryLog:
    details = {"position_id": position_id} if position_id else None
    return TelegramDeliveryLog(
        id="log-1",
        admin_id="admin-1",
        message_type=message_type,
        status="sent",
        symbol=symbol,
        details=details,
        created_at=datetime.now(timezone.utc),
    )


def test_duplicate_by_position_id():
    recent = [_log("position_closed", "BTCUSDT", position_id="pos-1")]
    assert _is_duplicate_delivery(
        recent,
        message_type="position_closed",
        symbol="BTCUSDT",
        details={"position_id": "pos-1"},
    )


def test_not_duplicate_different_position_same_symbol_with_position_id():
    recent = [_log("position_closed", "BTCUSDT", position_id="pos-1")]
    assert not _is_duplicate_delivery(
        recent,
        message_type="position_closed",
        symbol="BTCUSDT",
        details={"position_id": "pos-2"},
    )


def test_duplicate_by_symbol_when_position_id_missing():
    recent = [_log("position_opened", "ETHUSDT")]
    assert _is_duplicate_delivery(
        recent,
        message_type="position_opened",
        symbol="ETHUSDT",
        details=None,
    )


def test_test_messages_not_deduplicated():
    recent = [_log("test", "BTCUSDT")]
    assert not _is_duplicate_delivery(
        recent,
        message_type="test",
        symbol="BTCUSDT",
        details=None,
    )


async def test_deliver_position_opened_notification_does_not_leak_position_id_to_formatter(monkeypatch):
    """Regresyon: position_id, format_position_opened_message'a TypeError firlatmadan iletilmemeli."""

    async def _fake_resolve(*_args, **_kwargs):
        return None, td.SKIP_NO_CONFIG

    monkeypatch.setattr(td, "_resolve_customer_config", _fake_resolve)

    session = _FakeSession()
    status = await td.deliver_position_opened_notification(
        session,
        settings=object(),
        admin_id="admin-1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=100,
        quantity=1,
        margin_usdt=10,
        leverage=5,
        bot_mode="live",
        position_id="pos-123",
    )
    assert status == td.STATUS_SKIPPED
    assert session.added[0].details.get("position_id") == "pos-123"


async def test_deliver_position_closed_notification_does_not_leak_position_id_to_formatter(monkeypatch):
    """Regresyon: position_id, format_position_closed_message'a TypeError firlatmadan iletilmemeli."""

    async def _fake_resolve(*_args, **_kwargs):
        return None, td.SKIP_NO_CONFIG

    monkeypatch.setattr(td, "_resolve_customer_config", _fake_resolve)

    session = _FakeSession()
    status = await td.deliver_position_closed_notification(
        session,
        settings=object(),
        admin_id="admin-1",
        symbol="BTCUSDT",
        side="LONG",
        entry_price=100,
        exit_price=110,
        net_pnl_usdt=10,
        net_roi_pct=10,
        close_reason="TAKE_PROFIT",
        bot_mode="live",
        position_id="pos-123",
    )
    assert status == td.STATUS_SKIPPED
    assert session.added[0].details.get("position_id") == "pos-123"
