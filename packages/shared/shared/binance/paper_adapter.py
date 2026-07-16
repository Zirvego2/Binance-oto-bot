"""PAPER (sanal) Binance USDS-M Futures adapter'i (sartname bolum 5).

Bu adapter GERCEK Binance herkese acik piyasa verilerini kullanir (fiyat,
mark price, funding rate, kline, 24s hacim) ancak hesap/pozisyon/emir
durumunu bellek icinde simule eder - gercek Binance hesabina HICBIR emir
gonderilmez.

Bir gercek borsanin STOP_MARKET / TAKE_PROFIT_MARKET emirlerini otomatik
tetiklemesini simule etmek icin ``on_mark_price_update`` metodu, worker
tarafindan her mark price guncellemesinde cagirilmalidir. Bu, gercek
exchange davranisini (kullanicinin hicbir sey yapmasina gerek kalmadan
tetiklenen conditional emirler) taklit eder.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

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

ZERO = Decimal("0")


@dataclass
class _PaperPosition:
    symbol: str
    quantity: Decimal  # LONG > 0, SHORT < 0
    entry_price: Decimal
    leverage: int
    margin_type: str = "ISOLATED"
    isolated_margin: Decimal = ZERO
    mark_price: Decimal = ZERO

    @property
    def position_side_label(self) -> str:
        return "LONG" if self.quantity > 0 else "SHORT"


@dataclass
class _PaperOrder:
    order: ExchangeOrder
    is_algo: bool = False


class PaperFuturesAdapter(BinanceFuturesAdapter):
    environment = "paper"

    def __init__(
        self,
        market_base_url: str,
        starting_balance_usdt: Decimal,
        taker_commission_rate: Decimal,
    ) -> None:
        self._market_client = BinanceRestClient(base_url=market_base_url)
        self._market_data = PublicMarketDataClient(self._market_client)
        self._commission_rate = taker_commission_rate

        self._wallet_balance = starting_balance_usdt
        self._positions: dict[str, _PaperPosition] = {}
        self._open_orders: dict[str, ExchangeOrder] = {}
        self._open_algo_orders: dict[str, ExchangeOrder] = {}
        # Gercek Binance'de dolan/iptal edilen emirler bir sure sorgulanabilir
        # kalir (silinmez); ayni davranisi taklit etmek icin FILLED/CANCELED
        # emirleri burada saklariz (query_order/query_algo_order bu cache'e de bakar).
        self._closed_orders: dict[str, ExchangeOrder] = {}
        self._closed_algo_orders: dict[str, ExchangeOrder] = {}
        self._leverage_by_symbol: dict[str, int] = {}
        self._margin_type_by_symbol: dict[str, str] = {}
        self._order_seq = 0
        self._realized_pnl_total = ZERO

    async def close(self) -> None:
        await self._market_client.close()

    # --- Genel / herkese acik veri (gercek Binance verisi) ---
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

    # --- Sanal hesap ---
    async def test_connection(self) -> ConnectionTestResult:
        return ConnectionTestResult(
            is_configured=True,
            is_connected=True,
            account_access_ok=True,
            futures_account_usable=True,
            trading_permission_ok=True,
            error_message=None,
        )

    async def get_account_balance(self) -> list[AccountBalance]:
        unrealized = sum((self._unrealized_pnl(p) for p in self._positions.values()), ZERO)
        return [
            AccountBalance(
                asset="USDT",
                wallet_balance=self._wallet_balance,
                available_balance=self._available_balance(),
                unrealized_pnl=unrealized,
            )
        ]

    async def get_account_info(self) -> AccountInfo:
        unrealized = sum((self._unrealized_pnl(p) for p in self._positions.values()), ZERO)
        used_margin = sum((p.isolated_margin for p in self._positions.values()), ZERO)
        return AccountInfo(
            total_wallet_balance=self._wallet_balance,
            total_unrealized_pnl=unrealized,
            total_margin_balance=self._wallet_balance + unrealized,
            available_balance=self._available_balance(),
            total_maint_margin=used_margin * Decimal("0.4"),
            can_trade=True,
            multi_assets_margin=False,
        )

    def _available_balance(self) -> Decimal:
        used_margin = sum((p.isolated_margin for p in self._positions.values()), ZERO)
        return max(self._wallet_balance - used_margin, ZERO)

    @staticmethod
    def _unrealized_pnl(position: _PaperPosition) -> Decimal:
        if position.mark_price == ZERO:
            return ZERO
        return (position.mark_price - position.entry_price) * position.quantity

    async def get_open_positions(self) -> list[ExchangePosition]:
        result = []
        for pos in self._positions.values():
            if pos.quantity == ZERO:
                continue
            liq_price = self._estimate_liquidation(pos)
            result.append(
                ExchangePosition(
                    symbol=pos.symbol,
                    position_side="BOTH",
                    quantity=pos.quantity,
                    entry_price=pos.entry_price,
                    mark_price=pos.mark_price,
                    unrealized_pnl=self._unrealized_pnl(pos),
                    leverage=pos.leverage,
                    margin_type=pos.margin_type,
                    liquidation_price=liq_price,
                    isolated_margin=pos.isolated_margin,
                )
            )
        return result

    def _estimate_liquidation(self, position: _PaperPosition) -> Decimal:
        from shared.enums import PositionSide
        from shared.roi import estimate_liquidation_price

        side = PositionSide.LONG if position.quantity > 0 else PositionSide.SHORT
        return estimate_liquidation_price(position.entry_price, Decimal(position.leverage), side)

    async def get_open_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        orders = list(self._open_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    async def get_open_algo_orders(self, symbol: str | None = None) -> list[ExchangeOrder]:
        orders = list(self._open_algo_orders.values())
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    async def get_income_history(
        self, symbol: str | None = None, income_type: str | None = None, limit: int = 100
    ) -> list[IncomeRecord]:
        return []

    async def get_leverage_bracket(self, symbol: str) -> list[LeverageBracket]:
        # PAPER modda gercekci varsayilan bracket seti (Binance genel yapisina benzer).
        return [
            LeverageBracket(
                bracket=1, initial_leverage=125, notional_cap=Decimal("50000"),
                notional_floor=Decimal("0"), maint_margin_ratio=Decimal("0.004"),
            ),
            LeverageBracket(
                bracket=2, initial_leverage=100, notional_cap=Decimal("250000"),
                notional_floor=Decimal("50000"), maint_margin_ratio=Decimal("0.005"),
            ),
            LeverageBracket(
                bracket=3, initial_leverage=50, notional_cap=Decimal("1000000"),
                notional_floor=Decimal("250000"), maint_margin_ratio=Decimal("0.01"),
            ),
        ]

    async def change_leverage(self, symbol: str, leverage: int) -> LeverageChangeResult:
        self._leverage_by_symbol[symbol] = leverage
        return LeverageChangeResult(symbol=symbol, leverage=leverage, max_notional_value=Decimal("1000000"))

    async def change_margin_type(self, symbol: str, margin_type: str) -> MarginTypeChangeResult:
        already_set = self._margin_type_by_symbol.get(symbol) == margin_type
        self._margin_type_by_symbol[symbol] = margin_type
        return MarginTypeChangeResult(symbol=symbol, margin_type=margin_type, already_set=already_set)

    async def get_position_mode(self) -> str:
        return "ONE_WAY"

    async def set_position_mode(self, hedge_mode: bool) -> None:
        if hedge_mode:
            raise ValueError("PAPER modda sadece ONE_WAY desteklenir")

    async def get_multi_assets_mode(self) -> bool:
        return False

    async def set_multi_assets_mode(self, enabled: bool) -> None:
        if enabled:
            raise ValueError("PAPER modda Multi-Assets Mode desteklenmez")

    def _next_order_id(self) -> str:
        self._order_seq += 1
        return f"PAPER{int(time.time())}{self._order_seq:06d}"

    async def _current_mark_price(self, symbol: str) -> Decimal:
        tick = await self.get_mark_price(symbol)
        return tick.mark_price

    async def place_market_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        price = await self._current_mark_price(request.symbol)
        leverage = self._leverage_by_symbol.get(request.symbol, 1)
        signed_qty = request.quantity if request.side == "BUY" else -request.quantity

        existing = self._positions.get(request.symbol)
        notional = request.quantity * price
        commission = notional * self._commission_rate

        if existing is None or existing.quantity == ZERO:
            margin = notional / Decimal(leverage)
            self._wallet_balance -= commission
            self._positions[request.symbol] = _PaperPosition(
                symbol=request.symbol,
                quantity=signed_qty,
                entry_price=price,
                leverage=leverage,
                margin_type=self._margin_type_by_symbol.get(request.symbol, "ISOLATED"),
                isolated_margin=margin,
                mark_price=price,
            )
        else:
            same_direction = (existing.quantity > 0 and signed_qty > 0) or (
                existing.quantity < 0 and signed_qty < 0
            )
            if same_direction:
                # Ayni yonde ekleme (ortalama giris fiyati guncellenir)
                total_notional = abs(existing.quantity) * existing.entry_price + notional
                total_qty = abs(existing.quantity) + request.quantity
                existing.entry_price = total_notional / total_qty if total_qty else price
                existing.quantity = existing.quantity + signed_qty
                existing.isolated_margin += notional / Decimal(leverage)
                self._wallet_balance -= commission
            else:
                # Pozisyonu azaltan/kapatan/ters ceviren emir -> gerceklesen PnL
                closed_qty = min(abs(existing.quantity), request.quantity)
                if existing.quantity > 0:
                    realized = (price - existing.entry_price) * closed_qty
                else:
                    realized = (existing.entry_price - price) * closed_qty
                self._wallet_balance += realized - commission
                self._realized_pnl_total += realized

                if abs(existing.quantity) >= request.quantity:
                    # Kismi veya tam kapanis (ters cevirme yok)
                    existing.quantity = existing.quantity + signed_qty
                    if existing.quantity == ZERO:
                        existing.isolated_margin = ZERO
                        del self._positions[request.symbol]
                    else:
                        existing.isolated_margin = abs(existing.quantity) * existing.entry_price / Decimal(leverage)
                else:
                    # Emir miktari mevcut pozisyondan buyuk -> pozisyon ters cevrilir.
                    # Sistem normalde bu senaryoyu uretmez (kapanis emirleri her zaman
                    # tam pozisyon buyuklugunde gonderilir) ancak guvenlik icin ele alinir.
                    remaining_qty = request.quantity - abs(existing.quantity)
                    new_side_qty = remaining_qty if request.side == "BUY" else -remaining_qty
                    del self._positions[request.symbol]
                    self._positions[request.symbol] = _PaperPosition(
                        symbol=request.symbol,
                        quantity=new_side_qty,
                        entry_price=price,
                        leverage=leverage,
                        margin_type=self._margin_type_by_symbol.get(request.symbol, "ISOLATED"),
                        isolated_margin=abs(new_side_qty) * price / Decimal(leverage),
                        mark_price=price,
                    )

        order = ExchangeOrder(
            symbol=request.symbol,
            binance_order_id=self._next_order_id(),
            client_order_id=request.client_order_id,
            side=request.side,
            order_type="MARKET",
            status="FILLED",
            price=price,
            orig_qty=request.quantity,
            executed_qty=request.quantity,
            avg_price=price,
            reduce_only=request.reduce_only,
            close_position=False,
            stop_price=None,
            working_type=None,
            time_ms=int(time.time() * 1000),
        )
        # MARKET emirler aninda dolar; bu nedenle "acik emir" degil "kapali emir"
        # olarak saklanir (get_open_orders() bu emri artik listelememelidir).
        self._closed_orders[request.client_order_id] = order
        return order

    async def place_limit_order(self, request: PlaceOrderRequest) -> ExchangeOrder:
        """PAPER modda limit emirler aninda dolduruluyor (simülasyon)."""
        limit_price = request.price or await self._current_mark_price(request.symbol)
        leverage = self._leverage_by_symbol.get(request.symbol, 1)
        signed_qty = request.quantity if request.side == "BUY" else -request.quantity
        existing = self._positions.get(request.symbol)
        notional = request.quantity * limit_price
        commission = notional * self._commission_rate

        if existing is None or existing.quantity == ZERO:
            self._wallet_balance -= commission
            self._positions[request.symbol] = _PaperPosition(
                symbol=request.symbol,
                quantity=signed_qty,
                entry_price=limit_price,
                leverage=leverage,
                margin_type=self._margin_type_by_symbol.get(request.symbol, "ISOLATED"),
                isolated_margin=notional / Decimal(leverage),
                mark_price=limit_price,
            )
        else:
            same_direction = (existing.quantity > 0 and signed_qty > 0) or (
                existing.quantity < 0 and signed_qty < 0
            )
            if same_direction:
                total_notional = abs(existing.quantity) * existing.entry_price + notional
                total_qty = abs(existing.quantity) + request.quantity
                existing.entry_price = total_notional / total_qty if total_qty else limit_price
                existing.quantity = existing.quantity + signed_qty
                existing.isolated_margin += notional / Decimal(leverage)
                self._wallet_balance -= commission
            else:
                closed_qty = min(abs(existing.quantity), request.quantity)
                realized = (
                    (limit_price - existing.entry_price) * closed_qty
                    if existing.quantity > 0
                    else (existing.entry_price - limit_price) * closed_qty
                )
                self._wallet_balance += realized - commission
                self._realized_pnl_total += realized
                existing.quantity = existing.quantity + signed_qty
                if existing.quantity == ZERO:
                    existing.isolated_margin = ZERO
                    del self._positions[request.symbol]
                else:
                    existing.isolated_margin = abs(existing.quantity) * existing.entry_price / Decimal(leverage)

        order = ExchangeOrder(
            symbol=request.symbol,
            binance_order_id=self._next_order_id(),
            client_order_id=request.client_order_id,
            side=request.side,
            order_type="LIMIT",
            status="FILLED",
            price=limit_price,
            orig_qty=request.quantity,
            executed_qty=request.quantity,
            avg_price=limit_price,
            reduce_only=request.reduce_only,
            close_position=False,
            stop_price=None,
            working_type=None,
            time_ms=int(time.time() * 1000),
        )
        self._closed_orders[request.client_order_id] = order
        return order

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

    async def _place_algo(self, request: PlaceAlgoOrderRequest, order_type: str) -> ExchangeOrder:
        order = ExchangeOrder(
            symbol=request.symbol,
            binance_order_id=self._next_order_id(),
            client_order_id=request.client_algo_id,
            side=request.side,
            order_type=order_type,
            status="NEW",
            price=ZERO,
            orig_qty=ZERO,
            executed_qty=ZERO,
            avg_price=ZERO,
            reduce_only=not request.close_position,
            close_position=request.close_position,
            stop_price=request.stop_price,
            working_type=request.working_type,
            time_ms=int(time.time() * 1000),
        )
        self._open_algo_orders[request.client_algo_id] = order
        return order

    async def place_stop_loss_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder:
        return await self._place_algo(request, "STOP_MARKET")

    async def place_take_profit_order(self, request: PlaceAlgoOrderRequest) -> ExchangeOrder:
        return await self._place_algo(request, "TAKE_PROFIT_MARKET")

    async def query_order(self, symbol: str, client_order_id: str) -> ExchangeOrder | None:
        return self._open_orders.get(client_order_id) or self._closed_orders.get(client_order_id)

    async def query_algo_order(self, symbol: str, client_algo_id: str) -> ExchangeOrder | None:
        return self._open_algo_orders.get(client_algo_id) or self._closed_algo_orders.get(client_algo_id)

    async def cancel_order(self, symbol: str, client_order_id: str) -> bool:
        return self._open_orders.pop(client_order_id, None) is not None

    async def cancel_algo_order(self, symbol: str, client_algo_id: str) -> bool:
        return self._open_algo_orders.pop(client_algo_id, None) is not None

    async def cancel_all_open_orders(self, symbol: str) -> bool:
        for key in [k for k, v in self._open_algo_orders.items() if v.symbol == symbol]:
            del self._open_algo_orders[key]
        for key in [k for k, v in self._open_orders.items() if v.symbol == symbol]:
            del self._open_orders[key]
        return True

    # --- PAPER'a ozel yardimci metodlar (arayuzde yok, worker tarafindan kullanilir) ---
    async def on_mark_price_update(self, symbol: str, mark_price: Decimal) -> list[ExchangeOrder]:
        """Gercek bir borsanin STOP_MARKET/TAKE_PROFIT_MARKET emirlerini otomatik
        tetiklemesini simule eder. Tetiklenen algo emirlerini FILLED olarak
        isaretler, pozisyonu kapatir ve tetiklenen emir listesini dondurur."""

        position = self._positions.get(symbol)
        if position is not None:
            position.mark_price = mark_price

        triggered: list[ExchangeOrder] = []
        for client_algo_id, algo in list(self._open_algo_orders.items()):
            if algo.symbol != symbol or algo.status != "NEW":
                continue
            if not self._is_algo_triggered(algo, mark_price):
                continue
            if position is None or position.quantity == ZERO:
                # Pozisyon zaten (baska bir yoldan) kapanmis; bu algo emri
                # borsada da otomatik iptal edilmis olur -> CANCELED olarak sakla.
                canceled = ExchangeOrder(
                    symbol=algo.symbol,
                    binance_order_id=algo.binance_order_id,
                    client_order_id=algo.client_order_id,
                    side=algo.side,
                    order_type=algo.order_type,
                    status="CANCELED",
                    price=algo.price,
                    orig_qty=algo.orig_qty,
                    executed_qty=ZERO,
                    avg_price=ZERO,
                    reduce_only=algo.reduce_only,
                    close_position=algo.close_position,
                    stop_price=algo.stop_price,
                    working_type=algo.working_type,
                    time_ms=int(time.time() * 1000),
                )
                del self._open_algo_orders[client_algo_id]
                self._closed_algo_orders[client_algo_id] = canceled
                continue

            close_qty = abs(position.quantity)
            fill_request = PlaceOrderRequest(
                symbol=symbol,
                side=algo.side,
                quantity=close_qty,
                client_order_id=f"trig_{client_algo_id}",
                reduce_only=True,
            )
            await self.place_market_order(fill_request)

            filled_algo = ExchangeOrder(
                symbol=algo.symbol,
                binance_order_id=algo.binance_order_id,
                client_order_id=algo.client_order_id,
                side=algo.side,
                order_type=algo.order_type,
                status="FILLED",
                price=mark_price,
                orig_qty=close_qty,
                executed_qty=close_qty,
                avg_price=mark_price,
                reduce_only=algo.reduce_only,
                close_position=algo.close_position,
                stop_price=algo.stop_price,
                working_type=algo.working_type,
                time_ms=int(time.time() * 1000),
            )
            del self._open_algo_orders[client_algo_id]
            self._closed_algo_orders[client_algo_id] = filled_algo
            triggered.append(filled_algo)
        return triggered

    @staticmethod
    def _is_algo_triggered(algo: ExchangeOrder, mark_price: Decimal) -> bool:
        if algo.stop_price is None:
            return False
        if algo.order_type == "STOP_MARKET":
            # LONG stop-loss (side=SELL): mark <= stop tetikler
            # SHORT stop-loss (side=BUY): mark >= stop tetikler
            return mark_price <= algo.stop_price if algo.side == "SELL" else mark_price >= algo.stop_price
        if algo.order_type == "TAKE_PROFIT_MARKET":
            # LONG take-profit (side=SELL): mark >= stop tetikler
            # SHORT take-profit (side=BUY): mark <= stop tetikler
            return mark_price >= algo.stop_price if algo.side == "SELL" else mark_price <= algo.stop_price
        return False

    def apply_funding(self, symbol: str, funding_rate: Decimal) -> Decimal:
        """PAPER modunda funding gideri/gelirini simule eder (sartname bolum 27).

        Pozitif funding_rate ve LONG pozisyon -> LONG oder (bakiye azalir).
        Pozitif funding_rate ve SHORT pozisyon -> SHORT alir (bakiye artar).
        """

        position = self._positions.get(symbol)
        if position is None or position.quantity == ZERO:
            return ZERO
        notional = abs(position.quantity) * position.mark_price
        funding_fee = notional * funding_rate
        signed_fee = -funding_fee if position.quantity > 0 else funding_fee
        self._wallet_balance += signed_fee
        return signed_fee

    def get_wallet_balance(self) -> Decimal:
        return self._wallet_balance

    def restore_state(
        self,
        wallet_balance: Decimal,
        positions: list[tuple[str, Decimal, Decimal, int, Decimal]],
    ) -> None:
        """Worker yeniden baslatildiginda veritabanindaki acik PAPER pozisyonlarindan
        adapter'in bellek ici durumunu geri yukler (symbol, qty(signed), entry_price, leverage, isolated_margin)."""

        self._wallet_balance = wallet_balance
        self._positions.clear()
        for symbol, qty, entry_price, leverage, margin in positions:
            self._positions[symbol] = _PaperPosition(
                symbol=symbol,
                quantity=qty,
                entry_price=entry_price,
                leverage=leverage,
                isolated_margin=margin,
                mark_price=entry_price,
            )
