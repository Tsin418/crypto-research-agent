from __future__ import annotations

import csv
from io import StringIO
from typing import Any

import httpx

from backend.config import Settings
from backend.http_client import get_text
from backend.models import LayerResult
from backend.utils import round_float, safe_float


STOOQ_DAILY = "https://stooq.com/q/d/l/"
STOOQ_SYMBOLS = {
    "qqq": "qqq.us",
    "nasdaq": "^ndq",
    "dxy": "dx.f",
    "us10y": "10usy.b",
    "vix": "^vix",
    "gold": "xauusd",
}


async def _fetch_stooq_change(client: httpx.AsyncClient, key: str, symbol: str) -> tuple[dict[str, Any], list[str]]:
    text, error = await get_text(
        client,
        f"{STOOQ_DAILY}?s={symbol}&i=d",
        source=f"stooq_macro:{key}",
    )
    if error or not text:
        return {}, [error or f"stooq_macro:{key}: empty response"]
    rows = list(csv.DictReader(StringIO(text)))
    closes = [safe_float(row.get("Close")) for row in rows if row.get("Close")]
    closes = [value for value in closes if value is not None]
    if len(closes) < 2:
        return {}, [f"stooq_macro:{key}: fewer than 2 close values"]
    current = closes[-1]
    previous = closes[-2]
    if key == "us10y":
        change = (current - previous) * 100
        return {f"{key}_change_bp": round_float(change)}, []
    change_pct = ((current - previous) / previous) * 100 if previous else None
    return {f"{key}_change_24h_pct": round_float(change_pct)}, []


def classify_macro_signal(data: dict[str, Any], asset_price_change_24h_pct: float | None = None) -> dict[str, Any]:
    asset_down = asset_price_change_24h_pct is None or asset_price_change_24h_pct < 0
    asset_up = asset_price_change_24h_pct is None or asset_price_change_24h_pct > 0
    qqq = data.get("qqq_change_24h_pct") or data.get("nasdaq_change_24h_pct")
    dxy = data.get("dxy_change_24h_pct")
    us10y = data.get("us10y_change_bp")
    vix = data.get("vix_change_24h_pct")

    supporting: list[str] = []
    available = [value for value in (qqq, dxy, us10y, vix) if value is not None]
    if len(available) < 2:
        return {
            "macro_signal": "unavailable",
            "macro_confidence": "low",
            "macro_signal_evidence": ["Insufficient macro inputs available."],
        }

    if asset_down and qqq is not None and qqq < -0.5 and vix is not None and vix > 3:
        supporting.extend([f"QQQ/Nasdaq proxy fell {qqq:.2f}%.", f"VIX rose {vix:.2f}%."])
        return {"macro_signal": "risk_off", "macro_confidence": "high", "macro_signal_evidence": supporting}
    if asset_down and us10y is not None and us10y >= 5:
        supporting.append(f"US10Y rose {us10y:.1f} bp.")
        return {"macro_signal": "rates_pressure", "macro_confidence": "medium", "macro_signal_evidence": supporting}
    if asset_down and dxy is not None and dxy > 0.25:
        supporting.append(f"DXY rose {dxy:.2f}%.")
        return {"macro_signal": "dollar_pressure", "macro_confidence": "medium", "macro_signal_evidence": supporting}
    if asset_up and qqq is not None and qqq > 0.5 and dxy is not None and dxy < -0.25:
        supporting.extend([f"QQQ/Nasdaq proxy rose {qqq:.2f}%.", f"DXY fell {dxy:.2f}%."])
        return {"macro_signal": "risk_on", "macro_confidence": "high", "macro_signal_evidence": supporting}

    return {
        "macro_signal": "neutral",
        "macro_confidence": "low",
        "macro_signal_evidence": ["Macro inputs are mixed rather than clearly aligned."],
    }


def _macro_events() -> list[dict[str, str]]:
    return [{"event": "Macro calendar not connected", "timing": "none", "source": "static_calendar"}]


async def fetch_macro_context(settings: Settings, asset_price_change_24h_pct: float | None = None) -> LayerResult:
    errors: list[str] = []
    data: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        for key, symbol in STOOQ_SYMBOLS.items():
            payload, provider_errors = await _fetch_stooq_change(client, key, symbol)
            if payload:
                data.update(payload)
            else:
                errors.extend(provider_errors)

    signal = classify_macro_signal(data, asset_price_change_24h_pct)
    data.update(signal)
    data["macro_events"] = _macro_events()
    source = "stooq" if any(key.endswith(("_pct", "_bp")) for key in data) else "unavailable"
    data["source"] = source
    return LayerResult(layer="macro", source=source, data=data, errors=errors)
