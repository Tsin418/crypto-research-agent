import { useState } from "react";
import { Sparkline } from "./Sparkline";
import { shortenHash } from "../../utils/labels";

const transferData = [38, 42, 40, 45, 41, 44, 42];
const largeData = [7, 9, 8, 10, 9, 8, 9];
const inflowData = [4, 3, 5, 3, 4, 3, 3];
const labelData = [55, 57, 56, 58, 57, 59, 58];

const events = [
  { time: "14:21", asset: "ETH", amount: "1,240", hash: "0x3fa1b29d4c2e8f0a7b3c1d5e6f9a2b4c8e0d1f2a", from: "unknown_wallet", to: "Binance deposit", direction: "exchange_inflow", source: "alchemy" },
  { time: "13:48", asset: "ETH", amount: "830", hash: "0x9c4d7e2f1a0b3c5d8e9f2a4b6c8d0e2f4a6b8c0d", from: "custody_wallet", to: "unknown_wallet", direction: "large_transfer", source: "alchemy" },
  { time: "12:55", asset: "ETH", amount: "2,900", hash: "0x71cc059a8b2c4d6e8f0a2b4c6d8e0f2a4b6c8d0e", from: "staking_wallet", to: "custody_wallet", direction: "internal/custody", source: "etherscan" },
  { time: "11:40", asset: "ETH", amount: "620", hash: "0x2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a8b0c", from: "unknown_wallet", to: "OKX deposit", direction: "exchange_inflow", source: "alchemy" },
  { time: "10:36", asset: "ETH", amount: "1,120", hash: "0x8f0a2b4c6d8e0f2a4b6c8d0e2f4a6b8c0d2e4f6a", from: "whale_wallet", to: "unknown_wallet", direction: "large_transfer", source: "alchemy" },
  { time: "09:20", asset: "ETH", amount: "710", hash: "0x4b6c8d0e2f4a6b8c0d2e4f6a8b0c2d4e6f8a0b2c", from: "Kraken hot wallet", to: "unknown_wallet", direction: "exchange_outflow", source: "alchemy" },
];

function DirectionBadge({ direction }: { direction: string }) {
  const cls =
    direction === "exchange_inflow" ? "bg-red-100 text-red-700" :
    direction === "exchange_outflow" ? "bg-green-100 text-green-700" :
    direction === "large_transfer" ? "bg-orange-100 text-orange-700" :
    "bg-slate-100 text-slate-600";
  const label = direction.replaceAll("_", " ");
  return <span className={`text-xs px-2 py-0.5 rounded whitespace-nowrap ${cls}`}>{label}</span>;
}

export function OnchainEvents() {
  const [filter, setFilter] = useState("ETH only");
  const [limit, setLimit] = useState("Limit 50");

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>On-chain Events</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Inspect Alchemy webhook and large-transfer events used by the report engine for on-chain evidence.
        </p>
      </div>

      {/* Responsive stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "ETH Transfers", value: "42", sub: "last 24h", data: transferData, color: "#3B82F6" },
          { label: "Large Transfers", value: "9", sub: "> 500 ETH", data: largeData, color: "#F59E0B" },
          { label: "Exchange Inflows", value: "3", sub: "limited pressure", data: inflowData, color: "#EF4444" },
          { label: "Label Coverage", value: "58%", sub: "wallet labels", data: labelData, color: "#10B981" },
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

      {/* Events table */}
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
              {events.map((e, i) => (
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50 transition-colors">
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
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
