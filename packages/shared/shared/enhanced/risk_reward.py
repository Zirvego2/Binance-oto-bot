"""Risk/odul ve beklenen deger hesabi (Decimal)."""

from __future__ import annotations

from decimal import Decimal

from shared.enums import PositionSide
from shared.roi import RoiPriceInputs, compute_roi_prices

from .types import RiskRewardResult

HUNDRED = Decimal("100")


def compute_risk_reward(
    *,
    entry_price: Decimal,
    quantity: Decimal,
    side: str,
    leverage: int,
    take_profit_roi_pct: Decimal,
    stop_loss_roi_pct: Decimal,
    taker_commission_rate: Decimal,
    estimated_slippage_pct: Decimal,
    win_rate: Decimal,
) -> RiskRewardResult:
    side_enum = PositionSide.LONG if side == "LONG" else PositionSide.SHORT
    roi = compute_roi_prices(
        RoiPriceInputs(
            entry_price=entry_price,
            quantity=quantity,
            side=side_enum,
            leverage=Decimal(leverage),
            take_profit_roi_pct=take_profit_roi_pct,
            stop_loss_roi_pct=stop_loss_roi_pct,
            taker_commission_rate=taker_commission_rate,
        )
    )
    notional = entry_price * quantity
    margin = notional / Decimal(leverage)
    open_comm = notional * taker_commission_rate
    close_comm = notional * taker_commission_rate
    slippage = notional * (estimated_slippage_pct / HUNDRED)

    est_profit = margin * (take_profit_roi_pct / HUNDRED)
    est_loss = margin * (stop_loss_roi_pct / HUNDRED)

    net_profit = est_profit - open_comm - close_comm - slippage
    net_loss = est_loss + open_comm + close_comm + slippage
    if net_loss <= Decimal("0"):
        net_loss = Decimal("0.0001")

    rr = net_profit / net_loss
    break_even = net_loss / (net_profit + net_loss) * HUNDRED if (net_profit + net_loss) > 0 else HUNDRED
    ev = win_rate * net_profit - (Decimal("1") - win_rate) * net_loss

    return RiskRewardResult(
        estimated_profit_usdt=est_profit,
        estimated_loss_usdt=est_loss,
        net_expected_profit_usdt=net_profit,
        net_expected_loss_usdt=net_loss,
        risk_reward_ratio=rr,
        break_even_win_rate=break_even,
        expected_value_usdt=ev,
        entry_price=entry_price,
        stop_loss_price=roi.stop_loss_price,
        take_profit_price=roi.take_profit_price,
    )
