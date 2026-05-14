from __future__ import annotations

from backend.attribution import build_attribution


def test_attribution_trace_and_data_quality_are_returned() -> None:
    attribution = build_attribution(
        "BTC",
        {
            "price_change_24h_pct": -3.0,
            "price_now": 80000,
            "volume_ratio_vs_7d": 1.8,
            "spot_flow_bias": "sell_pressure",
            "provider": "gate",
        },
        {
            "open_interest_change_24h_pct": -8.0,
            "funding_rate_now": 0.0002,
            "funding_rate_change": 0.0001,
            "long_liquidations_24h": 30.0,
            "short_liquidations_24h": 5.0,
        },
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited", "onchain_evidence_quality": "unknown"},
        {"flow_direction": "unavailable", "source": "unavailable"},
        {"macro_signal": "risk_off", "macro_confidence": "high", "macro_signal_evidence": ["QQQ/Nasdaq proxy fell 1.10%.", "VIX rose 8.60%."]},
    )

    assert attribution["attribution_trace"]
    assert attribution["trace_summary"]["candidates_evaluated"] >= 1
    assert "data_quality" in attribution
    assert "macro" in attribution["data_quality"]
    assert attribution["overall_data_quality_score"] <= 1
    assert attribution["alternative_explanations"]
    first_trace = attribution["attribution_trace"][0]
    assert {"candidate_id", "driver", "source_layer", "final_score", "classification"} <= set(first_trace)


def test_macro_candidate_does_not_dominate_when_unaligned() -> None:
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": 3.0, "price_now": 80000, "volume_ratio_vs_7d": 1.0},
        {},
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
        {},
        {"macro_signal": "risk_off", "macro_confidence": "high", "macro_signal_evidence": ["VIX rose 8.60%."]},
    )

    primary_names = {item["driver"] for item in attribution["primary_drivers"]}
    assert "Macro risk-off pressure" not in primary_names
