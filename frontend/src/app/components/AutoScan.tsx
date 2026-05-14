import { useState } from "react";
import { Sparkline } from "./Sparkline";
import { Play, Loader2 } from "lucide-react";

const btcData = [103200, 102800, 103100, 102600, 102100, 101900, 102430];
const ethData = [3400, 3390, 3410, 3415, 3420, 3418, 3420];

const scanLog = [
  { time: "14:28", msg: "BTC report completed", status: "ok" },
  { time: "14:27", msg: "Fetched derivatives data", status: "ok" },
  { time: "14:26", msg: "RSS classification partial", status: "warn" },
  { time: "14:25", msg: "CoinGecko market snapshot", status: "ok" },
  { time: "14:24", msg: "Auto scan started", status: "info" },
];

const autoReportRows = [
  { label: "Market", value: "Falling" },
  { label: "Funding Rate", value: "4h cumulative -0.012%" },
  { label: "Key Drivers", value: "Leverage flush + spot sell pressure" },
  { label: "Risk Level", value: "Elevated" },
];

const processSteps = [
  "Fetching market data",
  "Fetching derivatives",
  "Classifying news",
  "On-chain context",
  "Building attribution",
  "Generating report",
];

export function AutoScan({ onOpenDetail }: { onOpenDetail?: () => void } = {}) {
  const [assets, setAssets] = useState<{ BTC: boolean; ETH: boolean }>({ BTC: true, ETH: true });
  const [window, setWindow] = useState("4h");
  const [forceRefresh, setForceRefresh] = useState(false);
  const [running, setRunning] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  function handleRun() {
    setRunning(true);
    setActiveStep(0);
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setActiveStep(i);
      if (i >= processSteps.length) {
        clearInterval(id);
        setRunning(false);
      }
    }, 450);
  }

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Auto Scan</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Trigger or monitor automatic BTC / ETH market scans using backend cache, 4h thresholds, and auto-report generation.
        </p>
      </div>

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
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-lg" style={{ fontWeight: 600 }}>BTC</span>
            <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Falling</span>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl" style={{ fontWeight: 700 }}>$102,430</div>
              <div className="text-sm text-red-500 mt-1">4h change −1.82%</div>
              <div className="text-xs text-slate-400 mt-1">Exceeded −1.5% 4h downside threshold</div>
            </div>
            <Sparkline data={btcData} color="#EF4444" width={110} height={50} />
          </div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-lg" style={{ fontWeight: 600 }}>ETH</span>
            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Neutral</span>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl" style={{ fontWeight: 700 }}>$3,420</div>
              <div className="text-sm text-green-600 mt-1">4h change +0.42%</div>
              <div className="text-xs text-slate-400 mt-1">Move stayed inside threshold band</div>
            </div>
            <Sparkline data={ethData} color="#10B981" width={110} height={50} />
          </div>
        </div>
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
          <div className="text-base mb-3 truncate" style={{ fontWeight: 600 }}>BTC 4h Market Scan Report</div>
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
              onClick={() => onOpenDetail?.()}
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
