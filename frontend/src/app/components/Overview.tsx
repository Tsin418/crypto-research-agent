import { Sparkline } from "./Sparkline";
import { TrendingDown, TrendingUp, Minus } from "lucide-react";

const btcSparkData = [103200, 102800, 103100, 102600, 102100, 101900, 102430];
const ethSparkData = [3400, 3390, 3410, 3415, 3420, 3418, 3420];
const stableSparkData = [159, 158.5, 158.8, 158.2, 158.5, 158.3, 158.2];

const attributionDrivers = [
  { name: "Long leverage flush", category: "Derivatives", color: "bg-blue-100 text-blue-700", value: 2.84, pct: 72 },
  { name: "Weak spot demand", category: "Market", color: "bg-purple-100 text-purple-700", value: 2.12, pct: 54 },
  { name: "ETF flow drag", category: "ETF Flow", color: "bg-orange-100 text-orange-700", value: 1.78, pct: 45 },
  { name: "Macro risk-off", category: "Macro", color: "bg-gray-100 text-gray-600", value: 1.62, pct: 41 },
];

const signalMatrix = [
  { signal: "Funding rate", value: "-0.012%", status: "bearish" },
  { signal: "OI change", value: "-8.4%", status: "bearish" },
  { signal: "Spot CVD", value: "-$142M", status: "bearish" },
  { signal: "Put/call ratio", value: "1.31", status: "neutral" },
  { signal: "ETF flow", value: "-$180M", status: "bearish" },
  { signal: "Macro", value: "risk-off", status: "bearish" },
];

const newsItems = [
  { headline: "Macro risk-off pressures crypto majors", tag: "macro", tagColor: "bg-red-100 text-red-700" },
  { headline: "BTC derivatives flush aligns with spot weakness", tag: "derivatives", tagColor: "bg-blue-100 text-blue-700" },
  { headline: "ETF outflows continue for 3rd consecutive day", tag: "etf", tagColor: "bg-orange-100 text-orange-700" },
];

// ETH on-chain context — shown as cross-asset signal, not BTC on-chain
const ethOnchainItems = [
  { event: "Exchange inflow: 1,240 ETH → Binance", type: "bearish" },
  { event: "Whale move: 830 ETH custody → unknown", type: "neutral" },
  { event: "Exchange outflow: 710 ETH from Kraken", type: "bullish" },
];

const sourceHealth = [
  { name: "CoinGecko", status: "Healthy" },
  { name: "Deribit", status: "Healthy" },
  { name: "RSS News", status: "Partial" },
  { name: "Alchemy", status: "Healthy" },
  { name: "ETF Parser", status: "Degraded" },
  { name: "Macro Stooq", status: "Healthy" },
];

const topNews = [
  "ETF flow data negative for second consecutive week",
  "BTC leverage positions face continued liquidation risk",
  "No exchange delisting detected",
];

function StatusDot({ status }: { status: string }) {
  const color =
    status === "Healthy" ? "bg-green-500" :
    status === "Partial" ? "bg-yellow-500" :
    "bg-red-500";
  return <span className={`inline-block w-2 h-2 rounded-full ${color}`} />;
}

function SignalBadge({ status }: { status: string }) {
  const cls =
    status === "bearish" ? "bg-red-100 text-red-700" :
    status === "bullish" ? "bg-green-100 text-green-700" :
    "bg-gray-100 text-gray-600";
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${cls}`}>{status}</span>
  );
}

interface OverviewProps {
  queryDraft?: string;
  onQueryChange?: (q: string) => void;
  onGenerateReport?: () => void;
  onOpenDetail?: () => void;
}

export function Overview({ queryDraft = "", onQueryChange, onGenerateReport, onOpenDetail }: OverviewProps) {
  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Overview</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Live market attribution summary and research command center.
        </p>
      </div>

      {/* Price stats — responsive */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {[
          {
            label: "BTC", value: "$102,430", change: "-1.82%", trend: "down",
            sub: "4h change", data: btcSparkData, color: "#EF4444",
          },
          {
            label: "ETH", value: "$3,420", change: "+0.42%", trend: "up",
            sub: "4h change", data: ethSparkData, color: "#10B981",
          },
          {
            label: "Stablecoin Supply", value: "$158.2B", change: "-0.38%", trend: "down",
            sub: "24h change", data: stableSparkData, color: "#EF4444",
          },
        ].map((item) => (
          <div key={item.label} className="bg-white rounded-xl border border-slate-100 p-4 flex items-center justify-between min-w-0">
            <div className="min-w-0 flex-1">
              <div className="text-xs text-slate-500 mb-1 truncate">{item.label}</div>
              <div className="text-xl" style={{ fontWeight: 600 }}>{item.value}</div>
              <div className={`flex items-center gap-1 mt-1 text-xs ${item.trend === "up" ? "text-green-600" : "text-red-500"}`}>
                {item.trend === "up" ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                <span>{item.change} {item.sub}</span>
              </div>
            </div>
            <Sparkline data={item.data} color={item.color} width={90} height={36} />
          </div>
        ))}
      </div>

      {/* Research Question */}
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

      {/* Main layout — responsive */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left 2/3 */}
        <div className="lg:col-span-2 space-y-4">
          {/* Attribution */}
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
              <h3 className="text-base" style={{ fontWeight: 600 }}>BTC Attribution</h3>
              <div className="flex flex-wrap gap-1.5">
                <span className="text-xs bg-red-50 border border-red-100 text-red-700 px-2 py-0.5 rounded-full">Market Bias: Bearish</span>
                <span className="text-xs bg-orange-50 border border-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Risk: High</span>
                <span className="text-xs bg-blue-50 border border-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Confidence: 71%</span>
              </div>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-slate-700 truncate" style={{ fontWeight: 600 }}>Long leverage flush + weak spot demand</div>
              <p className="text-xs text-slate-500 line-clamp-3">
                BTC's decline is most consistent with long leverage flush, as the -1.82% 4h move correlates with high funding rate reversion and open interest contraction.
              </p>
              {attributionDrivers.map((d) => (
                <div key={d.name} className="flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1 gap-2">
                      <span className="text-xs text-slate-700 truncate">{d.name}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded whitespace-nowrap shrink-0 ${d.color}`}>{d.category}</span>
                    </div>
                    <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-blue-500 rounded-full" style={{ width: `${d.pct}%` }} />
                    </div>
                  </div>
                  <span className="text-xs text-slate-500 w-8 text-right shrink-0">{d.value}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Signal Matrix */}
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-base mb-3" style={{ fontWeight: 600 }}>Signal Matrix</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {signalMatrix.map((s) => (
                <div key={s.signal} className="flex items-center justify-between text-xs py-1.5 border-b border-slate-50">
                  <span className="text-slate-600">{s.signal}</span>
                  <div className="flex items-center gap-2">
                    <span style={{ fontWeight: 500 }}>{s.value}</span>
                    <SignalBadge status={s.status} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* News + On-chain row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm mb-2" style={{ fontWeight: 600 }}>BTC News Drivers</h4>
              <div className="space-y-2">
                {newsItems.map((n, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <Minus size={10} className="text-slate-400 mt-0.5 shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-slate-700 line-clamp-2">{n.headline}</div>
                      <span className={`text-xs px-1 py-0.5 rounded mt-0.5 inline-block ${n.tagColor}`}>{n.tag}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm mb-2" style={{ fontWeight: 600 }}>ETH On-chain Context</h4>
              <p className="text-xs text-slate-400 mb-2">Cross-asset reference — ETH exchange flows</p>
              <div className="space-y-2">
                {ethOnchainItems.map((o, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <div className={`w-2 h-2 rounded-full mt-1 shrink-0 ${o.type === "bearish" ? "bg-red-500" : o.type === "bullish" ? "bg-green-500" : "bg-yellow-400"}`} />
                    <span className="text-slate-600 line-clamp-2">{o.event}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right column: AI Brief + Source Health + Top News */}
        <div className="space-y-4">
          {/* AI Brief — separated badges */}
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-base" style={{ fontWeight: 600 }}>AI Brief</h3>
            </div>
            <div className="flex items-end gap-2 mb-1">
              <span className="text-4xl" style={{ fontWeight: 700 }}>7</span>
              <span className="text-slate-400 text-sm mb-1">/ 12</span>
            </div>
            <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-3">
              <div className="h-full bg-orange-400 rounded-full" style={{ width: "58%" }} />
            </div>
            {/* Separated badges */}
            <div className="flex flex-wrap gap-1.5 mb-3">
              <span className="text-xs bg-red-50 border border-red-100 text-red-700 px-2 py-0.5 rounded-full">Bearish</span>
              <span className="text-xs bg-orange-50 border border-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Risk: High</span>
              <span className="text-xs bg-blue-50 border border-blue-100 text-blue-700 px-2 py-0.5 rounded-full">Conf: Med</span>
            </div>
            <div className="text-sm text-slate-700 truncate" style={{ fontWeight: 500 }}>Long leverage flush</div>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed line-clamp-3">
              BTC -1.82% decline consistent with long leverage flush and weak spot demand confirmed by multiple layers.
            </p>
            <button
              onClick={() => onOpenDetail?.()}
              className="mt-3 w-full text-xs border border-blue-200 text-blue-600 rounded-lg py-1.5 hover:bg-blue-50 transition-colors"
            >
              View full report
            </button>
          </div>

          {/* Source Health */}
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-base mb-3 truncate" style={{ fontWeight: 600 }}>Source Health</h3>
            <div className="space-y-2">
              {sourceHealth.map((s) => (
                <div key={s.name} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2 min-w-0">
                    <StatusDot status={s.status} />
                    <span className="text-slate-700 truncate">{s.name}</span>
                  </div>
                  <span className={`px-1.5 py-0.5 rounded text-xs whitespace-nowrap shrink-0 ml-2 ${
                    s.status === "Healthy" ? "text-green-600" :
                    s.status === "Partial" ? "text-yellow-600" :
                    "text-red-600"
                  }`}>{s.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Top News */}
          <div className="bg-white rounded-xl border border-slate-100 p-4">
            <h3 className="text-sm mb-3 truncate" style={{ fontWeight: 600 }}>Top News</h3>
            <div className="space-y-2">
              {topNews.map((n, i) => (
                <div key={i} className="text-xs text-slate-600 flex items-start gap-2">
                  <span className="text-slate-400 shrink-0">—</span>
                  <span className="line-clamp-2">{n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
