import { useState } from "react";
import { Search, FileText } from "lucide-react";
import type { ReportRecord } from "./dashboard/types";

interface DisplayReport {
  id: string;
  query: string;
  asset: string;
  mode: string;
  risk: string;
  updated: string;
  status: string;
  error?: string | null;
}

function RiskBadge({ risk }: { risk: string }) {
  const cls =
    risk === "High" ? "bg-red-100 text-red-700" :
    risk === "Medium" ? "bg-orange-100 text-orange-700" :
    "bg-green-100 text-green-700";
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{risk}</span>;
}

function AssetBadge({ asset }: { asset: string }) {
  const cls = asset === "BTC" ? "bg-orange-50 text-orange-700 border border-orange-200" : "bg-blue-50 text-blue-700 border border-blue-200";
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{asset}</span>;
}

const filterTabs = ["All", "BTC", "ETH", "Completed", "Processing", "Failed", "Event Attribution", "State Scan", "Risk Watch", "High Risk", "Low Risk"];

function titleCase(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatUpdated(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function Reports({
  reports: backendReports,
  onOpenDetail,
}: {
  reports?: ReportRecord[];
  onOpenDetail?: (reportId?: string) => void;
} = {}) {
  const [activeFilter, setActiveFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [selectedIdx, setSelectedIdx] = useState(0);
  const reports: DisplayReport[] = backendReports?.length
    ? backendReports.map((report) => ({
        id: report.report_id,
        query: report.user_query,
        asset: report.asset || "n/a",
        mode: titleCase(report.mode || "event attribution"),
        risk: titleCase(report.risk_level || (report.status === "failed" ? "high" : "medium")),
        updated: formatUpdated(report.updated_at),
        status: report.status,
        error: report.error_message,
      }))
    : [];

  const completedCount = reports.filter((r) => r.status === "completed").length;
  const failedCount = reports.filter((r) => r.status === "failed").length;
  const latestBTC = reports.find((r) => r.asset === "BTC");
  const latestETH = reports.find((r) => r.asset === "ETH");

  const filtered = reports.filter((r) => {
    const matchFilter =
      activeFilter === "All" ||
      r.asset === activeFilter ||
      (activeFilter === "Completed" && r.status === "completed") ||
      (activeFilter === "Processing" && r.status === "processing") ||
      (activeFilter === "Failed" && r.status === "failed") ||
      (activeFilter === "Event Attribution" && r.mode.toLowerCase() === "event attribution") ||
      (activeFilter === "State Scan" && r.mode.toLowerCase() === "state scan") ||
      (activeFilter === "Risk Watch" && r.mode.toLowerCase() === "risk watch") ||
      (activeFilter === "High Risk" && r.risk === "High") ||
      (activeFilter === "Low Risk" && r.risk === "Low");
    const matchSearch = !search || r.query.toLowerCase().includes(search.toLowerCase());
    return matchFilter && matchSearch;
  });

  const selected = filtered[selectedIdx] ?? reports[0];

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Reports</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Browse persisted backend reports, including completed, processing, and failed runs.
        </p>
      </div>

      {reports.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <div className="text-base text-slate-900" style={{ fontWeight: 600 }}>No reports loaded.</div>
          <p className="text-sm text-slate-500 mt-1">
            Generate a report or run Auto Scan to create report-backed dashboard data.
          </p>
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Total Reports</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{reports.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Completed</div>
          <div className="text-2xl text-green-600" style={{ fontWeight: 700 }}>{completedCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Failed</div>
          <div className="text-2xl text-red-600" style={{ fontWeight: 700 }}>{failedCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Latest BTC / ETH</div>
          <div className="text-xs mt-1 space-y-1">
            <div className="flex items-center gap-2">
              <AssetBadge asset="BTC" />
              <span className="text-slate-600 truncate">{latestBTC?.updated ?? "—"}</span>
            </div>
            <div className="flex items-center gap-2">
              <AssetBadge asset="ETH" />
              <span className="text-slate-600 truncate">{latestETH?.updated ?? "—"}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        {/* Report library */}
        <div className="flex-1 bg-white rounded-xl border border-slate-100 min-w-0">
          <div className="p-4 border-b border-slate-100">
            <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
              <h3 className="text-base" style={{ fontWeight: 600 }}>Report Library</h3>
              <div className="relative">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  className="text-xs border border-slate-200 rounded-lg pl-7 pr-3 py-1.5 outline-none focus:border-blue-400 bg-slate-50"
                  placeholder="Search reports..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {filterTabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => { setActiveFilter(tab); setSelectedIdx(0); }}
                  className={`text-xs px-3 py-1 rounded-full border transition-colors whitespace-nowrap ${
                    activeFilter === tab
                      ? "bg-blue-600 text-white border-blue-600"
                      : "border-slate-200 text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          <div className="p-4">
            <h4 className="text-sm mb-3" style={{ fontWeight: 600 }}>Recent Research Reports</h4>
            <div className="overflow-x-auto w-full">
              <table className="w-full text-xs table-fixed min-w-[500px]">
                <thead>
                  <tr className="text-slate-400 border-b border-slate-100">
                    <th className="text-left pb-2 w-1/2" style={{ fontWeight: 400 }}>Query</th>
                    <th className="text-left pb-2 w-[13%]" style={{ fontWeight: 400 }}>Asset</th>
                    <th className="text-left pb-2 w-[15%]" style={{ fontWeight: 400 }}>Mode</th>
                    <th className="text-left pb-2 w-[10%]" style={{ fontWeight: 400 }}>Risk</th>
                    <th className="text-left pb-2 w-[12%]" style={{ fontWeight: 400 }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr
                      key={r.id}
                      onClick={() => setSelectedIdx(i)}
                      onDoubleClick={() => onOpenDetail?.(r.id)}
                      className={`border-b border-slate-50 cursor-pointer transition-colors ${selectedIdx === i ? "bg-blue-50" : "hover:bg-slate-50"}`}
                    >
                      <td className="py-3 pr-4 text-slate-800 truncate">{r.query}</td>
                      <td className="py-3 pr-4 truncate"><AssetBadge asset={r.asset} /></td>
                      <td className="py-3 pr-4 text-slate-500 truncate">{r.mode}</td>
                      <td className="py-3 pr-4 truncate"><RiskBadge risk={r.risk} /></td>
                      <td className="py-3 text-slate-400 truncate" title={r.error || r.updated}>{r.status}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-xs text-slate-400">
                        {reports.length === 0 ? "No reports loaded." : "No reports match the selected filter."}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Selected report panel */}
        <div className="w-full lg:w-64 space-y-4 shrink-0">
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex items-center gap-2 mb-2">
              <FileText size={14} className="text-slate-400 shrink-0" />
              <div className="text-xs text-slate-400 truncate">Selected Report</div>
            </div>
            <h3 className="text-base mb-1 truncate" style={{ fontWeight: 600 }}>
              {selected ? `${selected.asset} 4h Market Scan` : "No report selected"}
            </h3>
            <p className="text-xs text-slate-500 mb-4 line-clamp-3">
              {selected?.error || (selected ? `Open this ${selected.asset} run to inspect its status, markdown, and trace.` : "Generate a report to inspect its details here.")}
            </p>
            <div className="text-xs text-slate-400 mb-1">Risk score</div>
            <div className="text-2xl mb-2" style={{ fontWeight: 700 }}>7 / 12</div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
              <div className="h-full bg-orange-400 rounded-full" style={{ width: "58%" }} />
            </div>
            <button
              onClick={() => selected && onOpenDetail?.(selected.id)}
              disabled={!selected}
              className="w-full text-sm bg-blue-600 text-white rounded-lg py-2 hover:bg-blue-700 transition-colors"
              style={{ fontWeight: 500 }}
            >
              Open dashboard
            </button>
            <div className="grid grid-cols-2 gap-2 mt-2">
              <button className="text-xs border border-slate-200 text-slate-700 rounded-lg py-1.5 hover:bg-slate-50">
                View markdown
              </button>
              <button className="text-xs border border-slate-200 text-slate-700 rounded-lg py-1.5 hover:bg-slate-50">
                View trace
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h4 className="text-sm mb-3" style={{ fontWeight: 600 }}>Quick Stats</h4>
            <div className="space-y-2 text-xs">
              {[
                { label: "Completed reports", value: String(completedCount) },
                { label: "Failed reports", value: String(failedCount) },
                { label: "BTC share", value: "62%" },
                { label: "Avg generation", value: "38s" },
              ].map((s) => (
                <div key={s.label} className="flex items-center justify-between">
                  <span className="text-slate-500">{s.label}</span>
                  <span style={{ fontWeight: 600 }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
