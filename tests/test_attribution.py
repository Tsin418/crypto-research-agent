from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.attribution import build_attribution


def test_post_move_news_should_not_be_primary() -> None:
    future_news_time = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": -4.0, "price_now": 80000, "volume_ratio_vs_7d": 1.0},
        {"derivatives_signal": "spot_driven_or_macro_driven"},
        {
            "events": [
                {
                    "title": "BTC falls as investors de-risk",
                    "published_at": future_news_time,
                    "direction": "bearish",
                    "impact_level": "high",
                    "asset_related": ["BTC"],
                    "category": "market_commentary",
                }
            ]
        },
        {"onchain_signal": "btc_onchain_data_limited"},
    )

    primary_titles = [item["driver"] for item in attribution["primary_drivers"]]
    assert not any("BTC falls as investors de-risk" in title for title in primary_titles)
    news_candidate = next(item for item in attribution["secondary_drivers"] if "BTC falls as investors de-risk" in item["driver"])
    assert news_candidate["causal_timing"] == "after_move"
    assert news_candidate["primary_eligible"] is False
    assert any("post-move commentary" in item for item in news_candidate["counter_evidence"])
    assert attribution["quality_check"]["post_move_news_promoted"] is False


def test_long_leverage_flush_is_primary_driver() -> None:
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": -5.0, "price_now": 80000, "volume_ratio_vs_7d": 1.1},
        {
            "open_interest_change_24h_pct": -8.0,
            "funding_rate_now": 0.0002,
            "funding_rate_change": 0.0001,
            "long_liquidations_24h": 30.0,
            "short_liquidations_24h": 5.0,
        },
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )

    primary = attribution["primary_drivers"][0]
    assert primary["driver"] == "Long leverage flush"
    assert primary["derivatives_regime"] == "long_leverage_flush"
    assert primary["causality_level"] in {"plausible", "confirmed"}
    assert "confidence_breakdown" in primary


def test_short_squeeze_is_bullish_derivatives_regime() -> None:
    attribution = build_attribution(
        "ETH",
        {"price_change_24h_pct": 4.0, "price_now": 3500, "volume_ratio_vs_7d": 1.1},
        {
            "open_interest_change_24h_pct": -7.0,
            "funding_rate_now": -0.0002,
            "funding_rate_change": -0.0001,
            "long_liquidations_24h": 4.0,
            "short_liquidations_24h": 25.0,
        },
        {"events": []},
        {"onchain_signal": "eth_onchain_data_limited"},
    )

    drivers = attribution["primary_drivers"] + attribution["secondary_drivers"]
    squeeze = next(item for item in drivers if item.get("derivatives_regime") == "short_squeeze")
    assert squeeze["driver"] == "Short squeeze"
    assert squeeze["direction"] == "bullish"
    assert any("Short liquidations materially exceeded long liquidations." in item for item in squeeze["supporting_evidence"])


def test_missing_liquidation_data_allows_weaker_possible_deleveraging() -> None:
    full_flush = build_attribution(
        "BTC",
        {"price_change_24h_pct": -5.0, "price_now": 80000, "volume_ratio_vs_7d": 1.1},
        {
            "open_interest_change_24h_pct": -8.0,
            "funding_rate_now": 0.0002,
            "funding_rate_change": 0.0001,
            "long_liquidations_24h": 30.0,
            "short_liquidations_24h": 5.0,
        },
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )
    missing_liq = build_attribution(
        "BTC",
        {"price_change_24h_pct": -5.0, "price_now": 80000, "volume_ratio_vs_7d": 1.1},
        {
            "open_interest_change_24h_pct": -8.0,
            "funding_rate_now": 0.0002,
            "funding_rate_change": 0.0001,
        },
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )

    candidate = missing_liq["primary_drivers"][0]
    assert candidate["driver"] == "Possible deleveraging"
    assert candidate["derivatives_regime"] == "possible_deleveraging"
    assert "Liquidation data unavailable." in candidate["missing_evidence"]
    assert candidate["confidence"] < full_flush["primary_drivers"][0]["confidence"]


def test_no_strong_evidence_returns_insufficient_evidence() -> None:
    attribution = build_attribution(
        "BTC",
        {"price_change_24h_pct": 0.4, "price_now": 80000, "volume_ratio_vs_7d": 1.0},
        {"derivatives_signal": "derivatives_data_limited"},
        {"events": []},
        {"onchain_signal": "btc_onchain_data_limited"},
    )

    assert attribution["primary_drivers"][0]["driver"] == "Insufficient confirmed evidence"
    assert attribution["quality_check"]["insufficient_evidence"] is True
