"""Coin performans profili hesaplama (shadow mod destekli)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import SymbolPerformanceProfile, Trade


def _confidence(total: int, min_sample: int) -> Decimal:
    if total < min_sample:
        return Decimal(str(min(50, total * 5)))
    return Decimal(str(min(100, 50 + (total - min_sample) * 2)))


async def refresh_symbol_profile(
    session: AsyncSession,
    symbol: str,
    *,
    min_sample: int = 10,
) -> dict[str, Any]:
    result = await session.execute(
        select(Trade).where(Trade.symbol == symbol).order_by(Trade.closed_at.desc())
    )
    trades = list(result.scalars().all())
    profile = await session.get(SymbolPerformanceProfile, symbol)
    if profile is None:
        profile = SymbolPerformanceProfile(symbol=symbol)
        session.add(profile)

    if not trades:
        profile.confidence_level = Decimal("0")
        profile.last_calculated_at = datetime.now(timezone.utc)
        await session.flush()
        return {"symbol": symbol, "total_trades": 0, "confidence_level": 0, "min_sample": min_sample}

    wins = [t for t in trades if t.net_pnl_usdt > 0]
    losses = [t for t in trades if t.net_pnl_usdt <= 0]
    long_trades = [t for t in trades if t.side == "LONG"]
    short_trades = [t for t in trades if t.side == "SHORT"]
    long_wins = [t for t in long_trades if t.net_pnl_usdt > 0]
    short_wins = [t for t in short_trades if t.net_pnl_usdt > 0]

    gross_profit = sum((t.net_pnl_usdt for t in wins), Decimal("0"))
    gross_loss = abs(sum((t.net_pnl_usdt for t in losses), Decimal("0")))
    pf = (gross_profit / gross_loss) if gross_loss > 0 else Decimal("0")

    profile.total_trades = len(trades)
    profile.winning_trades = len(wins)
    profile.losing_trades = len(losses)
    profile.win_rate = Decimal(str(len(wins) / len(trades) * 100))
    profile.average_net_pnl = sum((t.net_pnl_usdt for t in trades), Decimal("0")) / len(trades)
    profile.average_roi = sum((t.net_roi_pct for t in trades), Decimal("0")) / len(trades)
    profile.profit_factor = pf
    profile.expectancy = profile.average_net_pnl
    profile.long_win_rate = Decimal(str(len(long_wins) / len(long_trades) * 100)) if long_trades else Decimal("0")
    profile.short_win_rate = Decimal(str(len(short_wins) / len(short_trades) * 100)) if short_trades else Decimal("0")
    profile.confidence_level = _confidence(len(trades), min_sample)
    profile.last_calculated_at = datetime.now(timezone.utc)
    await session.flush()

    return {
        "symbol": symbol,
        "total_trades": profile.total_trades,
        "win_rate": float(profile.win_rate),
        "confidence_level": float(profile.confidence_level),
        "min_sample": min_sample,
    }


async def load_symbol_profiles(
    session: AsyncSession,
    symbols: list[str],
    *,
    min_sample: int,
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        row = await session.get(SymbolPerformanceProfile, sym)
        if row is None:
            continue
        out[sym] = {
            "total_trades": row.total_trades,
            "win_rate": float(row.win_rate),
            "confidence_level": float(row.confidence_level),
            "min_sample": min_sample,
        }
    return out
