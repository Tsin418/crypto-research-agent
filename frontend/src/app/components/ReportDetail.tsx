import { useState } from "react";
import { ArrowLeft, Copy, Download, ExternalLink, GitBranch, ChevronDown, ChevronUp } from "lucide-react";
import { labelForField, shortenHash } from "../../utils/labels";
import type {
  ResearchReport,
  DashboardData,
  MarketData,
  RiskData,
  AttributionData,
  AttributionDriver,
  DerivativesData,
  NewsData,
  NewsEvent,
  OnchainData,
  LargeTransfer,
  ETFData,
  MacroData,
  NormalizedSignal,
  ApiCallLog,
  SnapshotEnvelope,
} from "./dashboard/types";

interface ReportDetailProps {
  report: ResearchReport | null;
  defaultAsset?: string;
  errorMessage?: string;
  onBack?: () => void;
  onOpenTrace?: () => void;
}

type DetailTab = "overview" | "evidence" | "dataquality" | "apilogs" | "markdown";

const TABS: { id: DetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "dataquality", label: "Data Quality" },
  { id: "apilogs", label: "API Logs" },
  { id: "markdown", label: "Markdown" },
];

// — Data extraction helpers —

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function unwrapLayer<T>(dashboardData: DashboardData | undefined | null, layer: string): T {
  const snapshot = (dashboardData?.snapshots || {})[layer] as SnapshotEnvelope<T> | undefined;
  const payload = snapshot?.data;
  if (payload && typeof payload === "object" && "data" in payload) {
    return ((payload as { data?: T }).data || {}) as T;
  }
  return (payload as T) || ({} as T);
}

function formatCurrency(value: number | null | undefined, compact = false): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : value >= 1000 ? 0 : 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function formatLabel(value: string | null | undefined): string {
  if (!value) return "n/a";
  return value.replaceAll("_", " ");
}

function riskLabel(value: string | null | undefined): string {
  const label = formatLabel(value);
  return label === "n/a" ? label : label.replace(/\b\w/g, (char) => char.toUpperCase());
}

// — Shared components —

function Pill({ label, color }: { label: string; color?: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded whitespace-nowrap ${color ?? "bg-slate-100 text-slate-600"}`}>
      {label}
    </span>
  );
}

function DirBadge({ d }: { d: string | undefined }) {
  const val = (d || "neutral").toLowerCase();
  const cls =
    val === "bearish" || val === "outflow" ? "bg-red-100 text-red-700" :
    val === "bullish" || val === "inflow" ? "bg-green-100 text-green-700" :
    "bg-slate-100 text-slate-600";
  return <Pill label={val} color={cls} />;
}

function ImpactBadge({ i }: { i: string | undefined }) {
  const val = (i || "low").toLowerCase();
  const cls =
    val === "high" ? "bg-red-100 text-red-700" :
    val === "medium" ? "bg-orange-100 text-orange-700" :
    "bg-slate-100 text-slate-600";
  return <Pill label={val} color={cls} />;
}

function StatusPill({ s }: { s: string }) {
  const val = s.toLowerCase();
  const cls =
    val === "good" || val === "ok" ? "bg-green-100 text-green-700" :
    val === "partial" ? "bg-yellow-100 text-yellow-700" :
    val === "degraded" || val === "unavailable" ? "bg-orange-100 text-orange-700" :
    "bg-red-100 text-red-700";
  return <Pill label={val} color={cls} />;
}

function Card({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h3 className="text-sm" style={{ fontWeight: 600 }}>{title}</h3>
        {action}
      </div>
      {children}
    </div>
  );
}

function CollapsibleCard({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-white rounded-xl border border-slate-100">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <span className="text-sm" style={{ fontWeight: 600 }}>{title}</span>
        {open ? <ChevronUp size={14} className="text-slate-400 shrink-0" /> : <ChevronDown size={14} className="text-slate-400 shrink-0" />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// — Tab content components —

function TabOverview({
  asset,
  report,
  dashboardData,
  onSwitchTab,
  onOpenTrace,
}: {
  asset: string;
  report: ResearchReport;
  dashboardData: DashboardData | null;
  onSwitchTab: (t: DetailTab) => void;
  onOpenTrace?: () => void;
}) {
  const market = unwrapLayer<MarketData>(dashboardData, "market");
  const risk = unwrapLayer<RiskData>(dashboardData, "risk");
  const attribution = unwrapLayer<AttributionData>(dashboardData, "attribution");
  const derivatives = unwrapLayer<DerivativesData>(dashboardData, "derivatives");

  const metadata = report.metadata;
  const price = market.price_now ?? metadata?.price_now ?? null;
  const change4h = market.price_change_4h_pct ?? metadata?.price_change_4h_pct ?? null;
  const change24h = market.price_change_24h_pct ?? metadata?.price_change_24h_pct ?? null;
  const riskScore = risk.risk_score ?? metadata?.risk_score ?? null;
  const riskLevel = risk.risk_level ?? metadata?.risk_level ?? "n/a";
  const marketBias = market.direction || metadata?.direction || "neutral";
  const dataQualityScore = attribution.overall_data_quality_score;

  const primaryDrivers = attribution.primary_drivers || [];
  const mainDriverName = primaryDrivers[0]?.driver || attribution.event_summary || "No confirmed driver";
  const mainDriverExplanation = primaryDrivers[0]?.explanation || attribution.event_summary || "";

  const updatedAt = metadata?.updated_at || report.createdAt;
  const updatedLabel = updatedAt
    ? new Date(updatedAt).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })
    : null;

  const reportId = report.id.slice(0, 8);

  // Build market snapshot rows from real data
  const marketSnapshot: { label: string; value: string }[] = [
    { label: "price_now", value: formatCurrency(price) },
    { label: "price_change_1h_pct", value: formatPercent(market.price_change_1h_pct) },
    { label: "price_change_4h_pct", value: formatPercent(change4h) },
    { label: "price_change_24h_pct", value: formatPercent(change24h) },
    { label: "price_change_7d_pct", value: formatPercent(market.price_change_7d_pct) },
    { label: "volume_24h", value: formatCurrency(market.volume_24h, true) },
    { label: "volume_ratio_vs_7d", value: market.volume_ratio_vs_7d ? `${formatNumber(market.volume_ratio_vs_7d)}x` : "n/a" },
    { label: "market_cap", value: formatCurrency(market.market_cap, true) },
    { label: "market_signal", value: formatLabel(market.market_signal) },
    { label: "spot_turnover_24h", value: formatCurrency(market.spot_turnover_24h, true) },
    { label: "spot_flow_bias", value: formatLabel(market.spot_flow_bias) },
    { label: "spot_cvd_approx_4h", value: market.spot_cvd_approx_4h != null ? formatCurrency(market.spot_cvd_approx_4h, true) : "n/a" },
    { label: "price_vs_ema20", value: formatLabel(market.price_vs_ema20) },
    { label: "price_vs_ema50", value: formatLabel(market.price_vs_ema50) },
    { label: "price_vs_ema200", value: formatLabel(market.price_vs_ema200) },
  ];

  // Build risk breakdown from real data
  const riskBreakdownRaw = risk.risk_breakdown || {};
  const riskMaxScore = risk.risk_max_score || 12;
  const riskBreakdown = Object.keys(riskBreakdownRaw).length > 0
    ? Object.entries(riskBreakdownRaw).map(([key, val]) => ({
        label: formatLabel(key).replace(/\b\w/g, (c) => c.toUpperCase()),
        value: val,
        max: 3,
      }))
    : [
        { label: "Liquidity", value: 0, max: 3 },
        { label: "Leverage", value: 0, max: 3 },
        { label: "News", value: 0, max: 2 },
        { label: "On-chain", value: 0, max: 2 },
        { label: "Macro", value: 0, max: 2 },
      ];

  // Build drivers from attribution
  const allDrivers: Array<AttributionDriver & { type: string }> = [
    ...(attribution.primary_drivers || []).map((d) => ({ ...d, type: "Primary" })),
    ...(attribution.secondary_drivers || []).map((d) => ({ ...d, type: "Secondary" })),
    ...(attribution.noise || []).map((n) => ({ driver: n.driver, explanation: n.reason, confidence: n.confidence, type: "Noise" })),
  ].slice(0, 6);

  const hasData = Boolean(dashboardData);

  return (
    <div className="space-y-4">
      {/* Hero summary */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs bg-orange-100 text-orange-700 px-2.5 py-1 rounded-full" style={{ fontWeight: 600 }}>{asset}</span>
            <span className="text-xs text-slate-500">{metadata?.time_window || "4h"} Window · {reportId}</span>
            {updatedLabel && <span className="text-xs text-slate-400">Updated {updatedLabel}</span>}
          </div>
          <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">
            {hasData ? "Live Data" : "No Dashboard Data"}
          </span>
        </div>

        {/* Price */}
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <span className="text-4xl" style={{ fontWeight: 700 }}>{formatCurrency(price)}</span>
          <div className="pb-0.5">
            <div className={`text-sm ${(change4h || 0) < 0 ? "text-red-500" : "text-green-600"}`} style={{ fontWeight: 500 }}>
              {(change4h || 0) < 0 ? "▼" : "▲"} {formatPercent(change4h)} (4h)
            </div>
            <div className={`text-xs ${(change24h || 0) < 0 ? "text-red-400" : "text-green-500"}`}>
              {(change24h || 0) < 0 ? "▼" : "▲"} {formatPercent(change24h)} (24h)
            </div>
          </div>
        </div>

        {/* Badges */}
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="flex items-center gap-1.5 bg-red-50 border border-red-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Market Bias</span>
            <span className="text-xs text-red-700" style={{ fontWeight: 600 }}>{riskLabel(marketBias)}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-orange-50 border border-orange-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Risk Level</span>
            <span className="text-xs text-orange-700" style={{ fontWeight: 600 }}>{riskLabel(riskLevel)} · {riskScore ?? "n/a"} / {riskMaxScore}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Signals</span>
            <span className="text-xs text-blue-700" style={{ fontWeight: 600 }}>{dashboardData?.normalized_signals?.length || 0}</span>
          </div>
          {dataQualityScore != null && (
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
              <span className="text-xs text-slate-500">Data Quality</span>
              <span className="text-xs text-slate-700" style={{ fontWeight: 600 }}>{formatNumber(dataQualityScore)}</span>
            </div>
          )}
        </div>

        {/* Main driver */}
        <div className="bg-slate-50 rounded-lg p-3 mb-4">
          <div className="text-xs text-slate-400 mb-0.5">Main Driver</div>
          <div className="text-sm text-slate-800" style={{ fontWeight: 600 }}>{mainDriverName}</div>
          {mainDriverExplanation && (
            <p className="text-xs text-slate-500 mt-1 line-clamp-3">{mainDriverExplanation}</p>
          )}
        </div>

        {/* Quick action buttons */}
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => onSwitchTab("evidence")}
            className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 transition-colors"
          >
            View Evidence
          </button>
          <button
            onClick={onOpenTrace}
            className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50"
          >
            <GitBranch size={11} className="inline mr-1" />View Trace
          </button>
          <button
            onClick={() => onSwitchTab("apilogs")}
            className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50"
          >
            API Logs
          </button>
          <button
            onClick={() => onSwitchTab("markdown")}
            className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50"
          >
            Open Markdown
          </button>
        </div>
      </div>

      {/* Market Snapshot */}
      <Card title="Market Snapshot">
        {hasData ? (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
            {marketSnapshot.map((m) => (
              <div key={m.label} className="bg-slate-50 rounded-lg p-3 min-w-0">
                <div className="text-slate-400 truncate">{labelForField(m.label)}</div>
                <div className="text-slate-800 mt-1 truncate" style={{ fontWeight: 600 }}>{m.value}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-400">No market snapshot data loaded.</p>
        )}
      </Card>

      {/* Risk + Attribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Risk Score">
          <div className="flex items-end gap-2 mb-2">
            <span className="text-4xl" style={{ fontWeight: 700 }}>{riskScore ?? "n/a"}</span>
            <span className="text-slate-400 text-sm mb-1">/ {riskMaxScore}</span>
            <Pill label={riskLabel(riskLevel)} color={riskLevel === "high" ? "bg-red-100 text-red-700" : riskLevel === "medium" ? "bg-orange-100 text-orange-700" : "bg-green-100 text-green-700"} />
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
            <div className="h-full bg-orange-400 rounded-full" style={{ width: `${Math.min(100, ((riskScore || 0) / riskMaxScore) * 100)}%` }} />
          </div>
          <div className="space-y-2">
            {riskBreakdown.map((r) => (
              <div key={r.label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-600">{r.label}</span>
                  <span className="text-slate-500">{r.value} / {r.max}</span>
                </div>
                <div className="h-1 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${(r.value / r.max) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
          {risk.risk_summary && (
            <p className="text-xs text-slate-500 mt-3 leading-relaxed line-clamp-3">{risk.risk_summary}</p>
          )}
        </Card>

        <div className="lg:col-span-2">
          <Card
            title="Attribution"
            action={
              <button onClick={onOpenTrace} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                <GitBranch size={11} /> View trace
              </button>
            }
          >
            {attribution.event_summary && (
              <div className="bg-blue-50 rounded-lg p-3 mb-3 text-xs text-blue-800">
                {attribution.event_summary}
              </div>
            )}
            <div className="space-y-3">
              {allDrivers.length > 0 ? allDrivers.map((d) => {
                const typeColor = d.type === "Primary" ? "bg-blue-100 text-blue-700" : d.type === "Secondary" ? "bg-orange-100 text-orange-700" : "bg-slate-100 text-slate-600";
                return (
                  <div key={d.driver} className="border border-slate-100 rounded-lg p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <Pill label={d.type} color={typeColor} />
                        <span className="text-sm text-slate-800 truncate" style={{ fontWeight: 600 }}>{d.driver || "Unnamed"}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                        {d.score != null && <><span>Score {formatNumber(d.score)}</span><span>·</span></>}
                        {d.confidence != null && <><span>Conf {formatNumber(d.confidence)}</span><span>·</span></>}
                        <DirBadge d={d.direction} />
                      </div>
                    </div>
                    {d.explanation && <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{d.explanation}</p>}
                  </div>
                );
              }) : (
                <p className="text-xs text-slate-400">No attribution drivers available.</p>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TabEvidence({
  asset,
  dashboardData,
  signalLayer,
  setSignalLayer,
}: {
  asset: string;
  dashboardData: DashboardData | null;
  signalLayer: string;
  setSignalLayer: (l: string) => void;
}) {
  const derivatives = unwrapLayer<DerivativesData>(dashboardData, "derivatives");
  const news = unwrapLayer<NewsData>(dashboardData, "news");
  const onchain = unwrapLayer<OnchainData>(dashboardData, "onchain");
  const etf = unwrapLayer<ETFData>(dashboardData, "etf_flow");
  const macro = unwrapLayer<MacroData>(dashboardData, "macro");

  const signals: NormalizedSignal[] = dashboardData?.normalized_signals || [];
  const layerNames = ["all", "derivatives", "market", "onchain", "news", "etf_flow", "macro", "risk"];
  const filteredSignals = signalLayer === "all" ? signals : signals.filter((s) => s.layer === signalLayer);

  // Build derivatives display rows
  const derivativesRows: { k: string; v: string }[] = [
    { k: "provider", v: formatLabel(derivatives.provider || derivatives.symbol) },
    { k: "symbol", v: derivatives.symbol || "n/a" },
    { k: "funding_rate_now", v: formatPercent(derivatives.funding_rate_now) },
    { k: "funding_rate_8h_ago", v: formatPercent(derivatives.funding_rate_8h_ago) },
    { k: "funding_rate_change", v: formatPercent(derivatives.funding_rate_change) },
    { k: "open_interest_now", v: formatCurrency(derivatives.open_interest_now, true) },
    { k: "open_interest_change_24h_pct", v: formatPercent(derivatives.open_interest_change_24h_pct) },
    { k: "mark_price", v: formatCurrency(derivatives.mark_price) },
    { k: "basis_pct", v: formatPercent(derivatives.basis_pct) },
    { k: "put_call_ratio", v: formatNumber(derivatives.put_call_ratio) },
    { k: "put_call_volume_ratio", v: formatNumber(derivatives.put_call_volume_ratio) },
    { k: "liquidation_bias", v: formatLabel(derivatives.liquidation_bias) },
    { k: "long_liquidations_24h", v: formatCurrency(derivatives.long_liquidations_24h, true) },
    { k: "short_liquidations_24h", v: formatCurrency(derivatives.short_liquidations_24h, true) },
  ].filter((r) => r.v !== "n/a");

  // News events
  const newsEvents: NewsEvent[] = news.events || [];
  // On-chain transfers
  const transfers: LargeTransfer[] = onchain.large_transfers || [];

  // ETF flow rows
  const etfRows: { k: string; v: string }[] = [
    { k: "btc_etf_net_flow_usd_m", v: etf.btc_etf_net_flow_usd_m != null ? `${etf.btc_etf_net_flow_usd_m}M` : formatNumber(etf.net_flow_usd_m_latest) },
    { k: "flow_direction", v: formatLabel(etf.flow_direction) },
    { k: "etf_flow_signal", v: formatLabel(etf.etf_flow_signal) },
    { k: "flow_intensity", v: formatLabel(etf.flow_intensity) },
    { k: "is_stale", v: etf.is_stale != null ? String(etf.is_stale) : "n/a" },
    { k: "source", v: etf.source || "n/a" },
  ];

  // Macro rows
  const macroRows: { k: string; v: string }[] = [
    { k: "macro_signal", v: formatLabel(macro.macro_signal) },
    { k: "macro_confidence", v: macro.macro_confidence || "n/a" },
    { k: "macro_signal_evidence", v: (macro.macro_signal_evidence || []).join(", ") || "n/a" },
    { k: "source", v: macro.source || "n/a" },
  ];

  // On-chain stats
  const onchainStats = [
    { k: "onchain_signal", v: formatLabel(onchain.onchain_signal) },
    { k: "large_transfer_count", v: String(transfers.length) },
    { k: "stablecoin_supply_change_24h", v: formatCurrency(onchain.stablecoin_supply_change_24h, true) },
  ];

  const hasData = Boolean(dashboardData);

  return (
    <div className="space-y-4">
      {/* Signal Matrix */}
      <Card
        title="Signal Matrix"
        action={
          <div className="flex flex-wrap gap-1">
            {layerNames.map((l) => (
              <button
                key={l}
                onClick={() => setSignalLayer(l)}
                className={`text-xs px-2 py-0.5 rounded ${signalLayer === l ? "bg-blue-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}
              >
                {l}
              </button>
            ))}
          </div>
        }
      >
        {hasData && signals.length > 0 ? (
          <>
            <p className="text-xs text-slate-500 mb-3">
              {asset} signals across all evidence layers.
            </p>
            <div className="overflow-x-auto w-full">
              <table className="w-full text-xs table-fixed min-w-[500px]">
                <thead className="text-slate-400 border-b border-slate-100">
                  <tr>
                    <th className="text-left pb-2 w-[15%]" style={{ fontWeight: 400 }}>Layer</th>
                    <th className="text-left pb-2 w-[28%]" style={{ fontWeight: 400 }}>Signal</th>
                    <th className="text-left pb-2 w-[14%]" style={{ fontWeight: 400 }}>Value</th>
                    <th className="text-left pb-2 w-[13%]" style={{ fontWeight: 400 }}>Direction</th>
                    <th className="text-left pb-2 w-[12%]" style={{ fontWeight: 400 }}>Impact</th>
                    <th className="text-left pb-2 w-[18%]" style={{ fontWeight: 400 }}>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredSignals.map((s, i) => (
                    <tr key={`${s.layer}-${s.signal_name}-${i}`} className="border-b border-slate-50">
                      <td className="py-2 text-slate-500 truncate pr-2">{s.layer}</td>
                      <td className="py-2 text-slate-800 truncate pr-2">{s.signal_name}</td>
                      <td className="py-2 text-slate-700 truncate pr-2" style={{ fontWeight: 500 }}>{s.signal_value || "n/a"}</td>
                      <td className="py-2 pr-2"><DirBadge d={s.direction} /></td>
                      <td className="py-2 pr-2"><ImpactBadge i={s.impact_level} /></td>
                      <td className="py-2 text-slate-500 truncate">{formatNumber(s.confidence)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        ) : (
          <p className="text-xs text-slate-400 py-4">No normalized signals available for this report.</p>
        )}
      </Card>

      {/* Derivatives + News */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Derivatives">
          {derivativesRows.length > 0 ? (
            <>
              <p className="text-xs text-slate-500 mb-3">
                {formatLabel(derivatives.derivatives_signal)} · OI change {formatPercent(derivatives.open_interest_change_24h_pct)} · Liquidation bias: {formatLabel(derivatives.liquidation_bias)}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <tbody>
                    {derivativesRows.map((d) => (
                      <tr key={d.k} className="border-b border-slate-50">
                        <td className="py-1.5 text-slate-400 pr-4 w-1/2">{labelForField(d.k)}</td>
                        <td className="py-1.5 text-slate-700" style={{ fontWeight: 500 }}>{d.v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-400">No derivatives data available.</p>
          )}
        </Card>

        <Card title="News Drivers">
          {newsEvents.length > 0 ? (
            <>
              <p className="text-xs text-slate-500 mb-3">
                {news.news_signal ? formatLabel(news.news_signal) : "News events"} · {newsEvents.length} events classified.
              </p>
              <div className="space-y-3">
                {newsEvents.slice(0, 6).map((n, i) => (
                  <div key={`${n.title}-${i}`} className="border-b border-slate-50 pb-2 last:border-0 min-w-0">
                    <a href={n.url || "#"} className="text-xs text-blue-600 hover:underline flex items-start gap-1">
                      <span className="line-clamp-2">{n.title || "Untitled"}</span>
                      {n.url && <ExternalLink size={10} className="mt-0.5 shrink-0" />}
                    </a>
                    <div className="flex flex-wrap items-center gap-1.5 mt-1 text-xs">
                      <span className="text-slate-400 truncate max-w-[80px]">{n.source || "unknown"}</span>
                      <DirBadge d={n.direction} />
                      <ImpactBadge i={n.impact_level} />
                      <Pill label={n.category || "news"} />
                    </div>
                    {(n.summary || n.reason) && (
                      <p className="text-xs text-slate-500 mt-1 line-clamp-2">{n.summary || n.reason}</p>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className="text-xs text-slate-400">No news events available for this report.</p>
          )}
        </Card>
      </div>

      {/* On-chain + ETF Flow */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title={`On-chain (${asset} context)`}>
          <p className="text-xs text-slate-500 mb-3">
            {transfers.length > 0 ? `${transfers.length} large transfers detected.` : "No large transfers detected."}
          </p>
          <div className="grid grid-cols-3 gap-2 text-xs mb-3">
            {onchainStats.map((item) => (
              <div key={item.k} className="bg-slate-50 rounded-lg p-2">
                <div className="text-slate-400 truncate">{labelForField(item.k)}</div>
                <div className="text-slate-800 mt-0.5 truncate" style={{ fontWeight: 600 }}>{item.v}</div>
              </div>
            ))}
          </div>
          {transfers.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-xs min-w-[320px]">
                <thead className="text-slate-400 border-b border-slate-100">
                  <tr>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Tx Hash</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Amount</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>From → To</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Dir</th>
                    <th className="text-left pb-1.5" style={{ fontWeight: 400 }}>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {transfers.slice(0, 10).map((t, i) => (
                    <tr key={`${t.hash}-${i}`} className="border-b border-slate-50">
                      <td className="py-1.5 pr-2">
                        <span className="text-slate-500 font-mono text-xs" title={t.hash}>{shortenHash(t.hash || "")}</span>
                      </td>
                      <td className="py-1.5 pr-2 text-slate-700 truncate" style={{ fontWeight: 500 }}>
                        {formatNumber(t.amount, 4)} {asset}
                      </td>
                      <td className="py-1.5 pr-2 text-slate-500 text-xs max-w-[100px] truncate" title={`${t.from_label} → ${t.to_label}`}>
                        {t.from_label || "?"} → {t.to_label || "?"}
                      </td>
                      <td className="py-1.5 pr-2"><DirBadge d={t.direction} /></td>
                      <td className="py-1.5 text-slate-400 whitespace-nowrap">{t.timestamp ? new Date(t.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "n/a"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-xs text-slate-400">No on-chain transfers in this snapshot.</p>
          )}
        </Card>

        <div className="space-y-4">
          <Card title="ETF Flow">
            <p className="text-xs text-slate-500 mb-3">
              {etfRows.some((r) => r.v !== "n/a") ? formatLabel(etf.flow_direction || etf.etf_flow_signal) : "No ETF flow data."}
            </p>
            {etfRows.some((r) => r.v !== "n/a") ? (
              <div className="space-y-2 text-xs">
                {etfRows.map((e) => (
                  <div key={e.k} className="flex justify-between border-b border-slate-50 py-1.5 gap-2">
                    <span className="text-slate-400">{labelForField(e.k)}</span>
                    <span className="text-slate-700 truncate text-right" style={{ fontWeight: 500 }}>{e.v}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No ETF flow data available.</p>
            )}
          </Card>

          <Card title="Macro Context">
            <p className="text-xs text-slate-500 mb-3">
              {macro.macro_signal ? `Signal: ${formatLabel(macro.macro_signal)}. Confidence: ${macro.macro_confidence || "n/a"}.` : "No macro data available."}
            </p>
            {macroRows.some((r) => r.v !== "n/a") ? (
              <div className="space-y-2 text-xs">
                {macroRows.map((m) => (
                  <div key={m.k} className="border-b border-slate-50 pb-2 last:border-0">
                    <div className="text-slate-400">{labelForField(m.k)}</div>
                    <div className="text-slate-700 mt-0.5 line-clamp-2" style={{ fontWeight: 500 }}>{m.v}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">No macro data available.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

function TabDataQuality({ dashboardData }: { dashboardData: DashboardData | null }) {
  const attribution = unwrapLayer<AttributionData>(dashboardData, "attribution");
  const market = unwrapLayer<MarketData>(dashboardData, "market");
  const derivatives = unwrapLayer<DerivativesData>(dashboardData, "derivatives");
  const news = unwrapLayer<NewsData>(dashboardData, "news");
  const onchain = unwrapLayer<OnchainData>(dashboardData, "onchain");
  const etf = unwrapLayer<ETFData>(dashboardData, "etf_flow");
  const macro = unwrapLayer<MacroData>(dashboardData, "macro");

  const sections = attribution.data_quality as Record<string, { status?: string; source?: string; missing_fields?: string[] }> | undefined;

  // Fallback: build from individual layer data_quality fields
  const dataQualityLayers = sections
    ? Object.entries(sections).map(([layer, info]) => ({
        layer: layer.charAt(0).toUpperCase() + layer.slice(1).replace(/_/g, " "),
        status: info.status || "unknown",
        source: info.source || "n/a",
        quality: info.status === "good" ? 0.9 : info.status === "partial" ? 0.65 : info.status === "unavailable" ? 0.2 : 0.5,
      }))
    : [
        { layer: "Market", status: market.data_quality ? "good" : "unknown", source: "market", quality: market.data_quality ? 0.9 : 0.3 },
        { layer: "Derivatives", status: derivatives.data_quality ? "good" : "unknown", source: "derivatives", quality: derivatives.data_quality ? 0.85 : 0.3 },
        { layer: "News", status: news.data_quality ? "good" : "unknown", source: "rss", quality: news.data_quality ? 0.7 : 0.3 },
        { layer: "On-chain", status: onchain.data_quality ? "good" : "unknown", source: "onchain", quality: onchain.data_quality ? 0.75 : 0.3 },
        { layer: "ETF Flow", status: etf.source ? "partial" : "unavailable", source: etf.source || "n/a", quality: etf.source ? 0.55 : 0.2 },
        { layer: "Macro", status: macro.macro_signal ? "good" : "unavailable", source: macro.source || "n/a", quality: macro.macro_signal ? 0.75 : 0.2 },
      ];

  const overall = dataQualityLayers.length > 0
    ? (dataQualityLayers.reduce((a, q) => a + q.quality, 0) / dataQualityLayers.length).toFixed(2)
    : "0.00";
  const okCount = dataQualityLayers.filter((q) => q.status === "good" || q.status === "ok").length;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Overall Score</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{overall}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Healthy Layers</div>
          <div className="text-2xl text-green-600" style={{ fontWeight: 700 }}>{okCount} / {dataQualityLayers.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Status</div>
          <div className="text-sm text-yellow-700" style={{ fontWeight: 600 }}>
            {okCount === dataQualityLayers.length ? "All healthy" : okCount > dataQualityLayers.length / 2 ? "Partial" : "Degraded"}
          </div>
        </div>
      </div>

      <Card title="Layer Quality">
        <div className="overflow-x-auto w-full">
          <table className="w-full text-xs min-w-[360px]">
            <thead className="text-slate-400 border-b border-slate-100">
              <tr>
                <th className="text-left pb-2 pr-4" style={{ fontWeight: 400 }}>Layer</th>
                <th className="text-left pb-2 pr-4" style={{ fontWeight: 400 }}>Status</th>
                <th className="text-left pb-2 pr-4" style={{ fontWeight: 400 }}>Source</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Quality</th>
              </tr>
            </thead>
            <tbody>
              {dataQualityLayers.map((q) => (
                <tr key={q.layer} className="border-b border-slate-50">
                  <td className="py-2 pr-4 text-slate-700">{q.layer}</td>
                  <td className="py-2 pr-4"><StatusPill s={q.status} /></td>
                  <td className="py-2 pr-4 text-slate-500">{q.source}</td>
                  <td className="py-2">
                    <div className="flex items-center gap-2">
                      <div className="h-1 w-16 bg-slate-100 rounded-full overflow-hidden">
                        <div className="h-full bg-blue-500 rounded-full" style={{ width: `${q.quality * 100}%` }} />
                      </div>
                      <span className="text-slate-500">{q.quality.toFixed(2)}</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function TabAPILogs({
  dashboardData,
  logFilter,
  setLogFilter,
}: {
  dashboardData: DashboardData | null;
  logFilter: "all" | "errors";
  setLogFilter: (f: "all" | "errors") => void;
}) {
  const apiLogs: ApiCallLog[] = dashboardData?.api_call_logs || [];
  const filteredLogs = logFilter === "errors"
    ? apiLogs.filter((l) => (l.status_code || 200) >= 400)
    : apiLogs;
  const errorCount = apiLogs.filter((l) => (l.status_code || 200) >= 400).length;
  const avgLatency = apiLogs.length > 0
    ? Math.round(apiLogs.reduce((a, l) => a + (l.latency_ms || 0), 0) / apiLogs.length)
    : 0;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Total API Calls</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{apiLogs.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Errors</div>
          <div className={`text-2xl ${errorCount > 0 ? "text-red-600" : "text-green-600"}`} style={{ fontWeight: 700 }}>{errorCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Avg Latency</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{avgLatency} ms</div>
        </div>
      </div>

      <Card
        title="API Call Log"
        action={
          <div className="flex gap-1">
            <button
              onClick={() => setLogFilter("all")}
              className={`text-xs px-2 py-0.5 rounded ${logFilter === "all" ? "bg-blue-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}
            >
              All
            </button>
            <button
              onClick={() => setLogFilter("errors")}
              className={`text-xs px-2 py-0.5 rounded ${logFilter === "errors" ? "bg-red-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}
            >
              Errors only
            </button>
          </div>
        }
      >
        {apiLogs.length > 0 ? (
          <div className="overflow-x-auto w-full">
            <table className="w-full text-xs table-fixed min-w-[500px]">
              <thead className="text-slate-400 border-b border-slate-100">
                <tr>
                  <th className="text-left pb-2 w-[18%]" style={{ fontWeight: 400 }}>Provider</th>
                  <th className="text-left pb-2 w-[28%]" style={{ fontWeight: 400 }}>Endpoint</th>
                  <th className="text-left pb-2 w-[10%]" style={{ fontWeight: 400 }}>Status</th>
                  <th className="text-left pb-2 w-[14%]" style={{ fontWeight: 400 }}>Latency</th>
                  <th className="text-left pb-2 w-[12%]" style={{ fontWeight: 400 }}>Time</th>
                  <th className="text-left pb-2 w-[18%]" style={{ fontWeight: 400 }}>Error</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((l, i) => {
                  const statusCode = l.status_code || 0;
                  return (
                    <tr key={i} className="border-b border-slate-50">
                      <td className="py-2 text-slate-700 truncate pr-2">{l.provider || "unknown"}</td>
                      <td className="py-2 text-slate-500 truncate pr-2" title={l.endpoint}>{l.endpoint || "n/a"}</td>
                      <td className="py-2 pr-2">
                        <Pill
                          label={String(statusCode)}
                          color={statusCode >= 400 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}
                        />
                      </td>
                      <td className="py-2 text-slate-600 truncate pr-2">{l.latency_ms != null ? `${l.latency_ms} ms` : "n/a"}</td>
                      <td className="py-2 text-slate-400 truncate pr-2">
                        {l.created_at ? new Date(l.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "n/a"}
                      </td>
                      <td className="py-2 text-red-500 truncate" title={l.error_message ?? ""}>{l.error_message || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-4">No API call logs recorded for this report.</p>
        )}
      </Card>
    </div>
  );
}

function TabMarkdown({ copied, markdown, onCopy }: { copied: boolean; markdown: string; onCopy: () => void }) {
  return (
    <div className="space-y-4">
      <CollapsibleCard title="Full Markdown Report">
        <div className="flex gap-2 mb-3">
          <button
            onClick={onCopy}
            className="text-xs border border-slate-200 text-slate-700 rounded-md px-2 py-1 hover:bg-slate-50"
          >
            <Copy size={11} className="inline mr-1" />{copied ? "Copied!" : "Copy"}
          </button>
          <button className="text-xs border border-slate-200 text-slate-700 rounded-md px-2 py-1 hover:bg-slate-50">
            <Download size={11} className="inline mr-1" />Download
          </button>
        </div>
        <pre className="text-xs text-slate-700 bg-slate-50 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap max-h-[600px] overflow-y-auto" style={{ fontFamily: "ui-monospace, SFMono-Regular, monospace" }}>
          {markdown || "No markdown report available."}
        </pre>
      </CollapsibleCard>
    </div>
  );
}

// — Main component —

export function ReportDetail({
  report,
  defaultAsset = "BTC",
  errorMessage,
  onBack,
  onOpenTrace,
}: ReportDetailProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [signalLayer, setSignalLayer] = useState<string>("all");
  const [logFilter, setLogFilter] = useState<"all" | "errors">("all");
  const [copied, setCopied] = useState(false);

  const dashboardData = report?.dashboardData || null;
  const metadata = report?.metadata;
  const asset = metadata?.asset || defaultAsset;
  const query = report?.query || `Analyze ${asset} market conditions.`;
  const reportMarkdown = report?.reportMarkdown || "";
  const reportStatus = metadata?.status;
  const riskScore = metadata?.risk_score ?? undefined;
  const riskLevel = metadata?.risk_level ?? undefined;
  const updatedAt = metadata?.updated_at;
  const reportId = report?.id || "n/a";

  const updatedLabel = updatedAt
    ? new Date(updatedAt).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })
    : null;

  function handleCopy() {
    navigator.clipboard?.writeText(reportMarkdown).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      {/* Page header */}
      <div className="p-6 pb-0">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 mb-2"
            >
              <ArrowLeft size={12} /> Back
            </button>
            <h1 className="text-2xl" style={{ fontWeight: 600 }}>Report Detail</h1>
            <p className="text-sm text-slate-500 mt-0.5 line-clamp-2 max-w-xl">{query}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{reportId.slice(0, 8)}</span>
              {reportStatus && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{reportStatus}</span>}
              {riskScore !== undefined && <span className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded">Risk {riskScore}</span>}
              {riskLevel && <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{riskLabel(riskLevel)}</span>}
              {updatedLabel && <span className="text-xs text-slate-400 px-2 py-0.5">Updated {updatedLabel}</span>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={onOpenTrace}
              className="flex items-center gap-1.5 text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-2 hover:bg-slate-50"
            >
              <GitBranch size={12} /> Attribution trace
            </button>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1.5 text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-2 hover:bg-slate-50"
            >
              <Copy size={12} /> {copied ? "Copied" : "Copy markdown"}
            </button>
            <button className="flex items-center gap-1.5 text-xs bg-blue-600 text-white rounded-lg px-3 py-2 hover:bg-blue-700">
              <Download size={12} /> Download
            </button>
          </div>
        </div>
      </div>

      {/* Sticky tab nav */}
      <nav className="sticky top-0 z-10 bg-white border-b border-slate-100 px-6 flex gap-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`text-xs px-4 py-2.5 whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
            style={{ fontWeight: activeTab === tab.id ? 600 : 400 }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Tab content */}
      <div className="p-6 space-y-4">
        {errorMessage && (
          <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-3 text-xs">
            {errorMessage}
          </div>
        )}
        {!dashboardData && reportStatus === "completed" && (
          <div className="bg-yellow-50 border border-yellow-100 text-yellow-700 rounded-xl p-3 text-xs">
            Dashboard data is still loading or unavailable. Try refreshing.
          </div>
        )}
        {activeTab === "overview" && report && (
          <TabOverview
            asset={asset}
            report={report}
            dashboardData={dashboardData}
            onSwitchTab={setActiveTab}
            onOpenTrace={onOpenTrace}
          />
        )}
        {activeTab === "evidence" && (
          <TabEvidence
            asset={asset}
            dashboardData={dashboardData}
            signalLayer={signalLayer}
            setSignalLayer={setSignalLayer}
          />
        )}
        {activeTab === "dataquality" && (
          <TabDataQuality dashboardData={dashboardData} />
        )}
        {activeTab === "apilogs" && (
          <TabAPILogs
            dashboardData={dashboardData}
            logFilter={logFilter}
            setLogFilter={setLogFilter}
          />
        )}
        {activeTab === "markdown" && (
          <TabMarkdown copied={copied} markdown={reportMarkdown} onCopy={handleCopy} />
        )}

        <div className="text-xs text-slate-400 text-center pb-2">
          Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, hold, or use leverage.
        </div>
      </div>
    </div>
  );
}
