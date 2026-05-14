from __future__ import annotations

import time
from typing import Any

import httpx

from backend.config import Settings
from backend.data_quality import layer_quality, metric_meta
from backend.http_client import get_json, is_http_forbidden_error, post_json
from backend.data_options import fetch_deribit_put_call
from backend.models import LayerResult
from backend.utils import ASSET_META, iso_from_ms, percent_change, round_float, safe_float


BYBIT = "https://api.bybit.com"
COINALYZE = "https://api.coinalyze.net/v1"
DERIBIT_BOOK_SUMMARY = "https://www.deribit.com/api/v2/public/get_book_summary_by_instrument"
HYPERLIQUID_INFO = "https://api.hyperliquid.xyz/info"
MEXC_CONTRACT = "https://contract.mexc.com"
BITGET = "https://api.bitget.com"
OKX = "https://www.okx.com"
GATE = "https://api.gateio.ws/api/v4"
COINGECKO_DEMO = "https://api.coingecko.com/api/v3"
COINGECKO_PRO = "https://pro-api.coingecko.com/api/v3"


DERIVATIVE_PROVIDER_FIELDS = (
    ("mexc_contract", "mexc_contract_available"),
    ("bitget_contract", "bitget_contract_available"),
    ("okx_contract", "okx_contract_available"),
    ("gate_futures", "gate_futures_available"),
    ("coingecko_derivatives", "coingecko_derivatives_available"),
)


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


def _contract_formats(asset: str) -> dict[str, str]:
    return {
        "compact": ASSET_META[asset]["symbol"],
        "underscore": f"{asset}_USDT",
        "okx_swap": f"{asset}-USDT-SWAP",
    }


def _derivatives_payload(
    *,
    provider: str,
    symbol: str,
    funding_rate_now: float | None = None,
    funding_rate_8h_ago: float | None = None,
    open_interest_now: float | None = None,
    open_interest_change_24h_pct: float | None = None,
    mark_price: float | None = None,
    index_price: float | None = None,
    basis_pct: float | None = None,
    volume_usd: float | None = None,
    next_funding_time: str | None = None,
    error: str | None = None,
    unit_note: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "provider": provider,
        "symbol": symbol,
        "funding_rate_now": funding_rate_now,
        "funding_rate_8h_ago": funding_rate_8h_ago,
        "funding_rate_change": round_float(
            funding_rate_now - funding_rate_8h_ago
            if funding_rate_now is not None and funding_rate_8h_ago is not None
            else None,
            6,
        ),
        "open_interest_now": open_interest_now,
        "open_interest_change_24h_pct": open_interest_change_24h_pct,
        "mark_price": mark_price,
        "index_price": index_price,
        "basis_pct": basis_pct if basis_pct is not None else percent_change(mark_price, index_price),
        "volume_usd": volume_usd,
        "next_funding_time": next_funding_time,
    }
    if error:
        payload["error"] = error
    if unit_note:
        payload["unit_note"] = unit_note
    return payload


def _normalize_oi_notional(raw_oi: float | None, price: float | None, *, assume_base_units: bool) -> float | None:
    if raw_oi is None:
        return None
    if assume_base_units and price is not None:
        return round_float(raw_oi * price, 2)
    return raw_oi


def _has_derivative_signal(data: dict[str, Any]) -> bool:
    return any(
        data.get(key) is not None
        for key in (
            "funding_rate_now",
            "open_interest_now",
            "basis_pct",
            "volume_usd",
            "mark_price",
            "index_price",
        )
    )


async def _fetch_mexc_contract(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _contract_formats(asset)["underscore"]
    data, error = await get_json(
        client,
        f"{MEXC_CONTRACT}/api/v1/contract/ticker",
        params={"symbol": symbol},
        source="mexc_contract_ticker",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "mexc_contract_ticker: empty response"]
    row = data.get("data")
    if isinstance(row, list):
        row = next((item for item in row if isinstance(item, dict) and item.get("symbol") == symbol), row[0] if row else {})
    if not isinstance(row, dict) or not row:
        return {}, [f"mexc_contract_ticker: {data.get('message') or 'empty result'}"]

    mark_price = safe_float(row.get("fairPrice")) or safe_float(row.get("lastPrice"))
    index_price = safe_float(row.get("indexPrice"))
    raw_oi = safe_float(row.get("openInterest")) or safe_float(row.get("holdVol"))
    return _derivatives_payload(
        provider="mexc",
        symbol=symbol,
        funding_rate_now=safe_float(row.get("fundingRate")),
        open_interest_now=_normalize_oi_notional(raw_oi, mark_price or index_price, assume_base_units=False),
        mark_price=mark_price,
        index_price=index_price,
        volume_usd=safe_float(row.get("amount24")) or safe_float(row.get("volume24")),
        unit_note="MEXC holdVol/openInterest may be contract/base units; value is preserved as provider best effort.",
    ), []


async def _fetch_bitget_contract(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _contract_formats(asset)["compact"]
    errors: list[str] = []
    funding_data, error = await get_json(
        client,
        f"{BITGET}/api/v2/mix/market/current-fund-rate",
        params={"symbol": symbol, "productType": "USDT-FUTURES"},
        source="bitget_contract_funding",
    )
    if error:
        errors.append(error)
    oi_data, error = await get_json(
        client,
        f"{BITGET}/api/v2/mix/market/open-interest",
        params={"symbol": symbol, "productType": "USDT-FUTURES"},
        source="bitget_contract_open_interest",
    )
    if error:
        errors.append(error)
    ticker_data, error = await get_json(
        client,
        f"{BITGET}/api/v2/mix/market/ticker",
        params={"symbol": symbol, "productType": "USDT-FUTURES"},
        source="bitget_contract_ticker",
    )
    if error:
        errors.append(error)

    funding_row = _first_row(funding_data.get("data") if isinstance(funding_data, dict) else funding_data)
    ticker_row = _first_row(ticker_data.get("data") if isinstance(ticker_data, dict) else ticker_data)
    oi_row = oi_data.get("data") if isinstance(oi_data, dict) and isinstance(oi_data.get("data"), dict) else _first_row(oi_data.get("data") if isinstance(oi_data, dict) else oi_data)
    mark_price = safe_float(ticker_row.get("markPrice")) or safe_float(ticker_row.get("lastPr")) or safe_float(ticker_row.get("last"))
    index_price = safe_float(ticker_row.get("indexPrice"))
    raw_oi = (
        safe_float(oi_row.get("openInterest"))
        or safe_float(oi_row.get("size"))
        or safe_float(oi_row.get("holdingAmount"))
        or safe_float(ticker_row.get("openInterest"))
    )
    payload = _derivatives_payload(
        provider="bitget",
        symbol=symbol,
        funding_rate_now=safe_float(funding_row.get("fundingRate")) or safe_float(ticker_row.get("fundingRate")),
        open_interest_now=_normalize_oi_notional(raw_oi, mark_price or index_price, assume_base_units=True),
        mark_price=mark_price,
        index_price=index_price,
        volume_usd=safe_float(ticker_row.get("quoteVolume")) or safe_float(ticker_row.get("usdtVolume")),
        unit_note="Open interest is converted with mark/index price when Bitget returns base-size units.",
    )
    return (payload, errors) if _has_derivative_signal(payload) else ({}, errors or ["bitget_contract: no usable fields"])


async def _fetch_okx_contract(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _contract_formats(asset)["okx_swap"]
    errors: list[str] = []
    funding_data, error = await get_json(
        client,
        f"{OKX}/api/v5/public/funding-rate",
        params={"instId": symbol},
        source="okx_contract_funding",
    )
    if error:
        errors.append(error)
    oi_data, error = await get_json(
        client,
        f"{OKX}/api/v5/public/open-interest",
        params={"instType": "SWAP", "instId": symbol},
        source="okx_contract_open_interest",
    )
    if error:
        errors.append(error)
    ticker_data, error = await get_json(
        client,
        f"{OKX}/api/v5/market/ticker",
        params={"instId": symbol},
        source="okx_contract_ticker",
    )
    if error:
        errors.append(error)

    funding_row = _first_row(funding_data.get("data") if isinstance(funding_data, dict) else funding_data)
    oi_row = _first_row(oi_data.get("data") if isinstance(oi_data, dict) else oi_data)
    ticker_row = _first_row(ticker_data.get("data") if isinstance(ticker_data, dict) else ticker_data)
    mark_price = safe_float(ticker_row.get("last"))
    raw_oi = safe_float(oi_row.get("oiCcy")) or safe_float(oi_row.get("oi"))
    assume_base_units = safe_float(oi_row.get("oiCcy")) is not None
    payload = _derivatives_payload(
        provider="okx",
        symbol=symbol,
        funding_rate_now=safe_float(funding_row.get("fundingRate")),
        open_interest_now=_normalize_oi_notional(raw_oi, mark_price, assume_base_units=assume_base_units),
        mark_price=mark_price,
        volume_usd=safe_float(ticker_row.get("volCcy24h")),
        next_funding_time=iso_from_ms(funding_row.get("nextFundingTime")),
        unit_note="OKX oiCcy is converted with ticker last price when available; oi contract counts are otherwise preserved.",
    )
    return (payload, errors) if _has_derivative_signal(payload) else ({}, errors or ["okx_contract: no usable fields"])


async def _fetch_gate_futures(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _contract_formats(asset)["underscore"]
    errors: list[str] = []
    ticker_data, error = await get_json(
        client,
        f"{GATE}/futures/usdt/tickers",
        params={"contract": symbol},
        source="gate_futures_ticker",
    )
    if error:
        errors.append(error)
    contract_data, error = await get_json(
        client,
        f"{GATE}/futures/usdt/contracts/{symbol}",
        source="gate_futures_contract",
    )
    if error:
        errors.append(error)

    ticker_row = _first_row(ticker_data)
    contract_row = contract_data if isinstance(contract_data, dict) else {}
    mark_price = safe_float(ticker_row.get("mark_price")) or safe_float(contract_row.get("mark_price")) or safe_float(ticker_row.get("last"))
    index_price = safe_float(ticker_row.get("index_price")) or safe_float(contract_row.get("index_price"))
    raw_oi = safe_float(ticker_row.get("open_interest")) or safe_float(contract_row.get("open_interest"))
    payload = _derivatives_payload(
        provider="gate",
        symbol=symbol,
        funding_rate_now=safe_float(ticker_row.get("funding_rate")) or safe_float(contract_row.get("funding_rate")),
        open_interest_now=_normalize_oi_notional(raw_oi, mark_price or index_price, assume_base_units=False),
        mark_price=mark_price,
        index_price=index_price,
        volume_usd=safe_float(ticker_row.get("volume_24h_quote")) or safe_float(ticker_row.get("volume_24h_settle")),
        unit_note="Gate futures open interest is preserved as returned when contract multiplier details are unavailable.",
    )
    return (payload, errors) if _has_derivative_signal(payload) else ({}, errors or ["gate_futures: no usable fields"])


async def _fetch_coingecko_derivatives(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict[str, Any], list[str]]:
    base_url = COINGECKO_PRO if settings.coingecko_plan.lower() == "pro" else COINGECKO_DEMO
    header_name = "x-cg-pro-api-key" if settings.coingecko_plan.lower() == "pro" else "x-cg-demo-api-key"
    headers = {header_name: settings.coingecko_api_key} if settings.coingecko_api_key else {}
    data, error = await get_json(
        client,
        f"{base_url}/derivatives",
        headers=headers,
        source="coingecko_derivatives",
    )
    if error or not isinstance(data, list):
        return {}, [error or "coingecko_derivatives: empty response"]

    candidates: list[tuple[int, dict[str, Any]]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        haystack = " ".join(str(row.get(key) or "") for key in ("symbol", "base", "target", "market", "contract_type", "index_id")).upper()
        if asset.upper() not in haystack or "PERPETUAL" not in haystack:
            continue
        score = 0
        if "USDT" in haystack or "USD" in haystack:
            score += 4
        if any(exchange in haystack for exchange in ("MEXC", "BITGET", "OKX", "GATE")):
            score += 2
        candidates.append((score, row))
    if not candidates:
        return {}, ["coingecko_derivatives: no suitable perpetual ticker"]
    row = sorted(candidates, key=lambda item: item[0], reverse=True)[0][1]
    return _derivatives_payload(
        provider="coingecko",
        symbol=str(row.get("symbol") or row.get("index_id") or f"{asset}-PERP"),
        funding_rate_now=safe_float(row.get("funding_rate")),
        open_interest_now=safe_float(row.get("open_interest")),
        basis_pct=safe_float(row.get("basis")),
        volume_usd=safe_float(row.get("volume_24h")),
        unit_note="CoinGecko derivatives are aggregate exchange tickers and are lower precision than direct exchange endpoints.",
    ), []


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
        direct_provider_results: list[tuple[str, str, dict[str, Any], list[str]]] = []
        for data_key, flag_key, fetcher in (
            ("mexc_contract", "mexc_contract_available", _fetch_mexc_contract),
            ("bitget_contract", "bitget_contract_available", _fetch_bitget_contract),
            ("okx_contract", "okx_contract_available", _fetch_okx_contract),
            ("gate_futures", "gate_futures_available", _fetch_gate_futures),
        ):
            provider_data, provider_errors = await fetcher(client, asset)
            direct_provider_results.append((data_key, flag_key, provider_data, provider_errors))

        coingecko_derivatives, coingecko_derivatives_errors = await _fetch_coingecko_derivatives(client, settings, asset)
        direct_provider_results.append(
            (
                "coingecko_derivatives",
                "coingecko_derivatives_available",
                coingecko_derivatives,
                coingecko_derivatives_errors,
            )
        )

        coinalyze_data, coinalyze_errors = await _fetch_coinalyze_derivatives(client, settings, asset)
        deribit_perpetual, deribit_perpetual_errors = await _fetch_deribit_perpetual(client, asset)
        hyperliquid_perpetual, hyperliquid_errors = await _fetch_hyperliquid_perpetual(client, asset)
        options_data, options_errors = await fetch_deribit_put_call(client, asset)
        errors.extend(options_errors)

        bybit_provider: dict[str, Any] = {}
        direct_or_existing_available = any(
            _has_derivative_signal(provider_data) for _, _, provider_data, _ in direct_provider_results
        ) or any(_has_derivative_signal(data) for data in (coinalyze_data, deribit_perpetual, hyperliquid_perpetual))
        ticker_data = funding_data = oi_data = None
        if not direct_or_existing_available:
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

    bybit_blocked = bool(bybit_errors) and all(is_http_forbidden_error(error) for error in bybit_errors)
    if bybit_errors and not bybit_blocked:
        errors.extend(bybit_errors)

    ticker = {}
    if isinstance(ticker_data, dict) and ticker_data.get("retCode") == 0:
        rows = ticker_data.get("result", {}).get("list", [])
        ticker = rows[0] if rows else {}
    else:
        if ticker_data is not None and not bybit_blocked:
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
    if ticker:
        bybit_provider = _derivatives_payload(
            provider="bybit",
            symbol=symbol,
            funding_rate_now=funding_now,
            funding_rate_8h_ago=funding_8h_ago,
            open_interest_now=oi_now_value,
            open_interest_change_24h_pct=oi_change,
            mark_price=mark_price,
            index_price=index_price,
            basis_pct=basis_pct,
            next_funding_time=iso_from_ms(ticker.get("nextFundingTime")),
        )

    since_ms = int((time.time() - 24 * 60 * 60) * 1000)
    liquidation_stats = storage.get_liquidation_stats(asset, since_ms) if storage is not None else {"long": {"notional": 0, "count": 0}, "short": {"notional": 0, "count": 0}}
    local_long_liq = round_float(liquidation_stats["long"]["notional"], 2)
    local_short_liq = round_float(liquidation_stats["short"]["notional"], 2)
    long_liq = _merge_metric(coinalyze_data.get("long_liquidations_24h"), local_long_liq)
    short_liq = _merge_metric(coinalyze_data.get("short_liquidations_24h"), local_short_liq)
    liquidation_bias = _merge_metric(coinalyze_data.get("liquidation_bias"), _liquidation_bias(local_long_liq, local_short_liq))

    priority_data = [provider_data for _, _, provider_data, _ in direct_provider_results]
    priority_data.extend([coinalyze_data, deribit_perpetual, hyperliquid_perpetual, bybit_provider])
    merged_funding_now = _merge_metric(*(data.get("funding_rate_now") for data in priority_data))
    merged_funding_8h_ago = _merge_metric(*(data.get("funding_rate_8h_ago") for data in priority_data))
    merged_funding_change = _merge_metric(
        *(data.get("funding_rate_change") for data in priority_data),
        round_float(merged_funding_now - merged_funding_8h_ago if merged_funding_now is not None and merged_funding_8h_ago is not None else None, 6),
    )
    merged_oi_now = _merge_metric(*(data.get("open_interest_now") for data in priority_data))
    merged_oi_change = _merge_metric(*(data.get("open_interest_change_24h_pct") for data in priority_data))
    merged_basis_pct = _merge_metric(*(data.get("basis_pct") for data in priority_data))

    direct_available = any(_has_derivative_signal(provider_data) for _, _, provider_data, _ in direct_provider_results)
    any_provider_available = direct_available or any(
        _has_derivative_signal(data) for data in (coinalyze_data, deribit_perpetual, hyperliquid_perpetual, bybit_provider)
    )
    if not any_provider_available:
        for _, _, _, provider_errors in direct_provider_results:
            errors.extend(provider_errors)
    if coinalyze_errors and not any_provider_available:
        errors.extend(coinalyze_errors)
    if not deribit_perpetual and not any_provider_available:
        errors.extend(deribit_perpetual_errors)
    if not hyperliquid_perpetual and not any_provider_available:
        errors.extend(hyperliquid_errors)

    data = {
        "asset": asset,
        "source_note": (
            "Bybit public V5 market endpoints returned HTTP 403 in this runtime; derivatives metrics fall back to MEXC, Bitget, OKX, Gate, CoinGecko, Coinalyze, Deribit, Hyperliquid, and locally collected liquidation data."
            if bybit_blocked
            else "Derivatives metrics use MEXC first, then Bitget, OKX, Gate, CoinGecko derivatives, Coinalyze, Deribit, Hyperliquid, and local liquidation data as fallbacks. Bybit is optional last-resort only."
        ),
        "bybit_available": bool(bybit_provider) and not bybit_blocked,
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
        "bybit_contract": bybit_provider,
        "derivatives_signal": _signal(merged_oi_change, price_change, merged_funding_now, merged_funding_8h_ago, long_liq, short_liq),
        "bybit_next_funding_time": bybit_provider.get("next_funding_time"),
    }
    for data_key, flag_key, provider_data, _ in direct_provider_results:
        data[data_key] = provider_data
        data[flag_key] = _has_derivative_signal(provider_data)
    source_parts = []
    for data_key, _, provider_data, _ in direct_provider_results:
        if _has_derivative_signal(provider_data):
            source_parts.append(data_key)
    if coinalyze_data:
        source_parts.append("coinalyze")
    if deribit_perpetual or options_data:
        source_parts.append("deribit")
    if hyperliquid_perpetual:
        source_parts.append("hyperliquid")
    if bybit_provider:
        source_parts.append("bybit")
    if local_long_liq or local_short_liq:
        source_parts.append("local_liquidations")
    source = "/".join(source_parts) or "deribit/local_liquidations"
    data["data_quality"] = layer_quality(
        freshness="fresh" if any_provider_available or local_long_liq or local_short_liq else "unknown",
        confidence="medium" if any_provider_available else "low",
        methodology="Free public derivatives APIs plus locally tracked liquidation events; provider units may differ and are normalized best effort.",
        warnings=[
            "Tracked liquidation, not full-market liquidation.",
            "Open interest changes can mix provider units and fallback coverage.",
            *(["Some derivatives providers failed or returned incomplete data."] if errors else []),
        ],
    )
    data["open_interest_change_24h_pct_meta"] = metric_meta(
        methodology="Best-effort 24h open interest change from the first available public provider.",
        confidence=0.65 if merged_oi_change is not None else 0.25,
        source=source,
        warning="Open interest units and venue coverage can differ across providers.",
    )
    data["long_liquidations_24h_meta"] = metric_meta(
        methodology="Coinalyze liquidation history when available, otherwise locally tracked Bybit liquidation collector totals.",
        confidence=0.55 if long_liq is not None else 0.2,
        source="coinalyze_or_local_liquidations",
        warning="Tracked liquidation, not full-market liquidation.",
    )
    data["short_liquidations_24h_meta"] = metric_meta(
        methodology="Coinalyze liquidation history when available, otherwise locally tracked Bybit liquidation collector totals.",
        confidence=0.55 if short_liq is not None else 0.2,
        source="coinalyze_or_local_liquidations",
        warning="Tracked liquidation, not full-market liquidation.",
    )
    return LayerResult(layer="derivatives", source=source, data=data, errors=errors)
