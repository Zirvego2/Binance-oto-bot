"""Binance USDS-M Futures herkese acik (public) piyasa verisi istemcisi.

API anahtari GEREKTIRMEZ. PAPER modu da dahil olmak uzere tum modlar bu
sinif uzerinden GERCEK Binance piyasa verilerini okur (sartname bolum 5:
"PAPER: Gercek Binance piyasa fiyatlarini kullan").
"""

from __future__ import annotations

from decimal import Decimal

from .rest_client import BinanceRestClient
from .types import BookTicker, Kline, MarkPriceTick, OpenInterest, ServerTime, Ticker24h


def _d(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


class PublicMarketDataClient:
    def __init__(self, rest_client: BinanceRestClient) -> None:
        self._client = rest_client

    async def get_server_time(self) -> ServerTime:
        data = await self._client.public_get("/fapi/v1/time")
        return ServerTime(server_time_ms=int(data["serverTime"]))

    async def get_exchange_info(self) -> dict:
        return await self._client.public_get("/fapi/v1/exchangeInfo")

    async def get_mark_price(self, symbol: str) -> MarkPriceTick:
        data = await self._client.public_get("/fapi/v1/premiumIndex", {"symbol": symbol})
        return self._parse_mark_price(data)

    async def get_all_mark_prices(self) -> list[MarkPriceTick]:
        data = await self._client.public_get("/fapi/v1/premiumIndex")
        return [self._parse_mark_price(item) for item in data]

    @staticmethod
    def _parse_mark_price(data: dict) -> MarkPriceTick:
        return MarkPriceTick(
            symbol=data["symbol"],
            mark_price=_d(data.get("markPrice")),
            index_price=_d(data.get("indexPrice")),
            funding_rate=_d(data.get("lastFundingRate")),
            next_funding_time_ms=int(data.get("nextFundingTime", 0)),
            time_ms=int(data.get("time", 0)),
        )

    async def get_book_ticker(self, symbol: str) -> BookTicker:
        data = await self._client.public_get("/fapi/v1/ticker/bookTicker", {"symbol": symbol})
        return BookTicker(
            symbol=data["symbol"],
            bid_price=_d(data.get("bidPrice")),
            bid_qty=_d(data.get("bidQty")),
            ask_price=_d(data.get("askPrice")),
            ask_qty=_d(data.get("askQty")),
            time_ms=int(data.get("time", 0)),
        )

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[Kline]:
        data = await self._client.public_get(
            "/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit}
        )
        klines = []
        for row in data:
            klines.append(
                Kline(
                    open_time_ms=int(row[0]),
                    open=_d(row[1]),
                    high=_d(row[2]),
                    low=_d(row[3]),
                    close=_d(row[4]),
                    volume=_d(row[5]),
                    close_time_ms=int(row[6]),
                    quote_volume=_d(row[7]),
                    is_closed=True,
                )
            )
        return klines

    async def get_24h_tickers(self) -> list[Ticker24h]:
        data = await self._client.public_get("/fapi/v1/ticker/24hr")
        return [
            Ticker24h(
                symbol=item["symbol"],
                quote_volume=_d(item.get("quoteVolume")),
                price_change_percent=_d(item.get("priceChangePercent")),
                last_price=_d(item.get("lastPrice")),
            )
            for item in data
        ]

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        data = await self._client.public_get("/fapi/v1/openInterest", {"symbol": symbol})
        return OpenInterest(
            symbol=data["symbol"], open_interest=_d(data.get("openInterest")), time_ms=int(data.get("time", 0))
        )
