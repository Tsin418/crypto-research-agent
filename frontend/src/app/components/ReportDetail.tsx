import { useState } from "react";
import { ArrowLeft, Copy, Download, ExternalLink, GitBranch, ChevronDown, ChevronUp } from "lucide-react";
import { labelForField, shortenHash } from "../../utils/labels";

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

// — Data —

const marketSnapshot: { label: string; value: string }[] = [
  { label: "price_now", value: "$102,430" },
  { label: "price_change_1h_pct", value: "-0.41%" },
  { label: "price_change_4h_pct", value: "-1.82%" },
  { label: "price_change_24h_pct", value: "-2.71%" },
  { label: "price_change_7d_pct", value: "-4.92%" },
  { label: "volume_24h", value: "$48.2B" },
  { label: "volume_ratio_vs_7d", value: "1.18x" },
  { label: "market_cap", value: "$2.02T" },
  { label: "market_signal", value: "bearish" },
  { label: "spot_turnover_24h", value: "$18.4B" },
  { label: "spot_flow_bias", value: "sell-heavy" },
  { label: "spot_cvd_approx_4h", value: "-$142M" },
  { label: "price_vs_ema20", value: "below" },
  { label: "price_vs_ema50", value: "below" },
  { label: "price_vs_ema200", value: "above" },
];

const riskBreakdown = [
  { label: "Derivatives", value: 3, max: 3 },
  { label: "Spot flow", value: 2, max: 3 },
  { label: "News / Macro", value: 1, max: 2 },
  { label: "On-chain", value: 1, max: 2 },
  { label: "ETF flow", value: 0, max: 2 },
];

const drivers = [
  {
    type: "Primary",
    color: "bg-blue-100 text-blue-700",
    driver: "Long leverage flush",
    explanation: "Funding rate inverted and OI dropped 8.4% during the 4h window, indicating forced long unwinding.",
    score: 2.84,
    confidence: 0.78,
    direction: "bearish",
    causality: "high",
  },
  {
    type: "Secondary",
    color: "bg-orange-100 text-orange-700",
    driver: "Weak spot demand",
    explanation: "Spot CVD turned negative; sell-side flow dominated centralized exchanges.",
    score: 2.12,
    confidence: 0.66,
    direction: "bearish",
    causality: "medium",
  },
  {
    type: "Noise",
    color: "bg-slate-100 text-slate-600",
    driver: "Stablecoin supply chatter",
    explanation: "USDT supply changed within normal range; no causal contribution detected.",
    score: 0.41,
    confidence: 0.32,
    direction: "neutral",
    causality: "low",
  },
];

const signals = [
  { layer: "derivatives", name: "Funding rate", value: "-0.012%", direction: "bearish", impact: "high", confidence: 0.81 },
  { layer: "derivatives", name: "Open interest", value: "-8.4%", direction: "bearish", impact: "high", confidence: 0.77 },
  { layer: "market", name: "Spot CVD 4h", value: "-$142M", direction: "bearish", impact: "high", confidence: 0.74 },
  { layer: "derivatives", name: "Put/call ratio", value: "1.31", direction: "bearish", impact: "medium", confidence: 0.62 },
  { layer: "etf_flow", name: "ETF net flow", value: "-$180M", direction: "bearish", impact: "medium", confidence: 0.70 },
  { layer: "macro", name: "DXY 4h", value: "+0.31%", direction: "bearish", impact: "low", confidence: 0.55 },
  { layer: "onchain", name: "Exchange inflow", value: "1,240 BTC", direction: "bearish", impact: "medium", confidence: 0.61 },
  { layer: "news", name: "Sentiment", value: "risk-off", direction: "bearish", impact: "medium", confidence: 0.58 },
];

const derivativesData = [
  { k: "provider", v: "Deribit" },
  { k: "symbol", v: "BTC-PERP" },
  { k: "funding_rate_now", v: "-0.012%" },
  { k: "funding_rate_8h_ago", v: "+0.008%" },
  { k: "funding_rate_change", v: "-0.020%" },
  { k: "open_interest_now", v: "$12.4B" },
  { k: "open_interest_change_24h_pct", v: "-8.4%" },
  { k: "mark_price", v: "$102,415" },
  { k: "basis_pct", v: "-0.04%" },
  { k: "put_call_ratio", v: "1.31" },
  { k: "liquidation_bias", v: "long-skewed" },
  { k: "long_liquidations_24h", v: "$142M" },
];

const newsEvents = [
  {
    title: "Macro risk-off pressures crypto majors",
    source: "Reuters",
    url: "#",
    direction: "bearish",
    impact: "high",
    category: "macro",
    confidence: 0.74,
    reason: "DXY strength + treasury yields breaking range.",
  },
  {
    title: "BTC derivatives flush aligned with spot weakness",
    source: "Coindesk",
    url: "#",
    direction: "bearish",
    impact: "medium",
    category: "derivatives",
    confidence: 0.68,
    reason: "Liquidation cascade reported across major venues.",
  },
  {
    title: "ETF outflows continue for 3rd consecutive day",
    source: "Bloomberg",
    url: "#",
    direction: "bearish",
    impact: "medium",
    category: "etf",
    confidence: 0.71,
    reason: "Net redemption from IBIT/FBTC.",
  },
];

const largeTransfers = [
  { hash: "0x3fa1b29d4c2e8f0a7b3c1d5e6f9a2b4c", amount: "1,240 BTC", from: "Coinbase Custody", to: "Binance", direction: "inflow", ts: "14:18" },
  { hash: "0x9c4d7e2f1a0b3c5d8e9f2a4b6c8d0e2f", amount: "830 BTC", from: "Unknown", to: "Kraken", direction: "inflow", ts: "13:42" },
  { hash: "0x71cc059a8b2c4d6e8f0a2b4c6d8e0f2a", amount: "710 BTC", from: "Kraken", to: "Cold wallet", direction: "outflow", ts: "12:55" },
];

const etfFlowData = [
  { k: "btc_etf_net_flow_usd_m", v: "-180.4" },
  { k: "flow_direction", v: "outflow" },
  { k: "etf_flow_signal", v: "bearish" },
  { k: "flow_intensity", v: "moderate" },
  { k: "is_stale", v: "false" },
  { k: "source", v: "Farside" },
];

const macroData = [
  { k: "macro_signal", v: "risk-off" },
  { k: "macro_confidence", v: "0.62" },
  { k: "macro_signal_evidence", v: "DXY +0.31%, US10Y +4bp, SPX -0.74%" },
  { k: "source", v: "FRED + Yahoo" },
];

const dataQuality = [
  { layer: "Market", status: "ok", source: "CoinGecko", quality: 0.94 },
  { layer: "Spot Flow", status: "ok", source: "Binance", quality: 0.88 },
  { layer: "Derivatives", status: "ok", source: "Deribit", quality: 0.91 },
  { layer: "News", status: "partial", source: "RSS aggregator", quality: 0.62 },
  { layer: "On-chain", status: "ok", source: "Alchemy", quality: 0.85 },
  { layer: "ETF Flow", status: "degraded", source: "ETF Parser", quality: 0.51 },
  { layer: "Macro", status: "ok", source: "FRED", quality: 0.79 },
];

const apiLogs = [
  { provider: "CoinGecko", endpoint: "/coins/markets", status: 200, latency: 412, created: "14:28:11" },
  { provider: "Deribit", endpoint: "/public/get_book_summary", status: 200, latency: 318, created: "14:28:09" },
  { provider: "RSS", endpoint: "/feed/crypto", status: 200, latency: 1842, created: "14:28:02" },
  { provider: "ETF Parser", endpoint: "/etf/flows", status: 502, latency: 5000, created: "14:27:58", error: "upstream timeout" },
  { provider: "Alchemy", endpoint: "/transfers", status: 200, latency: 287, created: "14:27:51" },
  { provider: "FRED", endpoint: "/series/observations", status: 200, latency: 612, created: "14:27:44" },
];

const reportMarkdown = `# BTC 4h Market Scan

## Summary
BTC declined **-1.82%** in the past 4 hours, driven primarily by *long leverage flush* and weak spot demand.

## Market Bias
- Direction: **Bearish**
- Risk Level: **High** (7 / 12)
- Model Confidence: **Medium** (71%)

## Key Drivers
- Funding rate inverted to **-0.012%**
- Open interest contracted **-8.4%**
- Spot CVD turned negative (**-$142M**)

## On-chain Context (BTC)
| Event | Amount | Direction |
|-------|--------|-----------|
| Exchange inflow | 1,240 BTC | bearish |
| Whale move | 830 BTC | neutral |

## Disclaimer
> Research-only output. Not financial advice.
`;

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
    s === "ok" ? "bg-green-100 text-green-700" :
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

function TabOverview({ asset, onSwitchTab, onOpenTrace }: { asset: string; onSwitchTab: (t: DetailTab) => void; onOpenTrace?: () => void }) {
  return (
    <div className="space-y-4">
      {/* Hero summary */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs bg-orange-100 text-orange-700 px-2.5 py-1 rounded-full" style={{ fontWeight: 600 }}>{asset}</span>
            <span className="text-xs text-slate-500">4h Window · rpt_8a2f</span>
            <span className="text-xs text-slate-400">Updated 14:28</span>
          </div>
          <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded-full">Partial Data</span>
        </div>

        {/* Price */}
        <div className="flex flex-wrap items-end gap-4 mb-4">
          <span className="text-4xl" style={{ fontWeight: 700 }}>$102,430</span>
          <div className="pb-0.5">
            <div className="text-sm text-red-500" style={{ fontWeight: 500 }}>▼ -1.82% (4h)</div>
            <div className="text-xs text-red-400">▼ -2.71% (24h)</div>
          </div>
        </div>

        {/* Separated badges */}
        <div className="flex flex-wrap gap-2 mb-4">
          <div className="flex items-center gap-1.5 bg-red-50 border border-red-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Market Bias</span>
            <span className="text-xs text-red-700" style={{ fontWeight: 600 }}>Bearish</span>
          </div>
          <div className="flex items-center gap-1.5 bg-orange-50 border border-orange-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Risk Level</span>
            <span className="text-xs text-orange-700" style={{ fontWeight: 600 }}>High · 7 / 12</span>
          </div>
          <div className="flex items-center gap-1.5 bg-blue-50 border border-blue-100 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Confidence</span>
            <span className="text-xs text-blue-700" style={{ fontWeight: 600 }}>Medium · 71%</span>
          </div>
          <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5">
            <span className="text-xs text-slate-500">Data Quality</span>
            <span className="text-xs text-slate-700" style={{ fontWeight: 600 }}>0.79 / Partial</span>
          </div>
        </div>

        {/* Main driver */}
        <div className="bg-slate-50 rounded-lg p-3 mb-4">
          <div className="text-xs text-slate-400 mb-0.5">Main Driver</div>
          <div className="text-sm text-slate-800" style={{ fontWeight: 600 }}>Long leverage flush + weak spot demand</div>
          <p className="text-xs text-slate-500 mt-1">
            Funding rate inverted and open interest contracted -8.4% during the 4h window, indicating forced long unwinding confirmed by spot CVD.
          </p>
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
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 text-xs">
          {marketSnapshot.map((m) => (
            <div key={m.label} className="bg-slate-50 rounded-lg p-3 min-w-0">
              <div className="text-slate-400 truncate">{labelForField(m.label)}</div>
              <div className="text-slate-800 mt-1 truncate" style={{ fontWeight: 600 }}>{m.value}</div>
            </div>
          ))}
        </div>
      </Card>

      {/* Risk + Attribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="Risk Score">
          <div className="flex items-end gap-2 mb-2">
            <span className="text-4xl" style={{ fontWeight: 700 }}>7</span>
            <span className="text-slate-400 text-sm mb-1">/ 12</span>
            <Pill label="elevated" color="bg-orange-100 text-orange-700" />
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mb-4">
            <div className="h-full bg-orange-400 rounded-full" style={{ width: "58%" }} />
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
          <p className="text-xs text-slate-500 mt-3 leading-relaxed line-clamp-3">
            Derivatives and spot flow are aligned. ETF drag confirms the move.
          </p>
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
            <div className="bg-blue-50 rounded-lg p-3 mb-3 text-xs text-blue-800">
              Long leverage flush + weak spot demand driving the {asset} 4h move.
            </div>
            <div className="space-y-3">
              {drivers.map((d) => (
                <div key={d.driver} className="border border-slate-100 rounded-lg p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2">
                      <Pill label={d.type} color={d.color} />
                      <span className="text-sm text-slate-800 truncate" style={{ fontWeight: 600 }}>{d.driver}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
                      <span>Score {d.score}</span>
                      <span>·</span>
                      <span>Conf {d.confidence}</span>
                      <span>·</span>
                      <DirBadge d={d.direction} />
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed line-clamp-2">{d.explanation}</p>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TabEvidence({ asset, signalLayer, setSignalLayer }: { asset: string; signalLayer: string; setSignalLayer: (l: string) => void }) {
  const filteredSignals = signalLayer === "all" ? signals : signals.filter((s) => s.layer === signalLayer);

  return (
    <div className="space-y-4">
      {/* Signal Matrix */}
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
        <p className="text-xs text-slate-500 mb-3">
          {asset} signals across all evidence layers. Bearish alignment is high across derivatives, market, and ETF data.
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
              {filteredSignals.map((s) => (
                <tr key={s.name} className="border-b border-slate-50">
                  <td className="py-2 text-slate-500 truncate pr-2">{s.layer}</td>
                  <td className="py-2 text-slate-800 truncate pr-2">{s.name}</td>
                  <td className="py-2 text-slate-700 truncate pr-2" style={{ fontWeight: 500 }}>{s.value}</td>
                  <td className="py-2 pr-2"><DirBadge d={s.direction} /></td>
                  <td className="py-2 pr-2"><ImpactBadge i={s.impact} /></td>
                  <td className="py-2 text-slate-500 truncate">{s.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Derivatives + News */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Derivatives">
          <p className="text-xs text-slate-500 mb-3">
            Long-side liquidation pressure elevated. Funding rate inverted; open interest contracted 8.4%.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <tbody>
                {derivativesData.map((d) => (
                  <tr key={d.k} className="border-b border-slate-50">
                    <td className="py-1.5 text-slate-400 pr-4 w-1/2">{labelForField(d.k)}</td>
                    <td className="py-1.5 text-slate-700" style={{ fontWeight: 500 }}>{d.v}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="News Drivers">
          <p className="text-xs text-slate-500 mb-3">
            Macro and derivatives narratives dominated. ETF outflow stories supported the bearish sentiment.
          </p>
          <div className="space-y-3">
            {newsEvents.map((n) => (
              <div key={n.title} className="border-b border-slate-50 pb-2 last:border-0 min-w-0">
                <a href={n.url} className="text-xs text-blue-600 hover:underline flex items-start gap-1">
                  <span className="line-clamp-2">{n.title}</span>
                  <ExternalLink size={10} className="mt-0.5 shrink-0" />
                </a>
                <div className="flex flex-wrap items-center gap-1.5 mt-1 text-xs">
                  <span className="text-slate-400 truncate max-w-[80px]">{n.source}</span>
                  <DirBadge d={n.direction} />
                  <ImpactBadge i={n.impact} />
                  <Pill label={n.category} />
                </div>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2">{n.reason}</p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* On-chain + ETF Flow */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="On-chain (BTC context)">
          <p className="text-xs text-slate-500 mb-3">
            Moderate exchange inflows detected. No extreme whale accumulation signal.
          </p>
          <div className="grid grid-cols-3 gap-2 text-xs mb-3">
            {[
              { k: "onchain_signal", v: "bearish" },
              { k: "large_transfer_count", v: "14" },
              { k: "stable_supply_24h", v: "+$240M" },
            ].map((item) => (
              <div key={item.k} className="bg-slate-50 rounded-lg p-2">
                <div className="text-slate-400 truncate">{labelForField(item.k)}</div>
                <div className="text-slate-800 mt-0.5 truncate" style={{ fontWeight: 600 }}>{item.v}</div>
              </div>
            ))}
          </div>
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
                {largeTransfers.map((t) => (
                  <tr key={t.hash} className="border-b border-slate-50">
                    <td className="py-1.5 pr-2">
                      <span className="text-slate-500 font-mono text-xs" title={t.hash}>{shortenHash(t.hash)}</span>
                    </td>
                    <td className="py-1.5 pr-2 text-slate-700 truncate" style={{ fontWeight: 500 }}>{t.amount}</td>
                    <td className="py-1.5 pr-2 text-slate-500 text-xs max-w-[100px] truncate" title={`${t.from} → ${t.to}`}>{t.from} → {t.to}</td>
                    <td className="py-1.5 pr-2"><DirBadge d={t.direction} /></td>
                    <td className="py-1.5 text-slate-400 whitespace-nowrap">{t.ts}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card title="ETF Flow">
            <p className="text-xs text-slate-500 mb-3">
              Net outflow of $180M over 24h. Signal is bearish; data from Farside slightly stale.
            </p>
            <div className="space-y-2 text-xs">
              {etfFlowData.map((e) => (
                <div key={e.k} className="flex justify-between border-b border-slate-50 py-1.5 gap-2">
                  <span className="text-slate-400">{labelForField(e.k)}</span>
                  <span className="text-slate-700 truncate text-right" style={{ fontWeight: 500 }}>{e.v}</span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Macro Context">
            <p className="text-xs text-slate-500 mb-3">
              Risk-off environment. DXY strengthened and US10Y rose, both consistent with the BTC decline.
            </p>
            <div className="space-y-2 text-xs">
              {macroData.map((m) => (
                <div key={m.k} className="border-b border-slate-50 pb-2 last:border-0">
                  <div className="text-slate-400">{labelForField(m.k)}</div>
                  <div className="text-slate-700 mt-0.5 line-clamp-2" style={{ fontWeight: 500 }}>{m.v}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TabDataQuality() {
  const overall = (dataQuality.reduce((a, q) => a + q.quality, 0) / dataQuality.length).toFixed(2);
  const okCount = dataQuality.filter((q) => q.status === "ok").length;

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Overall Score</div>
          <div className="text-2xl" style={{ fontWeight: 700 }}>{overall}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Healthy Layers</div>
          <div className="text-2xl text-green-600" style={{ fontWeight: 700 }}>{okCount} / {dataQuality.length}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-4">
          <div className="text-xs text-slate-500 mb-1">Status</div>
          <div className="text-sm text-yellow-700" style={{ fontWeight: 600 }}>Partial — ETF data degraded</div>
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
              {dataQuality.map((q) => (
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

function TabAPILogs({ logFilter, setLogFilter }: { logFilter: "all" | "errors"; setLogFilter: (f: "all" | "errors") => void }) {
  const filteredLogs = logFilter === "errors" ? apiLogs.filter((l) => l.status >= 400) : apiLogs;
  const errorCount = apiLogs.filter((l) => l.status >= 400).length;

  return (
    <div className="space-y-4">
      {/* Summary */}
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
          <div className="text-2xl" style={{ fontWeight: 700 }}>
            {Math.round(apiLogs.reduce((a, l) => a + l.latency, 0) / apiLogs.length)} ms
          </div>
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
              {filteredLogs.map((l, i) => (
                <tr key={i} className="border-b border-slate-50">
                  <td className="py-2 text-slate-700 truncate pr-2">{l.provider}</td>
                  <td className="py-2 text-slate-500 truncate pr-2" title={l.endpoint}>{l.endpoint}</td>
                  <td className="py-2 pr-2">
                    <Pill
                      label={String(l.status)}
                      color={l.status >= 400 ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700"}
                    />
                  </td>
                  <td className="py-2 text-slate-600 truncate pr-2">{l.latency} ms</td>
                  <td className="py-2 text-slate-400 truncate pr-2">{l.created}</td>
                  <td className="py-2 text-red-500 truncate" title={l.error ?? ""}>{l.error ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
        <pre className="text-xs text-slate-700 bg-slate-50 rounded-lg p-4 overflow-x-auto whitespace-pre-wrap" style={{ fontFamily: "ui-monospace, SFMono-Regular, monospace" }}>
          {markdown}
        </pre>
      </CollapsibleCard>
    </div>
  );
}

// — Main component —

export function ReportDetail({
  reportId = "rpt_8a2f",
  asset = "BTC",
  query,
  reportMarkdown: liveReportMarkdown,
  reportStatus,
  riskScore,
  riskLevel,
  updatedAt,
  errorMessage,
  onBack,
  onOpenTrace,
}: ReportDetailProps) {
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [signalLayer, setSignalLayer] = useState<string>("all");
  const [logFilter, setLogFilter] = useState<"all" | "errors">("all");
  const [copied, setCopied] = useState(false);
  const activeReportMarkdown = liveReportMarkdown || reportMarkdown;
  const updatedLabel = updatedAt ? new Date(updatedAt).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" }) : null;

  function handleCopy() {
    navigator.clipboard?.writeText(activeReportMarkdown).catch(() => {});
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
            <p className="text-sm text-slate-500 mt-0.5 line-clamp-2 max-w-xl">
              {query ?? `Analyze why ${asset} dropped in the past 4 hours across market, derivatives, news, on-chain and macro context.`}
            </p>
            <div className="flex flex-wrap gap-2 mt-2">
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{reportId}</span>
              {reportStatus && <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded">{reportStatus}</span>}
              {riskScore !== undefined && <span className="text-xs bg-orange-50 text-orange-700 px-2 py-0.5 rounded">Risk {riskScore}</span>}
              {riskLevel && <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded">{riskLevel}</span>}
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
          <div className="bg-red-50 border border-red-100 text-red-700 rounded-xl p-4 text-xs">
            {errorMessage}
          </div>
        )}
        {activeTab === "overview" && (
          <TabOverview asset={asset} onSwitchTab={setActiveTab} onOpenTrace={onOpenTrace} />
        )}
        {activeTab === "evidence" && (
          <TabEvidence asset={asset} signalLayer={signalLayer} setSignalLayer={setSignalLayer} />
        )}
        {activeTab === "dataquality" && <TabDataQuality />}
        {activeTab === "apilogs" && (
          <TabAPILogs logFilter={logFilter} setLogFilter={setLogFilter} />
        )}
        {activeTab === "markdown" && (
          <TabMarkdown copied={copied} markdown={activeReportMarkdown} onCopy={handleCopy} />
        )}

        <div className="text-xs text-slate-400 text-center pb-2">
          Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, hold, or use leverage.
        </div>
      </div>
    </div>
  );
}
