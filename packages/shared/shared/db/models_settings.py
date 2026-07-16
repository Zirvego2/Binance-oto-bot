"""Bot ayarlari, calisma zamani durumu ve Binance baglanti durumu."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, MONEY_PRECISION, PCT_PRECISION, TimestampMixin, new_uuid


class BotSettings(Base, TimestampMixin):
    """Tek satirlik (singleton) ayar tablosu. id her zaman 'default'tur."""

    __tablename__ = "bot_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: "default")

    mode: Mapped[str] = mapped_column(String(16), default="paper", nullable=False)
    live_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_trading_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    bot_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    margin_per_trade_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("1"))
    leverage: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_allowed_leverage: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    margin_type: Mapped[str] = mapped_column(String(16), default="ISOLATED", nullable=False)
    position_mode: Mapped[str] = mapped_column(String(16), default="ONE_WAY", nullable=False)
    multi_assets_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    take_profit_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("10"))
    stop_loss_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("5"))

    max_open_positions: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_open_positions_per_symbol: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    daily_max_loss_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("1"))
    max_consecutive_losses: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    candle_timeframe: Mapped[str] = mapped_column(String(8), default="5m", nullable=False)
    scan_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    post_trade_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    min_24h_volume_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("5000000"))

    long_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    short_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trailing_stop_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trailing_stop_activation_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("5"))
    trailing_stop_callback_rate_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("1"))

    max_spread_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.15"))
    max_funding_rate_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.75"))
    max_volatility_atr_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("8"))

    ema_fast_period: Mapped[int] = mapped_column(Integer, default=9, nullable=False)
    ema_mid_period: Mapped[int] = mapped_column(Integer, default=21, nullable=False)
    ema_slow_period: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    rsi_period: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    atr_period: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    rsi_long_min: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("50"))
    rsi_long_max: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("65"))
    rsi_short_min: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("35"))
    rsi_short_max: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("50"))
    volume_multiplier_min: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("1.2"))
    min_signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("60"))
    top_n_symbols_by_volume: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    working_type: Mapped[str] = mapped_column(String(16), default="MARK_PRICE", nullable=False)
    min_liquidation_distance_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("10"))
    max_slippage_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.5"))

    paper_taker_commission_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=Decimal("0.0004"))
    paper_start_balance_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("100"))
    paper_funding_simulation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Olta (limit giris) modu: sinyal geldiginde market emri yerine limit emir
    limit_entry_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    limit_entry_offset_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.30"))
    limit_entry_timeout_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    limit_entry_max_pending: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    # Zarar esiginde kapatmak yerine ayni marj/miktar kadar ekleme (sadece normal market pozisyonlari)
    loss_add_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    loss_add_trigger_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("25"))
    loss_add_max_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # BTC piyasa yonu filtresi: SHORT piyasada LONG sinyal acma vb.
    market_direction_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Kar al (TP) ile kapanan pozisyonlarda panelde konfeti efekti
    take_profit_confetti_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Gelismis karar motoru ayarlari (varsayilan: PAPER + SHADOW acik, LIVE kapali) ---
    market_regime_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    block_trades_in_risk_off: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    min_regime_confidence: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("40"))
    high_volatility_score_threshold: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("75"))
    high_volatility_min_signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("65"))
    unknown_regime_min_signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("60"))

    max_allowed_risk_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("80"))
    high_risk_min_signal_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("75"))
    block_critical_risk: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    risk_adjusted_leverage_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    minimum_risk_reward_ratio: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("1.2"))

    symbol_profile_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    symbol_profile_shadow_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    symbol_profile_weight: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.3"))
    minimum_profile_sample_size: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    correlation_control_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    correlation_lookback: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    max_position_correlation: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.80"))
    block_high_correlation_trades: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    correlation_penalty_weight: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("1.0"))

    btc_mtf_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    btc_block_against_trend: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    enhanced_engine_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enhanced_engine_shadow_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enhanced_engine_live_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shadow_mode_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opportunity_score_weights: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ai_explanation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_post_trade_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_timeout_seconds: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    ai_daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("5"))
    ai_model: Mapped[str] = mapped_column(String(64), default="gpt-4o-mini", nullable=False)
    ai_data_retention_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    active_strategy_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # BTC impuls / lokal tepe-dip karsi islem modu (ayri sayfa)
    impulse_mode: Mapped[str] = mapped_column(String(16), default="OFF", nullable=False)  # OFF | MANUAL | AUTO
    impulse_btc_min_change_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("0.35"))
    impulse_lookback_minutes: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    impulse_extreme_min_score: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("50"))
    impulse_max_entries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    impulse_margin_usdt: Mapped[Decimal] = mapped_column(Numeric(*MONEY_PRECISION), default=Decimal("5"))
    impulse_leverage: Mapped[int] = mapped_column(Integer, default=8, nullable=False)  # 0 = global leverage
    impulse_tp_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("4"))
    impulse_sl_roi_pct: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("20"))
    impulse_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    impulse_top_n_scan: Mapped[int] = mapped_column(Integer, default=25, nullable=False)
    impulse_rsi_overbought: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("70"))
    impulse_rsi_oversold: Mapped[Decimal] = mapped_column(Numeric(*PCT_PRECISION), default=Decimal("30"))
    impulse_check_interval_seconds: Mapped[int] = mapped_column(Integer, default=20, nullable=False)

    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    updated_by_admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class BotRuntimeStatus(Base, TimestampMixin):
    """Botun anlik calisma durumu (tekil satir, id='default')."""

    __tablename__ = "bot_runtime_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: "default")
    admin_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True, index=True)
    run_state: Mapped[str] = mapped_column(String(24), default="STOPPED", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    safe_mode_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    worker_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    impulse_last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    impulse_last_direction: Mapped[str | None] = mapped_column(String(8), nullable=True)  # PUMP | DUMP
    impulse_last_btc_change_pct: Mapped[Decimal | None] = mapped_column(Numeric(*PCT_PRECISION), nullable=True)
    impulse_last_opened_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impulse_last_scan_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BinanceConnectionStatus(Base, TimestampMixin):
    """Musteri bazli Binance API baglanti durumu."""

    __tablename__ = "binance_connection_status"

    admin_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id: Mapped[str] = mapped_column(String(16), primary_key=True)  # paper | demo | live
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    account_access_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    futures_account_usable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trading_permission_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    position_mode_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    multi_assets_mode_off_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)
