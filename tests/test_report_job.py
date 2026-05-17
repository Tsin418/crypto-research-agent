from __future__ import annotations

import asyncio
from dataclasses import replace

from backend.config import get_settings
from backend.models import Intent, LayerResult, ReportRequest, ResearchContext
from backend.orchestrator import run_report_job
from backend.storage import Storage


def _context(time_window: str = "4h") -> ResearchContext:
    return ResearchContext(
        request=ReportRequest(query="Analyze BTC", asset="BTC", time_window=time_window),
        intent=Intent(asset="BTC", mode="event_attribution", time_window=time_window, user_intent="Analyze BTC"),
        market=LayerResult(layer="market", source="test", data={"price_now": 100, "price_change_4h_pct": 1.2}),
        derivatives=LayerResult(layer="derivatives", source="test", data={}),
        news=LayerResult(layer="news", source="test", data={"top_news": {}}),
        onchain=LayerResult(layer="onchain", source="test", data={}),
        risk={"risk_score": 1, "risk_level": "low"},
        attribution={"event_summary": "ok", "primary_drivers": [], "secondary_drivers": [], "noise": []},
    )


def test_run_report_job_uses_context_time_window(monkeypatch, tmp_path) -> None:
    settings = replace(
        get_settings(),
        db_path=tmp_path / "research.sqlite3",
        onchain_events_json_path=tmp_path / "events.jsonl",
    )
    storage = Storage(settings.db_path, settings.onchain_events_json_path)
    storage.create_report("report-1", "Analyze BTC")
    seen: dict[str, str] = {}

    async def fake_build_context(*_args, **_kwargs):
        return _context("4h")

    async def fake_generate_report(*_args, **_kwargs):
        return "# report"

    def fake_extract_signals(_context, time_window="24h"):
        seen["time_window"] = time_window
        return []

    async def fake_send_feishu(*_args, **_kwargs):
        return None

    monkeypatch.setattr("backend.orchestrator.build_research_context", fake_build_context)
    monkeypatch.setattr("backend.orchestrator.generate_report", fake_generate_report)
    monkeypatch.setattr("backend.orchestrator.extract_normalized_signals", fake_extract_signals)
    monkeypatch.setattr("backend.orchestrator.send_feishu_text", fake_send_feishu)

    asyncio.run(run_report_job(settings, storage, "report-1", ReportRequest(query="Analyze BTC")))

    report = storage.get_report("report-1")
    assert report is not None
    assert report.status == "completed"
    assert report.time_window == "4h"
    assert seen["time_window"] == "4h"
