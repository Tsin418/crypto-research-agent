import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  Clock3,
  ExternalLink,
  History,
  Loader2,
  Newspaper,
  RefreshCw,
  ShieldAlert,
  Waves,
} from 'lucide-react';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Skeleton } from '../ui/skeleton';
import type { AssetSelection, AutoScanReport, DerivativesData, MarketData } from './types';
import { formatCurrency, formatDateTime, formatNumber, formatPercent, getLayerData } from './utils';

interface ResearchDashboardProps {
  selectedAsset: AssetSelection;
  report: AutoScanReport | null;
  history: AutoScanReport[];
  isLoading: boolean;
  errorMessage: string | null;
  cacheHit: boolean | null;
  generatedAt: string | null;
  onAssetChange: (asset: AssetSelection) => void;
  onRefresh: () => void;
  onHistorySelect: (report: AutoScanReport) => void;
}

const shellClass = 'border border-[#26323d] bg-[#10161d] shadow-[0_14px_40px_rgba(0,0,0,0.24)]';
const panelClass = `${shellClass} rounded-md`;
const mutedLabelClass = 'text-xs font-semibold text-[#8a96a3]';

function directionClasses(direction?: string | null) {
  if (direction === 'rising') {
    return {
      badge: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
      text: 'text-emerald-300',
      icon: ArrowUpRight,
    };
  }
  if (direction === 'falling') {
    return {
      badge: 'border-red-500/30 bg-red-500/10 text-red-300',
      text: 'text-red-300',
      icon: ArrowDownRight,
    };
  }
  return {
    badge: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
    text: 'text-amber-200',
    icon: Waves,
  };
}

function zhDirection(direction?: string | null, label?: string | null) {
  if (label) {
    return label;
  }
  if (direction === 'rising') {
    return '上涨';
  }
  if (direction === 'falling') {
    return '下跌';
  }
  return '震荡';
}

export function ResearchDashboard({
  selectedAsset,
  report,
  history,
  isLoading,
  errorMessage,
  cacheHit,
  generatedAt,
  onAssetChange,
  onRefresh,
  onHistorySelect,
}: ResearchDashboardProps) {
  const market = getLayerData(report?.dashboardData, 'market') as unknown as MarketData;
  const derivatives = getLayerData(report?.dashboardData, 'derivatives') as unknown as DerivativesData;
  const direction = directionClasses(report?.direction);
  const DirectionIcon = direction.icon;

  return (
    <main className="flex h-full min-w-0 flex-col">
      <header className="border-b border-[#1d2833] bg-[#0b1016]">
        <div className="mx-auto flex min-h-[82px] w-full max-w-[1480px] flex-wrap items-center gap-4 px-5 py-4">
          <div className="mr-auto min-w-[240px]">
            <div className="text-xl font-semibold text-[#f3f7fb]">BTC / ETH 中文研究台</div>
            <div className="mt-1 text-sm text-[#8895a3]">4小时自动扫描 · 本地历史记录</div>
          </div>

          <div className="flex rounded-md border border-[#26323d] bg-[#111821] p-1">
            {(['BTC', 'ETH'] as AssetSelection[]).map(asset => (
              <button
                key={asset}
                onClick={() => onAssetChange(asset)}
                className={`h-9 min-w-[76px] rounded px-4 text-sm font-semibold transition-colors ${
                  selectedAsset === asset
                    ? 'bg-[#e8edf2] text-[#10161d]'
                    : 'text-[#aeb9c5] hover:bg-[#1a2430] hover:text-white'
                }`}
              >
                {asset}
              </button>
            ))}
          </div>

          <Button
            onClick={onRefresh}
            disabled={isLoading}
            className="h-10 rounded-md bg-[#dce7f3] text-[#0b1016] hover:bg-white"
          >
            {isLoading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            刷新分析
          </Button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto grid w-full max-w-[1480px] grid-cols-12 gap-4 px-5 py-5">
          {errorMessage && (
            <Alert className="col-span-12 border-red-500/30 bg-red-500/10 text-red-100">
              <ShieldAlert className="size-4" />
              <AlertTitle>请求失败</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          <section className="col-span-12 xl:col-span-9">
            {isLoading && !report ? (
              <LoadingState />
            ) : report ? (
              <div className="space-y-4">
                <section className={`${panelClass} p-5`}>
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div>
                      <div className={mutedLabelClass}>市场概览</div>
                      <div className="mt-3 flex flex-wrap items-end gap-3">
                        <h1 className="text-4xl font-semibold text-white">{selectedAsset}</h1>
                        <Badge variant="outline" className={`${direction.badge} h-8 gap-1 rounded-md px-3 text-sm`}>
                          <DirectionIcon className="size-4" />
                          {zhDirection(report.direction, report.direction_label_zh)}
                        </Badge>
                      </div>
                      <p className="mt-3 max-w-3xl text-sm leading-6 text-[#a8b3bf]">
                        {report.trigger_reason || '当前数据不足以确认 4 小时方向。'}
                      </p>
                    </div>
                    <div className="text-right text-sm text-[#8d99a6]">
                      <div>{cacheHit ? '使用缓存报告' : '最新生成报告'}</div>
                      <div className="mt-1 text-[#d8e0e8]">{formatDateTime(generatedAt || report.updated_at)}</div>
                    </div>
                  </div>
                </section>

                <MetricGrid report={report} market={market} derivatives={derivatives} />
                <NewsPanel report={report} />
                <ReportPanel markdown={report.report_markdown || ''} />
              </div>
            ) : (
              <EmptyState />
            )}
          </section>

          <aside className="col-span-12 xl:col-span-3">
            <HistoryPanel
              selectedId={report?.report_id || null}
              selectedAsset={selectedAsset}
              history={history}
              onSelect={onHistorySelect}
            />
          </aside>
        </div>
      </div>
    </main>
  );
}

function MetricGrid({
  report,
  market,
  derivatives,
}: {
  report: AutoScanReport;
  market: MarketData;
  derivatives: DerivativesData;
}) {
  const metrics = [
    { label: '当前价格', value: formatCurrency(report.price_now ?? market.price_now), helper: '现货参考价格' },
    {
      label: '4小时变化',
      value: formatPercent(report.price_change_4h_pct),
      helper: '自动判断依据',
      accent: (report.price_change_4h_pct || 0) < 0 ? 'text-red-300' : 'text-emerald-300',
    },
    {
      label: '24小时变化',
      value: formatPercent(report.price_change_24h_pct ?? market.price_change_24h_pct),
      helper: '可用时显示',
      accent: ((report.price_change_24h_pct ?? market.price_change_24h_pct) || 0) < 0 ? 'text-red-300' : 'text-emerald-300',
    },
    {
      label: '成交量',
      value: formatNumber((market as Record<string, unknown>).volume_24h as number | undefined),
      helper: '24小时成交量',
    },
    {
      label: 'Funding Rate',
      value: formatPercent(derivatives.funding_rate_now, 4),
      helper: '永续资金费率',
    },
    {
      label: 'Open Interest',
      value: formatPercent(derivatives.open_interest_change_24h_pct),
      helper: '24小时变化',
    },
    {
      label: '多头清算',
      value: formatCurrency(derivatives.long_liquidations_24h),
      helper: '本地采集 24小时',
    },
    {
      label: '空头清算',
      value: formatCurrency(derivatives.short_liquidations_24h),
      helper: '本地采集 24小时',
    },
  ];

  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-4">
      {metrics.map(metric => (
        <div key={metric.label} className={`${panelClass} min-h-[118px] p-4`}>
          <div className="flex items-center justify-between gap-3">
            <div className={mutedLabelClass}>{metric.label}</div>
            <Activity className="size-4 text-[#667381]" />
          </div>
          <div className={`mt-4 truncate text-2xl font-semibold ${metric.accent || 'text-[#f3f7fb]'}`}>
            {metric.value}
          </div>
          <div className="mt-2 text-xs text-[#7f8b98]">{metric.helper}</div>
        </div>
      ))}
    </section>
  );
}

function NewsPanel({ report }: { report: AutoScanReport }) {
  const news = report.top_news || {};
  return (
    <section className={`${panelClass} p-5`}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <div className={mutedLabelClass}>核心新闻</div>
          <h2 className="mt-1 text-lg font-semibold text-white">去重后的单条重点事件</h2>
        </div>
        <Newspaper className="size-5 text-[#7c8996]" />
      </div>
      {news.title ? (
        <div className="rounded-md border border-[#283644] bg-[#0c1219] p-4">
          {news.url ? (
            <a
              href={news.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-start gap-2 text-base font-semibold leading-6 text-[#dce7f3] hover:text-white"
            >
              <span>{news.title}</span>
              <ExternalLink className="mt-1 size-4 shrink-0" />
            </a>
          ) : (
            <div className="text-base font-semibold text-[#dce7f3]">{news.title}</div>
          )}
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Badge variant="outline" className="border-[#314152] bg-[#121b25] text-[#aab7c4]">
              {news.source || '来源不足'}
            </Badge>
            <Badge variant="outline" className="border-[#314152] bg-[#121b25] text-[#aab7c4]">
              {news.impact_level || 'low'}
            </Badge>
            <Badge variant="outline" className="border-[#314152] bg-[#121b25] text-[#aab7c4]">
              {news.direction || 'neutral'}
            </Badge>
          </div>
          <p className="mt-3 text-sm leading-6 text-[#9faab6]">{news.reason_zh || '当前数据不足以确认影响。'}</p>
        </div>
      ) : (
        <div className="rounded-md border border-dashed border-[#314152] px-4 py-8 text-sm text-[#8e9aa7]">
          暂未发现可确认的核心新闻。
        </div>
      )}
    </section>
  );
}

function ReportPanel({ markdown }: { markdown: string }) {
  return (
    <section className={`${panelClass} overflow-hidden`}>
      <div className="border-b border-[#26323d] px-5 py-4">
        <div className={mutedLabelClass}>研究报告</div>
      </div>
      <div className="bg-[#f7f9fb] p-5 text-[#18212b]">
        {markdown ? <MarkdownRenderer content={markdown} /> : <div className="text-sm text-[#5c6875]">报告内容为空。</div>}
      </div>
    </section>
  );
}

function HistoryPanel({
  selectedId,
  selectedAsset,
  history,
  onSelect,
}: {
  selectedId: string | null;
  selectedAsset: AssetSelection;
  history: AutoScanReport[];
  onSelect: (report: AutoScanReport) => void;
}) {
  return (
    <section className={`${panelClass} sticky top-5 max-h-[calc(100vh-120px)] overflow-hidden`}>
      <div className="flex items-center justify-between border-b border-[#26323d] px-4 py-4">
        <div>
          <div className={mutedLabelClass}>历史记录</div>
          <div className="mt-1 text-sm font-semibold text-white">{selectedAsset} 本地报告</div>
        </div>
        <History className="size-5 text-[#7c8996]" />
      </div>
      <div className="max-h-[calc(100vh-210px)] overflow-y-auto p-3">
        {history.length === 0 ? (
          <div className="rounded-md border border-dashed border-[#314152] px-3 py-8 text-sm leading-6 text-[#8e9aa7]">
            暂无历史报告。
          </div>
        ) : (
          <div className="space-y-2">
            {history.map(item => (
              <button
                key={item.report_id}
                onClick={() => onSelect(item)}
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  selectedId === item.report_id
                    ? 'border-[#dce7f3] bg-[#182330]'
                    : 'border-[#26323d] bg-[#0c1219] hover:border-[#405266]'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-[#edf3f8]">{item.asset}</span>
                  <span className="text-xs text-[#8793a0]">{formatDateTime(item.updated_at || item.created_at)}</span>
                </div>
                <div className="mt-2 flex items-center gap-2 text-xs">
                  <span className={directionClasses(item.direction).text}>
                    {zhDirection(item.direction, item.direction_label_zh)}
                  </span>
                  <span className="text-[#71808f]">{formatPercent(item.price_change_4h_pct)}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <div className="space-y-4">
      <section className={`${panelClass} p-5`}>
        <div className="flex items-center gap-3 text-[#dce7f3]">
          <Loader2 className="size-5 animate-spin" />
          <span className="font-semibold">正在扫描 BTC / ETH 过去 4 小时市场变化...</span>
        </div>
      </section>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-4">
        {[1, 2, 3, 4, 5, 6, 7, 8].map(item => (
          <Skeleton key={item} className="h-[118px] rounded-md bg-[#182330]" />
        ))}
      </div>
      <Skeleton className="h-[280px] rounded-md bg-[#182330]" />
    </div>
  );
}

function EmptyState() {
  return (
    <section className={`${panelClass} p-8`}>
      <div className="flex items-center gap-3 text-[#dce7f3]">
        <Clock3 className="size-5" />
        <span className="font-semibold">等待自动扫描结果。</span>
      </div>
    </section>
  );
}
