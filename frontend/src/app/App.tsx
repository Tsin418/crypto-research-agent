import { useEffect, useMemo, useState } from 'react';
import { ResearchDashboard } from './components/dashboard/ResearchDashboard';
import type {
  AssetSelection,
  AutoScanReport,
  AutoScanResponse,
  DashboardData,
  ReportRecord,
} from './components/dashboard/types';

const RESPONSE_BODY_PREVIEW_LENGTH = 500;

function getApiBaseUrl() {
  const baseUrl = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '');

  if (import.meta.env.PROD && !baseUrl) {
    throw new Error('生产环境缺少 VITE_API_URL，请配置 FastAPI 后端地址。');
  }

  return baseUrl;
}

async function parseErrorResponse(res: Response, label: string) {
  const body = await res.text().catch(() => '');
  const bodyPreview = body ? ` ${body.slice(0, RESPONSE_BODY_PREVIEW_LENGTH)}` : '';
  return new Error(`${label}：HTTP ${res.status} ${res.statusText || ''}${bodyPreview}`);
}

async function requestJson<T>(url: string, label: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init).catch(error => {
    const message = error instanceof Error ? error.message : String(error);
    throw new Error(`${label}：网络或 CORS 请求失败。${message}`);
  });

  if (!res.ok) {
    throw await parseErrorResponse(res, label);
  }

  return res.json();
}

function historyToAutoReport(report: ReportRecord): AutoScanReport {
  return {
    report_id: report.report_id,
    asset: (report.asset || 'BTC') as AssetSelection,
    price_now: report.price_now,
    price_change_4h_pct: report.price_change_4h_pct,
    price_change_24h_pct: report.price_change_24h_pct,
    direction: report.direction,
    direction_label_zh: report.direction_label_zh,
    trigger_reason: report.trigger_reason,
    top_news: report.top_news_json || {
      title: report.top_news_title || '',
      url: report.top_news_url || '',
      source: report.top_news_source || '',
      reason_zh: '',
    },
    report_markdown: report.report_markdown || '',
    created_at: report.created_at,
    updated_at: report.updated_at,
  };
}

type HistoryMap = Record<AssetSelection, AutoScanReport[]>;
type ReportMap = Partial<Record<AssetSelection, AutoScanReport>>;

export default function App() {
  const [selectedAsset, setSelectedAsset] = useState<AssetSelection>('BTC');
  const [reportsByAsset, setReportsByAsset] = useState<ReportMap>({});
  const [historyByAsset, setHistoryByAsset] = useState<HistoryMap>({ BTC: [], ETH: [] });
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [cacheHit, setCacheHit] = useState<boolean | null>(null);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);

  const selectedReport = useMemo(
    () => reportsByAsset[selectedAsset] || historyByAsset[selectedAsset][0] || null,
    [historyByAsset, reportsByAsset, selectedAsset],
  );

  const loadHistory = async () => {
    const baseUrl = getApiBaseUrl();
    const [btc, eth] = await Promise.all(
      (['BTC', 'ETH'] as AssetSelection[]).map(asset =>
        requestJson<{ reports: ReportRecord[] }>(
          `${baseUrl}/api/research/reports?asset=${asset}&limit=20`,
          `加载 ${asset} 历史记录失败`,
        ),
      ),
    );
    setHistoryByAsset({
      BTC: btc.reports.map(historyToAutoReport),
      ETH: eth.reports.map(historyToAutoReport),
    });
  };

  const enrichReportData = async (report: AutoScanReport): Promise<AutoScanReport> => {
    const baseUrl = getApiBaseUrl();
    const dashboardData = await requestJson<DashboardData>(
      `${baseUrl}/api/research/report/${report.report_id}/data`,
      `加载 ${report.asset} 数据明细失败`,
    ).catch(() => undefined);
    return { ...report, dashboardData };
  };

  const runScan = async (forceRefresh = false) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await requestJson<AutoScanResponse>(`${baseUrl}/api/research/auto-scan`, '自动扫描失败', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          assets: ['BTC', 'ETH'],
          time_window: '4h',
          force_refresh: forceRefresh,
        }),
      });
      const enrichedReports = await Promise.all(response.reports.map(enrichReportData));
      const nextReports: ReportMap = {};
      enrichedReports.forEach(report => {
        nextReports[report.asset] = report;
      });
      setReportsByAsset(nextReports);
      setCacheHit(response.cache_hit);
      setGeneratedAt(response.generated_at);
      await loadHistory();
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setErrorMessage(detail);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    runScan(false);
  }, []);

  return (
    <div className="h-screen overflow-hidden bg-[#080b0f] text-[#e8edf2]">
      <ResearchDashboard
        selectedAsset={selectedAsset}
        report={selectedReport}
        history={historyByAsset[selectedAsset]}
        isLoading={isLoading}
        errorMessage={errorMessage}
        cacheHit={cacheHit}
        generatedAt={generatedAt}
        onAssetChange={setSelectedAsset}
        onRefresh={() => runScan(true)}
        onHistorySelect={(report) => {
          setSelectedAsset(report.asset);
          setReportsByAsset(prev => ({ ...prev, [report.asset]: report }));
          enrichReportData(report).then(enriched => {
            setReportsByAsset(prev => ({ ...prev, [enriched.asset]: enriched }));
          });
        }}
      />
    </div>
  );
}
