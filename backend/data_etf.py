from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from backend.config import ROOT_DIR
from backend.http_client import get_text
from backend.models import LayerResult
from backend.utils import iso_now, safe_float


FARSIDE_BTC = "https://farside.co.uk/btc/"
DEFAULT_CACHE = ROOT_DIR / "data" / "etf_flow_cache.json"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _flow_direction(value: float | None) -> str:
    if value is None:
        return "unavailable"
    if value > 0:
        return "inflow"
    if value < 0:
        return "outflow"
    return "neutral"


def _flow_intensity(value: float | None) -> str:
    if value is None:
        return "unavailable"
    absolute = abs(value)
    if absolute >= 300:
        return "high"
    if absolute >= 100:
        return "medium"
    if absolute > 0:
        return "low"
    return "neutral"


def _payload(
    *,
    source: str,
    latest: float | None,
    five_day: float | None = None,
    updated_at: str | None = None,
    is_stale: bool = False,
    note: str,
) -> dict[str, Any]:
    return {
        "asset": "BTC",
        "net_flow_usd_m_latest": latest,
        "net_flow_usd_m_5d": five_day,
        "btc_etf_net_flow_usd_m": latest,
        "flow_direction": _flow_direction(latest),
        "flow_intensity": _flow_intensity(latest),
        "updated_at": updated_at or iso_now(),
        "is_stale": is_stale,
        "note": note,
        "etf_flow_signal": "etf_flow_available" if latest is not None else "etf_flow_unavailable",
        "source": source,
    }


def _read_cache(cache_path: Path) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_cache(cache_path: Path, payload: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _from_cache(cache_path: Path) -> dict[str, Any] | None:
    cached = _read_cache(cache_path)
    if not cached:
        return None
    updated_at = _parse_iso(cached.get("updated_at"))
    is_stale = True
    if updated_at is not None:
        is_stale = datetime.now(UTC) - updated_at > timedelta(hours=36)
    latest = safe_float(cached.get("net_flow_usd_m_latest") or cached.get("btc_etf_net_flow_usd_m"))
    return _payload(
        source="local_cache",
        latest=latest,
        five_day=safe_float(cached.get("net_flow_usd_m_5d")),
        updated_at=cached.get("updated_at"),
        is_stale=is_stale,
        note="ETF flow loaded from local cache; stale data is disclosed and should not be treated as same-day flow.",
    )


def _extract_farside_flows(html: str) -> tuple[float | None, float | None]:
    numbers = [float(value.replace(",", "")) for value in re.findall(r">\s*(-?\d[\d,]*\.\d)\s*<", html)]
    if not numbers:
        return None, None
    latest = numbers[-1]
    five_day = sum(numbers[-5:]) if len(numbers) >= 5 else latest
    return latest, round(five_day, 2)


async def _fetch_farside() -> tuple[dict[str, Any], list[str]]:
    async with httpx.AsyncClient(timeout=10) as client:
        html, error = await get_text(client, FARSIDE_BTC, source="farside_btc_etf_flow")
    if error or not html:
        return {}, [error or "farside_btc_etf_flow: empty response"]
    if "Just a moment" in html or "cf-browser-verification" in html:
        return {}, ["farside_btc_etf_flow: blocked by anti-bot page"]
    latest, five_day = _extract_farside_flows(html)
    if latest is None:
        return {}, ["farside_btc_etf_flow: no usable flow values"]
    return _payload(
        source="farside_best_effort_html",
        latest=latest,
        five_day=five_day,
        note="BTC spot ETF flow parsed from Farside best-effort HTML.",
    ), []


def _news_fallback(news: dict[str, Any] | None) -> dict[str, Any] | None:
    if not news:
        return None
    for event in news.get("events", []):
        if event.get("category") != "etf_flow":
            continue
        direction = event.get("direction")
        latest = -100.0 if direction == "bearish" else 100.0 if direction == "bullish" else None
        if latest is None:
            continue
        payload = _payload(
            source="news_fallback",
            latest=latest,
            note="ETF flow inferred from ETF-related news only; confidence is low and it cannot stand alone as primary evidence.",
        )
        payload["fallback_event_title"] = event.get("title")
        payload["flow_intensity"] = "medium"
        return payload
    return None


async def fetch_etf_flow(asset: str, *, cache_path: Path | None = None, news: dict[str, Any] | None = None) -> LayerResult:
    if asset != "BTC":
        return LayerResult(
            layer="etf_flow",
            source="unavailable",
            data=_payload(source="unavailable", latest=None, note="Spot ETF flow layer is currently BTC-only."),
            errors=[],
        )
    cache_path = cache_path or DEFAULT_CACHE
    errors: list[str] = []
    farside, farside_errors = await _fetch_farside()
    if farside:
        _write_cache(cache_path, farside)
        return LayerResult(layer="etf_flow", source="farside_best_effort_html", data=farside, errors=[])
    errors.extend(farside_errors)

    cached = _from_cache(cache_path)
    if cached and cached.get("net_flow_usd_m_latest") is not None:
        return LayerResult(layer="etf_flow", source="local_cache", data=cached, errors=errors)

    fallback = _news_fallback(news)
    if fallback:
        return LayerResult(layer="etf_flow", source="news_fallback", data=fallback, errors=errors)

    return LayerResult(
        layer="etf_flow",
        source="unavailable",
        data=_payload(
            source="unavailable",
            latest=None,
            note="ETF flow data is unavailable or stale; this report does not treat ETF flows as confirmed evidence.",
        ),
        errors=errors,
    )


async def fetch_btc_etf_flow() -> tuple[dict, list[str]]:
    result = await fetch_etf_flow("BTC")
    return result.data, result.errors
