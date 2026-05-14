import { useEffect, useState } from "react";
import { Sparkline } from "./Sparkline";
import { Play, Loader2, TrendingDown, TrendingUp, Minus } from "lucide-react";
import { requestJson } from "../api";

const emptySparkData = [0, 0, 0, 0, 0, 0, 0];

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

function formatCurrency(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: value >= 1000 ? 0 : 2,
  }).format(value);
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

interface MarketScanRecord {
  asset: "BTC" | "ETH";
  price_now: number | null;
  price_change_4h_pct: number | null;
  direction: "rising" | "falling" | "neutral";
  direction_label_zh: string;
  created_at: string;
}

const processSteps = [
  "Fetching market data",
  "Fetching derivatives",
  "Classifying news",
  "On-chain context",
  "Building attribution",
  "Generating report",
];

interface AutoScanReport {
  report_id: string;
  asset: string;
  price_now?: number | null;
  price_change_4h_pct?: number | null;
  price_change_24h_pct?: number | null;
  direction?: string | null;
  direction_label_zh?: string | null;
  trigger_reason?: string | null;
  report_markdown?: string;
  updated_at?: string;
}

function isMissingEndpointError(error: unknown) {
  return error instanceof Error && error.message.includes("HTTP 404");
}

function reportToMarketScan(report: AutoScanReport): MarketScanRecord | null {
  if (report.asset !== "BTC" && report.asset !== "ETH") return null;
  return {
    asset: report.asset,
    price_now: report.price_now ?? null,
    price_change_4h_pct: report.price_change_4h_pct ?? null,
    direction:
      report.direction === "rising" || report.direction === "falling" || report.direction === "neutral"
        ? report.direction
        : "neutral",
    direction_label_zh: report.direction_label_zh || "震荡",
    created_at: report.updated_at || new Date().toISOString(),
  };
}

export function AutoScan({ onOpenDetail }: { onOpenDetail?: (reportId?: string) => void } = {}) {
  const [assets, setAssets] = useState<{ BTC: boolean; ETH: boolean }>({ BTC: true, ETH: true });
  const [window, setWindow] = useState("4h");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(0);
  const [reports, setReports] = useState<AutoScanReport[]>([]);
  const [marketScans, setMarketScans] = useState<MarketScanRecord[]>([]);
  const [scanLog, setScanLog] = useState([
    { time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), msg: "Auto scan ready", status: "info" },
  ]);
  const [error, setError] = useState<string | null>(null);

  async function loadMarketScans(selectedAssets: Array<"BTC" | "ETH">, force = false) {
    const payload = await requestJson<{ results: MarketScanRecord[] }>("/api/research/market-scan", "Failed to load market prices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assets: selectedAssets, force_refresh: force }),
    });
    setMarketScans(payload.results || []);
    return payload.results || [];
  }

  useEffect(() => {
    loadMarketScans(["BTC", "ETH"], false)
      .catch(() => {});
  }, []);

  async function handleRun() {
    setRunning(true);
    setActiveStep(0);
    setError(null);
    setScanLog([{ time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), msg: "Auto scan started", status: "info" }]);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setActiveStep(i);
      if (i >= processSteps.length) {
        clearInterval(id);
      }
    }, 450);

    try {
      const selectedAssets = (Object.entries(assets).filter(([, enabled]) => enabled).map(([asset]) => asset) as Array<"BTC" | "ETH">);
      const payload = await requestJson<{ generated_at: string; cache_hit: boolean; reports: AutoScanReport[] }>("/api/research/auto-scan", "Failed to run auto scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          assets: selectedAssets.length ? selectedAssets : ["BTC", "ETH"],
          time_window: window,
          force_refresh: forceRefresh,
        }),
      });

      clearInterval(id);
      setActiveStep(processSteps.length);
      setReports(payload.reports || []);
      const scansFromReports = (payload.reports || [])
        .map(reportToMarketScan)
        .filter((scan): scan is MarketScanRecord => scan !== null);
      if (scansFromReports.length) {
        setMarketScans(scansFromReports);
      }
      setScanLog([
        {
          time: new Date(payload.generated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          msg: payload.cache_hit ? "Loaded cached auto-scan reports" : "Auto-scan reports generated",
          status: "ok",
        },
        ...payload.reports.map((report) => ({
          time: report.updated_at ? new Date(report.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "n/a",
          msg: `${report.asset} report completed`,
          status: "ok",
        })),
      ]);
    } catch (err) {
      if (isMissingEndpointError(err)) {
        try {
          const selectedAssets = (Object.entries(assets).filter(([, enabled]) => enabled).map(([asset]) => asset) as Array<"BTC" | "ETH">);
          const scans = await loadMarketScans(selectedAssets.length ? selectedAssets : ["BTC", "ETH"], forceRefresh);
          clearInterval(id);
          setActiveStep(processSteps.length);
          setError(null);
          setScanLog([
            {
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              msg: "Loaded market scan data; auto-report endpoint is not available on this backend",
              status: "ok",
            },
            ...scans.map((scan) => ({
              time: new Date(scan.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
              msg: `${scan.asset} market scan completed`,
              status: "ok",
            })),
          ]);
          return;
        } catch (fallbackErr) {
          err = fallbackErr;
        }
      }
      clearInterval(id);
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setScanLog((prev) => [
        { time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }), msg: "Auto scan failed", status: "warn" },
        ...prev,
      ]);
    } finally {
      setRunning(false);
    }
  }

  const latestReport = reports[0];
  const autoReportRows = latestReport
    ? [
        { label: "Asset", value: latestReport.asset },
        { label: "Market", value: latestReport.direction || latestReport.direction_label_zh || "n/a" },
        { label: "4h Change", value: latestReport.price_change_4h_pct === null || latestReport.price_change_4h_pct === undefined ? "n/a" : `${latestReport.price_change_4h_pct.toFixed(2)}%` },
        { label: "Trigger", value: latestReport.trigger_reason || "n/a" },
      ]
    : [
        { label: "Market", value: "Run auto scan to load backend data" },
        { label: "Assets", value: Object.entries(assets).filter(([, enabled]) => enabled).map(([asset]) => asset).join(", ") || "None" },
        { label: "Window", value: window },
        { label: "Force Refresh", value: forceRefresh ? "On" : "Off" },
      ];

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Auto Scan</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Trigger or monitor automatic BTC / ETH market scans using backend cache, 4h thresholds, and auto-report generation.
        </p>
      </div>

      {error && <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-3 text-xs">{error}</div>}

      {/* Scan Controls */}
      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <h3 className="text-sm" style={{ fontWeight: 600 }}>Scan Controls</h3>
            <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
              {(["BTC", "ETH"] as const).map((a) => (
                <button
                  key={a}
                  onClick={() => setAssets({ ...assets, [a]: !assets[a] })}
                  className={`text-xs px-3 py-1 rounded-md transition-colors ${
                    assets[a] ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-white"
                  }`}
                >
                  {a}
                </button>
              ))}
            </div>
            <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
              {(["4h", "24h", "7d"] as const).map((w) => (
                <button
                  key={w}
                  onClick={() => setWindow(w)}
                  className={`text-xs px-2.5 py-1 rounded-md transition-colors ${
                    window === w ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-white"
                  }`}
                >
                  {w}
                </button>
              ))}
            </div>
            <button
              onClick={() => setForceRefresh(!forceRefresh)}
              className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
                forceRefresh ? "border-orange-300 bg-orange-50 text-orange-600" : "border-slate-200 text-slate-500"
              }`}
            >
              {forceRefresh ? "Force refresh: on" : "Force refresh: off"}
            </button>
          </div>
          <button
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-2 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-60"
            style={{ fontWeight: 500 }}
          >
            <Play size={13} />
            {running ? "Running..." : "Run Auto Scan"}
          </button>
        </div>
      </div>

      {/* BTC + ETH price cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {(["BTC", "ETH"] as const).map((asset) => {
          const reportScan = reports.map(reportToMarketScan).find((s) => s?.asset === asset);
          const scan = marketScans.find((s) => s.asset === asset) || reportScan;
          const price = scan?.price_now ?? null;
          const change = scan?.price_change_4h_pct ?? null;
          const direction = scan?.direction || "neutral";
          const trend = trendFor(change);
          const directionLabel = direction === "falling" ? "Falling" : direction === "rising" ? "Rising" : "Neutral";
          const directionColor = direction === "falling" ? "bg-red-100 text-red-700" : direction === "rising" ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-600";
          const changeColor = trend === "down" ? "text-red-500" : trend === "up" ? "text-green-600" : "text-slate-500";
          const sparkColor = trend === "down" ? "#EF4444" : trend === "up" ? "#10B981" : "#64748B";
          const thresholdNote = direction === "falling" ? "Exceeded downside threshold" : direction === "rising" ? "Exceeded upside threshold" : "Move stayed inside threshold band";
          const TrendIcon = trend === "up" ? TrendingUp : trend === "down" ? TrendingDown : Minus;

          return (
            <div key={asset} className="bg-white rounded-xl border border-slate-100 p-5">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg" style={{ fontWeight: 600 }}>{asset}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${directionColor}`}>{price ? directionLabel : "No data"}</span>
              </div>
              <div className="flex items-end justify-between">
                <div>
                  <div className="text-3xl" style={{ fontWeight: 700 }}>{formatCurrency(price)}</div>
                  <div className={`text-sm mt-1 flex items-center gap-1 ${changeColor}`}>
                    <TrendIcon size={12} />
                    {formatPercent(change)}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">{price ? thresholdNote : "Run a scan to load market data"}</div>
                </div>
                <Sparkline data={sparkFromPrice(price, change)} color={sparkColor} width={110} height={50} />
              </div>
              {scan && (
                <div className="flex items-center gap-3 mt-3 pt-3 border-t border-slate-50 text-[10px] text-slate-400">
                  <span>Source: market scan</span>
                  <span>Snapshot: {new Date(scan.created_at).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Processing steps — responsive grid */}
      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm" style={{ fontWeight: 600 }}>Processing Steps</h3>
          <span className="text-xs text-slate-400">
            {running ? `Step ${Math.min(activeStep + 1, processSteps.length)} of ${processSteps.length}` : "Idle"}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
          {processSteps.map((step, i) => {
            const done = i < activeStep;
            const active = i === activeStep && running;
            return (
              <div
                key={step}
                className={`rounded-lg p-2.5 border ${
                  done ? "bg-green-50 border-green-200" :
                  active ? "bg-blue-50 border-blue-200" :
                  "bg-slate-50 border-slate-100"
                }`}
              >
                <div className={`text-xs ${done ? "text-green-700" : active ? "text-blue-700" : "text-slate-400"}`} style={{ fontWeight: 600 }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <div className={`text-xs mt-1 flex items-center gap-1 ${done ? "text-green-700" : active ? "text-blue-700" : "text-slate-500"}`}>
                  {step}
                  {active && <Loader2 size={12} className="animate-spin shrink-0" />}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Report + Scan Log row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-sm mb-3" style={{ fontWeight: 600 }}>Latest Auto Report</h3>
          <div className="text-base mb-1 truncate" style={{ fontWeight: 600 }}>
            {latestReport ? `${latestReport.asset} ${window} Market Scan Report` : "Latest Auto Report"}
          </div>
          {latestReport && (
            <div className="text-[10px] text-slate-400 mb-2">
              Report ID: {latestReport.report_id} · {latestReport.updated_at ? new Date(latestReport.updated_at).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : ""}
            </div>
          )}
          <div className="overflow-x-auto w-full">
            <table className="w-full text-xs mb-4">
              <tbody>
                {autoReportRows.map((row) => (
                  <tr key={row.label} className="border-b border-slate-50">
                    <td className="py-2 text-slate-400 w-28 shrink-0">{row.label}</td>
                    <td className="py-2 text-slate-700">{row.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onOpenDetail?.(latestReport?.report_id)}
              disabled={!latestReport}
              className="text-xs text-blue-600 border border-blue-200 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
            >
              Open full report
            </button>
            <button className="text-xs text-slate-600 border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">
              View trace
            </button>
            <button className="text-xs text-slate-600 border border-slate-200 px-3 py-1.5 rounded-lg hover:bg-slate-50 transition-colors">
              Copy markdown
            </button>
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-sm mb-3" style={{ fontWeight: 600 }}>Scan Log</h3>
          <div className="space-y-3">
            {scanLog.map((entry, i) => (
              <div key={i} className="flex items-center gap-3 text-xs">
                <div className={`w-2 h-2 rounded-full shrink-0 ${
                  entry.status === "ok" ? "bg-green-500" :
                  entry.status === "warn" ? "bg-yellow-400" :
                  "bg-blue-400"
                }`} />
                <span className="text-slate-400 w-10 shrink-0">{entry.time}</span>
                <span className="text-slate-600 truncate">{entry.msg}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
