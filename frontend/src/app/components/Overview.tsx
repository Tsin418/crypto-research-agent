import { useEffect, useMemo, useState } from "react";
import { Sparkline } from "./Sparkline";
import { TrendingDown, TrendingUp, Minus, Play, FileText } from "lucide-react";
import { requestJson } from "../api";

interface BackendReport {
  report_id: string;
  status: "processing" | "completed" | "failed";
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
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface DashboardData {
  report_id: string;
  snapshots: Record<string, { data?: unknown; source?: string; created_at?: string }>;
  normalized_signals: NormalizedSignal[];
  api_call_logs: unknown[];
}

interface NormalizedSignal {
  layer?: string;
  signal_name?: string;
  signal_value?: string;
  direction?: string;
  impact_level?: string;
  confidence?: number;
}

interface AttributionDriver {
  driver?: string;
  category?: string;
  score?: number;
  confidence?: number;
  explanation?: string;
  evidence?: string[];
}

interface SourceHealth {
  provider: string;
  success_count: number;
  error_count: number;
  avg_latency_ms: number;
  health_status: string;
}

interface NewsEvent {
  title?: string;
  direction?: string;
  impact_level?: string;
  category?: string;
  source?: string;
  url?: string;
}

interface OnchainTransfer {
  hash?: string;
  amount?: number | string;
  direction?: string;
  from_label?: string;
  to_label?: string;
}

interface MarketScanRecord {
  asset: "BTC" | "ETH";
  price_now: number | null;
  price_change_4h_pct: number | null;
  direction: "rising" | "falling" | "neutral";
  direction_label_zh: string;
  created_at: string;
}

interface BackendHealth {
  online: boolean;
  checked: boolean;
  apiUrl: string;
  error?: string;
}

interface OverviewProps {
  queryDraft?: string;
  reports?: BackendReport[];
  onQueryChange?: (q: string) => void;
  onGenerateReport?: () => void;
  onGenerateAssetReport?: (asset: "BTC" | "ETH") => void;
  onRunAutoScan?: () => void;
  onOpenDetail?: (reportId?: string) => void;
  hasReports?: boolean;
  marketScans?: MarketScanRecord[];
  marketLoading?: boolean;
  backendHealth?: BackendHealth;
}

const emptySparkData = [0, 0, 0, 0, 0, 0, 0];

function unwrapLayer<T extends Record<string, unknown>>(dashboardData: DashboardData | null, layer: string): T {
  const snapshot = dashboardData?.snapshots?.[layer];
  const payload = snapshot?.data;

  if (payload && typeof payload === "object" && "data" in payload) {
    return ((payload as { data?: T }).data || {}) as T;
  }

  return ((payload as T) || {}) as T;
}

function formatCurrency(value: number | null | undefined, compact = false) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    notation: compact ? "compact" : "standard",
    maximumFractionDigits: compact ? 1 : value >= 1000 ? 0 : 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value);
}

function formatLabel(value: string | null | undefined) {
  if (!value) return "n/a";
  return value.replaceAll("_", " ");
}

function riskLabel(value: string | null | undefined) {
  const label = formatLabel(value);
  return label === "n/a" ? label : label.replace(/\b\w/g, (char) => char.toUpperCase());
}

function trendFor(change: number | null | undefined) {
  if (change === null || change === undefined || change === 0) return "neutral";
  return change > 0 ? "up" : "down";
}

function sparkFromPrice(price: number | null | undefined, changePct: number | null | undefined) {
  if (!price || changePct === null || changePct === undefined || !Number.isFinite(price) || !Number.isFinite(changePct)) {
    return emptySparkData;
  }
  const start = price / (1 + changePct / 100);
  const mid = (start + price) / 2;
  return [start, start * 0.998, mid, mid * 1.001, price * 0.999, price * 1.0005, price];
}

function StatusDot({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const color =
    normalized === "healthy" ? "bg-green-500" :
    normalized === "degraded" ? "bg-yellow-500" :
    "bg-red-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}

function SignalBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const cls =
    normalized === "bearish" ? "bg-red-100 text-red-700" :
    normalized === "bullish" ? "bg-green-100 text-green-700" :
    "bg-gray-100 text-gray-600";
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${cls}`}>{status || "neutral"}</span>
  );
}

function driverCategory(driver: AttributionDriver) {
  const evidence = (driver.evidence || []).join(" ").toLowerCase();
  const name = (driver.driver || "").toLowerCase();
  if (driver.category) return driver.category;
  if (evidence.includes("derivative") || name.includes("leverage") || name.includes("funding")) return "Derivatives";
  if (evidence.includes("etf") || name.includes("etf")) return "ETF Flow";
  if (evidence.includes("macro") || name.includes("macro")) return "Macro";
  if (evidence.includes("chain") || name.includes("whale") || name.includes("exchange")) return "On-chain";
  return "Market";
}

function categoryClass(category: string) {
  if (category === "Derivatives") return "bg-blue-100 text-blue-700";
  if (category === "ETF Flow") return "bg-orange-100 text-orange-700";
  if (category === "Macro") return "bg-gray-100 text-gray-600";
  if (category === "On-chain") return "bg-emerald-100 text-emerald-700";
  return "bg-purple-100 text-purple-700";
}

function EmptyReportState({ onGenerateAssetReport, onRunAutoScan }: Pick<OverviewProps, "onGenerateAssetReport" | "onRunAutoScan">) {
  return (
    <div className="bg-white rounded-xl border border-slate-100 p-5">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="text-base text-slate-900" style={{ fontWeight: 600 }}>No completed reports yet.</div>
          <p className="text-sm text-slate-500 mt-1">
            Run Auto Scan or generate a BTC / ETH report to populate attribution, risk, news, and trace data.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <button
            onClick={() => onGenerateAssetReport?.("BTC")}
            className="inline-flex items-center gap-1.5 text-xs bg-orange-600 text-white rounded-lg px-3 py-2 hover:bg-orange-700 transition-colors"
            style={{ fontWeight: 500 }}
          >
            <FileText size={13} /> Generate BTC Report
          </button>
          <button
            onClick={() => onGenerateAssetReport?.("ETH")}
            className="inline-flex items-center gap-1.5 text-xs bg-blue-600 text-white rounded-lg px-3 py-2 hover:bg-blue-700 transition-colors"
            style={{ fontWeight: 500 }}
          >
            <FileText size={13} /> Generate ETH Report
          </button>
          <button
            onClick={() => onRunAutoScan?.()}
            className="inline-flex items-center gap-1.5 text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-2 hover:bg-slate-50 transition-colors"
            style={{ fontWeight: 500 }}
          >
            <Play size={13} /> Run Auto Scan
          </button>
        </div>
      </div>
    </div>
  );
}

export function Overview({
  queryDraft = "",
  reports = [],
  onQueryChange,
  onGenerateReport,
  onGenerateAssetReport,
  onRunAutoScan,
  onOpenDetail,
  hasReports,
  marketScans = [],
  marketLoading,
  backendHealth,
}: OverviewProps) {
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(null);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const completedReports = useMemo(
    () => reports.filter((report) => report.status === "completed"),
    [reports]
  );
  const btcReport = completedReports.find((report) => report.asset === "BTC") || null;
  const ethReport = completedReports.find((report) => report.asset === "ETH") || null;
  const selectedReport = btcReport || completedReports[0] || null;

  useEffect(() => {
    let cancelled = false;
    if (!selectedReport?.report_id) {
      setDashboardData(null);
      return;
    }

    requestJson<DashboardData>(
      `/api/research/report/${selectedReport.report_id}/data`,
      "Failed to load overview dashboard data"
    )
      .then((payload) => {
        if (!cancelled) {
          setDashboardData(payload);
          setLoadError(null);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          setDashboardData(null);
          setLoadError(error instanceof Error ? error.message : String(error));
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedReport?.report_id]);

  useEffect(() => {
    let cancelled = false;
    requestJson<{ sources: SourceHealth[] }>("/api/research/source-health?lookback_hours=24", "Failed to load source health")
      .then((payload) => {
        if (!cancelled) {
          setSources(payload.sources || []);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSources([]);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const attribution = unwrapLayer<{
    event_summary?: string;
    primary_drivers?: AttributionDriver[];
    secondary_drivers?: AttributionDriver[];
  }>(dashboardData, "attribution");
  const risk = unwrapLayer<{
    risk_score?: number;
    risk_level?: string;
    risk_summary?: string;
    risk_max_score?: number;
  }>(dashboardData, "risk");
  const news = unwrapLayer<{ events?: NewsEvent[]; top_news?: NewsEvent }>(dashboardData, "news");
  const onchain = unwrapLayer<{
    large_transfers?: OnchainTransfer[];
    stablecoin_supply_change_24h?: number;
    stablecoin_supply_usd?: number;
  }>(dashboardData, "onchain");

  const sourceStats = useMemo(() => {
    const healthy = sources.filter((source) => source.health_status === "healthy").length;
    return {
      healthy,
      total: sources.length,
      degraded: sources.filter((source) => source.health_status !== "healthy").length,
    };
  }, [sources]);

  const btcMarketScan = marketScans.find((scan) => scan.asset === "BTC");
  const ethMarketScan = marketScans.find((scan) => scan.asset === "ETH");

  const priceCards = [
    {
      label: "BTC",
      report: btcReport,
      fallbackPrice: btcMarketScan?.price_now,
      fallbackChange: btcMarketScan?.price_change_4h_pct,
      sub: "4h change",
    },
    {
      label: "ETH",
      report: ethReport,
      fallbackPrice: ethMarketScan?.price_now,
      fallbackChange: ethMarketScan?.price_change_4h_pct,
      sub: "4h change",
    },
  ].map((item) => {
    const change = item.report?.price_change_4h_pct ?? item.fallbackChange ?? null;
    const price = item.report?.price_now ?? item.fallbackPrice ?? null;
    const trend = trendFor(change);
    return {
      label: item.label,
      value: formatCurrency(price),
      change: formatPercent(change),
      trend,
      sub: item.sub,
      data: sparkFromPrice(price, change),
      color: trend === "up" ? "#10B981" : trend === "down" ? "#EF4444" : "#64748B",
      empty: price === null,
    };
  });

  const stablecoinChange = onchain.stablecoin_supply_change_24h;
  const stablecoinTrend = trendFor(stablecoinChange);
  const summaryCards = [
    ...priceCards,
    {
      label: "Stablecoin 24h Change",
      value: stablecoinChange === undefined ? "n/a" : formatCurrency(stablecoinChange, true),
      change: sourceStats.total ? `${sourceStats.healthy}/${sourceStats.total}` : "n/a",
      trend: stablecoinTrend,
      sub: "healthy sources",
      data: emptySparkData,
      color: stablecoinTrend === "up" ? "#10B981" : stablecoinTrend === "down" ? "#EF4444" : "#64748B",
      empty: stablecoinChange === undefined,
    },
  ];

  const drivers = [...(attribution.primary_drivers || []), ...(attribution.secondary_drivers || [])].slice(0, 4);
  const driverRows = drivers.map((driver, index) => {
    const category = driverCategory(driver);
    const score = driver.score ?? driver.confidence ?? 0;
    const pct = Math.max(12, Math.min(100, score <= 1 ? score * 100 : (score / 4) * 100));
    return {
      name: driver.driver || `Driver ${index + 1}`,
      category,
      color: categoryClass(category),
      value: score,
      pct,
    };
  });

  const signalRows = (dashboardData?.normalized_signals || []).slice(0, 6);
  const newsItems = [
    ...(selectedReport?.top_news_json?.title ? [{
      title: selectedReport.top_news_json.title,
      source: selectedReport.top_news_json.source,
      category: "top news",
      direction: "neutral",
    }] : []),
    ...(news.events || []),
  ].filter((item) => item.title).slice(0, 3);
  const onchainItems = (onchain.large_transfers || []).slice(0, 3);

  const riskScore = risk.risk_score ?? selectedReport?.risk_score ?? null;
  const riskMaxScore = risk.risk_max_score ?? 15;
  const riskPct = riskScore === null ? 0 : Math.max(0, Math.min(100, (riskScore / riskMaxScore) * 100));
  const riskLevel = risk.risk_level || selectedReport?.risk_level || "n/a";
  const marketBias = selectedReport?.direction || selectedReport?.direction_label_zh || "n/a";
  const mainDriver = drivers[0]?.driver || selectedReport?.trigger_reason || "No confirmed driver yet";
  const summaryText =
    attribution.event_summary ||
    risk.risk_summary ||
    selectedReport?.trigger_reason ||
    "Run a report or auto scan to load backend attribution data.";

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Overview</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Live market attribution summary and research command center.
        </p>
      </div>

      {loadError && (
        <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-3 text-xs">
          {loadError}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {summaryCards.map((item) => (
          <div key={item.label} className="bg-white rounded-xl border border-slate-100 p-4 flex items-center justify-between min-w-0">
            <div className="min-w-0 flex-1">
              <div className="text-xs text-slate-500 mb-1 truncate">{item.label}</div>
              <div className="text-xl" style={{ fontWeight: 600 }}>{item.value}</div>
              <div className={`flex items-center gap-1 mt-1 text-xs ${
                item.trend === "up" ? "text-green-600" : item.trend === "down" ? "text-red-500" : "text-slate-500"
              }`}>
                {item.trend === "up" ? <TrendingUp size={12} /> : item.trend === "down" ? <TrendingDown size={12} /> : <Minus size={12} />}
                <span>{item.empty ? "No backend data" : `${item.change} ${item.sub}`}</span>
              </div>
            </div>
            <Sparkline data={item.data} color={item.color} width={90} height={36} />
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <div className="text-sm text-slate-500 mb-2">Research Question</div>
        <div className="flex gap-2">
          <textarea
            className="flex-1 text-sm border border-slate-200 rounded-lg px-3 py-2 resize-none bg-slate-50 outline-none focus:border-blue-400 min-w-0"
            rows={2}
            placeholder="Ask a crypto research question (e.g., Why did BTC drop in the past 4h?)"
            value={queryDraft}
            onChange={(e) => onQueryChange?.(e.target.value)}
          />
          <button
            onClick={() => onGenerateReport?.()}
            className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg self-start hover:bg-blue-700 transition-colors shrink-0"
            style={{ fontWeight: 500 }}
          >
            Generate
          </button>
        </div>
      </div>

      {completedReports.length === 0 ? (
        <EmptyReportState onGenerateAssetReport={onGenerateAssetReport} onRunAutoScan={onRunAutoScan} />
      ) : (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h3 className="text-base" style={{ fontWeight: 600 }}>
                {selectedReport?.asset || "Market"} Attribution
              </h3>
              <div className="flex flex-wrap gap-1.5">
                <span className="text-xs bg-red-50 border border-red-100 text-red-700 px-2 py-0.5 rounded-full">
                  Market Bias: {riskLabel(marketBias)}
                </span>
                <span className="text-xs bg-orange-50 border border-orange-100 text-orange-700 px-2 py-0.5 rounded-full">
                  Risk: {riskLabel(riskLevel)}
                </span>
                <span className="text-xs bg-blue-50 border border-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                  Signals: {dashboardData?.normalized_signals?.length || 0}
                </span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-slate-700 truncate" style={{ fontWeight: 600 }}>{mainDriver}</div>
              <p className="text-xs text-slate-500 line-clamp-3">{summaryText}</p>
              {driverRows.length === 0 && (
                <div className="text-xs text-slate-400 bg-slate-50 rounded-lg p-3">
                  No attribution drivers loaded yet. Generate a report or run Auto Scan to populate this panel.
                </div>
              )}
              {driverRows.map((driver) => (
                <div key={driver.name} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <span className="text-xs text-slate-700 truncate">{driver.name}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${driver.color}`}>{driver.category}</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${driver.pct}%` }} />
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 w-8 text-right shrink-0">{formatNumber(driver.value)}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-base mb-3" style={{ fontWeight: 600 }}>Signal Matrix</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {signalRows.map((signal, index) => (
                <div key={`${signal.layer}-${signal.signal_name}-${index}`} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-50 gap-3">
                  <span className="text-slate-600 truncate">{signal.signal_name || signal.layer || "signal"}</span>
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="truncate" style={{ fontWeight: 500 }}>{signal.signal_value || "n/a"}</span>
                    <SignalBadge status={signal.direction || "neutral"} />
                  </div>
                </div>
              ))}
              {signalRows.length === 0 && <div className="text-xs text-slate-400">No normalized signals loaded.</div>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm mb-2" style={{ fontWeight: 600 }}>{selectedReport?.asset || "Market"} News Drivers</h4>
              <div className="space-y-2">
                {newsItems.map((item, index) => (
                  <div key={`${item.title}-${index}`} className="flex items-start gap-2 text-xs">
                    <Minus size={10} className="text-slate-400 mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-slate-700 line-clamp-2">{item.title}</div>
                      <span className="text-xs px-1 py-0.5 rounded mt-0.5 inline-block bg-slate-100 text-slate-600">
                        {item.category || item.source || "news"}
                      </span>
                    </div>
                  </div>
                ))}
                {newsItems.length === 0 && <div className="text-xs text-slate-400">No news drivers loaded.</div>}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm mb-2" style={{ fontWeight: 600 }}>{selectedReport?.asset || "Asset"} On-chain Context</h4>
              <p className="text-xs text-slate-400 mb-2">Latest backend on-chain snapshot</p>
              <div className="space-y-2">
                {onchainItems.map((item, index) => (
                  <div key={`${item.hash}-${index}`} className="flex items-start gap-2 text-xs">
                    <div className="w-2 h-2 rounded-full mt-1 shrink-0 bg-slate-400" />
                    <span className="text-slate-600 line-clamp-2">
                      {formatNumber(Number(item.amount), 4)} {selectedReport?.asset || ""} · {formatLabel(item.direction)} · {item.from_label || "unknown"} → {item.to_label || "unknown"}
                    </span>
                  </div>
                ))}
                {onchainItems.length === 0 && <div className="text-xs text-slate-400">No on-chain events in the latest snapshot.</div>}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base" style={{ fontWeight: 600 }}>AI Brief</h3>
            </div>
            <div className="flex items-end gap-2 mb-1">
              <span className="text-4xl" style={{ fontWeight: 700 }}>{riskScore ?? "n/a"}</span>
              <span className="text-slate-400 text-sm mb-1">/ {riskMaxScore}</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-3">
              <div className="h-full bg-orange-400 rounded-full" style={{ width: `${riskPct}%` }} />
            </div>
            <div className="flex flex-wrap gap-1.5 mb-3">
              <span className="text-xs bg-red-50 border border-red-100 text-red-700 px-2 py-0.5 rounded-full">{riskLabel(marketBias)}</span>
              <span className="text-xs bg-orange-50 border border-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Risk: {riskLabel(riskLevel)}</span>
              <span className="text-xs bg-blue-50 border border-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Signals: {signalRows.length}</span>
            </div>
            <div className="text-sm text-slate-700 truncate" style={{ fontWeight: 500 }}>{mainDriver}</div>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed line-clamp-3">{summaryText}</p>
            <button
              onClick={() => onOpenDetail?.(selectedReport?.report_id)}
              disabled={!selectedReport}
              className="mt-3 w-full text-xs border border-blue-200 text-blue-600 rounded-lg py-1.5 hover:bg-blue-50 transition-colors disabled:opacity-50"
            >
              View full report
            </button>
          </div>

          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-base mb-3 truncate" style={{ fontWeight: 600 }}>Source Health</h3>
            <div className="space-y-2">
              {sources.slice(0, 6).map((source) => (
                <div key={source.provider} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <StatusDot status={source.health_status} />
                    <span className="text-slate-700 truncate">{source.provider}</span>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-xs whitespace-nowrap shrink-0 ml-2 ${
                    source.health_status === "healthy" ? "text-green-600" :
                    source.health_status === "degraded" ? "text-yellow-600" :
                    "text-red-600"
                  }`}>{riskLabel(source.health_status)}</span>
                </div>
              ))}
              {sources.length === 0 && <div className="text-xs text-slate-400">No source health records loaded.</div>}
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-sm mb-3 truncate" style={{ fontWeight: 600 }}>Top News</h3>
            <div className="space-y-2">
              {newsItems.map((item, index) => (
                <div key={`${item.title}-${index}`} className="text-xs text-slate-600 flex items-start gap-2">
                  <span className="text-slate-400 shrink-0">-</span>
                  <span className="line-clamp-2">{item.title}</span>
                </div>
              ))}
              {newsItems.length === 0 && <div className="text-xs text-slate-400">No top news loaded.</div>}
            </div>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}
