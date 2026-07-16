"""Binance ile yerel veritabani arasinda reconciliation mantigi (sartname bolum 26).

Bu modul saf (side-effect'siz) karsilastirma fonksiyonlari icerir; DB
yazma islemleri cagiran taraf (api veya worker) tarafindan yapilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .binance.types import ExchangeOrder, ExchangePosition


@dataclass(frozen=True, slots=True)
class LocalPositionSnapshot:
    """Veritabanindaki acik pozisyonun reconciliation icin gerekli ozeti."""

    position_id: str
    symbol: str
    side: str  # LONG | SHORT
    quantity: Decimal
    entry_price: Decimal
    has_stop_loss: bool
    has_take_profit: bool


@dataclass(frozen=True, slots=True)
class Mismatch:
    symbol: str
    mismatch_type: str
    details: str


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    mismatches: list[Mismatch]
    external_positions: list[str]  # Binance'de var, DB'de yok olan semboller
    missing_on_exchange: list[str]  # DB'de acik ama Binance'de yok olan semboller
    positions_missing_protection: list[str]  # Binance'de acik ama SL/TP algo emri yok
    is_consistent: bool


_QTY_TOLERANCE = Decimal("0.00000001")
_PRICE_TOLERANCE_PCT = Decimal("0.5")  # %0.5 uzeri fark mismatch sayilir


def reconcile(
    exchange_positions: list[ExchangePosition],
    local_positions: list[LocalPositionSnapshot],
    exchange_algo_orders: list[ExchangeOrder],
) -> ReconciliationReport:
    mismatches: list[Mismatch] = []
    external_positions: list[str] = []
    missing_on_exchange: list[str] = []
    positions_missing_protection: list[str] = []

    exchange_by_symbol = {p.symbol: p for p in exchange_positions}
    local_by_symbol = {p.symbol: p for p in local_positions}

    for symbol, exch_pos in exchange_by_symbol.items():
        local_pos = local_by_symbol.get(symbol)
        if local_pos is None:
            external_positions.append(symbol)
            mismatches.append(
                Mismatch(symbol, "EXTERNAL_POSITION", f"{symbol} Binance'de acik ancak veritabaninda kaydi yok")
            )
            continue

        exchange_side = "LONG" if exch_pos.quantity > 0 else "SHORT"
        if exchange_side != local_pos.side:
            mismatches.append(
                Mismatch(symbol, "SIDE_MISMATCH", f"{symbol}: Binance={exchange_side}, DB={local_pos.side}")
            )
            continue

        qty_diff = abs(abs(exch_pos.quantity) - local_pos.quantity)
        if qty_diff > _QTY_TOLERANCE:
            mismatches.append(
                Mismatch(
                    symbol,
                    "QUANTITY_MISMATCH",
                    f"{symbol}: Binance qty={abs(exch_pos.quantity)}, DB qty={local_pos.quantity}",
                )
            )

        if local_pos.entry_price > 0:
            price_diff_pct = abs(exch_pos.entry_price - local_pos.entry_price) / local_pos.entry_price * 100
            if price_diff_pct > _PRICE_TOLERANCE_PCT:
                mismatches.append(
                    Mismatch(
                        symbol,
                        "ENTRY_PRICE_MISMATCH",
                        f"{symbol}: Binance entry={exch_pos.entry_price}, DB entry={local_pos.entry_price}",
                    )
                )

        symbol_algo_orders = [o for o in exchange_algo_orders if o.symbol == symbol and o.status == "NEW"]
        has_sl = any(o.order_type == "STOP_MARKET" for o in symbol_algo_orders)
        has_tp = any(o.order_type == "TAKE_PROFIT_MARKET" for o in symbol_algo_orders)
        if not has_sl or not has_tp:
            positions_missing_protection.append(symbol)
            mismatches.append(
                Mismatch(
                    symbol,
                    "MISSING_PROTECTIVE_ORDER",
                    f"{symbol}: stop_loss={'var' if has_sl else 'YOK'}, take_profit={'var' if has_tp else 'YOK'}",
                )
            )

    for symbol, local_pos in local_by_symbol.items():
        if symbol not in exchange_by_symbol:
            missing_on_exchange.append(symbol)
            mismatches.append(
                Mismatch(symbol, "MISSING_ON_EXCHANGE", f"{symbol} veritabaninda acik ancak Binance'de bulunamadi")
            )

    return ReconciliationReport(
        mismatches=mismatches,
        external_positions=external_positions,
        missing_on_exchange=missing_on_exchange,
        positions_missing_protection=positions_missing_protection,
        is_consistent=len(mismatches) == 0,
    )
