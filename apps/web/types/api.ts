/**
 * Backend Pydantic semalarina karsilik gelen TypeScript tipleri.
 * Decimal alanlar backend'den string olarak gelir (hassasiyet kaybi olmamasi icin);
 * gosterim icin lib/utils.ts icindeki formatUsdt/formatNumber/toNumber kullanilir.
 */

export type Decimal = string;

export type BotMode = "paper" | "demo" | "live";
export type PositionSide = "LONG" | "SHORT";
export type RunState = "STOPPED" | "RUNNING" | "EMERGENCY_STOPPED" | "SAFE_MODE";

export type UserRole = "platform_admin" | "customer";
export type ApprovalStatus = "pending" | "approved" | "blocked";

export interface AdminOut {
  id: string;
  email: string;
  full_name: string | null;
  phone?: string | null;
  city?: string | null;
  district?: string | null;
  last_login_at: string | null;
  firebase_uid?: string | null;
  role?: UserRole;
  approval_status?: ApprovalStatus;
  is_active?: boolean;
  membership_plan?: string | null;
  membership_starts_at?: string | null;
  membership_expires_at?: string | null;
  membership_days_remaining?: number | null;
  membership_active?: boolean | null;
}

export interface CustomerRegisterPendingOut {
  ok: boolean;
  message: string;
  email: string;
}

export interface PlatformOverviewOut {
  total_customers: number;
  pending_customers: number;
  approved_customers: number;
  blocked_customers: number;
  active_sessions: number;
  customers_with_binance: number;
  customers_with_telegram: number;
  customers_with_openai: number;
  customers_online: number;
  customers_bot_running: number;
  new_customers_7d: number;
  new_customers_30d: number;
  total_open_positions: number;
  trading_ready_customers: number;
  platform_capacity: number;
  registration_trend_7d: RegistrationDayOut[];
}

export interface RegistrationDayOut {
  date: string;
  count: number;
}

export interface PlatformActivityOut {
  id: string;
  action: string;
  entity_type: string;
  customer_id: string | null;
  customer_email: string | null;
  created_at: string;
  ip_address: string | null;
}

export interface CustomerEarningsPeriodOut {
  net_pnl_usdt: string;
  gross_pnl_usdt: string;
  trades_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: string;
}

export interface CustomerEarningsOut {
  customer_id: string;
  email: string;
  full_name: string | null;
  approval_status: string;
  daily: CustomerEarningsPeriodOut;
  weekly: CustomerEarningsPeriodOut;
  monthly: CustomerEarningsPeriodOut;
}

export interface CustomerEarningsDetailOut {
  customer_id: string;
  email: string;
  full_name: string | null;
  approval_status: string;
  bot_mode: string | null;
  bot_enabled: boolean;
  open_positions_count: number;
  total_unrealized_pnl_usdt: Decimal;
  daily: CustomerEarningsPeriodOut;
  weekly: CustomerEarningsPeriodOut;
  monthly: CustomerEarningsPeriodOut;
  lifetime: CustomerEarningsPeriodOut;
  generated_at: string;
}

export interface PlatformEarningsSummaryOut {
  daily_total_net_pnl_usdt: string;
  weekly_total_net_pnl_usdt: string;
  monthly_total_net_pnl_usdt: string;
  customer_count: number;
  customers: CustomerEarningsOut[];
  generated_at: string;
}

export interface AdminTradeOut extends TradeOut {
  customer_id: string | null;
  customer_email: string | null;
  customer_full_name: string | null;
}

export interface CustomerListItemOut {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  city: string | null;
  district: string | null;
  role: UserRole;
  approval_status: ApprovalStatus;
  is_active: boolean;
  firebase_uid: string | null;
  last_login_at: string | null;
  last_login_ip: string | null;
  created_at: string | null;
  approved_at: string | null;
  membership_plan: string | null;
  membership_starts_at: string | null;
  membership_expires_at: string | null;
  membership_days_remaining: number | null;
  membership_active: boolean;
  has_binance: boolean;
  has_telegram: boolean;
  has_openai: boolean;
  is_online: boolean;
  active_session_count: number;
  plan: string | null;
  blocked_reason: string | null;
  notes: string | null;
  open_positions_count: number;
  bot_run_state: string | null;
  bot_enabled: boolean;
  bot_mode: string | null;
}

export interface CustomerDetailOut extends CustomerListItemOut {
  failed_login_count: number;
  locked_until: string | null;
  live_trading_ack_at: string | null;
  firestore_synced: boolean;
  migration_mode: string | null;
}

export interface CustomerDeleteOut {
  ok: boolean;
  customer_id: string;
  email: string;
  message: string;
}

export interface MembershipPlanOut {
  id: string;
  label: string;
  duration_days: number;
  price_usdt: number;
}

export interface MembershipOverviewOut {
  total_customers: number;
  active_count: number;
  expiring_7d_count: number;
  expired_count: number;
  no_membership_count: number;
  plans: MembershipPlanOut[];
}

export interface WithdrawableCustomerOut {
  customer_id: string;
  email: string;
  full_name: string | null;
  bot_mode: string | null;
  has_binance: boolean;
  open_positions_count: number;
  ip_restrict: boolean;
  withdraw_enabled: boolean;
  eligible: boolean;
  ineligible_reason: string | null;
  futures_available_usdt: Decimal;
  spot_usdt_balance: Decimal;
  estimated_withdraw_usdt: Decimal;
  withdraw_fee_usdt: Decimal;
  destination_address: string;
  network: string;
}

export interface FundTransferExecuteOut {
  ok: boolean;
  transfer_id: string;
  amount_usdt: Decimal;
  withdraw_fee_usdt: Decimal;
  futures_transferred_usdt: Decimal;
  binance_withdraw_id: string | null;
  destination_address: string;
  network: string;
  message: string;
}

export interface FundTransferHistoryOut {
  id: string;
  customer_id: string;
  customer_email: string | null;
  platform_admin_email: string | null;
  amount_usdt: Decimal;
  withdraw_fee_usdt: Decimal | null;
  futures_transferred_usdt: Decimal | null;
  destination_address: string;
  network: string;
  binance_withdraw_id: string | null;
  status: string;
  error_message: string | null;
  created_at: string | null;
}

export interface LoginResponse {
  admin: AdminOut;
  csrf_token: string;
  auth_provider?: "local" | "firebase";
}

export interface BotStatusOut {
  bot_enabled: boolean;
  mode: BotMode;
  run_state: RunState;
  started_at: string | null;
  safe_mode_reason: string | null;
  worker_heartbeat_at: string | null;
  worker_connected?: boolean;
  worker_stale_seconds?: number | null;
}

export interface EmergencyStopResponse {
  run_state: RunState;
  closed_positions: string[];
  failed_positions: string[];
}

export interface EmergencyCloseAllResponse {
  closed_positions: string[];
  failed_positions: string[];
  closed_count: number;
}

export interface AddLosingPositionsResponse {
  added_positions: string[];
  failed_positions: string[];
  skipped_positions: string[];
  added_count: number;
}

export interface ChangeModeResponse {
  mode: BotMode;
  message: string;
}

export interface DashboardOut {
  bot_enabled: boolean;
  run_state: RunState;
  mode: BotMode;
  binance_connected: boolean;
  futures_connected: boolean;
  worker_connected: boolean;
  worker_heartbeat_at?: string | null;
  worker_stale_seconds?: number | null;
  websocket_connected: boolean;

  total_futures_balance_usdt: Decimal;
  wallet_balance_usdt: Decimal;
  available_usdt: Decimal;
  used_margin_usdt: Decimal;
  open_positions_count: number;

  daily_realized_pnl_usdt: Decimal;
  daily_unrealized_pnl_usdt: Decimal;
  total_net_pnl_usdt: Decimal;

  today_trades_count: number;
  winning_trades_count: number;
  losing_trades_count: number;
  win_rate_pct: Decimal;

  total_commission_usdt: Decimal;
  total_funding_usdt: Decimal;

  last_analysis_at: string | null;
  last_signal_at: string | null;
  last_order_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;

  bot_uptime_seconds: number | null;

  usdt_try_rate?: Decimal | null;
}

export interface DashboardStatisticsOut {
  stat_date: string;
  trades_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: Decimal;
  gross_pnl_usdt: Decimal;
  net_pnl_usdt: Decimal;
  total_commission_usdt: Decimal;
  total_funding_usdt: Decimal;
}

export interface BotSettingsOut {
  mode: BotMode;
  live_trading_enabled: boolean;
  auto_trading_enabled: boolean;
  bot_enabled: boolean;

  margin_per_trade_usdt: Decimal;
  leverage: number;
  max_allowed_leverage: number;
  margin_type: string;
  position_mode: string;
  multi_assets_mode: boolean;

  take_profit_roi_pct: Decimal;
  stop_loss_roi_pct: Decimal;

  max_open_positions: number;
  max_open_positions_per_symbol: number;
  daily_max_loss_usdt: Decimal;
  max_consecutive_losses: number;

  candle_timeframe: string;
  scan_interval_seconds: number;
  post_trade_cooldown_minutes: number;
  min_24h_volume_usdt: Decimal;

  long_enabled: boolean;
  short_enabled: boolean;
  trailing_stop_enabled: boolean;
  trailing_stop_activation_roi_pct: Decimal;
  trailing_stop_callback_rate_pct: Decimal;

  max_spread_pct: Decimal;
  max_funding_rate_pct: Decimal;
  max_volatility_atr_pct: Decimal;

  ema_fast_period: number;
  ema_mid_period: number;
  ema_slow_period: number;
  rsi_period: number;
  atr_period: number;
  rsi_long_min: Decimal;
  rsi_long_max: Decimal;
  rsi_short_min: Decimal;
  rsi_short_max: Decimal;
  volume_multiplier_min: Decimal;
  min_signal_score: Decimal;
  top_n_symbols_by_volume: number;

  working_type: string;
  min_liquidation_distance_pct: Decimal;
  max_slippage_pct: Decimal;

  paper_taker_commission_rate: Decimal;
  paper_start_balance_usdt: Decimal;
  paper_funding_simulation_enabled: boolean;

  limit_entry_enabled: boolean;
  limit_entry_offset_pct: Decimal;
  limit_entry_timeout_minutes: number;
  limit_entry_max_pending: number;

  loss_add_enabled: boolean;
  loss_add_trigger_roi_pct: Decimal;
  loss_add_max_count: number;

  market_direction_filter_enabled: boolean;

  take_profit_confetti_enabled: boolean;

  enhanced_engine_enabled: boolean;
  enhanced_engine_shadow_mode: boolean;
  enhanced_engine_live_enabled: boolean;
  shadow_mode_active: boolean;
  market_regime_enabled: boolean;
  symbol_profile_enabled: boolean;
  correlation_control_enabled: boolean;
  ai_explanation_enabled: boolean;
  ai_model: string;
  min_regime_confidence: Decimal;
  max_allowed_risk_score: Decimal;
  minimum_risk_reward_ratio: Decimal;
}

export type BotSettingsUpdate = Partial<
  Pick<
    BotSettingsOut,
    | "margin_per_trade_usdt"
    | "leverage"
    | "take_profit_roi_pct"
    | "stop_loss_roi_pct"
    | "max_open_positions"
    | "max_open_positions_per_symbol"
    | "daily_max_loss_usdt"
    | "max_consecutive_losses"
    | "candle_timeframe"
    | "scan_interval_seconds"
    | "post_trade_cooldown_minutes"
    | "min_24h_volume_usdt"
    | "max_spread_pct"
    | "max_funding_rate_pct"
    | "max_volatility_atr_pct"
    | "long_enabled"
    | "short_enabled"
    | "auto_trading_enabled"
    | "trailing_stop_enabled"
    | "trailing_stop_activation_roi_pct"
    | "trailing_stop_callback_rate_pct"
    | "ema_fast_period"
    | "ema_mid_period"
    | "ema_slow_period"
    | "rsi_period"
    | "atr_period"
    | "rsi_long_min"
    | "rsi_long_max"
    | "rsi_short_min"
    | "rsi_short_max"
    | "volume_multiplier_min"
    | "min_signal_score"
    | "top_n_symbols_by_volume"
    | "min_liquidation_distance_pct"
    | "max_slippage_pct"
    | "bot_enabled"
    | "limit_entry_enabled"
    | "limit_entry_offset_pct"
    | "limit_entry_timeout_minutes"
    | "limit_entry_max_pending"
    | "loss_add_enabled"
    | "loss_add_trigger_roi_pct"
    | "loss_add_max_count"
    | "market_direction_filter_enabled"
    | "take_profit_confetti_enabled"
    | "enhanced_engine_enabled"
    | "enhanced_engine_shadow_mode"
    | "shadow_mode_active"
    | "market_regime_enabled"
    | "symbol_profile_enabled"
    | "correlation_control_enabled"
    | "ai_explanation_enabled"
    | "ai_model"
    | "min_regime_confidence"
    | "max_allowed_risk_score"
    | "minimum_risk_reward_ratio"
  >
>;

export interface TimeframeAnalysisOut {
  interval: string;
  price: number;
  ema_fast: number;
  ema_mid: number;
  ema_slow: number;
  rsi: number;
  change_1h_pct: number;
  change_4h_pct: number;
  trend: string;
  momentum: string;
}

export interface MarketRegimeOut {
  symbol: string;
  direction: "LONG" | "SHORT" | "NEUTRAL";
  confidence: number;
  btc_price: number;
  change_1h_pct: number;
  change_4h_pct: number;
  primary: TimeframeAnalysisOut;
  confirm: TimeframeAnalysisOut;
  long_score: number;
  short_score: number;
  reason: string;
  recommendation: string;
  components: Record<string, number>;
  analyzed_at: string;
  primary_interval: string;
  confirm_interval: string;
}

export interface MarketOverviewOut {
  analyzed_at: string;
  universe_count: number;
  rising_count: number;
  falling_count: number;
  flat_count: number;
  rising_pct: number;
  falling_pct: number;
  flat_pct: number;
  sentiment: "BULLISH" | "BEARISH" | "NEUTRAL" | string;
  sentiment_score: number;
  buy_pressure_pct: number;
  sell_pressure_pct: number;
  avg_change_pct: number;
  median_change_pct: number;
  total_volume_24h_usdt: number;
  btc: {
    symbol: string;
    last_price: number;
    change_24h_pct: number;
    mark_price: number;
    funding_rate_pct: number;
    quote_volume_24h_usdt: number;
  };
  order_book_pressure?: {
    symbol: string;
    bid_qty: number;
    ask_qty: number;
    bid_pct: number;
    ask_pct: number;
    bias: "BUY" | "SELL" | "NEUTRAL" | string;
  } | null;
  bot_regime_direction?: string | null;
  market_direction_filter_enabled: boolean;
  top_gainers: TickerMoverOut[];
  top_losers: TickerMoverOut[];
  top_volume: TickerMoverOut[];
}

export interface TickerMoverOut {
  symbol: string;
  last_price: number;
  change_pct: number;
  quote_volume_usdt: number;
}

export interface MarketAiResearchOut {
  executive_summary: string;
  market_outlook: "BULLISH" | "BEARISH" | "NEUTRAL" | "UNCERTAIN" | string;
  confidence_pct: number;
  btc_analysis: string;
  altcoin_implications: string;
  key_observations: string[];
  risk_factors: string[];
  opportunities: string[];
  time_horizon: string;
  analyst_note: string;
  disclaimer: string;
  status: string;
  model?: string | null;
  cached: boolean;
  generated_at?: string | null;
}

export interface BinanceStatusOut {
  environment: BotMode;
  is_configured: boolean;
  is_connected: boolean;
  account_access_ok: boolean;
  futures_account_usable: boolean;
  trading_permission_ok: boolean;
  position_mode_verified: boolean;
  multi_assets_mode_off_verified: boolean;
  last_success_at: string | null;
  last_error_at: string | null;
  last_error_message: string | null;
  not_configured_message?: string | null;
}

export interface BinanceAccountBalanceOut {
  asset: string;
  wallet_balance: Decimal;
  available_balance: Decimal;
  unrealized_pnl: Decimal;
}

export interface BinanceAccountInfoOut {
  total_wallet_balance: Decimal;
  total_unrealized_pnl: Decimal;
  total_margin_balance: Decimal;
  available_balance: Decimal;
  can_trade: boolean;
  multi_assets_margin: boolean;
}

export interface BinancePositionOut {
  symbol: string;
  position_side: PositionSide;
  quantity: Decimal;
  entry_price: Decimal;
  mark_price: Decimal;
  unrealized_pnl: Decimal;
  leverage: number;
  margin_type: string;
  liquidation_price: Decimal;
}

export interface BinanceOrderOut {
  symbol: string;
  binance_order_id: string;
  client_order_id: string;
  side: string;
  order_type: string;
  status: string;
  price: Decimal;
  orig_qty: Decimal;
  executed_qty: Decimal;
}

export interface ReconciliationRunOut {
  id: string;
  triggered_by: string;
  status: string;
  mismatches_found: number;
  external_positions_found: number;
  entered_safe_mode: boolean;
  ran_at: string;
}

export interface SymbolOut {
  symbol: string;
  status: string;
  contract_type: string;
  price_tick_size: Decimal;
  lot_step_size: Decimal;
  min_qty: Decimal;
  min_notional: Decimal;
  last_price: Decimal | null;
  mark_price: Decimal | null;
  funding_rate: Decimal | null;
  volume_24h_usdt: Decimal | null;
  spread_pct: Decimal | null;

  in_analysis_list: boolean;
  is_blacklisted: boolean;
  blacklist_reason: string | null;
  long_enabled: boolean;
  short_enabled: boolean;
  max_leverage_override: number | null;
  last_signal_id: string | null;
  last_trade_at: string | null;

  required_min_margin_at_3x: Decimal | null;
}

export interface SymbolUpdateRequest {
  in_analysis_list?: boolean;
  is_blacklisted?: boolean;
  blacklist_reason?: string | null;
  long_enabled?: boolean;
  short_enabled?: boolean;
  max_leverage_override?: number | null;
  notes?: string | null;
}

export interface PositionOut {
  id: string;
  symbol: string;
  side: PositionSide;
  status: "OPEN" | "CLOSED";
  bot_mode: BotMode;
  margin_type: string;
  leverage: number;
  margin_usdt: Decimal;
  notional_usdt: Decimal;
  quantity: Decimal;
  entry_price: Decimal;
  mark_price: Decimal | null;
  break_even_price: Decimal | null;
  liquidation_price: Decimal | null;
  stop_loss_price: Decimal | null;
  take_profit_price: Decimal | null;
  unrealized_pnl: Decimal;
  roi_pct: Decimal;
  margin_ratio_pct: Decimal | null;
  funding_fee_usdt: Decimal;
  protective_orders_ok: boolean;
  loss_add_count: number;
  open_reason: string | null;
  opened_at: string;
  closed_at: string | null;
  is_external: boolean;
}

export interface OrderOut {
  id: string;
  position_id: string | null;
  symbol: string;
  side: string;
  order_type: string;
  purpose: string;
  reduce_only: boolean;
  quantity: Decimal;
  price: Decimal | null;
  avg_fill_price: Decimal | null;
  filled_quantity: Decimal;
  commission_usdt: Decimal;
  client_order_id: string;
  binance_order_id: string | null;
  status: string;
  retry_count: number;
  last_error: string | null;
  bot_mode: BotMode;
  submitted_at: string | null;
  created_at: string;
  filled_at: string | null;
  canceled_at: string | null;
}

export interface TradeOut {
  id: string;
  position_id: string;
  symbol: string;
  side: PositionSide;
  bot_mode: BotMode;
  entry_price: Decimal;
  exit_price: Decimal;
  margin_usdt: Decimal;
  leverage: number;
  quantity: Decimal;
  notional_usdt: Decimal;
  gross_pnl_usdt: Decimal;
  open_commission_usdt: Decimal;
  close_commission_usdt: Decimal;
  funding_fee_usdt: Decimal;
  net_pnl_usdt: Decimal;
  gross_roi_pct: Decimal;
  net_roi_pct: Decimal;
  open_reason: string | null;
  close_reason: string;
  stop_loss_price: Decimal | null;
  take_profit_price: Decimal | null;
  binance_order_id_open: string | null;
  binance_order_id_close: string | null;
  client_order_id_open: string | null;
  client_order_id_close: string | null;
  opened_at: string;
  closed_at: string;
}

export interface TradePnlPeriodSummary {
  net_pnl_usdt: Decimal;
  gross_pnl_usdt: Decimal;
  trades_count: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: Decimal;
}

export interface TradePnlSummaryOut {
  last_24h: TradePnlPeriodSummary;
  last_7d: TradePnlPeriodSummary;
  last_30d: TradePnlPeriodSummary;
}

export interface AnalysisResultOut {
  id: string;
  symbol: string;
  analyzed_at: string;
  price: Decimal;
  mark_price: Decimal;
  ema_fast: Decimal;
  ema_mid: Decimal;
  ema_slow: Decimal;
  rsi_value: Decimal;
  atr_value: Decimal;
  trend_score: Decimal;
  ema_score: Decimal;
  rsi_score: Decimal;
  volume_score: Decimal;
  volatility_score: Decimal;
  spread_score: Decimal;
  funding_score: Decimal;
  open_interest_score: Decimal;
  total_score: Decimal;
  suggested_side: PositionSide | null;
  decision: string;
  reason: string;
  bot_mode: BotMode;
}

export interface StrategySignalOut {
  id: string;
  symbol: string;
  side: PositionSide;
  total_score: Decimal;
  bot_mode: BotMode;
  consumed: boolean;
  resulting_position_id: string | null;
  created_at: string;
}

export type SignalEntryMode = "market" | "limit" | "settings";

export interface ExecuteSignalResponse {
  signal_id: string;
  status: "opened" | "limit_pending";
  position_id: string | null;
  order_id: string | null;
  message: string | null;
}

export interface BotEventOut {
  id: string;
  event_type: string;
  message: string;
  details: Record<string, unknown> | null;
  bot_mode: BotMode | null;
  admin_id: string | null;
  created_at: string;
}

export interface RiskEventOut {
  id: string;
  event_type: string;
  symbol: string | null;
  severity: string;
  message: string;
  details: Record<string, unknown> | null;
  bot_mode: BotMode | null;
  created_at: string;
}

export interface AuditLogOut {
  id: string;
  admin_id: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  before_data: Record<string, unknown> | null;
  after_data: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export interface SystemStatusOut {
  overall_status: string;
  components: { component: string; status: string; message: string | null; checked_at: string | null }[];
}

export interface TelegramTestOut {
  ok: boolean;
  message: string;
  configured: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PositionSyncOut {
  local_open_count: number;
  exchange_open_count: number;
  closed_ghosts: string[];
  synced_at: string;
  in_sync: boolean;
  skipped_throttle?: boolean;
}

export interface DashboardWsPositionSnapshot {
  id: string;
  symbol: string;
  side: PositionSide;
  entry_price: Decimal;
  mark_price: Decimal | null;
  unrealized_pnl: Decimal;
  roi_pct: Decimal;
}

export interface DashboardWsMessage {
  type: "snapshot";
  server_time: string;
  dashboard: DashboardOut;
  local_open_count?: number;
  exchange_open_count?: number;
  open_positions: DashboardWsPositionSnapshot[];
}

export interface EnhancedMarketRegimeOut {
  id?: string | null;
  regime: string;
  confidence: number;
  trend_strength: number;
  volatility_score: number;
  breadth_score: number;
  risk_off_score: number;
  reasons: string[];
  timeframe: string;
  btc_direction?: string | null;
  created_at?: string | null;
}

export interface TradeCandidateOut {
  scan_id: string;
  symbol: string;
  direction: string;
  signal_score: number;
  risk_score: number;
  risk_reward_ratio: number;
  regime_alignment_score: number;
  symbol_profile_score: number;
  correlation_penalty: number;
  final_opportunity_score: number;
  rank: number;
  selected: boolean;
  rejection_reason?: string | null;
}

export interface SymbolProfileOut {
  symbol: string;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  expectancy: number;
  max_drawdown: number;
  long_win_rate: number;
  short_win_rate: number;
  confidence_level: number;
  last_calculated_at?: string | null;
}

export interface LearningRunOut {
  id: string;
  period_start: string;
  period_end: string;
  total_trades: number;
  strategy_version: string;
  status: string;
  summary?: Record<string, unknown> | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface RecommendationOut {
  id: string;
  analysis_run_id: string;
  recommendation_type: string;
  target_scope: string;
  target_symbol?: string | null;
  expected_impact?: string | null;
  confidence: number;
  status: string;
  created_at: string;
}

export interface AiExplanationOut {
  signal_id: string;
  symbol: string;
  status: string;
  summary?: string | null;
  positive_factors: string[];
  negative_factors: string[];
  risk_level?: string | null;
  warnings: string[];
  suggestion?: string | null;
}

export interface StrategyVersionOut {
  id: string;
  version: string;
  name: string;
  description?: string | null;
  source: string;
  active_in_paper: boolean;
  active_in_demo: boolean;
  active_in_live: boolean;
  created_at: string;
}

export interface ShadowStatusOut {
  shadow_mode_active: boolean;
  enhanced_engine_shadow_mode: boolean;
  enhanced_engine_live_enabled: boolean;
  total_decisions: number;
  agreement_rate_pct: number;
}

export interface ShadowComparisonOut {
  agreement_rate_pct: number;
  disagreement_rate_pct: number;
  total_decisions: number;
  recent: { scan_id: string; current?: string | null; enhanced?: string | null; disagreement?: string | null; created_at?: string | null }[];
}

export type ImpulseMode = "OFF" | "MANUAL" | "AUTO";

export interface ImpulseSettingsOut {
  impulse_mode: ImpulseMode;
  impulse_btc_min_change_pct: Decimal;
  impulse_lookback_minutes: number;
  impulse_extreme_min_score: Decimal;
  impulse_max_entries: number;
  impulse_margin_usdt: Decimal;
  impulse_leverage: number;
  impulse_tp_roi_pct: Decimal;
  impulse_sl_roi_pct: Decimal;
  impulse_cooldown_minutes: number;
  impulse_top_n_scan: number;
  impulse_rsi_overbought: Decimal;
  impulse_rsi_oversold: Decimal;
  impulse_check_interval_seconds: number;
  impulse_last_event_at: string | null;
  impulse_last_direction: string | null;
  impulse_last_btc_change_pct: Decimal | null;
  impulse_last_opened_count: number;
  impulse_last_scan_at: string | null;
}

export interface ImpulseSettingsUpdate {
  impulse_mode?: ImpulseMode;
  impulse_btc_min_change_pct?: string;
  impulse_lookback_minutes?: number;
  impulse_extreme_min_score?: string;
  impulse_max_entries?: number;
  impulse_margin_usdt?: string;
  impulse_leverage?: number;
  impulse_tp_roi_pct?: string;
  impulse_sl_roi_pct?: string;
  impulse_cooldown_minutes?: number;
  impulse_top_n_scan?: number;
  impulse_rsi_overbought?: string;
  impulse_rsi_oversold?: string;
  impulse_check_interval_seconds?: number;
}

export interface ImpulseCandidateOut {
  symbol: string;
  side: string;
  score: number;
  rsi: number;
  proximity_pct: number;
  volume_ratio: number;
  price: number;
  reason: string;
}

export interface ImpulseScanOut {
  btc_direction: string;
  btc_change_pct: number;
  counter_side: string | null;
  cooldown_active: boolean;
  message: string;
  candidates: ImpulseCandidateOut[];
}

export interface ImpulseExecuteOut {
  opened: string[];
  skipped: string[];
  failed: string[];
  btc_direction: string;
  btc_change_pct: number;
  message: string;
}

export interface AvciCoinOut {
  symbol: string;
  last_price: number;
  change_pct: number;
  quote_volume_usdt: number;
}

export interface AvciScanOut {
  analyzed_at: string;
  top_gainers: AvciCoinOut[];
  top_losers: AvciCoinOut[];
  limit: number;
}

export interface AvciOpenOut {
  symbol: string;
  side: string;
  position_id: string;
  message: string;
  status: string;
}

export interface AvciKlineOut {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export type AvciChartHours = 1 | 4 | 6 | 12 | 24;

export interface AvciChartOut {
  symbol: string;
  interval: string;
  hours: AvciChartHours;
  change_pct: number;
  last_price: number;
  klines: AvciKlineOut[];
}

export interface ProfileConnectionsSummary {
  binance_configured: boolean;
  binance_source: string | null;
  telegram_configured: boolean;
  telegram_source: string | null;
  openai_configured: boolean;
  openai_source: string | null;
}

export interface ProfileOut {
  id: string;
  email: string;
  full_name: string | null;
  last_login_at: string | null;
  connections_unlocked: boolean;
  connections_summary: ProfileConnectionsSummary;
  firebase_uid: string | null;
  account_type: string;
}

export interface ProfileUnlockResponse {
  ok: boolean;
  connections_unlocked: boolean;
  expires_in_seconds: number;
}

export interface ProfileConnectionsOut {
  binance_api_key_masked: string | null;
  binance_api_secret_set: boolean;
  binance_configured: boolean;
  binance_source: string | null;
  telegram_bot_token_masked: string | null;
  telegram_chat_id: string | null;
  telegram_notifications_enabled: boolean;
  telegram_configured: boolean;
  telegram_source: string | null;
  openai_api_key_masked: string | null;
  openai_configured: boolean;
  openai_source: string | null;
}

export interface ProfileConnectionsUpdate {
  binance_api_key?: string | null;
  binance_api_secret?: string | null;
  telegram_bot_token?: string | null;
  telegram_chat_id?: string | null;
  telegram_notifications_enabled?: boolean | null;
  openai_api_key?: string | null;
}

export interface ProfileTestResult {
  ok: boolean;
  message: string;
}

export interface TelegramDiscoverChatIdResponse {
  ok: boolean;
  chat_id: string | null;
  message: string;
}

