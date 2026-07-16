"""Worker servisi testleri icin ortak fixture'lar.

Gercek PostgreSQL/Redis/Binance GEREKTIRMEZ: her test kendi bellek-ici (in
memory) SQLite veritabanini kullanir ve PaperFuturesAdapter'in tek
network-bagimli metodu (``get_mark_price``) mocklanir; adapterin
pozisyon/emir/algo-emir mantiginin TAMAMI gercek kod yoluyla (mock DEGIL)
calisir.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from shared.binance.paper_adapter import PaperFuturesAdapter
from shared.binance.types import MarkPriceTick
from shared.db import Base, BotSettings, Symbol, SymbolRule


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as db_session:
        yield db_session

    await engine.dispose()


@pytest_asyncio.fixture
async def settings_row(session: AsyncSession) -> BotSettings:
    row = BotSettings(
        id="default",
        mode="paper",
        live_trading_enabled=False,
        auto_trading_enabled=True,
        bot_enabled=True,
        margin_per_trade_usdt=Decimal("10"),
        leverage=5,
        max_allowed_leverage=10,
        margin_type="ISOLATED",
        position_mode="ONE_WAY",
        multi_assets_mode=False,
        take_profit_roi_pct=Decimal("10"),
        stop_loss_roi_pct=Decimal("5"),
        max_open_positions=3,
        max_open_positions_per_symbol=1,
        daily_max_loss_usdt=Decimal("50"),
        max_consecutive_losses=3,
        candle_timeframe="5m",
        scan_interval_seconds=60,
        post_trade_cooldown_minutes=30,
        min_24h_volume_usdt=Decimal("1000000"),
        long_enabled=True,
        short_enabled=True,
        trailing_stop_enabled=False,
        trailing_stop_activation_roi_pct=Decimal("5"),
        trailing_stop_callback_rate_pct=Decimal("1"),
        max_spread_pct=Decimal("0.15"),
        max_funding_rate_pct=Decimal("0.75"),
        max_volatility_atr_pct=Decimal("8"),
        ema_fast_period=9,
        ema_mid_period=21,
        ema_slow_period=50,
        rsi_period=14,
        atr_period=14,
        rsi_long_min=Decimal("50"),
        rsi_long_max=Decimal("65"),
        rsi_short_min=Decimal("35"),
        rsi_short_max=Decimal("50"),
        volume_multiplier_min=Decimal("1.2"),
        min_signal_score=Decimal("60"),
        top_n_symbols_by_volume=20,
        working_type="MARK_PRICE",
        min_liquidation_distance_pct=Decimal("10"),
        max_slippage_pct=Decimal("0.5"),
        paper_taker_commission_rate=Decimal("0.0004"),
        paper_start_balance_usdt=Decimal("1000"),
        paper_funding_simulation_enabled=True,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@pytest_asyncio.fixture
async def symbol_row(session: AsyncSession) -> Symbol:
    row = Symbol(
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        margin_asset="USDT",
        status="TRADING",
        contract_type="PERPETUAL",
        price_tick_size=Decimal("0.1"),
        lot_step_size=Decimal("0.001"),
        market_lot_step_size=Decimal("0.001"),
        min_qty=Decimal("0.001"),
        max_qty=Decimal("1000"),
        min_notional=Decimal("5"),
        last_price=Decimal("50000"),
        mark_price=Decimal("50000"),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


@pytest_asyncio.fixture
async def symbol_rule_row(session: AsyncSession, symbol_row: Symbol) -> SymbolRule:
    result = await session.execute(select(SymbolRule).where(SymbolRule.symbol == symbol_row.symbol))
    row = result.scalar_one_or_none()
    if row is not None:
        return row

    row = SymbolRule(symbol=symbol_row.symbol)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


def make_paper_adapter(mark_price: Decimal = Decimal("50000")) -> PaperFuturesAdapter:
    """Gercek PaperFuturesAdapter dondurur; SADECE agdan fiyat ceken
    ``get_mark_price`` mocklanir, boylece tum pozisyon/emir/algo-emir mantigi
    gercek kod uzerinden (network gerektirmeden) test edilir."""

    adapter = PaperFuturesAdapter(
        market_base_url="https://fapi.binance.com",
        starting_balance_usdt=Decimal("1000"),
        taker_commission_rate=Decimal("0.0004"),
    )

    state = {"price": mark_price}

    async def _get_mark_price(symbol: str) -> MarkPriceTick:
        return MarkPriceTick(
            symbol=symbol,
            mark_price=state["price"],
            index_price=state["price"],
            funding_rate=Decimal("0.0001"),
            next_funding_time_ms=0,
            time_ms=0,
        )

    adapter.get_mark_price = AsyncMock(side_effect=_get_mark_price)  # type: ignore[method-assign]
    adapter._test_state = state  # type: ignore[attr-defined]
    return adapter


def set_mark_price(adapter: PaperFuturesAdapter, price: Decimal) -> None:
    adapter._test_state["price"] = price  # type: ignore[attr-defined]
