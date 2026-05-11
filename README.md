---
title: Crypto Research Agent
emoji: 📈
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Crypto Research Agent Backend

Backend MVP for a BTC / ETH crypto research assistant. It collects market,
derivatives, news, on-chain context, computes explainable risk/attribution
signals, and renders a research-only Markdown report.

## Quick Start

Run the Python FastAPI backend and the Vite frontend in separate terminals. The
frontend dev server does not start the Python backend automatically.

Terminal 1, backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.server
```

Verify the backend:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Then start a report:

```bash
curl -X POST http://127.0.0.1:8000/api/research/report \
  -H "Content-Type: application/json" \
  -d '{"query":"Analyze why BTC dropped today."}'
```

Expected response shape:

```json
{
  "report_id": "...",
  "status": "processing"
}
```

Check the result:

```bash
curl http://127.0.0.1:8000/api/research/report/<report_id>
curl http://127.0.0.1:8000/api/research/report/<report_id>/data
```

Terminal 2, frontend:

```bash
npm run dev
```

In local development, `frontend/vite.config.ts` proxies `/api` to
`http://127.0.0.1:8000`. That proxy only exists while the Vite dev server is
running. You can leave `VITE_API_URL` empty locally to use the proxy, or copy
`frontend/.env.local.example` to `frontend/.env.local` and set it explicitly:

```text
VITE_API_URL=http://127.0.0.1:8000
```

## Cloudflare Pages / Production Deployment

The repository root is configured as the Cloudflare project root. Use:

```bash
npm run build
```

Set the build output directory to:

```text
frontend/dist
```

The frontend calls the report backend through `VITE_API_URL`.

For production, deploy the Python FastAPI backend separately first, for example
on Render, Railway, Fly.io, a VPS, or another service that can run:

```bash
python -m backend.server
```

Then set the Cloudflare Pages build-time environment variable:

```text
VITE_API_URL=https://your-fastapi-backend-domain.com
```

Set this in the Cloudflare Pages project settings for both Production and
Preview as needed. Do not set it only as a Cloudflare Worker runtime variable in
`wrangler.jsonc`; Vite client variables are embedded while the frontend is
built.

`VITE_API_URL` is a Vite build-time variable. If you change it in Cloudflare
Pages, rebuild and redeploy the frontend.

If production `VITE_API_URL` is missing, the frontend refuses to start report
generation and shows:

```text
Missing VITE_API_URL in production. Set it as a Cloudflare Pages build-time environment variable to the public FastAPI backend URL, then rebuild.
```

This is intentional. Without `VITE_API_URL`, browser requests would go to the
current Cloudflare domain, such as `/api/research/report`. The Cloudflare Worker
in this repository is not the report backend, so that path returns 404.

The current recommended MVP deployment is:

```text
Cloudflare Pages frontend
→ VITE_API_URL
→ external Python FastAPI backend /api/research/*
```

The Cloudflare Worker remains responsible for webhook and on-chain event routes:

```text
GET  /health
POST /api/webhooks/alchemy
GET  /api/onchain/events?limit=50
```

Alternative deployment: the Worker can proxy `/api/research/*` to the Python
backend if you add a `BACKEND_API_URL` Worker environment variable and forwarding
logic in `src/worker.ts`. In that setup the Worker must preserve method,
headers, and body, and must handle CORS. This repository does not enable that
proxy by default because direct frontend-to-FastAPI routing is simpler for the
current MVP.

## Hugging Face Spaces Backend Deployment

You can deploy the Python FastAPI backend for free on Hugging Face Spaces with
the Docker SDK, then use the Space URL as the frontend `VITE_API_URL`.

The root `Dockerfile` uses:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0
ENV PORT=7860
ENV BYBIT_LIQUIDATION_COLLECTOR_ENABLED=false
EXPOSE 7860
CMD ["python", "-m", "backend.server"]
```

Deploy flow:

1. Create a new Hugging Face Space.
2. Select **Docker** as the Space SDK.
3. Upload or connect this repository so the root `Dockerfile` is available.
4. Add any required backend secrets in the Space settings, such as
   `DEEPSEEK_API_KEY`, `COINGECKO_API_KEY`, `ETHERSCAN_API_KEY`, or
   `ALCHEMY_WEBHOOK_SECRET`.
5. Wait for the Space to build and start.

The Space backend URL will look like:

```text
https://<space-name>.hf.space
```

Verify health:

```bash
curl https://<space-name>.hf.space/health
```

Expected response:

```json
{"status":"ok"}
```

Start a report:

```bash
curl -X POST https://<space-name>.hf.space/api/research/report \
  -H "Content-Type: application/json" \
  -d '{"query":"Analyze why BTC dropped today."}'
```

Expected response shape:

```json
{
  "report_id": "...",
  "status": "processing"
}
```

Then set the frontend build-time environment variable:

```text
VITE_API_URL=https://<space-name>.hf.space
```

Rebuild and redeploy the frontend after changing `VITE_API_URL`.

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

For fully-free cloud hosting, deploy the Alchemy webhook receiver as a
Cloudflare Worker with D1 storage. This path does not require the local FastAPI
backend or a terminal to stay open:

```text
Alchemy Webhook
→ Cloudflare Worker /api/webhooks/alchemy
→ Cloudflare D1 onchain_events table
```

The Worker endpoints are:

```text
GET  /health
POST /api/webhooks/alchemy
GET  /api/onchain/events?limit=50
```

Deploy flow:

```bash
npx wrangler login
npx wrangler d1 create crypto_research_agent
```

Copy the returned `database_id` into `wrangler.jsonc`, replacing
`REPLACE_WITH_D1_DATABASE_ID`, then run:

```bash
npx wrangler d1 migrations apply crypto_research_agent --remote
npx wrangler secret put ALCHEMY_WEBHOOK_SECRET
npx wrangler deploy
```

After deploy, point Alchemy to:

```text
https://<your-worker-name>.<your-workers-subdomain>.workers.dev/api/webhooks/alchemy?secret=<ALCHEMY_WEBHOOK_SECRET>
```

Recent stored events can be inspected with the same secret:

```text
https://<your-worker-name>.<your-workers-subdomain>.workers.dev/api/onchain/events?limit=50&secret=<ALCHEMY_WEBHOOK_SECRET>
```

The local FastAPI layer remains available for local research reports:

```text
Alchemy Webhook
→ Cloudflare Tunnel public URL
→ FastAPI backend /api/webhooks/alchemy
→ local SQLite + JSONL storage
→ report generator reads stored on-chain events
```

Create an Alchemy Address Activity webhook and point it to the public tunnel URL:

```text
POST https://<your-cloudflare-tunnel-url>/api/webhooks/alchemy?secret=<ALCHEMY_WEBHOOK_SECRET>
```

For local development with Cloudflare Tunnel:

```bash
python -m backend.server
cloudflared tunnel --url http://127.0.0.1:8000
```

Set `ALCHEMY_WEBHOOK_SECRET` in `.env` and use the same value in the Alchemy URL query,
`X-Webhook-Secret`, or `Authorization: Bearer <secret>`. The backend stores ETH transfers
above `ETH_LARGE_TRANSFER_THRESHOLD_ETH` in SQLite at `DB_PATH`, appends the same normalized
events to `ONCHAIN_EVENTS_JSON_PATH`, and includes recent stored ETH events in later ETH
research reports.

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
