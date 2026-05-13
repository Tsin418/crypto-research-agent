from __future__ import annotations


def _liquidity_risk(market: dict) -> int:
    change = market.get("price_change_24h_pct")
    volume_ratio = market.get("volume_ratio_vs_7d")
    if volume_ratio is None:
        return 1
    if volume_ratio < 0.6 and change is not None and abs(change) >= 3:
        return 3
    if volume_ratio < 0.8:
        return 2
    if volume_ratio < 1.0:
        return 1
    return 0


def _leverage_risk(derivatives: dict) -> int:
    funding = derivatives.get("funding_rate_now")
    oi_change = derivatives.get("open_interest_change_24h_pct")
    signal = derivatives.get("derivatives_signal")
    long_liq = derivatives.get("long_liquidations_24h") or 0
    short_liq = derivatives.get("short_liquidations_24h") or 0
    total_liq = long_liq + short_liq
    if signal == "leverage_flush" or (funding is not None and abs(funding) >= 0.001 and oi_change is not None and abs(oi_change) >= 5 and total_liq >= 10_000_000):
        return 3
    if (oi_change is not None and abs(oi_change) >= 5) or total_liq >= 5_000_000:
        return 2
    if funding is not None and abs(funding) >= 0.0005:
        return 1
    return 0


def _news_risk(news: dict) -> int:
    events = news.get("events", [])
    high_bearish = [event for event in events if event.get("impact_level") == "high" and event.get("direction") == "bearish"]
    medium_bearish = [event for event in events if event.get("impact_level") == "medium" and event.get("direction") == "bearish"]
    etf_flow = news.get("etf_flow") or {}
    etf_bearish = (etf_flow.get("latest_detected_flow_usd_m") or 0) < -100
    if len(high_bearish) >= 2:
        return 3
    if high_bearish or len(medium_bearish) >= 2 or etf_bearish:
        return 2
    if medium_bearish or events:
        return 1
    return 0


def _onchain_risk(onchain: dict) -> int:
    transfers = onchain.get("large_transfers", [])
    inflows = [tx for tx in transfers if tx.get("direction") == "potential_sell_pressure"]
    large_transfers = [tx for tx in transfers if str(tx.get("direction", "")).startswith("large_")]
    stable_change = onchain.get("stablecoin_supply_change_24h")
    unstaking = onchain.get("eth_unstaking_queue")
    if len(inflows) >= 3 or len(large_transfers) >= 5 or (stable_change is not None and stable_change < -500_000_000):
        return 3
    if inflows or len(large_transfers) >= 2 or (stable_change is not None and stable_change < -100_000_000) or unstaking:
        return 2
    if transfers or (stable_change is not None and stable_change < 0):
        return 1
    return 0


def risk_level(score: int) -> str:
    if score <= 2:
        return "low"
    if score <= 5:
        return "medium"
    if score <= 8:
        return "medium_high"
    return "high"


def compute_risk(market: dict, derivatives: dict, news: dict, onchain: dict) -> dict:
    breakdown = {
        "liquidity_risk": _liquidity_risk(market),
        "leverage_risk": _leverage_risk(derivatives),
        "news_risk": _news_risk(news),
        "onchain_risk": _onchain_risk(onchain),
    }
    score = sum(breakdown.values())
    top = max(breakdown, key=breakdown.get)
    return {
        "risk_score": score,
        "risk_level": risk_level(score),
        "risk_breakdown": breakdown,
        "risk_summary": f"{top.replace('_', ' ').title()} is the largest current contributor to the risk score.",
    }
