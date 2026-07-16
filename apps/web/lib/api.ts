import { apiClient } from "./api-client";
import type {
  AdminOut,
  AnalysisResultOut,
  AuditLogOut,
  BinanceAccountBalanceOut,
  BinanceAccountInfoOut,
  BinanceOrderOut,
  BinancePositionOut,
  BinanceStatusOut,
  BotEventOut,
  BotSettingsOut,
  BotSettingsUpdate,
  BotStatusOut,
  ChangeModeResponse,
  DashboardOut,
  DashboardStatisticsOut,
  EmergencyStopResponse,
  EmergencyCloseAllResponse,
  AddLosingPositionsResponse,
  ExecuteSignalResponse,
  CustomerDetailOut,
  CustomerListItemOut,
  CustomerRegisterPendingOut,
  LoginResponse,
  MarketRegimeOut,
  OrderOut,
  PaginatedResponse,
  PositionOut,
  PositionSyncOut,
  ReconciliationRunOut,
  RiskEventOut,
  StrategySignalOut,
  SignalEntryMode,
  SymbolOut,
  SymbolUpdateRequest,
  SystemStatusOut,
  TradeOut,
} from "@/types/api";

export const authApi = {
  login: (email: string, password: string) => apiClient.post<LoginResponse>("/auth/login", { email, password }),
  customerLogin: (email: string, password: string) =>
    apiClient.post<LoginResponse>("/auth/customer-login", { email, password }),
  customerRegister: (payload: {
    email: string;
    password: string;
    full_name: string;
    phone: string;
    city: string;
    district: string;
  }) => apiClient.post<CustomerRegisterPendingOut>("/auth/customer-register", payload),
  firebaseLogin: (id_token: string) => apiClient.post<LoginResponse>("/auth/firebase-login", { id_token }),
  logout: () => apiClient.post<{ ok: boolean }>("/auth/logout"),
  me: () => apiClient.get<AdminOut>("/auth/me"),
};

export const platformAdminApi = {
  overview: () => apiClient.get<import("@/types/api").PlatformOverviewOut>("/platform/overview"),
  activity: (limit = 30) => apiClient.get<import("@/types/api").PlatformActivityOut[]>("/platform/activity", { limit }),
  customers: (params?: {
    approval_status?: string;
    search?: string;
    membership_filter?: "all" | "active" | "expiring" | "expired" | "none";
    page?: number;
    page_size?: number;
  }) => apiClient.get<PaginatedResponse<CustomerListItemOut>>("/platform/customers", params),
  customer: (id: string) => apiClient.get<CustomerDetailOut>(`/platform/customers/${id}`),
  deleteCustomer: (id: string) => apiClient.delete<import("@/types/api").CustomerDeleteOut>(`/platform/customers/${id}`),
  updateApproval: (id: string, payload: { approval_status: string; blocked_reason?: string | null; notes?: string | null; is_active?: boolean | null; membership_plan_id?: string | null }) =>
    apiClient.patch<CustomerDetailOut>(`/platform/customers/${id}/approval`, payload),
  customerEarnings: () => apiClient.get<import("@/types/api").PlatformEarningsSummaryOut>("/platform/customer-earnings"),
  customerEarningsDetail: (customerId: string) =>
    apiClient.get<import("@/types/api").CustomerEarningsDetailOut>(`/platform/customer-earnings/${customerId}`),
  customerPositions: (
    customerId: string,
    params?: { status_filter?: "OPEN" | "CLOSED"; page?: number; page_size?: number },
  ) =>
    apiClient.get<PaginatedResponse<import("@/types/api").PositionOut>>(
      `/platform/customers/${customerId}/positions`,
      params,
    ),
  trades: (params?: {
    symbol?: string;
    side?: string;
    bot_mode?: string;
    customer_id?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) => apiClient.get<PaginatedResponse<import("@/types/api").AdminTradeOut>>("/platform/trades", params),
  deleteTrade: (id: string) => apiClient.delete<void>(`/platform/trades/${id}`),
  membershipPlans: () => apiClient.get<import("@/types/api").MembershipPlanOut[]>("/platform/membership-plans"),
  membershipOverview: () => apiClient.get<import("@/types/api").MembershipOverviewOut>("/platform/memberships/overview"),
  extendMembership: (
    id: string,
    payload: { membership_plan_id?: string; duration_days?: number; note?: string | null },
  ) => apiClient.patch<CustomerDetailOut>(`/platform/customers/${id}/membership`, payload),
  fundTransfersEligible: () =>
    apiClient.get<import("@/types/api").WithdrawableCustomerOut[]>("/platform/fund-transfers/eligible"),
  fundTransferPreview: (customerId: string) =>
    apiClient.get<import("@/types/api").WithdrawableCustomerOut>(`/platform/fund-transfers/preview/${customerId}`),
  fundTransferExecute: (customerId: string) =>
    apiClient.post<import("@/types/api").FundTransferExecuteOut>(`/platform/fund-transfers/${customerId}/execute`),
  fundTransferHistory: (limit = 50) =>
    apiClient.get<import("@/types/api").FundTransferHistoryOut[]>("/platform/fund-transfers/history", { limit }),
};

export const profileApi = {
  get: () => apiClient.get<import("@/types/api").ProfileOut>("/profile"),
  updateFullName: (full_name: string | null) =>
    apiClient.put<import("@/types/api").ProfileOut>("/profile/full-name", { full_name }),
  unlock: (password: string) =>
    apiClient.post<import("@/types/api").ProfileUnlockResponse>("/profile/unlock", { password }),
  lock: () => apiClient.post<{ ok: boolean }>("/profile/lock"),
  getConnections: () => apiClient.get<import("@/types/api").ProfileConnectionsOut>("/profile/connections"),
  saveConnections: (payload: import("@/types/api").ProfileConnectionsUpdate) =>
    apiClient.put<import("@/types/api").ProfileConnectionsOut>("/profile/connections", payload),
  testBinance: () => apiClient.post<import("@/types/api").ProfileTestResult>("/profile/test/binance"),
  testTelegram: () => apiClient.post<import("@/types/api").ProfileTestResult>("/profile/test/telegram"),
  discoverTelegramChatId: (telegram_bot_token?: string) =>
    apiClient.post<import("@/types/api").TelegramDiscoverChatIdResponse>("/profile/telegram/discover-chat-id", {
      telegram_bot_token: telegram_bot_token?.trim() || undefined,
    }),
};

export const dashboardApi = {
  get: () => apiClient.get<DashboardOut>("/dashboard"),
  statistics: (days = 30) => apiClient.get<DashboardStatisticsOut[]>("/dashboard/statistics", { days }),
};

export const botApi = {
  status: () => apiClient.get<BotStatusOut>("/bot/status"),
  start: () => apiClient.post<BotStatusOut>("/bot/start"),
  stop: () => apiClient.post<BotStatusOut>("/bot/stop"),
  emergencyStop: (closeAllPositions: boolean, confirmationText: string | null) =>
    apiClient.post<EmergencyStopResponse>("/bot/emergency-stop", {
      close_all_positions: closeAllPositions,
      confirmation_text: confirmationText,
    }),
  changeMode: (targetMode: string, confirmationText: string | null, riskAck: boolean) =>
    apiClient.post<ChangeModeResponse>("/bot/change-mode", {
      target_mode: targetMode,
      confirmation_text: confirmationText,
      risk_ack: riskAck,
    }),
};

export type SettingsResetScope = "general" | "position" | "impulse" | "all";

export const settingsApi = {
  get: () => apiClient.get<BotSettingsOut>("/settings"),
  update: (payload: BotSettingsUpdate) => apiClient.put<BotSettingsOut>("/settings", payload),
  resetDefaults: (scope: SettingsResetScope = "general") =>
    apiClient.post<BotSettingsOut>("/settings/reset-defaults", undefined, { scope }),
};

export const binanceApi = {
  status: () => apiClient.get<BinanceStatusOut>("/binance/status"),
  testConnection: () => apiClient.post<BinanceStatusOut>("/binance/test-connection"),
  account: () => apiClient.get<BinanceAccountInfoOut>("/binance/account"),
  balance: () => apiClient.get<BinanceAccountBalanceOut[]>("/binance/balance"),
  positions: () => apiClient.get<BinancePositionOut[]>("/binance/positions"),
  openOrders: () => apiClient.get<BinanceOrderOut[]>("/binance/open-orders"),
  openAlgoOrders: () => apiClient.get<BinanceOrderOut[]>("/binance/open-algo-orders"),
  reconcile: () => apiClient.post<ReconciliationRunOut>("/binance/reconcile"),
};

export const symbolsApi = {
  list: () => apiClient.get<SymbolOut[]>("/symbols"),
  get: (symbol: string) => apiClient.get<SymbolOut>(`/symbols/${symbol}`),
  update: (symbol: string, payload: SymbolUpdateRequest) =>
    apiClient.patch<SymbolOut>(`/symbols/${symbol}`, payload),
};

export interface PageQuery {
  page?: number;
  page_size?: number;
  [key: string]: string | number | boolean | undefined | null;
}

export const positionsApi = {
  list: (query?: PageQuery) => apiClient.get<PaginatedResponse<PositionOut>>("/positions", query),
  get: (id: string) => apiClient.get<PositionOut>(`/positions/${id}`),
  close: (id: string, reason = "MANUAL") => apiClient.post<PositionOut>(`/positions/${id}/close`, { reason }),
  add: (id: string) => apiClient.post<PositionOut>(`/positions/${id}/add`),
  emergencyCloseAll: (password: string) =>
    apiClient.post<EmergencyCloseAllResponse>("/positions/emergency-close-all", { password }),
  addLosing: () => apiClient.post<AddLosingPositionsResponse>("/positions/add-losing"),
  sync: () => apiClient.post<PositionSyncOut>("/positions/sync"),
  oltaPositions: (status?: string) =>
    apiClient.get<PaginatedResponse<PositionOut>>("/positions", {
      open_reason: "limit_entry_filled",
      status_filter: status ?? "OPEN",
      page_size: 50,
    }),
};

export const ordersApi = {
  list: (query?: PageQuery) => apiClient.get<PaginatedResponse<OrderOut>>("/orders", query),
  get: (id: string) => apiClient.get<OrderOut>(`/orders/${id}`),
  cancel: (id: string) => apiClient.post<OrderOut>(`/orders/${id}/cancel`),
  pendingLimit: () =>
    apiClient.get<PaginatedResponse<OrderOut>>("/orders", {
      active_only: true,
      order_type: "LIMIT",
      purpose: "OPEN",
      page_size: 50,
    }),
};

export const marketApi = {
  regime: () => apiClient.get<MarketRegimeOut>("/market/regime"),
  overview: (forceRefresh = false) =>
    apiClient.get<import("@/types/api").MarketOverviewOut>("/market/overview", {
      force_refresh: forceRefresh,
    }),
  aiResearch: (forceRefresh = false) =>
    apiClient.post<import("@/types/api").MarketAiResearchOut>(
      "/market/ai-research",
      undefined,
      { force_refresh: forceRefresh }
    ),
};

export const tradesApi = {
  list: (query?: PageQuery) => apiClient.get<PaginatedResponse<TradeOut>>("/trades", query),
  get: (id: string) => apiClient.get<TradeOut>(`/trades/${id}`),
  pnlSummary: (query?: { symbol?: string }) =>
    apiClient.get<import("@/types/api").TradePnlSummaryOut>("/trades/pnl-summary", query),
};

export const signalsApi = {
  list: (query?: { symbol?: string; limit?: number }) => apiClient.get<StrategySignalOut[]>("/signals", query),
  analysis: (query?: { symbol?: string; limit?: number }) =>
    apiClient.get<AnalysisResultOut[]>("/signals/analysis", query),
  execute: (id: string, entryMode: SignalEntryMode = "market") =>
    apiClient.post<ExecuteSignalResponse>(`/signals/${id}/execute`, { entry_mode: entryMode }),
};

export const logsApi = {
  botEvents: (query?: PageQuery) => apiClient.get<PaginatedResponse<BotEventOut>>("/logs", query),
  auditLogs: (query?: PageQuery) => apiClient.get<PaginatedResponse<AuditLogOut>>("/audit-logs", query),
  riskEvents: (query?: PageQuery) => apiClient.get<PaginatedResponse<RiskEventOut>>("/risk-events", query),
};

export const systemApi = {
  status: () => apiClient.get<SystemStatusOut>("/system/status"),
  telegramTest: () => apiClient.post<import("@/types/api").TelegramTestOut>("/system/telegram-test"),
};

export const enhancedApi = {
  marketRegimeCurrent: () => apiClient.get<import("@/types/api").EnhancedMarketRegimeOut>("/market-regime/current"),
  marketRegimeHistory: (limit = 50) =>
    apiClient.get<import("@/types/api").EnhancedMarketRegimeOut[]>("/market-regime/history", { limit }),
  tradeCandidates: () => apiClient.get<import("@/types/api").TradeCandidateOut[]>("/trade-candidates"),
  tradeCandidatesByScan: (scanId: string) =>
    apiClient.get<import("@/types/api").TradeCandidateOut[]>(`/trade-candidates/${scanId}`),
  symbolProfiles: () => apiClient.get<import("@/types/api").SymbolProfileOut[]>("/symbol-profiles"),
  symbolProfile: (symbol: string) => apiClient.get<import("@/types/api").SymbolProfileOut>(`/symbol-profiles/${symbol}`),
  learningRuns: () => apiClient.get<import("@/types/api").LearningRunOut[]>("/learning/analysis-runs"),
  runLearning: (days = 30) => apiClient.post<import("@/types/api").LearningRunOut>("/learning/run", undefined, { days }),
  learningRecommendations: (status?: string) =>
    apiClient.get<import("@/types/api").RecommendationOut[]>("/learning/recommendations", status ? { status } : undefined),
  approveRecommendation: (id: string) => apiClient.post<import("@/types/api").RecommendationOut>(`/learning/recommendations/${id}/approve`),
  rejectRecommendation: (id: string) => apiClient.post<import("@/types/api").RecommendationOut>(`/learning/recommendations/${id}/reject`),
  paperTestRecommendation: (id: string) =>
    apiClient.post<import("@/types/api").RecommendationOut>(`/learning/recommendations/${id}/paper-test`),
  strategyVersions: () => apiClient.get<import("@/types/api").StrategyVersionOut[]>("/strategy-versions"),
  activateStrategyPaper: (id: string) => apiClient.post<import("@/types/api").StrategyVersionOut>(`/strategy-versions/${id}/activate-paper`),
  activateStrategyDemo: (id: string) => apiClient.post<import("@/types/api").StrategyVersionOut>(`/strategy-versions/${id}/activate-demo`),
  activateStrategyLive: (id: string) => apiClient.post<import("@/types/api").StrategyVersionOut>(`/strategy-versions/${id}/activate-live`),
  rollbackStrategy: (id: string) => apiClient.post<import("@/types/api").StrategyVersionOut>(`/strategy-versions/${id}/rollback`),
  aiExplanation: (signalId: string) => apiClient.get<import("@/types/api").AiExplanationOut>(`/ai-explanations/${signalId}`),
  riskAnalysis: (signalId: string) => apiClient.get<Record<string, unknown>>(`/risk-analysis/${signalId}`),
  shadowStatus: () => apiClient.get<import("@/types/api").ShadowStatusOut>("/shadow-mode/status"),
  shadowComparison: () => apiClient.get<import("@/types/api").ShadowComparisonOut>("/shadow-mode/comparison"),
  shadowStart: () => apiClient.post<{ ok: boolean }>("/shadow-mode/start"),
  shadowStop: () => apiClient.post<{ ok: boolean }>("/shadow-mode/stop"),
};

export const impulseApi = {
  settings: () => apiClient.get<import("@/types/api").ImpulseSettingsOut>("/impulse/settings"),
  updateSettings: (payload: import("@/types/api").ImpulseSettingsUpdate) =>
    apiClient.put<import("@/types/api").ImpulseSettingsOut>("/impulse/settings", payload),
  scan: (side?: string) =>
    apiClient.post<import("@/types/api").ImpulseScanOut>("/impulse/scan", undefined, side ? { side } : undefined),
  execute: (payload?: { side?: string; symbols?: string[]; max_entries?: number }) =>
    apiClient.post<import("@/types/api").ImpulseExecuteOut>("/impulse/execute", payload ?? {}),
};

export const avciApi = {
  scan: (limit = 15) => apiClient.get<import("@/types/api").AvciScanOut>("/avci/scan", { limit }),
  chart: (symbol: string, hours: import("@/types/api").AvciChartHours = 1) =>
    apiClient.get<import("@/types/api").AvciChartOut>("/avci/chart", { symbol, hours }),
  open: (symbol: string, side: "LONG" | "SHORT") =>
    apiClient.post<import("@/types/api").AvciOpenOut>("/avci/open", { symbol, side }),
};
