# Crypto Research Agent Frontend Functional Requirements

> Purpose: This document lists the frontend functions that need to be implemented or verified after the backend changes.  
> Scope: Functional requirements only. Visual style, typography, colors, and UI design details are intentionally excluded.

---

## 1. Product Goal

The frontend should evolve from a single report-generation page into a complete crypto research dashboard.

The frontend must support:

1. Manual research report generation.
2. BTC / ETH auto scan.
3. BTC / ETH 4h market scan.
4. Historical report browsing.
5. Report detail dashboard.
6. Attribution trace inspection.
7. Data source health monitoring.
8. On-chain event inspection.
9. Markdown report rendering.
10. Clear loading, error, empty, failed, processing, and completed states.
11. Research-only safety boundary.

---

## 2. Global Layout Requirements

The frontend should include these main areas:

```text
TopBar
Left Sidebar
Main Content Area
Optional Right Insight Panel
```

### 2.1 TopBar

The TopBar should include:

```text
App name
Search / research question input
Asset selector: AUTO / BTC / ETH
Time window selector: 4h / 24h / 7d
Auto Scan button
Generate Report button
Backend connection status
```

### 2.2 Sidebar

The Sidebar should support actual page switching.

Required pages:

```text
Overview
Reports
Auto Scan
On-chain
Sources
Trace
Settings
```

The Sidebar should also display Recent Reports.

Each navigation item must be clickable and must update the main content area.

Do not keep static fake navigation items.

### 2.3 Right Insight Panel

The right-side panel is optional but recommended for report-related pages.

It should show:

```text
AI brief
Risk score
Main driver
Source health summary
Top news
Report actions
```

Possible report actions:

```text
Open full markdown
View attribution trace
Copy markdown
Export report
```

---

## 3. Environment Variables

The frontend should support:

```env
VITE_API_URL=<FastAPI backend URL>
VITE_WORKER_URL=<Cloudflare Worker URL, optional>
```

### 3.1 VITE_API_URL

Used for FastAPI research backend endpoints.

Required in production.

### 3.2 VITE_WORKER_URL

Used for Worker-only routes such as:

```text
/api/onchain/events
```

Optional for MVP, but required if the On-chain Events page reads directly from the Worker.

---

## 4. API Client Requirements

Create a centralized API client instead of scattering `fetch` calls across components.

Suggested file:

```text
src/api/research.ts
```

The API client should handle:

```text
Base URL composition
JSON request headers
HTTP error parsing
Network / CORS errors
Timeouts
Empty response handling
Typed response parsing
```

All request errors should return user-readable error messages.

---

## 5. Core Data Types

### 5.1 Asset Types

```ts
type Asset = 'BTC' | 'ETH';
type AssetSelection = 'AUTO' | 'BTC' | 'ETH';
```

### 5.2 Time Window Types

```ts
type TimeWindow = '4h' | '24h' | '7d';
```

Important: `4h` must be supported because the backend auto scan and market scan logic is centered on 4h movement.

### 5.3 StoredReport

```ts
interface StoredReport {
  report_id: string;
  status: 'processing' | 'completed' | 'failed';
  user_query: string;

  asset: string | null;
  mode: string | null;
  time_window: string | null;

  report_markdown: string | null;
  risk_score: number | null;
  risk_level: string | null;

  price_now: number | null;
  price_change_4h_pct: number | null;
  price_change_24h_pct: number | null;

  direction: string | null;
  direction_label_zh: string | null;
  trigger_reason: string | null;

  top_news_title: string | null;
  top_news_url: string | null;
  top_news_source: string | null;
  top_news_json: Record<string, unknown> | null;

  error_message: string | null;
  created_at: string;
  updated_at: string;
}
```

### 5.4 MarketScanRecord

```ts
interface MarketScanRecord {
  asset: 'BTC' | 'ETH';
  price_now: number | null;
  price_change_4h_pct: number | null;
  direction: 'rising' | 'falling' | 'neutral';
  direction_label_zh: '上涨' | '下跌' | '震荡';
  created_at: string;
}
```

### 5.5 ReportData

```ts
interface ReportData {
  report_id: string;
  snapshots: Record<string, SnapshotEnvelope>;
  normalized_signals: NormalizedSignal[];
  api_call_logs: ApiCallLog[];
}
```

### 5.6 SnapshotEnvelope

```ts
interface SnapshotEnvelope<T = Record<string, unknown>> {
  source?: string;
  created_at?: string;
  data?: T | { data?: T; errors?: string[] };
}
```

### 5.7 NormalizedSignal

```ts
interface NormalizedSignal {
  layer: string;
  signal_name: string;
  signal_value: string;
  direction: string;
  impact_level: string;
  confidence: number;
  created_at?: string;
}
```

### 5.8 ApiCallLog

```ts
interface ApiCallLog {
  provider?: string;
  endpoint?: string;
  status_code?: number | null;
  latency_ms?: number | null;
  error_message?: string | null;
  created_at?: string;
}
```

### 5.9 SourceHealth

```ts
interface SourceHealth {
  provider: string;
  success_count: number;
  error_count: number;
  avg_latency_ms: number;
  last_success_at: string | null;
  last_error_at: string | null;
  health_status: 'healthy' | 'degraded' | 'down' | string;
}
```

### 5.10 AttributionTraceResponse

```ts
interface AttributionTraceResponse {
  report_id: string;
  attribution_trace: AttributionTraceItem[];
  trace_summary: Record<string, unknown>;
  data_quality: Record<string, unknown>;
  alternative_explanations: AlternativeExplanation[];
}
```

### 5.11 AttributionTraceItem

```ts
interface AttributionTraceItem {
  candidate_id?: string;
  driver?: string;
  source_layer?: string;
  raw_score?: number;
  adjustments?: AttributionAdjustment[];
  final_score?: number;
  primary_eligible?: boolean;
  classification?: string;
  classification_reason?: string;
}
```

### 5.12 AttributionAdjustment

```ts
interface AttributionAdjustment {
  name: string;
  value: number;
  reason: string;
}
```

### 5.13 AlternativeExplanation

```ts
interface AlternativeExplanation {
  explanation?: string;
  supporting_evidence?: string[];
  why_not_primary?: string;
}
```

---

## 6. API Methods To Implement

### 6.1 Health Check

```http
GET /health
```

Use this to check whether the FastAPI backend is online.

Expected usage:

```text
Show backend connected / disconnected status
Show backend status in Settings
Block report generation if backend is unavailable
```

---

### 6.2 Create Manual Research Report

```http
POST /api/research/report
```

Request:

```ts
{
  query: string;
  asset?: 'BTC' | 'ETH';
  time_window?: string;
}
```

Response:

```ts
{
  report_id: string;
  status: 'processing' | 'completed';
  refused?: boolean;
}
```

Frontend behavior:

1. User enters a research question.
2. User selects asset and time window.
3. Frontend sends the request.
4. If response status is `processing`, begin polling.
5. If response status is `completed`, fetch report detail directly.
6. If `refused` is true, display the refusal markdown as a completed research-only safety response.

---

### 6.3 Poll Report Status

```http
GET /api/research/report/{report_id}
```

Response: `StoredReport`

Frontend behavior:

1. Poll until status becomes `completed` or `failed`.
2. Do not permanently mark the report as failed only because of a short timeout.
3. If frontend polling times out, show a recoverable state:
   ```text
   Report is still processing. You can retry fetching status.
   ```
4. Once completed, fetch report data.

---

### 6.4 Fetch Report Data

```http
GET /api/research/report/{report_id}/data
```

Response:

```ts
{
  report_id: string;
  snapshots: Record<string, SnapshotEnvelope>;
  normalized_signals: NormalizedSignal[];
  api_call_logs: ApiCallLog[];
}
```

Used for:

```text
Market cards
Risk panel
Attribution panel
Signal matrix
Derivatives panel
News panel
On-chain panel
ETF panel
Macro panel
API logs panel
Data quality panel
```

---

### 6.5 Fetch Attribution Trace

```http
GET /api/research/report/{report_id}/trace
```

Response:

```ts
{
  report_id: string;
  attribution_trace: AttributionTraceItem[];
  trace_summary: Record<string, unknown>;
  data_quality: Record<string, unknown>;
  alternative_explanations: AlternativeExplanation[];
}
```

Used for the Attribution Trace page.

---

### 6.6 Run Auto Scan

```http
POST /api/research/auto-scan
```

Request:

```ts
{
  assets: ['BTC', 'ETH'];
  time_window: '4h';
  force_refresh: boolean;
}
```

Response:

```ts
{
  generated_at: string;
  cache_hit: boolean;
  reports: AutoScanReport[];
}
```

Suggested AutoScanReport type:

```ts
interface AutoScanReport {
  report_id: string;
  asset: string;
  price_now: number | null;
  price_change_4h_pct: number | null;
  price_change_24h_pct: number | null;
  direction: string | null;
  direction_label_zh: string | null;
  trigger_reason: string | null;
  top_news: Record<string, unknown>;
  report_markdown: string;
  created_at: string;
  updated_at: string;
}
```

---

### 6.7 Run Market Scan

```http
POST /api/research/market-scan
```

Request:

```ts
{
  assets: ['BTC', 'ETH'];
  force_refresh: boolean;
}
```

Response:

```ts
{
  generated_at: string;
  results: MarketScanRecord[];
}
```

Used for:

```text
Overview page BTC / ETH market cards
Auto Scan page scan result cards
Quick 4h direction display
```

---

### 6.8 Fetch Market Scan History

```http
GET /api/research/market-scans?asset=BTC&limit=20
```

Response:

```ts
{
  results: MarketScanRecord[];
}
```

Used for:

```text
Market scan history
4h movement history
Future mini trend charts
```

---

### 6.9 Fetch Source Health

```http
GET /api/research/source-health?lookback_hours=24
```

Response:

```ts
{
  generated_at: string;
  lookback_hours: number;
  sources: SourceHealth[];
}
```

Used for:

```text
Data Sources page
Right insight panel
Settings diagnostics
```

---

### 6.10 Fetch Historical Reports

```http
GET /api/research/reports?asset=BTC&limit=20
```

Response:

```ts
{
  reports: StoredReport[];
}
```

Used for:

```text
Reports page
Sidebar Recent Reports
Page refresh recovery
```

---

### 6.11 Fetch Latest Report

```http
GET /api/research/latest?asset=BTC
```

Response: latest report payload.

Used for:

```text
Overview default latest report
Auto Scan completion result
Quick open latest BTC / ETH report
```

---

### 6.12 Fetch Worker On-chain Events

If `VITE_WORKER_URL` is configured:

```http
GET {VITE_WORKER_URL}/api/onchain/events?limit=50
```

Used for the On-chain Events page.

If `VITE_WORKER_URL` is not configured, show a clear empty / setup state.

---

## 7. Page Requirements

---

## 7.1 Overview Page

### Purpose

The Overview page should be the default landing page. It gives users a quick view of market state and recent research output.

### Required data fetching on load

```text
POST /api/research/market-scan
GET /api/research/reports?limit=20
GET /api/research/source-health?lookback_hours=24
```

### Required sections

```text
BTC market card
ETH market card
Stablecoin / liquidity placeholder or derived card
Research question input
Latest report summary
Signal matrix preview
Attribution summary preview
Source health summary
Top news summary
```

### BTC / ETH market cards should show

```text
asset
price_now
price_change_4h_pct
direction
direction_label_zh
created_at
```

### Research input behavior

When the user clicks Generate Report:

1. Call `POST /api/research/report`.
2. Poll `GET /api/research/report/{report_id}`.
3. Once completed, call `GET /api/research/report/{report_id}/data`.
4. Render the report dashboard.

### Empty states

If there are no reports:

```text
No reports yet. Generate your first research report.
```

If market scan fails:

```text
Market scan unavailable. Please retry or check backend connection.
```

---

## 7.2 Reports Page

### Purpose

The Reports page should show backend-persisted reports. It should not rely only on browser state.

### Required data fetching

```text
GET /api/research/reports?limit=20
```

### Required filters

```text
All
BTC
ETH
Completed
Failed
Mode
Risk level
```

### Required table fields

```text
user_query
asset
mode
time_window
status
risk_score
risk_level
updated_at
```

### Row click behavior

When clicking a report row:

1. Call `GET /api/research/report/{report_id}`.
2. Call `GET /api/research/report/{report_id}/data`.
3. Show report detail preview or navigate to Report Detail page.

### Right-side preview fields

```text
query
asset
mode
risk_score
risk_level
trigger_reason
top_news_title
updated_at
```

### Actions

```text
Open dashboard
View markdown
View attribution trace
Copy report markdown
```

---

## 7.3 Auto Scan Page

### Purpose

The Auto Scan page should allow the user to trigger backend auto-scans for BTC and ETH.

### Required controls

```text
BTC selection
ETH selection
time_window: 4h
force_refresh toggle
Run Auto Scan button
```

### Required API call

```text
POST /api/research/auto-scan
```

### Required result fields

For each returned report:

```text
report_id
asset
price_now
price_change_4h_pct
price_change_24h_pct
direction
direction_label_zh
trigger_reason
top_news
report_markdown preview
created_at
updated_at
```

### Required states

```text
Idle
Running scan
Cache hit
Scan completed
Scan failed
Partial asset failure
```

### Suggested loading steps

The frontend can display static process steps:

```text
Fetching market data
Fetching derivatives data
Classifying news
Reading on-chain context
Building attribution
Generating report
```

### Required actions per report

```text
Open full report
View attribution trace
Copy markdown
```

---

## 7.4 On-chain Events Page

### Purpose

The On-chain Events page should show large transfer events from the Worker or from report snapshots.

### Data source priority

1. If `VITE_WORKER_URL` exists, call:
   ```text
   GET {VITE_WORKER_URL}/api/onchain/events?limit=50
   ```
2. If Worker URL is missing, show setup state.
3. If report detail contains on-chain snapshot data, show it inside the report detail page.

### Required table fields

```text
timestamp
asset
amount
tx_hash
from_label
to_label
direction
source
created_at
```

### Required filters

```text
asset
direction
min amount
source
```

### Required states

```text
Worker URL missing
Unauthorized
No events found
Loading events
Events loaded
Failed to load events
```

### Empty state copy

```text
No on-chain events received yet. Configure the Alchemy webhook first.
```

---

## 7.5 Data Sources Page

### Purpose

The Data Sources page should let users inspect whether the report data sources are healthy.

### Required API call

```text
GET /api/research/source-health?lookback_hours=24
```

### Required summary cards

```text
Healthy providers count
Degraded providers count
Down providers count
Average latency
```

### Required provider table fields

```text
provider
health_status
success_count
error_count
avg_latency_ms
last_success_at
last_error_at
```

### Required provider detail expansion

When clicking a provider, show:

```text
provider
health_status
success_count
error_count
avg_latency_ms
last_success_at
last_error_at
possible affected report layers
```

### Required API logs panel

Inside a report detail page, show `api_call_logs` with:

```text
provider
endpoint
status_code
latency_ms
error_message
created_at
```

---

## 7.6 Attribution Trace Page

### Purpose

The Attribution Trace page should explain why each candidate driver was classified as primary, secondary, context, or noise.

### Required API call

```text
GET /api/research/report/{report_id}/trace
```

### Required summary fields

```text
report_id
trace_summary
data_quality
alternative_explanations count
```

### Required candidate scoring table fields

```text
candidate_id
driver
source_layer
raw_score
adjustments
final_score
primary_eligible
classification
classification_reason
```

### Required adjustment expansion

For each adjustment:

```text
name
value
reason
```

### Required alternative explanations section

For each alternative explanation:

```text
explanation
supporting_evidence
why_not_primary
```

### Required data quality section

Display:

```text
market
spot_flow
derivatives
news
onchain
etf_flow
macro
overall_data_quality_score
```

---

## 7.7 Settings Page

### Purpose

The Settings page should help verify frontend/backend configuration and default behavior.

### Required fields

```text
VITE_API_URL
VITE_WORKER_URL
default asset
default time window
default report limit
source health lookback hours
```

### Required checks

```text
Backend health check
Worker URL presence
Current environment mode
```

### Required status outputs

```text
Backend connected
Backend disconnected
Worker configured
Worker missing
```

### Required safety copy

The safety disclaimer must always be visible somewhere in the app:

```text
Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, hold, or use leverage.
```

---

## 8. Report Detail Dashboard Requirements

The Report Detail page can be reached from:

```text
Overview
Reports
Auto Scan
Latest report
```

### Required module order

```text
1. Report Summary Header
2. Market Snapshot Cards
3. Risk Score Panel
4. Attribution Panel
5. Signal Matrix
6. Derivatives Panel
7. News Drivers Panel
8. On-chain Panel
9. ETF Flow Panel
10. Macro Context Panel
11. Data Quality Panel
12. API Logs Panel
13. Full Markdown Report
```

---

## 8.1 Report Summary Header

Display:

```text
user_query
asset
mode
time_window
status
updated_at
price_now
price_change_4h_pct
price_change_24h_pct
direction
direction_label_zh
trigger_reason
top_news_title
top_news_source
```

---

## 8.2 Market Snapshot Cards

Read from `snapshots.market`.

Display if available:

```text
price_now
price_change_1h_pct
price_change_4h_pct
price_change_24h_pct
price_change_7d_pct
volume_24h
volume_ratio_vs_7d
market_cap
market_signal
spot_turnover_24h
spot_volume_24h_base
spot_turnover_source
spot_flow_bias
spot_cvd_approx_1h
spot_cvd_approx_4h
price_vs_ema20
price_vs_ema50
price_vs_ema200
```

If a field is missing, display `n/a`.

---

## 8.3 Risk Score Panel

Read from `snapshots.risk`.

Display:

```text
risk_score
risk_level
risk_breakdown
risk_summary
```

Required behavior:

```text
Show score out of 12
Show risk level
Show risk breakdown
Show fallback if risk data is missing
```

---

## 8.4 Attribution Panel

Read from `snapshots.attribution`.

Display:

```text
event_summary
primary_drivers
secondary_drivers
noise
quality_check
```

Each driver should show:

```text
driver
explanation
evidence
score
confidence
direction
causality_level
supporting_evidence
counter_evidence
missing_evidence
```

Required action:

```text
View attribution trace
```

---

## 8.5 Signal Matrix

Read from `normalized_signals`.

Display:

```text
layer
signal_name
signal_value
direction
impact_level
confidence
created_at
```

Required filters:

```text
layer
direction
impact_level
```

---

## 8.6 Derivatives Panel

Read from `snapshots.derivatives`.

Display if available:

```text
provider
symbol
funding_rate_now
funding_rate_8h_ago
funding_rate_change
open_interest_now
open_interest_change_24h_pct
mark_price
index_price
basis_pct
volume_usd
next_funding_time
put_call_ratio
put_call_volume_ratio
liquidation_bias
long_liquidations_24h
short_liquidations_24h
long_liquidation_events_24h
short_liquidation_events_24h
derivatives_signal
source_note
```

---

## 8.7 News Drivers Panel

Read from `snapshots.news`.

Display:

```text
events
top_news
```

Each news event should show:

```text
title
source
url
published_at
direction
impact_level
category
confidence
reason
asset_related
```

If URL exists, title should be clickable.

---

## 8.8 On-chain Panel

Read from `snapshots.onchain`.

Display:

```text
onchain_signal
large_transfers
stablecoin_supply_change_24h
exchange_inflow_count
large_transfer_count
onchain_evidence_quality
```

Each large transfer should show:

```text
hash
amount
from_label
to_label
direction
timestamp
```

---

## 8.9 ETF Flow Panel

Read from `snapshots.etf_flow` or equivalent ETF snapshot.

Display if available:

```text
btc_etf_net_flow_usd_m
net_flow_usd_m_latest
flow_direction
etf_flow_signal
flow_intensity
is_stale
source
```

If unavailable, display:

```text
ETF flow unavailable for this report.
```

---

## 8.10 Macro Context Panel

Read from `snapshots.macro`.

Display if available:

```text
macro_signal
macro_confidence
macro_signal_evidence
source
```

If unavailable, display:

```text
Macro context unavailable for this report.
```

---

## 8.11 Data Quality Panel

Read from `snapshots.attribution.data_quality` or trace endpoint.

Display:

```text
market
spot_flow
derivatives
news
onchain
etf_flow
macro
overall_data_quality_score
```

Each section should show:

```text
status
source
missing_fields
stale
warnings
methodology
confidence
```

---

## 8.12 API Logs Panel

Read from `api_call_logs`.

Display:

```text
provider
endpoint
status_code
latency_ms
error_message
created_at
```

Required filters:

```text
provider
status code
error only
```

---

## 8.13 Full Markdown Report

Render `report_markdown`.

Required support:

```text
headings
paragraphs
bullet lists
numbered lists
tables
links
code blocks
blockquote
```

Required actions:

```text
Copy markdown
Download markdown
```

---

## 9. State Management Requirements

Suggested global state:

```ts
interface AppState {
  currentPage: string;
  selectedAsset: 'AUTO' | 'BTC' | 'ETH';
  selectedTimeWindow: '4h' | '24h' | '7d';
  queryDraft: string;

  reports: StoredReport[];
  currentReport: StoredReport | null;
  currentReportData: ReportData | null;
  currentTrace: AttributionTraceResponse | null;

  marketScans: MarketScanRecord[];
  sourceHealth: SourceHealth[];

  isGenerating: boolean;
  isAutoScanning: boolean;
  isLoadingReports: boolean;
  isLoadingReportData: boolean;
  isLoadingTrace: boolean;
  isLoadingSourceHealth: boolean;

  errorMessage: string | null;
}
```

---

## 10. Page Initialization Requirements

On app startup, call:

```text
GET /health
GET /api/research/reports?limit=20
POST /api/research/market-scan
GET /api/research/source-health?lookback_hours=24
```

If some calls fail, the app should still render partial UI.

Example:

```text
Reports load failed but market scan succeeded.
Source health failed but report generation still works.
```

---

## 11. Loading States

The frontend should distinguish:

```text
Backend health checking
Loading market scan
Loading historical reports
Starting report generation
Report processing
Fetching report data
Running auto scan
Fetching source health
Fetching attribution trace
Fetching on-chain events
```

Do not show one generic loading state for everything.

---

## 12. Error States

The frontend must handle:

```text
Backend offline
CORS error
VITE_API_URL missing
VITE_WORKER_URL missing
HTTP 400
HTTP 401
HTTP 404
HTTP 500
Report failed
Report processing timeout
Market scan unavailable
Source health empty
Trace empty
On-chain events empty
Worker unauthorized
```

Each error should be visible and recoverable where possible.

---

## 13. Empty States

Required empty states:

```text
No reports yet
No market scan data
No attribution trace
No normalized signals
No source health data
No API logs
No on-chain events
No markdown report
```

Each empty state should explain what the user can do next.

---

## 14. Polling Behavior

For manual report generation:

1. Start report.
2. Poll every 2 seconds.
3. Stop when status is `completed` or `failed`.
4. If still processing after a defined limit, show:
   ```text
   Report is still processing. Retry status check.
   ```
5. Do not delete the report from UI on timeout.
6. Allow manual refresh of status.

Suggested polling config:

```ts
const POLL_INTERVAL_MS = 2000;
const SOFT_TIMEOUT_MS = 60000;
```

After soft timeout, stop auto-polling but allow manual retry.

---

## 15. Report Recovery

If a report was started but frontend lost state:

1. Historical reports should be recoverable via:
   ```text
   GET /api/research/reports
   ```
2. Latest report should be recoverable via:
   ```text
   GET /api/research/latest?asset=BTC
   ```

Refreshing the page should not erase completed reports.

---

## 16. Safety Boundary

The frontend must clearly display that the product is research-only.

Required copy:

```text
Research-only dashboard. This is not financial advice, investment advice, or a recommendation to buy, sell, hold, or use leverage.
```

The frontend must not include:

```text
Buy button
Sell button
Trade button
Leverage recommendation
Position sizing recommendation
Guaranteed return language
```

---

## 17. Deprecated / Should Remove

### 17.1 Remove or isolate old ChatArea

If the product is now a dashboard, the old chat-style component should be removed or clearly separated.

Do not keep multiple competing input systems.

### 17.2 Remove fake navigation

Sidebar navigation items must actually work.

If a page is not implemented, do not show it as active navigation.

### 17.3 Remove unsupported controls

Do not show controls for backend features that do not exist, such as:

```text
file upload
paperclip
microphone
voice input
trading execution
wallet connection
```

---

## 18. MVP Priority

### P0: Must Implement First

```text
API client
VITE_API_URL support
Health check
4h / 24h / 7d support
AUTO / BTC / ETH support
StoredReport type update
Overview page
Reports page
Manual Generate Report flow
Report polling
Report data dashboard
Sidebar page switching
Loading states
Error states
Research-only disclaimer
```

### P1: Implement Second

```text
Auto Scan page
Market Scan cards
Data Sources page
Source Health summary
Attribution Trace page
API Logs panel
Latest report loading
Report recovery after refresh
```

### P2: Implement Third

```text
On-chain Events page
VITE_WORKER_URL support
ETF Flow panel
Macro Context panel
Data Quality panel
Copy markdown
Download markdown
Export report
Advanced filters
```

---

## 19. Frontend Engineer Checklist

Use this as the implementation checklist.

```text
[ ] Supports VITE_API_URL
[ ] Supports optional VITE_WORKER_URL
[ ] Has centralized API client
[ ] Handles backend health check
[ ] Supports AUTO / BTC / ETH
[ ] Supports 4h / 24h / 7d
[ ] Can create manual report
[ ] Can poll report status
[ ] Can fetch report data
[ ] Can render markdown report
[ ] Can load historical reports
[ ] Reports remain after page refresh
[ ] Can trigger auto scan
[ ] Can display auto scan result
[ ] Can run market scan
[ ] Can display BTC / ETH 4h market cards
[ ] Can fetch source health
[ ] Can display data source health
[ ] Can fetch attribution trace
[ ] Can display attribution trace table
[ ] Can display normalized signals
[ ] Can display API call logs
[ ] Can display on-chain snapshot data
[ ] Can optionally fetch Worker on-chain events
[ ] Sidebar navigation actually switches pages
[ ] Loading states are separated by task
[ ] Error states are recoverable
[ ] Empty states are handled
[ ] Unsupported ChatArea / Mic / Paperclip removed
[ ] Research-only safety disclaimer is visible
```

---

## 20. Final Acceptance Flow

The frontend is acceptable when this user journey works:

```text
Open the website
→ Backend health is checked
→ BTC / ETH 4h market scan appears
→ User clicks Auto Scan
→ BTC / ETH auto research results appear
→ User opens one report
→ Report Detail dashboard appears
→ User sees Market / Risk / Attribution / Signal / News / On-chain / Markdown
→ User opens Attribution Trace
→ Driver scoring and classification reasons appear
→ User opens Data Sources
→ Provider health status appears
→ User refreshes the page
→ Historical reports are still available
```

If this path works, the frontend and backend are functionally aligned.
