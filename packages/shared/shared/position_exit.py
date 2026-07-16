"""Acik pozisyon cikis algoritmasi: kar hedefi, zarar limiti ve trailing stop.

Worker her fiyat guncellemesinde (WebSocket mark price + periyodik poll) bu
kurallari degerlendirir ve gerektiginde pozisyonu yazilim uzerinden kapatir.
Borsadaki SL/TP emirlerine ek olarak calisan bir guvenlik katmanidir.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class PositionExitDecision:
    should_close: bool
    close_reason: str | None = None


def evaluate_position_exit(
    roi_pct: Decimal,
    peak_roi_pct: Decimal,
    *,
    take_profit_roi_pct: Decimal,
    stop_loss_roi_pct: Decimal,
    trailing_stop_enabled: bool,
    trailing_stop_activation_roi_pct: Decimal,
    trailing_stop_callback_rate_pct: Decimal,
) -> tuple[PositionExitDecision, Decimal]:
    """Anlik ROI'ye gore pozisyon kapatilmali mi karar verir.

    Kurallar (oncelik sirasi):
    1. ROI >= take_profit_roi_pct  -> kar al (TAKE_PROFIT)
    2. ROI <= -stop_loss_roi_pct   -> zarar kes / ters donus (STOP_LOSS)
    3. Trailing aktif ve zirve ROI aktivasyonu astiysa:
       - zirveden callback kadar geri cekilme -> TRAILING_STOP
       - karda iken sifirin altina dusme   -> TRAILING_STOP (break-even kilidi)
    """

    peak = peak_roi_pct if peak_roi_pct > roi_pct else roi_pct

    if roi_pct >= take_profit_roi_pct:
        return PositionExitDecision(should_close=True, close_reason="TAKE_PROFIT"), peak

    if roi_pct <= -stop_loss_roi_pct:
        return PositionExitDecision(should_close=True, close_reason="STOP_LOSS"), peak

    if trailing_stop_enabled and peak >= trailing_stop_activation_roi_pct:
        drawdown_from_peak = peak - roi_pct
        if drawdown_from_peak >= trailing_stop_callback_rate_pct:
            return PositionExitDecision(should_close=True, close_reason="TRAILING_STOP"), peak
        if roi_pct <= Decimal("0"):
            return PositionExitDecision(should_close=True, close_reason="TRAILING_STOP"), peak

    return PositionExitDecision(should_close=False), peak
