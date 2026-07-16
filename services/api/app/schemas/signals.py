from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisResultOut(BaseModel):
    id: str
    symbol: str
    analyzed_at: datetime
    price: Decimal
    mark_price: Decimal
    ema_fast: Decimal
    ema_mid: Decimal
    ema_slow: Decimal
    rsi_value: Decimal
    atr_value: Decimal
    trend_score: Decimal
    ema_score: Decimal
    rsi_score: Decimal
    volume_score: Decimal
    volatility_score: Decimal
    spread_score: Decimal
    funding_score: Decimal
    open_interest_score: Decimal
    total_score: Decimal
    suggested_side: str | None
    decision: str
    reason: str
    bot_mode: str

    class Config:
        from_attributes = True


class StrategySignalOut(BaseModel):
    id: str
    symbol: str
    side: str
    total_score: Decimal
    bot_mode: str
    consumed: bool
    resulting_position_id: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class ExecuteSignalRequest(BaseModel):
    entry_mode: Literal["market", "limit", "settings"] = Field(
        default="market",
        description="market: aninda piyasa emri, limit: olta, settings: bot ayarindaki olta modunu kullan",
    )


class ExecuteSignalResponse(BaseModel):
    signal_id: str
    status: Literal["opened", "limit_pending"]
    position_id: str | None = None
    order_id: str | None = None
    message: str | None = None
