"""Binance USDS-M Futures exchangeInfo filtre dogrulama mantigi.

Sartname bolum 9: PRICE_FILTER, LOT_SIZE, MARKET_LOT_SIZE, MIN_NOTIONAL /
NOTIONAL filtreleri kontrol edilir. Bu filtreleri gecmeyen hicbir emir
gonderilmemelidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .decimal_utils import ZERO, decimal_places, quantize_price, quantize_step, round_up_to_step, safe_div


@dataclass(frozen=True, slots=True)
class SymbolFilters:
    """Binance exchangeInfo yanitindan cikarilan filtre bilgileri."""

    symbol: str
    status: str
    contract_type: str
    quote_asset: str
    margin_asset: str
    price_tick_size: Decimal
    price_min: Decimal
    price_max: Decimal
    lot_step_size: Decimal
    lot_min_qty: Decimal
    lot_max_qty: Decimal
    market_lot_step_size: Decimal
    market_lot_min_qty: Decimal
    market_lot_max_qty: Decimal
    min_notional: Decimal

    @property
    def is_tradable_usdt_perpetual(self) -> bool:
        """Sartname bolum 9: yalnizca TRADING + PERPETUAL + USDT quote/margin."""

        return (
            self.status == "TRADING"
            and self.contract_type == "PERPETUAL"
            and self.quote_asset == "USDT"
            and self.margin_asset == "USDT"
        )


@dataclass(frozen=True, slots=True)
class FilterCheckResult:
    ok: bool
    reason: str | None
    quantity: Decimal
    notional: Decimal


def parse_symbol_filters(exchange_info_symbol: dict) -> SymbolFilters:
    """Binance ``/fapi/v1/exchangeInfo`` yanitindaki tek bir symbol bloğunu ayristirir."""

    filters_by_type = {f["filterType"]: f for f in exchange_info_symbol.get("filters", [])}

    price_filter = filters_by_type.get("PRICE_FILTER", {})
    lot_filter = filters_by_type.get("LOT_SIZE", {})
    market_lot_filter = filters_by_type.get("MARKET_LOT_SIZE", lot_filter)
    # Binance USDS-M futures gunumuzde MIN_NOTIONAL filtresini kullaniyor;
    # bazi eski/alternatif yanitlarda NOTIONAL adiyla da gelebilir.
    notional_filter = filters_by_type.get("MIN_NOTIONAL") or filters_by_type.get("NOTIONAL") or {}

    def _dec(mapping: dict, key: str, default: str) -> Decimal:
        return Decimal(str(mapping.get(key, default)))

    return SymbolFilters(
        symbol=exchange_info_symbol["symbol"],
        status=exchange_info_symbol.get("status", "UNKNOWN"),
        contract_type=exchange_info_symbol.get("contractType", "UNKNOWN"),
        quote_asset=exchange_info_symbol.get("quoteAsset", ""),
        margin_asset=exchange_info_symbol.get("marginAsset", ""),
        price_tick_size=_dec(price_filter, "tickSize", "0.01"),
        price_min=_dec(price_filter, "minPrice", "0"),
        price_max=_dec(price_filter, "maxPrice", "0"),
        lot_step_size=_dec(lot_filter, "stepSize", "0.001"),
        lot_min_qty=_dec(lot_filter, "minQty", "0"),
        lot_max_qty=_dec(lot_filter, "maxQty", "0"),
        market_lot_step_size=_dec(market_lot_filter, "stepSize", "0.001"),
        market_lot_min_qty=_dec(market_lot_filter, "minQty", "0"),
        market_lot_max_qty=_dec(market_lot_filter, "maxQty", "0"),
        min_notional=_dec(notional_filter, "notional", notional_filter.get("minNotional", "5")),
    )


def round_quantity_down(filters: SymbolFilters, raw_quantity: Decimal) -> Decimal:
    """Miktari MARKET_LOT_SIZE stepSize degerine gore asagi yuvarlar."""

    return quantize_step(raw_quantity, filters.market_lot_step_size)


def round_price(filters: SymbolFilters, raw_price: Decimal) -> Decimal:
    """Fiyati PRICE_FILTER tickSize degerine gore yuvarlar."""

    return quantize_price(raw_price, filters.price_tick_size)


def format_price_for_exchange(filters: SymbolFilters, price: Decimal) -> str:
    """Binance API'sine gonderilecek fiyat string'ini tick hassasiyetinde uretir."""

    rounded = round_price(filters, price)
    places = decimal_places(filters.price_tick_size)
    return f"{rounded:.{places}f}"


def format_quantity_for_exchange(filters: SymbolFilters, quantity: Decimal) -> str:
    """Binance API'sine gonderilecek miktar string'ini step hassasiyetinde uretir."""

    rounded = round_quantity_down(filters, quantity)
    places = decimal_places(filters.market_lot_step_size)
    return f"{rounded:.{places}f}"


def required_min_margin(filters: SymbolFilters, price: Decimal, leverage: Decimal) -> Decimal:
    """Verilen kaldirac ve fiyat icin Binance min notional'i karsilayacak
    minimum teminat tutarini hesaplar (sartname bolum 3 & 10)."""

    if leverage <= ZERO:
        raise ValueError("leverage pozitif olmalidir")
    min_qty_for_notional = safe_div(filters.min_notional, price)
    min_qty = max(min_qty_for_notional, filters.market_lot_min_qty, filters.lot_min_qty)
    min_qty_rounded = quantize_step(min_qty, filters.market_lot_step_size, rounding="ROUND_UP")  # type: ignore[arg-type]
    min_notional_actual = max(filters.min_notional, min_qty_rounded * price)
    required_margin = safe_div(min_notional_actual, leverage)
    # Kucuk yuvarlama hatalarina karsi 8 basamaga sabitle (asagi yuvarlama yapmadan,
    # cunku bu bir "en az" degeri - kullaniciya gosterilecek guvenlik payi icin yukari yuvarla).
    return round_up_to_step(required_margin, Decimal("0.01"))


def validate_order(
    filters: SymbolFilters,
    quantity: Decimal,
    price: Decimal,
) -> FilterCheckResult:
    """PRICE_FILTER / LOT_SIZE / MARKET_LOT_SIZE / MIN_NOTIONAL kontrollerini
    yapar. Sonuc ``ok=False`` ise emir kesinlikle gonderilmemelidir."""

    if not filters.is_tradable_usdt_perpetual:
        return FilterCheckResult(False, "symbol_not_tradable_usdt_perpetual", quantity, ZERO)

    if quantity <= ZERO:
        return FilterCheckResult(False, "quantity_zero_or_negative", quantity, ZERO)

    min_qty = max(filters.market_lot_min_qty, filters.lot_min_qty)
    if min_qty > ZERO and quantity < min_qty:
        return FilterCheckResult(False, "quantity_below_min_qty", quantity, ZERO)

    max_qty = min(
        q for q in (filters.market_lot_max_qty, filters.lot_max_qty) if q > ZERO
    ) if (filters.market_lot_max_qty > ZERO or filters.lot_max_qty > ZERO) else ZERO
    if max_qty > ZERO and quantity > max_qty:
        return FilterCheckResult(False, "quantity_above_max_qty", quantity, ZERO)

    if filters.price_min > ZERO and price < filters.price_min:
        return FilterCheckResult(False, "price_below_min_price", quantity, ZERO)
    if filters.price_max > ZERO and price > filters.price_max:
        return FilterCheckResult(False, "price_above_max_price", quantity, ZERO)

    notional = quantity * price
    if filters.min_notional > ZERO and notional < filters.min_notional:
        return FilterCheckResult(False, "notional_below_min_notional", quantity, notional)

    return FilterCheckResult(True, None, quantity, notional)
