from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AvciCoinOut(BaseModel):
    symbol: str
    last_price: float
    change_pct: float
    quote_volume_usdt: float


class AvciScanOut(BaseModel):
    analyzed_at: datetime
    top_gainers: list[AvciCoinOut]
    top_losers: list[AvciCoinOut]
    limit: int


class AvciOpenRequest(BaseModel):
    symbol: str = Field(min_length=5, max_length=32)
    side: Literal["LONG", "SHORT"]


class AvciOpenOut(BaseModel):
    symbol: str
    side: str
    position_id: str
    message: str
    status: str = "OPEN"


class AvciKlineOut(BaseModel):
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class AvciChartOut(BaseModel):
    symbol: str
    interval: str
    hours: int
    change_pct: float
    last_price: float
    klines: list[AvciKlineOut]
