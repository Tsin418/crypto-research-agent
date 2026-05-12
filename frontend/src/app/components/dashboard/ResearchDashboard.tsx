import ArrowDownRight from 'lucide-react/dist/esm/icons/arrow-down-right.js';
import ArrowUpRight from 'lucide-react/dist/esm/icons/arrow-up-right.js';
import Clock3 from 'lucide-react/dist/esm/icons/clock-3.js';
import History from 'lucide-react/dist/esm/icons/history.js';
import Loader2 from 'lucide-react/dist/esm/icons/loader-2.js';
import RefreshCw from 'lucide-react/dist/esm/icons/refresh-cw.js';
import ShieldAlert from 'lucide-react/dist/esm/icons/shield-alert.js';
import Waves from 'lucide-react/dist/esm/icons/waves.js';
import type { AssetSelection, MarketScanRecord } from './types';
import { formatCurrency, formatDateTime, formatPercent } from './utils';

interface ResearchDashboardProps {
  selectedAsset: AssetSelection;
  scan: MarketScanRecord | null;
  history: MarketScanRecord[];
  generatedAt: string | null;
  isLoading: boolean;
  errorMessage: string | null;
  onAssetChange: (asset: AssetSelection) => void;
  onRefresh: () => void;
  onHistorySelect: (scan: MarketScanRecord) => void;
}

function directionMeta(direction?: MarketScanRecord['direction']) {
  if (direction === 'rising') {
    return { tone: 'is-rising', icon: ArrowUpRight };
  }
  if (direction === 'falling') {
    return { tone: 'is-falling', icon: ArrowDownRight };
  }
  return { tone: 'is-neutral', icon: Waves };
}

export function ResearchDashboard({
  selectedAsset,
  scan,
  history,
  generatedAt,
  isLoading,
  errorMessage,
  onAssetChange,
  onRefresh,
  onHistorySelect,
}: ResearchDashboardProps) {
  const meta = directionMeta(scan?.direction);
  const DirectionIcon = meta.icon;

  return (
    <main className="market-dashboard">
      <header className="market-header">
        <div className="market-header-inner">
          <div className="market-title-block">
            <div className="market-title">BTC / ETH 4小时判断</div>
            <div className="market-subtitle">本地 SQLite 历史缓存</div>
          </div>

          <div className="asset-switcher" aria-label="选择币种">
            {(['BTC', 'ETH'] as AssetSelection[]).map(asset => (
              <button
                key={asset}
                type="button"
                onClick={() => onAssetChange(asset)}
                className={`asset-switcher-button ${selectedAsset === asset ? 'is-active' : ''}`}
              >
                {asset}
              </button>
            ))}
          </div>

          <button type="button" onClick={onRefresh} disabled={isLoading} className="refresh-button">
            {isLoading ? <Loader2 className="icon-sm is-spinning" /> : <RefreshCw className="icon-sm" />}
            刷新
          </button>
        </div>
      </header>

      <div className="market-body">
        <div className="market-grid">
          {errorMessage && (
            <div className="error-banner">
              <ShieldAlert className="icon-sm" />
              <div>
                <div className="error-title">请求失败</div>
                <div className="error-copy">{errorMessage}</div>
              </div>
            </div>
          )}

          <section className="market-main-column">
            {isLoading && !scan ? (
              <LoadingState />
            ) : scan ? (
              <>
                <section className="market-panel hero-panel">
                  <div>
                    <div className="muted-label">当前币种</div>
                    <div className="hero-row">
                      <h1>{selectedAsset}</h1>
                      <span className={`direction-badge ${meta.tone}`}>
                        <DirectionIcon className="icon-sm" />
                        {scan.direction_label_zh}
                      </span>
                    </div>
                  </div>
                  <div className="generated-at">
                    <div>生成时间</div>
                    <strong>{formatDateTime(generatedAt || scan.created_at)}</strong>
                  </div>
                </section>

                <section className="metric-grid">
                  <MetricBlock label="当前价格" value={formatCurrency(scan.price_now)} helper="USD 现货参考价格" />
                  <MetricBlock
                    label="4小时涨跌幅"
                    value={formatPercent(scan.price_change_4h_pct)}
                    helper="(当前价格 - 4小时前价格) / 4小时前价格"
                    tone={(scan.price_change_4h_pct || 0) < 0 ? 'is-falling' : 'is-rising'}
                  />
                  <MetricBlock label="判断结果" value={scan.direction_label_zh} helper={scan.direction} tone={meta.tone} />
                </section>
              </>
            ) : (
              <EmptyState />
            )}
          </section>

          <aside className="history-column">
            <HistoryPanel selectedAsset={selectedAsset} history={history} selectedScan={scan} onSelect={onHistorySelect} />
          </aside>
        </div>
      </div>
    </main>
  );
}

function MetricBlock({ label, value, helper, tone = '' }: { label: string; value: string; helper: string; tone?: string }) {
  return (
    <div className="market-panel metric-panel">
      <div className="muted-label">{label}</div>
      <div className={`metric-value ${tone}`}>{value}</div>
      <div className="metric-helper">{helper}</div>
    </div>
  );
}

function HistoryPanel({
  selectedAsset,
  history,
  selectedScan,
  onSelect,
}: {
  selectedAsset: AssetSelection;
  history: MarketScanRecord[];
  selectedScan: MarketScanRecord | null;
  onSelect: (scan: MarketScanRecord) => void;
}) {
  return (
    <section className="market-panel history-panel">
      <div className="history-header">
        <div>
          <div className="muted-label">历史记录</div>
          <div className="history-title">{selectedAsset} 最近 20 条</div>
        </div>
        <History className="icon-md" />
      </div>

      <div className="history-list">
        {history.length === 0 ? (
          <div className="empty-history">暂无历史记录。</div>
        ) : (
          history.map(item => {
            const meta = directionMeta(item.direction);
            const isSelected = selectedScan?.asset === item.asset && selectedScan?.created_at === item.created_at;
            return (
              <button
                key={`${item.asset}-${item.created_at}`}
                type="button"
                onClick={() => onSelect(item)}
                className={`history-item ${isSelected ? 'is-selected' : ''}`}
              >
                <div className="history-item-top">
                  <strong>{item.asset}</strong>
                  <span>{formatDateTime(item.created_at)}</span>
                </div>
                <div className="history-item-bottom">
                  <span className={meta.tone}>{item.direction_label_zh}</span>
                  <span>{formatPercent(item.price_change_4h_pct)}</span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <div className="loading-stack">
      <section className="market-panel loading-panel">
        <Loader2 className="icon-md is-spinning" />
        <span>正在获取 BTC / ETH 最近 4 小时价格变化...</span>
      </section>
      <section className="metric-grid">
        {[1, 2, 3].map(item => (
          <div key={item} className="metric-skeleton" />
        ))}
      </section>
    </div>
  );
}

function EmptyState() {
  return (
    <section className="market-panel empty-state">
      <Clock3 className="icon-md" />
      <span>等待 4 小时判断结果。</span>
    </section>
  );
}
