from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from backend.config import Settings
from backend.http_client import get_json, is_http_forbidden_error, post_json
from backend.data_options import fetch_deribit_put_call
from backend.models import LayerResult
from backend.utils import ASSET_META, iso_from_ms, percent_change, round_float, safe_float


BYBIT = "https://api.bybit.com"
COINALYZE = "https://api.coinalyze.net/v1"
DERIBIT_BOOK = "https://www.deribit.com/api/v2/public/get_book_summary_by_instrument"
HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"
COINALYZE_BLOCKED_EXCHANGES = ("binance", "bybit")
COINALYZE_PREFERRED_EXCHANGES = ("deribit", "okx", "gate", "hyperliquid", "kraken", "bitmex")


def _signal(
    oi_change: float | None,
    price_change: float | None,
    funding_now: float | None,
    funding_8h_ago: float | None,
    long_liq: float | None,
    short_liq: float | None,
) -> str:
    long_flush = long_liq is not None and short_liq is not None and long_liq > short_liq * 2
    if oi_change is not None and oi_change <= -5 and long_flush:
        return "leverage_flush"
    if oi_change is not None and oi_change >= 5 and price_change is not None and price_change < 0 and funding_now and funding_now > 0:
        return "crowded_longs_under_pressure"
    if funding_now is not None and funding_8h_ago is not None and funding_8h_ago > 0 and funding_now < 0:
        return "sentiment_flip_bearish"
    if oi_change is not None and abs(oi_change) < 3:
        return "spot_driven_or_macro_driven"
    return "derivatives_data_limited"


def _coinalyze_headers(settings: Settings) -> dict[str, str]:
    return {"api_key": settings.coinalyze_api_key}


def _coinalyze_value(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = safe_float(row.get(key))
        if value is not None:
            return value
    history = row.get("history")
    if isinstance(history, list) and history:
        return _coinalyze_value(history[-1], *keys, "c", "value")
    return None


def _coinalyze_history_values(data: Any, *keys: str) -> list[float]:
    if not isinstance(data, list) or not data:
        return []
    history = data[0].get("history") if isinstance(data[0], dict) else None
    if not isinstance(history, list):
        return []
    values = []
    for row in history:
        if isinstance(row, dict):
            value = _coinalyze_value(row, *keys, "c", "value")
            if value is not None:
                values.append(value)
    return values


def _coinalyze_liquidation_totals(data: Any) -> tuple[float | None, float | None]:
    if not isinstance(data, list) or not data:
        return None, None
    history = data[0].get("history") if isinstance(data[0], dict) else None
    if not isinstance(history, list):
        return None, None
    long_total = 0.0
    short_total = 0.0
    found = False
    for row in history:
        if not isinstance(row, dict):
            continue
        long_value = _coinalyze_value(row, "long", "long_liquidations", "l")
        short_value = _coinalyze_value(row, "short", "short_liquidations", "s")
        if long_value is not None:
            long_total += long_value
            found = True
        if short_value is not None:
            short_total += short_value
            found = True
    return (long_total, short_total) if found else (None, None)


def _coinalyze_market_score(row: dict[str, Any], asset: str) -> int:
    text = " ".join(
        str(row.get(key, ""))
        for key in ("symbol", "exchange", "market", "name", "base_asset", "quote_asset")
    ).lower()
    if asset.lower() not in text:
        return -100
    if any(blocked in text for blocked in COINALYZE_BLOCKED_EXCHANGES):
        return -50
    score = 0
    if "perp" in text or "perpetual" in text:
        score += 4
    if "usdt" in text or "usd" in text:
        score += 3
    for index, exchange in enumerate(COINALYZE_PREFERRED_EXCHANGES):
        if exchange in text:
            score += 10 - index
            break
    return score


async def _coinalyze_symbol(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[str | None, list[str]]:
    if not settings.coinalyze_api_key:
        return None, []
    data, error = await get_json(
        client,
        f"{COINALYZE}/future-markets",
        headers=_coinalyze_headers(settings),
        source="coinalyze_future_markets",
    )
    if error:
        return None, [error]
    if not isinstance(data, list):
        return None, ["coinalyze_future_markets: empty response"]
    candidates = [row for row in data if isinstance(row, dict)]
    candidates.sort(key=lambda row: _coinalyze_market_score(row, asset), reverse=True)
    best = candidates[0] if candidates and _coinalyze_market_score(candidates[0], asset) > 0 else None
    symbol = str(best.get("symbol")) if best and best.get("symbol") else None
    return symbol, [] if symbol else [f"coinalyze_future_markets: no suitable {asset} perpetual market found"]


async def _coinalyze_derivatives(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict, list[str]]:
    symbol, errors = await _coinalyze_symbol(client, settings, asset)
    if not symbol:
        return {}, errors
    headers = _coinalyze_headers(settings)
    now = int(datetime.now(UTC).timestamp())
    yesterday = int((datetime.now(UTC) - timedelta(days=1)).timestamp())
    data: dict[str, Any] = {"derivatives_primary_source": "coinalyze_free_api", "coinalyze_symbol": symbol}

    funding, error = await get_json(
        client,
        f"{COINALYZE}/funding-rate",
        params={"symbols": symbol},
        headers=headers,
        source="coinalyze_funding_rate",
    )
    if error:
        errors.append(error)
    elif isinstance(funding, list) and funding:
        data["funding_rate_now"] = _coinalyze_value(funding[0], "value", "funding_rate", "c")

    funding_history, error = await get_json(
        client,
        f"{COINALYZE}/funding-rate-history",
        params={"symbols": symbol, "interval": "4hour", "from": yesterday, "to": now},
        headers=headers,
        source="coinalyze_funding_rate_history",
    )
    if error:
        errors.append(error)
    else:
        funding_values = _coinalyze_history_values(funding_history, "value", "funding_rate")
        if len(funding_values) >= 2:
            data["funding_rate_8h_ago"] = funding_values[-2]

    oi, error = await get_json(
        client,
        f"{COINALYZE}/open-interest",
        params={"symbols": symbol, "convert_to_usd": "true"},
        headers=headers,
        source="coinalyze_open_interest",
    )
    if error:
        errors.append(error)
    elif isinstance(oi, list) and oi:
        data["open_interest_now"] = _coinalyze_value(oi[0], "value", "open_interest", "oi", "c")

    oi_history, error = await get_json(
        client,
        f"{COINALYZE}/open-interest-history",
        params={"symbols": symbol, "interval": "daily", "from": yesterday - 86400, "to": now, "convert_to_usd": "true"},
        headers=headers,
        source="coinalyze_open_interest_history",
    )
    if error:
        errors.append(error)
    else:
        oi_values = _coinalyze_history_values(oi_history, "value", "open_interest", "oi")
        if len(oi_values) >= 2:
            data["open_interest_change_24h_pct"] = percent_change(oi_values[-1], oi_values[-2])

    liquidations, error = await get_json(
        client,
        f"{COINALYZE}/liquidation-history",
        params={"symbols": symbol, "interval": "1hour", "from": yesterday, "to": now, "convert_to_usd": "true"},
        headers=headers,
        source="coinalyze_liquidation_history",
    )
    if error:
        errors.append(error)
    else:
        long_liq, short_liq = _coinalyze_liquidation_totals(liquidations)
        if long_liq is not None:
            data["long_liquidations_24h"] = round_float(long_liq, 2)
        if short_liq is not None:
            data["short_liquidations_24h"] = round_float(short_liq, 2)

    return {key: value for key, value in data.items() if value is not None}, errors


async def _deribit_perpetual(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    data, error = await get_json(
        client,
        DERIBIT_BOOK,
        params={"instrument_name": f"{asset}-PERPETUAL"},
        source="deribit_perpetual_summary",
    )
    if error:
        return {}, [error]
    rows = data.get("result", []) if isinstance(data, dict) else []
    if not rows:
        return {}, ["deribit_perpetual_summary: empty response"]
    row = rows[0]
    mark_price = safe_float(row.get("mark_price"))
    index_price = safe_float(row.get("estimated_delivery_price") or row.get("index_price"))
    return {
        "deribit_funding_rate_now": safe_float(row.get("current_funding")),
        "deribit_funding_8h": safe_float(row.get("funding_8h")),
        "deribit_open_interest_now": safe_float(row.get("open_interest")),
        "deribit_mark_price": mark_price,
        "deribit_index_price": index_price,
        "deribit_basis_pct": percent_change(mark_price, index_price),
        "deribit_volume_24h": safe_float(row.get("volume_usd")),
        "deribit_perpetual_source": "deribit_public_api",
    }, []


async def _hyperliquid_perpetual(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    data, error = await post_json(
        client,
        HYPERLIQUID_INFO,
        json_body={"type": "metaAndAssetCtxs"},
        source="hyperliquid_meta_asset_contexts",
    )
    if error:
        return {}, [error]
    if not isinstance(data, list) or len(data) < 2:
        return {}, ["hyperliquid_meta_asset_contexts: empty response"]
    meta, contexts = data[0], data[1]
    universe = meta.get("universe", []) if isinstance(meta, dict) else []
    if not isinstance(universe, list) or not isinstance(contexts, list):
        return {}, ["hyperliquid_meta_asset_contexts: malformed response"]
    for index, item in enumerate(universe):
        if not isinstance(item, dict) or item.get("name") != asset or index >= len(contexts):
            continue
        context = contexts[index]
        if not isinstance(context, dict):
            continue
        mark_price = safe_float(context.get("markPx"))
        index_price = safe_float(context.get("oraclePx"))
        return {
            "hyperliquid_funding_rate_now": safe_float(context.get("funding")),
            "hyperliquid_open_interest_now": safe_float(context.get("openInterest")),
            "hyperliquid_mark_price": mark_price,
            "hyperliquid_index_price": index_price,
            "hyperliquid_basis_pct": percent_change(mark_price, index_price),
            "hyperliquid_volume_24h": safe_float(context.get("dayNtlVlm")),
            "hyperliquid_perpetual_source": "hyperliquid_public_info_api",
        }, []
    return {}, [f"hyperliquid_meta_asset_contexts: {asset} not found"]


def _first_metric(*values: float | None) -> float | None:
    return next((value for value in values if value is not None), None)


async def fetch_derivatives(settings: Settings, asset: str, storage=None) -> LayerResult:
    symbol = ASSET_META[asset]["symbol"]
    errors: list[str] = []
    bybit_errors: list[str] = []
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        ticker_data, error = await get_json(
            client,
            f"{BYBIT}/v5/market/tickers",
            params={"category": "linear", "symbol": symbol},
            source="bybit_tickers",
        )
        if error:
            bybit_errors.append(error)
        funding_data, error = await get_json(
            client,
            f"{BYBIT}/v5/market/funding/history",
            params={"category": "linear", "symbol": symbol, "limit": 2},
            source="bybit_funding_history",
        )
        if error:
            bybit_errors.append(error)
        oi_data, error = await get_json(
            client,
            f"{BYBIT}/v5/market/open-interest",
            params={"category": "linear", "symbol": symbol, "intervalTime": "1d", "limit": 2},
            source="bybit_open_interest",
        )
        if error:
            bybit_errors.append(error)
        coinalyze_data, coinalyze_errors = await _coinalyze_derivatives(client, settings, asset)
        errors.extend(coinalyze_errors)
        deribit_perp_data, deribit_perp_errors = await _deribit_perpetual(client, asset)
        errors.extend(deribit_perp_errors)
        hyperliquid_data, hyperliquid_errors = await _hyperliquid_perpetual(client, asset)
        errors.extend(hyperliquid_errors)
        options_data, options_errors = await fetch_deribit_put_call(client, asset)
        errors.extend(options_errors)

    bybit_blocked = bool(bybit_errors) and all(is_http_forbidden_error(error) for error in bybit_errors)
    if bybit_errors and not bybit_blocked:
        errors.extend(bybit_errors)

    ticker = {}
    if isinstance(ticker_data, dict) and ticker_data.get("retCode") == 0:
        rows = ticker_data.get("result", {}).get("list", [])
        ticker = rows[0] if rows else {}
    else:
        if not bybit_blocked:
            errors.append("bybit_tickers: empty or non-OK response")

    funding_rows = []
    if isinstance(funding_data, dict) and funding_data.get("retCode") == 0:
        funding_rows = funding_data.get("result", {}).get("list", [])
        funding_rows = sorted(funding_rows, key=lambda row: int(row.get("fundingRateTimestamp", 0)))
    elif funding_data is not None:
        errors.append("bybit_funding_history: empty or non-OK response")

    oi_rows = []
    if isinstance(oi_data, dict) and oi_data.get("retCode") == 0:
        oi_rows = oi_data.get("result", {}).get("list", [])
        oi_rows = sorted(oi_rows, key=lambda row: int(row.get("timestamp", 0)))
    elif oi_data is not None:
        errors.append("bybit_open_interest: empty or non-OK response")
    bybit_available = not bybit_blocked and bool(ticker or funding_rows or oi_rows)

    bybit_funding_now = safe_float(ticker.get("fundingRate"))
    bybit_funding_8h_ago = safe_float(funding_rows[-2].get("fundingRate")) if len(funding_rows) >= 2 else None
    bybit_oi_now_value = safe_float(ticker.get("openInterestValue")) or safe_float(ticker.get("openInterest"))
    bybit_oi_change = None
    if len(oi_rows) >= 2:
        bybit_oi_change = percent_change(
            safe_float(oi_rows[-1].get("openInterest")),
            safe_float(oi_rows[-2].get("openInterest")),
        )

    bybit_mark_price = safe_float(ticker.get("markPrice"))
    bybit_index_price = safe_float(ticker.get("indexPrice"))
    bybit_basis_pct = percent_change(bybit_mark_price, bybit_index_price)
    price_change = safe_float(ticker.get("price24hPcnt"))
    if price_change is not None:
        price_change = round(price_change * 100, 2)

    since_ms = int((time.time() - 24 * 60 * 60) * 1000)
    liquidation_stats = storage.get_liquidation_stats(asset, since_ms) if storage is not None else {"long": {"notional": 0, "count": 0}, "short": {"notional": 0, "count": 0}}
    local_long_liq = round_float(liquidation_stats["long"]["notional"], 2)
    local_short_liq = round_float(liquidation_stats["short"]["notional"], 2)
    funding_now = _first_metric(
        coinalyze_data.get("funding_rate_now"),
        bybit_funding_now,
        deribit_perp_data.get("deribit_funding_rate_now"),
        hyperliquid_data.get("hyperliquid_funding_rate_now"),
    )
    funding_8h_ago = _first_metric(coinalyze_data.get("funding_rate_8h_ago"), bybit_funding_8h_ago)
    oi_now_value = _first_metric(
        coinalyze_data.get("open_interest_now"),
        bybit_oi_now_value,
        deribit_perp_data.get("deribit_open_interest_now"),
        hyperliquid_data.get("hyperliquid_open_interest_now"),
    )
    oi_change = _first_metric(coinalyze_data.get("open_interest_change_24h_pct"), bybit_oi_change)
    basis_pct = _first_metric(
        bybit_basis_pct,
        deribit_perp_data.get("deribit_basis_pct"),
        hyperliquid_data.get("hyperliquid_basis_pct"),
    )
    long_liq = _first_metric(coinalyze_data.get("long_liquidations_24h"), local_long_liq)
    short_liq = _first_metric(coinalyze_data.get("short_liquidations_24h"), local_short_liq)
    if long_liq and short_liq and long_liq > short_liq * 2:
        liquidation_bias = "long_flush"
    elif long_liq and short_liq and short_liq > long_liq * 2:
        liquidation_bias = "short_flush"
    elif long_liq or short_liq:
        liquidation_bias = "mixed_liquidations"
    else:
        liquidation_bias = "liquidation_data_limited"

    data = {
        "asset": asset,
        "source_note": "Derivatives metrics use Coinalyze when configured, Bybit when reachable, and Deribit/Hyperliquid public APIs as free fallbacks.",
        "bybit_available": bybit_available,
        "coinalyze_available": bool(coinalyze_data),
        "deribit_perpetual_available": bool(deribit_perp_data),
        "hyperliquid_available": bool(hyperliquid_data),
        "funding_rate_now": funding_now,
        "funding_rate_8h_ago": funding_8h_ago,
        "funding_rate_change": round_float(
            funding_now - funding_8h_ago if funding_now is not None and funding_8h_ago is not None else None,
            6,
        ),
        "open_interest_now": oi_now_value,
        "open_interest_change_24h_pct": oi_change,
        "long_liquidations_24h": long_liq,
        "short_liquidations_24h": short_liq,
        "long_liquidation_events_24h": liquidation_stats["long"]["count"],
        "short_liquidation_events_24h": liquidation_stats["short"]["count"],
        "liquidation_bias": liquidation_bias,
        "basis_pct": basis_pct,
        "put_call_ratio": options_data.get("put_call_ratio"),
        "put_call_volume_ratio": options_data.get("put_call_volume_ratio"),
        "options": options_data,
        "coinalyze": coinalyze_data,
        "deribit_perpetual": deribit_perp_data,
        "hyperliquid_perpetual": hyperliquid_data,
        "derivatives_signal": _signal(oi_change, price_change, funding_now, funding_8h_ago, long_liq, short_liq),
        "bybit_next_funding_time": iso_from_ms(ticker.get("nextFundingTime")),
    }
    source_parts = []
    if coinalyze_data:
        source_parts.append("coinalyze")
    if bybit_available:
        source_parts.append("bybit")
    if deribit_perp_data or options_data:
        source_parts.append("deribit")
    if hyperliquid_data:
        source_parts.append("hyperliquid")
    source_parts.append("local_liquidations")
    source = "/".join(dict.fromkeys(source_parts))
    return LayerResult(layer="derivatives", source=source, data=data, errors=errors)
