"""worker/order_engine.py testleri: pozisyon acma, koruyucu emirler ve
korumasiz pozisyon acil kapatma senaryolari (gercek PaperFuturesAdapter ile,
sadece fiyat kaynagi mocklanir)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import AlgoOrder, BotSettings, Order, Position, RiskEvent, Symbol
from worker.order_engine import PositionOpenSkipped, open_position_for_signal

from conftest import make_paper_adapter


@pytest.mark.asyncio
async def test_open_position_places_protective_orders_and_persists_state(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter = make_paper_adapter(mark_price=Decimal("50000"))

    position = await open_position_for_signal(
        session, adapter, settings_row, symbol_row, "LONG", signal_id=None, open_reason="MANUAL"
    )

    assert position.status == "OPEN"
    assert position.protective_orders_ok is True
    assert position.side == "LONG"
    assert position.quantity > 0
    assert position.stop_loss_algo_order_id is not None
    assert position.take_profit_algo_order_id is not None
    # SL entry'nin altinda, TP entry'nin ustunde olmali (LONG)
    assert position.stop_loss_price < position.entry_price < position.take_profit_price

    order_result = await session.execute(select(Order).where(Order.position_id == position.id))
    orders = order_result.scalars().all()
    assert len(orders) == 1
    assert orders[0].status == "FILLED"

    algo_result = await session.execute(select(AlgoOrder).where(AlgoOrder.position_id == position.id))
    algo_orders = algo_result.scalars().all()
    assert len(algo_orders) == 2
    assert {a.purpose for a in algo_orders} == {"STOP_LOSS", "TAKE_PROFIT"}
    assert all(a.status == "NEW" for a in algo_orders)

    # Borsada da (paper adaptorde) gercekten acik pozisyon ve algo emirleri olmali
    exchange_positions = await adapter.get_open_positions()
    assert len(exchange_positions) == 1
    open_algo = await adapter.get_open_algo_orders(symbol_row.symbol)
    assert len(open_algo) == 2


@pytest.mark.asyncio
async def test_open_short_position_sets_sl_above_and_tp_below_entry(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter = make_paper_adapter(mark_price=Decimal("50000"))

    position = await open_position_for_signal(
        session, adapter, settings_row, symbol_row, "SHORT", signal_id=None, open_reason="MANUAL"
    )

    assert position.side == "SHORT"
    assert position.take_profit_price < position.entry_price < position.stop_loss_price


@pytest.mark.asyncio
async def test_position_sizing_failure_raises_skipped_without_persisting_position(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    settings_row.margin_per_trade_usdt = Decimal("0.001")  # min notional'i asla karsilamaz
    adapter = make_paper_adapter(mark_price=Decimal("50000"))

    with pytest.raises(PositionOpenSkipped):
        await open_position_for_signal(
            session, adapter, settings_row, symbol_row, "LONG", signal_id=None, open_reason="MANUAL"
        )

    result = await session.execute(select(Position))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_protective_order_failure_triggers_emergency_close(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter = make_paper_adapter(mark_price=Decimal("50000"))
    adapter.place_stop_loss_order = AsyncMock(side_effect=RuntimeError("borsa hata donduruyor"))

    with pytest.raises(PositionOpenSkipped) as exc_info:
        await open_position_for_signal(
            session, adapter, settings_row, symbol_row, "LONG", signal_id=None, open_reason="MANUAL"
        )
    assert exc_info.value.reason == "protective_order_placement_failed"

    result = await session.execute(select(Position))
    positions = result.scalars().all()
    assert len(positions) == 1
    position = positions[0]
    assert position.status == "CLOSED"
    assert position.close_reason == "EMERGENCY_STOP"
    assert position.protective_orders_ok is False

    # Borsada (paper adaptorde) da pozisyon gercekten kapatilmis olmali
    exchange_positions = await adapter.get_open_positions()
    assert exchange_positions == []

    risk_events = (await session.execute(select(RiskEvent))).scalars().all()
    assert any(e.event_type == "PROTECTIVE_ORDER_FAILED" for e in risk_events)


@pytest.mark.asyncio
async def test_leverage_not_confirmed_skips_without_opening_order(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter = make_paper_adapter(mark_price=Decimal("50000"))

    from shared.binance.types import LeverageChangeResult

    adapter.change_leverage = AsyncMock(
        return_value=LeverageChangeResult(symbol=symbol_row.symbol, leverage=999, max_notional_value=Decimal("0"))
    )

    with pytest.raises(PositionOpenSkipped) as exc_info:
        await open_position_for_signal(
            session, adapter, settings_row, symbol_row, "LONG", signal_id=None, open_reason="MANUAL"
        )
    assert exc_info.value.reason == "leverage_not_confirmed"

    result = await session.execute(select(Order))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_fixed_leverage_not_reduced_when_risk_adjusted_disabled(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    settings_row.leverage = 8
    settings_row.stop_loss_roi_pct = Decimal("90")
    settings_row.min_liquidation_distance_pct = Decimal("3")
    settings_row.risk_adjusted_leverage_enabled = False
    await session.commit()

    adapter = make_paper_adapter(mark_price=Decimal("50000"))

    position = await open_position_for_signal(
        session, adapter, settings_row, symbol_row, "LONG", signal_id=None, open_reason="MANUAL"
    )

    assert position.leverage == 8
