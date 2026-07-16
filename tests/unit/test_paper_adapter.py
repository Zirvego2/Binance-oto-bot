"""PAPER adapter testleri: gercek Binance emri gonderilmez, tum durum bellek icinde simule edilir."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from shared.binance.paper_adapter import PaperFuturesAdapter
from shared.binance.types import MarkPriceTick, PlaceAlgoOrderRequest, PlaceOrderRequest


def make_adapter() -> PaperFuturesAdapter:
    adapter = PaperFuturesAdapter(
        market_base_url="https://fapi.binance.com",
        starting_balance_usdt=Decimal("100"),
        taker_commission_rate=Decimal("0.0004"),
    )
    return adapter


def mock_price(adapter: PaperFuturesAdapter, price: Decimal) -> None:
    adapter.get_mark_price = AsyncMock(  # type: ignore[method-assign]
        return_value=MarkPriceTick(
            symbol="BTCUSDT",
            mark_price=price,
            index_price=price,
            funding_rate=Decimal("0.0001"),
            next_funding_time_ms=0,
            time_ms=0,
        )
    )


@pytest.mark.asyncio
async def test_paper_long_open_and_close():
    adapter = make_adapter()
    await adapter.change_leverage("BTCUSDT", 5)
    mock_price(adapter, Decimal("100"))

    order = await adapter.place_market_order(
        PlaceOrderRequest(symbol="BTCUSDT", side="BUY", quantity=Decimal("1"), client_order_id="open1")
    )
    assert order.status == "FILLED"

    positions = await adapter.get_open_positions()
    assert len(positions) == 1
    assert positions[0].quantity == Decimal("1")
    assert positions[0].entry_price == Decimal("100")

    mock_price(adapter, Decimal("110"))
    close_order = await adapter.place_reduce_only_market_order(
        PlaceOrderRequest(symbol="BTCUSDT", side="SELL", quantity=Decimal("1"), client_order_id="close1")
    )
    assert close_order.status == "FILLED"

    positions_after = await adapter.get_open_positions()
    assert len(positions_after) == 0

    balance = await adapter.get_account_balance()
    # 100 USDT baslangic + (110-100)*1 kar - komisyonlar
    assert balance[0].wallet_balance > Decimal("100")


@pytest.mark.asyncio
async def test_paper_short_open_and_close():
    adapter = make_adapter()
    await adapter.change_leverage("ETHUSDT", 3)
    mock_price(adapter, Decimal("2000"))

    await adapter.place_market_order(
        PlaceOrderRequest(symbol="ETHUSDT", side="SELL", quantity=Decimal("1"), client_order_id="open_short")
    )
    positions = await adapter.get_open_positions()
    assert positions[0].quantity == Decimal("-1")

    mock_price(adapter, Decimal("1900"))
    await adapter.place_reduce_only_market_order(
        PlaceOrderRequest(symbol="ETHUSDT", side="BUY", quantity=Decimal("1"), client_order_id="close_short")
    )
    positions_after = await adapter.get_open_positions()
    assert len(positions_after) == 0

    balance = await adapter.get_account_balance()
    # fiyat dustugu icin SHORT kar etmeli: 100 baslangictan fazla olmali
    assert balance[0].wallet_balance > Decimal("100")


@pytest.mark.asyncio
async def test_paper_stop_loss_triggers_and_closes_position():
    adapter = make_adapter()
    await adapter.change_leverage("BTCUSDT", 5)
    mock_price(adapter, Decimal("100"))

    await adapter.place_market_order(
        PlaceOrderRequest(symbol="BTCUSDT", side="BUY", quantity=Decimal("1"), client_order_id="open2")
    )
    await adapter.place_stop_loss_order(
        PlaceAlgoOrderRequest(
            symbol="BTCUSDT", side="SELL", order_type="STOP_MARKET", stop_price=Decimal("95"), client_algo_id="sl1"
        )
    )

    triggered = await adapter.on_mark_price_update("BTCUSDT", Decimal("94"))
    assert len(triggered) == 1
    assert triggered[0].status == "FILLED"

    positions = await adapter.get_open_positions()
    assert len(positions) == 0


@pytest.mark.asyncio
async def test_paper_take_profit_triggers_for_short():
    adapter = make_adapter()
    await adapter.change_leverage("BTCUSDT", 5)
    mock_price(adapter, Decimal("100"))

    await adapter.place_market_order(
        PlaceOrderRequest(symbol="BTCUSDT", side="SELL", quantity=Decimal("1"), client_order_id="open3")
    )
    await adapter.place_take_profit_order(
        PlaceAlgoOrderRequest(
            symbol="BTCUSDT", side="BUY", order_type="TAKE_PROFIT_MARKET", stop_price=Decimal("90"), client_algo_id="tp1"
        )
    )

    triggered = await adapter.on_mark_price_update("BTCUSDT", Decimal("89"))
    assert len(triggered) == 1
    positions = await adapter.get_open_positions()
    assert len(positions) == 0


@pytest.mark.asyncio
async def test_paper_cancel_algo_order():
    adapter = make_adapter()
    await adapter.place_stop_loss_order(
        PlaceAlgoOrderRequest(
            symbol="BTCUSDT", side="SELL", order_type="STOP_MARKET", stop_price=Decimal("95"), client_algo_id="sl2"
        )
    )
    result = await adapter.cancel_algo_order("BTCUSDT", "sl2")
    assert result is True
    open_algo = await adapter.get_open_algo_orders("BTCUSDT")
    assert open_algo == []


@pytest.mark.asyncio
async def test_paper_connection_always_ok():
    adapter = make_adapter()
    result = await adapter.test_connection()
    assert result.is_connected is True
    assert result.is_configured is True
