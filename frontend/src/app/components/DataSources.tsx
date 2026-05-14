import { Sparkline } from "./Sparkline";

const healthyData = [6, 7, 7, 6, 7, 7, 7];
const degradedData = [1, 2, 1, 2, 2, 2, 2];
const downData = [1, 0, 1, 1, 1, 1, 1];
const latencyData = [580, 610, 590, 640, 620, 650, 642];

const providers = [
  { name: "CoinGecko", status: "Healthy", success: 32, errors: 0, latency: "410ms" },
  { name: "Deribit", status: "Healthy", success: 18, errors: 0, latency: "530ms" },
  { name: "RSS News", status: "Partial", success: 14, errors: 3, latency: "980ms" },
  { name: "Alchemy", status: "Healthy", success: 22, errors: 0, latency: "300ms" },
  { name: "ETF Parser", status: "Degraded", success: 4, errors: 5, latency: "1.6s" },
  { name: "Macro Stooq", status: "Healthy", success: 9, errors: 0, latency: "720ms" },
];

const apiLogs = [
  { provider: "coingecko", endpoint: "/coins/markets", code: 200, latency: "412ms" },
  { provider: "rss", endpoint: "CoinDesk feed", code: 200, latency: "930ms" },
  { provider: "farside", endpoint: "ETF flow parse", code: 502, latency: "1.8s" },
  { provider: "deribit", endpoint: "put-call ratio", code: 200, latency: "540ms" },
  { provider: "alchemy", endpoint: "onchain events", code: 200, latency: "310ms" },
];

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "Healthy" ? "bg-green-100 text-green-700" :
    status === "Partial" ? "bg-yellow-100 text-yellow-700" :
    "bg-red-100 text-red-700";
  return <span className={`text-xs px-2 py-0.5 rounded ${cls}`}>{status}</span>;
}

export function DataSources() {
  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Data Sources</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Monitor provider health, latency, last success time, and API call quality behind every research report.
        </p>
      </div>

      {/* Responsive stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Healthy", value: "7", sub: "providers online", data: healthyData, color: "#10B981" },
          { label: "Degraded", value: "2", sub: "partial failures", data: degradedData, color: "#F59E0B" },
          { label: "Down", value: "1", sub: "needs fallback", data: downData, color: "#EF4444" },
          { label: "Avg Latency", value: "642ms", sub: "last 24h", data: latencyData, color: "#3B82F6" },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex items-start justify-between">
              <div className="min-w-0 flex-1">
                <div className="text-xs text-slate-500 mb-1 truncate">{s.label}</div>
                <div className="text-2xl" style={{ fontWeight: 700 }}>{s.value}</div>
                <div className="text-xs text-slate-400 mt-0.5">{s.sub}</div>
              </div>
              <Sparkline data={s.data} color={s.color} width={70} height={30} />
            </div>
          </div>
        ))}
      </div>

      <div className="flex flex-col lg:flex-row gap-4">
        {/* Provider health table */}
        <div className="flex-1 bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-base mb-4" style={{ fontWeight: 600 }}>Provider Health</h3>
          <div className="overflow-x-auto w-full">
            <table className="w-full text-xs min-w-[400px]">
              <thead>
                <tr className="text-slate-400 border-b border-slate-100">
                  {["Provider", "Status", "Success", "Errors", "Latency"].map((h) => (
                    <th key={h} className="text-left pb-2 pr-4 whitespace-nowrap" style={{ fontWeight: 400 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {providers.map((p) => (
                  <tr key={p.name} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
                    <td className="py-3 pr-4" style={{ fontWeight: 500 }}>{p.name}</td>
                    <td className="py-3 pr-4"><StatusBadge status={p.status} /></td>
                    <td className="py-3 pr-4 text-slate-600">{p.success}</td>
                    <td className="py-3 pr-4 text-slate-600">{p.errors}</td>
                    <td className="py-3 text-slate-500">{p.latency}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* API logs */}
        <div className="w-full lg:w-72 bg-white rounded-xl border border-slate-100 p-4">
          <h3 className="text-base mb-4" style={{ fontWeight: 600 }}>Recent API Logs</h3>
          <div className="space-y-3">
            {apiLogs.map((log, i) => (
              <div key={i} className="border border-slate-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1 min-w-0 gap-2">
                  <span className="text-xs truncate" style={{ fontWeight: 600 }}>{log.provider}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className={`text-xs ${log.code === 200 ? "text-green-600" : "text-red-600"}`} style={{ fontWeight: 600 }}>
                      {log.code}
                    </span>
                    <span className="text-xs text-slate-400">{log.latency}</span>
                  </div>
                </div>
                <div className="text-xs text-slate-400 truncate" title={log.endpoint}>{log.endpoint}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
