"""Varsayilan rejim profillerini seed eder."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import StrategyRegimeProfile
from shared.enhanced.regime_weights import DEFAULT_HIGH_VOL_WEIGHTS, DEFAULT_SIDEWAYS_WEIGHTS, DEFAULT_TREND_WEIGHTS

DEFAULT_PROFILES = [
    ("STRONG_UPTREND", DEFAULT_TREND_WEIGHTS),
    ("WEAK_UPTREND", DEFAULT_TREND_WEIGHTS),
    ("STRONG_DOWNTREND", DEFAULT_TREND_WEIGHTS),
    ("WEAK_DOWNTREND", DEFAULT_TREND_WEIGHTS),
    ("BREAKOUT", DEFAULT_TREND_WEIGHTS),
    ("BREAKDOWN", DEFAULT_TREND_WEIGHTS),
    ("SIDEWAYS", DEFAULT_SIDEWAYS_WEIGHTS),
    ("LOW_VOLATILITY", DEFAULT_SIDEWAYS_WEIGHTS),
    ("HIGH_VOLATILITY", DEFAULT_HIGH_VOL_WEIGHTS),
    ("RISK_OFF", DEFAULT_HIGH_VOL_WEIGHTS),
    ("UNKNOWN", DEFAULT_TREND_WEIGHTS),
]


async def seed_strategy_regime_profiles(session: AsyncSession) -> None:
    existing = await session.execute(select(StrategyRegimeProfile.regime))
    have = {r[0] for r in existing.all()}
    for regime, weights in DEFAULT_PROFILES:
        if regime in have:
            continue
        session.add(
            StrategyRegimeProfile(
                regime=regime,
                enabled=True,
                min_signal_score=Decimal("60"),
                long_enabled=True,
                short_enabled=True,
                indicator_weights=weights,
                risk_multiplier=Decimal("1"),
            )
        )
    await session.flush()
