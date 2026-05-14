from __future__ import annotations

from typing import Any


def layer_quality(
    *,
    freshness: str = "unknown",
    confidence: str = "medium",
    methodology: str,
    source_timestamp: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "freshness": freshness,
        "confidence": confidence,
        "methodology": methodology,
        "source_timestamp": source_timestamp,
        "warnings": warnings or [],
    }


def metric_meta(
    *,
    methodology: str,
    confidence: float,
    source: str,
    warning: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "methodology": methodology,
        "confidence": confidence,
        "source": source,
    }
    if warning:
        payload["warning"] = warning
    return payload
