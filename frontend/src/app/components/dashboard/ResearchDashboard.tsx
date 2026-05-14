import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Clock3,
  Database,
  FileText,
  LineChart,
  Loader2,
  Newspaper,
  Radar,
  RefreshCw,
  ShieldAlert,
  WalletCards,
} from 'lucide-react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { MarkdownRenderer } from '../MarkdownRenderer';
import { Alert, AlertDescription, AlertTitle } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { Skeleton } from '../ui/skeleton';
import type {
  AssetSelection,
  AttributionData,
  DerivativesData,
  MarketData,
  NewsData,
  NewsEvent,
  NormalizedSignal,
  OnchainData,
  ResearchReport,
  RiskData,
  TimeWindow,
} from './types';
import {
  badgeClasses,
  clampPercent,
  formatCurrency,
  formatDateTime,
  formatLabel,
  formatNumber,
  formatPercent,
  getLayerData,
} from './utils';

interface ResearchDashboardProps {
  report: ResearchReport | null;
  asset: AssetSelection;
  timeWindow: TimeWindow;
  queryDraft: string;
  isLoading: boolean;
  processingQuery: string | null;
  errorMessage: string | null;
  onAssetChange: (value: AssetSelection) => void;
  onTimeWindowChange: (value: TimeWindow) => void;
  onQueryChange: (value: string) => void;
  onGenerate: () => void;
  onExampleSelect: (query: string) => void;
}

const panelClass = 'rounded-md border border-[#dededb] bg-white shadow-[0_1px_2px_rgba(20,23,26,0.03)]';
const mutedLabelClass = 'text-xs font-semibold uppercase tracking-[0.08em] text-[#858a90]';

const examples = [
  'Analyze why BTC dropped today',
  'What caused the recent ETH gas spike?',
  'Analyze BTC options put-call ratio',
];

export function ResearchDashboard({
  report,
  asset,
  timeWindow,
  queryDraft,
  isLoading,
  processingQuery,
  errorMessage,
  onAssetChange,
  onTimeWindowChange,
  onQueryChange,
  onGenerate,
  onExampleSelect,
}: ResearchDashboardProps) {
  const market = getLayerData(report?.dashboardData, 'market') as unknown as MarketData;
  const risk = getLayerData(report?.dashboardData, 'risk') as unknown as RiskData;
  const attribution = getLayerData(report?.dashboardData, 'attribution') as unknown as AttributionData;
  const derivatives = getLayerData(report?.dashboardData, 'derivatives') as unknown as DerivativesData;
  const news = getLayerData(report?.dashboardData, 'news') as unknown as NewsData;
  const onchain = getLayerData(report?.dashboardData, 'onchain') as unknown as OnchainData;
  const signals = report?.dashboardData?.normalized_signals || [];
  const completedReport = report && report.metadata?.status === 'completed';
  const hasReport = Boolean(report);

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      <TopBar
        asset={asset}
        timeWindow={timeWindow}
        queryDraft={queryDraft}
        isLoading={isLoading}
        onAssetChange={onAssetChange}
        onTimeWindowChange={onTimeWindowChange}
        onQueryChange={onQueryChange}
        onGenerate={onGenerate}
      />

      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-4 px-5 py-5">
          <DisclaimerStrip />

          {errorMessage && (
            <Alert variant="destructive" className="border-[#f2c5b4] bg-[#fff8f5] text-[#9f3f1c]">
              <AlertTriangle className="size-4" />
              <AlertTitle>Backend request failed</AlertTitle>
              <AlertDescription>{errorMessage}</AlertDescription>
            </Alert>
          )}

          {isLoading ? (
            <DashboardSkeleton query={processingQuery || queryDraft} asset={asset} timeWindow={timeWindow} />
          ) : report ? (
            <>
              <ReportSummaryHeader report={report} />

              {report.error && !completedReport ? (
                <Alert variant="destructive" className="border-[#f2c5b4] bg-white text-[#9f3f1c]">
                  <AlertTriangle className="size-4" />
                  <AlertTitle>Report generation failed</AlertTitle>
                  <AlertDescription>{report.error}</AlertDescription>
                </Alert>
              ) : (
                <div className="grid grid-cols-12 gap-4">
                  <section className="col-span-12">
                    <MarketSnapshotCards market={market} />
                  </section>

                  <section className="col-span-12 xl:col-span-4">
                    <RiskScorePanel risk={risk} report={report} />
                  </section>
                  <section className="col-span-12 xl:col-span-8">
                    <AttributionPanel attribution={attribution} />
                  </section>

                  <section className="col-span-12 2xl:col-span-7">
                    <SignalMatrix signals={signals} />
                  </section>
                  <section className="col-span-12 lg:col-span-6 2xl:col-span-5">
                    <DerivativesPanel derivatives={derivatives} />
                  </section>

                  <section className="col-span-12 lg:col-span-6">
                    <NewsDriversPanel news={news} />
                  </section>
                  <section className="col-span-12 lg:col-span-6">
                    <OnchainPanel onchain={onchain} />
                  </section>

                  <section className="col-span-12">
                    <MarkdownReportPanel markdown={report.reportMarkdown} />
                  </section>
                </div>
              )}
            </>
          ) : (
            <EmptyDashboard
              queryDraft={queryDraft}
              onQueryChange={onQueryChange}
              onGenerate={onGenerate}
              onExampleSelect={onExampleSelect}
            />
          )}
        </div>
      </div>
    </main>
  );
}

function TopBar({
  asset,
  timeWindow,
  queryDraft,
  isLoading,
  onAssetChange,
  onTimeWindowChange,
  onQueryChange,
  onGenerate,
}: Pick<
  ResearchDashboardProps,
  | 'asset'
  | 'timeWindow'
  | 'queryDraft'
  | 'isLoading'
  | 'onAssetChange'
  | 'onTimeWindowChange'
  | 'onQueryChange'
  | 'onGenerate'
>) {
  return (
    <header className="border-b border-[#dededb] bg-[#fbfbfa]">
      <div className="mx-auto flex h-[76px] max-w-[1480px] items-center gap-4 px-5">
        <div className="mr-auto min-w-[220px]">
          <h1 className="text-xl font-semibold leading-none text-[#111417]">Crypto Research Agent</h1>
          <p className="mt-1 text-xs text-[#73787f]">Research command center</p>
        </div>

        <div className="hidden min-w-0 flex-1 items-center md:flex">
          <input
            value={queryDraft}
            onChange={event => onQueryChange(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter') {
                onGenerate();
              }
            }}
            className="h-10 w-full rounded-md border border-[#d8d8d4] bg-white px-3 text-sm text-[#1f2328] outline-none transition-colors placeholder:text-[#969ba0] focus:border-[#aeb2b5]"
            placeholder="Analyze why BTC dropped today..."
          />
        </div>

        <Select value={asset} onValueChange={value => onAssetChange(value as AssetSelection)}>
          <SelectTrigger className="h-10 w-[112px] border-[#d8d8d4] bg-white">
            <SelectValue placeholder="Asset" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="AUTO">Auto</SelectItem>
            <SelectItem value="BTC">BTC</SelectItem>
            <SelectItem value="ETH">ETH</SelectItem>
          </SelectContent>
        </Select>

        <Select value={timeWindow} onValueChange={value => onTimeWindowChange(value as TimeWindow)}>
          <SelectTrigger className="h-10 w-[96px] border-[#d8d8d4] bg-white">
            <SelectValue placeholder="Window" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="4h">4h</SelectItem>
            <SelectItem value="24h">24h</SelectItem>
            <SelectItem value="7d">7d</SelectItem>
          </SelectContent>
        </Select>

        <Button
          onClick={onGenerate}
          disabled={!queryDraft.trim() || isLoading}
          className="h-10 rounded-md bg-[#14171a] px-4 text-white hover:bg-[#2c3034]"
        >
          {isLoading ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
          Generate Report
        </Button>
      </div>
      <div className="border-t border-[#eeeeeb] px-5 py-3 md:hidden">
        <input
          value={queryDraft}
          onChange={event => onQueryChange(event.target.value)}
          className="h-10 w-full rounded-md border border-[#d8d8d4] bg-white px-3 text-sm outline-none focus:border-[#aeb2b5]"
          placeholder="Research question..."
        />
      </div>
    </header>
  );
}

function DisclaimerStrip() {
  return (
    <div className="flex items-center gap-2 rounded-md border border-[#e0e0dc] bg-[#fffffd] px-3 py-2 text-xs text-[#636970]">
      <ShieldAlert className="size-4 text-[#73787f]" />
      <span>
        Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, or
        hold any asset.
      </span>
    </div>
  );
}

function EmptyDashboard({
  queryDraft,
  onQueryChange,
  onGenerate,
  onExampleSelect,
}: Pick<ResearchDashboardProps, 'queryDraft' | 'onQueryChange' | 'onGenerate' | 'onExampleSelect'>) {
  return (
    <div className="grid grid-cols-12 gap-4">
      <section className={`${panelClass} col-span-12 p-5 lg:col-span-7`}>
        <div className={mutedLabelClass}>New Research</div>
        <h2 className="mt-3 text-2xl font-semibold text-[#14171a]">Build a two-asset research dashboard.</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#666c73]">
          Enter a BTC or ETH question, then generate a report. The completed view will combine market, derivatives,
          news, on-chain, attribution, and the original markdown report.
        </p>
        <textarea
          value={queryDraft}
          onChange={event => onQueryChange(event.target.value)}
          className="mt-5 min-h-[110px] w-full resize-none rounded-md border border-[#d8d8d4] bg-[#fbfbfa] p-3 text-sm leading-6 outline-none focus:border-[#aeb2b5]"
          placeholder="Analyze why BTC dropped today..."
        />
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={onGenerate} className="bg-[#14171a] text-white hover:bg-[#2c3034]">
            Generate Report
            <ArrowRight className="size-4" />
          </Button>
          {examples.map(example => (
            <button
              key={example}
              onClick={() => onExampleSelect(example)}
              className="rounded-md border border-[#dededb] bg-white px-3 py-2 text-xs font-semibold text-[#4f555b] hover:border-[#bfc2c1]"
            >
              {example}
            </button>
          ))}
        </div>
      </section>

      <section className={`${panelClass} col-span-12 p-5 lg:col-span-5`}>
        <div className="flex items-center justify-between">
          <div>
            <div className={mutedLabelClass}>Dashboard Scope</div>
            <h3 className="mt-2 text-lg font-semibold text-[#14171a]">BTC / ETH research only</h3>
          </div>
          <Database className="size-5 text-[#767b81]" />
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3">
          {['Market snapshot', 'Risk score', 'Attribution', 'Signal matrix', 'Derivatives', 'On-chain'].map(item => (
            <div key={item} className="rounded-md border border-[#e3e3df] bg-[#fbfbfa] px-3 py-3 text-sm text-[#4f555b]">
              {item}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function DashboardSkeleton({ query, asset, timeWindow }: { query: string; asset: AssetSelection; timeWindow: TimeWindow }) {
  return (
    <div className="space-y-4">
      <section className={`${panelClass} p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className={mutedLabelClass}>Processing Research</div>
            <h2 className="mt-2 text-xl font-semibold text-[#14171a]">{query}</h2>
            <div className="mt-3 flex gap-2">
              <Badge variant="outline" className="border-[#d8d8d4] capitalize text-[#5f656b]">{asset.toLowerCase()}</Badge>
              <Badge variant="outline" className="border-[#d8d8d4] text-[#5f656b]">{timeWindow}</Badge>
            </div>
          </div>
          <div className="flex items-center gap-2 text-sm font-semibold text-[#565c62]">
            <Loader2 className="size-4 animate-spin" />
            Collecting source data
          </div>
        </div>
      </section>
      <div className="grid grid-cols-12 gap-4">
        {[1, 2, 3, 4].map(item => (
          <Skeleton key={item} className="col-span-12 h-[118px] rounded-md bg-[#e8e8e4] md:col-span-3" />
        ))}
        <Skeleton className="col-span-12 h-[320px] rounded-md bg-[#e8e8e4] xl:col-span-4" />
        <Skeleton className="col-span-12 h-[320px] rounded-md bg-[#e8e8e4] xl:col-span-8" />
        <Skeleton className="col-span-12 h-[340px] rounded-md bg-[#e8e8e4]" />
      </div>
    </div>
  );
}

function ReportSummaryHeader({ report }: { report: ResearchReport }) {
  const metadata = report.metadata;

  return (
    <section className={`${panelClass} p-5`}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className={mutedLabelClass}>Report Summary</div>
          <h2 className="mt-2 max-w-4xl truncate text-2xl font-semibold text-[#14171a]">{report.query}</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge variant="outline" className="border-[#d8d8d4] bg-[#f7f7f4] text-[#4f555b]">
              Asset: {metadata?.asset || 'n/a'}
            </Badge>
            <Badge variant="outline" className="border-[#d8d8d4] bg-[#f7f7f4] text-[#4f555b]">
              Mode: {formatLabel(metadata?.mode)}
            </Badge>
            <Badge variant="outline" className="border-[#d8d8d4] bg-[#f7f7f4] text-[#4f555b]">
              Window: {metadata?.time_window || 'n/a'}
            </Badge>
            <Badge variant="outline" className={badgeClasses(metadata?.status)}>
              Status: {metadata?.status || 'local error'}
            </Badge>
          </div>
        </div>
        <div className="text-right text-sm text-[#62686f]">
          <div className="flex items-center justify-end gap-2 font-semibold text-[#2b3035]">
            <Clock3 className="size-4" />
            Updated
          </div>
          <div className="mt-1">{formatDateTime(metadata?.updated_at || report.createdAt)}</div>
        </div>
      </div>
    </section>
  );
}

function MarketSnapshotCards({ market }: { market: MarketData }) {
  const cards = [
    {
      label: 'Price Now',
      value: formatCurrency(market.price_now),
      helper: 'Spot reference',
      accent: 'text-[#14171a]',
    },
    {
      label: '24h Change',
      value: formatPercent(market.price_change_24h_pct),
      helper: 'Market move',
      accent: (market.price_change_24h_pct || 0) < 0 ? 'text-[#b64a22]' : 'text-emerald-700',
    },
    {
      label: 'Volume vs 7d',
      value: market.volume_ratio_vs_7d ? `${formatNumber(market.volume_ratio_vs_7d, { maximumFractionDigits: 2 })}x` : 'n/a',
      helper: 'Relative activity',
      accent: 'text-[#14171a]',
    },
    {
      label: 'Market Signal',
      value: formatLabel(market.market_signal),
      helper: 'Normalized layer signal',
      accent: 'text-[#14171a]',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map(card => (
        <div key={card.label} className={`${panelClass} p-4`}>
          <div className="flex items-center justify-between gap-3">
            <div className={mutedLabelClass}>{card.label}</div>
            <LineChart className="size-4 text-[#8a8f95]" />
          </div>
          <div className={`mt-4 truncate text-2xl font-semibold capitalize ${card.accent}`}>{card.value}</div>
          <div className="mt-2 text-xs text-[#777d83]">{card.helper}</div>
        </div>
      ))}
    </div>
  );
}

function RiskScorePanel({ risk, report }: { risk: RiskData; report: ResearchReport }) {
  const score = risk.risk_score ?? report.metadata?.risk_score ?? 0;
  const riskLevel = risk.risk_level || report.metadata?.risk_level || 'n/a';
  const breakdown = risk.risk_breakdown || {};
  const chartData = Object.entries(breakdown).map(([name, value]) => ({
    name: formatLabel(name).replace(' risk', ''),
    value,
  }));

  return (
    <div className={`${panelClass} h-full p-5`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className={mutedLabelClass}>Risk Score</div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-4xl font-semibold text-[#14171a]">{score}</span>
            <span className="text-sm text-[#747a80]">/ 12</span>
          </div>
        </div>
        <Badge variant="outline" className={`${badgeClasses(riskLevel)} capitalize`}>
          {formatLabel(riskLevel)}
        </Badge>
      </div>

      <div className="mt-5 h-2 overflow-hidden rounded-full bg-[#eeeeeb]">
        <div className="h-full rounded-full bg-[#c4572c]" style={{ width: `${clampPercent(score)}%` }} />
      </div>

      {chartData.length > 0 && (
        <div className="mt-6 h-[160px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="vertical" margin={{ top: 4, right: 12, bottom: 4, left: 10 }}>
              <CartesianGrid stroke="#eeeeeb" horizontal={false} />
              <XAxis type="number" domain={[0, 3]} hide />
              <YAxis dataKey="name" type="category" width={78} tick={{ fontSize: 12, fill: '#6b7178' }} />
              <Tooltip cursor={{ fill: '#f5f5f2' }} />
              <Bar dataKey="value" fill="#9fa4a8" radius={[0, 4, 4, 0]} barSize={14} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <p className="mt-4 text-sm leading-6 text-[#62686f]">{risk.risk_summary || 'No risk summary was returned.'}</p>
    </div>
  );
}

function AttributionPanel({ attribution }: { attribution: AttributionData }) {
  const primary = attribution.primary_drivers || [];
  const secondary = attribution.secondary_drivers || [];
  const topDriver = primary[0];

  return (
    <div className={`${panelClass} h-full p-5`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className={mutedLabelClass}>Attribution</div>
          <h3 className="mt-2 text-lg font-semibold text-[#14171a]">Primary and secondary drivers</h3>
        </div>
        <Badge variant="outline" className="border-[#d8d8d4] bg-[#f7f7f4] text-[#4f555b]">
          Confidence {formatNumber(topDriver?.confidence, { maximumFractionDigits: 2 })}
        </Badge>
      </div>

      <p className="mt-4 text-sm leading-6 text-[#62686f]">
        {attribution.event_summary || topDriver?.explanation || 'Attribution data was not returned for this report.'}
      </p>

      <div className="mt-5 grid gap-4 lg:grid-cols-2">
        <DriverList title="Primary Drivers" drivers={primary} />
        <DriverList title="Secondary Drivers" drivers={secondary} />
      </div>
    </div>
  );
}

function DriverList({ title, drivers }: { title: string; drivers: AttributionData['primary_drivers'] }) {
  return (
    <div className="rounded-md border border-[#e5e5e1] bg-[#fbfbfa] p-3">
      <div className="text-xs font-semibold uppercase tracking-[0.08em] text-[#858a90]">{title}</div>
      <div className="mt-3 space-y-3">
        {drivers && drivers.length > 0 ? (
          drivers.slice(0, 4).map((driver, index) => (
            <div key={`${driver.driver}-${index}`} className="border-t border-[#e9e9e5] pt-3 first:border-t-0 first:pt-0">
              <div className="flex items-start gap-2">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full border border-[#d8d8d4] text-[10px] font-semibold text-[#6b7178]">
                  {index + 1}
                </span>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-[#24282d]">{driver.driver || 'Unnamed driver'}</div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#666c73]">{driver.explanation || 'No explanation provided.'}</p>
                  {driver.evidence && driver.evidence.length > 0 && (
                    <div className="mt-2 text-xs text-[#777d83]">Evidence: {driver.evidence.slice(0, 2).join(' · ')}</div>
                  )}
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="text-sm text-[#777d83]">No driver with enough evidence.</div>
        )}
      </div>
    </div>
  );
}

function SignalMatrix({ signals }: { signals: NormalizedSignal[] }) {
  return (
    <div className={`${panelClass} h-full overflow-hidden`}>
      <div className="flex items-center justify-between border-b border-[#e8e8e4] px-5 py-4">
        <div>
          <div className={mutedLabelClass}>Signal Matrix</div>
          <h3 className="mt-1 text-lg font-semibold text-[#14171a]">Normalized multi-layer signals</h3>
        </div>
        <BarChart3 className="size-5 text-[#767b81]" />
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-[#fbfbfa] text-left text-xs uppercase tracking-[0.08em] text-[#858a90]">
            <tr>
              <th className="px-5 py-3 font-semibold">Layer</th>
              <th className="px-5 py-3 font-semibold">Signal</th>
              <th className="px-5 py-3 font-semibold">Value</th>
              <th className="px-5 py-3 font-semibold">Direction</th>
              <th className="px-5 py-3 font-semibold">Impact</th>
              <th className="px-5 py-3 font-semibold">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {signals.length > 0 ? (
              signals.map((signal, index) => (
                <tr key={`${signal.layer}-${signal.signal_name}-${index}`} className="border-t border-[#eeeeeb]">
                  <td className="px-5 py-3 font-semibold capitalize text-[#24282d]">{signal.layer}</td>
                  <td className="px-5 py-3 text-[#4f555b]">{signal.signal_name}</td>
                  <td className="max-w-[280px] truncate px-5 py-3 text-[#4f555b]">{signal.signal_value || 'n/a'}</td>
                  <td className="px-5 py-3">
                    <Badge variant="outline" className={`${badgeClasses(signal.direction)} capitalize`}>
                      {formatLabel(signal.direction)}
                    </Badge>
                  </td>
                  <td className="px-5 py-3 capitalize text-[#4f555b]">{formatLabel(signal.impact_level)}</td>
                  <td className="px-5 py-3 text-[#4f555b]">{formatNumber(signal.confidence, { maximumFractionDigits: 2 })}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={6} className="px-5 py-8 text-center text-[#777d83]">
                  No normalized signals returned.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DerivativesPanel({ derivatives }: { derivatives: DerivativesData }) {
  const rows = [
    ['Funding rate', formatPercent(derivatives.funding_rate_now, 4)],
    ['Open interest 24h', formatPercent(derivatives.open_interest_change_24h_pct)],
    ['Put/call ratio', formatNumber(derivatives.put_call_ratio, { maximumFractionDigits: 2 })],
    ['Liquidation bias', formatLabel(derivatives.liquidation_bias)],
  ];

  return (
    <div className={`${panelClass} h-full p-5`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={mutedLabelClass}>Derivatives</div>
          <h3 className="mt-1 text-lg font-semibold text-[#14171a]">Positioning pressure</h3>
        </div>
        <Radar className="size-5 text-[#767b81]" />
      </div>
      <div className="mt-4">
        <Badge variant="outline" className={`${badgeClasses(derivatives.derivatives_signal)} capitalize`}>
          {formatLabel(derivatives.derivatives_signal)}
        </Badge>
      </div>
      <div className="mt-5 divide-y divide-[#eeeeeb]">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-4 py-3">
            <span className="text-sm text-[#676d73]">{label}</span>
            <span className="text-sm font-semibold text-[#24282d]">{value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function NewsDriversPanel({ news }: { news: NewsData }) {
  const events = news.events || [];

  return (
    <div className={`${panelClass} h-full p-5`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={mutedLabelClass}>News Drivers</div>
          <h3 className="mt-1 text-lg font-semibold text-[#14171a]">Event context</h3>
        </div>
        <Newspaper className="size-5 text-[#767b81]" />
      </div>
      <div className="mt-5 space-y-3">
        {events.length > 0 ? (
          events.slice(0, 6).map((event, index) => <NewsEventRow key={`${event.title}-${index}`} event={event} />)
        ) : (
          <div className="rounded-md border border-dashed border-[#d8d8d4] bg-[#fbfbfa] px-3 py-6 text-center text-sm text-[#777d83]">
            No classified news events returned.
          </div>
        )}
      </div>
    </div>
  );
}

function NewsEventRow({ event }: { event: NewsEvent }) {
  return (
    <div className="rounded-md border border-[#e5e5e1] bg-[#fbfbfa] p-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline" className={`${badgeClasses(event.direction)} capitalize`}>
          {formatLabel(event.direction)}
        </Badge>
        <span className="text-xs capitalize text-[#777d83]">{formatLabel(event.impact_level)} impact</span>
        <span className="text-xs capitalize text-[#777d83]">{formatLabel(event.category)}</span>
        <span className="ml-auto text-xs text-[#777d83]">
          Conf. {formatNumber(event.confidence, { maximumFractionDigits: 2 })}
        </span>
      </div>
      <div className="mt-2 text-sm font-semibold leading-5 text-[#24282d]">{event.title || 'Untitled event'}</div>
    </div>
  );
}

function OnchainPanel({ onchain }: { onchain: OnchainData }) {
  const transfers = onchain.large_transfers || [];

  return (
    <div className={`${panelClass} h-full p-5`}>
      <div className="flex items-center justify-between">
        <div>
          <div className={mutedLabelClass}>On-chain</div>
          <h3 className="mt-1 text-lg font-semibold text-[#14171a]">Flow and transfer monitor</h3>
        </div>
        <WalletCards className="size-5 text-[#767b81]" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <div className="rounded-md border border-[#e5e5e1] bg-[#fbfbfa] p-3">
          <div className="text-xs text-[#777d83]">On-chain signal</div>
          <div className="mt-2 text-sm font-semibold capitalize text-[#24282d]">{formatLabel(onchain.onchain_signal)}</div>
        </div>
        <div className="rounded-md border border-[#e5e5e1] bg-[#fbfbfa] p-3">
          <div className="text-xs text-[#777d83]">Stablecoin supply 24h</div>
          <div className="mt-2 text-sm font-semibold text-[#24282d]">
            {formatNumber(onchain.stablecoin_supply_change_24h, { notation: 'compact', maximumFractionDigits: 2 })}
          </div>
        </div>
      </div>
      <div className="mt-5 space-y-2">
        {transfers.length > 0 ? (
          transfers.slice(0, 5).map((transfer, index) => (
            <div key={`${transfer.hash}-${index}`} className="rounded-md border border-[#e5e5e1] bg-[#fbfbfa] p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-semibold text-[#24282d]">
                    {transfer.from_label || 'Unknown'} to {transfer.to_label || 'Unknown'}
                  </div>
                  <div className="mt-1 truncate text-xs text-[#777d83]">{transfer.hash || transfer.timestamp || 'No hash'}</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-semibold text-[#24282d]">
                    {formatNumber(transfer.amount, { notation: 'compact', maximumFractionDigits: 2 })}
                  </div>
                  <div className="text-xs capitalize text-[#777d83]">{formatLabel(transfer.direction)}</div>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-md border border-dashed border-[#d8d8d4] bg-[#fbfbfa] px-3 py-6 text-center text-sm text-[#777d83]">
            No large transfers returned.
          </div>
        )}
      </div>
    </div>
  );
}

function MarkdownReportPanel({ markdown }: { markdown: string }) {
  return (
    <div className={`${panelClass} overflow-hidden`}>
      <div className="flex items-center justify-between border-b border-[#e8e8e4] px-5 py-4">
        <div>
          <div className={mutedLabelClass}>Markdown Report</div>
          <h3 className="mt-1 text-lg font-semibold text-[#14171a]">Original analyst report</h3>
        </div>
        <FileText className="size-5 text-[#767b81]" />
      </div>
      <div className="max-h-[680px] overflow-y-auto px-5 py-4">
        <MarkdownRenderer content={markdown} />
      </div>
    </div>
  );
}
