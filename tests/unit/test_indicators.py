import pytest

from shared.indicators import Candle, atr, crossed_above, crossed_below, ema, rsi, sma


def test_ema_length_and_first_value_is_sma():
    values = [float(v) for v in range(1, 31)]
    result = ema(values, 9)
    expected_first = sum(values[:9]) / 9
    assert len(result) == len(values) - 9 + 1
    assert abs(result[0] - expected_first) < 1e-9


def test_ema_returns_empty_when_not_enough_data():
    assert ema([1.0, 2.0], 9) == []


def test_ema_trends_upward_for_rising_prices():
    values = [100 + i for i in range(40)]
    result = ema(values, 9)
    assert result[-1] > result[0]


def test_rsi_is_100_when_all_gains():
    values = [100 + i for i in range(20)]
    result = rsi(values, 14)
    assert result[0] == 100.0


def test_rsi_is_0_when_all_losses():
    values = [100 - i for i in range(20)]
    result = rsi(values, 14)
    assert result[0] == 0.0


def test_rsi_between_0_and_100_for_mixed_data():
    values = [100, 102, 101, 103, 102, 105, 104, 106, 108, 107, 109, 110, 108, 111, 112]
    result = rsi(values, 14)
    assert len(result) == 1
    assert 0 <= result[0] <= 100


def test_rsi_raises_on_invalid_period():
    with pytest.raises(ValueError):
        rsi([1.0, 2.0], 0)


def test_atr_positive_for_volatile_candles():
    candles = [
        Candle(high=100 + i + 2, low=100 + i - 2, close=100 + i) for i in range(20)
    ]
    result = atr(candles, 14)
    assert len(result) > 0
    assert all(v > 0 for v in result)


def test_sma_basic():
    values = [1, 2, 3, 4, 5]
    result = sma([float(v) for v in values], 3)
    assert result == [2.0, 3.0, 4.0]


def test_crossed_above_true_case():
    assert crossed_above(fast_prev=9, fast_curr=11, slow_prev=10, slow_curr=10) is True


def test_crossed_above_false_when_already_above():
    assert crossed_above(fast_prev=12, fast_curr=13, slow_prev=10, slow_curr=10) is False


def test_crossed_below_true_case():
    assert crossed_below(fast_prev=11, fast_curr=9, slow_prev=10, slow_curr=10) is True
