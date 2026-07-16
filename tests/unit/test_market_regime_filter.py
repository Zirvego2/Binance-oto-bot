"""BTC piyasa yonu filtresi testleri."""

from worker.market_regime import (
    select_best_signal_for_regime,
    signal_allowed_for_regime,
)


class _Breakdown:
    def __init__(self, score: float) -> None:
        self.total_score = score


class _Signal:
    def __init__(self, side: str | None, score: float) -> None:
        self.suggested_side = side
        self.breakdown = _Breakdown(score)


class _Symbol:
    def __init__(self, name: str) -> None:
        self.symbol = name


def test_signal_allowed_long_market_blocks_short():
    assert signal_allowed_for_regime("LONG", "LONG") is True
    assert signal_allowed_for_regime("SHORT", "LONG") is False


def test_signal_allowed_short_market_blocks_long():
    assert signal_allowed_for_regime("SHORT", "SHORT") is True
    assert signal_allowed_for_regime("LONG", "SHORT") is False


def test_signal_allowed_neutral_allows_both():
    assert signal_allowed_for_regime("LONG", "NEUTRAL") is True
    assert signal_allowed_for_regime("SHORT", "NEUTRAL") is True


def test_select_best_signal_for_regime():
    candidates = [
        (_Symbol("AAA"), _Signal("SHORT", 90)),
        (_Symbol("BBB"), _Signal("LONG", 70)),
        (_Symbol("CCC"), _Signal("LONG", 85)),
    ]
    best = select_best_signal_for_regime(candidates, filter_enabled=True, market_direction="LONG")
    assert best is not None
    assert best[0].symbol == "CCC"
