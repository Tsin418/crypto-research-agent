from __future__ import annotations

import asyncio
from dataclasses import replace

from backend.config import get_settings
from backend.models import LayerResult
from backend.scheduler import safe_run_once
from backend.snapshot_scan import run_snapshot_scan
from backend.storage import Storage


def _settings(tmp_path):
    return replace(
        get_settings(),
        db_path=tmp_path / "research.sqlite3",
        onchain_events_json_path=tmp_path / "onchain_events.jsonl",
        snapshot_scheduler_enabled=True,
        snapshot_scheduler_assets=("BTC",),
        snapshot_scheduler_run_on_startup=False,
    )


def _layer(layer: str, source: str, data: dict, errors: list[str] | None = None) -> LayerResult:
    return LayerResult(layer=layer, source=source, data=data, errors=errors or [])


def test_snapshot_scan_saves_scheduled_snapshots_and_metrics(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path)
    storage = Storage(settings.db_path, settings.onchain_events_json_path)

    async def fake_4h(*_):
        return _layer("market_4h", "test_4h", {"asset": "BTC", "price_change_4h_pct": 1.2})

    async def fake_market(*_):
        return _layer("market", "test_market", {"asset": "BTC", "volume_ratio_vs_7d": 1.5})

    async def fake_derivatives(*_):
        return _layer("derivatives", "test_derivatives", {"funding_rate_now": 0.01})

    async def fake_news(*_args, **_kwargs):
        return _layer("news", "test_news", {"events": [], "top_news": {}})

    async def fake_onchain(*_):
        return _layer("onchain", "test_onchain", {"large_transfer_count": 2})

    async def fake_etf(*_args, **_kwargs):
        return _layer("etf_flow", "test_etf", {"btc_etf_net_flow_usd_m": -10.0})

    monkeypatch.setattr("backend.snapshot_scan.fetch_4h_market_snapshot", fake_4h)
    monkeypatch.setattr("backend.snapshot_scan.fetch_market", fake_market)
    monkeypatch.setattr("backend.snapshot_scan.fetch_derivatives", fake_derivatives)
    monkeypatch.setattr("backend.snapshot_scan.fetch_news", fake_news)
    monkeypatch.setattr("backend.snapshot_scan.fetch_onchain", fake_onchain)
    monkeypatch.setattr("backend.snapshot_scan.fetch_etf_flow", fake_etf)

    result = asyncio.run(run_snapshot_scan(settings, storage, ["BTC"]))

    assert result["status"] == "completed"
    snapshots = storage.list_scheduled_snapshots(asset="BTC", limit=10)
    assert {snapshot["layer"] for snapshot in snapshots} == {
        "market_4h",
        "market",
        "derivatives",
        "news",
        "onchain",
        "etf_flow",
    }
    assert storage.get_metric_history("BTC", "volume_ratio_vs_7d") == [1.5]
    assert storage.get_metric_history("BTC", "funding_rate_now") == [0.01]
    assert storage.get_metric_history("BTC", "large_transfer_count") == [2.0]
    assert storage.get_metric_history("BTC", "btc_etf_net_flow_usd_m") == [-10.0]
    assert storage.list_reports() == []


def test_safe_run_once_logs_scheduler_status(monkeypatch, tmp_path) -> None:
    settings = _settings(tmp_path)
    storage = Storage(settings.db_path, settings.onchain_events_json_path)

    async def fake_scan(*_):
        return {"status": "completed", "results": []}

    monkeypatch.setattr("backend.scheduler.run_snapshot_scan", fake_scan)

    result = asyncio.run(safe_run_once(settings, storage))
    runs = storage.list_scheduler_runs()

    assert result["status"] == "completed"
    assert len(runs) == 1
    assert runs[0]["status"] == "completed"
    assert runs[0]["assets"] == ["BTC"]
