from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _driver(name: str, evidence: list[str], explanation: str, confidence: float, score: float = 0.0) -> dict:
    return {
        "driver": name,
        "evidence": evidence,
        "explanation": explanation,
        "confidence": round(confidence, 2),
        "score": round(score, 2),
    }


def _candidate(name: str, evidence: list[str], explanation: str, score: float, confidence: float) -> dict[str, Any]:
    return _driver(name, evidence, explanation, confidence, score)


def _news_candidates(asset: str, market_change: float | None, news: dict) -> tuple[list[dict], list[dict]]:
    candidates: list[dict] = []
    noise: list[dict] = []
    price_direction = "bearish" if market_change is not None and market_change < 0 else "bullish" if market_change is not None and market_change > 0 else "neutral"
    for event in news.get("events", [])[:12]:
        direction = event.get("direction", "neutral")
        impact = event.get("impact_level", "low")
        related = event.get("asset_related", [])
        score = 0.0
        evidence = ["news"]
        if asset in related:
            score += 1.0
        if impact == "high":
            score += 1.0
        elif impact == "medium":
            score += 0.5
        if direction == price_direction and direction != "neutral":
            score += 1.0
        if event.get("category") == "etf_flow" and asset == "BTC":
            score += 0.5
            evidence.append("etf_flow")
        published = _parse_time(event.get("published_at"))
        if published:
            hours_old = (datetime.now(UTC) - published).total_seconds() / 3600
            if hours_old <= 4:
                score += 0.5
            elif hours_old > 24:
                score -= 1.0
        if score >= 1.5 and direction != "neutral":
            if direction == price_direction and direction != "neutral":
                explanation = event.get("reason") or f"A {impact} {direction} news item is asset-relevant and directionally aligned with the move."
            else:
                explanation = event.get("reason") or f"A {impact} {direction} news item is asset-relevant, but it is not directionally aligned with the latest 24h price move, so it is supporting context rather than a confirmed driver."
            candidates.append(
                _candidate(
                    f"{event.get('category', 'news_event').replace('_', ' ').title()}: {event.get('title')}",
                    evidence,
                    explanation,
                    score,
                    min(0.9, 0.45 + score * 0.12),
                )
            )
        elif impact == "low" or direction == "neutral":
            noise.append(
                {
                    "driver": event.get("title") or "Low-impact news",
                    "reason": "The item is low impact, neutral, stale, or not directionally confirmed by other layers.",
                    "confidence": 0.52,
                }
            )
    return candidates, noise


def build_attribution(asset: str, market: dict, derivatives: dict, news: dict, onchain: dict) -> dict:
    candidates: list[dict] = []
    noise: list[dict] = []
    market_change = market.get("price_change_24h_pct")
    volume_ratio = market.get("volume_ratio_vs_7d")
    price = market.get("price_now")
    event_summary = (
        f"{asset} moved {market_change:.2f}% over the last 24h. Current spot reference price is ${price:,.2f}."
        if market_change is not None and price
        else f"{asset} market data is limited for this window."
    )

    if volume_ratio is not None and volume_ratio >= 1.5 and market_change is not None and abs(market_change) >= 2:
        candidates.append(
            _candidate(
                "Elevated spot activity",
                ["market_volume", "price_change"],
                "The price move is accompanied by volume at least 1.5x the recent average, suggesting real spot participation.",
                2.2,
                0.72,
            )
        )

    derivative_signal = derivatives.get("derivatives_signal")
    long_liq = derivatives.get("long_liquidations_24h") or 0
    short_liq = derivatives.get("short_liquidations_24h") or 0
    oi_change = derivatives.get("open_interest_change_24h_pct")
    if derivative_signal in {"leverage_flush", "sentiment_flip_bearish", "crowded_longs_under_pressure"} or long_liq or short_liq:
        score = 1.0
        evidence = ["funding_rate", "open_interest", "bybit"]
        if oi_change is not None and abs(oi_change) >= 5:
            score += 1.0
        if long_liq or short_liq:
            score += 1.0
            evidence.append("liquidations")
        if derivative_signal == "leverage_flush":
            score += 0.8
        candidates.append(
            _candidate(
                "Derivatives leverage pressure",
                evidence,
                "Funding, open interest, and Bybit liquidation data indicate positioning stress rather than a purely spot-driven move.",
                score,
                min(0.9, 0.5 + score * 0.12),
            )
        )

    put_call = derivatives.get("put_call_ratio")
    if put_call is not None and put_call >= 1.2:
        candidates.append(
            _candidate(
                "Options downside hedging demand",
                ["deribit_options", "put_call_ratio"],
                "Deribit put/call open interest is elevated, indicating relatively stronger downside hedging demand.",
                1.4,
                0.62,
            )
        )

    news_candidates, news_noise = _news_candidates(asset, market_change, news)
    candidates.extend(news_candidates)
    noise.extend(news_noise)

    onchain_signal = onchain.get("onchain_signal")
    if onchain_signal == "exchange_inflow_pressure":
        candidates.append(
            _candidate(
                "Potential exchange inflow pressure",
                ["onchain_transfers", "address_labels"],
                "Large transfers include exchange-bound flows, which can signal potential sell pressure.",
                2.0,
                0.68,
            )
        )
    elif onchain_signal in {"large_transfer_cluster", "large_transfer_activity"}:
        candidates.append(
            _candidate(
                "Large on-chain transfer activity",
                ["alchemy_webhooks", "etherscan", "mempool.space"],
                "Large BTC/ETH transfers were detected, but wallet labels are limited so this is supporting context rather than confirmed sell pressure.",
                1.2,
                0.58,
            )
        )
    elif onchain_signal == "liquidity_contraction":
        candidates.append(
            _candidate(
                "Stablecoin liquidity contraction",
                ["defillama_stablecoins"],
                "USDT/USDC supply change is negative, which can indicate weaker crypto liquidity conditions.",
                1.5,
                0.62,
            )
        )

    candidates = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)
    primary = [item for item in candidates if item.get("score", 0) >= 2.2][:3]
    secondary = [item for item in candidates if item not in primary and item.get("score", 0) >= 1.0][:5]

    if not primary and secondary and secondary[0].get("score", 0) >= 1.5:
        primary.append(secondary.pop(0))
    if not primary and not secondary:
        primary.append(
            _driver(
                "Insufficient confirmed evidence",
                ["market", "derivatives", "news", "onchain"],
                "The available layers do not cross-confirm a single dominant driver. Treat this as insufficient evidence rather than a firm attribution.",
                0.45,
                0.5,
            )
        )

    quality = {
        "has_primary_with_evidence": all(bool(item.get("evidence")) for item in primary),
        "candidate_count": len(candidates),
        "insufficient_evidence": primary[0]["driver"] == "Insufficient confirmed evidence",
    }
    return {
        "event_summary": event_summary,
        "primary_drivers": primary,
        "secondary_drivers": secondary,
        "noise": noise[:6],
        "quality_check": quality,
    }
