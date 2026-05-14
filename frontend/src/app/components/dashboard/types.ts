export type AssetSelection = 'AUTO' | 'BTC' | 'ETH';
export type TimeWindow = '4h' | '24h' | '7d';
export type Direction = 'bullish' | 'bearish' | 'neutral' | string;

// --- Backend report record (matches StoredReport Pydantic model) ---
export interface ReportRecord {
  report_id: string;
  status: 'processing' | 'completed' | 'failed';
  user_query: string;
  asset: string | null;
  mode: string | null;
  time_window: string | null;
  report_markdown: string | null;
  risk_score: number | null;
  risk_level: string | null;
  price_now?: number | null;
  price_change_4h_pct?: number | null;
  price_change_24h_pct?: number | null;
  direction?: string | null;
  direction_label_zh?: string | null;
  trigger_reason?: string | null;
  top_news_title?: string | null;
  top_news_url?: string | null;
  top_news_source?: string | null;
  top_news_json?: {
    title?: string;
    url?: string;
    source?: string;
    reason_zh?: string;
    published_at?: string;
    impact_level?: string;
    direction?: string;
    related_assets?: string[];
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// --- Dashboard data (from /api/research/report/{id}/data) ---
export interface SnapshotEnvelope<T = Record<string, unknown>> {
  source?: string;
  created_at?: string;
  data?: T | { data?: T; errors?: string[] };
}

export interface NormalizedSignal {
  layer: string;
  signal_name: string;
  signal_value: string;
  direction: Direction;
  severity?: string | null;
  impact_level: string;
  confidence: number;
  created_at?: string;
}

export interface ApiCallLog {
  provider?: string;
  endpoint?: string;
  status_code?: number | null;
  latency_ms?: number | null;
  error_message?: string | null;
  created_at?: string;
}

export interface DashboardData {
  report_id: string;
  snapshots: Record<string, SnapshotEnvelope<Record<string, unknown>>>;
  normalized_signals: NormalizedSignal[];
  api_call_logs: ApiCallLog[];
}

export interface ResearchReport {
  id: string;
  query: string;
  createdAt: string;
  metadata?: ReportRecord;
  dashboardData?: DashboardData;
  reportMarkdown: string;
  error?: string;
}

// --- Layer data shapes (extracted from snapshots) ---
export interface MarketData {
  price_now?: number;
  price_change_1h_pct?: number;
  price_change_4h_pct?: number;
  price_change_24h_pct?: number;
  price_change_7d_pct?: number;
  volume_24h?: number;
  volume_7d_avg?: number;
  volume_ratio_vs_7d?: number;
  market_cap?: number;
  market_signal?: string;
  spot_turnover_24h?: number;
  spot_flow_bias?: string;
  spot_cvd_approx_4h?: number;
  spot_cvd_approx_1h?: number;
  price_vs_ema20?: string;
  price_vs_ema50?: string;
  price_vs_ema200?: string;
  ema_20?: number;
  ema_50?: number;
  ema_200?: number;
  direction?: string;
  direction_label_zh?: string;
  trigger_reason?: string;
  data_quality?: Record<string, unknown>;
}

export interface RiskData {
  risk_score?: number;
  risk_max_score?: number;
  risk_level?: string;
  risk_breakdown?: Record<string, number>;
  risk_summary?: string;
  risk_confidence?: number;
  data_coverage?: Record<string, string>;
  missing_data?: string[];
}

export interface AttributionDriver {
  driver?: string;
  evidence?: string[];
  explanation?: string;
  confidence?: number;
  score?: number;
  direction?: string;
  supporting_evidence?: string[];
  counter_evidence?: string[];
  missing_evidence?: string[];
  causality_level?: string;
  primary_eligible?: boolean;
  confidence_breakdown?: Record<string, number>;
  source_layer?: string;
  derivatives_regime?: string;
  causal_timing?: string;
  category_prior?: number;
  source_weight?: number;
}

export interface AttributionData {
  event_summary?: string;
  primary_drivers?: AttributionDriver[];
  secondary_drivers?: AttributionDriver[];
  noise?: Array<{ driver?: string; reason?: string; confidence?: number }>;
  quality_check?: Record<string, unknown>;
  alternative_explanations?: Array<{
    explanation?: string;
    supporting_evidence?: string[];
    why_not_primary?: string;
  }>;
  data_quality?: Record<string, unknown>;
  overall_data_quality_score?: number;
  attribution_trace?: Array<Record<string, unknown>>;
  trace_summary?: Record<string, unknown>;
}

export interface DerivativesData {
  funding_rate_now?: number;
  funding_rate_8h_ago?: number;
  funding_rate_change?: number;
  open_interest_now?: number;
  open_interest_change_24h_pct?: number;
  put_call_ratio?: number;
  put_call_volume_ratio?: number;
  liquidation_bias?: string;
  long_liquidations_24h?: number;
  short_liquidations_24h?: number;
  long_liquidation_events_24h?: number;
  short_liquidation_events_24h?: number;
  derivatives_signal?: string;
  basis_pct?: number;
  mark_price?: number;
  index_price?: number;
  symbol?: string;
  provider?: string;
  source_note?: string;
  data_quality?: Record<string, unknown>;
}

export interface NewsEvent {
  title?: string;
  direction?: Direction;
  impact_level?: string;
  category?: string;
  source?: string;
  url?: string;
  confidence?: number;
  published_at?: string;
  summary?: string;
  asset_related?: string[];
  reason?: string;
}

export interface NewsData {
  events?: NewsEvent[];
  top_news?: NewsEvent;
  news_signal?: string;
  etf_flow?: Record<string, unknown>;
  data_quality?: Record<string, unknown>;
}

export interface LargeTransfer {
  hash?: string;
  amount?: number;
  from_label?: string;
  to_label?: string;
  direction?: string;
  timestamp?: string;
  source?: string;
  block_height?: number;
}

export interface OnchainData {
  large_transfers?: LargeTransfer[];
  onchain_signal?: string;
  stablecoin_supply_change_24h?: number;
  stablecoin_supply_change_7d?: number;
  stablecoin_supply_usd?: number;
  exchange_netflow_24h?: number | null;
  onchain_evidence_quality?: string;
  exchange_inflow_count?: number;
  large_transfer_count?: number;
  data_quality?: Record<string, unknown>;
}

export interface ETFData {
  btc_etf_net_flow_usd_m?: number;
  net_flow_usd_m_latest?: number;
  flow_direction?: string;
  flow_intensity?: string;
  etf_flow_signal?: string;
  is_stale?: boolean;
  source?: string;
}

export interface MacroData {
  macro_signal?: string;
  macro_confidence?: string;
  macro_signal_evidence?: string[];
  source?: string;
}

// --- Market scan ---
export interface MarketScanRecord {
  asset: 'BTC' | 'ETH';
  price_now: number | null;
  price_change_4h_pct: number | null;
  direction: 'rising' | 'falling' | 'neutral';
  direction_label_zh: string;
  created_at: string;
}

// --- Source health ---
export interface SourceHealth {
  provider: string;
  success_count: number;
  error_count: number;
  avg_latency_ms: number;
  health_status: string;
  last_success_at?: string;
  last_error_at?: string;
}

// --- Backend health ---
export interface BackendHealth {
  online: boolean;
  checked: boolean;
  apiUrl: string;
  error?: string;
}
