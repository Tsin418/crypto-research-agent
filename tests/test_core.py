from __future__ import annotations

from backend.attribution import build_attribution
from backend.compliance import is_trading_advice_request
from backend.data_onchain import normalize_alchemy_webhook
from backend.intent import _heuristic_intent
from backend.models import Intent, LayerResult, ReportRequest, ResearchContext
from backend.report import local_report, sanitize_report
from backend.risk import compute_risk
from backend.signals import extract_normalized_signals


def test_heuristic_intent_eth_state_scan() -> None:
    intent = _heuristic_intent(ReportRequest(query="What is the current market state of ETH?"))
    assert intent.asset == "ETH"
    assert intent.mode == "state_scan"
    assert intent.time_window == "24h"


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
    assert events[0]["direction"] == "large_eth_transfer"
    assert events[0]["amount"] == 600


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
