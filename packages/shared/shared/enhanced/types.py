"""Gelismis karar motoru tipleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class MarketRegimeType(str, Enum):
    STRONG_UPTREND = "STRONG_UPTREND"
    WEAK_UPTREND = "WEAK_UPTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    WEAK_DOWNTREND = "WEAK_DOWNTREND"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    BREAKOUT = "BREAKOUT"
    BREAKDOWN = "BREAKDOWN"
    RISK_OFF = "RISK_OFF"
    UNKNOWN = "UNKNOWN"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class RegimeResult:
    regime: MarketRegimeType
    confidence: float
    trend_strength: float
    volatility_score: float
    breadth_score: float
    risk_off_score: float
    reasons: list[str]
    timeframe: str
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    calculated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RiskScoreResult:
    risk_score: float
    risk_level: RiskLevel
    risk_reasons: list[str]
    blocking_reasons: list[str]
    recommended_max_leverage: int
    recommended_margin_multiplier: Decimal
    recommended_action: str


@dataclass(frozen=True, slots=True)
class RiskRewardResult:
    estimated_profit_usdt: Decimal
    estimated_loss_usdt: Decimal
    net_expected_profit_usdt: Decimal
    net_expected_loss_usdt: Decimal
    risk_reward_ratio: Decimal
    break_even_win_rate: Decimal
    expected_value_usdt: Decimal
    entry_price: Decimal
    stop_loss_price: Decimal
    take_profit_price: Decimal


@dataclass(frozen=True, slots=True)
class CandidateMetrics:
    symbol: str
    direction: str
    signal_score: float
    risk_score: float
    expected_reward_score: float
    expected_loss_score: float
    risk_reward_ratio: float
    regime_alignment_score: float
    symbol_profile_score: float
    liquidity_score: float
    correlation_penalty: float
    final_opportunity_score: float
    rank: int
    selected: bool
    rejection_reason: str | None
    risk_level: RiskLevel
    blocking_reasons: list[str]


@dataclass(frozen=True, slots=True)
class EnhancedScanResult:
    scan_id: str
    market_regime: RegimeResult
    btc_mtf: dict[str, Any]
    candidates: list[CandidateMetrics]
    selected: CandidateMetrics | None
    shadow_only: bool
    strategy_version_id: str | None
