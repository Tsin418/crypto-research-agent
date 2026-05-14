import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Copy, Download, ExternalLink, GitBranch, ChevronDown, ChevronUp } from "lucide-react";
import { labelForField, shortenHash } from "../../utils/labels";
import { requestJson } from "../api";

interface ReportDetailProps {
  reportId?: string;
  asset?: string;
  query?: string;
  reportMarkdown?: string;
  reportStatus?: string;
  riskScore?: number;
  riskLevel?: string | null;
  updatedAt?: string;
  errorMessage?: string;
  dashboardData?: DashboardData;
  onBack?: () => void;
  onOpenTrace?: () => void;
}

interface DashboardData {
  report_id: string;
  snapshots: Record<string, SnapshotEnvelope>;
  normalized_signals: NormalizedSignal[];
  api_call_logs: ApiCallLog[];
}

interface SnapshotEnvelope {
  source?: string;
  created_at?: string;
  data?: Record<string, unknown> | { data?: Record<string, unknown>; errors?: string[] };
}

interface NormalizedSignal {
  layer?: string;
  signal_name?: string;
  signal_value?: string;
  direction?: string;
  impact_level?: string;
  confidence?: number;
}

interface ApiCallLog {
  provider?: string;
  endpoint?: string;
  status_code?: number | null;
  latency_ms?: number | null;
  error_message?: string | null;
  created_at?: string;
}

type DetailTab = "overview" | "evidence" | "dataquality" | "apilogs" | "markdown";

const TABS: { id: DetailTab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "dataquality", label: "Data Quality" },
  { id: "apilogs", label: "API Logs" },
  { id: "markdown", label: "Markdown" },
];

function getSnapshotData(snapshot?: SnapshotEnvelope): Record<string, unknown> {
  const data = snapshot?.data;
  if (!data) return {};
  if ("data" in data && data.data && typeof data.data === "object") return data.data as Record<string, unknown>;
  return data as Record<string, unknown>;
}

function formatCurrency(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined, maxDigits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(maxDigits)}%`;
}

function formatNum(value: number | null | undefined, maxDigits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: maxDigits }).format(value);
}

function formatLabel(value: string | null | undefined): string {
  if (!value) return "n/a";
  return value.replaceAll("_", " ");
}

// — Shared components —

function Pill({ label, color }: { label: string; color?: string }) {
  return (
    <span className={`text-xs px-2 py-0.5 rounded whitespace-nowrap ${color ?? "bg-slate-100 text-slate-600"}`}>
      {label}
    </span>
  );
}

function DirBadge({ d }: { d: string }) {
  const cls =
    d === "bearish" ? "bg-red-100 text-red-700" :
    d === "bullish" ? "bg-green-100 text-green-700" :
    d === "outflow" ? "bg-green-100 text-green-700" :
    d === "inflow" ? "bg-red-100 text-red-700" :
    "bg-slate-100 text-slate-600";
  return <Pill label={d} color={cls} />;
}

function ImpactBadge({ i }: { i: string }) {
  const cls =
    i === "high" ? "bg-red-100 text-red-700" :
    i === "medium" ? "bg-orange-100 text-orange-700" :
    "bg-slate-100 text-slate-600";
  return <Pill label={i} color={cls} />;
}

function StatusPill({ s }: { s: string }) {
  const cls =
    s === "ok" || s === "good" ? "bg-green-100 text-green-700" :
    s === "partial" ? "bg-yellow-100 text-yellow-700" :
    s === "degraded" ? "bg-orange-100 text-orange-700" :
    "bg-red-100 text-red-700";
  return <Pill label={s} color={cls} />;
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
  reportId,
  marketData,
  riskData,
  attributionData,
  onSwitchTab,
  onOpenTrace,
}: {
  asset: string;
  reportId?: string;
  marketData: Record<string, unknown>;
  riskData: Record<string, unknown>;
  attributionData: Record<string, unknown>;
  onSwitchTab: (t: DetailTab) => void;
  onOpenTrace?: () => void;
}) {
  const priceNow = marketData.price_now as number | null;
  const change4h = marketData.price_change_4h_pct as number | null;
  const change24h = marketData.price_change_24h_pct as number | null;
  const marketSignal = (marketData.market_signal as string) || "n/a";
  const riskScore = riskData.risk_score as number | null;
  const riskMax = (riskData.risk_max_score as number) || 12;
  const riskLevel = (riskData.risk_level as string) || "n/a";
  const riskBreakdown = (riskData.risk_breakdown as Record<string, number>) || {};
  const riskSummary = (riskData.risk_summary as string) || "";
  const primaryDrivers = (attributionData.primary_drivers as Array<Record<string, unknown>>) || [];
  const secondaryDrivers = (attributionData.secondary_drivers as Array<Record<string, unknown>>) || [];
  const eventSummary = (attributionData.event_summary as string) || "";
  const topPrimary = primaryDrivers[0];

  const marketEntries = Object.entries(marketData)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => ({ label: k, value: typeof v === "number" ? formatNum(v) : String(v) }));

  const breakdownEntries = Object.entries(riskBreakdown).map(([k, v]) => ({
    label: formatLabel(k),
    value: v,
    max: 3,
  }));

  const allDrivers = [
    ...primaryDrivers.map((d) => ({ ...d, type: "Primary", color: "bg-blue-100 text-blue-700" })),
    ...secondaryDrivers.map((d) => ({ ...d, type: "Secondary", color: "bg-orange-100 text-orange-700" })),
  ];

  const trend4h = change4h !== null && change4h !== undefined ? (change4h < 0 ? "down" : "up") : "flat";

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs bg-orange-100 text-orange-700 px-2.5 py-1 rounded-full" style={{ fontWeight: 600 }}>{asset}</span>
            <span className="text-xs text-slate-500">{reportId ? `Report ${reportId.slice(0, 8)}` : "Latest report"}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4 mb-4">
          <span className="text-4xl" style={{ fontWeight: 700 }}>{formatCurrency(priceNow)}</span>
          <div className="pb-0.5">
            <div className={`text-sm ${trend4h === "down" ? "text-red-500" : "text-green-600"}`} style={{ fontWeight: 500 }}>
              {trend4h === "down" ? "▼" : "▲"} {formatPercent(change4h)} (4h)
            </div>
            <div className={`text-xs ${(change24h || 0) < 0 ? "text-red-400" : "text-green-500"}`}>
              {formatPercent(change24h)} (24h)
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mb-4">
          <div className="flex items-center gap-1.5 bg-red-50 border border-red-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Market Bias</span>
            <span className="text-xs text-red-700" style={{ fontWeight: 600 }}>{formatLabel(marketSignal)}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-orange-50 border border-orange-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Risk Level</span>
            <span className="text-xs text-orange-700" style={{ fontWeight: 600 }}>{formatLabel(riskLevel)} · {riskScore ?? "n/a"} / {riskMax}</span>
          </div>
        </div>

        {eventSummary ? (
          <div className="bg-slate-50 rounded-lg p-3 mb-4">
            <div className="text-xs text-slate-400 mb-0.5">Summary</div>
            <p className="text-sm text-slate-700">{eventSummary}</p>
          </div>
        ) : null}

        <div className="flex flex-wrap gap-2">
          <button onClick={() => onSwitchTab("evidence")} className="text-xs bg-blue-600 text-white rounded-lg px-3 py-1.5 hover:bg-blue-700 transition-colors">View Evidence</button>
          <button onClick={onOpenTrace} className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50"><GitBranch size={11} className="inline mr-1" />View Trace</button>
          <button onClick={() => onSwitchTab("apilogs")} className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50">API Logs</button>
          <button onClick={() => onSwitchTab("markdown")} className="text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-1.5 hover:bg-slate-50">Open Markdown</button>
        </div>
      </div>

      {marketEntries.length > 0 && (
        <Card title="Market Snapshot">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
            {marketEntries.map((m) => (
              <div key={m.label} className="bg-slate-50 rounded-lg p-3 min-w-0">
                <div className="text-slate-400 truncate">{labelForField(m.label)}</div>
                <div className="text-slate-800 mt-1 truncate" style={{ fontWeight: 600 }}>{m.value}</div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Risk Score">
          <div className="flex items-end gap-2 mb-2">
            <span className="text-4xl" style={{ fontWeight: 700 }}>{riskScore ?? "n/a"}</span>
            <span className="text-slate-400 text-sm mb-1">/ {riskMax}</span>
            <Pill label={formatLabel(riskLevel)} color="bg-orange-100 text-orange-700" />
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
            <div className="h-full bg-orange-400 rounded-full" style={{ width: `${Math.min(100, ((riskScore || 0) / riskMax) * 100)}%` }} />
          </div>
          {breakdownEntries.length > 0 && (
            <div className="space-y-2">
              {breakdownEntries.map((r) => (
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
          )}
          {riskSummary && <p className="text-xs text-slate-500 mt-3 leading-relaxed">{riskSummary}</p>}
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
            {eventSummary && (
              <div className="bg-blue-50 rounded-lg p-3 mb-3 text-xs text-blue-800">{eventSummary}</div>
            )}
            <div className="space-y-3">
              {allDrivers.length > 0 ? allDrivers.map((d, i) => (
                <div key={`${d.driver}-${i}`} className="border border-slate-100 rounded-lg p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <Pill label={d.type as string} color={d.color as string} />
                      <span className="text-sm text-slate-800 truncate" style={{ fontWeight: 600 }}>{formatLabel(d.driver as string)}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      <span>Score {formatNum(d.score as number)}</span>
                      <span>·</span>
                      <span>Conf {formatNum(d.confidence as number)}</span>
                      <span>·</span>
                      <DirBadge d={formatLabel(d.direction as string)} />
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{d.explanation as string || "No explanation provided."}</p>
                </div>
              )) : (
                <div className="text-xs text-slate-400 py-4 text-center">No attribution drivers available for this report.</div>
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
  signals,
  derivativesData,
  newsData,
  onchainData,
  etfData,
  macroData,
  signalLayer,
  setSignalLayer,
}: {
  asset: string;
  signals: NormalizedSignal[];
  derivativesData: Record<string, unknown>;
  newsData: Record<string, unknown>;
  onchainData: Record<string, unknown>;
  etfData: Record<string, unknown>;
  macroData: Record<string, unknown>;
  signalLayer: string;
  setSignalLayer: (l: string) => void;
}) {
  const filteredSignals = signalLayer === "all" ? signals : signals.filter((s) => s.layer === signalLayer);

  const derivEntries = Object.entries(derivativesData)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => ({ k, v: typeof v === "number" ? formatNum(v) : String(v) }));

  const newsEvents = (newsData.events as Array<Record<string, unknown>>) || [];
  const largeTransfers = (onchainData.large_transfers as Array<Record<string, unknown>>) || [];

  const etfEntries = Object.entries(etfData)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => ({ k, v: typeof v === "number" ? formatNum(v) : String(v) }));

  const macroEntries = Object.entries(macroData)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => ({ k, v: typeof v === "number" ? formatNum(v) : String(v) }));

  const onchainSignal = (onchainData.onchain_signal as string) || "n/a";
  const largeTransferCount = (onchainData.large_transfer_count as number) || largeTransfers.length;
  const stablecoinChange = onchainData.stablecoin_supply_change_24h as number | null;

  return (
    <div className="space-y-4">
      <Card
        title="Signal Matrix"
        action={
          <div className="flex flex-wrap gap-1">
            {(["all", "derivatives", "market", "onchain", "news", "etf_flow", "macro"] as const).map((l) => (
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
        <p className="text-xs text-slate-500 mb-3">{asset} signals across all evidence layers.</p>
        <div className="overflow-x-auto w-full">
          <table className="w-full text-xs min-w-[560px]">
            <thead className="text-slate-400 border-b border-slate-100">
              <tr>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Layer</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Signal</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Value</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Direction</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Impact</th>
                <th className="text-left pb-2" style={{ fontWeight: 400 }}>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {filteredSignals.length > 0 ? filteredSignals.map((s, i) => (
                <tr key={`${s.layer}-${s.signal_name}-${i}`} className="border-b border-slate-50">
                  <td className="py-2 text-slate-500 truncate pr-2">{s.layer || "n/a"}</td>
                  <td className="py-2 text-slate-800 truncate pr-2">{formatLabel(s.signal_name)}</td>
                  <td className="py-2 text-slate-700 truncate pr-2" style={{ fontWeight: 500 }}>{s.signal_value || "n/a"}</td>
                  <td className="py-2 pr-2"><DirBadge d={formatLabel(s.direction)} /></td>
                  <td className="py-2 pr-2"><ImpactBadge i={s.impact_level || "low"} /></td>
                  <td className="py-2 text-slate-500 truncate">{formatNum(s.confidence)}</td>
                </tr>
              )) : (
                <tr><td colSpan={6} className="py-8 text-center text-slate-400">No normalized signals returned.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Derivatives">
          <p className="text-xs text-slate-500 mb-3">
            {derivEntries.length > 0 ? "Derivatives data from available providers." : "No derivatives data available."}
          </p>
          {derivEntries.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <tbody>
                  {derivEntries.map((d) => (
                    <tr key={d.k} className="border-b border-slate-50">
                      <td className="py-1.5 text-slate-400 pr-4 w-1/2">{labelForField(d.k)}</td>
                      <td className="py-1.5 text-slate-700" style={{ fontWeight: 500 }}>{d.v}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="News Drivers">
          <p className="text-xs text-slate-500 mb-3">
            {newsEvents.length > 0 ? "News events classified by direction, impact, and relevance." : "No classified news events."}
          </p>
          <div className="space-y-3">
            {newsEvents.length > 0 ? newsEvents.slice(0, 8).map((n, i) => (
              <div key={`${n.title}-${i}`} className="border-b border-slate-50 pb-2 last:border-0 min-w-0">
                <div className="text-xs text-slate-800 line-clamp-2" style={{ fontWeight: 500 }}>{n.title as string || "Untitled event"}</div>
                <div className="flex flex-wrap items-center gap-1.5 mt-1 text-xs">
                  <span className="text-slate-400 truncate max-w-[80px]">{(n.source as string) || "n/a"}</span>
                  <DirBadge d={formatLabel(n.direction as string)} />
                  <ImpactBadge i={(n.impact_level as string) || "low"} />
                  <Pill label={formatLabel(n.category as string)} />
                </div>
              </div>
            )) : (
              <div className="text-xs text-slate-400 py-4 text-center">No news events available.</div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title={`On-chain (${asset} context)`}>
          <p className="text-xs text-slate-500 mb-3">
            On-chain signal: {formatLabel(onchainSignal)}. Large transfers: {largeTransferCount}.
          </p>
          <div className="grid grid-cols-3 gap-2 text-xs mb-3">
            {[
              { k: "onchain_signal", v: formatLabel(onchainSignal) },
              { k: "large_transfer_count", v: String(largeTransferCount) },
              { k: "stablecoin_supply_24h", v: formatCurrency(stablecoinChange) },
            ].map((item) => (
              <div key={item.k} className="bg-slate-50 rounded-lg p-2">
                <div className="text-slate-400 truncate">{labelForField(item.k)}</div>
                <div className="text-slate-800 mt-0.5 truncate" style={{ fontWeight: 600 }}>{item.v}</div>
              </div>
            ))}
          </div>
          {largeTransfers.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs min-w-[320px]">
                <thead className="text-slate-400 border-b border-slate-100">
                  <tr>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Tx Hash</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Amount</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>From → To</th>
                    <th className="text-left pb-1.5 pr-2" style={{ fontWeight: 400 }}>Dir</th>
                  </tr>
                </thead>
                <tbody>
                  {largeTransfers.slice(0, 5).map((t, i) => (
                    <tr key={`${t.hash}-${i}`} className="border-b border-slate-50">
                      <td className="py-1.5 pr-2">
                        <span className="text-slate-500 font-mono text-xs" title={(t.hash as string) || ""}>{shortenHash((t.hash as string) || `transfer-${i}`)}</span>
                      </td>
                      <td className="py-1.5 pr-2 text-slate-700 truncate" style={{ fontWeight: 500 }}>{formatNum(t.amount as number)}</td>
                      <td className="py-1.5 pr-2 text-slate-500 text-xs max-w-[100px] truncate">{(t.from_label as string) || "unknown"} → {(t.to_label as string) || "unknown"}</td>
                      <td className="py-1.5 pr-2"><DirBadge d={formatLabel(t.direction as string)} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          {etfEntries.length > 0 && (
            <Card title="ETF Flow">
              <div className="space-y-2 text-xs">
                {etfEntries.map((e) => (
                  <div key={e.k} className="flex justify-between border-b border-slate-50 py-1.5 gap-2">
                    <span className="text-slate-400">{labelForField(e.k)}</span>
                    <span className="text-slate-700 truncate text-right" style={{ fontWeight: 500 }}>{e.v}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {macroEntries.length > 0 && (
            <Card title="Macro Context">
              <div className="space-y-2 text-xs">
                {macroEntries.map((m) => (
                  <div key={m.k} className="border-b border-slate-50 pb-2 last:border-0">
                    <div className="text-slate-400">{labelForField(m.k)}</div>
                    <div className="text-slate-700 mt-0.5 line-clamp-2" style={{ fontWeight: 500 }}>{m.v}</div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function TabDataQuality({ dataQualitySections }: { dataQualitySections: Record<string, Record<string, unknown>> }) {
  const sections = dataQualitySections || {};
  const entries = Object.entries(sections).map(([layer, info]) => ({
    layer: formatLabel(layer),
    status: (info.status as string) || "unknown",
    source: (info.source as string) || "n/a",
    quality: typeof info.overall_data_quality_score === "number" ? info.overall_data_quality_score as number : 0.5,
  }));

  const overall = entries.length > 0
    ? entries.reduce((sum, e) => sum + e.quality, 0) / entries.length
    : 0;
  const okCount = entries.filter((q) => q.status === "good" || q.status === "ok").length;

  if (entries.length === 0) {
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-xl border border-slate-100 p-8 text-center text-slate-400 text-sm">
          No data quality information available for this report.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Overall Score</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{overall.toFixed(2)}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Healthy Layers</div>
          <div className="text-2xl text-green-600" style={{ fontWeight: 700 }}>{okCount} / {entries.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Status</div>
          <div className="text-sm text-slate-700" style={{ fontWeight: 600 }}>
            {okCount === entries.length ? "All layers healthy" : okCount > entries.length / 2 ? "Partial — some layers degraded" : "Several layers degraded"}
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
              {entries.map((q) => (
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
  apiLogs,
  logFilter,
  setLogFilter,
}: {
  apiLogs: ApiCallLog[];
  logFilter: "all" | "errors";
  setLogFilter: (f: "all" | "errors") => void;
}) {
  const filteredLogs = logFilter === "errors" ? apiLogs.filter((l) => (l.status_code || 0) >= 400) : apiLogs;
  const errorCount = apiLogs.filter((l) => (l.status_code || 0) >= 400).length;
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
            <button onClick={() => setLogFilter("all")} className={`text-xs px-2 py-0.5 rounded ${logFilter === "all" ? "bg-blue-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}>All</button>
            <button onClick={() => setLogFilter("errors")} className={`text-xs px-2 py-0.5 rounded ${logFilter === "errors" ? "bg-red-600 text-white" : "text-slate-500 hover:bg-slate-50"}`}>Errors only</button>
          </div>
        }
      >
        {apiLogs.length > 0 ? (
          <div className="overflow-x-auto w-full">
            <table className="w-full text-xs min-w-[500px]">
              <thead className="text-slate-400 border-b border-slate-100">
                <tr>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Provider</th>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Endpoint</th>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Status</th>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Latency</th>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Time</th>
                  <th className="text-left pb-2" style={{ fontWeight: 400 }}>Error</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((l, i) => (
                  <tr key={i} className="border-b border-slate-50">
                    <td className="py-2 text-slate-700 truncate pr-2">{l.provider || "n/a"}</td>
                    <td className="py-2 text-slate-500 truncate pr-2" title={l.endpoint}>{l.endpoint || "n/a"}</td>
                    <td className="py-2 pr-2">
                      <Pill label={String(l.status_code ?? "n/a")} color={(l.status_code || 0) >= 400 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"} />
                    </td>
                    <td className="py-2 text-slate-600 truncate pr-2">{l.latency_ms ?? "n/a"} ms</td>
                    <td className="py-2 text-slate-400 truncate pr-2">{l.created_at ? new Date(l.created_at).toLocaleTimeString() : "n/a"}</td>
                    <td className="py-2 text-red-500 truncate" title={l.error_message ?? ""}>{l.error_message ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-slate-400 py-8 text-center">No API call logs for this report yet.</div>
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
          <button onClick={onCopy} className="text-xs border border-slate-200 text-slate-700 rounded-md px-2 py-1 hover:bg-slate-50">
            <Copy size={11} className="inline mr-1" />{copied ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="text-xs text-slate-700 bg-slate-50 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap" style={{ fontFamily: "ui-monospace, SFMono-Regular, monospace" }}>
          {markdown || "No markdown report available."}
        </pre>
      </CollapsibleCard>
    </div>
  );
}

// — Main component —

export function ReportDetail({
  reportId,
  asset = "BTC",
  query,
  reportMarkdown: liveReportMarkdown,
  reportStatus,
  riskScore,
  riskLevel,
  updatedAt,
  errorMessage,
  dashboardData: initialDashboardData,
  onBack,
  onOpenTrace,
}: ReportDetailProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [signalLayer, setSignalLayer] = useState<string>("all");
  const [logFilter, setLogFilter] = useState<"all" | "errors">("all");
  const [copied, setCopied] = useState(false);
  const [dashboardData, setDashboardData] = useState<DashboardData | null>(initialDashboardData || null);

  useEffect(() => {
    if (initialDashboardData) {
      setDashboardData(initialDashboardData);
      return;
    }
    if (!reportId) return;
    let cancelled = false;
    requestJson<DashboardData>(`/api/research/report/${reportId}/data`, "Failed to load report data")
      .then((data) => { if (!cancelled) setDashboardData(data); })
      .catch(() => { if (!cancelled) setDashboardData(null); });
    return () => { cancelled = true; };
  }, [reportId, initialDashboardData]);

  const marketData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.market), [dashboardData]);
  const riskData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.risk), [dashboardData]);
  const attributionData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.attribution), [dashboardData]);
  const derivativesData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.derivatives), [dashboardData]);
  const newsData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.news), [dashboardData]);
  const onchainData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.onchain), [dashboardData]);
  const etfData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.etf_flow), [dashboardData]);
  const macroData = useMemo(() => getSnapshotData(dashboardData?.snapshots?.macro), [dashboardData]);
  const signals = dashboardData?.normalized_signals || [];
  const apiLogs = dashboardData?.api_call_logs || [];
  const dataQualitySections = (attributionData.data_quality as Record<string, Record<string, unknown>>) || {};

  const activeReportMarkdown = liveReportMarkdown || "No markdown report available.";
  const updatedLabel = updatedAt ? new Date(updatedAt).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : null;

  function handleCopy() {
    navigator.clipboard?.writeText(activeReportMarkdown).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div>
      <div className="p-6 pb-0">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <button onClick={onBack} className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-800 mb-2">
              <ArrowLeft size={12} /> Back
            </button>
            <h1 className="text-2xl" style={{ fontWeight: 600 }}>Report Detail</h1>
            <p className="text-sm text-slate-500 mt-0.5 line-clamp-2 max-w-xl">
              {query || `Research report for ${asset}`}
            </p>
            <div className="flex flex-wrap gap-2 mt-2">
              {reportId && <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{reportId.slice(0, 8)}</span>}
              {reportStatus && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{reportStatus}</span>}
              {riskScore !== undefined && <span className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded">Risk {riskScore}</span>}
              {riskLevel && <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{riskLevel}</span>}
              {updatedLabel && <span className="text-xs text-slate-400 px-2 py-0.5">Updated {updatedLabel}</span>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={onOpenTrace} className="flex items-center gap-1.5 text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-2 hover:bg-slate-50">
              <GitBranch size={12} /> Attribution trace
            </button>
            <button onClick={handleCopy} className="flex items-center gap-1.5 text-xs border border-slate-200 text-slate-700 rounded-lg px-3 py-2 hover:bg-slate-50">
              <Copy size={12} /> {copied ? "Copied" : "Copy markdown"}
            </button>
          </div>
        </div>
      </div>

      <nav className="sticky top-0 z-10 bg-white border-b border-slate-100 px-6 flex gap-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`text-xs px-4 py-2.5 whitespace-nowrap border-b-2 transition-colors ${
              activeTab === tab.id ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
            style={{ fontWeight: activeTab === tab.id ? 600 : 400 }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <div className="p-6 space-y-4">
        {errorMessage && (
          <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-4 text-xs">{errorMessage}</div>
        )}
        {activeTab === "overview" && (
          <TabOverview asset={asset} reportId={reportId} marketData={marketData} riskData={riskData} attributionData={attributionData} onSwitchTab={setActiveTab} onOpenTrace={onOpenTrace} />
        )}
        {activeTab === "evidence" && (
          <TabEvidence asset={asset} signals={signals} derivativesData={derivativesData} newsData={newsData} onchainData={onchainData} etfData={etfData} macroData={macroData} signalLayer={signalLayer} setSignalLayer={setSignalLayer} />
        )}
        {activeTab === "dataquality" && <TabDataQuality dataQualitySections={dataQualitySections} />}
        {activeTab === "apilogs" && <TabAPILogs apiLogs={apiLogs} logFilter={logFilter} setLogFilter={setLogFilter} />}
        {activeTab === "markdown" && <TabMarkdown copied={copied} markdown={activeReportMarkdown} onCopy={handleCopy} />}

        <div className="text-xs text-slate-400 text-center pb-2">
          Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, hold, or use leverage.
        </div>
      </div>
    </div>
  );
}
