"""Pozisyon boyutu hesaplama (sartname bolum 10).

Hesaplama sirasi:
  1. margin_usdt
  2. leverage
  3. target_notional = margin_usdt * leverage
  4. price (mark price veya guvenilir emir fiyati)
  5. raw_quantity = target_notional / price
  6. quantity -> stepSize ile asagi yuvarla
  7. gercek notional'i tekrar hesapla
  8. Binance filtrelerini kontrol et
  9. komisyon ve slippage guvenlik payi kontrolu
  10. bakiye yeterliligi kontrolu

Sistem KULLANICININ BELIRLEDIGI TEMINAT TUTARINI ASMAZ. Eger Binance'in
minimum notional gereksinimi bu teminatla karsilanamiyorsa, teminat
otomatik yukseltilmez; islem atlanir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .binance_filters import SymbolFilters, required_min_margin, round_quantity_down, validate_order
from .decimal_utils import ZERO, safe_div


@dataclass(frozen=True, slots=True)
class PositionSizingInputs:
    margin_usdt: Decimal
    leverage: Decimal
    price: Decimal
    filters: SymbolFilters
    available_balance_usdt: Decimal
    safety_buffer_pct: Decimal = Decimal("0.5")  # komisyon/slippage icin ek guvenlik payi (%)


@dataclass(frozen=True, slots=True)
class PositionSizingResult:
    ok: bool
    reason: str | None
    quantity: Decimal
    notional: Decimal
    required_margin: Decimal
    suggested_min_margin: Decimal | None


def calculate_position_size(inputs: PositionSizingInputs) -> PositionSizingResult:
    if inputs.margin_usdt <= ZERO:
        return PositionSizingResult(False, "margin_must_be_positive", ZERO, ZERO, ZERO, None)
    if inputs.leverage <= ZERO:
        return PositionSizingResult(False, "leverage_must_be_positive", ZERO, ZERO, ZERO, None)
    if inputs.price <= ZERO:
        return PositionSizingResult(False, "invalid_price", ZERO, ZERO, ZERO, None)

    if not inputs.filters.is_tradable_usdt_perpetual:
        return PositionSizingResult(False, "symbol_not_tradable_usdt_perpetual", ZERO, ZERO, ZERO, None)

    target_notional = inputs.margin_usdt * inputs.leverage
    raw_quantity = safe_div(target_notional, inputs.price)
    quantity = round_quantity_down(inputs.filters, raw_quantity)

    suggested_min_margin = required_min_margin(inputs.filters, inputs.price, inputs.leverage)

    if quantity <= ZERO:
        return PositionSizingResult(
            False, "quantity_rounds_to_zero", ZERO, ZERO, ZERO, suggested_min_margin
        )

    notional = quantity * inputs.price
    check = validate_order(inputs.filters, quantity, inputs.price)
    if not check.ok:
        reason = check.reason or "filter_check_failed"
        return PositionSizingResult(False, reason, quantity, notional, ZERO, suggested_min_margin)

    required_margin = safe_div(notional, inputs.leverage)

    # Kullanicinin belirledigi teminati asmiyor mu kontrolu (kucuk yuvarlama
    # farklarina tolerans tanimak icin %0.5 pay birakilir).
    max_allowed_margin = inputs.margin_usdt * (Decimal("1") + Decimal("0.005"))
    if required_margin > max_allowed_margin:
        return PositionSizingResult(
            False, "required_margin_exceeds_user_margin", quantity, notional, required_margin, suggested_min_margin
        )

    safety_multiplier = Decimal("1") + (inputs.safety_buffer_pct / Decimal("100"))
    required_with_buffer = required_margin * safety_multiplier
    if inputs.available_balance_usdt < required_with_buffer:
        return PositionSizingResult(
            False, "insufficient_balance", quantity, notional, required_margin, suggested_min_margin
        )

    return PositionSizingResult(True, None, quantity, notional, required_margin, suggested_min_margin)
