from __future__ import annotations

import httpx

from backend.http_client import get_json
from backend.utils import round_float


STABLECOINS = "https://stablecoins.llama.fi/stablecoins"
STABLECOIN_CHART = "https://stablecoins.llama.fi/stablecoincharts/all"
TARGET_STABLES = {"USDT", "USDC"}


def _pegged_usd(row: dict) -> float | None:
    value = row.get("totalCirculatingUSD") or row.get("totalCirculating") or row.get("circulating")
    if isinstance(value, dict):
        value = value.get("peggedUSD")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def fetch_stablecoin_supply(client: httpx.AsyncClient) -> tuple[dict, list[str]]:
    data, error = await get_json(client, STABLECOINS, params={"includePrices": "true"}, source="defillama_stablecoins")
    if error:
        return {}, [error]
    if not isinstance(data, dict) or not isinstance(data.get("peggedAssets"), list):
        return {}, ["defillama_stablecoins: empty response"]

    total_now = 0.0
    assets: dict[str, dict] = {}
    errors: list[str] = []
    for asset in data["peggedAssets"]:
        symbol = asset.get("symbol")
        if symbol not in TARGET_STABLES:
            continue
        current = _pegged_usd(asset.get("circulating") if isinstance(asset.get("circulating"), dict) else asset)
        if current is None:
            current = _pegged_usd(asset)
        total_now += current or 0.0
        chart, chart_error = await get_json(
            client,
            STABLECOIN_CHART,
            params={"stablecoin": asset.get("id")},
            source="defillama_stablecoin_chart",
        )
        if chart_error:
            errors.append(chart_error)
            assets[symbol] = {"current_supply_usd": round_float(current, 2)}
            continue
        history = chart if isinstance(chart, list) else []
        one_day = _pegged_usd(history[-2]) if len(history) >= 2 else None
        seven_day = _pegged_usd(history[-8]) if len(history) >= 8 else None
        assets[symbol] = {
            "current_supply_usd": round_float(current, 2),
            "change_24h_usd": round_float((current - one_day) if current is not None and one_day is not None else None, 2),
            "change_7d_usd": round_float((current - seven_day) if current is not None and seven_day is not None else None, 2),
        }

    change_24h = sum((item.get("change_24h_usd") or 0) for item in assets.values())
    change_7d = sum((item.get("change_7d_usd") or 0) for item in assets.values())
    return {
        "stablecoin_assets": assets,
        "stablecoin_supply_usd": round_float(total_now, 2),
        "stablecoin_supply_change_24h": round_float(change_24h, 2),
        "stablecoin_supply_change_7d": round_float(change_7d, 2),
        "stablecoin_source": "defillama_public_api",
    }, errors
