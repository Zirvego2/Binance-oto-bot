from decimal import Decimal

from shared.binance.live_adapter import _normalize_algo_status, _to_algo_exchange_order


def test_normalize_algo_status_maps_triggered_to_filled() -> None:
    assert _normalize_algo_status("TRIGGERED") == "FILLED"
    assert _normalize_algo_status("FINISHED") == "FILLED"
    assert _normalize_algo_status("NEW") == "NEW"
    assert _normalize_algo_status("CANCELED") == "CANCELED"


def test_to_algo_exchange_order_parses_trigger_price() -> None:
    order = _to_algo_exchange_order(
        {
            "algoId": 2146760,
            "clientAlgoId": "algo_sl_test123",
            "algoType": "CONDITIONAL",
            "orderType": "STOP_MARKET",
            "symbol": "XRPUSDT",
            "side": "BUY",
            "positionSide": "BOTH",
            "algoStatus": "NEW",
            "triggerPrice": "1.1050000",
            "closePosition": "true",
            "updateTime": 1750485492076,
        }
    )
    assert order.binance_order_id == "2146760"
    assert order.client_order_id == "algo_sl_test123"
    assert order.order_type == "STOP_MARKET"
    assert order.status == "NEW"
    assert order.stop_price == Decimal("1.1050000")
    assert order.close_position is True
