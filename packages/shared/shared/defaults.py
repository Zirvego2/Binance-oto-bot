"""Sartname bolum 2: sistemin varsayilan baslangic ayarlari.

Bu degerler ilk migration ile ``bot_settings`` tablosuna yazilir ve admin
paneli uzerinden degistirilebilir. Kod icinde sabit deger olarak
kullanilmamali, her zaman veritabanindaki guncel ayar okunmalidir.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

DEFAULT_BOT_SETTINGS: dict[str, Any] = {
    "mode": "paper",
    "live_trading_enabled": False,
    "auto_trading_enabled": True,
    "bot_enabled": False,
    "margin_per_trade_usdt": "1",
    "leverage": "10",
    "max_allowed_leverage": "20",
    "margin_type": "ISOLATED",
    "position_mode": "ONE_WAY",
    "multi_assets_mode": False,
    "take_profit_roi_pct": "10",
    "stop_loss_roi_pct": "5",
    "max_open_positions": "1",
    "max_open_positions_per_symbol": "1",
    "daily_max_loss_usdt": "1",
    "max_consecutive_losses": "3",
    "candle_timeframe": "5m",
    "scan_interval_seconds": "60",
    "post_trade_cooldown_minutes": "30",
    "min_24h_volume_usdt": "5000000",
    "long_enabled": True,
    "short_enabled": True,
    "trailing_stop_enabled": False,
    "trailing_stop_activation_roi_pct": "5",
    "trailing_stop_callback_rate_pct": "1",
    "max_spread_pct": "0.15",
    "max_funding_rate_pct": "0.75",
    "max_volatility_atr_pct": "8",
    "ema_fast_period": "9",
    "ema_mid_period": "21",
    "ema_slow_period": "50",
    "rsi_period": "14",
    "atr_period": "14",
    "rsi_long_min": "50",
    "rsi_long_max": "65",
    "rsi_short_min": "35",
    "rsi_short_max": "50",
    "volume_multiplier_min": "1.2",
    "min_signal_score": "60",
    "top_n_symbols_by_volume": "20",
    "working_type": "MARK_PRICE",
    "min_liquidation_distance_pct": "10",
    "max_slippage_pct": "0.5",
    "paper_taker_commission_rate": "0.0004",
    "paper_start_balance_usdt": "100",
    "paper_funding_simulation_enabled": True,
}

DEFAULT_MIN_LEVERAGE = 1
DEFAULT_ENV_MAX_LEVERAGE = 20

# Coin taramasi icin varsayilan islem yapilamayacak/hariç tutulacak durumlar
MAX_BLACKLIST_COOLDOWN_MINUTES = 24 * 60

DECIMAL_ONE = Decimal("1")
DECIMAL_HUNDRED = Decimal("100")
