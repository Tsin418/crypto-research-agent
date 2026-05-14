const candidates = [
  {
    driver: "Long leverage flush",
    layer: "derivatives",
    raw: 2.50,
    adjustments: "+ timing + cross-layer − missing liquidation data",
    final: 2.84,
    cls: "Primary",
    reason: "Score, timing alignment, cross-layer confirmation, and data-quality adjustment were evaluated. Funding rate inversion and open interest contraction strongly support primary classification.",
  },
  {
    driver: "Weak spot demand",
    layer: "market",
    raw: 1.90,
    adjustments: "+ volume confirmation",
    final: 2.12,
    cls: "Secondary",
    reason: "Score, timing alignment, cross-layer confirmation, and data-quality adjustment were evaluated. Spot CVD turned negative, confirming secondary driver status.",
  },
  {
    driver: "ETF flow drag",
    layer: "etf_flow",
    raw: 1.70,
    adjustments: "+ category prior − stale data",
    final: 1.78,
    cls: "Secondary",
    reason: "Score, timing alignment, cross-layer confirmation, and data-quality adjustment were evaluated. ETF outflows are supporting but slightly stale.",
  },
  {
    driver: "Macro risk-off pressure",
    layer: "macro",
    raw: 1.40,
    adjustments: "+ aligned with price move",
    final: 1.62,
    cls: "Context",
    reason: "Score, timing alignment, cross-layer confirmation, and data-quality adjustment were evaluated. Macro provides contextual support but not a direct causal driver.",
  },
  {
    driver: "Low-impact headline",
    layer: "news",
    raw: 0.60,
    adjustments: "− weak timing − low impact",
    final: 0.42,
    cls: "Noise",
    reason: "Score, timing alignment, cross-layer confirmation, and data-quality adjustment were evaluated. Headline lacks causal alignment; classified as noise.",
  },
];

const primaryCount = candidates.filter((c) => c.cls === "Primary").length;
const secondaryCount = candidates.filter((c) => c.cls === "Secondary").length;
const contextCount = candidates.filter((c) => c.cls === "Context").length;
const noiseCount = candidates.filter((c) => c.cls === "Noise").length;

function ClassBadge({ cls }: { cls: string }) {
  const map: Record<string, string> = {
    Primary: "bg-blue-100 text-blue-700",
    Secondary: "bg-orange-100 text-orange-700",
    Context: "bg-slate-100 text-slate-600",
    Noise: "bg-red-100 text-red-700",
  };
  return <span className={`text-xs px-2 py-0.5 rounded ${map[cls] ?? "bg-gray-100 text-gray-600"}`}>{cls}</span>;
}

export function AttributionTrace() {
  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Attribution Trace</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Audit why each candidate driver was classified as primary, secondary, context, or noise.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: "Primary Drivers", value: primaryCount, color: "bg-blue-50 border-blue-100", text: "text-blue-700" },
          { label: "Secondary Drivers", value: secondaryCount, color: "bg-orange-50 border-orange-100", text: "text-orange-700" },
          { label: "Context / Noise", value: contextCount + noiseCount, color: "bg-slate-50 border-slate-200", text: "text-slate-600" },
          { label: "Overall Data Quality", value: "0.71", color: "bg-yellow-50 border-yellow-100", text: "text-yellow-700" },
        ].map((s) => (
          <div key={s.label} className={`rounded-xl border p-4 ${s.color}`}>
            <div className="text-xs text-slate-500 mb-1">{s.label}</div>
            <div className={`text-2xl ${s.text}`} style={{ fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Context card */}
      <div className="bg-white rounded-xl border border-slate-100 p-5">
        <h3 className="text-base mb-1" style={{ fontWeight: 600 }}>BTC 4h decline — attribution trace</h3>
        <p className="text-xs text-slate-500">
          This view turns the report from a black-box summary into an explainable research decision trail. Each candidate driver was scored, adjusted, and classified.
        </p>
      </div>

      {/* Scoring table */}
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
              {candidates.map((c, i) => (
                <>
                  <tr key={`row-${i}`} className="border-b border-slate-50">
                    <td className="pt-4 pb-1 pr-6 text-slate-800 max-w-[140px] truncate" style={{ fontWeight: 500 }} title={c.driver}>{c.driver}</td>
                    <td className="pt-4 pb-1 pr-6 text-slate-500 whitespace-nowrap">{c.layer}</td>
                    <td className="pt-4 pb-1 pr-6" style={{ fontWeight: 600 }}>{c.raw.toFixed(2)}</td>
                    <td className="pt-4 pb-1 pr-6 text-slate-500 max-w-[180px] truncate" title={c.adjustments}>{c.adjustments}</td>
                    <td className="pt-4 pb-1 pr-6" style={{ fontWeight: 600 }}>{c.final.toFixed(2)}</td>
                    <td className="pt-4 pb-1"><ClassBadge cls={c.cls} /></td>
                  </tr>
                  <tr key={`reason-${i}`} className="border-b border-slate-100">
                    <td colSpan={6} className="pb-3 pr-6 text-slate-400 text-xs line-clamp-2">
                      {c.reason}
                    </td>
                  </tr>
                </>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
