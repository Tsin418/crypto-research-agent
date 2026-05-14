import { useEffect, useMemo, useState } from "react";
import { Sparkline } from "./Sparkline";
import { shortenHash } from "../../utils/labels";
import { requestJson } from "../api";

const emptyTrend = [0, 0, 0, 0, 0, 0, 0];

interface LatestReport {
  report_id: string;
}

interface SnapshotEnvelope {
  source?: string;
  data?: { data?: Record<string, unknown>; errors?: string[] } | Record<string, unknown>;
}

interface ReportData {
  snapshots: Record<string, SnapshotEnvelope>;
}

interface OnchainEvent {
  time: string;
  asset: string;
  amount: string;
  hash: string;
  from: string;
  to: string;
  direction: string;
  source: string;
}

function getSnapshotData(snapshot?: SnapshotEnvelope) {
  const data = snapshot?.data;
  if (!data) return {};
  if ("data" in data && data.data && typeof data.data === "object") return data.data as Record<string, unknown>;
  return data as Record<string, unknown>;
}

function DirectionBadge({ direction }: { direction: string }) {
  const cls =
    direction.includes("inflow") ? "bg-red-100 text-red-700" :
    direction.includes("outflow") ? "bg-green-100 text-green-700" :
    direction.includes("large") ? "bg-orange-100 text-orange-700" :
    "bg-slate-100 text-slate-600";
  const label = direction.replaceAll("_", " ");
  return <span className={`text-xs px-2 py-0.5 rounded whitespace-nowrap ${cls}`}>{label}</span>;
}

export function OnchainEvents() {
  const [filter, setFilter] = useState("ETH only");
  const [limit, setLimit] = useState("Limit 50");
  const [events, setEvents] = useState<OnchainEvent[]>([]);
  const [source, setSource] = useState<string>("backend");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const latest = await requestJson<LatestReport>("/api/research/latest?asset=ETH", "Failed to load latest ETH report");
        const data = await requestJson<ReportData>(`/api/research/report/${latest.report_id}/data`, "Failed to load on-chain report data");
        const onchainSnapshot = data.snapshots.onchain;
        const onchain = getSnapshotData(onchainSnapshot);
        const rawTransfers = Array.isArray(onchain.large_transfers) ? onchain.large_transfers : [];
        const mapped = rawTransfers.slice(0, limit === "Limit 50" ? 50 : 100).map((item, index) => {
          const row = item as Record<string, unknown>;
          return {
            time: typeof row.timestamp === "string" ? new Date(row.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "n/a",
            asset: "ETH",
            amount: row.amount === undefined || row.amount === null ? "n/a" : String(row.amount),
            hash: typeof row.hash === "string" ? row.hash : `event-${index}`,
            from: typeof row.from_label === "string" ? row.from_label : "unknown",
            to: typeof row.to_label === "string" ? row.to_label : "unknown",
            direction: typeof row.direction === "string" ? row.direction : "large_transfer",
            source: onchainSnapshot?.source || "onchain",
          };
        });

        if (!cancelled) {
          setEvents(mapped);
          setSource(onchainSnapshot?.source || "backend");
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
  }, [limit]);

  const stats = useMemo(() => {
    const inflows = events.filter((event) => event.direction.includes("inflow")).length;
    const outflows = events.filter((event) => event.direction.includes("outflow")).length;
    const labeled = events.filter((event) => event.from !== "unknown" || event.to !== "unknown").length;
    const coverage = events.length ? Math.round((labeled / events.length) * 100) : 0;

    return [
      { label: "ETH Transfers", value: String(events.length), sub: source, data: emptyTrend, color: "#3B82F6" },
      { label: "Large Transfers", value: String(events.length), sub: "latest report", data: emptyTrend, color: "#F59E0B" },
      { label: "Exchange Inflows", value: String(inflows), sub: `${outflows} outflows`, data: emptyTrend, color: "#EF4444" },
      { label: "Label Coverage", value: events.length ? `${coverage}%` : "n/a", sub: "wallet labels", data: emptyTrend, color: "#10B981" },
    ];
  }, [events, source]);

  const visibleEvents = filter === "ETH only" ? events.filter((event) => event.asset === "ETH") : events;

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>On-chain Events</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Inspect on-chain evidence from the latest backend report snapshot.
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

      <div className="bg-white rounded-xl border border-slate-100 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h3 className="text-base" style={{ fontWeight: 600 }}>Recent On-chain Events</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setFilter(filter === "ETH only" ? "All" : "ETH only")}
              className={`text-xs px-3 py-1 rounded-lg border transition-colors ${
                filter === "ETH only" ? "border-blue-600 bg-blue-600 text-white" : "border-slate-200 text-slate-600"
              }`}
            >
              {filter}
            </button>
            <button
              onClick={() => setLimit(limit === "Limit 50" ? "Limit 100" : "Limit 50")}
              className="text-xs px-3 py-1 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              {limit}
            </button>
          </div>
        </div>
        <div className="overflow-x-auto w-full">
          <table className="w-full text-xs min-w-[600px]">
            <thead>
              <tr className="text-slate-400 border-b border-slate-100">
                {["Time", "Asset", "Amount", "Tx Hash", "From", "To", "Direction", "Source"].map((h) => (
                  <th key={h} className="text-left pb-2 pr-4 whitespace-nowrap" style={{ fontWeight: 400 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleEvents.map((e, i) => (
                <tr key={`${e.hash}-${i}`} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                  <td className="py-3 pr-4 text-slate-400 whitespace-nowrap">{e.time}</td>
                  <td className="py-3 pr-4" style={{ fontWeight: 600 }}>{e.asset}</td>
                  <td className="py-3 pr-4" style={{ fontWeight: 500 }}>{e.amount}</td>
                  <td className="py-3 pr-4">
                    <span className="text-slate-500 font-mono" title={e.hash}>
                      {shortenHash(e.hash)}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-slate-500 max-w-[120px] truncate" title={e.from}>{e.from}</td>
                  <td className="py-3 pr-4 text-slate-500 max-w-[120px] truncate" title={e.to}>{e.to}</td>
                  <td className="py-3 pr-4"><DirectionBadge direction={e.direction} /></td>
                  <td className="py-3 text-slate-400">{e.source}</td>
                </tr>
              ))}
              {!loading && visibleEvents.length === 0 && (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">No on-chain events in the latest report snapshot.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
