from __future__ import annotations

import httpx

from backend.config import Settings
from backend.http_client import get_json, is_http_forbidden_error
from backend.models import LayerResult
from backend.utils import ASSET_META, ema, percent_change, round_float, safe_float


COINGECKO_DEMO = "https://api.coingecko.com/api/v3"
COINGECKO_PRO = "https://pro-api.coingecko.com/api/v3"
BYBIT = "https://api.bybit.com"
COINPAPRIKA = "https://api.coinpaprika.com/v1"


def _market_signal(price: float | None, chg24: float | None, ema20: float | None, ema50: float | None) -> str:
    if price is None:
        return "market_data_unavailable"
    if chg24 is not None and chg24 <= -2 and ema20 is not None and price < ema20:
        return "short_term_weakness"
    if chg24 is not None and chg24 >= 2 and ema20 is not None and price > ema20:
        return "short_term_strength"
    if ema20 is not None and ema50 is not None and price > ema20 > ema50:
        return "uptrend_intact"
    if ema20 is not None and ema50 is not None and price < ema20 < ema50:
        return "downtrend_pressure"
    return "neutral"


async def _coingecko(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict, list[str]]:
    meta = ASSET_META[asset]
    base_url = COINGECKO_PRO if settings.coingecko_plan.lower() == "pro" else COINGECKO_DEMO
    header_name = "x-cg-pro-api-key" if settings.coingecko_plan.lower() == "pro" else "x-cg-demo-api-key"
    headers = {header_name: settings.coingecko_api_key} if settings.coingecko_api_key else {}
    params = {
        "vs_currency": "usd",
        "ids": meta["coingecko_id"],
        "price_change_percentage": "1h,24h,7d",
    }
    data, error = await get_json(
        client,
        f"{base_url}/coins/markets",
        params=params,
        headers=headers,
        source="coingecko",
    )
    if error or not isinstance(data, list) or not data:
        return {}, [error or "coingecko: empty response"]
    row = data[0]
    return {
        "price_now": safe_float(row.get("current_price")),
        "price_change_1h_pct": round_float(safe_float(row.get("price_change_percentage_1h_in_currency"))),
        "price_change_24h_pct": round_float(safe_float(row.get("price_change_percentage_24h_in_currency"))),
        "price_change_7d_pct": round_float(safe_float(row.get("price_change_percentage_7d_in_currency"))),
        "volume_24h": safe_float(row.get("total_volume")),
        "market_cap": safe_float(row.get("market_cap")),
    }, []


async def _coinpaprika(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    meta = ASSET_META[asset]
    data, error = await get_json(
        client,
        f"{COINPAPRIKA}/tickers/{meta['coinpaprika_id']}",
        source="coinpaprika",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "coinpaprika: empty response"]
    quote = data.get("quotes", {}).get("USD", {})
    return {
        "price_now": safe_float(quote.get("price")),
        "price_change_1h_pct": round_float(safe_float(quote.get("percent_change_1h"))),
        "price_change_24h_pct": round_float(safe_float(quote.get("percent_change_24h"))),
        "price_change_7d_pct": round_float(safe_float(quote.get("percent_change_7d"))),
        "volume_24h": safe_float(quote.get("volume_24h")),
        "market_cap": safe_float(quote.get("market_cap")),
    }, []


async def _bybit_klines(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = ASSET_META[asset]["symbol"]
    params = {"category": "spot", "symbol": symbol, "interval": "D", "limit": 220}
    data, error = await get_json(
        client,
        f"{BYBIT}/v5/market/kline",
        params=params,
        source="bybit_kline",
    )
    if error or not isinstance(data, dict) or data.get("retCode") != 0:
        return {}, [error or f"bybit_kline: {data.get('retMsg') if isinstance(data, dict) else 'bad response'}"]
    rows = data.get("result", {}).get("list", [])
    rows = sorted(rows, key=lambda item: int(item[0]))
    closes = [safe_float(row[4]) for row in rows]
    volumes = [safe_float(row[6]) for row in rows[-7:]]
    closes_f = [value for value in closes if value is not None]
    volumes_f = [value for value in volumes if value is not None]
    avg_volume = sum(volumes_f) / len(volumes_f) if volumes_f else None
    return {
        "volume_7d_avg": round_float(avg_volume),
        "ema_20": ema(closes_f, 20),
        "ema_50": ema(closes_f, 50),
        "ema_200": ema(closes_f, 200),
        "technical_source": "bybit_public_klines",
    }, []


async def _coingecko_market_chart(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict, list[str]]:
    meta = ASSET_META[asset]
    base_url = COINGECKO_PRO if settings.coingecko_plan.lower() == "pro" else COINGECKO_DEMO
    header_name = "x-cg-pro-api-key" if settings.coingecko_plan.lower() == "pro" else "x-cg-demo-api-key"
    headers = {header_name: settings.coingecko_api_key} if settings.coingecko_api_key else {}
    data, error = await get_json(
        client,
        f"{base_url}/coins/{meta['coingecko_id']}/market_chart",
        params={"vs_currency": "usd", "days": 220, "interval": "daily"},
        headers=headers,
        source="coingecko_market_chart",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "coingecko_market_chart: empty response"]

    prices = [safe_float(row[1]) for row in data.get("prices", []) if isinstance(row, list) and len(row) >= 2]
    volumes = [safe_float(row[1]) for row in data.get("total_volumes", []) if isinstance(row, list) and len(row) >= 2]
    prices_f = [value for value in prices if value is not None]
    volumes_f = [value for value in volumes[-7:] if value is not None]
    avg_volume = sum(volumes_f) / len(volumes_f) if volumes_f else None
    if not prices_f and avg_volume is None:
        return {}, ["coingecko_market_chart: no usable price or volume rows"]
    return {
        "volume_7d_avg": round_float(avg_volume),
        "ema_20": ema(prices_f, 20),
        "ema_50": ema(prices_f, 50),
        "ema_200": ema(prices_f, 200),
        "technical_source": "coingecko_market_chart",
    }, []


async def _bybit_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = ASSET_META[asset]["symbol"]
    data, error = await get_json(
        client,
        f"{BYBIT}/v5/market/tickers",
        params={"category": "spot", "symbol": symbol},
        source="bybit_spot_ticker",
    )
    if error or not isinstance(data, dict) or data.get("retCode") != 0:
        return {}, [error or f"bybit_spot_ticker: {data.get('retMsg') if isinstance(data, dict) else 'bad response'}"]
    rows = data.get("result", {}).get("list", [])
    if not rows:
        return {}, ["bybit_spot_ticker: empty result"]
    row = rows[0]
    return {
        "spot_turnover_24h": safe_float(row.get("turnover24h")),
        "spot_volume_24h_base": safe_float(row.get("volume24h")),
    }, []


async def fetch_market(settings: Settings, asset: str) -> LayerResult:
    notes: list[str] = []
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        primary, errors = await _coingecko(client, settings, asset)
        source = "coingecko"
        if not primary:
            primary, fallback_errors = await _coinpaprika(client, asset)
            errors.extend(fallback_errors)
            source = "coinpaprika" if primary else "unavailable"
        technicals, technical_errors = await _bybit_klines(client, asset)
        if technical_errors and all(is_http_forbidden_error(error) for error in technical_errors):
            notes.append("Bybit public kline endpoints returned HTTP 403 in this runtime; using CoinGecko market chart for EMA and 7d volume.")
            technicals, chart_errors = await _coingecko_market_chart(client, settings, asset)
            errors.extend(chart_errors)
        else:
            errors.extend(technical_errors)
        bybit_spot, spot_errors = await _bybit_spot_ticker(client, asset)
        if spot_errors and all(is_http_forbidden_error(error) for error in spot_errors):
            notes.append("Bybit spot ticker returned HTTP 403 in this runtime; using primary market volume where possible.")
        else:
            errors.extend(spot_errors)

    merged = {"asset": asset, **primary, **technicals, **bybit_spot}
    turnover_24h = merged.get("spot_turnover_24h") or merged.get("volume_24h")
    merged["volume_ratio_vs_7d"] = round_float(
        (turnover_24h / merged["volume_7d_avg"])
        if turnover_24h is not None and merged.get("volume_7d_avg")
        else None
    )
    merged["volume_ratio_source"] = (
        "bybit_spot_turnover_vs_bybit_7d_avg_turnover"
        if merged.get("spot_turnover_24h") is not None
        else "primary_market_volume_vs_technical_7d_avg_volume"
    )
    price = merged.get("price_now")
    for period in (20, 50, 200):
        value = merged.get(f"ema_{period}")
        if price is None or value is None:
            merged[f"price_vs_ema{period}"] = "unknown"
        elif abs(price - value) / value < 0.01:
            merged[f"price_vs_ema{period}"] = "near"
        elif price > value:
            merged[f"price_vs_ema{period}"] = "above"
        else:
            merged[f"price_vs_ema{period}"] = "below"
    merged["market_signal"] = _market_signal(
        price,
        merged.get("price_change_24h_pct"),
        merged.get("ema_20"),
        merged.get("ema_50"),
    )
    if notes:
        merged["note"] = " ".join(notes)
    elif merged.get("volume_7d_avg") is None:
        merged["note"] = "EMA/7d volume use Bybit public klines and may be unavailable if Bybit is blocked."
    return LayerResult(layer="market", source=source, data=merged, errors=errors)
