from __future__ import annotations


def _target_change(market: dict, time_window: str) -> float | None:
    if time_window == "4h":
        return market.get("price_change_4h_pct")
    if time_window == "7d":
        return market.get("price_change_7d_pct")
    return market.get("price_change_24h_pct")


def _liquidity_risk(market: dict, time_window: str = "24h") -> int:
    change = _target_change(market, time_window)
    volume_ratio = market.get("volume_ratio_vs_7d")
    spot_bias = market.get("spot_flow_bias")

    if volume_ratio is None:
        return 1

    score = 0

    if volume_ratio < 0.6 and change is not None and abs(change) >= 3:
        score = max(score, 3)
    elif volume_ratio < 0.8:
        score = max(score, 2)
    elif volume_ratio < 1.0:
        score = max(score, 1)

    if spot_bias == "sell_pressure" and change is not None and change < -2:
        score = max(score, 2)
    elif spot_bias == "sell_pressure":
        score = max(score, 1)

    return score


def _leverage_risk(derivatives: dict) -> int:
    funding = derivatives.get("funding_rate_now")
    oi_change = derivatives.get("open_interest_change_24h_pct")
    signal = derivatives.get("derivatives_signal")
    long_liq = derivatives.get("long_liquidations_24h") or 0
    short_liq = derivatives.get("short_liquidations_24h") or 0
    total_liq = long_liq + short_liq
    put_call_vol = derivatives.get("put_call_volume_ratio")

    score = 0

    if signal == "leverage_flush" or (funding is not None and abs(funding) >= 0.001 and oi_change is not None and abs(oi_change) >= 5 and total_liq >= 10_000_000):
        score = max(score, 3)
    elif (oi_change is not None and abs(oi_change) >= 5) or total_liq >= 5_000_000:
        score = max(score, 2)
    elif funding is not None and abs(funding) >= 0.0005:
        score = max(score, 1)

    if put_call_vol is not None and put_call_vol >= 1.5:
        score = max(score, 2)
    elif put_call_vol is not None and put_call_vol >= 1.2:
        score = max(score, 1)

    return score


def _news_risk(news: dict, etf: dict | None = None) -> int:
    events = news.get("events", [])
    high_bearish = [e for e in events if e.get("impact_level") == "high" and e.get("direction") == "bearish"]
    medium_bearish = [e for e in events if e.get("impact_level") == "medium" and e.get("direction") == "bearish"]

    etf_bearish = False
    if etf:
        etf_latest = etf.get("btc_etf_net_flow_usd_m") or etf.get("net_flow_usd_m_latest")
        etf_bearish = etf_latest is not None and etf_latest < -100

    score = 0
    if len(high_bearish) >= 2:
        score = max(score, 3)
    elif high_bearish or len(medium_bearish) >= 2 or etf_bearish:
        score = max(score, 2)
    elif medium_bearish or events:
        score = max(score, 1)
    return score


def _macro_risk(macro: dict | None) -> int:
    if not macro:
        return 0
    signal = macro.get("macro_signal")
    confidence = macro.get("macro_confidence", "low")
    if signal is None or signal in ("unavailable", "neutral"):
        return 0
    if confidence == "high":
        if signal == "risk_off":
            return 3
        if signal in ("rates_pressure", "dollar_pressure"):
            return 2
        return 1
    if confidence == "medium":
        if signal == "risk_off":
            return 2
        return 1
    return 1


def _onchain_risk(onchain: dict) -> int:
    transfers = onchain.get("large_transfers", [])
    inflows = [tx for tx in transfers if tx.get("direction") == "potential_sell_pressure"]
    large_transfers = [tx for tx in transfers if str(tx.get("direction", "")).startswith("large_")]
    stable_change = onchain.get("stablecoin_supply_change_24h")
    unstaking = onchain.get("eth_unstaking_queue")
    evidence_quality = onchain.get("onchain_evidence_quality")

    score = 0
    if len(inflows) >= 3 or len(large_transfers) >= 5 or (stable_change is not None and stable_change < -500_000_000):
        score = 3
    elif inflows or len(large_transfers) >= 2 or (stable_change is not None and stable_change < -100_000_000) or unstaking:
        score = 2
    elif transfers or (stable_change is not None and stable_change < 0):
        score = 1

    if evidence_quality == "weak" and score >= 2:
        score -= 1
    if evidence_quality == "strong" and score >= 1:
        score = min(3, score + 1)

    return score


def risk_level(score: int) -> str:
    if score <= 2:
        return "low"
    if score <= 6:
        return "medium"
    if score <= 10:
        return "medium_high"
    return "high"


def compute_risk(market: dict, derivatives: dict, news: dict, onchain: dict, etf: dict | None = None, macro: dict | None = None, time_window: str = "24h") -> dict:
    breakdown = {
        "liquidity_risk": _liquidity_risk(market, time_window),
        "leverage_risk": _leverage_risk(derivatives),
        "news_risk": _news_risk(news, etf),
        "onchain_risk": _onchain_risk(onchain),
        "macro_risk": _macro_risk(macro),
    }
    score = sum(breakdown.values())

    # Calculate data coverage
    funding_available = derivatives.get("funding_rate_now") is not None
    oi_available = derivatives.get("open_interest_change_24h_pct") is not None
    liq_available = derivatives.get("long_liquidations_24h") is not None or derivatives.get("short_liquidations_24h") is not None
    derivatives_fields = [funding_available, oi_available, liq_available]
    derivatives_coverage = sum(derivatives_fields) / len(derivatives_fields) if derivatives_fields else 0

    data_coverage = {
        "market": "high" if market.get("price_now") is not None else "low",
        "derivatives": "high" if derivatives_coverage >= 0.66 else "medium" if derivatives_coverage >= 0.33 else "low",
        "news": "medium" if news.get("events") else "low",
        "onchain": "medium" if onchain.get("onchain_signal") else "low",
    }
    missing_data = []
    if not funding_available:
        missing_data.append("funding_rate")
    if not oi_available:
        missing_data.append("open_interest_change")
    if not liq_available:
        missing_data.append("liquidation_data")
    if not onchain.get("exchange_netflow_24h"):
        missing_data.append("labeled_exchange_flows")

    risk_confidence = round(0.85 - (len(missing_data) * 0.12), 2)
    risk_confidence = max(0.25, min(0.90, risk_confidence))

    top = max(breakdown, key=breakdown.get)
    return {
        "risk_score": score,
        "risk_max_score": 15,
        "risk_level": risk_level(score),
        "risk_breakdown": breakdown,
        "risk_summary": f"{top.replace('_', ' ').title()} is the largest current contributor to the risk score.",
        "risk_confidence": risk_confidence,
        "data_coverage": data_coverage,
        "missing_data": missing_data,
    }
