export type AssetSelection = 'AUTO' | 'BTC' | 'ETH';
export type TimeWindow = '24h' | '7d';
export type Direction = 'bullish' | 'bearish' | 'neutral' | string;

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
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

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

export interface MarketData {
  price_now?: number;
  price_change_24h_pct?: number;
  volume_ratio_vs_7d?: number;
  market_signal?: string;
}

export interface RiskData {
  risk_score?: number;
  risk_level?: string;
  risk_breakdown?: Record<string, number>;
  risk_summary?: string;
}

export interface AttributionDriver {
  driver?: string;
  evidence?: string[];
  explanation?: string;
  confidence?: number;
  score?: number;
}

export interface AttributionData {
  event_summary?: string;
  primary_drivers?: AttributionDriver[];
  secondary_drivers?: AttributionDriver[];
  noise?: Array<{ driver?: string; reason?: string }>;
  quality_check?: Record<string, unknown>;
}

export interface DerivativesData {
  funding_rate_now?: number;
  open_interest_change_24h_pct?: number;
  put_call_ratio?: number;
  liquidation_bias?: string;
  derivatives_signal?: string;
}

export interface NewsEvent {
  title?: string;
  direction?: Direction;
  impact_level?: string;
  category?: string;
  confidence?: number;
  url?: string;
}

export interface NewsData {
  events?: NewsEvent[];
}

export interface LargeTransfer {
  hash?: string;
  amount?: number;
  from_label?: string;
  to_label?: string;
  direction?: string;
  timestamp?: string;
}

export interface OnchainData {
  large_transfers?: LargeTransfer[];
  onchain_signal?: string;
  stablecoin_supply_change_24h?: number;
}
