from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import httpx

from backend.attribution import build_attribution
from backend.data_etf import fetch_etf_flow
from backend.data_history import enrich_with_history
from backend.data_spot_flow import fetch_spot_flow
from backend.storage import Storage


def test_spot_cvd_falls_back_from_okx_to_gate(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_get_json(*_, source: str, **__):
        calls.append(source)
        if source == "okx_public_trades":
            return None, "okx_public_trades: unavailable"
        if source == "gate_public_trades":
            return [
                {"price": "100", "amount": "1", "side": "sell"},
                {"price": "99", "amount": "1", "side": "sell"},
                {"price": "98", "amount": "1", "side": "sell"},
                {"price": "99", "amount": "0.1", "side": "buy"},
                {"price": "100", "amount": "0.1", "side": "buy"},
            ], None
        return None, f"{source}: unexpected"

    monkeypatch.setattr("backend.data_spot_flow.get_json", fake_get_json)
    async def run():
        async with httpx.AsyncClient() as client:
            return await fetch_spot_flow(client, "BTC")

    result = asyncio.run(run())
    assert result.data["provider"] == "gate"
    assert result.data["spot_flow_bias"] == "sell_pressure"
    assert "okx_public_trades" in calls
    assert "gate_public_trades" in calls
    assert not any("binance" in call for call in calls)


def test_spot_cvd_unavailable_keeps_direction_unconfirmed_attribution(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        return None, f"{source}: unavailable"

    monkeypatch.setattr("backend.data_spot_flow.get_json", fake_get_json)
    async def run():
        async with httpx.AsyncClient() as client:
            return await fetch_spot_flow(client, "BTC")

    spot_flow = asyncio.run(run())
    assert spot_flow.data["spot_flow_bias"] == "unavailable"

    attribution = build_attribution(
        "BTC",
        {
            "price_change_24h_pct": -3.0,
            "price_now": 80000,
            "volume_ratio_vs_7d": 1.8,
            **spot_flow.data,
        },
        {},
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )
    drivers = attribution["primary_drivers"] + attribution["secondary_drivers"]
    assert any(item["driver"] == "Elevated spot activity, direction unconfirmed" for item in drivers)


def test_historical_cold_start_outputs_note(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3")
    for index in range(5):
        storage.save_metric_snapshot(
            asset="BTC",
            layer="market",
            metric_name="volume_ratio_vs_7d",
            metric_value=1.0 + index * 0.01,
        )

    enriched = enrich_with_history(storage, "BTC", "market", {"volume_ratio_vs_7d": 1.8})
    context = enriched["historical_context"]["volume_ratio_vs_7d"]
    assert context["sample_size"] == 5
    assert context["note"] == "Insufficient history; using fixed thresholds."
    assert "zscore_30d" not in context


def test_historical_enrichment_computes_zscore_and_percentile(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3")
    for index in range(30):
        storage.save_metric_snapshot(
            asset="BTC",
            layer="market",
            metric_name="volume_ratio_vs_7d",
            metric_value=1.0 + index * 0.01,
        )

    enriched = enrich_with_history(storage, "BTC", "market", {"volume_ratio_vs_7d": 1.8})
    context = enriched["historical_context"]["volume_ratio_vs_7d"]
    assert context["sample_size"] == 30
    assert context["zscore_30d"] is not None
    assert context["percentile_90d"] >= 0.9

    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": -3.0, "price_now": 80000, **enriched, "spot_flow_bias": "sell_pressure"},
        {},
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )
    spot_driver = next(item for item in attribution["primary_drivers"] + attribution["secondary_drivers"] if item["driver"] == "Spot-led selling pressure")
    assert any("historically unusual" in item for item in spot_driver["supporting_evidence"])


def test_etf_flow_farside_blocked_uses_cache(monkeypatch, tmp_path) -> None:
    async def fake_get_text(*_, **__):
        return "<html>Just a moment</html>", None

    cache_path = tmp_path / "etf_flow_cache.json"
    cache_path.write_text(
        json.dumps(
            {
                "net_flow_usd_m_latest": -320.5,
                "net_flow_usd_m_5d": -820.0,
                "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("backend.data_etf.get_text", fake_get_text)

    result = asyncio.run(fetch_etf_flow("BTC", cache_path=cache_path))
    assert result.source == "local_cache"
    assert result.data["flow_direction"] == "outflow"
    assert result.data["flow_intensity"] == "high"
    assert result.data["is_stale"] is False


def test_unknown_large_transfer_is_secondary_at_most() -> None:
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": -3.0, "price_now": 80000, "volume_ratio_vs_7d": 1.0},
        {},
        {"events": []},
        {
            "onchain_signal": "large_transfer_cluster",
            "onchain_evidence_quality": "weak",
            "onchain_primary_eligible": False,
            "large_transfer_count": 3,
            "exchange_inflow_count": 0,
        },
    )

    onchain_candidates = [
        item
        for item in attribution["primary_drivers"] + attribution["secondary_drivers"]
        if item["driver"] == "Large on-chain transfer activity"
    ]
    assert onchain_candidates
    assert all(item["driver"] != "Large on-chain transfer activity" for item in attribution["primary_drivers"])
    assert onchain_candidates[0]["primary_eligible"] is False
    assert onchain_candidates[0]["onchain_evidence_quality"] == "weak"
