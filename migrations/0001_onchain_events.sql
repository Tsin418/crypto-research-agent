CREATE TABLE IF NOT EXISTS onchain_events (
  id TEXT PRIMARY KEY,
  asset TEXT NOT NULL,
  source TEXT NOT NULL,
  tx_hash TEXT,
  amount REAL,
  from_label TEXT,
  to_label TEXT,
  direction TEXT,
  timestamp TEXT,
  raw_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_onchain_events_asset_created_at
ON onchain_events(asset, created_at DESC);
