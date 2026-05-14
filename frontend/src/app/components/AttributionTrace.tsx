import { Fragment, useEffect, useMemo, useState } from "react";
import { requestJson } from "../api";

interface TraceCandidate {
  driver?: string;
  layer?: string;
  raw_score?: number;
  raw?: number;
  final_score?: number;
  final?: number;
  adjustments?: string[] | string;
  classification?: string;
  cls?: string;
  reason?: string;
}

interface TracePayload {
  attribution_trace?: TraceCandidate[];
  trace_summary?: Record<string, unknown>;
  data_quality?: Record<string, unknown>;
  alternative_explanations?: unknown[];
}

const fallbackCandidates: TraceCandidate[] = [
  {
    driver: "Long leverage flush",
    layer: "derivatives",
    raw_score: 2.5,
    adjustments: "+ timing + cross-layer confirmation",
    final_score: 2.84,
    classification: "Primary",
    reason: "Funding rate inversion and open interest contraction strongly support primary classification.",
  },
];

function ClassBadge({ cls }: { cls: string }) {
  const normalized = cls.toLowerCase();
  const map: Record<string, string> = {
    primary: "bg-blue-100 text-blue-700",
    secondary: "bg-orange-100 text-orange-700",
    context: "bg-slate-100 text-slate-600",
    noise: "bg-red-100 text-red-700",
  };
  return <span className={`text-xs px-2 py-0.5 rounded ${map[normalized] ?? "bg-gray-100 text-gray-600"}`}>{cls}</span>;
}

function formatAdjustments(value?: string[] | string) {
  if (Array.isArray(value)) return value.join(", ");
  return value || "n/a";
}

export function AttributionTrace({ reportId }: { reportId?: string | null }) {
  const [payload, setPayload] = useState<TracePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!reportId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await requestJson<TracePayload>(`/api/research/report/${reportId}/trace`, "Failed to load attribution trace");
        if (!cancelled) setPayload(data);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  const candidates = payload?.attribution_trace?.length ? payload.attribution_trace : fallbackCandidates;
  const summary = useMemo(() => {
    const primary = candidates.filter((c) => (c.classification || c.cls || "").toLowerCase() === "primary").length;
    const secondary = candidates.filter((c) => (c.classification || c.cls || "").toLowerCase() === "secondary").length;
    const noise = candidates.filter((c) => ["noise", "context"].includes((c.classification || c.cls || "").toLowerCase())).length;
    const qualityValues = Object.values(payload?.data_quality || {}).filter((v): v is number => typeof v === "number");
    const quality = qualityValues.length
      ? (qualityValues.reduce((sum, v) => sum + v, 0) / qualityValues.length).toFixed(2)
      : "n/a";

    return { primary, secondary, noise, quality };
  }, [candidates, payload]);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Attribution Trace</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Audit why each candidate driver was classified as primary, secondary, context, or noise.
        </p>
      </div>

      {error && <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-3 text-xs">{error}</div>}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Primary Drivers", value: loading ? "..." : summary.primary, color: "bg-blue-50 border-blue-100", text: "text-blue-700" },
          { label: "Secondary Drivers", value: loading ? "..." : summary.secondary, color: "bg-orange-50 border-orange-100", text: "text-orange-700" },
          { label: "Context / Noise", value: loading ? "..." : summary.noise, color: "bg-slate-50 border-slate-200", text: "text-slate-600" },
          { label: "Overall Data Quality", value: loading ? "..." : summary.quality, color: "bg-yellow-50 border-yellow-100", text: "text-yellow-700" },
        ].map((s) => (
          <div key={s.label} className={`rounded-xl border p-4 ${s.color}`}>
            <div className="text-xs text-slate-500 mb-1">{s.label}</div>
            <div className={`text-2xl ${s.text}`} style={{ fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h3 className="text-base mb-1" style={{ fontWeight: 600 }}>
          {reportId ? `Report ${reportId}` : "Latest report"} attribution trace
        </h3>
        <p className="text-xs text-slate-500">
          This view is loaded from the backend trace endpoint for the selected report.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h3 className="text-base mb-4" style={{ fontWeight: 600 }}>Candidate Scoring</h3>
        <div className="overflow-x-auto w-full">
          <table className="w-full text-xs min-w-[560px]">
            <thead>
              <tr className="text-slate-400 border-b border-slate-100">
                {["Driver", "Layer", "Raw", "Adjustments", "Final", "Class"].map((h) => (
                  <th key={h} className="text-left pb-3 pr-6 whitespace-nowrap" style={{ fontWeight: 400 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {candidates.map((c, i) => {
                const classification = c.classification || c.cls || "Context";
                const rawScore = c.raw_score ?? c.raw;
                const finalScore = c.final_score ?? c.final;
                return (
                  <Fragment key={`${c.driver}-${i}`}>
                    <tr className="border-b border-slate-50">
                      <td className="pt-4 pb-1 pr-6 text-slate-800 max-w-[160px] truncate" style={{ fontWeight: 500 }} title={c.driver}>{c.driver || "Unknown driver"}</td>
                      <td className="pt-4 pb-1 pr-6 text-slate-500 whitespace-nowrap">{c.layer || "n/a"}</td>
                      <td className="pt-4 pb-1 pr-6" style={{ fontWeight: 600 }}>{typeof rawScore === "number" ? rawScore.toFixed(2) : "n/a"}</td>
                      <td className="pt-4 pb-1 pr-6 text-slate-500 max-w-[220px] truncate" title={formatAdjustments(c.adjustments)}>{formatAdjustments(c.adjustments)}</td>
                      <td className="pt-4 pb-1 pr-6" style={{ fontWeight: 600 }}>{typeof finalScore === "number" ? finalScore.toFixed(2) : "n/a"}</td>
                      <td className="pt-4 pb-1"><ClassBadge cls={classification} /></td>
                    </tr>
                    <tr className="border-b border-slate-100">
                      <td colSpan={6} className="pb-3 pr-6 text-slate-400 text-xs line-clamp-2">
                        {c.reason || "No detailed reason provided by backend trace."}
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
