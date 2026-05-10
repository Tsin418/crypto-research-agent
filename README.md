# Crypto Research Agent Backend

Backend MVP for a BTC / ETH crypto research assistant. It collects market,
derivatives, news, on-chain context, computes explainable risk/attribution
signals, and renders a research-only Markdown report.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.server
```

Then call:

```bash
curl -X POST http://127.0.0.1:8000/api/research/report \
  -H "Content-Type: application/json" \
  -d '{"query":"Analyze why BTC dropped today."}'
```

Check the result:

```bash
curl http://127.0.0.1:8000/api/research/report/<report_id>
curl http://127.0.0.1:8000/api/research/report/<report_id>/data
```

## API Sources

- DeepSeek: intent parsing and Markdown report generation.
- CoinGecko / CoinPaprika: market data.
- Bybit: derivatives funding/open interest. Binance is intentionally optional for now.
- RSS feeds: crypto news classification.
- Etherscan: ETH gas context and optional watched-address transfer scans.
- Alchemy Webhooks: ETH/EVM large-transfer ingestion.
- mempool.space: BTC latest-block large-transfer scans.

Whale Alert has been removed.

## Safety Boundary

The report generator is constrained to research summaries only. It should not
produce buy, sell, hold, leverage, or guaranteed-return instructions.

## Alchemy Webhook

Create an Alchemy Address Activity webhook and point it to:

```text
POST http://<your-public-backend-url>/api/webhooks/alchemy?secret=<ALCHEMY_WEBHOOK_SECRET>
```

For local development, expose the backend with a tunnel such as ngrok or Cloudflare Tunnel.
The backend stores ETH transfers above `ETH_LARGE_TRANSFER_THRESHOLD_ETH` and includes them
in later ETH research reports.

## Implemented Backend Behavior

- Direct trading-advice requests are refused at the API boundary.
- `event_attribution`, `state_scan`, and `risk_watch` produce different report shapes.
- RSS news items use keyword classification first, then DeepSeek classification when `DEEPSEEK_API_KEY` is configured.
- Each report stores raw snapshots, normalized signals, and API call logs for debugging.
- This is currently optimized for single-user local usage; no user-account logic is required yet.

## Free Data Source Additions

- Deribit public API: BTC / ETH options put-call ratios.
- Bybit public WebSocket: BTC / ETH liquidation event collection while the backend is running.
- DeFiLlama stablecoins API: USDT / USDC supply and 24h / 7d liquidity changes.
- beaconcha.in API: ETH validator entry / exit queue when `BEACONCHAIN_API_KEY` is configured.
- Local `data/address_labels.json`: optional exchange/custody wallet labels for transfer direction.
- Farside BTC ETF flow parsing is best-effort; if blocked, the report records `etf_flow_unavailable`.
