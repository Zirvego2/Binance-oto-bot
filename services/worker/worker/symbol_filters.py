"""``Symbol`` DB satirindan ``SymbolFilters`` dataclass'i insa eder."""

from __future__ import annotations

from decimal import Decimal

from shared.binance_filters import SymbolFilters
from shared.db import Symbol

_UNLIMITED = Decimal("0")  # validate_order/round_price bu degeri "sinir yok" olarak yorumlar


def build_symbol_filters(row: Symbol) -> SymbolFilters:
    """``symbols`` tablosunda PRICE_FILTER min/max saklanmaz (yalniz tickSize);
    bu nedenle min/max fiyat siniri kontrolu bilerek devre disi birakilir
    (0 = sinirsiz). Miktar ve minimum notional kontrolleri tam calisir."""

    return SymbolFilters(
        symbol=row.symbol,
        status=row.status,
        contract_type=row.contract_type,
        quote_asset=row.quote_asset,
        margin_asset=row.margin_asset,
        price_tick_size=row.price_tick_size,
        price_min=_UNLIMITED,
        price_max=_UNLIMITED,
        lot_step_size=row.lot_step_size,
        lot_min_qty=row.min_qty,
        lot_max_qty=row.max_qty,
        market_lot_step_size=row.market_lot_step_size,
        market_lot_min_qty=row.min_qty,
        market_lot_max_qty=row.max_qty,
        min_notional=row.min_notional,
    )
