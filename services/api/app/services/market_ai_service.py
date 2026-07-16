"""Piyasa sayfasi icin GPT arastirma servisi."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from redis.asyncio import Redis
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai_market_research import (
    MarketAiResearchResult,
    generate_market_research,
    market_research_cache_key,
)
from shared.db import BotSettings, MarketRegimeSnapshot

from ..core.config import Settings
from ..schemas.market import MarketAiResearchOut, MarketRegimeOut
from .market_helpers import fetch_market_regime_out


async def _build_research_payload(
    session: AsyncSession,
    regime: MarketRegimeOut,
) -> dict:
    enhanced = await session.execute(
        select(MarketRegimeSnapshot)
        .where(MarketRegimeSnapshot.market_scope == "GLOBAL")
        .order_by(desc(MarketRegimeSnapshot.created_at))
        .limit(1)
    )
    snap = enhanced.scalar_one_or_none()
    payload = {
        "symbol": regime.symbol,
        "btc_price": regime.btc_price,
        "direction": regime.direction,
        "confidence": regime.confidence,
        "change_1h_pct": regime.change_1h_pct,
        "change_4h_pct": regime.change_4h_pct,
        "long_score": regime.long_score,
        "short_score": regime.short_score,
        "reason": regime.reason,
        "recommendation": regime.recommendation,
        "primary_timeframe": {
            "interval": regime.primary.interval,
            "rsi": regime.primary.rsi,
            "trend": regime.primary.trend,
            "momentum": regime.primary.momentum,
            "change_1h_pct": regime.primary.change_1h_pct,
            "change_4h_pct": regime.primary.change_4h_pct,
            "ema_fast": regime.primary.ema_fast,
            "ema_mid": regime.primary.ema_mid,
            "ema_slow": regime.primary.ema_slow,
        },
        "confirm_timeframe": {
            "interval": regime.confirm.interval,
            "rsi": regime.confirm.rsi,
            "trend": regime.confirm.trend,
            "momentum": regime.confirm.momentum,
        },
        "components": regime.components,
        "analyzed_at": regime.analyzed_at.isoformat(),
    }
    if snap:
        payload["enhanced_regime"] = {
            "regime": snap.regime,
            "confidence": float(snap.confidence),
            "trend_strength": float(snap.trend_strength),
            "volatility_score": float(snap.volatility_score),
            "risk_off_score": float(snap.risk_off_score),
            "reasons": snap.reasons or [],
        }
    settings = await session.get(BotSettings, "default")
    if settings:
        payload["bot_context"] = {
            "mode": settings.mode,
            "market_direction_filter_enabled": settings.market_direction_filter_enabled,
        }
    return payload


def _to_out(result: MarketAiResearchResult, *, cached: bool) -> MarketAiResearchOut:
    return MarketAiResearchOut(
        executive_summary=result.executive_summary,
        market_outlook=result.market_outlook,
        confidence_pct=result.confidence_pct,
        btc_analysis=result.btc_analysis,
        altcoin_implications=result.altcoin_implications,
        key_observations=result.key_observations,
        risk_factors=result.risk_factors,
        opportunities=result.opportunities,
        time_horizon=result.time_horizon,
        analyst_note=result.analyst_note,
        disclaimer=result.disclaimer,
        status=result.status,
        model=result.model,
        cached=cached,
        generated_at=datetime.now(timezone.utc),
    )


async def run_market_ai_research(
    session: AsyncSession,
    settings: Settings,
    redis: Redis | None,
    *,
    force_refresh: bool = False,
) -> MarketAiResearchOut:
    if not settings.ai_market_research_enabled:
        return _to_out(
            MarketAiResearchResult(
                executive_summary="Piyasa AI arastirmasi devre disi (AI_MARKET_RESEARCH_ENABLED=false).",
                market_outlook="UNCERTAIN",
                confidence_pct=0,
                btc_analysis="",
                altcoin_implications="",
                key_observations=[],
                risk_factors=["AI_MARKET_RESEARCH_ENABLED=false"],
                opportunities=[],
                time_horizon="INTRADAY",
                analyst_note="",
                disclaimer="Bu analiz yatirim tavsiyesi degildir.",
                status="DISABLED",
            ),
            cached=False,
        )

    if not settings.openai_api_key:
        return _to_out(
            MarketAiResearchResult(
                executive_summary="OpenAI API anahtari yapilandirilmamis.",
                market_outlook="UNCERTAIN",
                confidence_pct=0,
                btc_analysis="",
                altcoin_implications="",
                key_observations=[],
                risk_factors=["OPENAI_API_KEY eksik"],
                opportunities=[],
                time_horizon="INTRADAY",
                analyst_note="",
                disclaimer="Bu analiz yatirim tavsiyesi degildir.",
                status="UNAVAILABLE",
            ),
            cached=False,
        )

    bot_settings = await session.get(BotSettings, "default")

    regime = await fetch_market_regime_out(session, settings)
    payload = await _build_research_payload(session, regime)
    cache_key = market_research_cache_key(payload)
    ttl = settings.ai_market_research_cache_seconds

    if redis and not force_refresh:
        cached_raw = await redis.get(cache_key)
        if cached_raw:
            data = json.loads(cached_raw)
            result = MarketAiResearchResult(**{**data, "status": data.get("status", "OK"), "cached": True})
            out = _to_out(result, cached=True)
            return out

    model = bot_settings.ai_model if bot_settings else settings.ai_model
    timeout = int(bot_settings.ai_timeout_seconds) if bot_settings else settings.ai_timeout_seconds

    result = await generate_market_research(
        api_key=settings.openai_api_key,
        payload=payload,
        model=model,
        timeout_seconds=timeout,
    )

    out = _to_out(result, cached=False)
    if redis and result.status == "OK":
        await redis.setex(
            cache_key,
            ttl,
            json.dumps(
                {
                    "executive_summary": result.executive_summary,
                    "market_outlook": result.market_outlook,
                    "confidence_pct": result.confidence_pct,
                    "btc_analysis": result.btc_analysis,
                    "altcoin_implications": result.altcoin_implications,
                    "key_observations": result.key_observations,
                    "risk_factors": result.risk_factors,
                    "opportunities": result.opportunities,
                    "time_horizon": result.time_horizon,
                    "analyst_note": result.analyst_note,
                    "disclaimer": result.disclaimer,
                    "status": result.status,
                    "model": result.model,
                },
                ensure_ascii=False,
            ),
        )
    return out
