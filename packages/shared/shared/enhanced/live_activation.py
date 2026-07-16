"""LIVE gelismis motor aktivasyon guvenlik kontrolleri."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotRuntimeStatus, BotSettings, Position, ShadowDecision, Trade

MIN_SHADOW_DECISIONS = 100
MIN_CLOSED_PAPER_TRADES = 30


async def validate_live_enhanced_activation(session: AsyncSession, settings: BotSettings) -> None:
    """Backend alt sinirlari — admin tarafindan dusurulemez."""
    if settings.mode != "live":
        raise ValueError("live_mode_required")
    if not settings.live_trading_enabled:
        raise ValueError("live_trading_not_enabled")
    if settings.bot_enabled:
        raise ValueError("bot_must_be_stopped")

    runtime = await session.get(BotRuntimeStatus, "default")
    if runtime and runtime.run_state == "SAFE_MODE":
        raise ValueError("safe_mode_active")

    open_count = await session.scalar(
        select(func.count()).select_from(Position).where(Position.status == "OPEN")
    )
    if open_count and open_count > 0:
        raise ValueError("open_positions_must_be_closed")

    shadow_count = await session.scalar(select(func.count()).select_from(ShadowDecision))
    if (shadow_count or 0) < MIN_SHADOW_DECISIONS:
        raise ValueError(f"minimum_shadow_decisions_not_met:{MIN_SHADOW_DECISIONS}")

    paper_trades = await session.scalar(
        select(func.count()).select_from(Trade).where(Trade.bot_mode == "paper")
    )
    if (paper_trades or 0) < MIN_CLOSED_PAPER_TRADES:
        raise ValueError(f"minimum_paper_trades_not_met:{MIN_CLOSED_PAPER_TRADES}")
