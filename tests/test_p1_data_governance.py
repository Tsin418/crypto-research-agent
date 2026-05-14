from __future__ import annotations

import asyncio
from dataclasses import replace

from backend.config import get_settings
from backend.data_etf import fetch_etf_flow
from backend.data_market import fetch_market
from backend.models import Intent, LayerResult, ReportRequest, ResearchContext
from backend.report import local_report
from backend.storage import Storage


def test_source_health_rollup_marks_healthy_degraded_and_down(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3")
    for _ in range(10):
        storage.save_api_call_log(
            provider="healthy",
            endpoint="https://example.com/ok",
            status_code=200,
            latency_ms=100,
            error_message=None,
        )
    for status_code, error_message in [(200, None), (200, None), (200, None), (429, "HTTP status 429")]:
        storage.save_api_call_log(
            provider="degraded",
            endpoint="https://example.com/mixed",
            status_code=status_code,
            latency_ms=120,
            error_message=error_message,
        )
    storage.save_api_call_log(
        provider="down",
        endpoint="https://example.com/error",
        status_code=None,
        latency_ms=300,
        error_message="request failed",
    )

    health = {row["provider"]: row for row in storage.get_source_health()}

    assert health["healthy"]["health_status"] == "healthy"
    assert health["degraded"]["health_status"] == "degraded"
    assert health["down"]["health_status"] == "down"
    assert health["healthy"]["success_count"] == 10
    assert health["healthy"]["error_count"] == 0


def test_market_layer_adds_spot_cvd_methodology(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        if source == "coingecko":
            return [
                {
                    "current_price": 100,
                    "price_change_percentage_1h_in_currency": 1,
                    "price_change_percentage_24h_in_currency": 2,
                    "price_change_percentage_7d_in_currency": 3,
                    "total_volume": 700,
                    "market_cap": 1000,
                }
            ], None
        if source == "coingecko_market_chart":
            return {
                "prices": [[index, 100 + index] for index in range(220)],
                "total_volumes": [[index, 700] for index in range(220)],
            }, None
        if source == "bitget_spot_ticker":
            return {"data": [{"quoteVolume": "900", "baseVolume": "9", "lastPr": "100"}]}, None
        if source == "okx_public_trades":
            return {"data": [{"px": "100", "sz": "1", "side": "buy"} for _ in range(6)]}, None
        return None, f"{source}: unexpected call"

    monkeypatch.setattr("backend.data_market.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_spot_flow.get_json", fake_get_json)

    result = asyncio.run(fetch_market(get_settings(), "BTC"))

    assert result.data["data_quality"]["confidence"] == "high"
    assert result.data["spot_cvd_approx_4h_meta"]["warning"] == "Do not describe as exact CVD."


def test_etf_layer_discloses_stale_best_effort_cache(monkeypatch, tmp_path) -> None:
    async def fake_get_text(*_, **__):
        return "<html>Just a moment</html>", None

    cache_path = tmp_path / "etf_flow_cache.json"
    cache_path.write_text(
        '{"net_flow_usd_m_latest": -10, "updated_at": "2024-01-01T00:00:00Z"}',
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.data_etf.get_text", fake_get_text)

    result = asyncio.run(fetch_etf_flow("BTC", cache_path=cache_path))

    assert result.data["data_quality"]["freshness"] == "stale"
    assert "ETF flow best effort" in result.data["btc_etf_net_flow_usd_m_meta"]["warning"]


def test_local_report_includes_p1_methodology_labels() -> None:
    context = ResearchContext(
        request=ReportRequest(query="sample"),
        intent=Intent(asset="BTC", mode="state_scan", time_window="24h", user_intent="sample"),
        market=LayerResult(
            layer="market",
            source="test",
            data={
                "price_now": 80000,
                "price_change_1h_pct": 0.1,
                "price_change_24h_pct": 2.0,
                "price_change_7d_pct": 4.0,
                "volume_24h": 1,
                "volume_ratio_vs_7d": 1.2,
                "ema_20": 79000,
                "ema_50": 78000,
                "ema_200": 70000,
                "market_signal": "uptrend_intact",
                "data_quality": {"freshness": "fresh", "confidence": "high", "warnings": []},
            },
        ),
        derivatives=LayerResult(
            layer="derivatives",
            source="test",
            data={
                "funding_rate_now": 0.0001,
                "open_interest_change_24h_pct": 1,
                "long_liquidations_24h": 10,
                "short_liquidations_24h": 5,
                "derivatives_signal": "spot_driven_or_macro_driven",
                "data_quality": {"freshness": "fresh", "confidence": "medium", "warnings": []},
            },
        ),
        news=LayerResult(layer="news", source="test", data={"events": [], "news_signal": "no_relevant_news_found"}),
        onchain=LayerResult(layer="onchain", source="test", data={"onchain_signal": "btc_onchain_data_limited", "large_transfers": []}),
        risk={"risk_score": 2, "risk_level": "low", "risk_breakdown": {"liquidity_risk": 1, "leverage_risk": 0, "news_risk": 0, "onchain_risk": 1}, "risk_summary": "Low risk."},
        attribution={"event_summary": "BTC moved higher.", "primary_drivers": [], "secondary_drivers": [], "noise": [], "data_quality": {}, "overall_data_quality_score": 0.8},
    )

    report = local_report(context)

    assert "tracked liquidation, not full-market liquidation" in report
    assert "spot CVD approximation, not exact CVD" in report
