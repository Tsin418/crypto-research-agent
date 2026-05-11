from __future__ import annotations

import re

import httpx

from backend.http_client import get_text


FARSIDE_BTC = "https://farside.co.uk/btc/"


async def fetch_btc_etf_flow() -> tuple[dict, list[str]]:
    async with httpx.AsyncClient(timeout=10) as client:
        html, error = await get_text(client, FARSIDE_BTC, source="farside_btc_etf_flow")
    if error or not html:
        return {"etf_flow_signal": "etf_flow_unavailable"}, [error or "farside_btc_etf_flow: empty response"]
    if "Just a moment" in html or "cf-browser-verification" in html:
        return {"etf_flow_signal": "etf_flow_unavailable"}, ["farside_btc_etf_flow: blocked by anti-bot page"]
    numbers = [float(value.replace(",", "")) for value in re.findall(r">\s*(-?\d[\d,]*\.\d)\s*<", html)]
    latest = numbers[-1] if numbers else None
    return {
        "etf_flow_signal": "etf_flow_available" if latest is not None else "etf_flow_unavailable",
        "latest_detected_flow_usd_m": latest,
        "source": "farside_best_effort_html",
    }, []
