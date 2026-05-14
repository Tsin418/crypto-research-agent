export const FIELD_LABELS: Record<string, string> = {
  price_now: "Price Now",
  price_change_1h_pct: "1h Change",
  price_change_4h_pct: "4h Change",
  price_change_24h_pct: "24h Change",
  price_change_7d_pct: "7d Change",
  volume_24h: "Volume 24h",
  volume_ratio_vs_7d: "Volume vs 7d Avg",
  market_cap: "Market Cap",
  market_signal: "Market Signal",
  spot_turnover_24h: "Spot Turnover 24h",
  spot_flow_bias: "Spot Flow Bias",
  spot_cvd_approx_4h: "Spot CVD (4h)",
  price_vs_ema20: "vs EMA20",
  price_vs_ema50: "vs EMA50",
  price_vs_ema200: "vs EMA200",
  open_interest_change_24h_pct: "Open Interest 24h Change",
  funding_rate_now: "Current Funding Rate",
  funding_rate_8h_ago: "Funding Rate (8h ago)",
  funding_rate_change: "Funding Rate Change",
  open_interest_now: "Open Interest",
  mark_price: "Mark Price",
  basis_pct: "Basis",
  put_call_ratio: "Put / Call Ratio",
  liquidation_bias: "Liquidation Bias",
  long_liquidations_24h: "Long Liquidations 24h",
  macro_signal: "Macro Signal",
  macro_confidence: "Macro Confidence",
  macro_signal_evidence: "Macro Evidence",
  onchain_signal: "On-chain Signal",
  large_transfer_count: "Large Transfers",
  stable_supply_24h: "Stablecoin Supply Change",
  btc_etf_net_flow_usd_m: "BTC ETF Net Flow (USD M)",
  flow_direction: "Flow Direction",
  etf_flow_signal: "ETF Flow Signal",
  flow_intensity: "Flow Intensity",
  is_stale: "Data Stale",
  onchain_evidence_quality: "On-chain Evidence Quality",
  report_id: "Report ID",
  asset: "Asset",
  mode: "Analysis Mode",
  time_window: "Time Window",
  status: "Status",
  updated_at: "Last Updated",
  direction: "Direction",
  trigger_reason: "Trigger Reason",
  provider: "Provider",
  symbol: "Symbol",
  source: "Source",
};

export function labelForField(field: string): string {
  return FIELD_LABELS[field] ?? field.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function shortenHash(value?: string | null, start = 6, end = 4): string {
  if (!value) return "n/a";
  if (value.length <= start + end + 3) return value;
  return `${value.slice(0, start)}...${value.slice(-end)}`;
}

export function displayOrNA(value: unknown): string {
  if (value === null || value === undefined || value === "") return "n/a";
  return String(value);
}
