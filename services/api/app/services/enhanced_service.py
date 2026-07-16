"""Enhanced decision engine API servisleri."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import (
    AiExplanation,
    BotSettings,
    LearningAnalysisRun,
    MarketRegimeSnapshot,
    ShadowDecision,
    StrategyRecommendation,
    StrategyVersion,
    SymbolPerformanceProfile,
    TradeCandidateRanking,
)
from shared.enhanced.learning_engine import run_learning_analysis
from shared.enhanced.shadow_mode import shadow_agreement_rate
from shared.enhanced.strategy_versioning import activate_strategy_version, create_strategy_version, rollback_strategy_version


async def get_current_market_regime(session: AsyncSession) -> MarketRegimeSnapshot | None:
    result = await session.execute(
        select(MarketRegimeSnapshot)
        .where(MarketRegimeSnapshot.market_scope == "GLOBAL")
        .order_by(desc(MarketRegimeSnapshot.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_regime_history(session: AsyncSession, limit: int = 50) -> list[MarketRegimeSnapshot]:
    result = await session.execute(
        select(MarketRegimeSnapshot).order_by(desc(MarketRegimeSnapshot.created_at)).limit(limit)
    )
    return list(result.scalars().all())


async def get_latest_candidates(session: AsyncSession, scan_id: str | None = None) -> list[TradeCandidateRanking]:
    if scan_id is None:
        latest = await session.scalar(
            select(TradeCandidateRanking.scan_id).order_by(desc(TradeCandidateRanking.created_at)).limit(1)
        )
        if not latest:
            return []
        scan_id = latest
    result = await session.execute(
        select(TradeCandidateRanking)
        .where(TradeCandidateRanking.scan_id == scan_id)
        .order_by(TradeCandidateRanking.rank)
    )
    return list(result.scalars().all())


async def list_symbol_profiles(session: AsyncSession) -> list[SymbolPerformanceProfile]:
    result = await session.execute(select(SymbolPerformanceProfile).order_by(SymbolPerformanceProfile.symbol))
    return list(result.scalars().all())


async def get_symbol_profile(session: AsyncSession, symbol: str) -> SymbolPerformanceProfile | None:
    return await session.get(SymbolPerformanceProfile, symbol)


async def list_learning_runs(session: AsyncSession) -> list[LearningAnalysisRun]:
    result = await session.execute(select(LearningAnalysisRun).order_by(desc(LearningAnalysisRun.started_at)))
    return list(result.scalars().all())


async def trigger_learning_run(session: AsyncSession, days: int = 30) -> LearningAnalysisRun:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    return await run_learning_analysis(session, period_start=start, period_end=end)


async def list_recommendations(session: AsyncSession, status: str | None = None) -> list[StrategyRecommendation]:
    q = select(StrategyRecommendation).order_by(desc(StrategyRecommendation.created_at))
    if status:
        q = q.where(StrategyRecommendation.status == status)
    result = await session.execute(q)
    return list(result.scalars().all())


async def approve_recommendation(session: AsyncSession, rec_id: str, admin_id: str) -> StrategyRecommendation:
    rec = await session.get(StrategyRecommendation, rec_id)
    if rec is None:
        raise ValueError("recommendation_not_found")
    rec.status = "APPROVED"
    rec.approved_by = admin_id
    rec.approved_at = datetime.now(timezone.utc)
    await session.flush()
    return rec


async def reject_recommendation(session: AsyncSession, rec_id: str, admin_id: str) -> StrategyRecommendation:
    rec = await session.get(StrategyRecommendation, rec_id)
    if rec is None:
        raise ValueError("recommendation_not_found")
    rec.status = "REJECTED"
    rec.approved_by = admin_id
    rec.approved_at = datetime.now(timezone.utc)
    await session.flush()
    return rec


async def paper_test_recommendation(session: AsyncSession, rec_id: str) -> StrategyRecommendation:
    rec = await session.get(StrategyRecommendation, rec_id)
    if rec is None:
        raise ValueError("recommendation_not_found")
    rec.status = "PAPER_TEST"
    await session.flush()
    return rec


async def list_strategy_versions(session: AsyncSession) -> list[StrategyVersion]:
    result = await session.execute(select(StrategyVersion).order_by(desc(StrategyVersion.created_at)))
    return list(result.scalars().all())


async def get_strategy_version(session: AsyncSession, version_id: str) -> StrategyVersion | None:
    return await session.get(StrategyVersion, version_id)


async def create_version_from_settings(session: AsyncSession, admin_id: str, name: str) -> StrategyVersion:
    settings = await session.get(BotSettings, "default")
    if settings is None:
        raise ValueError("settings_not_found")
    return await create_strategy_version(session, settings, name=name, created_by=admin_id)


async def get_shadow_status(session: AsyncSession) -> tuple[BotSettings, int, float]:
    settings = await session.get(BotSettings, "default")
    total = await session.scalar(select(func.count()).select_from(ShadowDecision)) or 0
    recent_result = await session.execute(select(ShadowDecision).order_by(desc(ShadowDecision.created_at)).limit(200))
    recent = list(recent_result.scalars().all())
    rate = shadow_agreement_rate(recent)
    return settings, total, rate


async def get_shadow_comparison(session: AsyncSession, limit: int = 50) -> tuple[float, list[ShadowDecision]]:
    result = await session.execute(select(ShadowDecision).order_by(desc(ShadowDecision.created_at)).limit(limit))
    decisions = list(result.scalars().all())
    rate = shadow_agreement_rate(decisions)
    return rate, decisions


async def get_ai_explanation(session: AsyncSession, signal_id: str) -> AiExplanation | None:
    result = await session.execute(select(AiExplanation).where(AiExplanation.signal_id == signal_id))
    return result.scalar_one_or_none()
