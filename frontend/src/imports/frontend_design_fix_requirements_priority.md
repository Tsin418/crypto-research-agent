# Frontend Design Fix Requirements

> Scope: This document only includes the selected design / UX fixes from the current frontend review.  
> Selected items: 4, 5, 6, 7, 8, 9, 10, 12, 13.  
> Goal: Improve usability, layout robustness, information hierarchy, and product quality before connecting or fully relying on real backend data.

---

## Priority Overview

### P0 — Must Fix First

These issues directly affect usability and may cause layout breakage or user confusion.

1. Responsive layout for all major pages.
2. Long-text overflow handling in tables and cards.
3. Report Detail page navigation / section structure.
4. Sidebar active state when viewing Report Detail.
5. BTC / ETH data consistency and typo fixes.
6. Clarify duplicate research input behavior.

### P1 — Fix Before Deeper Backend Integration

These issues affect whether the product feels reliable once real data is connected.

1. Settings page should not behave like fake settings.
2. Report Detail first-screen summary hierarchy.
3. Clear semantic separation between risk, direction, and confidence.

### P2 — Product Quality Optimization

These issues affect whether the product feels like a polished research product rather than a generic data admin panel.

1. Reduce backend-field exposure.
2. Improve narrative explanation cards.
3. Reduce table-heavy layout.
4. Add collapsible sections for dense evidence.

---

# P0 Fixes

---

## 1. Add Responsive Layout Across All Pages

### Problem

The current frontend uses many fixed grid layouts such as:

```tsx
grid grid-cols-3
grid grid-cols-4
grid grid-cols-5
grid grid-cols-6
grid grid-cols-2
```

Many pages do not have responsive breakpoints such as:

```tsx
sm:
md:
lg:
xl:
```

This means the UI may look acceptable on a large desktop screen but can break on smaller laptop screens or narrower browser windows.

Affected pages:

```text
Overview
Reports
Auto Scan
On-chain Events
Data Sources
Attribution Trace
Settings
Report Detail
```

### Required Fix

All multi-column layouts should use responsive grid rules.

Examples:

```tsx
grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3
```

```tsx
grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4
```

```tsx
grid grid-cols-1 lg:grid-cols-2
```

For complex report detail sections:

```tsx
grid grid-cols-1 xl:grid-cols-12
```

### Required Page-Level Behavior

#### Overview

Market cards should not be fixed to 3 columns on all widths.

Expected behavior:

```text
Mobile / narrow width: 1 column
Medium width: 2 columns
Large width: 3 columns
```

#### Reports

Report table should remain readable on smaller screens.

Expected behavior:

```text
Table should become horizontally scrollable if needed.
Preview panel should move below the table on narrower screens.
```

#### Auto Scan

BTC and ETH result cards should stack on smaller screens.

Expected behavior:

```text
Mobile / narrow width: 1 column
Large width: 2 columns
```

#### On-chain Events

Metric cards should collapse responsively.

Expected behavior:

```text
Mobile / narrow width: 1 column
Medium width: 2 columns
Large width: 4 columns
```

#### Data Sources

Provider health cards should collapse responsively.

Expected behavior:

```text
Mobile / narrow width: 1 column
Medium width: 2 columns
Large width: 4 columns
```

#### Report Detail

Dense evidence panels should not squeeze into narrow columns.

Expected behavior:

```text
Summary cards stack first.
Tables become horizontally scrollable.
Secondary panels move below primary panels.
```

### Acceptance Criteria

```text
[ ] No page breaks when browser width is reduced.
[ ] No cards become unreadably narrow.
[ ] Tables do not overflow outside the viewport.
[ ] Main navigation remains usable on laptop-sized screens.
[ ] Report Detail remains readable without horizontal page-level overflow.
```

---

## 2. Handle Long Text Overflow in Tables and Cards

### Problem

Several components display long text directly. With real backend data, these values can become very long:

```text
wallet addresses
transaction hashes
API endpoints
news titles
attribution explanations
error messages
report queries
source URLs
```

Potentially affected components:

```text
On-chain Events table
API Logs table
Reports table
Attribution Trace table
News Drivers panel
Report Detail panels
Sidebar Recent Reports
```

### Required Fix

All long text fields must use truncation, wrapping, line-clamp, or horizontal scrolling depending on context.

### General Rules

#### For table cells

Use a max width and truncation:

```tsx
className="max-w-[220px] truncate"
```

#### For long explanations

Use line clamp:

```tsx
className="line-clamp-2"
```

or:

```tsx
className="line-clamp-3"
```

#### For tables

Wrap the table with:

```tsx
<div className="overflow-x-auto">
  <table>...</table>
</div>
```

#### For wallet addresses and transaction hashes

Show shortened versions:

```text
0x1234...abcd
```

Add full value on hover via `title`.

Example:

```tsx
<span title={fullAddress}>
  {shortenAddress(fullAddress)}
</span>
```

### Helper Function Recommendation

Add utility functions:

```ts
export function shortenHash(value?: string | null, start = 6, end = 4) {
  if (!value) return 'n/a';
  if (value.length <= start + end + 3) return value;
  return `${value.slice(0, start)}...${value.slice(-end)}`;
}
```

```ts
export function displayOrNA(value: unknown) {
  if (value === null || value === undefined || value === '') return 'n/a';
  return String(value);
}
```

### Specific Requirements

#### On-chain Events

Fields requiring truncation:

```text
tx_hash
from_label
to_label
direction
source
```

#### API Logs

Fields requiring truncation:

```text
endpoint
error_message
provider
```

#### Reports

Fields requiring truncation:

```text
user_query
mode
top_news_title
trigger_reason
```

#### Attribution Trace

Fields requiring truncation or line clamp:

```text
driver
adjustments
classification_reason
```

#### News Drivers

Fields requiring line clamp:

```text
title
reason
url
```

### Acceptance Criteria

```text
[ ] No wallet address or transaction hash breaks table layout.
[ ] API endpoints do not stretch the page.
[ ] News titles stay inside cards.
[ ] Attribution explanations do not overflow.
[ ] Sidebar recent reports do not overflow.
[ ] Long values remain accessible through tooltip, title, expand, or detail view.
```

---

## 3. Add Navigation Structure to Report Detail Page

### Problem

The Report Detail page contains many sections:

```text
Market Snapshot
Risk Score
Attribution
Signal Matrix
Derivatives
News
On-chain
ETF Flow
Macro
Data Quality
API Logs
Markdown Report
```

Currently, if all sections are stacked vertically, the page becomes too long and users can easily lose context.

### Required Fix

Add a second-level navigation structure inside the Report Detail page.

There are two acceptable approaches.

---

### Option A: Sticky Section Navigation

Add a sticky section navigation below the report summary header.

Suggested sections:

```text
Summary
Market
Risk
Attribution
Signals
News
On-chain
Data Quality
Logs
Markdown
```

Expected behavior:

```text
Clicking a section scrolls to that section.
Active section updates based on scroll position if possible.
The nav remains visible while scrolling.
```

Suggested implementation:

```tsx
<nav className="sticky top-0 z-10">
  <button>Summary</button>
  <button>Market</button>
  <button>Risk</button>
  <button>Attribution</button>
  <button>Signals</button>
  <button>News</button>
  <button>On-chain</button>
  <button>Logs</button>
  <button>Markdown</button>
</nav>
```

---

### Option B: Tabs

Group sections into tabs.

Suggested tabs:

```text
Overview
Evidence
Data Quality
API Logs
Markdown
```

Recommended tab grouping:

#### Overview

```text
Report Summary
Market Snapshot
Risk Score
AI Brief
Main Attribution
```

#### Evidence

```text
Signal Matrix
Derivatives
News
On-chain
ETF Flow
Macro
```

#### Data Quality

```text
Data Quality Panel
Source notes
Missing fields
Warnings
```

#### API Logs

```text
API call logs
Provider status
Errors
```

#### Markdown

```text
Full markdown report
Copy / download markdown
```

### Recommendation

For MVP, implement **Option B: Tabs** first.

Reason:

```text
It reduces page length.
It makes the report easier to scan.
It avoids forcing users to scroll through every dense evidence section.
```

### Acceptance Criteria

```text
[ ] Report Detail is not one endless unstructured page.
[ ] User can quickly jump to Markdown.
[ ] User can quickly inspect API Logs.
[ ] User can quickly inspect evidence sections.
[ ] User can return to summary without losing context.
```

---

## 4. Fix Sidebar Active State for Report Detail

### Problem

The app has a Report Detail state, but the Sidebar does not have a matching nav item.

When the user enters Report Detail from:

```text
Overview
Reports
Auto Scan
Latest Report
```

the Sidebar may not show any active navigation state.

This creates location confusion.

### Required Fix

Track the parent page that led to Report Detail.

Suggested state:

```ts
type Page = 'overview' | 'reports' | 'autoscan' | 'onchain' | 'sources' | 'trace' | 'settings' | 'detail';

type ParentPage = 'overview' | 'reports' | 'autoscan';

const [currentPage, setCurrentPage] = useState<Page>('overview');
const [detailParentPage, setDetailParentPage] = useState<ParentPage>('overview');
```

When opening a report:

```ts
function openReportDetail(reportId: string, parent: ParentPage) {
  setSelectedReportId(reportId);
  setDetailParentPage(parent);
  setCurrentPage('detail');
}
```

Sidebar active logic:

```ts
const activePage = currentPage === 'detail' ? detailParentPage : currentPage;
```

### Alternative

Add a temporary nav label:

```text
Report Detail
```

But this is less recommended because Report Detail is usually a child view, not a main nav section.

### Acceptance Criteria

```text
[ ] Opening a report from Reports keeps Reports active.
[ ] Opening a report from Auto Scan keeps Auto Scan active.
[ ] Opening latest report from Overview keeps Overview active.
[ ] Sidebar never appears with no active state while in Report Detail.
```

---

## 5. Clarify Research Input Behavior

### Problem

There are currently multiple research input entry points:

```text
TopBar search / ask input
Overview Research Question textarea
Generate button
Get Research button
```

If multiple inputs exist but behave differently, users may not know which one actually generates a report.

### Required Fix

Define clear behavior for each input.

There are two acceptable approaches.

---

### Option A: TopBar Is the Global Research Input

TopBar input is the main input for report generation.

Overview card should display the same query draft or act as a quick prompt area.

Expected behavior:

```text
Typing in TopBar updates the same queryDraft state.
Typing in Overview textarea updates the same queryDraft state.
Generate button and Get Research button trigger the same submit function.
```

Required shared function:

```ts
handleGenerateReport(queryDraft, selectedAsset, selectedTimeWindow)
```

---

### Option B: TopBar Is Search, Overview Is Research Input

TopBar input is only for searching reports or navigating data.

Overview textarea is the only place for research question generation.

Expected behavior:

```text
TopBar placeholder should say Search reports or data sources.
Overview textarea should say Ask a crypto research question.
Only Overview textarea triggers report generation.
```

### Recommendation

For MVP, implement **Option A**.

Reason:

```text
Users expect the top input to be actionable.
It reduces duplicated logic.
It creates a faster command-center feeling.
```

### Required Changes

1. Use a single `queryDraft` state.
2. Use one shared submit function.
3. Rename duplicate buttons consistently.
4. Avoid having one button that works and another button that is only decorative.

### Acceptance Criteria

```text
[ ] TopBar Generate and Overview Generate call the same function.
[ ] Both inputs show the same query value or have clearly different purposes.
[ ] No decorative research button remains.
[ ] User can generate a report from the most obvious input.
```

---

## 6. Fix Data and Copy Semantic Inconsistencies

### Problem

Some UI labels or sample data are semantically inconsistent or contain typos.

Examples identified:

```text
Total Mkt Cap uses $158.2B, which looks more like stablecoin supply.
On-chain data mixes BTC and ETH examples.
Typo: ITF Power.
Typo: No exchange exchange delisted detected.
Confidence badge may be confused with bullish / safe signal.
```

### Required Fixes

---

### 6.1 Fix Total Market Cap / Stablecoin Supply Confusion

If the value is around `$158.2B`, label it as:

```text
Stablecoin Supply
```

Do not label it as:

```text
Total Mkt Cap
```

unless it is actually total crypto market cap.

---

### 6.2 Ensure Asset Consistency

If the current report is BTC:

```text
Market data should be BTC.
Derivatives data should be BTC-related.
On-chain examples should not randomly show ETH unless clearly marked as ETH context.
```

If the current report is ETH:

```text
All main report cards should use ETH context.
```

For cross-asset context, explicitly label it:

```text
ETH on-chain context
Stablecoin liquidity context
Macro context
```

Do not mix BTC / ETH without labels.

---

### 6.3 Fix Typos

Replace:

```text
ITF Power
```

with:

```text
ETF Parser
```

Replace:

```text
No exchange exchange delisted detected
```

with:

```text
No exchange delisting detected
```

or:

```text
No major exchange disruption detected
```

---

### 6.4 Separate Risk, Direction, and Confidence

Do not use one badge like `Confident` to imply that the market is safe or bullish.

Use separate fields:

```text
Market Bias: Bearish / Bullish / Neutral / Cautious
Risk Level: Low / Medium / High
Confidence: Low / Medium / High
```

Recommended mapping:

```text
Risk = safety / volatility warning
Direction = market move or pressure
Confidence = model/data confidence
```

### Acceptance Criteria

```text
[ ] Stablecoin supply is not labeled as total market cap.
[ ] BTC report does not randomly show unlabeled ETH data.
[ ] ETH report does not randomly show unlabeled BTC data.
[ ] All known typos are fixed.
[ ] Risk, direction, and confidence are visually and textually separate.
```

---

# P1 Fixes

---

## 7. Make Settings Page Real or Read-Only

### Problem

The current Settings page appears editable, but changes may only update local component state and show `Saved!`.

If the settings do not actually affect the app or persist after refresh, the page behaves like fake settings.

### Required Fix

Choose one of the following approaches.

---

### Option A: Make Settings Read-Only Diagnostics

Recommended for MVP.

Settings page should display current runtime configuration:

```text
Current VITE_API_URL
Current VITE_WORKER_URL
Backend health status
Worker configured / missing
Default asset
Default time window
Environment mode
```

Do not allow editing if changes do not actually persist or affect API behavior.

Use labels like:

```text
Configured Backend URL
Configured Worker URL
Current Default Window
```

---

### Option B: Make Settings Truly Editable

If editing is allowed:

1. Save changes to `localStorage`.
2. Make API client read from saved settings.
3. Persist values after page refresh.
4. Provide reset-to-env-default button.

Suggested localStorage keys:

```text
cra.apiBaseUrl
cra.workerBaseUrl
cra.defaultAsset
cra.defaultTimeWindow
cra.reportLimit
cra.sourceHealthLookback
```

### Recommendation

For now, implement **Option A: Read-Only Diagnostics**.

Reason:

```text
Environment variables are usually build-time configuration.
Fake editable settings damage trust.
Read-only diagnostics are enough for MVP.
```

### Acceptance Criteria

```text
[ ] Settings page does not pretend to save values that do not affect the app.
[ ] Backend URL shown matches actual API client config.
[ ] Worker URL shown matches actual Worker config.
[ ] Backend health check is displayed.
[ ] Missing Worker URL is clearly shown as a setup issue, not a user error.
```

---

## 8. Improve Report Detail First-Screen Information Hierarchy

### Problem

Report Detail currently gives many panels similar visual weight.

Users need to immediately understand:

```text
What happened?
Why did it happen?
How risky is it?
How reliable is the data?
What should I inspect next?
```

If every module looks equally important, the page feels like a data dump.

### Required Fix

Add a strong first-screen summary at the top of Report Detail.

Required summary fields:

```text
Asset
Time window
Price now
4h change
24h change
Direction
Risk score
Risk level
Main driver
Confidence
Data quality
Updated at
```

Suggested structure:

```text
Report Summary
- BTC moved -1.82% over 4h.
- Main driver: Long leverage flush + weak spot demand.
- Risk level: High, 7 / 12.
- Data quality: Partial.
```

Below the summary, add quick action buttons:

```text
View Evidence
View Trace
View API Logs
Open Markdown
```

### Required Behavior

The first screen should answer the report conclusion before showing all evidence.

Evidence sections should come after summary.

### Acceptance Criteria

```text
[ ] First screen explains the report conclusion.
[ ] Main driver is visible without scrolling deeply.
[ ] Risk score is visible near the top.
[ ] Data quality is visible near the top.
[ ] User can jump to trace, logs, and markdown from the top.
```

---

## 9. Make the Product Feel Like a Research Product, Not a Data Admin Panel

### Problem

The current UI may feel like a generic data backend because:

```text
Too many raw tables
Too many backend field names
Too little natural-language explanation
All panels have similar weight
Important conclusions are not visually separated from raw data
```

### Required Fix

Convert backend-style fields into user-readable research language.

---

### 9.1 Humanize Field Labels

Avoid exposing raw backend field names directly.

Examples:

```text
Bad: price_change_4h_pct
Good: 4h Price Change

Bad: open_interest_change_24h_pct
Good: Open Interest 24h Change

Bad: macro_signal_evidence
Good: Macro Evidence

Bad: onchain_evidence_quality
Good: On-chain Evidence Quality
```

### 9.2 Add Explanation Cards

For each major evidence layer, include a short interpretation.

Examples:

```text
Market: BTC broke the 4h downside threshold with weaker spot demand.
Derivatives: Long liquidation pressure increased while open interest declined.
News: ETF flow and macro headlines were directionally negative.
On-chain: No strong exchange-inflow confirmation was detected.
```

### 9.3 Reduce Table-Only Sections

Tables are useful for raw data, but each table should have a summary above it.

Required pattern:

```text
Short interpretation
Key metrics
Detailed table
```

### 9.4 Use Expand / Collapse for Dense Evidence

Dense sections should be collapsible:

```text
API Logs
Raw data quality
Alternative explanations
Full markdown
Detailed adjustments
```

### Acceptance Criteria

```text
[ ] User sees conclusions before raw data.
[ ] Backend field names are translated into readable labels.
[ ] Dense tables have summaries above them.
[ ] Full Markdown is not forced into the first screen.
[ ] API Logs and raw evidence can be expanded when needed.
```

---

# P2 Fixes

---

## 10. Reduce Table-Heavy Layout

### Problem

Tables are currently used heavily across:

```text
Reports
On-chain Events
Sources
Trace
API Logs
Signal Matrix
```

This is acceptable for detailed inspection but can make the product feel like a database viewer.

### Required Fix

Keep tables for detailed data, but add higher-level cards or summaries before them.

Examples:

#### Reports

Before table:

```text
Total reports
Completed reports
Failed reports
Latest BTC report
Latest ETH report
```

#### On-chain Events

Before table:

```text
Large transfers count
Exchange inflow count
Total amount
Latest event time
```

#### Sources

Before table:

```text
Healthy providers
Degraded providers
Down providers
Average latency
```

#### Trace

Before table:

```text
Primary drivers
Secondary drivers
Noise candidates
Overall data quality
```

### Acceptance Criteria

```text
[ ] Each table page has summary cards above the table.
[ ] User can understand the page without reading every row.
[ ] Tables remain available for inspection.
```

---

## 11. Add Collapsible Dense Sections

### Problem

Some sections are necessary but too dense for default display:

```text
API Logs
Full Markdown
Attribution adjustments
Alternative explanations
Data quality missing fields
Raw error messages
```

### Required Fix

Use collapsible sections or tabs.

Default collapsed sections:

```text
API Logs
Full Markdown
Raw data quality details
Alternative explanations
Full attribution adjustment list
```

Default expanded sections:

```text
Report Summary
Market Snapshot
Risk Score
Main Attribution
Top Signals
```

### Acceptance Criteria

```text
[ ] Dense technical sections do not dominate the page by default.
[ ] User can expand details when needed.
[ ] Expanded sections preserve readable layout.
```

---

## 12. Improve Backend Field Mapping Layer

### Problem

If UI components directly use backend field names, the frontend becomes hard to read and hard to maintain.

### Required Fix

Create a label mapping layer.

Suggested file:

```text
src/utils/labels.ts
```

Example:

```ts
export const FIELD_LABELS: Record<string, string> = {
  price_change_4h_pct: '4h Price Change',
  price_change_24h_pct: '24h Price Change',
  volume_ratio_vs_7d: 'Volume vs 7d Average',
  open_interest_change_24h_pct: 'Open Interest 24h Change',
  funding_rate_now: 'Current Funding Rate',
  macro_signal_evidence: 'Macro Evidence',
  onchain_evidence_quality: 'On-chain Evidence Quality',
};
```

Helper:

```ts
export function labelForField(field: string) {
  return FIELD_LABELS[field] || field.replaceAll('_', ' ');
}
```

### Acceptance Criteria

```text
[ ] User-facing labels do not show raw snake_case unless unavoidable.
[ ] Label mapping is centralized.
[ ] New backend fields can be added without rewriting every component.
```

---

# Final Implementation Checklist

```text
[ ] Responsive grid added to all major pages.
[ ] All tables wrapped with overflow-x-auto.
[ ] Long text fields use truncate, line-clamp, or shorten helper.
[ ] Wallet addresses and hashes are shortened with full value available on hover.
[ ] Report Detail has tabs or sticky section navigation.
[ ] Sidebar remains active when viewing Report Detail.
[ ] TopBar input and Overview research input behavior is unified.
[ ] Duplicate or decorative research buttons removed.
[ ] Stablecoin supply is not mislabeled as total market cap.
[ ] BTC / ETH sample data is consistent with selected asset.
[ ] Typos fixed: ITF Power, No exchange exchange.
[ ] Risk, direction, and confidence are separated.
[ ] Settings page is read-only diagnostics or truly persistent.
[ ] Report Detail first screen has strong summary.
[ ] Main driver, risk, confidence, and data quality are visible near top.
[ ] Backend field names are mapped to human-readable labels.
[ ] Dense technical sections are collapsible.
[ ] Full markdown is not forced into the first screen.
[ ] API Logs are available but not visually dominant by default.
```

---

# Suggested Frontend Refactor Order

## Step 1: Layout Safety

```text
Responsive grids
Overflow handling
Text truncation
Hash / address shortening
```

## Step 2: Navigation Clarity

```text
Report Detail tabs or sticky nav
Sidebar active parent state
Unified research input behavior
```

## Step 3: Semantic Cleanup

```text
Fix typos
Fix asset consistency
Fix Total Mkt Cap vs Stablecoin Supply
Separate risk / direction / confidence
```

## Step 4: Trust and Product Feel

```text
Settings diagnostics
Report Detail top summary
Human-readable field labels
Explanation cards before tables
Collapsible technical sections
```

---

# Acceptance Test

After implementation, verify this flow:

```text
Open app on large desktop width
→ Overview looks correct
→ Reduce browser width
→ Cards stack correctly
→ Tables remain scrollable
→ Generate / open a report
→ Sidebar still shows the correct active parent page
→ Report Detail first screen clearly shows conclusion, risk, main driver, data quality
→ User can jump to Evidence / Logs / Markdown
→ Long addresses, endpoints, news titles, and explanations do not overflow
→ Settings page does not pretend to save fake values
→ BTC and ETH examples are not mixed without labels
```
