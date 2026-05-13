# Bybit Replacement Plan

## Background

The app currently uses Bybit public market endpoints for BTC/ETH market and derivatives data. On a Hong Kong based server, Bybit public endpoints can return `403 Forbidden`, likely due to IP, region, or WAF restrictions. Binance may have a similar access risk from the same server location, so it should not be the primary replacement.

The goal is to keep Bybit as an optional enhancement source, but make the research agent work without it.

## Current Bybit Usage

| Area | Current Bybit endpoint | Purpose | Replacement status |
|---|---|---|---|
| 4h market snapshot | `/v5/market/kline` spot, interval `240` | current price, 4h ago price, 4h percent change | Already can fall back to CoinGecko market chart |
| Daily klines | `/v5/market/kline` spot, interval `D` | EMA20/50/200, 7d average volume | Already can fall back to CoinGecko market chart |
| Spot ticker | `/v5/market/tickers` spot | 24h turnover and base volume | Can fall back to CoinGecko total market volume, but exchange-level turnover is lost |
| Perp ticker | `/v5/market/tickers` linear | funding now, next funding time, mark/index price, basis, OI | Needs replacement |
| Funding history | `/v5/market/funding/history` linear | previous funding rate | Needs replacement |
| Open interest history | `/v5/market/open-interest` linear | 24h OI change | Needs replacement |
| Liquidation stream | `wss://stream.bybit.com/v5/public/linear` `allLiquidation.*` | local long/short liquidation events | Needs replacement or statistical fallback |

## Recommended Replacement Stack

### 1. Market Layer

Keep the existing non-exchange sources as the main path:

- CoinGecko for current price, 1h/24h/7d change, market cap, volume, 4h approximation, and EMA/volume fallback.
- CoinPaprika as a fallback for basic market price data.

Rationale:

- Works without exchange account credentials.
- Less likely to be blocked than Bybit/Binance from Hong Kong.
- Good enough for a research dashboard where exchange-specific spot turnover is not essential.

### 2. Derivatives Primary Source: Coinalyze

Use Coinalyze Free API when `COINALYZE_API_KEY` is configured.

Target fields:

- `funding_rate_now`
- `funding_rate_8h_ago`
- `funding_rate_change`
- `open_interest_now`
- `open_interest_change_24h_pct`
- `long_liquidations_24h`
- `short_liquidations_24h`
- `liquidation_bias`

Implementation idea:

- Add `COINALYZE_API_KEY` to `.env`.
- Call `future-markets` to discover BTC/ETH perpetual markets automatically.
- Prefer non-Bybit and non-Binance markets where possible.
- Use:
  - `funding-rate`
  - `funding-rate-history`
  - `open-interest`
  - `open-interest-history`
  - `liquidation-history`
- Convert OI and liquidation values to USD when the API supports it.

Manual registration:

- Coinalyze API key page: <https://coinalyze.net/account/api-key/>
- API docs: <https://api.coinalyze.net/v1/doc/>

Notes:

- Free plan is limited, so cache or keep calls minimal.
- Do not hardcode a single exchange symbol if avoidable; let the app discover symbols.

### 3. Derivatives Fallback: Deribit Public API

Use Deribit public endpoints without API key.

Good for:

- BTC/ETH options put/call ratio. This already exists in the app.
- BTC/ETH perpetual summary as a fallback for funding, OI, mark price, and basis.

Target endpoint:

- `public/get_book_summary_by_instrument`
- Instruments:
  - `BTC-PERPETUAL`
  - `ETH-PERPETUAL`

Target fields:

- `current_funding`
- `funding_8h`
- `open_interest`
- `mark_price`
- `estimated_delivery_price` or index price equivalent
- `volume_usd`

Docs:

- <https://docs.deribit.com/>

### 4. Derivatives Cross-Check: Hyperliquid Public Info API

Use Hyperliquid public API without key as a supplemental perp sentiment source.

Target endpoint:

- `POST https://api.hyperliquid.xyz/info`
- Body:

```json
{"type":"metaAndAssetCtxs"}
```

Target fields:

- `funding`
- `openInterest`
- `markPx`
- `oraclePx`
- `dayNtlVlm`

Docs:

- <https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals>

Notes:

- Hyperliquid is not a traditional centralized exchange, so treat it as a cross-check rather than the only derivatives source.

## Sources To Avoid As Primary Replacements

### Binance

Binance has equivalent public endpoints for klines, tickers, funding, OI, and liquidation streams. However, from a Hong Kong server it may have the same access or compliance risk as Bybit. It can be optional, but should not be the main dependency.

### Gate and OKX

Gate and OKX have useful public APIs, but their restricted-location policies may also create access risk from Hong Kong. They are acceptable as optional future providers if tested, but not ideal as the core fix.

## Data Priority Rules

Recommended priority order:

1. Market price and technicals:
   - CoinGecko
   - CoinPaprika fallback
   - Bybit only when reachable

2. Derivatives:
   - Coinalyze if API key exists and calls succeed
   - Bybit if reachable
   - Deribit perpetual public API
   - Hyperliquid public API
   - local liquidation store as historical fallback

3. Options:
   - Deribit public options summary

4. Liquidations:
   - Coinalyze liquidation history as the preferred free statistical fallback
   - local collected liquidation events when available
   - Bybit websocket only when reachable

## Output Compatibility

Keep the existing report and risk fields stable:

- `funding_rate_now`
- `funding_rate_8h_ago`
- `funding_rate_change`
- `open_interest_now`
- `open_interest_change_24h_pct`
- `long_liquidations_24h`
- `short_liquidations_24h`
- `liquidation_bias`
- `basis_pct`
- `put_call_ratio`
- `put_call_volume_ratio`
- `derivatives_signal`

Add provider-specific nested diagnostics:

- `coinalyze`
- `deribit_perpetual`
- `hyperliquid_perpetual`

Add availability flags:

- `bybit_available`
- `coinalyze_available`
- `deribit_perpetual_available`
- `hyperliquid_available`

## Error Handling

For Bybit `403 Forbidden`:

- Treat it as a handled provider-unavailable condition.
- Do not expose raw `HTTPStatusError` in user-facing reports.
- Add a short note that the runtime cannot access Bybit public endpoints.
- Continue using fallback sources.

For Coinalyze missing key:

- Do not report an error.
- Skip Coinalyze quietly and use Deribit/Hyperliquid fallback.

For fallback provider failures:

- Keep errors in raw snapshot/debug data.
- Avoid failing the whole report unless all market data sources fail.

## Implementation Checklist

- Add `COINALYZE_API_KEY` to settings and `.env.example`.
- Add `post_json` helper for Hyperliquid.
- Add Coinalyze derivatives fetcher with market discovery.
- Add Deribit perpetual fetcher.
- Add Hyperliquid perpetual fetcher.
- Merge metrics with stable field names and clear source priority.
- Update attribution copy from "Bybit liquidation data" to generic "liquidation data".
- Add tests:
  - Bybit 403 is suppressed and falls back.
  - Coinalyze is preferred when available.
  - Deribit/Hyperliquid fields do not break report generation.
- Keep Cloudflare/front-end UI rollback separate from backend data-source changes.

## Operational Notes

If Cloudflare needs to build a specific UI version, confirm which branch it listens to. In this project, production is expected to listen to `main`. Reverting a non-production branch will not change the Cloudflare production UI.

The white dashboard UI was identified around commit:

```text
6bd04d6 Revert frontend to white dashboard
```

The data-source fallback work was separate and should not be mixed with UI rollback unless intentionally redeploying both.
