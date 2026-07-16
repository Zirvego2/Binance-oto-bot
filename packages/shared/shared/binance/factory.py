"""Bot moduna (paper/demo/live) gore dogru Binance adapter'ini olusturur.

DEMO ve LIVE ayri API anahtarlari ve ayri base URL kullanir; hicbir kod
yolu bu ikisini birbirine karistiramaz (sartname bolum 5 & 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .interface import BinanceFuturesAdapter
from .live_adapter import LiveFuturesAdapter
from .paper_adapter import PaperFuturesAdapter


@dataclass(frozen=True, slots=True)
class BinanceAdapterConfig:
    binance_env: str  # paper | demo | live

    live_base_url: str
    live_api_key: str
    live_api_secret: str

    demo_base_url: str
    demo_api_key: str
    demo_api_secret: str

    paper_market_base_url: str
    paper_start_balance_usdt: Decimal
    paper_taker_commission_rate: Decimal


def build_adapter(config: BinanceAdapterConfig) -> BinanceFuturesAdapter:
    if config.binance_env == "paper":
        return PaperFuturesAdapter(
            market_base_url=config.paper_market_base_url,
            starting_balance_usdt=config.paper_start_balance_usdt,
            taker_commission_rate=config.paper_taker_commission_rate,
        )
    if config.binance_env == "demo":
        return LiveFuturesAdapter(
            environment="demo",
            base_url=config.demo_base_url,
            api_key=config.demo_api_key,
            api_secret=config.demo_api_secret,
        )
    if config.binance_env == "live":
        return LiveFuturesAdapter(
            environment="live",
            base_url=config.live_base_url,
            api_key=config.live_api_key,
            api_secret=config.live_api_secret,
        )
    raise ValueError(f"Gecersiz BINANCE_ENV degeri: {config.binance_env}")
