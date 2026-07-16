"""worker/position_monitor.py testleri: acik pozisyon PnL guncelleme, TP/SL
tetiklenerek kapanan pozisyonlarin dogru ``close_reason`` ile sonuclandirilmasi
ve gunluk istatistik/cooldown guncellemeleri."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, DailyStatistic, Position, Symbol, SymbolRule, Trade
from worker.order_engine import open_position_for_signal
from worker.position_monitor import refresh_open_positions

from conftest import make_paper_adapter, set_mark_price


async def _open_position(session, settings_row, symbol_row, side, mark_price=Decimal("50000")):
    adapter = make_paper_adapter(mark_price=mark_price)
    position = await open_position_for_signal(
        session, adapter, settings_row, symbol_row, side, signal_id=None, open_reason="MANUAL"
    )
    return adapter, position


@pytest.mark.asyncio
async def test_refresh_open_positions_updates_mark_price_and_pnl(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter, position = await _open_position(session, settings_row, symbol_row, "LONG")

    set_mark_price(adapter, Decimal("50100"))
    await adapter.on_mark_price_update(symbol_row.symbol, Decimal("50100"))

    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)

    assert position.status == "OPEN"
    assert position.mark_price == Decimal("50100")
    assert position.unrealized_pnl > 0


@pytest.mark.asyncio
async def test_stop_loss_trigger_closes_position_with_correct_reason(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter, position = await _open_position(session, settings_row, symbol_row, "LONG")
    sl_price = position.stop_loss_price

    # Fiyati stop-loss tetikleme seviyesinin altina dusur.
    trigger_price = sl_price - Decimal("50")
    set_mark_price(adapter, trigger_price)
    triggered = await adapter.on_mark_price_update(symbol_row.symbol, trigger_price)
    assert len(triggered) == 1

    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)

    assert position.status == "CLOSED"
    assert position.close_reason == "STOP_LOSS"
    assert position.closed_at is not None

    trades = (await session.execute(select(Trade).where(Trade.position_id == position.id))).scalars().all()
    assert len(trades) == 1
    assert trades[0].close_reason == "STOP_LOSS"

    stat = (
        await session.execute(select(DailyStatistic).where(DailyStatistic.bot_mode == "paper"))
    ).scalar_one()
    assert stat.trades_count == 1
    assert stat.losing_trades == 1
    assert stat.consecutive_losses == 1

    rule = (
        await session.execute(select(SymbolRule).where(SymbolRule.symbol == symbol_row.symbol))
    ).scalar_one()
    assert rule.cooldown_until is not None


@pytest.mark.asyncio
async def test_take_profit_trigger_closes_position_with_correct_reason(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter, position = await _open_position(session, settings_row, symbol_row, "LONG")
    tp_price = position.take_profit_price

    trigger_price = tp_price + Decimal("50")
    set_mark_price(adapter, trigger_price)
    triggered = await adapter.on_mark_price_update(symbol_row.symbol, trigger_price)
    assert len(triggered) == 1

    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)

    assert position.status == "CLOSED"
    assert position.close_reason == "TAKE_PROFIT"

    stat = (
        await session.execute(select(DailyStatistic).where(DailyStatistic.bot_mode == "paper"))
    ).scalar_one()
    assert stat.winning_trades == 1
    assert stat.consecutive_losses == 0


@pytest.mark.asyncio
async def test_short_position_take_profit_on_price_drop(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    adapter, position = await _open_position(session, settings_row, symbol_row, "SHORT")
    tp_price = position.take_profit_price

    trigger_price = tp_price - Decimal("50")
    set_mark_price(adapter, trigger_price)
    triggered = await adapter.on_mark_price_update(symbol_row.symbol, trigger_price)
    assert len(triggered) == 1

    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)

    assert position.status == "CLOSED"
    assert position.close_reason == "TAKE_PROFIT"


@pytest.mark.asyncio
async def test_software_trailing_stop_closes_profitable_reversal(
    session: AsyncSession, settings_row: BotSettings, symbol_row: Symbol, symbol_rule_row
):
    settings_row.trailing_stop_enabled = True
    settings_row.trailing_stop_activation_roi_pct = Decimal("5")
    settings_row.trailing_stop_callback_rate_pct = Decimal("1")
    settings_row.take_profit_roi_pct = Decimal("50")
    await session.commit()

    adapter, position = await _open_position(session, settings_row, symbol_row, "LONG")

    # ROI ~%6 karda (50600)
    set_mark_price(adapter, Decimal("50600"))
    await adapter.on_mark_price_update(symbol_row.symbol, Decimal("50600"))
    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)
    assert position.status == "OPEN"

    # Zirveden %1+ geri cekilme -> trailing stop (50400 ~ %4 ROI)
    set_mark_price(adapter, Decimal("50400"))
    await adapter.on_mark_price_update(symbol_row.symbol, Decimal("50400"))
    await refresh_open_positions(session, adapter, "paper")
    await session.refresh(position)

    assert position.status == "CLOSED"
    assert position.close_reason == "TRAILING_STOP"


@pytest.mark.asyncio
async def test_refresh_open_positions_noop_when_no_open_positions(
    session: AsyncSession, symbol_row: Symbol
):
    adapter = make_paper_adapter()
    # Hata firlatmadan sessizce donmeli.
    await refresh_open_positions(session, adapter, "paper")
    result = await session.execute(select(Position))
    assert result.scalars().all() == []
