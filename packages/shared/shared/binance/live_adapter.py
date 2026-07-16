"""Gercek Binance USDS-M Futures adapter'i (DEMO/testnet ve LIVE icin kullanilir).

DEMO ve LIVE tamamen ayri ``base_url`` ve API anahtari ile olusturulur
(bkz. ``factory.py``); hicbir zaman ayni environment bilgisi paylasilmaz.

2025-12-09'dan itibaren STOP_MARKET / TAKE_PROFIT_MARKET / TRAILING_STOP_MARKET
emirleri yalnizca Algo Order API uzerinden kabul edilir (``/fapi/v1/algoOrder``).
Eski ``/fapi/v1/order`` endpointi -4120 hatasi dondurur.
"""

from __future__ import annotations

from decimal import Decimal

from ..decimal_utils import format_decimal_plain
from .errors import BinanceApiError, LeverageNotConfirmedError
from .interface import BinanceFuturesAdapter
from .market_data import PublicMarketDataClient
from .rest_client import BinanceRestClient
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

ALGO_ORDER_TYPES = {"STOP_MARKET", "TAKE_PROFIT_MARKET", "TRAILING_STOP_MARKET"}


def _d(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _to_exchange_order(raw: dict) -> ExchangeOrder:
    return ExchangeOrder(
        symbol=raw["symbol"],
        binance_order_id=str(raw.get("orderId", "")),
        client_order_id=raw.get("clientOrderId", ""),
        side=raw.get("side", ""),
        order_type=raw.get("type", raw.get("origType", "")),
        status=raw.get("status", "UNKNOWN"),
        price=_d(raw.get("price")),
        orig_qty=_d(raw.get("origQty")),
        executed_qty=_d(raw.get("executedQty")),
        avg_price=_d(raw.get("avgPrice")),
        reduce_only=bool(raw.get("reduceOnly", False)),
        close_position=bool(raw.get("closePosition", False)),
        stop_price=_d(raw.get("stopPrice")) if raw.get("stopPrice") is not None else None,
        working_type=raw.get("workingType"),
        time_ms=int(raw.get("updateTime") or raw.get("time") or 0),
    )


def _normalize_algo_status(algo_status: str) -> str:
    """Algo emir durumunu standart emir durumuna cevirir."""
    if algo_status in ("TRIGGERED", "FINISHED"):
        return "FILLED"
    if algo_status == "NEW":
        return "NEW"
    if algo_status in ("CANCELED", "EXPIRED"):
        return "CANCELED"
    return algo_status or "UNKNOWN"


def _to_algo_exchange_order(raw: dict) -> ExchangeOrder:
    actual_price = raw.get("actualPrice")
    avg_price = _d(actual_price) if actual_price not in (None, "", "0", "0.00000") else Decimal("0")
    return ExchangeOrder(
        symbol=raw["symbol"],
        binance_order_id=str(raw.get("algoId", raw.get("orderId", ""))),
        client_order_id=raw.get("clientAlgoId", raw.get("clientOrderId", "")),
        side=raw.get("side", ""),
        order_type=raw.get("orderType", raw.get("type", "")),
        status=_normalize_algo_status(raw.get("algoStatus", raw.get("status", "UNKNOWN"))),
        price=_d(raw.get("price")),
        orig_qty=_d(raw.get("quantity", raw.get("origQty"))),
        executed_qty=_d(raw.get("actualQty", raw.get("executedQty"))),
        avg_price=avg_price,
        reduce_only=bool(raw.get("reduceOnly", False)),
        close_position=str(raw.get("closePosition", "")).lower() == "true",
        stop_price=_d(raw.get("triggerPrice")) if raw.get("triggerPrice") is not None else None,
        working_type=raw.get("workingType"),
        time_ms=int(raw.get("updateTime") or raw.get("createTime") or raw.get("time") or 0),
    )


class LiveFuturesAdapter(BinanceFuturesAdapter):
    """DEMO (testnet) ve LIVE (production) icin ortak gercek adapter."""

    def __init__(self, environment: str, base_url: str, api_key: str, api_secret: str) -> None:
        if environment not in ("demo", "live"):
            raise ValueError("LiveFuturesAdapter sadece 'demo' veya 'live' icin kullanilabilir")
        self.environment = environment
        self._client = BinanceRestClient(base_url=base_url, api_key=api_key, api_secret=api_secret)
        self._market_data = PublicMarketDataClient(self._client)

    async def close(self) -> None:
        await self._client.close()

    # --- Genel / herkese acik veri (PublicMarketDataClient'a devredilir) ---
    async def get_server_time(self) -> ServerTime:
        return await self._market_data.get_server_time()

    async def get_exchange_info(self) -> dict:
        return await self._market_data.get_exchange_info()

    async def get_mark_price(self, symbol: str) -> MarkPriceTick:
        return await self._market_data.get_mark_price(symbol)

    async def get_all_mark_prices(self) -> list[MarkPriceTick]:
        return await self._market_data.get_all_mark_prices()

    async def get_book_ticker(self, symbol: str) -> BookTicker:
        return await self._market_data.get_book_ticker(symbol)

    async def get_klines(self, symbol: str, interval: str, limit: int = 100) -> list[Kline]:
        return await self._market_data.get_klines(symbol, interval, limit)

    async def get_24h_tickers(self) -> list[Ticker24h]:
        return await self._market_data.get_24h_tickers()

    async def get_open_interest(self, symbol: str) -> OpenInterest:
        return await self._market_data.get_open_interest(symbol)

    # --- Hesap ---
    async def test_connection(self) -> ConnectionTestResult:
        if not self._client.is_configured:
            return ConnectionTestResult(
                is_configured=False,
                is_connected=False,
                account_access_ok=False,
                futures_account_usable=False,
                trading_permission_ok=False,
                error_message="Binance API bilgileri henuz eklenmedi",
            )
        try:
            await self._client.sync_server_time()
            account = await self.get_account_info()
            await self.get_account_balance()
            return ConnectionTestResult(
                is_configured=True,
                is_connected=True,
                account_access_ok=True,
                futures_account_usable=True,
                trading_permission_ok=account.can_trade,
                error_message=None,
            )
        except BinanceApiError as exc:
            return ConnectionTestResult(
                is_configured=True,
                is_connected=True,
                account_access_ok=False,
                futures_account_usable=False,
                trading_permission_ok=False,
                error_message=exc.message,
            )
        except Exception as exc:  # pragma: no cover - savunma amacli genel hata yakalama
            return ConnectionTestResult(
                is_configured=True,
                is_connected=False,
                account_access_ok=False,
                futures_account_usable=False,
                trading_permission_ok=False,
                error_message=str(exc),
            )

    async def get_account_balance(self) -> list[AccountBalance]:
        data = await self._client.signed_get("/fapi/v2/balance")
        return [
            AccountBalance(
                asset=item["asset"],
                wallet_balance=_d(item.get("balance")),
                available_balance=_d(item.get("availableBalance")),
                unrealized_pnl=_d(item.get("crossUnPnl")),
            )
            for item in data
        ]

    async def get_account_info(self) -> AccountInfo:
        data = await self._client.signed_get("/fapi/v2/account")
        return AccountInfo(
            total_wallet_balance=_d(data.get("totalWalletBalance")),
            total_unrealized_pnl=_d(data.get("totalUnrealizedProfit")),
            total_margin_balance=_d(data.get("totalMarginBalance")),
            available_balance=_d(data.get("availableBalance")),
            total_maint_margin=_d(data.get("totalMaintMargin")),
            can_trade=bool(data.get("canTrade", False)),
            multi_assets_margin=bool(data.get("multiAssetsMargin", False)),
        )

    async def get_open_positions(self) -> list[ExchangePosition]:
        data = await self._client.signed_get("/fapi/v2/positionRisk")
        positions = []
        for item in data:
            qty = _d(item.get("positionAmt"))
            if qty == 0:
                continue
            positions.append(
                ExchangePosition(
                    symbol=item["symbol"],
                    position_side=item.get("positionSide", "BOTH"),
                    quantity=qty,
                    entry_price=_d(item.get("entryPrice")),
                    mark_price=_d(item.get("markPrice")),
                    unrealized_pnl=_d(item.get("unRealizedProfit")),
                    leverage=int(item.get("leverage", 1)),
                    margin_type=item.get("marginType", "isolated").upper(),
                    liquidation_price=_d(item.get("liquidationPrice")),
                    isolated_margin=_d(item.get("isolatedMargin")),
                )
            )
        return positions

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        data = await self._client.signed_get("/fapi/v1/openOrders", {"symbol": symbol})
        orders = [_to_exchange_order(row) for row in data]
        return [o for o in orders if o.order_type not in ALGO_ORDER_TYPES]

    async def get_open_algo_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        params: dict = {"algoType": "CONDITIONAL"}
        if symbol:
            params["symbol"] = symbol
        data = await self._client.signed_get("/fapi/v1/openAlgoOrders", params)
        rows = data if isinstance(data, list) else data.get("orders", [])
        return [_to_algo_exchange_order(row) for row in rows]

    async def get_income_history(
        self, symbol: str | None = None, income_type: str | None = None, limit: int = 100
    ) -> list[IncomeRecord]:
        params = {"symbol": symbol, "incomeType": income_type, "limit": limit}
        data = await self._client.signed_get("/fapi/v1/income", params)
        return [
            IncomeRecord(
                symbol=item.get("symbol") or None,
                income_type=item.get("incomeType", "UNKNOWN"),
                income=_d(item.get("income")),
                asset=item.get("asset", "USDT"),
                time_ms=int(item.get("time", 0)),
            )
            for item in data
        ]

    async def get_leverage_bracket(self, symbol: str) -> list[LeverageBracket]:
        data = await self._client.signed_get("/fapi/v1/leverageBracket", {"symbol": symbol})
        brackets_raw = data[0]["brackets"] if data else []
        return [
            LeverageBracket(
                bracket=int(b["bracket"]),
                initial_leverage=int(b["initialLeverage"]),
                notional_cap=_d(b.get("notionalCap")),
                notional_floor=_d(b.get("notionalFloor")),
                maint_margin_ratio=_d(b.get("maintMarginRatio")),
            )
            for b in brackets_raw
        ]

    async def change_leverage(self, symbol: str, leverage: int) -> LeverageChangeResult:
        data = await self._client.signed_post("/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})
        result = LeverageChangeResult(
            symbol=data["symbol"], leverage=int(data["leverage"]), max_notional_value=_d(data.get("maxNotionalValue"))
        )
        if result.leverage != leverage:
            raise LeverageNotConfirmedError(
                f"{symbol} icin istenen kaldirac {leverage}x, Binance {result.leverage}x dondu"
            )
        return result

    async def change_margin_type(self, symbol: str, margin_type: str) -> MarginTypeChangeResult:
        try:
            await self._client.signed_post("/fapi/v1/marginType", {"symbol": symbol, "marginType": margin_type})
            return MarginTypeChangeResult(symbol=symbol, margin_type=margin_type, already_set=False)
        except BinanceApiError as exc:
            # -4046 "No need to change margin type" -> zaten istenen tipte, hata degil
            if exc.code == -4046:
                return MarginTypeChangeResult(symbol=symbol, margin_type=margin_type, already_set=True)
            raise

    async def get_position_mode(self) -> str:
        data = await self._client.signed_get("/fapi/v1/positionSide/dual")
        return "HEDGE" if data.get("dualSidePosition") else "ONE_WAY"

    async def set_position_mode(self, hedge_mode: bool) -> None:
        await self._client.signed_post("/fapi/v1/positionSide/dual", {"dualSidePosition": str(hedge_mode).lower()})

    async def get_multi_assets_mode(self) -> bool:
        data = await self._client.signed_get("/fapi/v1/multiAssetsMargin")
        return bool(data.get("multiAssetsMargin", False))

    async def set_multi_assets_mode(self, enabled: bool) -> None:
        await self._client.signed_post("/fapi/v1/multiAssetsMargin", {"multiAssetsMargin": str(enabled).lower()})

    # --- Emir yonetimi ---
    async def place_market_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        params = {
            "symbol": request.symbol,
            "side": request.side,
            "type": "MARKET",
            "quantity": format_decimal_plain(request.quantity),
            "newClientOrderId": request.client_order_id,
            "positionSide": request.position_side,
            "newOrderRespType": "RESULT",
        }
        if request.reduce_only:
            params["reduceOnly"] = "true"
        data = await self._client.signed_post("/fapi/v1/order", params)
        return _to_exchange_order(data)

    async def place_limit_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        """GTC limit emir gonderir (olta modu icin — fiyat elle belirlenir)."""
        params = {
            "symbol": request.symbol,
            "side": request.side,
            "type": "LIMIT",
            "quantity": format_decimal_plain(request.quantity),
            "price": str(request.price),
            "timeInForce": "GTC",
            "newClientOrderId": request.client_order_id,
            "positionSide": request.position_side,
            "newOrderRespType": "RESULT",
        }
        data = await self._client.signed_post("/fapi/v1/order", params)
        return _to_exchange_order(data)

    async def place_reduce_only_market_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        reduce_request = PlaceOrderRequest(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            client_order_id=request.client_order_id,
            reduce_only=True,
            position_side=request.position_side,
        )
        return await self.place_market_order(reduce_request)

    async def _place_algo_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder:
        params: dict = {
            "algoType": "CONDITIONAL",
            "symbol": request.symbol,
            "side": request.side,
            "type": request.order_type,
            "triggerPrice": str(request.stop_price.normalize()),
            "workingType": request.working_type,
            "clientAlgoId": request.client_algo_id,
            "positionSide": request.position_side,
        }
        if request.order_type == "TRAILING_STOP_MARKET" and request.callback_rate_pct is not None:
            params["callbackRate"] = str(request.callback_rate_pct)
        if request.close_position:
            params["closePosition"] = "true"
        else:
            params["reduceOnly"] = "true"
        data = await self._client.signed_post("/fapi/v1/algoOrder", params)
        return _to_algo_exchange_order(data)

    async def place_stop_loss_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder:
        stop_request = PlaceAlgoOrderRequest(
            symbol=request.symbol,
            side=request.side,
            order_type="STOP_MARKET",
            stop_price=request.stop_price,
            client_algo_id=request.client_algo_id,
            working_type=request.working_type,
            close_position=request.close_position,
            position_side=request.position_side,
        )
        return await self._place_algo_order(stop_request)

    async def place_take_profit_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder:
        tp_request = PlaceAlgoOrderRequest(
            symbol=request.symbol,
            side=request.side,
            order_type="TAKE_PROFIT_MARKET",
            stop_price=request.stop_price,
            client_algo_id=request.client_algo_id,
            working_type=request.working_type,
            close_position=request.close_position,
            position_side=request.position_side,
        )
        return await self._place_algo_order(tp_request)

    async def query_order(self, symbol: str, client_order_id: str) -> ExchangeOrder | None:
        try:
            data = await self._client.signed_get(
                "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_order_id}
            )
            return _to_exchange_order(data)
        except BinanceApiError as exc:
            if exc.code == -2013:  # Order does not exist
                return None
            raise

    async def query_algo_order(self, symbol: str, client_algo_id: str) -> ExchangeOrder | None:
        try:
            data = await self._client.signed_get(
                "/fapi/v1/algoOrder", {"symbol": symbol, "clientAlgoId": client_algo_id}
            )
            return _to_algo_exchange_order(data)
        except BinanceApiError as exc:
            if exc.code == -2013:  # Order does not exist
                return None
            raise

    async def cancel_order(self, symbol: str, client_order_id: str) -> bool:
        try:
            await self._client.signed_delete(
                "/fapi/v1/order", {"symbol": symbol, "origClientOrderId": client_order_id}
            )
            return True
        except BinanceApiError as exc:
            if exc.code == -2011:  # Unknown order sent (zaten iptal/dolmus)
                return False
            raise

    async def cancel_algo_order(self, symbol: str, client_algo_id: str) -> bool:
        try:
            await self._client.signed_delete(
                "/fapi/v1/algoOrder", {"symbol": symbol, "clientAlgoId": client_algo_id}
            )
            return True
        except BinanceApiError as exc:
            if exc.code in (-2011, -2013):  # Unknown order / does not exist
                return False
            raise

    async def cancel_all_open_orders(self, symbol: str) -> bool:
        await self._client.signed_delete("/fapi/v1/allOpenOrders", {"symbol": symbol})
        await self._client.signed_delete("/fapi/v1/algoOpenOrders", {"symbol": symbol})
        return True
