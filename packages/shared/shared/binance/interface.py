"""Binance USDS-M Futures adapter arayuzu (sartname bolum 4 & 7).

Uygulamanin hicbir yeri (api, worker) dogrudan Binance endpointlerine
baglanmaz; her zaman bu arayuz uzerinden calisir. PAPER, DEMO ve LIVE
modlarinin her biri bu arayuzu ayri sekilde uygular
(``PaperFuturesAdapter``, ``LiveFuturesAdapter``).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from .types import (
    AccountBalance,
    AccountInfo,
    BookTicker,
    ConnectionTestResult,
    ExchangeOrder,
    ExchangePosition,
    IncomeRecord,
    Kline,
    LeverageBracket,
    LeverageChangeResult,
    MarginTypeChangeResult,
    MarkPriceTick,
    OpenInterest,
    PlaceAlgoOrderRequest,
    PlaceOrderRequest,
    ServerTime,
    Ticker24h,
)


class BinanceFuturesAdapter(ABC):
    """USDS-M Futures islemleri icin ortak adapter arayuzu."""

    environment: str  # "paper" | "demo" | "live"

    # --- Genel / herkese acik (public) veri ---
    @abstractmethod
    async def get_server_time(self) -> ServerTime: ...

    @abstractmethod
    async def get_exchange_info(self) -> dict: ...

    @abstractmethod
    async def get_mark_price(self, symbol: str) -> MarkPriceTick: ...

    @abstractmethod
    async def get_all_mark_prices(self) -> list[MarkPriceTick]: ...

    @abstractmethod
    async def get_book_ticker(self, symbol: str) -> BookTicker: ...

    @abstractmethod
    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[Kline]: ...

    @abstractmethod
    async def get_24h_tickers(self) -> list[Ticker24h]: ...

    @abstractmethod
    async def get_open_interest(self, symbol: str) -> OpenInterest: ...

    # --- Hesap (private, API anahtari gerektirir) ---
    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult: ...

    @abstractmethod
    async def get_account_balance(self) -> list[AccountBalance]: ...

    @abstractmethod
    async def get_account_info(self) -> AccountInfo: ...

    @abstractmethod
    async def get_open_positions(self) -> list[ExchangePosition]: ...

    @abstractmethod
    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]: ...

    @abstractmethod
    async def get_open_algo_orders(self, symbol: str | None = None) -> list[ExchangeOrder]: ...

    @abstractmethod
    async def get_income_history(
        self, symbol: str | None = None, income_type: str | None = None, limit: int = 100
    ) -> list[IncomeRecord]: ...

    @abstractmethod
    async def get_leverage_bracket(self, symbol: str) -> list[LeverageBracket]: ...

    @abstractmethod
    async def change_leverage(self, symbol: str, leverage: int) -> LeverageChangeResult: ...

    @abstractmethod
    async def change_margin_type(self, symbol: str, margin_type: str) -> MarginTypeChangeResult: ...

    @abstractmethod
    async def get_position_mode(self) -> str: ...

    @abstractmethod
    async def set_position_mode(self, hedge_mode: bool) -> None: ...

    @abstractmethod
    async def get_multi_assets_mode(self) -> bool: ...

    @abstractmethod
    async def set_multi_assets_mode(self, enabled: bool) -> None: ...

    # --- Emir yonetimi ---
    @abstractmethod
    async def place_market_order(self, request: PlaceOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def place_limit_order(self, request: PlaceOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def place_reduce_only_market_order(self, request: PlaceOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def place_stop_loss_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def place_take_profit_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder: ...

    @abstractmethod
    async def query_order(self, symbol: str, client_order_id: str) -> ExchangeOrder | None: ...

    @abstractmethod
    async def query_algo_order(self, symbol: str, client_algo_id: str) -> ExchangeOrder | None: ...

    @abstractmethod
    async def cancel_order(self, symbol: str, client_order_id: str) -> bool: ...

    @abstractmethod
    async def cancel_algo_order(self, symbol: str, client_algo_id: str) -> bool: ...

    @abstractmethod
    async def cancel_all_open_orders(self, symbol: str) -> bool: ...
