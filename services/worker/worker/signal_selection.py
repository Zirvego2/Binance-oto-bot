"""En guncel ortak sinyalden islem acilacak adayi secer."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import BotSettings, Position, StrategySignal, Symbol
from shared.platform_signals import shared_admin_id_clause
from shared.trading_risk import build_risk_context, evaluate_portfolio_risk

from .market_regime import signal_allowed_for_regime

logger = logging.getLogger("worker.signal_selection")


async def select_latest_signal_for_trade(
    session: AsyncSession,
    settings_row: BotSettings,
    admin_id: str,
    *,
    filter_enabled: bool,
    market_direction: str | None,
    signals_since: datetime | None = None,
) -> tuple[Symbol, StrategySignal] | None:
    """Bu tarama dongusundeki en son sinyali (created_at) islem adayi olarak dondurur."""

    query = (
        select(StrategySignal)
        .where(
            shared_admin_id_clause(StrategySignal.admin_id),
            StrategySignal.bot_mode == settings_row.mode,
        )
        .order_by(StrategySignal.created_at.desc())
        .limit(50)
    )
    if signals_since is not None:
        query = query.where(StrategySignal.created_at >= signals_since)

    signals = (await session.execute(query)).scalars().all()
    if not signals:
        return None

    for signal in signals:
        if filter_enabled and market_direction and not signal_allowed_for_regime(signal.side, market_direction):
            continue

        symbol_row = (
            await session.execute(select(Symbol).where(Symbol.symbol == signal.symbol))
        ).scalar_one_or_none()
        if symbol_row is None:
            continue

        open_for_symbol = (
            await session.execute(
                select(Position.id).where(
                    Position.admin_id == admin_id,
                    Position.symbol == signal.symbol,
                    Position.status == "OPEN",
                    Position.bot_mode == settings_row.mode,
                )
            )
        ).first()
        if open_for_symbol is not None:
            continue

        ctx = await build_risk_context(session, settings_row, signal.symbol)
        risk = evaluate_portfolio_risk(settings_row, ctx, signal.side)
        if not risk.ok:
            logger.debug(
                "En son sinyal %s %s islem acma riski nedeniyle atlandi: %s",
                signal.symbol,
                signal.side,
                risk.reason,
            )
            continue

        return symbol_row, signal

    return None


# Geriye uyumluluk
select_best_recent_signal_for_trade = select_latest_signal_for_trade
