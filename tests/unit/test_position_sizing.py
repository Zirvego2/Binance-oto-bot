from decimal import Decimal

from shared.binance_filters import parse_symbol_filters
from shared.position_sizing import PositionSizingInputs, calculate_position_size

BTC_FILTERS = {
    "symbol": "BTCUSDT",
    "status": "TRADING",
    "contractType": "PERPETUAL",
    "quoteAsset": "USDT",
    "marginAsset": "USDT",
    "filters": [
        {"filterType": "PRICE_FILTER", "tickSize": "0.10"},
        {"filterType": "LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "1000"},
        {"filterType": "MARKET_LOT_SIZE", "stepSize": "0.001", "minQty": "0.001", "maxQty": "120"},
        {"filterType": "MIN_NOTIONAL", "notional": "5"},
    ],
}

LOW_PRICE_FILTERS = {
    "symbol": "DOGEUSDT",
    "status": "TRADING",
    "contractType": "PERPETUAL",
    "quoteAsset": "USDT",
    "marginAsset": "USDT",
    "filters": [
        {"filterType": "PRICE_FILTER", "tickSize": "0.00001"},
        {"filterType": "LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "10000000"},
        {"filterType": "MARKET_LOT_SIZE", "stepSize": "1", "minQty": "1", "maxQty": "1000000"},
        {"filterType": "MIN_NOTIONAL", "notional": "5"},
    ],
}


def test_calculate_position_size_success():
    filters = parse_symbol_filters(BTC_FILTERS)
    result = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=Decimal("10"),
            leverage=Decimal("5"),
            price=Decimal("60000"),
            filters=filters,
            available_balance_usdt=Decimal("100"),
        )
    )
    # target_notional = 50, raw_qty = 50/60000 = 0.000833 -> yuvarlaninca 0
    assert result.ok is False
    assert result.quantity == Decimal("0")
    assert result.reason == "quantity_rounds_to_zero"


def test_calculate_position_size_1usdt_margin_3x_below_min_notional_is_skipped():
    """Sartname bolum 3 & 10: 1 USDT teminat + 3x kaldirac ile pozisyon buyuklugu
    3 USDT olur. BTCUSDT icin min notional 5 USDT oldugundan islem ATLANMALI,
    teminat otomatik yukseltilmemelidir."""

    filters = parse_symbol_filters(BTC_FILTERS)
    result = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=Decimal("1"),
            leverage=Decimal("3"),
            price=Decimal("60000"),
            filters=filters,
            available_balance_usdt=Decimal("100"),
        )
    )
    assert result.ok is False
    assert result.suggested_min_margin is not None
    assert result.suggested_min_margin > Decimal("1")


def test_calculate_position_size_low_price_coin_within_margin():
    filters = parse_symbol_filters(LOW_PRICE_FILTERS)
    result = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=Decimal("2"),
            leverage=Decimal("3"),
            price=Decimal("0.12"),
            filters=filters,
            available_balance_usdt=Decimal("100"),
        )
    )
    assert result.ok is True
    assert result.quantity > Decimal("0")
    # required margin kullanicinin belirledigi teminati asmamali
    assert result.required_margin <= Decimal("2") * Decimal("1.01")


def test_calculate_position_size_insufficient_balance():
    filters = parse_symbol_filters(LOW_PRICE_FILTERS)
    result = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=Decimal("2"),
            leverage=Decimal("3"),
            price=Decimal("0.12"),
            filters=filters,
            available_balance_usdt=Decimal("0.10"),
        )
    )
    assert result.ok is False
    assert result.reason == "insufficient_balance"


def test_calculate_position_size_never_exceeds_user_margin():
    """Kullanicinin belirledigi teminat asilmamali - buyuk leverage ile
    stepSize yuvarlamasi teminati asarsa islem reddedilmeli."""

    filters = parse_symbol_filters(BTC_FILTERS)
    result = calculate_position_size(
        PositionSizingInputs(
            margin_usdt=Decimal("0.02"),
            leverage=Decimal("1"),
            price=Decimal("60000"),
            filters=filters,
            available_balance_usdt=Decimal("100"),
        )
    )
    assert result.ok is False
