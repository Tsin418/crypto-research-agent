export interface Env {
  DB: D1Database;
  ALCHEMY_WEBHOOK_SECRET?: string;
  ETH_LARGE_TRANSFER_THRESHOLD_ETH?: string;
  SNAPSHOT_CRON_ENABLED?: string;
}

const WEI_PER_ETH = 1_000_000_000_000_000_000;

function json(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    ...init,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET, POST, OPTIONS",
      "access-control-allow-headers": "Content-Type, Authorization, X-Webhook-Secret",
      ...init.headers,
    },
  });
}

function safeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function rawContractEthValue(rawValue: unknown): number | null {
  if (!rawValue) return null;
  try {
    const value = typeof rawValue === "string" ? BigInt(rawValue) : BigInt(String(rawValue));
    return Number(value) / WEI_PER_ETH;
  } catch {
    return null;
  }
}

function isAuthorized(request: Request, url: URL, env: Env): boolean {
  const secret = env.ALCHEMY_WEBHOOK_SECRET || "";
  if (!secret) return true;
  const headerSecret = request.headers.get("x-webhook-secret") || "";
  const authorization = request.headers.get("authorization") || "";
  const querySecret = url.searchParams.get("secret") || "";
  return headerSecret === secret || authorization === `Bearer ${secret}` || querySecret === secret;
}

function normalizeAlchemyWebhook(payload: any, thresholdEth: number): Record<string, unknown>[] {
  const event = payload?.event ?? payload ?? {};
  const activities = event?.activity ?? payload?.activity ?? [];
  if (!Array.isArray(activities)) return [];

  const normalized: Record<string, unknown>[] = [];
  for (const item of activities) {
    const asset = String(item?.asset ?? item?.rawContract?.symbol ?? "ETH").toUpperCase();
    if (asset !== "ETH" && asset !== "WETH") continue;

    const amount = safeNumber(item?.value) ?? rawContractEthValue(item?.rawContract?.value);
    if (amount === null || amount < thresholdEth) continue;

    normalized.push({
      amount: Math.round(amount * 100_000_000) / 100_000_000,
      asset: "ETH",
      from_label: item?.fromAddress ?? item?.from ?? "unknown_address",
      to_label: item?.toAddress ?? item?.to ?? "unknown_address",
      timestamp: payload?.createdAt ?? event?.createdAt ?? null,
      direction: "large_eth_transfer",
      hash: item?.hash ?? item?.transactionHash ?? null,
      source: "alchemy_webhook",
      category: item?.category ?? null,
      raw: item,
    });
  }
  return normalized;
}

async function storeEvents(env: Env, events: Record<string, unknown>[]): Promise<void> {
  const statements = events.map((event, index) => {
    const txHash = String(event.hash || "unknown");
    const amount = Number(event.amount || 0);
    const eventId = `alchemy:${txHash}:${amount}:${index}`;
    return env.DB.prepare(
      `INSERT OR REPLACE INTO onchain_events
       (id, asset, source, tx_hash, amount, from_label, to_label, direction, timestamp, raw_json, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))`,
    ).bind(
      eventId,
      "ETH",
      "alchemy_webhook",
      txHash,
      amount,
      String(event.from_label || ""),
      String(event.to_label || ""),
      String(event.direction || ""),
      event.timestamp ? String(event.timestamp) : null,
      JSON.stringify(event),
    );
  });
  if (statements.length > 0) {
    await env.DB.batch(statements);
  }
}

async function handleAlchemyWebhook(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  if (!isAuthorized(request, url, env)) {
    return json({ error: "unauthorized webhook" }, { status: 401 });
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch (error) {
    return json({ error: "invalid json", details: String(error) }, { status: 400 });
  }

  const threshold = Number(env.ETH_LARGE_TRANSFER_THRESHOLD_ETH || "500");
  const events = normalizeAlchemyWebhook(payload, Number.isFinite(threshold) ? threshold : 500);
  await storeEvents(env, events);
  return json({ status: "accepted", stored_events: events.length }, { status: 202 });
}

async function listEvents(env: Env, url: URL): Promise<Response> {
  const limit = Math.min(Number(url.searchParams.get("limit") || "50") || 50, 200);
  const result = await env.DB.prepare(
    `SELECT id, asset, source, tx_hash, amount, from_label, to_label, direction, timestamp, raw_json, created_at
     FROM onchain_events
     ORDER BY COALESCE(timestamp, created_at) DESC
     LIMIT ?`,
  ).bind(limit).all();
  return json({ events: result.results ?? [] });
}

// --- Lightweight Snapshot Cron ---

function isoNow(): string {
  return new Date().toISOString().replace("T", " ").replace(/\.\d{3}Z$/, "");
}

async function fetchCoinGeckoPrice(asset: string): Promise<Record<string, unknown>> {
  const ids: Record<string, string> = { BTC: "bitcoin", ETH: "ethereum" };
  const id = ids[asset];
  if (!id) return {};
  try {
    const resp = await fetch(
      `https://api.coingecko.com/api/v3/simple/price?ids=${id}&vs_currencies=usd&include_24hr_change=true`,
    );
    if (!resp.ok) return {};
    const data = (await resp.json()) as Record<string, Record<string, number>>;
    const row = data[id];
    if (!row) return {};
    return {
      asset,
      price_usd: row.usd ?? null,
      price_change_24h_pct: row.usd_24h_change ?? null,
    };
  } catch {
    return {};
  }
}

async function fetchStablecoinSupply(): Promise<Record<string, unknown>> {
  try {
    const resp = await fetch("https://stablecoins.llama.fi/stablecoins?includePrices=false");
    if (!resp.ok) return {};
    const data = (await resp.json()) as { peggedAssets?: Array<{ circulating: { peggedUSD: number } }> };
    const assets = data.peggedAssets ?? [];
    const totalSupply = assets.reduce((sum, a) => sum + (a.circulating?.peggedUSD ?? 0), 0);
    return { total_stablecoin_supply_usd: Math.round(totalSupply), asset_count: assets.length };
  } catch {
    return {};
  }
}

async function fetchLatestRssTimestamps(): Promise<Record<string, unknown>> {
  const feeds: Record<string, string> = {
    CoinDesk: "https://www.coindesk.com/arc/outboundfeeds/rss/",
    CoinTelegraph: "https://cointelegraph.com/rss",
  };
  const timestamps: Record<string, string | null> = {};
  for (const [source, url] of Object.entries(feeds)) {
    try {
      const resp = await fetch(url);
      if (!resp.ok) { timestamps[source] = null; continue; }
      const text = await resp.text();
      const match = text.match(/<pubDate>([^<]+)<\/pubDate>/);
      timestamps[source] = match ? match[1] : null;
    } catch {
      timestamps[source] = null;
    }
  }
  return { rss_latest_timestamps: timestamps };
}

async function ensureLightweightTable(env: Env): Promise<void> {
  await env.DB.prepare(`
    CREATE TABLE IF NOT EXISTS lightweight_snapshots (
      id TEXT PRIMARY KEY,
      asset TEXT NOT NULL,
      layer TEXT NOT NULL,
      source TEXT NOT NULL,
      raw_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    )
  `).run();
  await env.DB.prepare(`
    CREATE INDEX IF NOT EXISTS idx_lightweight_snapshots_lookup
      ON lightweight_snapshots(asset, layer, created_at DESC)
  `).run();
}

function snapshotId(layer: string, asset: string): string {
  return `${layer}:${asset}:${isoNow()}`;
}

async function insertSnapshot(
  env: Env,
  layer: string,
  asset: string,
  source: string,
  data: Record<string, unknown>,
): Promise<void> {
  await env.DB.prepare(
    `INSERT OR REPLACE INTO lightweight_snapshots
     (id, asset, layer, source, raw_json, created_at)
     VALUES (?, ?, ?, ?, ?, ?)`,
  ).bind(snapshotId(layer, asset), asset, layer, source, JSON.stringify(data), isoNow()).run();
}

async function runLightweightSnapshot(env: Env): Promise<void> {
  await ensureLightweightTable(env);

  for (const asset of ["BTC", "ETH"]) {
    const price = await fetchCoinGeckoPrice(asset);
    if (price.asset) {
      await insertSnapshot(env, "price", asset, "coingecko_free", price);
    }
  }

  const stablecoins = await fetchStablecoinSupply();
  if (stablecoins.total_stablecoin_supply_usd) {
    await insertSnapshot(env, "stablecoins", "ALL", "defillama_free", stablecoins);
  }

  const rss = await fetchLatestRssTimestamps();
  await insertSnapshot(env, "rss_headlines", "ALL", "rss_free", rss);
}

// --- End Lightweight Snapshot ---

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return json({ ok: true });
    }

    if (url.pathname === "/health") {
      return json({ status: "ok", runtime: "cloudflare-worker" });
    }

    if (url.pathname === "/api/webhooks/alchemy" && request.method === "POST") {
      return handleAlchemyWebhook(request, env);
    }

    if (url.pathname === "/api/onchain/events" && request.method === "GET") {
      if (!isAuthorized(request, url, env)) {
        return json({ error: "unauthorized" }, { status: 401 });
      }
      return listEvents(env, url);
    }

    if (url.pathname === "/api/snapshots/latest" && request.method === "GET") {
      const asset = url.searchParams.get("asset") || "BTC";
      const layer = url.searchParams.get("layer") || "price";
      const result = await env.DB.prepare(
        `SELECT id, asset, layer, source, raw_json, created_at
         FROM lightweight_snapshots
         WHERE asset = ? AND layer = ?
         ORDER BY created_at DESC
         LIMIT 1`,
      ).bind(asset, layer).first();
      if (!result) {
        return json({ error: "not found" }, { status: 404 });
      }
      return json({ snapshot: result });
    }

    return json({ error: "not found" }, { status: 404 });
  },

  async scheduled(_controller: ScheduledController, env: Env, _ctx: ExecutionContext): Promise<void> {
    if (env.SNAPSHOT_CRON_ENABLED !== "true") return;
    _ctx.waitUntil(runLightweightSnapshot(env));
  },
};
