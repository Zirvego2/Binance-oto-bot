"""Binance exchangeInfo ve piyasa verisi senkronizasyonu (sartname bolum 8-9, 15).

- ``sync_exchange_info``: tum USDT-M perpetual sembollerini ``symbols`` tablosuna
  yazar/gunceller (filtre bilgileri dahil). Nadiren calisir (varsayilan 30 dk).
- ``refresh_market_data``: mark price, funding rate, 24h hacim ve spread
  bilgilerini gunceller. Her tarama dongusunde calisir.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.db import Symbol

import logging

logger = logging.getLogger("worker.market_sync")


async def sync_exchange_info(session: AsyncSession, adapter: BinanceFuturesAdapter) -> int:
    info = await adapter.get_exchange_info()
    symbols_payload = info.get("symbols", [])
    now = datetime.now(timezone.utc)
    count = 0

    for entry in symbols_payload:
        if entry.get("contractType") != "PERPETUAL":
            continue
        if entry.get("quoteAsset") != "USDT" or entry.get("marginAsset") != "USDT":
            continue

        filters_by_type = {f["filterType"]: f for f in entry.get("filters", [])}
        price_filter = filters_by_type.get("PRICE_FILTER", {})
        lot_filter = filters_by_type.get("LOT_SIZE", {})
        market_lot_filter = filters_by_type.get("MARKET_LOT_SIZE", lot_filter)
        notional_filter = filters_by_type.get("MIN_NOTIONAL") or filters_by_type.get("NOTIONAL") or {}

        symbol_name = entry["symbol"]
        result = await session.execute(select(Symbol).where(Symbol.symbol == symbol_name))
        row = result.scalar_one_or_none()
        if row is None:
            row = Symbol(symbol=symbol_name)
            session.add(row)

        row.base_asset = entry.get("baseAsset", "")
        row.quote_asset = entry.get("quoteAsset", "")
        row.margin_asset = entry.get("marginAsset", "")
        row.status = entry.get("status", "UNKNOWN")
        row.contract_type = entry.get("contractType", "UNKNOWN")
        row.price_tick_size = Decimal(str(price_filter.get("tickSize", "0.01")))
        row.lot_step_size = Decimal(str(lot_filter.get("stepSize", "0.001")))
        row.market_lot_step_size = Decimal(str(market_lot_filter.get("stepSize", "0.001")))
        row.min_qty = Decimal(str(lot_filter.get("minQty", "0")))
        row.max_qty = Decimal(str(lot_filter.get("maxQty", "0")))
        row.min_notional = Decimal(str(notional_filter.get("notional", notional_filter.get("minNotional", "5"))))

        # SymbolRule musteri bazlidir (admin_id zorunlu); burada otomatik kayit olusturulmaz.

        count += 1

    await session.commit()
    logger.info("Exchange bilgisi senkronize edildi: %d sembol", count)
    return count


async def refresh_market_data(session: AsyncSession, adapter: BinanceFuturesAdapter) -> int:
    tickers = await adapter.get_24h_tickers()
    ticker_by_symbol = {t.symbol: t for t in tickers}

    mark_prices = await adapter.get_all_mark_prices()
    mark_by_symbol = {m.symbol: m for m in mark_prices}

    result = await session.execute(select(Symbol).where(Symbol.status == "TRADING"))
    rows = result.scalars().all()
    now = datetime.now(timezone.utc)
    updated = 0

    for row in rows:
        ticker = ticker_by_symbol.get(row.symbol)
        mark = mark_by_symbol.get(row.symbol)
        if ticker is not None:
            row.last_price = ticker.last_price
            row.volume_24h_usdt = ticker.quote_volume
        if mark is not None:
            row.mark_price = mark.mark_price
            row.funding_rate = mark.funding_rate
        row.market_data_updated_at = now
        updated += 1

    await session.commit()
    return updated


async def refresh_spread_and_oi(session: AsyncSession, adapter: BinanceFuturesAdapter, symbols: list[str]) -> None:
    """Sadece taramaya dahil edilecek daraltilmis sembol listesi icin spread ve
    open interest bilgisini gunceller (tum semboller icin yapmak asiri API
    cagrisina yol acar)."""

    for symbol_name in symbols:
        try:
            book_ticker = await adapter.get_book_ticker(symbol_name)
            open_interest = await adapter.get_open_interest(symbol_name)
        except Exception:  # noqa: BLE001 - tek sembol hatasi taramayi durdurmamali
            continue

        result = await session.execute(select(Symbol).where(Symbol.symbol == symbol_name))
        row = result.scalar_one_or_none()
        if row is None:
            continue
        mid = (book_ticker.bid_price + book_ticker.ask_price) / 2
        if mid > 0:
            row.spread_pct = (book_ticker.ask_price - book_ticker.bid_price) / mid * Decimal("100")
        row.open_interest = open_interest.open_interest

    await session.commit()
