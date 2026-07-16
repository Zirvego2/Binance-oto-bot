"""Gelistirme amacli manuel duman testi (otomatik test degildir).

Gercek Binance genel (public) piyasa verisini kullanarak PAPER moda ozel tum
uctan uca akisi (exchangeInfo senkronizasyonu -> piyasa verisi -> tarama ->
sinyal -> pozisyon acma -> koruyucu emirler -> pozisyon izleme) yerel bir
SQLite veritabaninda dener. Gercek Binance API anahtari GEREKTIRMEZ ve
GERCEK PARA kullanmaz (tamamen PAPER/simule).

Kullanim (services/worker klasorunden):
    $env:DATABASE_URL="sqlite+aiosqlite:///./smoke.db"
    python scripts/manual_smoke_test.py
"""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from shared.binance import BinanceAdapterConfig, build_adapter  # noqa: E402
from shared.db import BotSettings, Position  # noqa: E402

from worker.db import AsyncSessionLocal, create_all_tables  # noqa: E402
from worker.market_sync import refresh_market_data, refresh_spread_and_oi, sync_exchange_info  # noqa: E402
from worker.order_engine import PositionOpenSkipped, open_position_for_signal  # noqa: E402
from worker.position_monitor import refresh_open_positions  # noqa: E402
from worker.strategy import analyze_symbol, select_candidate_symbols  # noqa: E402


async def main() -> None:
    await create_all_tables()

    adapter = build_adapter(
        BinanceAdapterConfig(
            binance_env="paper",
            live_base_url="", live_api_key="", live_api_secret="",
            demo_base_url="", demo_api_key="", demo_api_secret="",
            paper_market_base_url="https://fapi.binance.com",
            paper_start_balance_usdt=Decimal("100"),
            paper_taker_commission_rate=Decimal("0.0004"),
        )
    )

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.id == "default"))
        settings_row = result.scalar_one_or_none()
        if settings_row is None:
            settings_row = BotSettings(id="default", margin_per_trade_usdt=Decimal("50"), leverage=5, bot_enabled=True)
            session.add(settings_row)
            await session.commit()
            await session.refresh(settings_row)

        print("1) exchangeInfo senkronize ediliyor...")
        count = await sync_exchange_info(session, adapter)
        print(f"   -> {count} sembol senkronize edildi")

        print("2) piyasa verisi (mark price / hacim / funding) yenileniyor...")
        updated = await refresh_market_data(session, adapter)
        print(f"   -> {updated} sembol icin piyasa verisi guncellendi")

        print("3) aday semboller seciliyor...")
        candidates = await select_candidate_symbols(session, settings_row)
        print(f"   -> {len(candidates)} aday sembol: {[c.symbol for c in candidates[:10]]}")

        if candidates:
            await refresh_spread_and_oi(session, adapter, [c.symbol for c in candidates[:5]])

        print("4) ilk 5 aday analiz ediliyor...")
        for symbol_row in candidates[:5]:
            result = await analyze_symbol(session, adapter, settings_row, symbol_row)
            if result is None:
                print(f"   {symbol_row.symbol}: yetersiz veri")
                continue
            print(
                f"   {symbol_row.symbol}: decision={result.decision.value} "
                f"side={result.suggested_side} score={result.breakdown.total_score:.1f}"
            )

        target_symbol_name = "XRPUSDT"
        print(f"5) {target_symbol_name} icin manuel LONG pozisyon acma deneniyor (test amacli, sinyal zorlanarak)...")
        from shared.db import Symbol

        symbol_row_result = await session.execute(select(Symbol).where(Symbol.symbol == target_symbol_name))
        btc_symbol = symbol_row_result.scalar_one_or_none()
        if btc_symbol is None:
            print(f"   {target_symbol_name} sembolu bulunamadi, atlaniyor")
        else:
            try:
                position = await open_position_for_signal(
                    session, adapter, settings_row, btc_symbol, "LONG", None, "manual_smoke_test"
                )
                print(
                    f"   -> POZISYON ACILDI: {position.symbol} {position.side} qty={position.quantity} "
                    f"entry={position.entry_price} sl={position.stop_loss_price} tp={position.take_profit_price} "
                    f"protected={position.protective_orders_ok}"
                )
            except PositionOpenSkipped as exc:
                print(f"   -> pozisyon acma atlandi: {exc.reason}")

        print("6) acik pozisyonlar yenileniyor...")
        await refresh_open_positions(session, adapter, "paper")
        open_result = await session.execute(select(Position).where(Position.status == "OPEN"))
        for p in open_result.scalars().all():
            print(f"   {p.symbol}: mark={p.mark_price} unrealized_pnl={p.unrealized_pnl} roi={p.roi_pct}%")

        print("\nDUMAN TESTI TAMAMLANDI.")


if __name__ == "__main__":
    asyncio.run(main())
