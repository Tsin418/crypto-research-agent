from __future__ import annotations

from backend.data_macro import classify_macro_signal


def test_macro_signal_risk_off() -> None:
    result = classify_macro_signal(
        {"qqq_change_24h_pct": -1.1, "vix_change_24h_pct": 8.6, "dxy_change_24h_pct": 0.2},
        asset_price_change_24h_pct=-3.0,
    )

    assert result["macro_signal"] == "risk_off"
    assert result["macro_confidence"] == "high"
    assert any("VIX rose" in item for item in result["macro_signal_evidence"])


def test_macro_signal_unavailable_when_inputs_missing() -> None:
    result = classify_macro_signal({}, asset_price_change_24h_pct=-3.0)

    assert result["macro_signal"] == "unavailable"
    assert result["macro_confidence"] == "low"
