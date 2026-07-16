"""Paneldeki guncel (referans) varsayilan bot ayarlari."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

SettingsResetScope = Literal["general", "position", "impulse", "all"]

# /settings — Genel Ayarlar
DEFAULT_GENERAL_SETTINGS: dict[str, object] = {
    "scan_interval_seconds": 30,
    "min_24h_volume_usdt": Decimal("5000000"),
    "max_spread_pct": Decimal("0.15"),
    "max_funding_rate_pct": Decimal("0.75"),
    "max_volatility_atr_pct": Decimal("12"),
    "min_signal_score": Decimal("50"),
    "top_n_symbols_by_volume": 30,
    "long_enabled": True,
    "short_enabled": True,
    "auto_trading_enabled": True,
    "market_direction_filter_enabled": True,
    "take_profit_confetti_enabled": True,
}

# /pozisyon-ayarlari — Pozisyon Ayarlari
DEFAULT_POSITION_SETTINGS: dict[str, object] = {
    "margin_per_trade_usdt": Decimal("5"),
    "leverage": 8,
    "take_profit_roi_pct": Decimal("4"),
    "stop_loss_roi_pct": Decimal("90"),
    "loss_add_enabled": True,
    "loss_add_trigger_roi_pct": Decimal("25"),
    "loss_add_max_count": 15,
    "trailing_stop_enabled": False,
    "trailing_stop_activation_roi_pct": Decimal("5"),
    "trailing_stop_callback_rate_pct": Decimal("1"),
    "max_open_positions": 8,
    "max_open_positions_per_symbol": 1,
    "daily_max_loss_usdt": Decimal("20"),
    "max_consecutive_losses": 3,
    "min_liquidation_distance_pct": Decimal("3"),
    "max_slippage_pct": Decimal("0.5"),
    "post_trade_cooldown_minutes": 2,
    "limit_entry_enabled": False,
    "limit_entry_offset_pct": Decimal("2"),
    "limit_entry_timeout_minutes": 60,
    "limit_entry_max_pending": 3,
}

# /btc-impuls — BTC Impuls ayarlari
DEFAULT_IMPULSE_SETTINGS: dict[str, object] = {
    "impulse_mode": "OFF",
    "impulse_btc_min_change_pct": Decimal("0.35"),
    "impulse_lookback_minutes": 3,
    "impulse_extreme_min_score": Decimal("50"),
    "impulse_max_entries": 3,
    "impulse_margin_usdt": Decimal("2.6"),
    "impulse_leverage": 8,
    "impulse_tp_roi_pct": Decimal("4"),
    "impulse_sl_roi_pct": Decimal("20"),
    "impulse_cooldown_minutes": 20,
    "impulse_top_n_scan": 25,
    "impulse_rsi_overbought": Decimal("70"),
    "impulse_rsi_oversold": Decimal("30"),
    "impulse_check_interval_seconds": 20,
}

SETTINGS_PRESERVE_ON_RESET = frozenset(
    {
        "id",
        "admin_id",
        "mode",
        "bot_enabled",
        "live_trading_enabled",
        "updated_by_admin_id",
        "created_at",
        "updated_at",
    }
)


def defaults_for_scope(scope: SettingsResetScope) -> dict[str, object]:
    if scope == "general":
        return dict(DEFAULT_GENERAL_SETTINGS)
    if scope == "position":
        return dict(DEFAULT_POSITION_SETTINGS)
    if scope == "impulse":
        return dict(DEFAULT_IMPULSE_SETTINGS)
    merged: dict[str, object] = {}
    merged.update(DEFAULT_GENERAL_SETTINGS)
    merged.update(DEFAULT_POSITION_SETTINGS)
    merged.update(DEFAULT_IMPULSE_SETTINGS)
    return merged
