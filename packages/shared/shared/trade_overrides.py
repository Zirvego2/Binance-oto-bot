"""Pozisyon acilisinda gecici ayar override'lari (impuls islemleri icin)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class TradeOpenOverrides:
    margin_usdt: Decimal | None = None
    leverage: int | None = None
    take_profit_roi_pct: Decimal | None = None
    stop_loss_roi_pct: Decimal | None = None
    bypass_market_direction_filter: bool = False


MANUAL_TRADE_OVERRIDES = TradeOpenOverrides(bypass_market_direction_filter=True)


class SettingsOverlay:
    """BotSettings uzerine gecici override katmani."""

    __slots__ = ("_base", "_overrides")

    def __init__(self, base: Any, overrides: TradeOpenOverrides | None) -> None:
        self._base = base
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if self._overrides is not None:
            if name == "margin_per_trade_usdt" and self._overrides.margin_usdt is not None:
                return self._overrides.margin_usdt
            if name == "leverage" and self._overrides.leverage is not None:
                return self._overrides.leverage
            if name == "take_profit_roi_pct" and self._overrides.take_profit_roi_pct is not None:
                return self._overrides.take_profit_roi_pct
            if name == "stop_loss_roi_pct" and self._overrides.stop_loss_roi_pct is not None:
                return self._overrides.stop_loss_roi_pct
        return getattr(self._base, name)


def apply_trade_overrides(base: Any, overrides: TradeOpenOverrides | None) -> Any:
    if overrides is None:
        return base
    return SettingsOverlay(base, overrides)
