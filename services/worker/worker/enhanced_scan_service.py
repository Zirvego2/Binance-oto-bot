"""Worker tarafinda gelismis tarama, persist ve shadow mode."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.binance.interface import BinanceFuturesAdapter
from shared.db import (
    BotSettings,
    MarketRegimeSnapshot,
    Position,
    TradeCandidateRanking,
)
from shared.enhanced.cache import cache_get, cache_set, regime_cache_key
from shared.enhanced.orchestrator import DEFAULT_OPPORTUNITY_WEIGHTS, run_enhanced_scan
from shared.enhanced.types import EnhancedScanResult
from shared.enhanced.seed_profiles import seed_strategy_regime_profiles
from shared.enhanced.shadow_mode import build_shadow_decision, persist_shadow_decision
from shared.enhanced.symbol_profile import load_symbol_profiles
from shared.signal_scoring import SignalResult

logger = logging.getLogger("worker.enhanced_scan")

BTC_SYMBOL = "BTCUSDT"
BTC_TFS = ("5m", "15m", "1h", "4h")


async def _fetch_btc_klines(adapter: BinanceFuturesAdapter) -> dict:
    out = {}
    for tf in BTC_TFS:
        try:
            klines = await adapter.get_klines(BTC_SYMBOL, tf, limit=120)
            if klines:
                out[tf] = (
                    [float(k.close) for k in klines],
                    [float(k.high) for k in klines],
                    [float(k.low) for k in klines],
                    [float(k.quote_volume) for k in klines],
                )
        except Exception:  # noqa: BLE001
            logger.debug("BTC %s kline alinamadi", tf)
    return out


async def _open_position_closes(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    bot_mode: str,
    *,
    timeframe: str = "5m",
    lookback: int = 100,
) -> dict[str, list[float]]:
    result = await session.execute(
        select(Position).where(Position.status == "OPEN", Position.bot_mode == bot_mode)
    )
    positions = result.scalars().all()
    out: dict[str, list[float]] = {}
    for p in positions:
        try:
            klines = await adapter.get_klines(p.symbol, timeframe, limit=lookback)
            out[p.symbol] = [float(k.close) for k in klines] if klines else []
        except Exception:  # noqa: BLE001
            logger.debug("%s kline alinamadi (korelasyon)", p.symbol)
            out[p.symbol] = []
    return out


async def enrich_signals_from_enhanced_scan(
    session: AsyncSession,
    scan_result: EnhancedScanResult,
    bot_mode: str,
    admin_id: str | None = None,
) -> None:
    """Son sinyallere enhanced risk/rejim bilgisini yazar."""
    from sqlalchemy import desc

    from shared.db import StrategySignal

    regime = scan_result.market_regime.regime.value if scan_result.market_regime else None
    for candidate in scan_result.candidates:
        sig_result = await session.execute(
            select(StrategySignal)
            .where(
                StrategySignal.symbol == candidate.symbol,
                StrategySignal.bot_mode == bot_mode,
                StrategySignal.consumed.is_(False),
                StrategySignal.admin_id.is_(None) if admin_id is None else StrategySignal.admin_id == admin_id,
            )
            .order_by(desc(StrategySignal.created_at))
            .limit(1)
        )
        signal = sig_result.scalar_one_or_none()
        if signal is None:
            continue
        signal.risk_score = Decimal(str(candidate.risk_score))
        if regime:
            signal.regime_at_signal = regime
    await session.flush()


async def persist_enhanced_scan(
    session: AsyncSession,
    scan_result,
    settings: BotSettings,
) -> None:
    regime = scan_result.market_regime
    session.add(
        MarketRegimeSnapshot(
            market_scope="GLOBAL",
            symbol=None,
            timeframe=regime.timeframe,
            regime=regime.regime.value,
            confidence=Decimal(str(regime.confidence)),
            trend_strength=Decimal(str(regime.trend_strength)),
            volatility_score=Decimal(str(regime.volatility_score)),
            breadth_score=Decimal(str(regime.breadth_score)),
            risk_off_score=Decimal(str(regime.risk_off_score)),
            raw_metrics=regime.raw_metrics,
            reasons=regime.reasons,
            created_at=datetime.now(timezone.utc),
        )
    )
    for c in scan_result.candidates:
        session.add(
            TradeCandidateRanking(
                scan_id=scan_result.scan_id,
                symbol=c.symbol,
                direction=c.direction,
                signal_score=Decimal(str(c.signal_score)),
                risk_score=Decimal(str(c.risk_score)),
                expected_reward_score=Decimal(str(c.expected_reward_score)),
                expected_loss_score=Decimal(str(c.expected_loss_score)),
                risk_reward_ratio=Decimal(str(c.risk_reward_ratio)),
                regime_alignment_score=Decimal(str(c.regime_alignment_score)),
                symbol_profile_score=Decimal(str(c.symbol_profile_score)),
                liquidity_score=Decimal(str(c.liquidity_score)),
                correlation_penalty=Decimal(str(c.correlation_penalty)),
                final_opportunity_score=Decimal(str(c.final_opportunity_score)),
                rank=c.rank,
                selected=c.selected,
                rejection_reason=c.rejection_reason,
                created_at=datetime.now(timezone.utc),
            )
        )
    await session.flush()


async def run_enhanced_scan_cycle(
    session: AsyncSession,
    adapter: BinanceFuturesAdapter,
    settings: BotSettings,
    *,
    scan_signals: list[tuple[str, SignalResult, dict]],
    current_best: tuple[str, SignalResult] | None,
    redis: Redis | None = None,
) -> EnhancedScanResult | None:
    if not getattr(settings, "enhanced_engine_shadow_mode", True) and not getattr(settings, "enhanced_engine_enabled", False):
        return None

    await seed_strategy_regime_profiles(session)

    cached = await cache_get(redis, regime_cache_key("GLOBAL", settings.candle_timeframe))
    btc_klines = await _fetch_btc_klines(adapter)

    market_closes = btc_klines.get("5m", ([], [], [], []))[0] if btc_klines else []
    market_highs = btc_klines.get("5m", ([], [], [], []))[1] if btc_klines else []
    market_lows = btc_klines.get("5m", ([], [], [], []))[2] if btc_klines else []
    market_volumes = btc_klines.get("5m", ([], [], [], []))[3] if btc_klines else []

    rising = 0
    total = len(scan_signals)
    for _, sig, _ in scan_signals:
        if sig.suggested_side == "LONG":
            rising += 1
    rising_ratio = rising / total if total else 0.5

    symbols = [s[0] for s in scan_signals]
    profiles = await load_symbol_profiles(
        session, symbols, min_sample=int(settings.minimum_profile_sample_size)
    )
    open_closes = await _open_position_closes(
        session,
        adapter,
        settings.mode,
        timeframe=settings.candle_timeframe,
        lookback=int(getattr(settings, "correlation_lookback", 100) or 100),
    )

    weights = settings.opportunity_score_weights or DEFAULT_OPPORTUNITY_WEIGHTS
    shadow_only = not (
        settings.enhanced_engine_live_enabled
        and settings.mode == "live"
        and settings.enhanced_engine_enabled
    )

    result = run_enhanced_scan(
        settings=settings,
        scan_signals=scan_signals,
        market_closes=market_closes,
        market_highs=market_highs,
        market_lows=market_lows,
        market_volumes=market_volumes,
        btc_klines_by_tf=btc_klines,
        rising_ratio=rising_ratio,
        avg_funding_pct=0.0,
        open_position_closes=open_closes,
        symbol_profiles=profiles if settings.symbol_profile_enabled else {},
        opportunity_weights=weights,
        shadow_only=shadow_only,
        strategy_version_id=settings.active_strategy_version_id,
    )

    await persist_enhanced_scan(session, result, settings)

    current_sym = current_best[0] if current_best else None
    current_sig = current_best[1] if current_best else None
    shadow = build_shadow_decision(
        result.scan_id,
        current_symbol=current_sym,
        current_direction=current_sig.suggested_side if current_sig else None,
        current_score=float(current_sig.breakdown.total_score) if current_sig else None,
        enhanced=result,
    )
    if settings.shadow_mode_active:
        await persist_shadow_decision(session, shadow)

    if cached is None and result.market_regime:
        await cache_set(
            redis,
            regime_cache_key("GLOBAL", settings.candle_timeframe),
            {"regime": result.market_regime.regime.value, "confidence": result.market_regime.confidence},
            ttl_seconds=30,
        )

    logger.info(
        "Enhanced scan %s: rejim=%s aday=%d secilen=%s shadow=%s",
        result.scan_id,
        result.market_regime.regime.value,
        len(result.candidates),
        result.selected.symbol if result.selected else "yok",
        shadow_only,
    )
    return result
