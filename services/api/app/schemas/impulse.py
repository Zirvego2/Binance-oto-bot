from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


ImpulseMode = Literal["OFF", "MANUAL", "AUTO"]
ImpulseSide = Literal["LONG", "SHORT"]


class ImpulseCandidateOut(BaseModel):
    symbol: str
    side: str
    score: float
    rsi: float
    proximity_pct: float
    volume_ratio: float
    price: float
    reason: str


class ImpulseSettingsOut(BaseModel):
    impulse_mode: ImpulseMode
    impulse_btc_min_change_pct: Decimal
    impulse_lookback_minutes: int
    impulse_extreme_min_score: Decimal
    impulse_max_entries: int
    impulse_margin_usdt: Decimal
    impulse_leverage: int
    impulse_tp_roi_pct: Decimal
    impulse_sl_roi_pct: Decimal
    impulse_cooldown_minutes: int
    impulse_top_n_scan: int
    impulse_rsi_overbought: Decimal
    impulse_rsi_oversold: Decimal
    impulse_check_interval_seconds: int

    impulse_last_event_at: str | None = None
    impulse_last_direction: str | None = None
    impulse_last_btc_change_pct: Decimal | None = None
    impulse_last_opened_count: int = 0
    impulse_last_scan_at: str | None = None

    class Config:
        from_attributes = True


class ImpulseSettingsUpdate(BaseModel):
    impulse_mode: ImpulseMode | None = None
    impulse_btc_min_change_pct: Decimal | None = Field(default=None, gt=0, le=10)
    impulse_lookback_minutes: int | None = Field(default=None, ge=1, le=30)
    impulse_extreme_min_score: Decimal | None = Field(default=None, ge=0, le=100)
    impulse_max_entries: int | None = Field(default=None, ge=1, le=10)
    impulse_margin_usdt: Decimal | None = Field(default=None, gt=0)
    impulse_leverage: int | None = Field(default=None, ge=0, le=20)
    impulse_tp_roi_pct: Decimal | None = Field(default=None, gt=0, le=100)
    impulse_sl_roi_pct: Decimal | None = Field(default=None, gt=0, le=100)
    impulse_cooldown_minutes: int | None = Field(default=None, ge=0, le=1440)
    impulse_top_n_scan: int | None = Field(default=None, ge=5, le=100)
    impulse_rsi_overbought: Decimal | None = Field(default=None, ge=50, le=100)
    impulse_rsi_oversold: Decimal | None = Field(default=None, ge=0, le=50)
    impulse_check_interval_seconds: int | None = Field(default=None, ge=5, le=300)


class ImpulseScanOut(BaseModel):
    btc_direction: str
    btc_change_pct: float
    counter_side: str | None
    cooldown_active: bool
    message: str
    candidates: list[ImpulseCandidateOut]


class ImpulseExecuteRequest(BaseModel):
    side: ImpulseSide | None = None
    symbols: list[str] | None = None
    max_entries: int | None = Field(default=None, ge=1, le=10)


class ImpulseExecuteOut(BaseModel):
    opened: list[str]
    skipped: list[str]
    failed: list[str]
    btc_direction: str
    btc_change_pct: float
    message: str
