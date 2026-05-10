from __future__ import annotations

from typing import Any


def _signal(layer: str, name: str, value: Any, direction: str, impact: str, confidence: float) -> dict[str, Any]:
    return {
        "layer": layer,
        "signal_name": name,
        "signal_value": "" if value is None else str(value),
        "direction": direction,
        "impact_level": impact,
        "confidence": confidence,
    }


def extract_normalized_signals(context) -> list[dict[str, Any]]:
    market = context.market.data
    derivatives = context.derivatives.data
    news = context.news.data
    onchain = context.onchain.data
    risk = context.risk
    signals: list[dict[str, Any]] = []

    market_direction = "neutral"
    chg24 = market.get("price_change_24h_pct")
    if chg24 is not None:
        if chg24 > 1:
            market_direction = "bullish"
        elif chg24 < -1:
            market_direction = "bearish"
    signals.append(_signal("market", "market_signal", market.get("market_signal"), market_direction, "medium", 0.72))
    signals.append(_signal("market", "volume_ratio_vs_7d", market.get("volume_ratio_vs_7d"), "neutral", "medium", 0.66))

    derivative_signal = derivatives.get("derivatives_signal")
    derivative_direction = "neutral"
    if derivative_signal in {"leverage_flush", "crowded_longs_under_pressure", "sentiment_flip_bearish"}:
        derivative_direction = "bearish"
    signals.append(_signal("derivatives", "derivatives_signal", derivative_signal, derivative_direction, "medium", 0.7))
    signals.append(_signal("derivatives", "put_call_ratio", derivatives.get("put_call_ratio"), "bearish" if (derivatives.get("put_call_ratio") or 0) >= 1.2 else "neutral", "medium", 0.62))
    signals.append(_signal("derivatives", "liquidation_bias", derivatives.get("liquidation_bias"), "bearish" if derivatives.get("liquidation_bias") == "long_flush" else "neutral", "medium", 0.66))

    for event in news.get("events", [])[:8]:
        signals.append(
            _signal(
                "news",
                event.get("category", "news_event"),
                event.get("title"),
                event.get("direction", "neutral"),
                event.get("impact_level", "low"),
                float(event.get("confidence") or 0.55),
            )
        )

    onchain_signal = onchain.get("onchain_signal")
    onchain_direction = "neutral"
    if onchain_signal in {"exchange_inflow_pressure", "liquidity_contraction", "large_transfer_cluster"}:
        onchain_direction = "bearish"
    signals.append(_signal("onchain", "onchain_signal", onchain_signal, onchain_direction, "medium", 0.62))
    signals.append(_signal("onchain", "stablecoin_supply_change_24h", onchain.get("stablecoin_supply_change_24h"), "bearish" if (onchain.get("stablecoin_supply_change_24h") or 0) < 0 else "bullish" if (onchain.get("stablecoin_supply_change_24h") or 0) > 0 else "neutral", "medium", 0.68))
    signals.append(_signal("risk", "risk_score", risk.get("risk_score"), risk.get("risk_level", "neutral"), "high", 0.86))
    return signals
