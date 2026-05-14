from __future__ import annotations

import math
from typing import Any


HISTORY_MIN_SAMPLE = 20

LAYER_METRICS = {
    "market": (
        "price_change_24h_pct",
        "volume_24h",
        "spot_turnover_24h",
        "volume_ratio_vs_7d",
        "spot_cvd_approx_1h",
        "spot_cvd_approx_4h",
    ),
    "derivatives": (
        "funding_rate_now",
        "funding_rate_change",
        "open_interest_change_24h_pct",
        "long_liquidations_24h",
        "short_liquidations_24h",
        "put_call_ratio",
    ),
    "onchain": (
        "stablecoin_supply_change_24h",
        "stablecoin_supply_change_7d",
        "large_transfer_count",
        "exchange_inflow_count",
    ),
    "etf_flow": ("btc_etf_net_flow_usd_m",),
}


def zscore(current_value: float | None, history_values: list[float]) -> float | None:
    if current_value is None or len(history_values) < HISTORY_MIN_SAMPLE:
        return None
    mean = sum(history_values) / len(history_values)
    variance = sum((value - mean) ** 2 for value in history_values) / len(history_values)
    stddev = math.sqrt(variance)
    if stddev == 0:
        return 0.0
    return round((current_value - mean) / stddev, 2)


def percentile_rank(current_value: float | None, history_values: list[float]) -> float | None:
    if current_value is None or len(history_values) < HISTORY_MIN_SAMPLE:
        return None
    less_or_equal = sum(1 for value in history_values if value <= current_value)
    return round(less_or_equal / len(history_values), 2)


def _numeric(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def enrich_with_history(storage: Any, asset: str, layer: str, layer_data: dict[str, Any], lookback_days: int = 90) -> dict[str, Any]:
    enriched = dict(layer_data)
    historical_context: dict[str, Any] = {}
    metrics = LAYER_METRICS.get(layer, ())
    for metric_name in metrics:
        current = _numeric(enriched.get(metric_name))
        if current is None:
            continue
        history = storage.get_metric_history(asset, metric_name, lookback_days=lookback_days)
        sample_size = len(history)
        metric_context: dict[str, Any] = {"current": current, "sample_size": sample_size}
        if sample_size >= HISTORY_MIN_SAMPLE:
            recent_30 = history[:30]
            metric_context["zscore_30d"] = zscore(current, recent_30 if len(recent_30) >= HISTORY_MIN_SAMPLE else history)
            metric_context["percentile_90d"] = percentile_rank(current, history)
        else:
            metric_context["note"] = "Insufficient history; using fixed thresholds."
        historical_context[metric_name] = metric_context
    if historical_context:
        enriched["historical_context"] = historical_context
    return enriched


def save_layer_metric_snapshots(
    storage: Any,
    asset: str,
    layer: str,
    layer_data: dict[str, Any],
    *,
    source: str | None = None,
    report_id: str | None = None,
) -> None:
    for metric_name in LAYER_METRICS.get(layer, ()):
        value = _numeric(layer_data.get(metric_name))
        if value is None:
            continue
        storage.save_metric_snapshot(
            asset=asset,
            layer=layer,
            metric_name=metric_name,
            metric_value=value,
            source=source,
            report_id=report_id,
        )
