from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.models import MarketScanRecord, StoredReport
from backend.utils import iso_now


class Storage:
    def __init__(self, db_path: Path, onchain_events_json_path: Path | None = None):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.onchain_events_json_path = onchain_events_json_path or self.db_path.parent / "onchain_events.jsonl"
        self.onchain_events_json_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    user_query TEXT NOT NULL,
                    asset TEXT,
                    mode TEXT,
                    time_window TEXT,
                    report_markdown TEXT,
                    risk_score INTEGER,
                    risk_level TEXT,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS raw_data_snapshots (
                    id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    source TEXT,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES reports(id)
                );

                CREATE TABLE IF NOT EXISTS scheduled_snapshots (
                    id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    source TEXT,
                    raw_json TEXT NOT NULL,
                    scan_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_scheduled_snapshots_asset_layer_created
                    ON scheduled_snapshots(asset, layer, created_at DESC);

                CREATE TABLE IF NOT EXISTS scheduler_runs (
                    id TEXT PRIMARY KEY,
                    scan_type TEXT NOT NULL,
                    assets TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_scheduler_runs_created
                    ON scheduler_runs(started_at DESC);

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
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS normalized_signals (
                    id TEXT PRIMARY KEY,
                    report_id TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    signal_name TEXT,
                    signal_value TEXT,
                    direction TEXT,
                    impact_level TEXT,
                    confidence REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(report_id) REFERENCES reports(id)
                );

                CREATE TABLE IF NOT EXISTS api_call_logs (
                    id TEXT PRIMARY KEY,
                    report_id TEXT,
                    provider TEXT,
                    endpoint TEXT,
                    status_code INTEGER,
                    latency_ms INTEGER,
                    error_message TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS liquidation_events (
                    id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT,
                    price REAL,
                    quantity REAL,
                    notional REAL,
                    timestamp_ms INTEGER,
                    raw_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS market_scans (
                    id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    price_now REAL,
                    price_change_4h_pct REAL,
                    direction TEXT NOT NULL,
                    direction_label_zh TEXT NOT NULL,
                    raw_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_market_scans_asset_created
                    ON market_scans(asset, created_at DESC);

                CREATE TABLE IF NOT EXISTS metric_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    layer TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    source TEXT,
                    report_id TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_metric_snapshots_lookup
                    ON metric_snapshots(asset, metric_name, created_at DESC);
                """
            )
            metric_snapshot_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(metric_snapshots)").fetchall()
            }
            if "methodology" not in metric_snapshot_columns:
                conn.execute("ALTER TABLE metric_snapshots ADD COLUMN methodology TEXT")
            if "confidence" not in metric_snapshot_columns:
                conn.execute("ALTER TABLE metric_snapshots ADD COLUMN confidence REAL")
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(reports)").fetchall()
            }
            report_columns = {
                "price_now": "REAL",
                "price_change_4h_pct": "REAL",
                "price_change_24h_pct": "REAL",
                "direction": "TEXT",
                "direction_label_zh": "TEXT",
                "trigger_reason": "TEXT",
                "top_news_title": "TEXT",
                "top_news_url": "TEXT",
                "top_news_source": "TEXT",
                "top_news_json": "TEXT",
            }
            for column, column_type in report_columns.items():
                if column not in existing_columns:
                    conn.execute(f"ALTER TABLE reports ADD COLUMN {column} {column_type}")

    @staticmethod
    def _market_scan_from_row(row: sqlite3.Row) -> MarketScanRecord:
        return MarketScanRecord(
            asset=row["asset"],
            price_now=row["price_now"],
            price_change_4h_pct=row["price_change_4h_pct"],
            direction=row["direction"],
            direction_label_zh=row["direction_label_zh"],
            created_at=row["created_at"],
        )

    def save_market_scan(
        self,
        *,
        asset: str,
        price_now: float | None,
        price_change_4h_pct: float | None,
        direction: str,
        direction_label_zh: str,
        raw_json: dict[str, Any] | None = None,
    ) -> MarketScanRecord:
        created_at = iso_now()
        scan_id = f"market-scan:{asset}:{created_at}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO market_scans
                (id, asset, price_now, price_change_4h_pct, direction,
                 direction_label_zh, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    asset,
                    price_now,
                    price_change_4h_pct,
                    direction,
                    direction_label_zh,
                    json.dumps(raw_json or {}, ensure_ascii=False),
                    created_at,
                ),
            )
            row = conn.execute("SELECT * FROM market_scans WHERE id=?", (scan_id,)).fetchone()
        return self._market_scan_from_row(row)

    def get_latest_market_scan(self, asset: str) -> MarketScanRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM market_scans
                WHERE asset=?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (asset,),
            ).fetchone()
        return self._market_scan_from_row(row) if row else None

    def list_market_scans(self, asset: str | None = None, limit: int = 20) -> list[MarketScanRecord]:
        limit = max(1, min(limit, 100))
        with self._connect() as conn:
            if asset:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scans
                    WHERE asset=?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (asset, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM market_scans
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [self._market_scan_from_row(row) for row in rows]

    def create_report(self, report_id: str, user_query: str) -> None:
        now = iso_now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO reports (id, status, user_query, created_at, updated_at)
                VALUES (?, 'processing', ?, ?, ?)
                """,
                (report_id, user_query, now, now),
            )

    def complete_report(
        self,
        report_id: str,
        *,
        asset: str,
        mode: str,
        time_window: str,
        report_markdown: str,
        risk_score: int,
        risk_level: str,
        price_now: float | None = None,
        price_change_4h_pct: float | None = None,
        price_change_24h_pct: float | None = None,
        direction: str | None = None,
        direction_label_zh: str | None = None,
        trigger_reason: str | None = None,
        top_news: dict[str, Any] | None = None,
    ) -> None:
        top_news = top_news or {}
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE reports
                SET status='completed', asset=?, mode=?, time_window=?, report_markdown=?,
                    risk_score=?, risk_level=?, price_now=?, price_change_4h_pct=?,
                    price_change_24h_pct=?, direction=?, direction_label_zh=?,
                    trigger_reason=?, top_news_title=?, top_news_url=?, top_news_source=?,
                    top_news_json=?, updated_at=?
                WHERE id=?
                """,
                (
                    asset,
                    mode,
                    time_window,
                    report_markdown,
                    risk_score,
                    risk_level,
                    price_now,
                    price_change_4h_pct,
                    price_change_24h_pct,
                    direction,
                    direction_label_zh,
                    trigger_reason,
                    top_news.get("title"),
                    top_news.get("url"),
                    top_news.get("source"),
                    json.dumps(top_news, ensure_ascii=False) if top_news else None,
                    iso_now(),
                    report_id,
                ),
            )

    def fail_report(self, report_id: str, message: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE reports SET status='failed', error_message=?, updated_at=? WHERE id=?",
                (message, iso_now(), report_id),
            )

    def save_snapshot(self, report_id: str, layer: str, source: str, raw_json: dict[str, Any]) -> None:
        snapshot_id = f"{report_id}:{layer}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO raw_data_snapshots
                (id, report_id, layer, source, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (snapshot_id, report_id, layer, source, json.dumps(raw_json), iso_now()),
            )

    def save_scheduled_snapshot(
        self,
        *,
        asset: str,
        layer: str,
        source: str | None,
        raw_json: dict[str, Any],
        scan_type: str = "snapshot",
    ) -> str:
        snapshot_id = f"{scan_type}:{asset}:{layer}:{iso_now()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_snapshots
                (id, asset, layer, source, raw_json, scan_type, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    asset,
                    layer,
                    source,
                    json.dumps(raw_json, ensure_ascii=False),
                    scan_type,
                    iso_now(),
                ),
            )
        return snapshot_id

    def list_scheduled_snapshots(
        self,
        *,
        asset: str | None = None,
        layer: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 500))
        conditions: list[str] = []
        params: list[Any] = []
        if asset:
            conditions.append("asset=?")
            params.append(asset)
        if layer:
            conditions.append("layer=?")
            params.append(layer)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, asset, layer, source, raw_json, scan_type, created_at
                FROM scheduled_snapshots
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "asset": row["asset"],
                "layer": row["layer"],
                "source": row["source"],
                "data": json.loads(row["raw_json"]),
                "scan_type": row["scan_type"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def start_scheduler_run(self, *, scan_type: str, assets: list[str] | tuple[str, ...]) -> str:
        run_id = f"scheduler:{scan_type}:{iso_now()}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduler_runs
                (id, scan_type, assets, status, started_at)
                VALUES (?, ?, ?, 'running', ?)
                """,
                (run_id, scan_type, json.dumps(list(assets)), iso_now()),
            )
        return run_id

    def complete_scheduler_run(self, run_id: str, *, status: str, error_message: str | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE scheduler_runs
                SET status=?, completed_at=?, error_message=?
                WHERE id=?
                """,
                (status, iso_now(), error_message, run_id),
            )

    def list_scheduler_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 100))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, scan_type, assets, status, started_at, completed_at, error_message
                FROM scheduler_runs
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            {
                **dict(row),
                "assets": json.loads(row["assets"]) if row["assets"] else [],
            }
            for row in rows
        ]

    def save_metric_snapshot(
        self,
        *,
        asset: str,
        layer: str,
        metric_name: str,
        metric_value: float | None,
        source: str | None = None,
        report_id: str | None = None,
        methodology: str | None = None,
        confidence: float | None = None,
    ) -> None:
        if metric_value is None:
            return
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO metric_snapshots
                (created_at, asset, layer, metric_name, metric_value, source, report_id,
                 methodology, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (iso_now(), asset, layer, metric_name, metric_value, source, report_id,
                 methodology, confidence),
            )

    def get_metric_history(self, asset: str, metric_name: str, lookback_days: int = 90, limit: int = 500) -> list[float]:
        limit = max(1, min(limit, 1000))
        cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT metric_value FROM metric_snapshots
                WHERE asset=? AND metric_name=?
                  AND created_at >= ?
                  AND metric_value IS NOT NULL
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (asset, metric_name, cutoff, limit),
            ).fetchall()
        return [float(row["metric_value"]) for row in rows if row["metric_value"] is not None]

    def get_report(self, report_id: str) -> StoredReport | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            return None
        top_news_json = None
        if row["top_news_json"]:
            try:
                top_news_json = json.loads(row["top_news_json"])
            except json.JSONDecodeError:
                top_news_json = None
        return StoredReport(
            report_id=row["id"],
            status=row["status"],
            user_query=row["user_query"],
            asset=row["asset"],
            mode=row["mode"],
            time_window=row["time_window"],
            report_markdown=row["report_markdown"],
            risk_score=row["risk_score"],
            risk_level=row["risk_level"],
            price_now=row["price_now"],
            price_change_4h_pct=row["price_change_4h_pct"],
            price_change_24h_pct=row["price_change_24h_pct"],
            direction=row["direction"],
            direction_label_zh=row["direction_label_zh"],
            trigger_reason=row["trigger_reason"],
            top_news_title=row["top_news_title"],
            top_news_url=row["top_news_url"],
            top_news_source=row["top_news_source"],
            top_news_json=top_news_json,
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_reports(self, asset: str | None = None, limit: int = 20, status: str = "completed") -> list[StoredReport]:
        limit = max(1, min(limit, 100))
        status = status.lower()
        with self._connect() as conn:
            if asset:
                if status == "all":
                    rows = conn.execute(
                        """
                        SELECT id FROM reports
                        WHERE asset=?
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (asset, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id FROM reports
                        WHERE asset=? AND status=?
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (asset, status, limit),
                    ).fetchall()
            else:
                if status == "all":
                    rows = conn.execute(
                        """
                        SELECT id FROM reports
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT id FROM reports
                        WHERE status=?
                        ORDER BY updated_at DESC
                        LIMIT ?
                        """,
                        (status, limit),
                    ).fetchall()
        return [report for row in rows if (report := self.get_report(row["id"])) is not None]

    def get_latest_report(self, asset: str, time_window: str | None = None) -> StoredReport | None:
        with self._connect() as conn:
            if time_window:
                row = conn.execute(
                    """
                    SELECT id FROM reports
                    WHERE asset=? AND time_window=? AND status='completed'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (asset, time_window),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT id FROM reports
                    WHERE asset=? AND status='completed'
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (asset,),
                ).fetchone()
        return self.get_report(row["id"]) if row else None

    def get_snapshots(self, report_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT layer, source, raw_json, created_at FROM raw_data_snapshots WHERE report_id=?",
                (report_id,),
            ).fetchall()
        return {
            row["layer"]: {
                "source": row["source"],
                "created_at": row["created_at"],
                "data": json.loads(row["raw_json"]),
            }
            for row in rows
        }

    def _append_onchain_event_json(self, event_id: str, asset: str, source: str, event: dict[str, Any]) -> None:
        record = {
            "id": event_id,
            "asset": asset,
            "source": source,
            "event": event,
            "created_at": iso_now(),
        }
        with self.onchain_events_json_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def save_onchain_event(self, event_id: str, asset: str, source: str, event: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO onchain_events
                (id, asset, source, tx_hash, amount, from_label, to_label, direction,
                 timestamp, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    asset,
                    source,
                    event.get("hash"),
                    event.get("amount"),
                    event.get("from_label"),
                    event.get("to_label"),
                    event.get("direction"),
                    event.get("timestamp"),
                    json.dumps(event),
                    iso_now(),
                ),
            )
            self._append_onchain_event_json(event_id, asset, source, event)

    def get_recent_onchain_events(self, asset: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT raw_json FROM onchain_events
                WHERE asset=?
                ORDER BY COALESCE(timestamp, created_at) DESC
                LIMIT ?
                """,
                (asset, limit),
            ).fetchall()
        return [json.loads(row["raw_json"]) for row in rows]

    def save_normalized_signals(self, report_id: str, signals: list[dict[str, Any]]) -> None:
        with self._lock, self._connect() as conn:
            for index, signal in enumerate(signals):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO normalized_signals
                    (id, report_id, layer, signal_name, signal_value, direction,
                     impact_level, confidence, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{report_id}:signal:{index}",
                        report_id,
                        signal.get("layer"),
                        signal.get("signal_name"),
                        signal.get("signal_value"),
                        signal.get("direction"),
                        signal.get("impact_level"),
                        signal.get("confidence"),
                        iso_now(),
                    ),
                )

    def get_normalized_signals(self, report_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT layer, signal_name, signal_value, direction, impact_level, confidence, created_at
                FROM normalized_signals
                WHERE report_id=?
                ORDER BY created_at ASC, id ASC
                """,
                (report_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_api_call_log(
        self,
        *,
        provider: str,
        endpoint: str,
        status_code: int | None,
        latency_ms: int | None,
        error_message: str | None,
        report_id: str | None = None,
    ) -> None:
        log_id = f"api:{iso_now()}:{provider}:{endpoint}:{status_code}:{latency_ms}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO api_call_logs
                (id, report_id, provider, endpoint, status_code, latency_ms, error_message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, report_id, provider, endpoint, status_code, latency_ms, error_message, iso_now()),
            )

    def get_api_call_logs(self, report_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if report_id:
                rows = conn.execute(
                    """
                    SELECT provider, endpoint, status_code, latency_ms, error_message, created_at
                    FROM api_call_logs
                    WHERE report_id=? OR report_id IS NULL
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (report_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT provider, endpoint, status_code, latency_ms, error_message, created_at
                    FROM api_call_logs
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(row) for row in rows]

    def get_source_health(self, lookback_hours: int = 24) -> list[dict[str, Any]]:
        lookback_hours = max(1, min(lookback_hours, 168))
        cutoff = (datetime.now(UTC) - timedelta(hours=lookback_hours)).isoformat().replace("+00:00", "Z")
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    provider,
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status_code BETWEEN 200 AND 399 AND error_message IS NULL THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status_code BETWEEN 200 AND 399 AND error_message IS NULL THEN 0 ELSE 1 END) AS error_count,
                    AVG(latency_ms) AS avg_latency_ms,
                    MAX(CASE WHEN status_code BETWEEN 200 AND 399 AND error_message IS NULL THEN created_at END) AS last_success_at,
                    MAX(CASE WHEN status_code BETWEEN 200 AND 399 AND error_message IS NULL THEN NULL ELSE created_at END) AS last_error_at
                FROM api_call_logs
                WHERE created_at >= ?
                  AND provider IS NOT NULL
                  AND provider != ''
                GROUP BY provider
                ORDER BY provider ASC
                """,
                (cutoff,),
            ).fetchall()

        now = datetime.now(UTC)
        sources: list[dict[str, Any]] = []
        for row in rows:
            total_count = int(row["total_count"] or 0)
            success_count = int(row["success_count"] or 0)
            error_count = int(row["error_count"] or 0)
            error_rate = error_count / total_count if total_count else 1.0
            last_success_at = row["last_success_at"]
            last_success_dt = None
            if last_success_at:
                try:
                    last_success_dt = datetime.fromisoformat(last_success_at.replace("Z", "+00:00")).astimezone(UTC)
                except ValueError:
                    last_success_dt = None
            success_age_hours = (now - last_success_dt).total_seconds() / 3600 if last_success_dt else None

            if error_rate >= 0.5 or success_count == 0:
                health_status = "down"
            elif error_rate >= 0.1 or success_age_hours is None or success_age_hours > 2:
                health_status = "degraded"
            else:
                health_status = "healthy"

            sources.append(
                {
                    "provider": row["provider"],
                    "success_count": success_count,
                    "error_count": error_count,
                    "avg_latency_ms": round(float(row["avg_latency_ms"] or 0), 2),
                    "last_success_at": last_success_at,
                    "last_error_at": row["last_error_at"],
                    "health_status": health_status,
                }
            )
        return sources

    def save_liquidation_event(self, event_id: str, asset: str, symbol: str, event: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO liquidation_events
                (id, asset, symbol, side, price, quantity, notional, timestamp_ms, raw_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    asset,
                    symbol,
                    event.get("side"),
                    event.get("price"),
                    event.get("quantity"),
                    event.get("notional"),
                    event.get("timestamp_ms"),
                    json.dumps(event),
                    iso_now(),
                ),
            )

    def get_liquidation_stats(self, asset: str, since_ms: int) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT side, SUM(notional) AS total_notional, COUNT(*) AS event_count
                FROM liquidation_events
                WHERE asset=? AND timestamp_ms >= ?
                GROUP BY side
                """,
                (asset, since_ms),
            ).fetchall()
        stats = {"long": {"notional": 0.0, "count": 0}, "short": {"notional": 0.0, "count": 0}}
        for row in rows:
            side = row["side"] if row["side"] in stats else "long"
            stats[side] = {"notional": float(row["total_notional"] or 0), "count": int(row["event_count"] or 0)}
        return stats
