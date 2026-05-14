import { CheckCircle, XCircle, AlertCircle, Info } from "lucide-react";

interface SettingsProps {
  backendOnline?: boolean;
  apiBaseUrl?: string;
}

const VITE_WORKER_URL = "https://crypto-research-agent.workers.dev";
const DEFAULT_ASSET = "AUTO";
const DEFAULT_WINDOW = "4h";
const ENV_MODE = "production";
const REPORT_LIMIT = 20;
const SOURCE_HEALTH_LOOKBACK = 24;

function StatusIcon({ ok, warn }: { ok: boolean; warn?: boolean }) {
  if (ok) return <CheckCircle size={14} className="text-green-500 shrink-0" />;
  if (warn) return <AlertCircle size={14} className="text-yellow-500 shrink-0" />;
  return <XCircle size={14} className="text-red-500 shrink-0" />;
}

function ConfigRow({ label, value, note, ok, warn }: { label: string; value: string; note?: string; ok?: boolean; warn?: boolean }) {
  return (
    <div className="flex items-start justify-between py-3 border-b border-slate-50 last:border-0 gap-4">
      <div className="min-w-0">
        <div className="text-xs text-slate-500">{label}</div>
        {note && <div className="text-xs text-slate-400 mt-0.5">{note}</div>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {ok !== undefined && <StatusIcon ok={ok} warn={warn} />}
        <span className="text-xs text-slate-800 max-w-[220px] truncate text-right" style={{ fontWeight: 500 }} title={value}>
          {value}
        </span>
      </div>
    </div>
  );
}

export function Settings({ backendOnline = true, apiBaseUrl = "" }: SettingsProps = {}) {
  const workerConfigured = Boolean(VITE_WORKER_URL);
  const apiConfigured = Boolean(apiBaseUrl);

  return (
    <div className="p-6 space-y-5">
      <div>
        <h1 className="text-2xl" style={{ fontWeight: 600 }}>Settings</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Runtime configuration diagnostics. These values are read-only and reflect the current build environment.
        </p>
      </div>

      {/* Connection status cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Backend API",
            value: backendOnline ? "Connected" : "Disconnected",
            sub: backendOnline ? "GET /api/research/reports → 200" : "Backend request failed",
            color: backendOnline ? "bg-green-500" : "bg-red-500",
            text: backendOnline ? "text-green-700" : "text-red-700",
            bg: backendOnline ? "bg-green-50 border-green-100" : "bg-red-50 border-red-100",
          },
          {
            label: "Worker URL",
            value: workerConfigured ? "Configured" : "Missing",
            sub: workerConfigured ? "VITE_WORKER_URL set" : "On-chain events unavailable",
            color: workerConfigured ? "bg-green-500" : "bg-yellow-500",
            text: workerConfigured ? "text-green-700" : "text-yellow-700",
            bg: workerConfigured ? "bg-green-50 border-green-100" : "bg-yellow-50 border-yellow-100",
          },
          {
            label: "API Base URL",
            value: apiConfigured ? "Set" : "Proxy",
            sub: apiConfigured ? "Remote backend configured" : "Using local Vite proxy",
            color: apiConfigured ? "bg-green-500" : "bg-blue-500",
            text: apiConfigured ? "text-green-700" : "text-blue-700",
            bg: apiConfigured ? "bg-green-50 border-green-100" : "bg-blue-50 border-blue-100",
          },
          {
            label: "Environment",
            value: ENV_MODE,
            sub: "Build mode",
            color: "bg-blue-500",
            text: "text-blue-700",
            bg: "bg-blue-50 border-blue-100",
          },
        ].map((d) => (
          <div key={d.label} className={`rounded-xl border p-4 min-w-0 ${d.bg}`}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`w-2 h-2 rounded-full shrink-0 ${d.color}`} />
              <span className="text-xs text-slate-500 truncate">{d.label}</span>
            </div>
            <div className={`text-sm truncate ${d.text}`} style={{ fontWeight: 600 }} title={d.value}>{d.value}</div>
            <div className="text-xs text-slate-400 mt-0.5 truncate" title={d.sub}>{d.sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Runtime Configuration */}
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h3 className="text-base mb-1" style={{ fontWeight: 600 }}>Runtime Configuration</h3>
          <p className="text-xs text-slate-400 mb-4">Read from build-time environment variables. To change these, update your deployment environment and redeploy.</p>
          <div>
            <ConfigRow
              label="Backend API URL"
              value={apiBaseUrl || "Local proxy /api"}
              note="VITE_API_URL"
              ok={apiConfigured}
              warn={!apiConfigured}
            />
            <ConfigRow
              label="Worker URL"
              value={VITE_WORKER_URL || "Not configured"}
              note="VITE_WORKER_URL"
              ok={workerConfigured}
              warn={!workerConfigured}
            />
            <ConfigRow
              label="Environment Mode"
              value={ENV_MODE}
              note="NODE_ENV"
            />
          </div>
        </div>

        {/* Default Settings */}
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h3 className="text-base mb-1" style={{ fontWeight: 600 }}>Default Settings</h3>
          <p className="text-xs text-slate-400 mb-4">These are the application defaults. They do not persist across refreshes without backend configuration.</p>
          <div>
            <ConfigRow label="Default Asset" value={DEFAULT_ASSET} />
            <ConfigRow label="Default Time Window" value={DEFAULT_WINDOW} />
            <ConfigRow label="Report Limit" value={String(REPORT_LIMIT)} />
            <ConfigRow label="Source Health Lookback" value={`${SOURCE_HEALTH_LOOKBACK}h`} />
          </div>
        </div>

        {/* Frontend Feature Flags */}
        <div className="bg-white rounded-xl border border-slate-100 p-5">
          <h3 className="text-base mb-1" style={{ fontWeight: 600 }}>Active Features</h3>
          <p className="text-xs text-slate-400 mb-4">Features currently enabled in this build.</p>
          <div className="space-y-3">
            {[
              { label: "Load reports on startup", enabled: true },
              { label: "Show source health rail", enabled: true },
              { label: "Attribution trace", enabled: true },
              { label: "Human confirmation gate", enabled: true },
              { label: "Auto-refresh market scans", enabled: false },
            ].map((f) => (
              <div key={f.label} className="flex items-center justify-between py-1">
                <span className="text-xs text-slate-700">{f.label}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${f.enabled ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-500"}`}>
                  {f.enabled ? "Enabled" : "Disabled"}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Safety Notice */}
        <div className="bg-white rounded-xl border border-slate-100 p-5 flex flex-col gap-4">
          <div>
            <h3 className="text-base mb-2" style={{ fontWeight: 600 }}>Safety Boundary</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              This application is a <strong>research-only</strong> tool. It does not connect to any trading systems, execute orders, or provide financial advice. All output is for informational purposes only.
            </p>
          </div>
          <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 flex items-start gap-2">
            <Info size={13} className="text-blue-500 shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700 leading-relaxed">
              Settings in this panel are read-only diagnostics. They reflect the current deployment configuration and cannot be edited here. Update your <code className="bg-blue-100 px-1 rounded">VITE_*</code> environment variables and redeploy to change configuration.
            </p>
          </div>
          <div className="text-xs text-slate-400">
            Not financial advice · Not investment advice · No leverage recommendations
          </div>
        </div>
      </div>
    </div>
  );
}
