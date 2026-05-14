import { useEffect, useMemo, useState } from "react";
import { Sparkline } from "./Sparkline";
import { requestJson } from "../api";

const emptyTrend = [0, 0, 0, 0, 0, 0, 0];

interface SourceHealth {
  provider: string;
  success_count: number;
  error_count: number;
  avg_latency_ms: number;
  last_success_at: string | null;
  last_error_at: string | null;
  health_status: "healthy" | "degraded" | "down" | string;
}

interface ApiLog {
  provider?: string;
  endpoint?: string;
  status_code?: number | null;
  latency_ms?: number | null;
  error_message?: string | null;
  created_at?: string;
}

interface ReportRecord {
  report_id: string;
}

interface ReportData {
  api_call_logs: ApiLog[];
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "healthy" ? "bg-green-100 text-green-700" :
    status === "degraded" ? "bg-yellow-100 text-yellow-700" :
    "bg-red-100 text-red-700";
  const label = status.charAt(0).toUpperCase() + status.slice(1);
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{label}</span>;
}

function formatLatency(value?: number | null) {
  if (value === null || value === undefined) return "n/a";
  return value >= 1000 ? `${(value / 1000).toFixed(1)}s` : `${Math.round(value)}ms`;
}

function logsToSourceHealth(logs: ApiLog[]): SourceHealth[] {
  const byProvider = new Map<string, ApiLog[]>();
  for (const log of logs) {
    const provider = log.provider || "unknown";
    byProvider.set(provider, [...(byProvider.get(provider) || []), log]);
  }

  return Array.from(byProvider.entries()).map(([provider, providerLogs]) => {
    const successes = providerLogs.filter((log) => (log.status_code || 0) >= 200 && (log.status_code || 0) < 400 && !log.error_message);
    const errors = providerLogs.length - successes.length;
    const avgLatency = providerLogs.reduce((sum, log) => sum + (log.latency_ms || 0), 0) / Math.max(providerLogs.length, 1);
    return {
      provider,
      success_count: successes.length,
      error_count: errors,
      avg_latency_ms: avgLatency,
      last_success_at: successes[0]?.created_at || null,
      last_error_at: providerLogs.find((log) => log.error_message || (log.status_code || 0) >= 400)?.created_at || null,
      health_status: errors === 0 ? "healthy" : errors >= successes.length ? "down" : "degraded",
    };
  });
}

export function DataSources() {
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [apiLogs, setApiLogs] = useState<ApiLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        let healthSources: SourceHealth[] = [];
        try {
          const health = await requestJson<{ sources: SourceHealth[] }>("/api/research/source-health?lookback_hours=24", "Failed to load source health");
          healthSources = health.sources || [];
        } catch (healthError) {
          console.warn(healthError);
        }

        const reports = await requestJson<{ reports: ReportRecord[] }>("/api/research/reports?limit=1", "Failed to load latest report");
        let logs: ApiLog[] = [];
        if (reports.reports[0]?.report_id) {
          const data = await requestJson<ReportData>(`/api/research/report/${reports.reports[0].report_id}/data`, "Failed to load API logs");
          logs = data.api_call_logs || [];
        }

        if (!cancelled) {
          setSources(healthSources.length ? healthSources : logsToSourceHealth(logs));
          setApiLogs(logs);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    const healthy = sources.filter((s) => s.health_status === "healthy").length;
    const degraded = sources.filter((s) => s.health_status === "degraded").length;
    const down = sources.filter((s) => s.health_status === "down").length;
    const avgLatency = sources.length
      ? Math.round(sources.reduce((sum, s) => sum + (s.avg_latency_ms || 0), 0) / sources.length)
      : 0;

    return [
      { label: "Healthy", value: String(healthy), sub: "providers online", data: emptyTrend, color: "#10B981" },
      { label: "Degraded", value: String(degraded), sub: "partial failures", data: emptyTrend, color: "#F59E0B" },
      { label: "Down", value: String(down), sub: "needs fallback", data: emptyTrend, color: "#EF4444" },
      { label: "Avg Latency", value: avgLatency ? formatLatency(avgLatency) : "n/a", sub: "last 24h", data: emptyTrend, color: "#3B82F6" },
    ];
  }, [sources]);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Data Sources</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Monitor provider health, latency, last success time, and API call quality behind every research report.
        </p>
      </div>

      {error && <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-3 text-xs">{error}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-xs text-slate-500 mb-1 truncate">{s.label}</div>
                <div className="text-2xl" style={{ fontWeight: 700 }}>{loading ? "..." : s.value}</div>
                <div className="text-xs text-slate-400 mt-0.5">{s.sub}</div>
              </div>
              <Sparkline data={s.data} color={s.color} width={70} height={30} />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-base mb-4" style={{ fontWeight: 600 }}>Provider Health</h3>
          <div className="overflow-x-auto w-full">
            <table className="w-full text-xs min-w-[520px]">
              <thead>
                <tr className="text-slate-400 border-b border-slate-100">
                  {["Provider", "Status", "Success", "Errors", "Latency", "Last Success"].map((h) => (
                    <th key={h} className="text-left pb-2 pr-4 whitespace-nowrap" style={{ fontWeight: 400 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sources.map((p) => (
                  <tr key={p.provider} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                    <td className="py-3 pr-4" style={{ fontWeight: 500 }}>{p.provider}</td>
                    <td className="py-3 pr-4"><StatusBadge status={p.health_status} /></td>
                    <td className="py-3 pr-4 text-slate-600">{p.success_count}</td>
                    <td className="py-3 pr-4 text-slate-600">{p.error_count}</td>
                    <td className="py-3 pr-4 text-slate-500">{formatLatency(p.avg_latency_ms)}</td>
                    <td className="py-3 text-slate-400 whitespace-nowrap">{p.last_success_at ? new Date(p.last_success_at).toLocaleString() : "n/a"}</td>
                  </tr>
                ))}
                {!loading && sources.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-slate-400">No source health records yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="w-full lg:w-72 bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-base mb-4" style={{ fontWeight: 600 }}>Recent API Logs</h3>
          <div className="space-y-3">
            {apiLogs.slice(0, 8).map((log, i) => (
              <div key={`${log.provider}-${log.endpoint}-${i}`} className="border border-slate-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1 min-w-0 gap-2">
                  <span className="text-xs truncate" style={{ fontWeight: 600 }}>{log.provider || "unknown"}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs ${(log.status_code || 0) < 400 ? "text-green-600" : "text-red-600"}`} style={{ fontWeight: 600 }}>
                      {log.status_code ?? "n/a"}
                    </span>
                    <span className="text-xs text-slate-400">{formatLatency(log.latency_ms)}</span>
                  </div>
                </div>
                <div className="text-xs text-slate-400 truncate" title={log.endpoint}>{log.endpoint || "n/a"}</div>
              </div>
            ))}
            {!loading && apiLogs.length === 0 && <div className="text-xs text-slate-400">No API logs for the latest report yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
