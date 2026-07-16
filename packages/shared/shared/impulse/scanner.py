"""Alt coin lokal tepe/dip aday taramasi (BTC impulsuna karsi yon)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.db import BotSettings, Symbol, SymbolRule
from shared.indicators import Candle, rsi

from .detector import BTC_SYMBOL, impulse_to_counter_side


@dataclass(frozen=True, slots=True)
class ImpulseCandidate:
    symbol: str
    side: str
    score: float
    rsi: float
    proximity_pct: float
    volume_ratio: float
    price: float
    reason: str


async def _eligible_symbols(session: AsyncSession, settings_row: BotSettings, top_n: int) -> list[Symbol]:
    result = await session.execute(select(Symbol).where(Symbol.status == "TRADING"))
    all_symbols = [s for s in result.scalars().all() if s.symbol != BTC_SYMBOL]

    rules_result = await session.execute(select(SymbolRule))
    rules_by_symbol = {r.symbol: r for r in rules_result.scalars().all()}

    eligible: list[Symbol] = []
    for s in all_symbols:
        rule = rules_by_symbol.get(s.symbol)
        if rule is not None and (not rule.in_analysis_list or rule.is_blacklisted):
            continue
        if s.volume_24h_usdt is None or s.volume_24h_usdt < settings_row.min_24h_volume_usdt:
            continue
        eligible.append(s)

    eligible.sort(key=lambda s: s.volume_24h_usdt or Decimal("0"), reverse=True)
    return eligible[:top_n]


def _score_candidate(
    side: str,
    rsi_value: float,
    proximity_pct: float,
    volume_ratio: float,
    rsi_overbought: float,
    rsi_oversold: float,
) -> tuple[float, str]:
    if side == "SHORT":
        rsi_part = max(0.0, min(30.0, (rsi_value - (rsi_overbought - 10)) * 1.5))
        prox_part = max(0.0, min(35.0, (100.0 - proximity_pct) * 0.7))
        vol_part = max(0.0, min(20.0, (volume_ratio - 1.0) * 10.0))
        reason = f"RSI={rsi_value:.1f}, tepeye yakinlik=%{proximity_pct:.1f}, hacim x{volume_ratio:.2f}"
    else:
        rsi_part = max(0.0, min(30.0, ((rsi_oversold + 10) - rsi_value) * 1.5))
        prox_part = max(0.0, min(35.0, (100.0 - proximity_pct) * 0.7))
        vol_part = max(0.0, min(20.0, (volume_ratio - 1.0) * 10.0))
        reason = f"RSI={rsi_value:.1f}, dibe yakinlik=%{proximity_pct:.1f}, hacim x{volume_ratio:.2f}"

    base = 15.0 if side in ("LONG", "SHORT") else 0.0
    score = base + rsi_part + prox_part + vol_part
    return min(100.0, score), reason


async def scan_extreme_candidates(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    impulse_direction: str,
    *,
    force_side: str | None = None,
) -> list[ImpulseCandidate]:
    side = force_side or impulse_to_counter_side(impulse_direction)
    if side is None:
        return []

    symbols = await _eligible_symbols(session, settings_row, settings_row.impulse_top_n_scan)
    candidates: list[ImpulseCandidate] = []

    rsi_overbought = float(settings_row.impulse_rsi_overbought)
    rsi_oversold = float(settings_row.impulse_rsi_oversold)
    min_score = float(settings_row.impulse_extreme_min_score)

    for symbol_row in symbols:
        try:
            klines = await adapter.get_klines(symbol_row.symbol, "1m", limit=40)
        except Exception:  # noqa: BLE001
            continue
        if len(klines) < 20:
            continue

        closes = [float(k.close) for k in klines]
        highs = [float(k.high) for k in klines]
        lows = [float(k.low) for k in klines]
        volumes = [float(k.volume) for k in klines]

        rsi_values = rsi(closes, period=14)
        if not rsi_values:
            continue
        rsi_value = rsi_values[-1]

        window = 15
        recent_high = max(highs[-window:])
        recent_low = min(lows[-window:])
        price = closes[-1]

        if side == "SHORT":
            if rsi_value < rsi_overbought - 5:
                continue
            if recent_high <= 0:
                continue
            proximity_pct = max(0.0, (recent_high - price) / recent_high * 100.0)
        else:
            if rsi_value > rsi_oversold + 5:
                continue
            if recent_low <= 0:
                continue
            proximity_pct = max(0.0, (price - recent_low) / recent_low * 100.0)

        avg_vol = sum(volumes[-21:-1]) / 20.0 if len(volumes) >= 21 else sum(volumes[:-1]) / max(len(volumes) - 1, 1)
        volume_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0

        score, reason = _score_candidate(
            side, rsi_value, proximity_pct, volume_ratio, rsi_overbought, rsi_oversold
        )
        if score < min_score:
            continue

        candidates.append(
            ImpulseCandidate(
                symbol=symbol_row.symbol,
                side=side,
                score=score,
                rsi=rsi_value,
                proximity_pct=proximity_pct,
                volume_ratio=volume_ratio,
                price=price,
                reason=reason,
            )
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates
