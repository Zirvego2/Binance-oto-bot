"""Enhanced decision engine API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class MarketRegimeCurrentOut(BaseModel):
    id: str | None = None
    regime: str
    confidence: float
    trend_strength: float
    volatility_score: float
    breadth_score: float
    risk_off_score: float
    reasons: list[str] = Field(default_factory=list)
    timeframe: str
    btc_direction: str | None = None
    btc_trend_strength: float | None = None
    created_at: datetime | None = None


class TradeCandidateOut(BaseModel):
    scan_id: str
    symbol: str
    direction: str
    signal_score: float
    risk_score: float
    risk_reward_ratio: float
    regime_alignment_score: float
    symbol_profile_score: float
    correlation_penalty: float
    final_opportunity_score: float
    rank: int
    selected: bool
    rejection_reason: str | None = None


class SymbolProfileOut(BaseModel):
    symbol: str
    total_trades: int
    win_rate: float
    profit_factor: float
    expectancy: float
    max_drawdown: float
    long_win_rate: float
    short_win_rate: float
    confidence_level: float
    last_calculated_at: datetime | None = None


class LearningRunOut(BaseModel):
    id: str
    period_start: datetime
    period_end: datetime
    total_trades: int
    strategy_version: str
    status: str
    summary: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class RecommendationOut(BaseModel):
    id: str
    analysis_run_id: str
    recommendation_type: str
    target_scope: str
    target_symbol: str | None = None
    target_regime: str | None = None
    current_value: dict[str, Any] | None = None
    recommended_value: dict[str, Any] | None = None
    expected_impact: str | None = None
    confidence: float
    status: str
    created_at: datetime


class StrategyVersionOut(BaseModel):
    id: str
    version: str
    name: str
    description: str | None = None
    source: str
    active_in_paper: bool
    active_in_demo: bool
    active_in_live: bool
    created_at: datetime


class ShadowStatusOut(BaseModel):
    shadow_mode_active: bool
    enhanced_engine_shadow_mode: bool
    enhanced_engine_live_enabled: bool
    total_decisions: int
    agreement_rate_pct: float


class ShadowComparisonOut(BaseModel):
    agreement_rate_pct: float
    disagreement_rate_pct: float
    total_decisions: int
    recent: list[dict[str, Any]]


class AiExplanationOut(BaseModel):
    signal_id: str
    symbol: str
    status: str
    summary: str | None = None
    positive_factors: list[str] = Field(default_factory=list)
    negative_factors: list[str] = Field(default_factory=list)
    risk_level: str | None = None
    warnings: list[str] = Field(default_factory=list)
    suggestion: str | None = None


class ActivateStrategyRequest(BaseModel):
    confirmation_text: str | None = None


class LiveEnhancedActivateRequest(BaseModel):
    confirmation_text: str = Field(..., min_length=1)
