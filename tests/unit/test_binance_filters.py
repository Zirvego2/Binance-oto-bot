from decimal import Decimal

from shared.binance_filters import parse_symbol_filters, required_min_margin, round_quantity_down, validate_order

SAMPLE_EXCHANGE_INFO_SYMBOL = {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "contractType": "PERPETUAL",
    "quoteAsset": "USDT",
    "marginAsset": "USDT",
    "filters": [
        {"filterType": "PRICE_FILTER", "tickSize": "0.10", "minPrice": "556.80", "maxPrice": "4529764"},
        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
        {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "120"},
        {"filterType": "MIN_NOTIONAL", "notional": "5"},
    ],
}


def test_parse_symbol_filters():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    assert filters.symbol == "BTCUSDT"
    assert filters.is_tradable_usdt_perpetual is True
    assert filters.price_tick_size == Decimal("0.10")
    assert filters.market_lot_step_size == Decimal("0.001")
    assert filters.min_notional == Decimal("5")


def test_round_quantity_down_uses_market_lot_step():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    rounded = round_quantity_down(filters, Decimal("0.0459"))
    assert rounded == Decimal("0.045")


def test_validate_order_rejects_below_min_notional():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    # 0.001 * 1000 = 1 USDT notional, min notional 5 USDT -> reddedilmeli
    result = validate_order(filters, Decimal("0.001"), Decimal("1000"))
    assert result.ok is False
    assert result.reason == "notional_below_min_notional"


def test_validate_order_accepts_when_notional_sufficient():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    result = validate_order(filters, Decimal("0.010"), Decimal("1000"))
    assert result.ok is True
    assert result.notional == Decimal("10.000")


def test_validate_order_rejects_quantity_zero():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    result = validate_order(filters, Decimal("0"), Decimal("100"))
    assert result.ok is False
    assert result.reason == "quantity_zero_or_negative"


def test_validate_order_rejects_non_perpetual_or_non_usdt():
    non_usdt = dict(SAMPLE_EXCHANGE_INFO_SYMBOL, quoteAsset="BUSD", marginAsset="BUSD")
    filters = parse_symbol_filters(non_usdt)
    result = validate_order(filters, Decimal("1"), Decimal("100"))
    assert result.ok is False
    assert result.reason == "symbol_not_tradable_usdt_perpetual"


def test_required_min_margin_for_low_price_high_min_notional():
    filters = parse_symbol_filters(SAMPLE_EXCHANGE_INFO_SYMBOL)
    # Fiyat 3 USDT, min notional 5 USDT, kaldirac 3x -> gerekli min teminat en az 5/3 = 1.667 USDT
    margin = required_min_margin(filters, Decimal("3"), Decimal("3"))
    assert margin >= Decimal("1.66")
