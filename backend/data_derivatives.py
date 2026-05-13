from __future__ import annotations

import time
from typing import Any

import httpx

from backend.config import Settings
from backend.http_client import get_json, is_http_forbidden_error, post_json
from backend.data_options import fetch_deribit_put_call
from backend.models import LayerResult
from backend.utils import ASSET_META, iso_from_ms, percent_change, round_float, safe_float


BYBIT = "https://api.bybit.com"
COINALYZE = "https://api.coinalyze.net/v1"
DERIBIT_BOOK_SUMMARY = "https://www.deribit.com/api/v2/public/get_book_summary_by_instrument"
HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"


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


def _first_row(data: Any) -> dict[str, Any]:
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]
    if isinstance(data, dict) and isinstance(data.get("result"), list) and data["result"] and isinstance(data["result"][0], dict):
        return data["result"][0]
    return {}


def _history_rows(data: Any) -> list[dict[str, Any]]:
    row = _first_row(data)
    history = row.get("history")
    if isinstance(history, list):
        return [item for item in history if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _coinalyze_value(row: dict[str, Any]) -> float | None:
    for key in ("value", "c", "close", "rate", "funding_rate", "open_interest"):
        value = safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _liquidation_value(row: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = safe_float(row.get(key))
        if value is not None:
            return value
    return None


def _liquidation_bias(long_liq: float | None, short_liq: float | None) -> str:
    if long_liq and short_liq and long_liq > short_liq * 2:
        return "long_flush"
    if long_liq and short_liq and short_liq > long_liq * 2:
        return "short_flush"
    if long_liq or short_liq:
        return "mixed_liquidations"
    return "liquidation_data_limited"


def _select_coinalyze_symbol(markets: Any, asset: str) -> str | None:
    if not isinstance(markets, list):
        return None
    preferred: list[tuple[int, str]] = []
    for row in markets:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        haystack = " ".join(str(row.get(key) or "") for key in ("symbol", "base_asset", "quote_asset", "exchange", "market_type", "type")).lower()
        if asset.lower() not in haystack or "perp" not in haystack:
            continue
        score = 0
        exchange = str(row.get("exchange") or "").lower()
        quote = str(row.get("quote_asset") or symbol).upper()
        if "USDT" in quote or "USD" in quote:
            score += 4
        if "bybit" not in exchange and "binance" not in exchange:
            score += 3
        if asset.upper() in symbol.upper():
            score += 2
        preferred.append((score, symbol))
    if not preferred:
        return None
    return sorted(preferred, reverse=True)[0][1]


async def _fetch_coinalyze_derivatives(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict[str, Any], list[str]]:
    if not settings.coinalyze_api_key:
        return {}, []

    errors: list[str] = []
    auth = {"api_key": settings.coinalyze_api_key}
    markets, error = await get_json(client, f"{COINALYZE}/future-markets", params=auth, source="coinalyze_future_markets")
    if error:
        return {}, [error]
    symbol = _select_coinalyze_symbol(markets, asset)
    if symbol is None:
        return {}, ["coinalyze_future_markets: no suitable perpetual market"]

    now = int(time.time())
    day_ago = now - 24 * 60 * 60
    ten_hours_ago = now - 10 * 60 * 60
    common = {"symbols": symbol, **auth}
    funding_now_data, error = await get_json(client, f"{COINALYZE}/funding-rate", params=common, source="coinalyze_funding_rate")
    if error:
        errors.append(error)
    funding_history_data, error = await get_json(
        client,
        f"{COINALYZE}/funding-rate-history",
        params={**common, "interval": "1hour", "from": ten_hours_ago, "to": now},
        source="coinalyze_funding_history",
    )
    if error:
        errors.append(error)
    oi_now_data, error = await get_json(client, f"{COINALYZE}/open-interest", params=common, source="coinalyze_open_interest")
    if error:
        errors.append(error)
    oi_history_data, error = await get_json(
        client,
        f"{COINALYZE}/open-interest-history",
        params={**common, "interval": "1hour", "from": day_ago, "to": now},
        source="coinalyze_open_interest_history",
    )
    if error:
        errors.append(error)
    liquidation_data, error = await get_json(
        client,
        f"{COINALYZE}/liquidation-history",
        params={**common, "interval": "1hour", "from": day_ago, "to": now},
        source="coinalyze_liquidation_history",
    )
    if error:
        errors.append(error)

    funding_now = _coinalyze_value(_first_row(funding_now_data))
    funding_history = sorted(_history_rows(funding_history_data), key=lambda row: safe_float(row.get("t")) or 0)
    funding_8h_ago = _coinalyze_value(funding_history[0]) if funding_history else None
    if funding_now is None and funding_history:
        funding_now = _coinalyze_value(funding_history[-1])

    oi_now = _coinalyze_value(_first_row(oi_now_data))
    oi_history = sorted(_history_rows(oi_history_data), key=lambda row: safe_float(row.get("t")) or 0)
    oi_24h_ago = _coinalyze_value(oi_history[0]) if oi_history else None
    if oi_now is None and oi_history:
        oi_now = _coinalyze_value(oi_history[-1])

    long_liq = short_liq = 0.0
    for row in _history_rows(liquidation_data):
        long_liq += _liquidation_value(row, ("l", "long", "long_liquidations", "long_liquidations_usd")) or 0.0
        short_liq += _liquidation_value(row, ("s", "short", "short_liquidations", "short_liquidations_usd")) or 0.0

    return {
        "symbol": symbol,
        "funding_rate_now": funding_now,
        "funding_rate_8h_ago": funding_8h_ago,
        "funding_rate_change": round_float(funding_now - funding_8h_ago if funding_now is not None and funding_8h_ago is not None else None, 6),
        "open_interest_now": oi_now,
        "open_interest_change_24h_pct": percent_change(oi_now, oi_24h_ago),
        "long_liquidations_24h": round_float(long_liq, 2) if long_liq else None,
        "short_liquidations_24h": round_float(short_liq, 2) if short_liq else None,
        "liquidation_bias": _liquidation_bias(long_liq, short_liq),
    }, errors


async def _fetch_deribit_perpetual(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    data, error = await get_json(
        client,
        DERIBIT_BOOK_SUMMARY,
        params={"instrument_name": f"{asset}-PERPETUAL"},
        source="deribit_perpetual_summary",
    )
    if error:
        return {}, [error]
    row = _first_row(data)
    if not row:
        return {}, ["deribit_perpetual_summary: empty response"]
    funding_now = safe_float(row.get("current_funding"))
    funding_8h = safe_float(row.get("funding_8h"))
    mark_price = safe_float(row.get("mark_price"))
    index_price = safe_float(row.get("estimated_delivery_price")) or safe_float(row.get("underlying_price"))
    return {
        "instrument_name": row.get("instrument_name") or f"{asset}-PERPETUAL",
        "funding_rate_now": funding_now,
        "funding_rate_8h_ago": funding_8h,
        "funding_rate_change": round_float(funding_now - funding_8h if funding_now is not None and funding_8h is not None else None, 6),
        "open_interest_now": safe_float(row.get("open_interest")),
        "mark_price": mark_price,
        "index_price": index_price,
        "basis_pct": percent_change(mark_price, index_price),
        "volume_usd": safe_float(row.get("volume_usd")),
    }, []


async def _fetch_hyperliquid_perpetual(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    data, error = await post_json(client, HYPERLIQUID_INFO, json={"type": "metaAndAssetCtxs"}, source="hyperliquid_meta_asset_contexts")
    if error:
        return {}, [error]
    if not isinstance(data, list) or len(data) < 2:
        return {}, ["hyperliquid_meta_asset_contexts: empty response"]
    universe = data[0].get("universe") if isinstance(data[0], dict) else None
    contexts = data[1]
    if not isinstance(universe, list) or not isinstance(contexts, list):
        return {}, ["hyperliquid_meta_asset_contexts: unexpected response"]
    for index, market in enumerate(universe):
        if not isinstance(market, dict) or market.get("name") != asset:
            continue
        row = contexts[index] if index < len(contexts) and isinstance(contexts[index], dict) else {}
        mark_price = safe_float(row.get("markPx"))
        oracle_price = safe_float(row.get("oraclePx"))
        return {
            "symbol": asset,
            "funding_rate_now": safe_float(row.get("funding")),
            "open_interest_now": safe_float(row.get("openInterest")),
            "mark_price": mark_price,
            "index_price": oracle_price,
            "basis_pct": percent_change(mark_price, oracle_price),
            "volume_usd": safe_float(row.get("dayNtlVlm")),
        }, []
    return {}, [f"hyperliquid_meta_asset_contexts: {asset} market not found"]


def _merge_metric(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


async def fetch_derivatives(settings: Settings, asset: str, storage=None) -> LayerResult:
    symbol = ASSET_META[asset]["symbol"]
    errors: list[str] = []
    bybit_errors: list[str] = []
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        coinalyze_data, coinalyze_errors = await _fetch_coinalyze_derivatives(client, settings, asset)
        if coinalyze_errors:
            errors.extend(coinalyze_errors)
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
        deribit_perpetual, deribit_perpetual_errors = await _fetch_deribit_perpetual(client, asset)
        hyperliquid_perpetual, hyperliquid_errors = await _fetch_hyperliquid_perpetual(client, asset)
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

    funding_now = safe_float(ticker.get("fundingRate"))
    funding_8h_ago = safe_float(funding_rows[-2].get("fundingRate")) if len(funding_rows) >= 2 else None
    bybit_funding_change = round_float(
        funding_now - funding_8h_ago if funding_now is not None and funding_8h_ago is not None else None,
        6,
    )
    oi_now_value = safe_float(ticker.get("openInterestValue")) or safe_float(ticker.get("openInterest"))
    oi_change = None
    if len(oi_rows) >= 2:
        oi_change = percent_change(
            safe_float(oi_rows[-1].get("openInterest")),
            safe_float(oi_rows[-2].get("openInterest")),
        )

    mark_price = safe_float(ticker.get("markPrice"))
    index_price = safe_float(ticker.get("indexPrice"))
    basis_pct = percent_change(mark_price, index_price)
    price_change = safe_float(ticker.get("price24hPcnt"))
    if price_change is not None:
        price_change = round(price_change * 100, 2)

    since_ms = int((time.time() - 24 * 60 * 60) * 1000)
    liquidation_stats = storage.get_liquidation_stats(asset, since_ms) if storage is not None else {"long": {"notional": 0, "count": 0}, "short": {"notional": 0, "count": 0}}
    local_long_liq = round_float(liquidation_stats["long"]["notional"], 2)
    local_short_liq = round_float(liquidation_stats["short"]["notional"], 2)
    long_liq = _merge_metric(coinalyze_data.get("long_liquidations_24h"), local_long_liq)
    short_liq = _merge_metric(coinalyze_data.get("short_liquidations_24h"), local_short_liq)
    liquidation_bias = _merge_metric(coinalyze_data.get("liquidation_bias"), _liquidation_bias(local_long_liq, local_short_liq))

    merged_funding_now = _merge_metric(coinalyze_data.get("funding_rate_now"), funding_now, deribit_perpetual.get("funding_rate_now"), hyperliquid_perpetual.get("funding_rate_now"))
    merged_funding_8h_ago = _merge_metric(coinalyze_data.get("funding_rate_8h_ago"), funding_8h_ago, deribit_perpetual.get("funding_rate_8h_ago"))
    merged_funding_change = _merge_metric(
        coinalyze_data.get("funding_rate_change"),
        bybit_funding_change,
        deribit_perpetual.get("funding_rate_change"),
        round_float(merged_funding_now - merged_funding_8h_ago if merged_funding_now is not None and merged_funding_8h_ago is not None else None, 6),
    )
    merged_oi_now = _merge_metric(coinalyze_data.get("open_interest_now"), oi_now_value, deribit_perpetual.get("open_interest_now"), hyperliquid_perpetual.get("open_interest_now"))
    merged_oi_change = _merge_metric(coinalyze_data.get("open_interest_change_24h_pct"), oi_change)
    merged_basis_pct = _merge_metric(basis_pct, deribit_perpetual.get("basis_pct"), hyperliquid_perpetual.get("basis_pct"))

    if not deribit_perpetual:
        errors.extend(deribit_perpetual_errors)
    if not hyperliquid_perpetual:
        errors.extend(hyperliquid_errors)

    data = {
        "asset": asset,
        "source_note": (
            "Bybit public V5 market endpoints returned HTTP 403 in this runtime; derivatives metrics fall back to Coinalyze, Deribit, Hyperliquid, and locally collected liquidation data."
            if bybit_blocked
            else "Derivatives metrics use Coinalyze when configured, then Bybit, Deribit, Hyperliquid, and local liquidation data as fallbacks."
        ),
        "bybit_available": not bybit_blocked,
        "coinalyze_available": bool(coinalyze_data),
        "deribit_perpetual_available": bool(deribit_perpetual),
        "hyperliquid_available": bool(hyperliquid_perpetual),
        "funding_rate_now": merged_funding_now,
        "funding_rate_8h_ago": merged_funding_8h_ago,
        "funding_rate_change": merged_funding_change,
        "open_interest_now": merged_oi_now,
        "open_interest_change_24h_pct": merged_oi_change,
        "long_liquidations_24h": long_liq,
        "short_liquidations_24h": short_liq,
        "long_liquidation_events_24h": liquidation_stats["long"]["count"],
        "short_liquidation_events_24h": liquidation_stats["short"]["count"],
        "liquidation_bias": liquidation_bias,
        "basis_pct": merged_basis_pct,
        "put_call_ratio": options_data.get("put_call_ratio"),
        "put_call_volume_ratio": options_data.get("put_call_volume_ratio"),
        "options": options_data,
        "coinalyze": coinalyze_data,
        "deribit_perpetual": deribit_perpetual,
        "hyperliquid_perpetual": hyperliquid_perpetual,
        "derivatives_signal": _signal(merged_oi_change, price_change, merged_funding_now, merged_funding_8h_ago, long_liq, short_liq),
        "bybit_next_funding_time": iso_from_ms(ticker.get("nextFundingTime")),
    }
    source_parts = []
    if coinalyze_data:
        source_parts.append("coinalyze")
    if not bybit_blocked and ticker:
        source_parts.append("bybit")
    if deribit_perpetual or options_data:
        source_parts.append("deribit")
    if hyperliquid_perpetual:
        source_parts.append("hyperliquid")
    if local_long_liq or local_short_liq:
        source_parts.append("local_liquidations")
    source = "/".join(source_parts) or "deribit/local_liquidations"
    return LayerResult(layer="derivatives", source=source, data=data, errors=errors)
