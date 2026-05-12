import { useEffect, useMemo, useState } from 'react';
import { ResearchDashboard } from './components/dashboard/ResearchDashboard';
import type { AssetSelection, MarketScanRecord, MarketScanResponse } from './components/dashboard/types';

const RESPONSE_BODY_PREVIEW_LENGTH = 500;
const ASSETS: AssetSelection[] = ['BTC', 'ETH'];

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

type HistoryMap = Record<AssetSelection, MarketScanRecord[]>;
type ScanMap = Partial<Record<AssetSelection, MarketScanRecord>>;

export default function App() {
  const [selectedAsset, setSelectedAsset] = useState<AssetSelection>('BTC');
  const [latestByAsset, setLatestByAsset] = useState<ScanMap>({});
  const [historyByAsset, setHistoryByAsset] = useState<HistoryMap>({ BTC: [], ETH: [] });
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedScan = useMemo(
    () => latestByAsset[selectedAsset] || historyByAsset[selectedAsset][0] || null,
    [historyByAsset, latestByAsset, selectedAsset],
  );

  const loadHistory = async () => {
    const baseUrl = getApiBaseUrl();
    const histories = await Promise.all(
      ASSETS.map(asset =>
        requestJson<MarketScanResponse>(
          `${baseUrl}/api/research/market-scans?asset=${asset}&limit=20`,
          `加载 ${asset} 历史记录失败`,
        ),
      ),
    );
    setHistoryByAsset({
      BTC: histories[0]?.results || [],
      ETH: histories[1]?.results || [],
    });
  };

  const runMarketScan = async (forceRefresh = false) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const baseUrl = getApiBaseUrl();
      const response = await requestJson<MarketScanResponse>(
        `${baseUrl}/api/research/market-scan`,
        '4小时市场判断失败',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ assets: ASSETS, force_refresh: forceRefresh }),
        },
      );
      const nextLatest: ScanMap = {};
      response.results.forEach(result => {
        nextLatest[result.asset] = result;
      });
      setLatestByAsset(nextLatest);
      setGeneratedAt(response.generated_at);
      await loadHistory();
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      setErrorMessage(detail);
      await loadHistory().catch(() => undefined);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    runMarketScan(false);
  }, []);

  return (
    <div className="app-shell">
      <ResearchDashboard
        selectedAsset={selectedAsset}
        scan={selectedScan}
        history={historyByAsset[selectedAsset]}
        generatedAt={generatedAt}
        isLoading={isLoading}
        errorMessage={errorMessage}
        onAssetChange={setSelectedAsset}
        onRefresh={() => runMarketScan(true)}
        onHistorySelect={scan => {
          setSelectedAsset(scan.asset);
          setLatestByAsset(prev => ({ ...prev, [scan.asset]: scan }));
        }}
      />
    </div>
  );
}
