import { useEffect, useMemo, useState } from "react";
import {
  Search,
  ChevronDown,
  LayoutDashboard,
  FileText,
  RefreshCw,
  Link2,
  Database,
  GitBranch,
  Settings2,
  Play,
  Loader2,
} from "lucide-react";
import { Overview } from "./components/Overview";
import { Reports } from "./components/Reports";
import { AutoScan } from "./components/AutoScan";
import { OnchainEvents } from "./components/OnchainEvents";
import { DataSources } from "./components/DataSources";
import { AttributionTrace } from "./components/AttributionTrace";
import { Settings } from "./components/Settings";
import { ReportDetail } from "./components/ReportDetail";
import { DEFAULT_API_BASE_URL, getApiBaseUrl, requestJson } from "./api";

type Page = "overview" | "reports" | "autoscan" | "onchain" | "sources" | "trace" | "settings" | "detail";
type ParentPage = "overview" | "reports" | "autoscan";
type AssetSel = "AUTO" | "BTC" | "ETH";
type WindowSel = "4h" | "24h" | "7d";

interface ReportRecord {
  report_id: string;
  status: "processing" | "completed" | "failed";
  user_query: string;
  asset: string | null;
  mode: string | null;
  time_window: string | null;
  report_markdown: string | null;
  risk_score: number | null;
  risk_level: string | null;
  price_now?: number | null;
  price_change_4h_pct?: number | null;
  price_change_24h_pct?: number | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

interface DashboardData {
  report_id: string;
  snapshots: Record<string, unknown>;
  normalized_signals: unknown[];
  api_call_logs: unknown[];
}

interface ResearchReport {
  id: string;
  query: string;
  createdAt: string;
  metadata: ReportRecord;
  dashboardData?: DashboardData;
  reportMarkdown: string;
  error?: string;
}

const MAX_POLL_RETRIES = 30;
const POLL_INTERVAL_MS = 2000;

const navItems: { id: Exclude<Page, "detail">; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard size={14} /> },
  { id: "reports", label: "Reports", icon: <FileText size={14} /> },
  { id: "autoscan", label: "Auto Scan", icon: <RefreshCw size={14} /> },
  { id: "onchain", label: "On-chain", icon: <Link2 size={14} /> },
  { id: "sources", label: "Sources", icon: <Database size={14} /> },
  { id: "trace", label: "Trace", icon: <GitBranch size={14} /> },
  { id: "settings", label: "Settings", icon: <Settings2 size={14} /> },
];

function toResearchReport(record: ReportRecord, dashboardData?: DashboardData): ResearchReport {
  return {
    id: record.report_id,
    query: record.user_query,
    createdAt: record.created_at || new Date().toISOString(),
    metadata: record,
    dashboardData,
    reportMarkdown:
      record.report_markdown ||
      (record.status === "failed"
        ? `Report generation failed: ${record.error_message || "Unknown error"}`
        : "Report generated but no markdown was provided."),
    error: record.status === "failed" ? record.error_message || "Report generation failed." : undefined,
  };
}

function formatRecentTime(value?: string) {
  if (!value) return "Just now";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function DropdownPicker<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        className="flex items-center gap-1 text-xs border border-slate-200 rounded-lg px-3 py-2 bg-white hover:bg-slate-50 transition-colors"
        style={{ fontWeight: 500 }}
      >
        {value} <ChevronDown size={11} />
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-slate-200 rounded-lg shadow-sm py-1 min-w-[80px] z-20">
          {options.map((o) => (
            <button
              key={o}
              onMouseDown={() => {
                onChange(o);
                setOpen(false);
              }}
              className={`w-full text-left text-xs px-3 py-1.5 hover:bg-slate-50 ${value === o ? "text-blue-600" : "text-slate-700"}`}
              style={{ fontWeight: value === o ? 600 : 400 }}
            >
              {o}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [detailParentPage, setDetailParentPage] = useState<ParentPage>("overview");
  const [queryDraft, setQueryDraft] = useState(
    "Analyze why BTC dropped in the past 4 hours across market, derivatives, news, on-chain and macro context."
  );
  const [asset, setAsset] = useState<AssetSel>("AUTO");
  const [timeframe, setTimeframe] = useState<WindowSel>("4h");
  const [backendOnline, setBackendOnline] = useState(false);
  const [reports, setReports] = useState<ResearchReport[]>([]);
  const [currentReportId, setCurrentReportId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currentReport = useMemo(
    () => reports.find((report) => report.id === currentReportId) || null,
    [reports, currentReportId]
  );

  const recentReports = useMemo(
    () =>
      reports.slice(0, 3).map((report) => ({
        id: report.id,
        label: report.metadata.asset ? `${report.metadata.asset} ${report.metadata.time_window || "report"}` : "Research report",
        sub: `${report.metadata.risk_level || report.metadata.status} · ${formatRecentTime(report.metadata.updated_at)}`,
        color:
          report.metadata.status === "failed"
            ? "bg-red-500"
            : report.metadata.asset === "ETH"
              ? "bg-blue-500"
              : "bg-orange-500",
      })),
    [reports]
  );

  useEffect(() => {
    requestJson<{ reports: ReportRecord[] }>("/api/research/reports?limit=20", "Failed to load reports")
      .then((payload) => {
        setReports(payload.reports.map((record) => toResearchReport(record)));
        setBackendOnline(true);
      })
      .catch((error) => {
        setBackendOnline(false);
        console.warn(error);
      });
  }, []);

  function openReportDetail(parent: ParentPage, reportId?: string) {
    if (reportId) {
      setCurrentReportId(reportId);
      void loadReportDetail(reportId);
    }
    setDetailParentPage(parent);
    setPage("detail");
  }

  async function hydrateReport(record: ReportRecord) {
    let dashboardData: DashboardData | undefined;
    if (record.status === "completed") {
      dashboardData = await requestJson<DashboardData>(
        `/api/research/report/${record.report_id}/data`,
        "Failed to fetch dashboard data"
      );
    }

    const report = toResearchReport(record, dashboardData);
    setReports((prev) => [report, ...prev.filter((item) => item.id !== report.id)]);
    setCurrentReportId(report.id);
    return report;
  }

  async function loadReportDetail(reportId: string) {
    try {
      const record = await requestJson<ReportRecord>(`/api/research/report/${reportId}`, "Failed to load report");
      await hydrateReport(record);
      setBackendOnline(true);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setErrorMessage(detail);
      console.error(error);
    }
  }

  async function handleGenerateReport() {
    const query = queryDraft.trim();
    if (!query || isGenerating) return;

    setIsGenerating(true);
    setErrorMessage(null);

    try {
      const start = await requestJson<{ report_id: string }>("/api/research/report", "Failed to start report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          asset: asset === "AUTO" ? undefined : asset,
          time_window: timeframe,
        }),
      });

      let reportData: ReportRecord | null = null;
      for (let retries = 0; retries < MAX_POLL_RETRIES; retries += 1) {
        await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
        reportData = await requestJson<ReportRecord>(
          `/api/research/report/${start.report_id}`,
          "Failed to fetch report status"
        );

        if (reportData.status === "completed" || reportData.status === "failed") {
          break;
        }
      }

      if (!reportData || reportData.status === "processing") {
        throw new Error("Report generation timed out after 60 seconds. Please try again.");
      }

      await hydrateReport(reportData);
      openReportDetail("overview", reportData.report_id);
      setBackendOnline(true);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setErrorMessage(detail);
      setBackendOnline(false);
      console.error(error);
    } finally {
      setIsGenerating(false);
    }
  }

  const activePage: Exclude<Page, "detail"> = page === "detail" ? detailParentPage : (page as Exclude<Page, "detail">);

  const pageComponents: Record<Page, React.ReactNode> = {
    overview: (
      <Overview
        queryDraft={queryDraft}
        onQueryChange={setQueryDraft}
        onGenerateReport={handleGenerateReport}
        onOpenDetail={() => openReportDetail("overview", currentReportId || reports[0]?.id)}
      />
    ),
    reports: <Reports reports={reports.map((report) => report.metadata)} onOpenDetail={(id) => openReportDetail("reports", id)} />,
    autoscan: <AutoScan onOpenDetail={(reportId) => openReportDetail("autoscan", reportId || currentReportId || reports[0]?.id)} />,
    onchain: <OnchainEvents />,
    sources: <DataSources />,
    trace: <AttributionTrace reportId={currentReportId || reports[0]?.id} />,
    settings: <Settings backendOnline={backendOnline} apiBaseUrl={getApiBaseUrl() || DEFAULT_API_BASE_URL} />,
    detail: (
      <ReportDetail
        reportId={currentReport?.id}
        asset={(currentReport?.metadata.asset || (asset === "AUTO" ? "BTC" : asset)) as string}
        query={currentReport?.query || queryDraft}
        reportMarkdown={currentReport?.reportMarkdown}
        reportStatus={currentReport?.metadata.status}
        riskScore={currentReport?.metadata.risk_score ?? undefined}
        riskLevel={currentReport?.metadata.risk_level ?? undefined}
        updatedAt={currentReport?.metadata.updated_at}
        errorMessage={currentReport?.error || errorMessage || undefined}
        onBack={() => setPage(detailParentPage)}
        onOpenTrace={() => setPage("trace")}
      />
    ),
  };

  return (
    <div className="flex flex-col h-screen bg-slate-50 overflow-hidden" style={{ fontFamily: "Inter, system-ui, sans-serif" }}>
      <header className="h-14 bg-white border-b border-slate-100 flex items-center px-5 gap-4 shrink-0 z-10">
        <div className="text-base text-slate-900 shrink-0" style={{ fontWeight: 700, letterSpacing: "-0.01em" }}>
          Crypto Research
        </div>
        <span className="text-xs bg-slate-100 text-slate-600 px-2.5 py-1 rounded-full shrink-0 hidden sm:inline" style={{ fontWeight: 500 }}>
          Research-only
        </span>

        <div className="flex-1 relative max-w-xl">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className="w-full text-xs border border-slate-200 rounded-xl pl-8 pr-4 py-2 outline-none focus:border-blue-400 bg-slate-50"
            placeholder="Ask a research question (e.g., Why did BTC drop in the past 4h?)"
            value={queryDraft}
            onChange={(e) => setQueryDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleGenerateReport()}
          />
        </div>

        <DropdownPicker<AssetSel> value={asset} options={["AUTO", "BTC", "ETH"] as const} onChange={setAsset} />
        <DropdownPicker<WindowSel> value={timeframe} options={["4h", "24h", "7d"] as const} onChange={setTimeframe} />

        <button
          onClick={() => setPage("autoscan")}
          className="hidden sm:flex items-center gap-1.5 text-xs border border-blue-200 text-blue-600 rounded-lg px-3 py-2 hover:bg-blue-50 transition-colors"
          style={{ fontWeight: 500 }}
        >
          <Play size={11} /> Auto Scan
        </button>

        <button
          onClick={handleGenerateReport}
          disabled={isGenerating || !queryDraft.trim()}
          className="text-xs bg-blue-600 text-white rounded-lg px-4 py-2 hover:bg-blue-700 transition-colors disabled:opacity-50 shrink-0 min-w-[88px]"
          style={{ fontWeight: 500 }}
        >
          {isGenerating ? <Loader2 size={13} className="animate-spin mx-auto" /> : "Generate"}
        </button>

        <div className="flex items-center gap-1.5 text-xs text-slate-500 pl-2 border-l border-slate-100 shrink-0">
          <span className={`w-2 h-2 rounded-full ${backendOnline ? "bg-green-500" : "bg-red-500"}`} />
          <span className="hidden md:inline">{backendOnline ? "Backend" : "Offline"}</span>
        </div>
      </header>

      {errorMessage && (
        <div className="bg-red-50 border-b border-red-100 px-5 py-2 text-xs text-red-700">
          {errorMessage}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <aside className="w-52 bg-white border-r border-slate-100 flex flex-col shrink-0 overflow-y-auto">
          <div className="p-4 border-b border-slate-100">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm shrink-0" style={{ fontWeight: 700 }}>
                R
              </div>
              <div className="min-w-0">
                <div className="text-xs text-slate-800 truncate" style={{ fontWeight: 600 }}>Research Desk</div>
                <div className="text-xs text-slate-400 truncate">Institutional view</div>
              </div>
            </div>
          </div>

          <nav className="flex-1 p-3 space-y-0.5">
            {navItems.map((item) => {
              const active = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setPage(item.id)}
                  className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-colors text-left ${
                    active ? "bg-blue-600 text-white" : "text-slate-600 hover:bg-slate-50"
                  }`}
                  style={{ fontWeight: active ? 600 : 400 }}
                >
                  <span className={active ? "text-white" : "text-slate-400"}>{item.icon}</span>
                  {item.label}
                </button>
              );
            })}
          </nav>

          <div className="p-3 border-t border-slate-100">
            <div className="text-xs text-slate-400 px-2 mb-2" style={{ fontWeight: 600, letterSpacing: "0.05em" }}>
              RECENT REPORTS
            </div>
            <div className="space-y-1">
              {recentReports.length === 0 && <div className="px-2 py-2 text-xs text-slate-400">No reports loaded.</div>}
              {recentReports.map((report) => (
                <button
                  key={report.id}
                  onClick={() => openReportDetail("overview", report.id)}
                  className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-slate-50 transition-colors text-left"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${report.color}`} />
                  <div className="min-w-0">
                    <div className="text-xs text-slate-700 truncate" style={{ fontWeight: 500 }}>{report.label}</div>
                    <div className="text-xs text-slate-400 truncate">{report.sub}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="p-3 border-t border-slate-100">
            <div className="px-2 py-2 bg-slate-50 rounded-lg">
              <div className="text-xs text-slate-700 truncate" style={{ fontWeight: 600 }}>Safety Boundary</div>
              <div className="text-xs text-slate-400 mt-0.5">Research only. No trades.</div>
            </div>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto">{pageComponents[page]}</main>
      </div>
    </div>
  );
}
