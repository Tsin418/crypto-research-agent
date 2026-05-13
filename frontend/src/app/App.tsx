import { useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ResearchDashboard } from './components/dashboard/ResearchDashboard';
import type { AssetSelection, DashboardData, ReportRecord, ResearchReport, TimeWindow } from './components/dashboard/types';

const RESPONSE_BODY_PREVIEW_LENGTH = 500;
const MAX_POLL_RETRIES = 30;
const POLL_INTERVAL_MS = 2000;

function getApiBaseUrl() {
  const baseUrl = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '');

  if (import.meta.env.PROD && !baseUrl) {
    throw new Error(
      'Missing VITE_API_URL in production. Please set it to the public FastAPI backend URL.'
    );
  }

  return baseUrl;
}

async function parseErrorResponse(res: Response, label: string) {
  const body = await res.text().catch(() => '');
  const bodyPreview = body ? ` ${body.slice(0, RESPONSE_BODY_PREVIEW_LENGTH)}` : '';
  return new Error(`${label}: HTTP ${res.status} ${res.statusText || ''}${bodyPreview}`);
}

function formatFetchError(error: unknown, label: string, url: string) {
  const message = error instanceof Error ? error.message : String(error);
  return new Error(`${label}: network or CORS error while requesting ${url}. ${message}`);
}

async function requestJson<T>(url: string, label: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init).catch(error => {
    throw formatFetchError(error, label, url);
  });

  if (!res.ok) {
    throw await parseErrorResponse(res, label);
  }

  return res.json();
}

export default function App() {
  const [reports, setReports] = useState<ResearchReport[]>([]);
  const [currentReportId, setCurrentReportId] = useState<string | null>(null);
  const [asset, setAsset] = useState<AssetSelection>('AUTO');
  const [timeWindow, setTimeWindow] = useState<TimeWindow>('24h');
  const [queryDraft, setQueryDraft] = useState('Analyze why BTC dropped today');
  const [isLoading, setIsLoading] = useState(false);
  const [processingQuery, setProcessingQuery] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const currentReport = reports.find(report => report.id === currentReportId) || null;

  const handleNewResearch = () => {
    setCurrentReportId(null);
    setErrorMessage(null);
  };

  const handleSelectReport = (id: string) => {
    setCurrentReportId(id);
    setErrorMessage(null);
  };

  const handleSubmit = async (queryOverride?: string) => {
    const query = (queryOverride || queryDraft).trim();
    if (!query || isLoading) {
      return;
    }

    setIsLoading(true);
    setProcessingQuery(query);
    setErrorMessage(null);
    setCurrentReportId(null);

    try {
      const baseUrl = getApiBaseUrl();
      const reportEndpoint = `${baseUrl}/api/research/report`;
      const payload = {
        query,
        asset: asset === 'AUTO' ? undefined : asset,
        time_window: timeWindow,
      };

      const start = await requestJson<{ report_id: string }>(reportEndpoint, 'Failed to start report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      let reportData: ReportRecord | null = null;
      for (let retries = 0; retries < MAX_POLL_RETRIES; retries += 1) {
        await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS));
        const statusEndpoint = `${baseUrl}/api/research/report/${start.report_id}`;
        reportData = await requestJson<ReportRecord>(statusEndpoint, 'Failed to fetch report status');

        if (reportData.status === 'completed' || reportData.status === 'failed') {
          break;
        }
      }

      if (!reportData || reportData.status === 'processing') {
        throw new Error('Report generation timed out after 60 seconds. Please try again.');
      }

      let dashboardData: DashboardData | undefined;
      if (reportData.status === 'completed') {
        const dataEndpoint = `${baseUrl}/api/research/report/${start.report_id}/data`;
        dashboardData = await requestJson<DashboardData>(dataEndpoint, 'Failed to fetch dashboard data');
      }

      const report: ResearchReport = {
        id: start.report_id,
        query,
        createdAt: reportData.created_at || new Date().toISOString(),
        metadata: reportData,
        dashboardData,
        reportMarkdown:
          reportData.report_markdown ||
          (reportData.status === 'failed'
            ? `Report generation failed: ${reportData.error_message || 'Unknown error'}`
            : 'Report generated but no markdown was provided.'),
        error: reportData.status === 'failed' ? reportData.error_message || 'Report generation failed.' : undefined,
      };

      setReports(prev => [report, ...prev.filter(item => item.id !== report.id)]);
      setCurrentReportId(report.id);
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      const fallbackId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2);
      const failedReport: ResearchReport = {
        id: fallbackId,
        query,
        createdAt: new Date().toISOString(),
        reportMarkdown: `**Error:** Could not generate the research dashboard.\n\n${detail}`,
        error: detail,
      };

      console.error(error);
      setErrorMessage(detail);
      setReports(prev => [failedReport, ...prev]);
      setCurrentReportId(failedReport.id);
    } finally {
      setIsLoading(false);
      setProcessingQuery(null);
    }
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#f6f6f4] text-[#1f2328]">
      <Sidebar
        reports={reports}
        currentId={currentReportId}
        onNew={handleNewResearch}
        onSelect={handleSelectReport}
      />
      <ResearchDashboard
        report={currentReport}
        asset={asset}
        timeWindow={timeWindow}
        queryDraft={queryDraft}
        isLoading={isLoading}
        processingQuery={processingQuery}
        errorMessage={errorMessage}
        onAssetChange={setAsset}
        onTimeWindowChange={setTimeWindow}
        onQueryChange={setQueryDraft}
        onGenerate={() => handleSubmit()}
        onExampleSelect={(query) => {
          setQueryDraft(query);
          handleSubmit(query);
        }}
      />
    </div>
  );
}
