from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest

from backend.attribution import build_attribution
from backend.auto_scan import _is_cache_fresh
from backend.compliance import is_trading_advice_request
from backend.config import get_settings
from backend.data_derivatives import fetch_derivatives
from backend.data_market import classify_4h_direction, fetch_market
from backend.data_news import dedupe_news_events, select_top_news_event
from backend.data_onchain import normalize_alchemy_webhook
from backend.http_client import is_http_forbidden_error
from backend.intent import _heuristic_intent
from backend.models import Intent, LayerResult, ReportRequest, ResearchContext
from backend.orchestrator import build_research_context
from backend.report import local_report, sanitize_report
from backend.risk import compute_risk
from backend.signals import extract_normalized_signals
from backend.storage import Storage


def test_heuristic_intent_eth_state_scan() -> None:
    intent = _heuristic_intent(ReportRequest(query="What is the current market state of ETH?"))
    assert intent.asset == "ETH"
    assert intent.mode == "state_scan"
    assert intent.time_window == "24h"


def test_price_refresh_defaults_to_two_minutes(monkeypatch) -> None:
    monkeypatch.setenv("MARKET_SCAN_CACHE_TTL_MINUTES", "")
    monkeypatch.setenv("SNAPSHOT_SCHEDULER_INTERVAL_MINUTES", "")

    settings = get_settings()

    assert settings.market_scan_cache_ttl_minutes == 2
    assert settings.snapshot_scheduler_interval_minutes == 2


def test_heuristic_intent_next_24_hours_is_not_4h() -> None:
    intent = _heuristic_intent(ReportRequest(query="What risks should I watch for BTC in the next 24 hours?"))
    assert intent.asset == "BTC"
    assert intent.mode == "risk_watch"
    assert intent.time_window == "24h"


def test_risk_score_mapping() -> None:
    risk = compute_risk(
        {"price_change_24h_pct": -4, "volume_ratio_vs_7d": 0.5},
        {"funding_rate_now": -0.001, "open_interest_change_24h_pct": -8, "derivatives_signal": "derivatives_data_limited"},
        {"events": [{"impact_level": "high", "direction": "bearish"}]},
        {"large_transfers": [{"direction": "potential_sell_pressure"}]},
    )
    assert risk["risk_score"] == 9
    assert risk["risk_level"] == "high"


def test_attribution_promotes_secondary_when_no_primary() -> None:
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": -3.2, "price_now": 80000, "volume_ratio_vs_7d": 1.7},
        {"derivatives_signal": "spot_driven_or_macro_driven"},
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )
    assert attribution["primary_drivers"]
    assert attribution["primary_drivers"][0]["driver"] == "Elevated spot activity"


def test_report_sanitizer_adds_disclaimer_and_removes_forbidden_instruction() -> None:
    report = sanitize_report("Buy BTC now. This is guaranteed.")
    assert "[removed: trading instruction]" in report
    assert "This report is for research and educational purposes only." in report


def test_alchemy_webhook_normalization_filters_large_eth_transfers() -> None:
    payload = {
        "event": {
            "activity": [
                {
                    "asset": "ETH",
                    "value": 600,
                    "fromAddress": "0xfrom",
                    "toAddress": "0xto",
                    "hash": "0xhash",
                    "category": "external",
                },
                {"asset": "ETH", "value": 10, "hash": "0xsmall"},
            ]
        }
    }
    events = normalize_alchemy_webhook(payload, threshold_eth=500)
    assert len(events) == 1
    assert events[0]["direction"] == "unknown_transfer"
    assert events[0]["amount"] == 600


def test_onchain_event_storage_writes_sqlite_and_json(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3", tmp_path / "onchain_events.jsonl")
    storage.save_onchain_event(
        "alchemy:0xlarge:600:0",
        "ETH",
        "alchemy_webhook",
        {"hash": "0xlarge", "amount": 600, "direction": "large_eth_transfer"},
    )

    stored = storage.get_recent_onchain_events("ETH")
    assert stored[0]["hash"] == "0xlarge"
    assert "0xlarge" in (tmp_path / "onchain_events.jsonl").read_text(encoding="utf-8")


def _sample_context(mode: str) -> ResearchContext:
    return ResearchContext(
        request=ReportRequest(query="sample"),
        intent=Intent(asset="BTC", mode=mode, time_window="24h", user_intent="sample"),
        market=LayerResult(layer="market", source="test", data={"price_now": 80000, "price_change_1h_pct": 0.1, "price_change_24h_pct": 2.0, "price_change_7d_pct": 4.0, "volume_24h": 1, "volume_ratio_vs_7d": 1.2, "ema_20": 79000, "ema_50": 78000, "ema_200": 70000, "market_signal": "uptrend_intact"}),
        derivatives=LayerResult(layer="derivatives", source="test", data={"funding_rate_now": 0.0001, "open_interest_change_24h_pct": 1, "derivatives_signal": "spot_driven_or_macro_driven"}),
        news=LayerResult(layer="news", source="test", data={"events": [], "news_signal": "no_relevant_news_found"}),
        onchain=LayerResult(layer="onchain", source="test", data={"onchain_signal": "btc_onchain_data_limited", "large_transfers": []}),
        risk={"risk_score": 2, "risk_level": "low", "risk_breakdown": {"liquidity_risk": 1, "leverage_risk": 0, "news_risk": 0, "onchain_risk": 1}, "risk_summary": "Low risk."},
        attribution={"event_summary": "BTC moved higher.", "primary_drivers": [{"driver": "Momentum", "explanation": "Price is higher.", "confidence": 0.7, "evidence": ["market"]}], "secondary_drivers": [], "noise": []},
    )


def test_trading_advice_request_is_detected() -> None:
    assert is_trading_advice_request("Should I buy BTC now?")
    assert not is_trading_advice_request("Analyze BTC market state today")


def test_mode_specific_local_reports() -> None:
    state_report = local_report(_sample_context("state_scan"))
    risk_report = local_report(_sample_context("risk_watch"))
    assert "## Bullish Factors" in state_report
    assert "## Key Risks" in risk_report
    assert "## Primary Drivers" not in risk_report


def test_extract_normalized_signals() -> None:
    signals = extract_normalized_signals(_sample_context("event_attribution"))
    names = {signal["signal_name"] for signal in signals}
    assert "market_signal" in names
    assert "risk_score" in names

from backend.liquidations import normalize_bybit_liquidation


def test_bybit_liquidation_normalization() -> None:
    event = normalize_bybit_liquidation({"s": "BTCUSDT", "S": "Sell", "p": "80000", "v": "0.5", "T": 1000})
    assert event is not None
    assert event["asset"] == "BTC"
    assert event["side"] == "long"
    assert event["notional"] == 40000


def test_http_forbidden_error_detection() -> None:
    assert is_http_forbidden_error("bybit_kline: HTTPStatusError: Client error '403 Forbidden'")
    assert not is_http_forbidden_error("coingecko: HTTPStatusError: Client error '429 Too Many Requests'")


def test_market_uses_bitget_spot_turnover_first(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_get_json(*_, source: str, **__):
        calls.append(source)
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
        return None, f"{source}: unexpected call"

    monkeypatch.setattr("backend.data_market.get_json", fake_get_json)
    result = asyncio.run(fetch_market(get_settings(), "BTC"))

    assert result.errors == []
    assert result.data["technical_source"] == "coingecko_market_chart"
    assert result.data["spot_turnover_24h"] == 900
    assert result.data["spot_turnover_source"] == "bitget_spot"
    assert result.data["bitget_spot_available"] is True
    assert "bybit_kline" not in calls


@pytest.mark.parametrize(
    ("successful_source", "expected_source", "payload", "turnover"),
    [
        ("gate_spot_ticker", "gate_spot", [{"quote_volume": "800", "base_volume": "8", "last": "100"}], 800),
        ("okx_spot_ticker", "okx_spot", {"data": [{"volCcy24h": "700", "vol24h": "7", "last": "100"}]}, 700),
        ("binance_spot_ticker", "binance_spot", {"quoteVolume": "600", "volume": "6", "lastPrice": "100"}, 600),
    ],
)
def test_spot_turnover_falls_back_by_priority(monkeypatch, successful_source, expected_source, payload, turnover) -> None:
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
        if source == successful_source:
            return payload, None
        if source in {"bitget_spot_ticker", "gate_spot_ticker", "okx_spot_ticker"}:
            return None, f"{source}: unavailable"
        return None, f"{source}: unexpected call"

    monkeypatch.setattr("backend.data_market.get_json", fake_get_json)
    result = asyncio.run(fetch_market(get_settings(), "BTC"))

    assert result.errors == []
    assert result.data["spot_turnover_source"] == expected_source
    assert result.data["spot_turnover_24h"] == turnover


def test_derivatives_does_not_call_bybit_when_replacement_succeeds(monkeypatch) -> None:
    calls: list[str] = []

    async def fake_get_json(*_, source: str, **__):
        calls.append(source)
        if source == "mexc_contract_ticker":
            return {
                "data": {
                    "symbol": "BTC_USDT",
                    "fundingRate": "0.0004",
                    "holdVol": "1000",
                    "fairPrice": "101",
                    "indexPrice": "100",
                    "amount24": "2000",
                }
            }, None
        return None, f"{source}: HTTPStatusError: Client error '403 Forbidden'"

    async def fake_deribit_perpetual(*_):
        return {}, []

    async def fake_hyperliquid(*_):
        return {}, []

    async def fake_options(*_):
        return {"put_call_ratio": 0.8, "put_call_volume_ratio": 0.9}, []

    monkeypatch.setattr("backend.data_derivatives.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_derivatives._fetch_deribit_perpetual", fake_deribit_perpetual)
    monkeypatch.setattr("backend.data_derivatives._fetch_hyperliquid_perpetual", fake_hyperliquid)
    monkeypatch.setattr("backend.data_derivatives.fetch_deribit_put_call", fake_options)

    result = asyncio.run(fetch_derivatives(replace(get_settings(), coinalyze_api_key=""), "BTC"))

    assert result.errors == []
    assert result.data["mexc_contract_available"] is True
    assert result.data["funding_rate_now"] == 0.0004
    assert result.data["bybit_available"] is False
    assert "bybit_tickers" not in calls


def test_derivatives_prefers_mexc_over_lower_priority_sources(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        if source == "mexc_contract_ticker":
            return {
                "data": {
                    "symbol": "BTC_USDT",
                    "fundingRate": "0.0003",
                    "holdVol": "1000",
                    "fairPrice": "101",
                    "indexPrice": "100",
                    "amount24": "2000",
                }
            }, None
        if source == "bitget_contract_funding":
            return {"data": [{"fundingRate": "0.001"}]}, None
        if source == "bitget_contract_open_interest":
            return {"data": {"openInterest": "3"}}, None
        if source == "bitget_contract_ticker":
            return {"data": [{"markPrice": "100", "indexPrice": "100", "quoteVolume": "500"}]}, None
        if source == "okx_contract_funding":
            return {"data": [{"fundingRate": "0.002"}]}, None
        if source == "okx_contract_open_interest":
            return {"data": [{"oiCcy": "4"}]}, None
        if source == "okx_contract_ticker":
            return {"data": [{"last": "100", "volCcy24h": "600"}]}, None
        if source in {"gate_futures_ticker", "gate_futures_contract"}:
            return {}, None
        if source == "coingecko_derivatives":
            return [], None
        return {}, None

    async def fake_deribit_perpetual(*_):
        return {"funding_rate_now": 0.004, "open_interest_now": 4000, "basis_pct": 4.0}, []

    async def fake_hyperliquid(*_):
        return {"funding_rate_now": 0.005, "open_interest_now": 5000, "basis_pct": 5.0}, []

    async def fake_options(*_):
        return {"put_call_ratio": 0.8, "put_call_volume_ratio": 0.9}, []

    monkeypatch.setattr("backend.data_derivatives.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_derivatives._fetch_deribit_perpetual", fake_deribit_perpetual)
    monkeypatch.setattr("backend.data_derivatives._fetch_hyperliquid_perpetual", fake_hyperliquid)
    monkeypatch.setattr("backend.data_derivatives.fetch_deribit_put_call", fake_options)

    result = asyncio.run(fetch_derivatives(replace(get_settings(), coinalyze_api_key=""), "BTC"))

    assert result.errors == []
    assert result.data["mexc_contract_available"] is True
    assert result.data["bitget_contract_available"] is True
    assert result.data["funding_rate_now"] == 0.0003
    assert result.data["open_interest_now"] == 1000
    assert result.data["basis_pct"] == 1.0


def test_derivatives_fills_missing_mexc_fields_from_bitget(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        if source == "mexc_contract_ticker":
            return {"data": {"symbol": "BTC_USDT", "fairPrice": "101", "indexPrice": "100"}}, None
        if source == "bitget_contract_funding":
            return {"data": [{"fundingRate": "0.0005"}]}, None
        if source == "bitget_contract_open_interest":
            return {"data": {"openInterest": "3"}}, None
        if source == "bitget_contract_ticker":
            return {"data": [{"markPrice": "100", "indexPrice": "100", "quoteVolume": "500"}]}, None
        if source in {
            "okx_contract_funding",
            "okx_contract_open_interest",
            "okx_contract_ticker",
            "gate_futures_ticker",
            "gate_futures_contract",
        }:
            return {}, None
        if source == "coingecko_derivatives":
            return [], None
        return {}, None

    async def fake_deribit_perpetual(*_):
        return {}, []

    async def fake_hyperliquid(*_):
        return {}, []

    async def fake_options(*_):
        return {}, []

    monkeypatch.setattr("backend.data_derivatives.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_derivatives._fetch_deribit_perpetual", fake_deribit_perpetual)
    monkeypatch.setattr("backend.data_derivatives._fetch_hyperliquid_perpetual", fake_hyperliquid)
    monkeypatch.setattr("backend.data_derivatives.fetch_deribit_put_call", fake_options)

    result = asyncio.run(fetch_derivatives(replace(get_settings(), coinalyze_api_key=""), "BTC"))

    assert result.errors == []
    assert result.data["basis_pct"] == 1.0
    assert result.data["funding_rate_now"] == 0.0005
    assert result.data["open_interest_now"] == 300


def test_derivatives_uses_coinalyze_when_direct_sources_are_missing(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        if source in {
            "mexc_contract_ticker",
            "bitget_contract_funding",
            "bitget_contract_open_interest",
            "bitget_contract_ticker",
            "okx_contract_funding",
            "okx_contract_open_interest",
            "okx_contract_ticker",
            "gate_futures_ticker",
            "gate_futures_contract",
        }:
            return {}, None
        if source == "coingecko_derivatives":
            return [], None
        if source == "coinalyze_future_markets":
            return [
                {
                    "symbol": "BTCUSDT_PERP.OKX",
                    "exchange": "OKX",
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "market_type": "perpetual",
                }
            ], None
        if source == "coinalyze_funding_rate":
            return [{"symbol": "BTCUSDT_PERP.OKX", "value": 0.0003}], None
        if source == "coinalyze_funding_history":
            return [{"symbol": "BTCUSDT_PERP.OKX", "history": [{"t": 1, "c": 0.0001}, {"t": 2, "c": 0.0003}]}], None
        if source == "coinalyze_open_interest":
            return [{"symbol": "BTCUSDT_PERP.OKX", "value": 1000}], None
        if source == "coinalyze_open_interest_history":
            return [{"symbol": "BTCUSDT_PERP.OKX", "history": [{"t": 1, "c": 900}, {"t": 2, "c": 1000}]}], None
        if source == "coinalyze_liquidation_history":
            return [{"symbol": "BTCUSDT_PERP.OKX", "history": [{"t": 1, "l": 10, "s": 2}, {"t": 2, "l": 5, "s": 1}]}], None
        return {}, None

    async def fake_deribit_perpetual(*_):
        return {"funding_rate_now": 0.002, "open_interest_now": 3000, "basis_pct": 2.0}, []

    async def fake_hyperliquid(*_):
        return {"funding_rate_now": 0.003, "open_interest_now": 4000, "basis_pct": 3.0}, []

    async def fake_options(*_):
        return {"put_call_ratio": 0.8, "put_call_volume_ratio": 0.9}, []

    settings = replace(get_settings(), coinalyze_api_key="test-key")
    monkeypatch.setattr("backend.data_derivatives.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_derivatives._fetch_deribit_perpetual", fake_deribit_perpetual)
    monkeypatch.setattr("backend.data_derivatives._fetch_hyperliquid_perpetual", fake_hyperliquid)
    monkeypatch.setattr("backend.data_derivatives.fetch_deribit_put_call", fake_options)

    result = asyncio.run(fetch_derivatives(settings, "BTC"))

    assert result.errors == []
    assert result.data["coinalyze_available"] is True
    assert result.data["bybit_available"] is False
    assert result.data["funding_rate_now"] == 0.0003
    assert result.data["open_interest_now"] == 1000
    assert result.data["open_interest_change_24h_pct"] == 11.11
    assert result.data["long_liquidations_24h"] == 15
    assert result.data["short_liquidations_24h"] == 3
    assert result.data["liquidation_bias"] == "long_flush"


def test_derivatives_uses_deribit_and_hyperliquid_fallbacks(monkeypatch) -> None:
    async def fake_get_json(*_, source: str, **__):
        if source in {
            "mexc_contract_ticker",
            "bitget_contract_funding",
            "bitget_contract_open_interest",
            "bitget_contract_ticker",
            "okx_contract_funding",
            "okx_contract_open_interest",
            "okx_contract_ticker",
            "gate_futures_ticker",
            "gate_futures_contract",
        }:
            return {}, None
        if source == "coingecko_derivatives":
            return [], None
        return None, f"{source}: HTTPStatusError: Client error '403 Forbidden'"

    async def fake_deribit_perpetual(*_):
        return {
            "funding_rate_now": 0.0002,
            "funding_rate_8h_ago": 0.0001,
            "funding_rate_change": 0.0001,
            "open_interest_now": 1200,
            "basis_pct": 0.4,
        }, []

    async def fake_hyperliquid(*_):
        return {
            "funding_rate_now": 0.0005,
            "open_interest_now": 2200,
            "basis_pct": 0.7,
        }, []

    async def fake_options(*_):
        return {"put_call_ratio": 1.1, "put_call_volume_ratio": 1.2}, []

    monkeypatch.setattr("backend.data_derivatives.get_json", fake_get_json)
    monkeypatch.setattr("backend.data_derivatives._fetch_deribit_perpetual", fake_deribit_perpetual)
    monkeypatch.setattr("backend.data_derivatives._fetch_hyperliquid_perpetual", fake_hyperliquid)
    monkeypatch.setattr("backend.data_derivatives.fetch_deribit_put_call", fake_options)

    result = asyncio.run(fetch_derivatives(replace(get_settings(), coinalyze_api_key=""), "ETH"))

    assert result.errors == []
    assert result.data["bybit_available"] is False
    assert result.data["deribit_perpetual_available"] is True
    assert result.data["hyperliquid_available"] is True
    assert result.data["funding_rate_now"] == 0.0002
    assert result.data["open_interest_now"] == 1200
    assert result.data["basis_pct"] == 0.4
    assert result.data["hyperliquid_perpetual"]["open_interest_now"] == 2200


def test_4h_direction_classification() -> None:
    rising = classify_4h_direction("BTC", 1.4, 1.0, -1.0)
    falling = classify_4h_direction("ETH", -1.4, 1.0, -1.0)
    neutral = classify_4h_direction("BTC", 0.3, 1.0, -1.0)

    assert rising["direction"] == "rising"
    assert rising["direction_label_zh"] == "上涨"
    assert falling["direction"] == "falling"
    assert falling["direction_label_zh"] == "下跌"
    assert neutral["direction"] == "neutral"
    assert neutral["direction_label_zh"] == "震荡"


def test_research_context_merges_4h_market_snapshot(monkeypatch, tmp_path) -> None:
    async def fake_parse_intent(*_):
        return Intent(asset="ETH", mode="event_attribution", time_window="4h", user_intent="sample")

    async def fake_market_4h(*_):
        return LayerResult(
            layer="market_4h",
            source="coingecko",
            data={
                "asset": "ETH",
                "price_change_4h_pct": -1.25,
                "direction": "falling",
                "direction_label_zh": "下跌",
                "trigger_reason": "ETH 过去 4 小时下跌 1.25%",
            },
        )

    async def fake_market(*_):
        return LayerResult(
            layer="market",
            source="market",
            data={"asset": "ETH", "price_now": 2200, "price_change_24h_pct": -2, "volume_ratio_vs_7d": 1.1},
        )

    async def fake_derivatives(*_):
        return LayerResult(layer="derivatives", source="derivatives", data={"derivatives_signal": "derivatives_data_limited"})

    async def fake_news(*_):
        return LayerResult(layer="news", source="news", data={"events": [], "top_news": {}, "news_signal": "no_relevant_news_found"})

    async def fake_onchain(*_):
        return LayerResult(layer="onchain", source="onchain", data={"onchain_signal": "eth_onchain_data_limited", "large_transfers": []})

    async def fake_etf(*_, **__):
        return LayerResult(layer="etf_flow", source="unavailable", data={"etf_flow_signal": "etf_flow_unavailable"})

    async def fake_macro(*_):
        return LayerResult(layer="macro", source="macro", data={"macro_signal": "unavailable"})

    monkeypatch.setattr("backend.orchestrator.parse_intent", fake_parse_intent)
    monkeypatch.setattr("backend.orchestrator.fetch_4h_market_snapshot", fake_market_4h)
    monkeypatch.setattr("backend.orchestrator.fetch_market", fake_market)
    monkeypatch.setattr("backend.orchestrator.fetch_derivatives", fake_derivatives)
    monkeypatch.setattr("backend.orchestrator.fetch_news", fake_news)
    monkeypatch.setattr("backend.orchestrator.fetch_onchain", fake_onchain)
    monkeypatch.setattr("backend.orchestrator.fetch_etf_flow", fake_etf)
    monkeypatch.setattr("backend.orchestrator.fetch_macro_context", fake_macro)

    storage = Storage(tmp_path / "research.sqlite3", tmp_path / "events.jsonl")
    context = asyncio.run(build_research_context(get_settings(), ReportRequest(query="ETH 4h", asset="ETH", time_window="4h"), storage))

    assert context.market.data["price_change_4h_pct"] == -1.25
    assert context.market.data["direction"] == "falling"
    assert context.market.data["direction_label_zh"] == "下跌"
    assert context.market.data["four_hour_layer_source"] == "coingecko"


def test_report_cache_ttl_behavior(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3", tmp_path / "events.jsonl")
    storage.create_report("fresh", "BTC 4h")
    storage.complete_report(
        "fresh",
        asset="BTC",
        mode="state_scan",
        time_window="4h",
        report_markdown="ok",
        risk_score=1,
        risk_level="low",
    )

    assert _is_cache_fresh(storage.get_latest_report("BTC", "4h"), ttl_minutes=15)
    assert not _is_cache_fresh(storage.get_latest_report("BTC", "4h"), ttl_minutes=-1)


def test_history_retrieval_with_auto_scan_fields(tmp_path) -> None:
    storage = Storage(tmp_path / "research.sqlite3", tmp_path / "events.jsonl")
    storage.create_report("btc-report", "BTC 4h")
    storage.complete_report(
        "btc-report",
        asset="BTC",
        mode="state_scan",
        time_window="4h",
        report_markdown="# BTC",
        risk_score=2,
        risk_level="low",
        price_now=103000,
        price_change_4h_pct=-1.4,
        direction="falling",
        direction_label_zh="下跌",
        top_news={"title": "ETF flow changes", "url": "https://example.com", "source": "test"},
    )

    reports = storage.list_reports("BTC", limit=20)

    assert len(reports) == 1
    assert reports[0].asset == "BTC"
    assert reports[0].price_change_4h_pct == -1.4
    assert reports[0].top_news_json["title"] == "ETF flow changes"


def test_news_dedup_output_shape() -> None:
    events = [
        {
            "title": "Bitcoin ETF sees record inflow",
            "url": "https://example.com/story?utm=1",
            "source": "A",
            "impact_level": "high",
            "direction": "bullish",
        },
        {
            "title": "Bitcoin ETF sees record inflow",
            "url": "https://example.com/story?utm=2",
            "source": "B",
            "impact_level": "high",
            "direction": "bullish",
        },
    ]

    deduped = dedupe_news_events(events)
    selected = asyncio.run(select_top_news_event(None, deduped, "BTC"))

    assert len(deduped) == 1
    assert set(selected) >= {"title", "url", "source", "related_assets", "impact_level", "direction", "reason_zh"}
    assert selected["related_assets"] == ["BTC"]
