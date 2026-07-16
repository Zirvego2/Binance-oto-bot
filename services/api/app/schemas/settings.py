from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class BotSettingsOut(BaseModel):
    mode: str
    live_trading_enabled: bool
    auto_trading_enabled: bool
    bot_enabled: bool

    margin_per_trade_usdt: Decimal
    leverage: int
    max_allowed_leverage: int
    margin_type: str
    position_mode: str
    multi_assets_mode: bool

    take_profit_roi_pct: Decimal
    stop_loss_roi_pct: Decimal

    max_open_positions: int
    max_open_positions_per_symbol: int
    daily_max_loss_usdt: Decimal
    max_consecutive_losses: int

    candle_timeframe: str
    scan_interval_seconds: int
    post_trade_cooldown_minutes: int
    min_24h_volume_usdt: Decimal

    long_enabled: bool
    short_enabled: bool
    trailing_stop_enabled: bool
    trailing_stop_activation_roi_pct: Decimal
    trailing_stop_callback_rate_pct: Decimal

    max_spread_pct: Decimal
    max_funding_rate_pct: Decimal
    max_volatility_atr_pct: Decimal

    ema_fast_period: int
    ema_mid_period: int
    ema_slow_period: int
    rsi_period: int
    atr_period: int
    rsi_long_min: Decimal
    rsi_long_max: Decimal
    rsi_short_min: Decimal
    rsi_short_max: Decimal
    volume_multiplier_min: Decimal
    min_signal_score: Decimal
    top_n_symbols_by_volume: int

    working_type: str
    min_liquidation_distance_pct: Decimal
    max_slippage_pct: Decimal

    paper_taker_commission_rate: Decimal
    paper_start_balance_usdt: Decimal
    paper_funding_simulation_enabled: bool

    limit_entry_enabled: bool
    limit_entry_offset_pct: Decimal
    limit_entry_timeout_minutes: int
    limit_entry_max_pending: int

    loss_add_enabled: bool
    loss_add_trigger_roi_pct: Decimal
    loss_add_max_count: int

    market_direction_filter_enabled: bool

    take_profit_confetti_enabled: bool

    # Gelismis karar motoru
    enhanced_engine_enabled: bool
    enhanced_engine_shadow_mode: bool
    enhanced_engine_live_enabled: bool
    shadow_mode_active: bool
    market_regime_enabled: bool
    symbol_profile_enabled: bool
    correlation_control_enabled: bool
    ai_explanation_enabled: bool
    ai_model: str
    min_regime_confidence: Decimal
    max_allowed_risk_score: Decimal
    minimum_risk_reward_ratio: Decimal

    class Config:
        from_attributes = True


class BotSettingsUpdate(BaseModel):
    """Kismi guncelleme icin tum alanlar opsiyoneldir. Sadece gonderilen
    alanlar degistirilir. Kaldiraç, MAX_ALLOWED_LEVERAGE environment
    sinirini asamaz (backend'de yeniden dogrulanir)."""

    margin_per_trade_usdt: Decimal | None = Field(default=None, gt=0)
    leverage: int | None = Field(default=None, ge=1)
    take_profit_roi_pct: Decimal | None = Field(default=None, gt=0)
    stop_loss_roi_pct: Decimal | None = Field(default=None, gt=0)
    max_open_positions: int | None = Field(default=None, ge=1, le=50)
    max_open_positions_per_symbol: int | None = Field(default=None, ge=1, le=5)
    daily_max_loss_usdt: Decimal | None = Field(default=None, gt=0)
    max_consecutive_losses: int | None = Field(default=None, ge=1, le=20)
    candle_timeframe: str | None = None
    scan_interval_seconds: int | None = Field(default=None, ge=5, le=3600)
    post_trade_cooldown_minutes: int | None = Field(default=None, ge=0, le=1440)
    min_24h_volume_usdt: Decimal | None = Field(default=None, ge=0)
    max_spread_pct: Decimal | None = Field(default=None, gt=0)
    max_funding_rate_pct: Decimal | None = Field(default=None, gt=0)
    max_volatility_atr_pct: Decimal | None = Field(default=None, gt=0)
    long_enabled: bool | None = None
    short_enabled: bool | None = None
    auto_trading_enabled: bool | None = None
    trailing_stop_enabled: bool | None = None
    trailing_stop_activation_roi_pct: Decimal | None = Field(default=None, gt=0)
    trailing_stop_callback_rate_pct: Decimal | None = Field(default=None, gt=0)
    ema_fast_period: int | None = Field(default=None, ge=2, le=200)
    ema_mid_period: int | None = Field(default=None, ge=2, le=200)
    ema_slow_period: int | None = Field(default=None, ge=2, le=400)
    rsi_period: int | None = Field(default=None, ge=2, le=100)
    atr_period: int | None = Field(default=None, ge=2, le=100)
    rsi_long_min: Decimal | None = Field(default=None, ge=0, le=100)
    rsi_long_max: Decimal | None = Field(default=None, ge=0, le=100)
    rsi_short_min: Decimal | None = Field(default=None, ge=0, le=100)
    rsi_short_max: Decimal | None = Field(default=None, ge=0, le=100)
    volume_multiplier_min: Decimal | None = Field(default=None, gt=0)
    min_signal_score: Decimal | None = Field(default=None, ge=0, le=100)
    top_n_symbols_by_volume: int | None = Field(default=None, ge=1, le=200)
    min_liquidation_distance_pct: Decimal | None = Field(default=None, gt=0)
    max_slippage_pct: Decimal | None = Field(default=None, gt=0)
    bot_enabled: bool | None = None
    limit_entry_enabled: bool | None = None
    limit_entry_offset_pct: Decimal | None = Field(default=None, ge=0, le=5)
    limit_entry_timeout_minutes: int | None = Field(default=None, ge=1, le=1440)
    limit_entry_max_pending: int | None = Field(default=None, ge=1, le=20)
    loss_add_enabled: bool | None = None
    loss_add_trigger_roi_pct: Decimal | None = Field(default=None, gt=0)
    loss_add_max_count: int | None = Field(default=None, ge=0, le=15)
    market_direction_filter_enabled: bool | None = None
    take_profit_confetti_enabled: bool | None = None

    enhanced_engine_enabled: bool | None = None
    enhanced_engine_shadow_mode: bool | None = None
    shadow_mode_active: bool | None = None
    market_regime_enabled: bool | None = None
    symbol_profile_enabled: bool | None = None
    correlation_control_enabled: bool | None = None
    ai_explanation_enabled: bool | None = None
    ai_model: str | None = None
    min_regime_confidence: Decimal | None = Field(default=None, ge=0, le=100)
    max_allowed_risk_score: Decimal | None = Field(default=None, ge=0, le=100)
    minimum_risk_reward_ratio: Decimal | None = Field(default=None, gt=0)

    @field_validator("leverage")
    @classmethod
    def validate_leverage_range(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("Kaldirac en az 1 olmalidir")
        return v


class DefaultGeneralSettingsOut(BaseModel):
    scan_interval_seconds: int
    min_24h_volume_usdt: str
    max_spread_pct: str
    max_funding_rate_pct: str
    max_volatility_atr_pct: str
    min_signal_score: str
    top_n_symbols_by_volume: int
    long_enabled: bool
    short_enabled: bool
    auto_trading_enabled: bool
    market_direction_filter_enabled: bool
    take_profit_confetti_enabled: bool


class PanelDefaultsOut(BaseModel):
    general: dict[str, str | int | bool] | None = None
    position: dict[str, str | int | bool] | None = None
    impulse: dict[str, str | int | bool] | None = None
