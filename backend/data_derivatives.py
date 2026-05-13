from __future__ import annotations

import time

import httpx

from backend.config import Settings
from backend.http_client import get_json, is_http_forbidden_error
from backend.data_options import fetch_deribit_put_call
from backend.models import LayerResult
from backend.utils import ASSET_META, iso_from_ms, percent_change, round_float, safe_float


BYBIT = "https://api.bybit.com"


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
    long_liq = round_float(liquidation_stats["long"]["notional"], 2)
    short_liq = round_float(liquidation_stats["short"]["notional"], 2)
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
        "source_note": (
            "Bybit public V5 market endpoints returned HTTP 403 in this runtime; derivatives metrics fall back to Deribit options and locally collected liquidation data."
            if bybit_blocked
            else "Bybit public V5 market endpoints; Binance is optional and currently not required."
        ),
        "bybit_available": not bybit_blocked,
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
        "derivatives_signal": _signal(oi_change, price_change, funding_now, funding_8h_ago, long_liq, short_liq),
        "bybit_next_funding_time": iso_from_ms(ticker.get("nextFundingTime")),
    }
    source = "deribit/local_liquidations" if bybit_blocked else "bybit/deribit"
    return LayerResult(layer="derivatives", source=source, data=data, errors=errors)
