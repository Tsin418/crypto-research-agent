from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from backend.models import StoredReport
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
                """
            )

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
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE reports
                SET status='completed', asset=?, mode=?, time_window=?, report_markdown=?,
                    risk_score=?, risk_level=?, updated_at=?
                WHERE id=?
                """,
                (asset, mode, time_window, report_markdown, risk_score, risk_level, iso_now(), report_id),
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

    def get_report(self, report_id: str) -> StoredReport | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
        if row is None:
            return None
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
            error_message=row["error_message"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
