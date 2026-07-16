"""Ogrenme analitik motoru — yalnizca oneri uretir, otomatik uygulamaz."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import LearningAnalysisRun, StrategyRecommendation, Trade


async def run_learning_analysis(
    session: AsyncSession,
    *,
    period_start: datetime,
    period_end: datetime,
    strategy_version: str = "default",
    min_sample: int = 5,
) -> LearningAnalysisRun:
    run = LearningAnalysisRun(
        id=str(uuid.uuid4()),
        period_start=period_start,
        period_end=period_end,
        strategy_version=strategy_version,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.flush()

    result = await session.execute(
        select(Trade).where(
            Trade.closed_at >= period_start,
            Trade.closed_at <= period_end,
        )
    )
    trades = list(result.scalars().all())
    run.total_trades = len(trades)

    recommendations: list[StrategyRecommendation] = []
    by_symbol: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_symbol[t.symbol].append(t)

    for symbol, sym_trades in by_symbol.items():
        if len(sym_trades) < min_sample:
            continue
        wins = sum(1 for t in sym_trades if t.net_pnl_usdt > 0)
        win_rate = wins / len(sym_trades) * 100
        if win_rate < 35:
            recommendations.append(
                StrategyRecommendation(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    recommendation_type="SYMBOL_CAUTION",
                    target_scope="SYMBOL",
                    target_symbol=symbol,
                    current_value={"win_rate": win_rate, "trades": len(sym_trades)},
                    recommended_value={"action": "review_or_reduce_exposure"},
                    expected_impact="Dusuk basari oranli coin icin islem frekansini azalt",
                    confidence=Decimal(str(min(90, 100 - win_rate))),
                    evidence={"sample_size": len(sym_trades), "win_rate": win_rate},
                    status="PENDING",
                    created_at=datetime.now(timezone.utc),
                )
            )
        elif win_rate >= 65:
            recommendations.append(
                StrategyRecommendation(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    recommendation_type="SYMBOL_STRENGTH",
                    target_scope="SYMBOL",
                    target_symbol=symbol,
                    current_value={"win_rate": win_rate, "trades": len(sym_trades)},
                    recommended_value={"action": "monitor_for_increased_weight"},
                    expected_impact="Yuksek basari orani — shadow modda agirlik artisi degerlendirilebilir",
                    confidence=Decimal(str(min(85, win_rate))),
                    evidence={"sample_size": len(sym_trades), "win_rate": win_rate},
                    status="PENDING",
                    created_at=datetime.now(timezone.utc),
                )
            )

    long_trades = [t for t in trades if t.side == "LONG"]
    if len(long_trades) >= min_sample:
        long_wins = sum(1 for t in long_trades if t.net_pnl_usdt > 0)
        long_wr = long_wins / len(long_trades) * 100
        if long_wr < 40:
            recommendations.append(
                StrategyRecommendation(
                    id=str(uuid.uuid4()),
                    analysis_run_id=run.id,
                    recommendation_type="DIRECTION_REVIEW",
                    target_scope="GLOBAL",
                    target_regime=None,
                    current_value={"direction": "LONG", "win_rate": long_wr},
                    recommended_value={"min_signal_score_increase": 5},
                    expected_impact="LONG islemlerde minimum sinyal esigini artirmayi dusunun",
                    confidence=Decimal("60"),
                    evidence={"sample_size": len(long_trades)},
                    status="PENDING",
                    created_at=datetime.now(timezone.utc),
                )
            )

    for rec in recommendations:
        session.add(rec)

    run.status = "COMPLETED"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        "total_trades": len(trades),
        "recommendations_created": len(recommendations),
        "symbols_analyzed": len(by_symbol),
    }
    await session.flush()
    return run


def recommendation_must_not_auto_apply(rec: StrategyRecommendation) -> bool:
    """Oneriler otomatik uygulanmaz — admin onayi gerekir."""
    return rec.status in ("PENDING", "REJECTED") or rec.approved_by is None
