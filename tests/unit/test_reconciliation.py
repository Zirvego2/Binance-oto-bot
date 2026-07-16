from decimal import Decimal

from shared.binance.types import ExchangeOrder, ExchangePosition
from shared.reconciliation import LocalPositionSnapshot, reconcile


def _exchange_position(symbol="BTCUSDT", qty=Decimal("1"), entry=Decimal("100")) -> ExchangePosition:
    return ExchangePosition(
        symbol=symbol,
        position_side="BOTH",
        quantity=qty,
        entry_price=entry,
        mark_price=entry,
        unrealized_pnl=Decimal("0"),
        leverage=5,
        margin_type="ISOLATED",
        liquidation_price=Decimal("80"),
        isolated_margin=Decimal("20"),
    )


def _algo_order(symbol, order_type, side) -> ExchangeOrder:
    return ExchangeOrder(
        symbol=symbol,
        binance_order_id="1",
        client_order_id="algo1",
        side=side,
        order_type=order_type,
        status="NEW",
        price=Decimal("0"),
        orig_qty=Decimal("0"),
        executed_qty=Decimal("0"),
        avg_price=Decimal("0"),
        reduce_only=True,
        close_position=True,
        stop_price=Decimal("95"),
        working_type="MARK_PRICE",
        time_ms=0,
    )


def test_reconciliation_matches_when_consistent():
    exchange_positions = [_exchange_position()]
    local_positions = [
        LocalPositionSnapshot("pos1", "BTCUSDT", "LONG", Decimal("1"), Decimal("100"), True, True)
    ]
    algo_orders = [_algo_order("BTCUSDT", "STOP_MARKET", "SELL"), _algo_order("BTCUSDT", "TAKE_PROFIT_MARKET", "SELL")]

    report = reconcile(exchange_positions, local_positions, algo_orders)
    assert report.is_consistent is True
    assert report.external_positions == []
    assert report.missing_on_exchange == []


def test_reconciliation_detects_external_position():
    exchange_positions = [_exchange_position(symbol="ETHUSDT")]
    report = reconcile(exchange_positions, [], [])
    assert report.is_consistent is False
    assert "ETHUSDT" in report.external_positions


def test_reconciliation_detects_missing_on_exchange():
    local_positions = [
        LocalPositionSnapshot("pos1", "BTCUSDT", "LONG", Decimal("1"), Decimal("100"), True, True)
    ]
    report = reconcile([], local_positions, [])
    assert report.is_consistent is False
    assert "BTCUSDT" in report.missing_on_exchange


def test_reconciliation_detects_quantity_mismatch():
    exchange_positions = [_exchange_position(qty=Decimal("2"))]
    local_positions = [
        LocalPositionSnapshot("pos1", "BTCUSDT", "LONG", Decimal("1"), Decimal("100"), True, True)
    ]
    report = reconcile(exchange_positions, local_positions, [])
    assert report.is_consistent is False
    assert any(m.mismatch_type == "QUANTITY_MISMATCH" for m in report.mismatches)


def test_reconciliation_detects_missing_protective_orders():
    exchange_positions = [_exchange_position()]
    local_positions = [
        LocalPositionSnapshot("pos1", "BTCUSDT", "LONG", Decimal("1"), Decimal("100"), True, True)
    ]
    report = reconcile(exchange_positions, local_positions, [])  # algo emirleri bos
    assert report.is_consistent is False
    assert "BTCUSDT" in report.positions_missing_protection


def test_reconciliation_detects_side_mismatch():
    exchange_positions = [_exchange_position(qty=Decimal("-1"))]  # SHORT
    local_positions = [
        LocalPositionSnapshot("pos1", "BTCUSDT", "LONG", Decimal("1"), Decimal("100"), True, True)
    ]
    report = reconcile(exchange_positions, local_positions, [])
    assert any(m.mismatch_type == "SIDE_MISMATCH" for m in report.mismatches)
