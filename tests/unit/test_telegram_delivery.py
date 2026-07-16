"""Telegram bildirim deduplication mantigi."""

from datetime import datetime, timezone

from shared.db import TelegramDeliveryLog
from shared.telegram_delivery import _is_duplicate_delivery


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


def test_not_duplicate_different_position_same_symbol():
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
