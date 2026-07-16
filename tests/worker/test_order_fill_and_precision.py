"""Emir dolum takibi ve koruyucu fiyat yuvarlama testleri."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.types import ExchangeOrder
from shared.db import BotSettings, Order, Position, Symbol
from worker.order_engine import (
    ORDER_FILL_MAX_ATTEMPTS,
    PositionOpenSkipped,
    _await_order_fill,
    _round_protective_trigger_price,
    open_position_for_signal,
)

from conftest import make_paper_adapter
from worker.symbol_filters import build_symbol_filters


def test_round_protective_trigger_price_respects_tick_size():
    filters = build_symbol_filters(
        Symbol(
            symbol="ARBUSDT",
            base_asset="ARB",
            quote_asset="USDT",
            margin_asset="USDT",
            status="TRADING",
            contract_type="PERPETUAL",
            price_tick_size=Decimal("0.00001"),
            lot_step_size=Decimal("0.1"),
            market_lot_step_size=Decimal("0.1"),
            min_qty=Decimal("0.1"),
            max_qty=Decimal("1000000"),
            min_notional=Decimal("5"),
            last_price=Decimal("0.0906"),
            mark_price=Decimal("0.0906"),
        )
    )
    sl = _round_protective_trigger_price(filters, Decimal("0.0920396635"), "SHORT", "STOP_LOSS")
    tp = _round_protective_trigger_price(filters, Decimal("0.0875095580"), "SHORT", "TAKE_PROFIT")
    assert sl == Decimal("0.09204")
    assert tp == Decimal("0.08750")


@pytest.mark.asyncio
async def test_await_order_fill_polls_until_filled():
    adapter = AsyncMock()
    adapter.query_order = AsyncMock(
        side_effect=[
            ExchangeOrder(
                symbol="BTCUSDT", binance_order_id="1", client_order_id="c1", side="BUY",
                order_type="MARKET", status="PARTIALLY_FILLED", price=Decimal("0"), orig_qty=Decimal("1"),
                executed_qty=Decimal("0.5"), avg_price=Decimal("50000"), reduce_only=False, close_position=False,
                stop_price=None, working_type=None, time_ms=0,
            ),
            ExchangeOrder(
                symbol="BTCUSDT", binance_order_id="1", client_order_id="c1", side="BUY",
                order_type="MARKET", status="FILLED", price=Decimal("0"), orig_qty=Decimal("1"),
                executed_qty=Decimal("1"), avg_price=Decimal("50000"), reduce_only=False, close_position=False,
                stop_price=None, working_type=None, time_ms=0,
            ),
        ]
    )
    initial = ExchangeOrder(
        symbol="BTCUSDT", binance_order_id="1", client_order_id="c1", side="BUY",
        order_type="MARKET", status="NEW", price=Decimal("0"), orig_qty=Decimal("1"),
        executed_qty=Decimal("0"), avg_price=Decimal("0"), reduce_only=False, close_position=False,
        stop_price=None, working_type=None, time_ms=0,
    )
    order_row = Order(
        symbol="BTCUSDT", side="BUY", order_type="MARKET", purpose="OPEN",
        quantity=Decimal("1"), client_order_id="c1", status="SUBMITTING", bot_mode="paper",
    )
    filled = await _await_order_fill(
        AsyncMock(), adapter, AsyncMock(), Symbol(symbol="BTCUSDT"), "LONG", "c1", initial, order_row, None,
    )
    assert filled.status == "FILLED"
    assert filled.executed_qty == Decimal("1")
    assert adapter.query_order.await_count == 2


@pytest.mark.asyncio
async def test_await_order_fill_raises_when_not_filled():
    adapter = AsyncMock()
    adapter.query_order = AsyncMock(return_value=None)
    initial = ExchangeOrder(
        symbol="BTCUSDT", binance_order_id="1", client_order_id="c1", side="BUY",
        order_type="MARKET", status="NEW", price=Decimal("0"), orig_qty=Decimal("1"),
        executed_qty=Decimal("0"), avg_price=Decimal("0"), reduce_only=False, close_position=False,
        stop_price=None, working_type=None, time_ms=0,
    )
    order_row = Order(
        symbol="BTCUSDT", side="BUY", order_type="MARKET", purpose="OPEN",
        quantity=Decimal("1"), client_order_id="c1", status="SUBMITTING", bot_mode="paper",
    )
    with pytest.raises(PositionOpenSkipped, match="order_not_filled"):
        await _await_order_fill(
            AsyncMock(), adapter, AsyncMock(), Symbol(symbol="BTCUSDT"), "LONG", "c1", initial, order_row, None,
        )
    assert adapter.query_order.await_count == ORDER_FILL_MAX_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_open_position_with_fine_tick_symbol_places_protective_orders(
    session: AsyncSession, settings_row: BotSettings, symbol_rule_row
):
    arb = Symbol(
        symbol="ARBUSDT",
        base_asset="ARB",
        quote_asset="USDT",
        margin_asset="USDT",
        status="TRADING",
        contract_type="PERPETUAL",
        price_tick_size=Decimal("0.00001"),
        lot_step_size=Decimal("0.1"),
        market_lot_step_size=Decimal("0.1"),
        min_qty=Decimal("0.1"),
        max_qty=Decimal("1000000"),
        min_notional=Decimal("5"),
        last_price=Decimal("0.0906"),
        mark_price=Decimal("0.0906"),
    )
    session.add(arb)
    await session.commit()

    adapter = make_paper_adapter(mark_price=Decimal("0.0906"))
    position = await open_position_for_signal(
        session, adapter, settings_row, arb, "SHORT", signal_id=None, open_reason="MANUAL"
    )
    assert position.status == "OPEN"
    assert position.protective_orders_ok is True
    assert position.stop_loss_price == _round_protective_trigger_price(
        build_symbol_filters(arb), position.stop_loss_price, "SHORT", "STOP_LOSS"
    )
    result = await session.execute(select(Position).where(Position.id == position.id))
    assert result.scalar_one().status == "OPEN"
