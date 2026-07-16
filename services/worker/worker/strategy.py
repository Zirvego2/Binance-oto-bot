"""Tarama dongusu: uygun sembolleri secer, gostergeleri hesaplar, sinyal
uretir ve aciklanabilir analiz kaydini veritabanina yazar (sartname bolum 15-18).

GPT: Yalnizca aciklama modu — emir karari vermez (bkz. shared.ai_explanation).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.client_ids import generate_signal_id
from shared.db import AiExplanation, AnalysisResult, BotSettings, StrategySignal, Symbol, SymbolRule
from shared.enums import SignalDecision
from shared.indicators import Candle, atr, ema, rsi, sma
from shared.signal_scoring import SignalInputs, SignalResult, StrategyThresholds, evaluate_signal

from .risk import build_risk_context

logger = logging.getLogger("worker.strategy")

_MIN_CANDLES_REQUIRED = 60


def _thresholds_from_settings(settings_row: BotSettings) -> StrategyThresholds:
    return StrategyThresholds(
        rsi_long_min=float(settings_row.rsi_long_min),
        rsi_long_max=float(settings_row.rsi_long_max),
        rsi_short_min=float(settings_row.rsi_short_min),
        rsi_short_max=float(settings_row.rsi_short_max),
        volume_multiplier_min=float(settings_row.volume_multiplier_min),
        max_spread_pct=float(settings_row.max_spread_pct),
        max_funding_rate_pct=float(settings_row.max_funding_rate_pct),
        max_volatility_atr_pct=float(settings_row.max_volatility_atr_pct),
        min_signal_score=float(settings_row.min_signal_score),
        long_enabled=settings_row.long_enabled,
        short_enabled=settings_row.short_enabled,
    )


async def select_candidate_symbols(session: AsyncSession, settings_row: BotSettings) -> list[Symbol]:
    result = await session.execute(select(Symbol).where(Symbol.status == "TRADING"))
    all_symbols = result.scalars().all()

    rules_query = select(SymbolRule)
    if settings_row.admin_id:
        rules_query = rules_query.where(SymbolRule.admin_id == settings_row.admin_id)
    rules_result = await session.execute(rules_query)
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
    return eligible[: settings_row.top_n_symbols_by_volume]


@dataclass(frozen=True, slots=True)
class _ComputedSignal:
    result: SignalResult
    current_price: float
    mark_price: Decimal
    ema_fast: float
    ema_mid: float
    ema_slow: float
    rsi_value: float
    atr_value: float
    current_volume: float
    avg_volume_20: float
    spread_pct: float
    funding_rate_pct: float
    open_interest: float | None


async def _compute_signal_for_symbol(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    symbol_row: Symbol,
    *,
    platform_shared: bool = False,
) -> _ComputedSignal | None:
    """Sembol icin guncel sinyal skorunu hesaplar (DB'ye yazmaz)."""

    klines = await adapter.get_klines(symbol_row.symbol, settings_row.candle_timeframe, limit=100)
    if len(klines) < _MIN_CANDLES_REQUIRED:
        return None

    closes = [float(k.close) for k in klines]
    highs = [float(k.high) for k in klines]
    lows = [float(k.low) for k in klines]
    volumes = [float(k.quote_volume) for k in klines]

    ema_fast_series = ema(closes, settings_row.ema_fast_period)
    ema_mid_series = ema(closes, settings_row.ema_mid_period)
    ema_slow_series = ema(closes, settings_row.ema_slow_period)
    rsi_series = rsi(closes, settings_row.rsi_period)
    candles = [Candle(high=h, low=l, close=c) for h, l, c in zip(highs, lows, closes)]
    atr_series = atr(candles, settings_row.atr_period)
    avg_volume_series = sma(volumes, 20)

    if not ema_fast_series or not ema_mid_series or not ema_slow_series or not rsi_series or not atr_series:
        return None
    if len(ema_fast_series) < 2 or len(ema_mid_series) < 2:
        return None

    current_price = closes[-1]
    mark_price_tick = symbol_row.mark_price or Decimal(str(current_price))

    ctx = None
    if not platform_shared and settings_row.admin_id:
        ctx = await build_risk_context(session, settings_row, symbol_row.symbol)

    spread_pct = float(symbol_row.spread_pct or 0)
    funding_rate_pct = float((symbol_row.funding_rate or Decimal("0")) * Decimal("100"))
    open_interest = float(symbol_row.open_interest) if symbol_row.open_interest else None

    inputs = SignalInputs(
        symbol=symbol_row.symbol,
        price=current_price,
        mark_price=float(mark_price_tick),
        ema_fast=ema_fast_series[-1],
        ema_fast_prev=ema_fast_series[-2],
        ema_mid=ema_mid_series[-1],
        ema_mid_prev=ema_mid_series[-2],
        ema_slow=ema_slow_series[-1],
        rsi_value=rsi_series[-1],
        atr_value=atr_series[-1],
        current_volume=volumes[-1],
        avg_volume_20=avg_volume_series[-1] if avg_volume_series else volumes[-1],
        volume_24h_usdt=float(symbol_row.volume_24h_usdt or 0),
        spread_pct=spread_pct,
        funding_rate_pct=funding_rate_pct,
        open_interest=open_interest,
        thresholds=_thresholds_from_settings(settings_row),
        is_blacklisted=ctx.is_blacklisted if ctx else False,
        has_enough_candles=True,
        min_notional_satisfiable=True,
    )

    result = evaluate_signal(inputs)
    return _ComputedSignal(
        result=result,
        current_price=current_price,
        mark_price=mark_price_tick,
        ema_fast=ema_fast_series[-1],
        ema_mid=ema_mid_series[-1],
        ema_slow=ema_slow_series[-1],
        rsi_value=rsi_series[-1],
        atr_value=atr_series[-1],
        current_volume=volumes[-1],
        avg_volume_20=avg_volume_series[-1] if avg_volume_series else volumes[-1],
        spread_pct=spread_pct,
        funding_rate_pct=funding_rate_pct,
        open_interest=open_interest,
    )


async def evaluate_live_signal_score(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    symbol_row: Symbol,
) -> SignalResult | None:
    """Acik emir takibi sirasinda guncel skor/yon kontrolu icin hafif sinyal hesabi."""

    computed = await _compute_signal_for_symbol(session, adapter, settings_row, symbol_row)
    return computed.result if computed is not None else None


async def analyze_symbol(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings_row: BotSettings,
    symbol_row: Symbol,
    *,
    platform_shared: bool = False,
) -> SignalResult | None:
    computed = await _compute_signal_for_symbol(
        session, adapter, settings_row, symbol_row, platform_shared=platform_shared
    )
    if computed is None:
        return None
    result = computed.result

    record_admin_id = None if platform_shared else settings_row.admin_id

    analysis = AnalysisResult(
        admin_id=record_admin_id,
        symbol=symbol_row.symbol,
        analyzed_at=datetime.now(timezone.utc),
        price=Decimal(str(computed.current_price)),
        mark_price=computed.mark_price,
        ema_fast=Decimal(str(computed.ema_fast)),
        ema_mid=Decimal(str(computed.ema_mid)),
        ema_slow=Decimal(str(computed.ema_slow)),
        rsi_value=Decimal(str(computed.rsi_value)),
        atr_value=Decimal(str(computed.atr_value)),
        current_volume=Decimal(str(computed.current_volume)),
        avg_volume_20=Decimal(str(computed.avg_volume_20)),
        volume_24h_usdt=symbol_row.volume_24h_usdt or Decimal("0"),
        spread_pct=Decimal(str(computed.spread_pct)),
        funding_rate_pct=Decimal(str(computed.funding_rate_pct)),
        open_interest=Decimal(str(computed.open_interest)) if computed.open_interest else None,
        trend_score=Decimal(str(result.breakdown.trend_score)),
        ema_score=Decimal(str(result.breakdown.ema_score)),
        rsi_score=Decimal(str(result.breakdown.rsi_score)),
        volume_score=Decimal(str(result.breakdown.volume_score)),
        volatility_score=Decimal(str(result.breakdown.volatility_score)),
        spread_score=Decimal(str(result.breakdown.spread_score)),
        funding_score=Decimal(str(result.breakdown.funding_score)),
        open_interest_score=Decimal(str(result.breakdown.open_interest_score)),
        total_score=Decimal(str(result.breakdown.total_score)),
        suggested_side=result.suggested_side,
        decision=result.decision.value,
        reason=result.reason,
        bot_mode=settings_row.mode,
    )
    session.add(analysis)
    await session.flush()

    signal_row: StrategySignal | None = None
    if result.suggested_side is not None:
        signal_row = StrategySignal(
            id=generate_signal_id(),
            admin_id=record_admin_id,
            analysis_result_id=analysis.id,
            symbol=symbol_row.symbol,
            side=result.suggested_side,
            total_score=Decimal(str(result.breakdown.total_score)),
            bot_mode=settings_row.mode,
            strategy_version_id=settings_row.active_strategy_version_id,
        )
        session.add(signal_row)
        await session.flush()

        await _maybe_store_ai_explanation(session, settings_row, signal_row, computed, result)

    await session.commit()

    if platform_shared:
        from shared.firestore.platform_sync import sync_platform_analysis, sync_platform_signal

        await sync_platform_analysis(analysis)
        if signal_row is not None:
            await sync_platform_signal(signal_row)
    else:
        from shared.firestore.tenant_sync import sync_analysis_to_firestore, sync_signal_to_firestore

        await sync_analysis_to_firestore(settings_row.admin_id, analysis)
        if signal_row is not None:
            await sync_signal_to_firestore(settings_row.admin_id, signal_row)

    return result


async def _maybe_store_ai_explanation(
    session: AsyncSession,
    settings_row: BotSettings,
    signal: StrategySignal,
    computed: _ComputedSignal,
    result: SignalResult,
) -> None:
    """GPT aciklama — karar motorunu etkilemez."""
    if not getattr(settings_row, "ai_explanation_enabled", False):
        return
    try:
        from .config import get_worker_settings
        from shared.ai_explanation import generate_signal_explanation

        worker_cfg = get_worker_settings()
        if not worker_cfg.openai_api_key:
            return
        payload = {
            "symbol": result.symbol,
            "direction": result.suggested_side,
            "score": result.breakdown.total_score,
            "rsi": computed.rsi_value,
            "spread_pct": computed.spread_pct,
            "funding_rate_pct": computed.funding_rate_pct,
        }
        explanation = await generate_signal_explanation(
            api_key=worker_cfg.openai_api_key,
            payload=payload,
            model=getattr(settings_row, "ai_model", "gpt-4o-mini"),
            timeout_seconds=int(getattr(settings_row, "ai_timeout_seconds", 15)),
        )
        session.add(
            AiExplanation(
                signal_id=signal.id,
                symbol=signal.symbol,
                status=explanation.status,
                summary=explanation.summary,
                positive_factors=explanation.positive_factors,
                negative_factors=explanation.negative_factors,
                risk_level=explanation.risk_level,
                warnings=explanation.warnings,
                suggestion=explanation.suggestion,
                model=explanation.model,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.flush()
    except Exception:  # noqa: BLE001
        logger.warning("AI aciklama kaydedilemedi (%s)", signal.symbol, exc_info=True)
