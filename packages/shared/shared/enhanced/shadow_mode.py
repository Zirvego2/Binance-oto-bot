"""Shadow mode karar karsilastirmasi — gercek emir gondermez."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import ShadowDecision
from shared.enhanced.types import CandidateMetrics, EnhancedScanResult


def build_shadow_decision(
    scan_id: str,
    *,
    current_symbol: str | None,
    current_direction: str | None,
    current_score: float | None,
    enhanced: EnhancedScanResult,
) -> ShadowDecision:
    sel = enhanced.selected
    disagreement = None
    if current_symbol != (sel.symbol if sel else None) or current_direction != (sel.direction if sel else None):
        parts = []
        if current_symbol != (sel.symbol if sel else None):
            parts.append(f"symbol:{current_symbol}->{sel.symbol if sel else 'none'}")
        if current_direction != (sel.direction if sel else None):
            parts.append(f"direction:{current_direction}->{sel.direction if sel else 'none'}")
        disagreement = ";".join(parts)

    return ShadowDecision(
        scan_id=scan_id,
        current_engine_decision="TRADE" if current_symbol else "SKIP",
        enhanced_engine_decision="TRADE" if sel else "SKIP",
        current_selected_symbol=current_symbol,
        enhanced_selected_symbol=sel.symbol if sel else None,
        current_direction=current_direction,
        enhanced_direction=sel.direction if sel else None,
        current_score=Decimal(str(current_score)) if current_score is not None else None,
        enhanced_score=Decimal(str(sel.final_opportunity_score)) if sel else None,
        enhanced_risk_score=Decimal(str(sel.risk_score)) if sel else None,
        disagreement_reason=disagreement,
        created_at=datetime.now(timezone.utc),
    )


async def persist_shadow_decision(session: AsyncSession, decision: ShadowDecision) -> None:
    session.add(decision)
    await session.flush()


def shadow_agreement_rate(decisions: list[ShadowDecision]) -> float:
    if not decisions:
        return 0.0
    same = sum(
        1
        for d in decisions
        if d.current_selected_symbol == d.enhanced_selected_symbol
        and d.current_direction == d.enhanced_direction
    )
    return same / len(decisions) * 100
