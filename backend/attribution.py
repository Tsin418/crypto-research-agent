from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


TIMING_SCORE = {
    "before_move": 0.8,
    "during_move": 0.4,
    "unknown": 0.0,
    "after_move": -0.8,
}

TIMING_QUALITY = {
    "before_move": 1.0,
    "during_move": 0.7,
    "unknown": 0.4,
    "after_move": 0.1,
}

PRICE_MOVE_THRESHOLD = 2.0
OI_MOVE_THRESHOLD = 5.0
LIQ_DOMINANCE_RATIO = 2.0
LOW_LIQUIDATION_THRESHOLD = 1.0


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _price_direction(market_change: float | None) -> str:
    if market_change is None:
        return "neutral"
    if market_change < 0:
        return "bearish"
    if market_change > 0:
        return "bullish"
    return "neutral"


def _causal_timing(published_at: str | None, now_utc: datetime) -> str:
    published = _parse_time(published_at)
    if published is None:
        return "unknown"
    move_start = now_utc - timedelta(hours=24)
    move_end = now_utc
    if published < move_start:
        return "before_move"
    if move_start <= published <= move_end:
        return "during_move"
    return "after_move"


def _source_quality(source_type: str, evidence: list[str]) -> float:
    if source_type == "news":
        if "official_announcement" in evidence or "regulatory" in evidence:
            return 1.0
        return 0.7
    if source_type in {"market", "derivatives"}:
        return 0.8
    if source_type == "onchain":
        return 0.6 if "address_labels" in evidence else 0.4
    return 0.6


def _cross_layer_confirmation(
    *,
    direction: str,
    source_type: str,
    market: dict,
    derivatives: dict,
    onchain: dict,
) -> float:
    market_change = market.get("price_change_24h_pct")
    volume_ratio = market.get("volume_ratio_vs_7d")
    price_direction = _price_direction(market_change)
    score = 0.0
    if direction != "neutral" and direction == price_direction:
        score += 0.2
    if source_type != "market" and market_change is not None and abs(market_change) >= PRICE_MOVE_THRESHOLD:
        score += 0.15
    if source_type != "market" and volume_ratio is not None and volume_ratio >= 1.5:
        score += 0.15
    oi_change = derivatives.get("open_interest_change_24h_pct")
    long_liq = derivatives.get("long_liquidations_24h")
    short_liq = derivatives.get("short_liquidations_24h")
    if source_type != "derivatives" and (oi_change is not None and abs(oi_change) >= OI_MOVE_THRESHOLD or long_liq or short_liq):
        score += 0.2
    onchain_signal = onchain.get("onchain_signal")
    if source_type != "onchain" and onchain_signal == "exchange_inflow_pressure" and direction == "bearish":
        score += 0.2
    return _clamp(score)


def _data_completeness(candidate: dict[str, Any]) -> float:
    source_type = candidate.get("source_type")
    if source_type == "news":
        required = ("driver", "direction", "causal_timing", "source_quality")
    elif source_type == "derivatives":
        required = ("derivatives_regime", "direction", "source_quality", "score")
    elif source_type == "market":
        required = ("driver", "direction", "source_quality", "score")
    elif source_type == "onchain":
        required = ("driver", "direction", "source_quality", "score")
    else:
        required = ("driver", "score")
    available = [field for field in required if candidate.get(field) is not None]
    base = len(available) / len(required)
    missing_penalty = min(0.35, len(candidate.get("missing_evidence", [])) * 0.08)
    return _clamp(base - missing_penalty)


def infer_causality_level(candidate: dict[str, Any]) -> str:
    supporting = candidate.get("supporting_evidence", [])
    counter = candidate.get("counter_evidence", [])
    if len(supporting) >= 3 and not counter and candidate.get("primary_eligible", True):
        return "confirmed"
    if len(supporting) >= 2 and candidate.get("primary_eligible", True):
        return "plausible"
    if supporting:
        return "weak"
    return "context_only"


def compute_confidence(candidate: dict[str, Any]) -> tuple[float, dict[str, float]]:
    score = candidate.get("score", 0.0)
    evidence_strength = _clamp(score / 3.0)
    timing_quality = TIMING_QUALITY.get(candidate.get("causal_timing"), 0.7)
    source_quality = candidate.get("source_quality", 0.6)
    cross_layer = candidate.get("cross_layer_confirmation", 0.0)
    data_completeness = _data_completeness(candidate)
    counter_penalty = min(1.0, len(candidate.get("counter_evidence", [])) * 0.25)
    breakdown = {
        "evidence_strength": round(evidence_strength, 2),
        "timing_quality": round(timing_quality, 2),
        "source_quality": round(source_quality, 2),
        "cross_layer_confirmation": round(cross_layer, 2),
        "data_completeness": round(data_completeness, 2),
        "counter_evidence_penalty": round(counter_penalty, 2),
    }
    confidence = (
        0.30
        + 0.15 * evidence_strength
        + 0.15 * timing_quality
        + 0.15 * source_quality
        + 0.15 * cross_layer
        + 0.10 * data_completeness
        - 0.15 * counter_penalty
    )
    return round(max(0.30, min(0.90, confidence)), 2), breakdown


def _finalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["causality_level"] = infer_causality_level(candidate)
    confidence, breakdown = compute_confidence(candidate)
    candidate["confidence"] = confidence
    candidate["confidence_breakdown"] = breakdown
    candidate["score"] = round(candidate.get("score", 0.0), 2)
    candidate.pop("source_type", None)
    candidate.pop("source_quality", None)
    candidate.pop("cross_layer_confirmation", None)
    return candidate


def _build_candidate(
    *,
    name: str,
    evidence: list[str],
    explanation: str,
    score: float,
    source_type: str,
    direction: str = "neutral",
    supporting_evidence: list[str] | None = None,
    counter_evidence: list[str] | None = None,
    missing_evidence: list[str] | None = None,
    primary_eligible: bool = True,
    market: dict | None = None,
    derivatives: dict | None = None,
    onchain: dict | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "driver": name,
        "evidence": evidence,
        "supporting_evidence": supporting_evidence or [],
        "counter_evidence": counter_evidence or [],
        "missing_evidence": missing_evidence or [],
        "explanation": explanation,
        "score": score,
        "primary_eligible": primary_eligible,
        "source_type": source_type,
        "source_quality": _source_quality(source_type, evidence),
        "direction": direction,
        "cross_layer_confirmation": _cross_layer_confirmation(
            direction=direction,
            source_type=source_type,
            market=market or {},
            derivatives=derivatives or {},
            onchain=onchain or {},
        ),
    }
    if extra:
        candidate.update(extra)
    return _finalize_candidate(candidate)


def classify_derivatives_regime(
    price_change_24h_pct: float | None,
    oi_change_24h_pct: float | None,
    funding_now: float | None,
    funding_change: float | None,
    long_liquidations_24h: float | None,
    short_liquidations_24h: float | None,
) -> dict[str, Any]:
    supporting: list[str] = []
    counter: list[str] = []
    missing: list[str] = []
    long_liq = long_liquidations_24h
    short_liq = short_liquidations_24h

    if price_change_24h_pct is None:
        missing.append("24h price change unavailable.")
    if oi_change_24h_pct is None:
        missing.append("Open interest change unavailable.")
    if funding_now is None and funding_change is None:
        missing.append("Funding rate unavailable.")
    if long_liq is None and short_liq is None:
        missing.append("Liquidation data unavailable.")

    if oi_change_24h_pct is not None:
        if abs(oi_change_24h_pct) >= OI_MOVE_THRESHOLD:
            supporting.append("Open interest changed materially.")
        elif abs(oi_change_24h_pct) < 3:
            counter.append("Open interest was relatively stable.")
    if long_liq is not None or short_liq is not None:
        if (long_liq or 0) > 0 or (short_liq or 0) > 0:
            supporting.append("Liquidation data confirms forced position closing.")
        else:
            counter.append("No meaningful liquidation spike detected.")
    if funding_now is not None:
        supporting.append("Funding rate data is available.")

    price_state = "unknown"
    if price_change_24h_pct is not None:
        if abs(price_change_24h_pct) < 1:
            price_state = "flat"
        elif price_change_24h_pct <= -PRICE_MOVE_THRESHOLD:
            price_state = "down"
        elif price_change_24h_pct >= PRICE_MOVE_THRESHOLD:
            price_state = "up"
        else:
            price_state = "mild"

    oi_state = "unknown"
    if oi_change_24h_pct is not None:
        if oi_change_24h_pct <= -OI_MOVE_THRESHOLD:
            oi_state = "down"
        elif oi_change_24h_pct >= OI_MOVE_THRESHOLD:
            oi_state = "up"
        else:
            oi_state = "flat"

    funding_positive = (funding_now is not None and funding_now > 0) or (funding_change is not None and funding_change > 0)
    funding_negative = (funding_now is not None and funding_now < 0) or (funding_change is not None and funding_change < 0)
    long_dominant = long_liq is not None and short_liq is not None and long_liq > short_liq * LIQ_DOMINANCE_RATIO
    short_dominant = long_liq is not None and short_liq is not None and short_liq > long_liq * LIQ_DOMINANCE_RATIO
    low_liquidation = (
        long_liq is not None
        and short_liq is not None
        and long_liq <= LOW_LIQUIDATION_THRESHOLD
        and short_liq <= LOW_LIQUIDATION_THRESHOLD
    )

    result = {
        "regime": "derivatives_data_limited",
        "label": "Derivatives data limited",
        "direction": "neutral",
        "score_base": 0.8,
        "primary_eligible": False,
        "supporting_evidence": supporting,
        "counter_evidence": counter,
        "missing_evidence": missing,
    }

    if oi_change_24h_pct is None or (funding_now is None and funding_change is None):
        return result

    if price_state == "down" and oi_state == "down" and long_dominant and funding_positive:
        supporting.append("Long liquidations materially exceeded short liquidations.")
        return {
            **result,
            "regime": "long_leverage_flush",
            "label": "Long leverage flush",
            "direction": "bearish",
            "score_base": 2.5,
            "primary_eligible": True,
        }
    if price_state == "up" and oi_state == "down" and short_dominant and funding_negative:
        supporting.append("Short liquidations materially exceeded long liquidations.")
        return {
            **result,
            "regime": "short_squeeze",
            "label": "Short squeeze",
            "direction": "bullish",
            "score_base": 2.5,
            "primary_eligible": True,
        }
    if price_state == "down" and oi_state == "up" and funding_positive:
        supporting.append("Open interest rose while price fell, suggesting longs may be trapped.")
        if low_liquidation:
            counter.append("No strong liquidation spike has confirmed forced deleveraging yet.")
        return {
            **result,
            "regime": "crowded_longs_under_pressure",
            "label": "Crowded longs under pressure",
            "direction": "bearish",
            "score_base": 2.0,
            "primary_eligible": True,
        }
    if price_state == "up" and oi_state == "up" and funding_positive and not short_dominant:
        supporting.append("Open interest and funding rose alongside price.")
        return {
            **result,
            "regime": "new_long_positioning",
            "label": "Fresh long positioning",
            "direction": "bullish",
            "score_base": 1.9,
            "primary_eligible": True,
        }
    if price_state == "flat" and oi_state == "up" and funding_positive and (low_liquidation or long_liq is None and short_liq is None):
        supporting.append("Leverage increased while spot price was broadly flat.")
        return {
            **result,
            "regime": "leverage_build_up_risk",
            "label": "Leverage build-up risk",
            "direction": "neutral",
            "score_base": 1.5,
            "primary_eligible": False,
        }
    if price_state == "down" and oi_state == "down":
        supporting.append("Price and open interest both declined, consistent with possible deleveraging.")
        return {
            **result,
            "regime": "possible_deleveraging",
            "label": "Possible deleveraging",
            "direction": "bearish",
            "score_base": 1.7,
            "primary_eligible": True,
        }

    return result


def _news_candidates(asset: str, market: dict, derivatives: dict, news: dict, onchain: dict, now_utc: datetime) -> tuple[list[dict], list[dict]]:
    candidates: list[dict] = []
    noise: list[dict] = []
    market_change = market.get("price_change_24h_pct")
    price_direction = _price_direction(market_change)
    for event in news.get("events", [])[:12]:
        direction = event.get("direction", "neutral")
        impact = event.get("impact_level", "low")
        related = [str(item).upper() for item in event.get("asset_related", [])]
        causal_timing = _causal_timing(event.get("published_at"), now_utc)
        score = TIMING_SCORE[causal_timing]
        evidence = ["news"]
        supporting: list[str] = []
        counter: list[str] = []
        missing: list[str] = []

        if asset.upper() in related:
            score += 1.0
            supporting.append("News item directly references the queried asset.")
        if impact == "high":
            score += 1.0
            supporting.append("News item is classified as high impact.")
        elif impact == "medium":
            score += 0.5
        if direction == price_direction and direction != "neutral":
            score += 1.0
        elif direction != "neutral" and price_direction != "neutral":
            counter.append("News direction is not aligned with the price move.")
        if causal_timing in {"before_move", "during_move"}:
            supporting.append("News timing is compatible with the market move.")
        if causal_timing == "after_move":
            counter.append("News was published after the observed move and may be post-move commentary.")
        if event.get("published_at") is None:
            missing.append("News timestamp unavailable.")
        if event.get("category") == "etf_flow" and asset == "BTC":
            score += 0.5
            evidence.append("etf_flow")
        category = str(event.get("category", "news_event"))
        if category in {"regulation", "regulatory", "etf_flow", "exchange_announcement"}:
            evidence.append("regulatory" if "regulat" in category else "official_announcement")

        primary_eligible = causal_timing != "after_move"
        cross_layer = _cross_layer_confirmation(
            direction=direction,
            source_type="news",
            market=market,
            derivatives=derivatives,
            onchain=onchain,
        )
        if causal_timing == "during_move" and cross_layer < 0.3:
            primary_eligible = False

        if score >= 1.0 and direction != "neutral":
            if direction == price_direction and direction != "neutral":
                explanation = event.get("reason") or f"A {impact} {direction} news item is asset-relevant and directionally aligned with the move."
            else:
                explanation = event.get("reason") or f"A {impact} {direction} news item is asset-relevant, but it is not directionally aligned with the latest 24h price move, so it is supporting context rather than a confirmed driver."
            candidate = _build_candidate(
                name=f"{category.replace('_', ' ').title()}: {event.get('title')}",
                evidence=evidence,
                explanation=explanation,
                score=score,
                source_type="news",
                direction=direction,
                supporting_evidence=supporting,
                counter_evidence=counter,
                missing_evidence=missing,
                primary_eligible=primary_eligible,
                market=market,
                derivatives=derivatives,
                onchain=onchain,
                extra={"causal_timing": causal_timing},
            )
            candidates.append(candidate)
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
    now_utc = datetime.now(UTC)
    market_change = market.get("price_change_24h_pct")
    volume_ratio = market.get("volume_ratio_vs_7d")
    price = market.get("price_now")
    event_summary = (
        f"{asset} moved {market_change:.2f}% over the last 24h. Current spot reference price is ${price:,.2f}."
        if market_change is not None and price
        else f"{asset} market data is limited for this window."
    )

    if market_change is not None and abs(market_change) >= PRICE_MOVE_THRESHOLD:
        supporting = ["24h price move exceeded 2%."]
        counter: list[str] = []
        missing: list[str] = []
        score = 1.0
        if volume_ratio is not None and volume_ratio >= 1.5:
            supporting.append("24h spot turnover/volume was above recent average.")
            score += 1.2
        elif volume_ratio is not None and volume_ratio < 1.2:
            counter.append("Volume expansion was limited, weakening a spot-led explanation.")
        else:
            missing.append("Spot volume ratio unavailable.")
        if market.get("spot_flow_bias") is None:
            missing.append("Spot buy/sell flow unavailable.")
        if score >= 1.0:
            candidates.append(
                _build_candidate(
                    name="Elevated spot activity",
                    evidence=["market_volume", "price_change"],
                    explanation="The price move is accompanied by available spot activity evidence, suggesting spot participation should be considered.",
                    score=score,
                    source_type="market",
                    direction=_price_direction(market_change),
                    supporting_evidence=supporting,
                    counter_evidence=counter,
                    missing_evidence=missing,
                    market=market,
                    derivatives=derivatives,
                    onchain=onchain,
                )
            )

    regime = classify_derivatives_regime(
        market_change,
        derivatives.get("open_interest_change_24h_pct"),
        derivatives.get("funding_rate_now"),
        derivatives.get("funding_rate_change"),
        derivatives.get("long_liquidations_24h"),
        derivatives.get("short_liquidations_24h"),
    )
    if regime["score_base"] >= 1.0:
        candidates.append(
            _build_candidate(
                name=regime["label"],
                evidence=["funding_rate", "open_interest", "derivatives_market"]
                + (["liquidations"] if "Liquidation data confirms forced position closing." in regime["supporting_evidence"] else []),
                explanation=(
                    "Funding, open interest, and liquidation data point to a specific derivatives positioning regime rather than a generic leverage signal."
                    if regime["regime"] != "derivatives_data_limited"
                    else "Derivatives inputs are incomplete, so this layer is disclosed as limited evidence rather than a firm driver."
                ),
                score=regime["score_base"],
                source_type="derivatives",
                direction=regime["direction"],
                supporting_evidence=regime["supporting_evidence"],
                counter_evidence=regime["counter_evidence"],
                missing_evidence=regime["missing_evidence"],
                primary_eligible=regime["primary_eligible"],
                market=market,
                derivatives=derivatives,
                onchain=onchain,
                extra={"derivatives_regime": regime["regime"]},
            )
        )

    put_call = derivatives.get("put_call_ratio")
    if put_call is not None and put_call >= 1.2:
        candidates.append(
            _build_candidate(
                name="Options downside hedging demand",
                evidence=["deribit_options", "put_call_ratio"],
                explanation="Deribit put/call open interest is elevated, indicating relatively stronger downside hedging demand.",
                score=1.4,
                source_type="derivatives",
                direction="bearish",
                supporting_evidence=["Options put/call ratio is elevated."],
                missing_evidence=[],
                market=market,
                derivatives=derivatives,
                onchain=onchain,
            )
        )

    news_candidates, news_noise = _news_candidates(asset, market, derivatives, news, onchain, now_utc)
    candidates.extend(news_candidates)
    noise.extend(news_noise)

    onchain_signal = onchain.get("onchain_signal")
    if onchain_signal == "exchange_inflow_pressure":
        candidates.append(
            _build_candidate(
                name="Potential exchange inflow pressure",
                evidence=["onchain_transfers", "address_labels"],
                explanation="Large transfers include exchange-bound flows, which can signal potential sell pressure.",
                score=2.0,
                source_type="onchain",
                direction="bearish",
                supporting_evidence=["Labeled exchange-bound transfers detected."],
                missing_evidence=["Exchange netflow data unavailable."] if onchain.get("exchange_netflow_24h") is None else [],
                market=market,
                derivatives=derivatives,
                onchain=onchain,
            )
        )
    elif onchain_signal in {"large_transfer_cluster", "large_transfer_activity"}:
        candidates.append(
            _build_candidate(
                name="Large on-chain transfer activity",
                evidence=["alchemy_webhooks", "etherscan", "mempool.space"],
                explanation="Large BTC/ETH transfers were detected, but wallet labels are limited so this is supporting context rather than confirmed sell pressure.",
                score=1.2,
                source_type="onchain",
                direction="neutral",
                supporting_evidence=["Large transfer activity was detected."],
                counter_evidence=["Large transfer activity does not confirm sell pressure without wallet labels."],
                missing_evidence=["Wallet labeling coverage is limited."],
                primary_eligible=False,
                market=market,
                derivatives=derivatives,
                onchain=onchain,
            )
        )
    elif onchain_signal == "liquidity_contraction":
        candidates.append(
            _build_candidate(
                name="Stablecoin liquidity contraction",
                evidence=["defillama_stablecoins"],
                explanation="USDT/USDC supply change is negative, which can indicate weaker crypto liquidity conditions.",
                score=1.5,
                source_type="onchain",
                direction="bearish",
                supporting_evidence=["Stablecoin liquidity contracted over the observed window."],
                missing_evidence=[],
                market=market,
                derivatives=derivatives,
                onchain=onchain,
            )
        )

    candidates = sorted(candidates, key=lambda item: item.get("score", 0), reverse=True)
    primary = [
        item
        for item in candidates
        if item.get("score", 0) >= 2.2
        and item.get("primary_eligible", True)
        and item.get("causality_level") in {"confirmed", "plausible"}
    ][:3]
    secondary = [item for item in candidates if item not in primary and item.get("score", 0) >= 1.0][:5]

    if not primary and secondary and secondary[0].get("score", 0) >= 1.5 and secondary[0].get("primary_eligible", True):
        primary.append(secondary.pop(0))
    if not primary:
        primary.append(
            _build_candidate(
                name="Insufficient confirmed evidence",
                evidence=["market", "derivatives", "news", "onchain"],
                explanation="The available layers do not cross-confirm a single dominant driver. Treat this as insufficient evidence rather than a firm attribution.",
                score=0.5,
                source_type="fallback",
                supporting_evidence=[],
                missing_evidence=["No candidate met the primary-driver evidence threshold."],
                primary_eligible=False,
                market=market,
                derivatives=derivatives,
                onchain=onchain,
            )
        )

    all_ranked = primary + secondary
    quality = {
        "has_primary_with_evidence": all(bool(item.get("evidence")) for item in primary),
        "candidate_count": len(candidates),
        "insufficient_evidence": primary[0]["driver"] == "Insufficient confirmed evidence",
        "has_counter_evidence": any(bool(item.get("counter_evidence")) for item in all_ranked),
        "has_missing_evidence_disclosure": any(bool(item.get("missing_evidence")) for item in all_ranked),
        "post_move_news_promoted": any(item.get("causal_timing") == "after_move" for item in primary),
        "derivatives_regime_available": any("derivatives_regime" in item for item in all_ranked),
    }
    return {
        "event_summary": event_summary,
        "primary_drivers": primary,
        "secondary_drivers": secondary,
        "noise": noise[:6],
        "quality_check": quality,
    }
