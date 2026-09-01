const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
const TOKEN_STORAGE_KEY = "aparix_access_token";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response wasn't JSON — fall back to statusText
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ── Types (mirrors apps/api/app/schemas/*.py) ─────────────────────────────

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserPreferences {
  experience_level: string;
  complexity_level: number;
  ai_detail_level: number;
  ai_mode: string;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  preferences: UserPreferences;
  is_admin: boolean;
  role: UserRole;
}

export interface Portfolio {
  id: string;
  name: string;
  kind: string;
}

export interface Holding {
  id: string;
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  avg_price: number;
  last_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface SectorExposure {
  sector: string;
  weight_pct: number;
  value: number;
}

export interface PortfolioAnalytics {
  portfolio_id: string;
  total_value: number;
  total_invested: number;
  total_pnl: number;
  total_pnl_pct: number;
  day_pnl: number;
  day_pnl_pct: number;
  holdings_count: number;
  sector_exposure: SectorExposure[];
  concentration_score: number;
  annualized_volatility_pct: number | null;
  beta_vs_nifty: number | null;
  risk_score: number;
  is_mock: boolean;
}

export interface Security {
  id: string;
  symbol: string;
  name: string;
  sector: string;
  is_index: boolean;
  is_mock: boolean;
}

export interface RiskMatrix {
  symbols: string[];
  matrix: Record<string, Record<string, number | null>>;
}

export interface RiskProfile {
  portfolio_id: string;
  sample_size: number;
  risk_free_rate_annual_pct: number;
  var_95_pct: number | null;
  var_99_pct: number | null;
  cvar_95_pct: number | null;
  cvar_99_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number | null;
  correlation_matrix: RiskMatrix | null;
  covariance_matrix: RiskMatrix | null;
  is_mock: boolean;
}

export interface MonteCarloResult {
  method: string;
  horizon_days: number;
  num_paths: number;
  current_value: number;
  p5: number;
  p25: number;
  p50: number;
  p75: number;
  p95: number;
  probability_of_loss_pct: number;
  sample_paths: number[][];
  assumptions: string;
  is_mock: boolean;
}

export interface HoldingShockImpact {
  symbol: string;
  sector: string;
  shock_applied_pct: number;
  impact: number;
  basis: string;
}

export interface StressTestResult {
  target: string;
  shock_pct: number;
  portfolio_value_before: number;
  estimated_impact: number;
  estimated_impact_pct: number;
  portfolio_value_after: number;
  per_holding_impact: HoldingShockImpact[];
  assumptions: string;
  is_mock: boolean;
}

export interface EquityPoint {
  trade_date: string;
  value: number;
}

export interface BacktestResult {
  id: string | null;
  initial_value: number;
  final_value: number;
  total_return_pct: number;
  cagr_pct: number | null;
  sharpe_ratio: number | null;
  sortino_ratio: number | null;
  max_drawdown_pct: number | null;
  annualized_volatility_pct: number | null;
  num_trading_days: number;
  equity_curve: EquityPoint[];
  assumptions: string;
  created_at: string | null;
  is_mock: boolean;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  message: string;
  mode: string;
  provider: string;
  tool_calls: ToolCall[];
}

export interface AiConfig {
  provider: string;
  model: string | null;
  supported_modes: string[];
}

export interface MacroIndicator {
  code: string;
  name: string;
  value: number;
  unit: string;
  is_mock: boolean;
}

export interface AparixEvent {
  id: string;
  headline: string;
  summary: string;
  event_type: string;
  severity: "low" | "medium" | "high";
  direction: "positive" | "negative" | "neutral";
  primary_target: string;
  secondary_tags: string[];
  region: string | null;
  published_at: string;
  is_mock: boolean;
}

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  url: string;
  publisher: string;
  published_at: string;
  discovered_at: string;
  language: string;
  region: string | null;
  source: string;
  event_id: string | null;
  is_mock: boolean;
}

export interface NewsIngestResult {
  provider: string;
  fetched: number;
  new_articles: number;
  events_created: number;
}

export interface EventImpact {
  event_id: string;
  headline: string;
  severity: string;
  direction: string;
  target: string;
  shock_pct: number;
  portfolio_value_before: number;
  estimated_impact: number;
  estimated_impact_pct: number;
  portfolio_value_after: number;
  per_holding_impact: HoldingShockImpact[];
  assumptions: string;
  is_mock: boolean;
}

export type UserRole = "super_admin" | "admin" | "compliance" | "analyst" | "support" | "user";

export const ALL_ROLES: UserRole[] = ["super_admin", "admin", "compliance", "analyst", "support", "user"];

export interface AdminUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  created_at: string;
  experience_level: string;
  complexity_level: number;
  portfolio_count: number;
}

export interface AdminAuditLog {
  id: string;
  user_id: string | null;
  action: string;
  result: string;
  created_at: string;
}

export interface AdminAiUsage {
  total_sessions: number;
  total_messages: number;
  tool_usage: { tool_name: string; count: number }[];
}

export interface AdminSystemHealth {
  users_count: number;
  portfolios_count: number;
  securities_count: number;
  events_count: number;
  last_market_tick: string | null;
  database_backend: string;
}

export interface DataQualityFinding {
  check: string;
  status: "GOOD" | "WARNING" | "STALE" | "INVALID" | "UNKNOWN";
  detail: string;
}

export interface PaperPortfolio {
  id: string;
  name: string;
  cash_balance: number;
  is_mock: boolean;
}

export interface PaperOrder {
  id: string;
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  requested_price: number;
  fill_price: number | null;
  slippage_pct: number | null;
  brokerage_fee: number | null;
  status: "filled" | "rejected";
  rejection_reason: string | null;
  created_at: string;
  is_mock: boolean;
}

export interface TradePreview {
  symbol: string;
  side: "buy" | "sell";
  quantity: number;
  estimated_fill_price: number;
  estimated_slippage_pct: number;
  estimated_brokerage: number;
  estimated_total: number;
  cash_before: number;
  cash_after: number;
  affordable: boolean;
  concentration_score_before: number;
  concentration_score_after: number;
  sector_exposure_after: SectorExposure[];
  is_mock: boolean;
}

export interface OrderEvaluation {
  order_id: string;
  symbol: string | null;
  side: string;
  status: string;
  fill_price: number | null;
  range_30d_low: number | null;
  range_30d_high: number | null;
  fill_percentile_in_30d_range: number | null;
  slippage_pct: number | null;
  brokerage_fee: number | null;
  assumptions: string;
  is_mock: boolean;
}

export interface BrokerStatus {
  connected: boolean;
  broker: string | null;
  status: "connected" | "expired" | null;
  broker_user_id: string | null;
  connected_at: string | null;
  last_synced_at: string | null;
  live_trading_enabled: boolean;
}

export interface BrokerLoginUrl {
  broker: string;
  login_url: string;
}

export interface BrokerHolding {
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  avg_price: number;
  last_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface BrokerPortfolio {
  id: string;
  name: string;
  holdings: BrokerHolding[];
  total_value: number;
  is_mock: boolean;
}

export interface BrokerSyncResult {
  synced_holdings: number;
  skipped_symbols: string[];
  synced_at: string;
}

export interface BrokerOrderResult {
  broker_order_id: string;
  status: string;
  fill_price: number | null;
  message: string | null;
}

export interface FinancialStatement {
  symbol: string;
  period_end: string;
  period_type: "annual" | "quarterly";
  fiscal_year: number;
  announcement_date: string;
  effective_date: string;
  is_restated: boolean;
  currency: string;
  unit: string;
  shares_outstanding: number | null;
  revenue: number;
  gross_profit: number;
  ebitda: number;
  ebit: number;
  pbt: number;
  pat: number;
  eps: number;
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  cash_and_equivalents: number;
  total_debt: number;
  current_assets: number;
  current_liabilities: number;
  interest_expense: number;
  cfo: number;
  cfi: number;
  cff: number;
  free_cash_flow: number;
  is_mock: boolean;
}

export interface FundamentalRatios {
  symbol: string;
  as_of: string;
  period_end: string;
  price_used: number | null;
  price_as_of: string | null;
  roe_pct: number | null;
  roce_pct: number | null;
  roa_pct: number | null;
  debt_to_equity: number | null;
  interest_coverage: number | null;
  current_ratio: number | null;
  asset_turnover: number | null;
  market_cap: number | null;
  pe_ratio: number | null;
  pb_ratio: number | null;
  enterprise_value: number | null;
  ev_to_ebitda: number | null;
  ev_to_sales: number | null;
  fcf_yield_pct: number | null;
  assumptions: string;
  is_mock: boolean;
}

export interface CorporateAction {
  id: string;
  symbol: string;
  action_type: "dividend" | "split" | "bonus" | "rights" | "buyback" | "merger" | "demerger" | "symbol_change" | "isin_change" | "delisting";
  ratio: number | null;
  amount: number | null;
  new_security_symbol: string | null;
  announcement_date: string;
  record_date: string | null;
  ex_date: string;
  effective_date: string;
  source: string;
  is_mock: boolean;
}

export interface ExpiryList {
  symbol: string;
  expiries: string[];
}

export interface OptionContract {
  strike: number;
  option_type: "call" | "put";
  premium: number;
  iv_pct: number;
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface OptionChain {
  symbol: string;
  spot: number;
  expiry: string;
  days_to_expiry: number;
  risk_free_rate_annual_pct: number;
  contracts: OptionContract[];
  is_mock: boolean;
}

// ── API surface ─────────────────────────────────────────────────────────

export const api = {
  auth: {
    register: (payload: { email: string; password: string; full_name: string }) =>
      request<TokenPair>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(payload) }),
    login: (payload: { email: string; password: string }) =>
      request<TokenPair>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(payload) }),
    me: () => request<User>("/api/v1/auth/me"),
  },
  users: {
    updatePreferences: (payload: Partial<UserPreferences>) =>
      request<User>("/api/v1/users/me/preferences", { method: "PATCH", body: JSON.stringify(payload) }),
  },
  portfolios: {
    list: () => request<Portfolio[]>("/api/v1/portfolios"),
    create: (payload: { name: string; kind: string }) =>
      request<Portfolio>("/api/v1/portfolios", { method: "POST", body: JSON.stringify(payload) }),
    holdings: (portfolioId: string) => request<Holding[]>(`/api/v1/portfolios/${portfolioId}/holdings`),
    addHolding: (portfolioId: string, payload: { symbol: string; quantity: number; avg_price: number }) =>
      request<Holding>(`/api/v1/portfolios/${portfolioId}/holdings`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    analytics: (portfolioId: string) =>
      request<PortfolioAnalytics>(`/api/v1/portfolios/${portfolioId}/analytics`),
  },
  market: {
    securities: () => request<Security[]>("/api/v1/market/securities"),
  },
  risk: {
    profile: (portfolioId: string) => request<RiskProfile>(`/api/v1/portfolios/${portfolioId}/risk`),
  },
  simulation: {
    monteCarlo: (portfolioId: string, payload: { method: "gbm" | "bootstrap"; horizon_days: number; num_paths: number }) =>
      request<MonteCarloResult>(`/api/v1/portfolios/${portfolioId}/monte-carlo`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    stressTest: (portfolioId: string, payload: { target: string; shock_pct: number }) =>
      request<StressTestResult>(`/api/v1/portfolios/${portfolioId}/stress-test`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    runBacktest: (portfolioId: string, payload: { initial_value: number }) =>
      request<BacktestResult>(`/api/v1/portfolios/${portfolioId}/backtest`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    backtestHistory: (portfolioId: string) =>
      request<BacktestResult[]>(`/api/v1/portfolios/${portfolioId}/backtests`),
  },
  ai: {
    chat: (payload: { portfolio_id: string; message: string; session_id?: string }) =>
      request<ChatResponse>("/api/v1/ai/chat", { method: "POST", body: JSON.stringify(payload) }),
    config: () => request<AiConfig>("/api/v1/ai/config"),
  },
  events: {
    list: () => request<AparixEvent[]>("/api/v1/events"),
    impact: (eventId: string, portfolioId: string) =>
      request<EventImpact>(`/api/v1/events/${eventId}/impact?portfolio_id=${portfolioId}`),
  },
  news: {
    list: () => request<NewsArticle[]>("/api/v1/news"),
    ingest: () => request<NewsIngestResult>("/api/v1/news/ingest", { method: "POST" }),
  },
  macro: {
    indicators: () => request<MacroIndicator[]>("/api/v1/macro/indicators"),
  },
  admin: {
    users: () => request<AdminUser[]>("/api/v1/admin/users"),
    auditLogs: () => request<AdminAuditLog[]>("/api/v1/admin/audit-logs"),
    aiUsage: () => request<AdminAiUsage>("/api/v1/admin/ai-usage"),
    systemHealth: () => request<AdminSystemHealth>("/api/v1/admin/system-health"),
    dataQuality: () => request<DataQualityFinding[]>("/api/v1/admin/data-quality"),
    updateUserRole: (userId: string, role: UserRole) =>
      request<{ id: string; email: string; role: UserRole }>(`/api/v1/admin/users/${userId}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      }),
  },
  paperTrading: {
    portfolio: () => request<PaperPortfolio>("/api/v1/paper/portfolio"),
    orders: () => request<PaperOrder[]>("/api/v1/paper/portfolio/orders"),
    preview: (payload: { symbol: string; side: "buy" | "sell"; quantity: number }) =>
      request<TradePreview>("/api/v1/paper/portfolio/preview", { method: "POST", body: JSON.stringify(payload) }),
    placeOrder: (payload: { symbol: string; side: "buy" | "sell"; quantity: number }) =>
      request<PaperOrder>("/api/v1/paper/portfolio/orders", { method: "POST", body: JSON.stringify(payload) }),
    evaluateOrder: (orderId: string) =>
      request<OrderEvaluation>(`/api/v1/paper/portfolio/orders/${orderId}/evaluation`),
  },
  broker: {
    status: () => request<BrokerStatus>("/api/v1/broker/status"),
    loginUrl: () => request<BrokerLoginUrl>("/api/v1/broker/login-url"),
    connect: (requestToken?: string) =>
      request<BrokerStatus>("/api/v1/broker/connect", {
        method: "POST",
        body: JSON.stringify({ request_token: requestToken ?? null }),
      }),
    disconnect: () => request<void>("/api/v1/broker/disconnect", { method: "DELETE" }),
    sync: () => request<BrokerSyncResult>("/api/v1/broker/sync", { method: "POST" }),
    portfolio: () => request<BrokerPortfolio>("/api/v1/broker/portfolio"),
    placeOrder: (payload: { symbol: string; side: "buy" | "sell"; quantity: number }) =>
      request<BrokerOrderResult>("/api/v1/broker/orders", { method: "POST", body: JSON.stringify(payload) }),
  },
  options: {
    expiries: (symbol: string) =>
      request<ExpiryList>(`/api/v1/options/expiries?symbol=${encodeURIComponent(symbol)}`),
    chain: (symbol: string, expiry: string) =>
      request<OptionChain>(
        `/api/v1/options/chain?symbol=${encodeURIComponent(symbol)}&expiry=${encodeURIComponent(expiry)}`
      ),
  },
  fundamentals: {
    latest: (symbol: string, periodType: "annual" | "quarterly" = "annual") =>
      request<FinancialStatement>(
        `/api/v1/fundamentals/${encodeURIComponent(symbol)}?period_type=${periodType}`
      ),
    history: (symbol: string, periodType: "annual" | "quarterly" = "annual") =>
      request<FinancialStatement[]>(
        `/api/v1/fundamentals/${encodeURIComponent(symbol)}/history?period_type=${periodType}`
      ),
    ratios: (symbol: string, periodType: "annual" | "quarterly" = "annual") =>
      request<FundamentalRatios>(
        `/api/v1/fundamentals/${encodeURIComponent(symbol)}/ratios?period_type=${periodType}`
      ),
  },
  corporateActions: {
    list: (symbol: string) =>
      request<CorporateAction[]>(`/api/v1/corporate-actions/${encodeURIComponent(symbol)}`),
  },
};
