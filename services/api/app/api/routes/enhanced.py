"""Gelismis karar motoru API endpointleri."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import Admin, BotSettings, TradeCandidateRanking

from ...core.database import get_db
from ...schemas.enhanced import (
    ActivateStrategyRequest,
    AiExplanationOut,
    LearningRunOut,
    MarketRegimeCurrentOut,
    RecommendationOut,
    ShadowComparisonOut,
    ShadowStatusOut,
    StrategyVersionOut,
    SymbolProfileOut,
    TradeCandidateOut,
)
from ...services.enhanced_service import (
    approve_recommendation,
    create_version_from_settings,
    get_ai_explanation,
    get_current_market_regime,
    get_latest_candidates,
    get_regime_history,
    get_shadow_comparison,
    get_shadow_status,
    get_strategy_version,
    get_symbol_profile,
    list_learning_runs,
    list_recommendations,
    list_strategy_versions,
    list_symbol_profiles,
    paper_test_recommendation,
    reject_recommendation,
    trigger_learning_run,
)
from ...services.enhanced_service import activate_strategy_version as activate_sv
from shared.enhanced.strategy_versioning import rollback_strategy_version as rollback_sv
from ..deps import get_current_admin, require_csrf, require_platform_admin

router = APIRouter(tags=["enhanced"])


@router.get("/market-regime/current", response_model=MarketRegimeCurrentOut)
async def market_regime_current(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> MarketRegimeCurrentOut:
    row = await get_current_market_regime(session)
    if row is None:
        return MarketRegimeCurrentOut(
            regime="UNKNOWN", confidence=0, trend_strength=0, volatility_score=0,
            breadth_score=0, risk_off_score=0, timeframe="5m",
        )
    return MarketRegimeCurrentOut(
        id=row.id,
        regime=row.regime,
        confidence=float(row.confidence),
        trend_strength=float(row.trend_strength),
        volatility_score=float(row.volatility_score),
        breadth_score=float(row.breadth_score),
        risk_off_score=float(row.risk_off_score),
        reasons=row.reasons or [],
        timeframe=row.timeframe,
        created_at=row.created_at,
    )


@router.get("/market-regime/history", response_model=list[MarketRegimeCurrentOut])
async def market_regime_history(
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[MarketRegimeCurrentOut]:
    rows = await get_regime_history(session, limit=limit)
    return [
        MarketRegimeCurrentOut(
            id=r.id, regime=r.regime, confidence=float(r.confidence),
            trend_strength=float(r.trend_strength), volatility_score=float(r.volatility_score),
            breadth_score=float(r.breadth_score), risk_off_score=float(r.risk_off_score),
            reasons=r.reasons or [], timeframe=r.timeframe, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/trade-candidates", response_model=list[TradeCandidateOut])
async def trade_candidates(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[TradeCandidateOut]:
    rows = await get_latest_candidates(session)
    return [_candidate_out(r) for r in rows]


@router.get("/trade-candidates/{scan_id}", response_model=list[TradeCandidateOut])
async def trade_candidates_by_scan(
    scan_id: str,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[TradeCandidateOut]:
    rows = await get_latest_candidates(session, scan_id=scan_id)
    return [_candidate_out(r) for r in rows]


def _candidate_out(r) -> TradeCandidateOut:
    return TradeCandidateOut(
        scan_id=r.scan_id, symbol=r.symbol, direction=r.direction,
        signal_score=float(r.signal_score), risk_score=float(r.risk_score),
        risk_reward_ratio=float(r.risk_reward_ratio),
        regime_alignment_score=float(r.regime_alignment_score),
        symbol_profile_score=float(r.symbol_profile_score),
        correlation_penalty=float(r.correlation_penalty),
        final_opportunity_score=float(r.final_opportunity_score),
        rank=r.rank, selected=r.selected, rejection_reason=r.rejection_reason,
    )


@router.get("/symbol-profiles", response_model=list[SymbolProfileOut])
async def symbol_profiles(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[SymbolProfileOut]:
    rows = await list_symbol_profiles(session)
    return [_profile_out(r) for r in rows]


@router.get("/symbol-profiles/{symbol}", response_model=SymbolProfileOut)
async def symbol_profile_detail(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> SymbolProfileOut:
    row = await get_symbol_profile(session, symbol.upper())
    if row is None:
        raise HTTPException(status_code=404, detail="Profil bulunamadi")
    return _profile_out(row)


def _profile_out(r) -> SymbolProfileOut:
    return SymbolProfileOut(
        symbol=r.symbol, total_trades=r.total_trades, win_rate=float(r.win_rate),
        profit_factor=float(r.profit_factor), expectancy=float(r.expectancy),
        max_drawdown=float(r.max_drawdown), long_win_rate=float(r.long_win_rate),
        short_win_rate=float(r.short_win_rate), confidence_level=float(r.confidence_level),
        last_calculated_at=r.last_calculated_at,
    )


@router.get("/learning/analysis-runs", response_model=list[LearningRunOut])
async def learning_analysis_runs(
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[LearningRunOut]:
    rows = await list_learning_runs(session)
    return [LearningRunOut.model_validate(r) for r in rows]


@router.post("/learning/run", response_model=LearningRunOut, dependencies=[Depends(require_csrf)])
async def learning_run(
    days: int = 30,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> LearningRunOut:
    run = await trigger_learning_run(session, days=days)
    return LearningRunOut.model_validate(run)


@router.get("/learning/recommendations", response_model=list[RecommendationOut])
async def learning_recommendations(
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
) -> list[RecommendationOut]:
    rows = await list_recommendations(session, status=status)
    return [RecommendationOut.model_validate(r) for r in rows]


@router.post("/learning/recommendations/{rec_id}/approve", response_model=RecommendationOut, dependencies=[Depends(require_csrf)])
async def approve_rec(rec_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        rec = await approve_recommendation(session, rec_id, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RecommendationOut.model_validate(rec)


@router.post("/learning/recommendations/{rec_id}/reject", response_model=RecommendationOut, dependencies=[Depends(require_csrf)])
async def reject_rec(rec_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        rec = await reject_recommendation(session, rec_id, admin.id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RecommendationOut.model_validate(rec)


@router.post("/learning/recommendations/{rec_id}/paper-test", response_model=RecommendationOut, dependencies=[Depends(require_csrf)])
async def paper_test_rec(rec_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        rec = await paper_test_recommendation(session, rec_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return RecommendationOut.model_validate(rec)


@router.get("/strategy-versions", response_model=list[StrategyVersionOut])
async def strategy_versions(session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    rows = await list_strategy_versions(session)
    return [StrategyVersionOut.model_validate(r) for r in rows]


@router.get("/strategy-versions/{version_id}", response_model=StrategyVersionOut)
async def strategy_version_detail(version_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    row = await get_strategy_version(session, version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Versiyon bulunamadi")
    return StrategyVersionOut.model_validate(row)


@router.post("/strategy-versions/create", response_model=StrategyVersionOut, dependencies=[Depends(require_csrf)])
async def create_strategy_version_endpoint(name: str = "Manual snapshot", session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    sv = await create_version_from_settings(session, admin.id, name)
    return StrategyVersionOut.model_validate(sv)


@router.post("/strategy-versions/{version_id}/activate-paper", response_model=StrategyVersionOut, dependencies=[Depends(require_csrf)])
async def activate_paper(version_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        sv = await activate_sv(session, version_id, mode="paper", admin_id=admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StrategyVersionOut.model_validate(sv)


@router.post("/strategy-versions/{version_id}/activate-demo", response_model=StrategyVersionOut, dependencies=[Depends(require_csrf)])
async def activate_demo(version_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        sv = await activate_sv(session, version_id, mode="demo", admin_id=admin.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StrategyVersionOut.model_validate(sv)


@router.post("/strategy-versions/{version_id}/activate-live", response_model=StrategyVersionOut, dependencies=[Depends(require_csrf)])
async def activate_live(
    version_id: str,
    payload: ActivateStrategyRequest,
    session: AsyncSession = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    try:
        sv = await activate_sv(
            session, version_id, mode="live", admin_id=admin.id,
            confirmation_text=payload.confirmation_text,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StrategyVersionOut.model_validate(sv)


@router.post("/strategy-versions/{version_id}/rollback", response_model=StrategyVersionOut, dependencies=[Depends(require_csrf)])
async def rollback_version(version_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    try:
        sv = await rollback_sv(session, version_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return StrategyVersionOut.model_validate(sv)


@router.get("/shadow-mode/status", response_model=ShadowStatusOut)
async def shadow_status(session: AsyncSession = Depends(get_db), _admin=Depends(require_platform_admin)):
    settings, total, rate = await get_shadow_status(session)
    return ShadowStatusOut(
        shadow_mode_active=bool(settings.shadow_mode_active) if settings else True,
        enhanced_engine_shadow_mode=bool(settings.enhanced_engine_shadow_mode) if settings else True,
        enhanced_engine_live_enabled=bool(settings.enhanced_engine_live_enabled) if settings else False,
        total_decisions=total,
        agreement_rate_pct=rate,
    )


@router.post("/shadow-mode/start", dependencies=[Depends(require_csrf)])
async def shadow_start(session: AsyncSession = Depends(get_db), _admin=Depends(require_platform_admin)):
    settings = await session.get(BotSettings, "default")
    if settings:
        settings.shadow_mode_active = True
        settings.enhanced_engine_shadow_mode = True
        await session.commit()
    return {"ok": True}


@router.post("/shadow-mode/stop", dependencies=[Depends(require_csrf)])
async def shadow_stop(session: AsyncSession = Depends(get_db), _admin=Depends(require_platform_admin)):
    settings = await session.get(BotSettings, "default")
    if settings:
        settings.shadow_mode_active = False
        await session.commit()
    return {"ok": True}


@router.get("/shadow-mode/comparison", response_model=ShadowComparisonOut)
async def shadow_comparison(session: AsyncSession = Depends(get_db), _admin=Depends(require_platform_admin)):
    rate, decisions = await get_shadow_comparison(session)
    return ShadowComparisonOut(
        agreement_rate_pct=rate,
        disagreement_rate_pct=100 - rate if decisions else 0,
        total_decisions=len(decisions),
        recent=[
            {
                "scan_id": d.scan_id,
                "current": d.current_selected_symbol,
                "enhanced": d.enhanced_selected_symbol,
                "disagreement": d.disagreement_reason,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in decisions[:20]
        ],
    )


@router.get("/ai-explanations/{signal_id}", response_model=AiExplanationOut)
async def ai_explanation(signal_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    row = await get_ai_explanation(session, signal_id)
    if row is None:
        return AiExplanationOut(signal_id=signal_id, symbol="", status="UNAVAILABLE", summary="Kullanilamiyor")
    return AiExplanationOut(
        signal_id=row.signal_id, symbol=row.symbol, status=row.status, summary=row.summary,
        positive_factors=row.positive_factors or [], negative_factors=row.negative_factors or [],
        risk_level=row.risk_level, warnings=row.warnings or [], suggestion=row.suggestion,
    )


@router.get("/risk-analysis/{signal_id}")
async def risk_analysis(signal_id: str, session: AsyncSession = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    from shared.db import StrategySignal

    signal = await session.get(StrategySignal, signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail="Sinyal bulunamadi")
    ranking = await session.scalar(
        select(TradeCandidateRanking)
        .where(TradeCandidateRanking.symbol == signal.symbol)
        .order_by(desc(TradeCandidateRanking.created_at))
        .limit(1)
    )
    if ranking is None:
        return {
            "signal_id": signal_id,
            "symbol": signal.symbol,
            "risk_score": float(signal.risk_score) if signal.risk_score else None,
            "message": "Detayli risk analizi henuz kaydedilmedi",
        }
    return {
        "signal_id": signal_id,
        "symbol": signal.symbol,
        "direction": signal.side,
        "signal_score": float(ranking.signal_score),
        "risk_score": float(ranking.risk_score),
        "risk_reward_ratio": float(ranking.risk_reward_ratio),
        "risk_level": "HIGH" if float(ranking.risk_score) >= 65 else "MEDIUM" if float(ranking.risk_score) >= 40 else "LOW",
        "blocking_reasons": [],
        "recommended_max_leverage": max(1, int(7 * (1 - float(ranking.risk_score) / 120))),
    }
