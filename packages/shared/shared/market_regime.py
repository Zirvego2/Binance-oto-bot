"""BTC tabanli kisa vadeli piyasa yonu (market regime) analizi.

BTC dusunce altcoinler genelde duser, BTC yukselince piyasa yukselir.
Bu modul BTCUSDT uzerinden LONG / SHORT / NEUTRAL yonu uretir.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .indicators import Candle, atr, ema, rsi


@dataclass(frozen=True, slots=True)
class TimeframeAnalysis:
    interval: str
    price: float
    ema_fast: float
    ema_mid: float
    ema_slow: float
    rsi: float
    change_1h_pct: float
    change_4h_pct: float
    trend: str  # BULLISH | BEARISH | MIXED
    momentum: str  # STRONG_UP | UP | FLAT | DOWN | STRONG_DOWN


@dataclass(frozen=True, slots=True)
class MarketRegimeResult:
    symbol: str
    direction: str  # LONG | SHORT | NEUTRAL
    confidence: float
    btc_price: float
    change_1h_pct: float
    change_4h_pct: float
    primary: TimeframeAnalysis
    confirm: TimeframeAnalysis
    long_score: float
    short_score: float
    reason: str
    recommendation: str
    components: dict[str, float] = field(default_factory=dict)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _trend_label(price: float, ema_fast: float, ema_mid: float, ema_slow: float) -> str:
    if price > ema_fast > ema_mid > ema_slow:
        return "BULLISH"
    if price < ema_fast < ema_mid < ema_slow:
        return "BEARISH"
    if ema_fast > ema_mid and price > ema_mid:
        return "BULLISH"
    if ema_fast < ema_mid and price < ema_mid:
        return "BEARISH"
    return "MIXED"


def _momentum_label(rsi_val: float, change_1h_pct: float) -> str:
    if rsi_val >= 60 and change_1h_pct >= 0.5:
        return "STRONG_UP"
    if rsi_val >= 52 or change_1h_pct >= 0.2:
        return "UP"
    if rsi_val <= 40 and change_1h_pct <= -0.5:
        return "STRONG_DOWN"
    if rsi_val <= 48 or change_1h_pct <= -0.2:
        return "DOWN"
    return "FLAT"


def _pct_change(from_price: float, to_price: float) -> float:
    if from_price <= 0:
        return 0.0
    return (to_price - from_price) / from_price * 100.0


def _analyze_timeframe(
    closes: list[float],
    highs: list[float],
    lows: list[float],
    interval: str,
    *,
    ema_fast_period: int = 9,
    ema_mid_period: int = 21,
    ema_slow_period: int = 50,
    rsi_period: int = 14,
    candles_1h: int = 12,
    candles_4h: int = 48,
) -> TimeframeAnalysis | None:
    min_len = max(ema_slow_period + 5, rsi_period + 5, candles_4h + 1)
    if len(closes) < min_len:
        return None

    ema_f = ema(closes, ema_fast_period)
    ema_m = ema(closes, ema_mid_period)
    ema_s = ema(closes, ema_slow_period)
    rsi_vals = rsi(closes, rsi_period)
    if not ema_f or not ema_m or not ema_s or not rsi_vals:
        return None

    price = closes[-1]
    ef, em, es = ema_f[-1], ema_m[-1], ema_s[-1]
    rsi_val = rsi_vals[-1]

    idx_1h = max(0, len(closes) - candles_1h - 1)
    idx_4h = max(0, len(closes) - candles_4h - 1)
    change_1h = _pct_change(closes[idx_1h], price)
    change_4h = _pct_change(closes[idx_4h], price)

    return TimeframeAnalysis(
        interval=interval,
        price=price,
        ema_fast=ef,
        ema_mid=em,
        ema_slow=es,
        rsi=rsi_val,
        change_1h_pct=change_1h,
        change_4h_pct=change_4h,
        trend=_trend_label(price, ef, em, es),
        momentum=_momentum_label(rsi_val, change_1h),
    )


def _score_timeframe(tf: TimeframeAnalysis) -> tuple[float, float, dict[str, float]]:
    """(long_points, short_points, component breakdown)"""
    long_pts = 0.0
    short_pts = 0.0
    components: dict[str, float] = {}

    if tf.trend == "BULLISH":
        long_pts += 30
        components[f"{tf.interval}_trend"] = 30
    elif tf.trend == "BEARISH":
        short_pts += 30
        components[f"{tf.interval}_trend"] = -30
    else:
        components[f"{tf.interval}_trend"] = 0

    if tf.rsi >= 55:
        long_pts += 20
        components[f"{tf.interval}_rsi"] = 20
    elif tf.rsi <= 45:
        short_pts += 20
        components[f"{tf.interval}_rsi"] = -20
    elif tf.rsi >= 50:
        long_pts += 8
        components[f"{tf.interval}_rsi"] = 8
    elif tf.rsi <= 50:
        short_pts += 8
        components[f"{tf.interval}_rsi"] = -8
    else:
        components[f"{tf.interval}_rsi"] = 0

    if tf.change_1h_pct >= 0.3:
        long_pts += 15
        components[f"{tf.interval}_1h"] = 15
    elif tf.change_1h_pct <= -0.3:
        short_pts += 15
        components[f"{tf.interval}_1h"] = -15
    elif tf.change_1h_pct > 0:
        long_pts += 5
        components[f"{tf.interval}_1h"] = 5
    elif tf.change_1h_pct < 0:
        short_pts += 5
        components[f"{tf.interval}_1h"] = -5
    else:
        components[f"{tf.interval}_1h"] = 0

    if tf.change_4h_pct >= 0.5:
        long_pts += 10
        components[f"{tf.interval}_4h"] = 10
    elif tf.change_4h_pct <= -0.5:
        short_pts += 10
        components[f"{tf.interval}_4h"] = -10
    elif tf.change_4h_pct > 0:
        long_pts += 3
        components[f"{tf.interval}_4h"] = 3
    elif tf.change_4h_pct < 0:
        short_pts += 3
        components[f"{tf.interval}_4h"] = -3
    else:
        components[f"{tf.interval}_4h"] = 0

    mom = tf.momentum
    if mom in ("STRONG_UP", "UP"):
        long_pts += 10 if mom == "STRONG_UP" else 5
        components[f"{tf.interval}_mom"] = 10 if mom == "STRONG_UP" else 5
    elif mom in ("STRONG_DOWN", "DOWN"):
        short_pts += 10 if mom == "STRONG_DOWN" else 5
        components[f"{tf.interval}_mom"] = -10 if mom == "STRONG_DOWN" else -5
    else:
        components[f"{tf.interval}_mom"] = 0

    return long_pts, short_pts, components


def analyze_btc_market_regime(
    klines_primary: list,
    klines_confirm: list,
    *,
    symbol: str = "BTCUSDT",
    primary_interval: str = "5m",
    confirm_interval: str = "15m",
) -> MarketRegimeResult | None:
    """Iki timeframe kline listesinden piyasa yonu uretir."""

    def _extract(klines: list) -> tuple[list[float], list[float], list[float]]:
        closes = [float(k.close) for k in klines]
        highs = [float(k.high) for k in klines]
        lows = [float(k.low) for k in klines]
        return closes, highs, lows

    c1, h1, l1 = _extract(klines_primary)
    c2, h2, l2 = _extract(klines_confirm)

    primary = _analyze_timeframe(c1, h1, l1, primary_interval)
    confirm = _analyze_timeframe(c2, h2, l2, confirm_interval)
    if primary is None or confirm is None:
        return None

    long_total = 0.0
    short_total = 0.0
    all_components: dict[str, float] = {}

    for tf in (primary, confirm):
        lp, sp, comps = _score_timeframe(tf)
        long_total += lp
        short_total += sp
        all_components.update(comps)

    net = long_total - short_total
    max_possible = 170.0  # yaklasik iki timeframe toplam max

    if net >= 35:
        direction = "LONG"
        confidence = min(95.0, 50.0 + abs(net) / max_possible * 50.0)
        reason = "BTC yukselis egiliminde; altcoinler genelde yukari hareket eder"
        recommendation = "Kisa vadede LONG sinyalleri oncelikli degerlendirin"
    elif net <= -35:
        direction = "SHORT"
        confidence = min(95.0, 50.0 + abs(net) / max_possible * 50.0)
        reason = "BTC dusus egiliminde; altcoinler genelde asagi hareket eder"
        recommendation = "Kisa vadede SHORT sinyalleri oncelikli degerlendirin"
    else:
        direction = "NEUTRAL"
        confidence = max(30.0, 50.0 - abs(net))
        reason = "BTC yatay veya karisik; piyasa yonu net degil"
        recommendation = "Dikkatli olun, hem LONG hem SHORT icin sinyal skoruna bakin"

    if primary.trend == confirm.trend and primary.trend in ("BULLISH", "BEARISH"):
        confidence = min(98.0, confidence + 8.0)
        all_components["alignment_bonus"] = 8.0 if primary.trend == "BULLISH" else -8.0

    return MarketRegimeResult(
        symbol=symbol,
        direction=direction,
        confidence=round(confidence, 1),
        btc_price=primary.price,
        change_1h_pct=round(primary.change_1h_pct, 3),
        change_4h_pct=round(primary.change_4h_pct, 3),
        primary=primary,
        confirm=confirm,
        long_score=round(long_total, 1),
        short_score=round(short_total, 1),
        reason=reason,
        recommendation=recommendation,
        components=all_components,
    )
