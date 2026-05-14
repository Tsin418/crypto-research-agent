from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx

from backend.config import Settings
from backend.http_client import get_json, is_http_forbidden_error
from backend.models import LayerResult
from backend.utils import ASSET_META, ema, percent_change, round_float, safe_float


COINGECKO_DEMO = "https://api.coingecko.com/api/v3"
COINGECKO_PRO = "https://pro-api.coingecko.com/api/v3"
BYBIT = "https://api.bybit.com"
COINPAPRIKA = "https://api.coinpaprika.com/v1"
BITGET = "https://api.bitget.com"
GATE = "https://api.gateio.ws/api/v4"
OKX = "https://www.okx.com"
BINANCE = "https://api.binance.com"


SPOT_PROVIDER_FIELDS = (
    ("bitget_spot", "bitget_spot_available"),
    ("gate_spot", "gate_spot_available"),
    ("okx_spot", "okx_spot_available"),
    ("binance_spot", "binance_spot_available"),
)


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


def classify_4h_direction(
    asset: str,
    price_change_4h_pct: float | None,
    up_threshold: float,
    down_threshold: float,
) -> dict:
    if price_change_4h_pct is None:
        return {
            "direction": "neutral",
            "direction_label_zh": "震荡",
            "trigger_reason": f"{asset} 过去 4 小时价格变化数据不足，暂按震荡处理",
        }
    if price_change_4h_pct >= up_threshold:
        direction = "rising"
        label = "上涨"
        reason = f"{asset} 过去 4 小时上涨 {price_change_4h_pct:.2f}%，超过 +{up_threshold:.1f}% 阈值"
    elif price_change_4h_pct <= down_threshold:
        direction = "falling"
        label = "下跌"
        reason = f"{asset} 过去 4 小时下跌 {abs(price_change_4h_pct):.2f}%，超过 {down_threshold:.1f}% 阈值"
    else:
        direction = "neutral"
        label = "震荡"
        reason = f"{asset} 过去 4 小时变化 {price_change_4h_pct:.2f}%，未超过方向阈值"
    return {"direction": direction, "direction_label_zh": label, "trigger_reason": reason}


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


async def _bybit_4h_snapshot(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = ASSET_META[asset]["symbol"]
    data, error = await get_json(
        client,
        f"{BYBIT}/v5/market/kline",
        params={"category": "spot", "symbol": symbol, "interval": "240", "limit": 2},
        source="bybit_4h_kline",
    )
    if error or not isinstance(data, dict) or data.get("retCode") != 0:
        return {}, [error or f"bybit_4h_kline: {data.get('retMsg') if isinstance(data, dict) else 'bad response'}"]
    rows = data.get("result", {}).get("list", [])
    if len(rows) < 2:
        return {}, ["bybit_4h_kline: fewer than 2 rows"]
    rows = sorted(rows, key=lambda item: int(item[0]))
    price_4h_ago = safe_float(rows[-2][4])
    current_price = safe_float(rows[-1][4])
    return {
        "price_now": current_price,
        "price_4h_ago": price_4h_ago,
        "price_change_4h_pct": percent_change(current_price, price_4h_ago),
        "four_hour_source": "bybit_public_spot_kline",
    }, []


async def _coingecko_4h_snapshot(client: httpx.AsyncClient, settings: Settings, asset: str) -> tuple[dict, list[str]]:
    meta = ASSET_META[asset]
    base_url = COINGECKO_PRO if settings.coingecko_plan.lower() == "pro" else COINGECKO_DEMO
    header_name = "x-cg-pro-api-key" if settings.coingecko_plan.lower() == "pro" else "x-cg-demo-api-key"
    headers = {header_name: settings.coingecko_api_key} if settings.coingecko_api_key else {}
    data, error = await get_json(
        client,
        f"{base_url}/coins/{meta['coingecko_id']}/market_chart",
        params={"vs_currency": "usd", "days": 1},
        headers=headers,
        source="coingecko_4h_market_chart",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "coingecko_4h_market_chart: empty response"]
    rows = [
        (safe_float(row[0]), safe_float(row[1]))
        for row in data.get("prices", [])
        if isinstance(row, list) and len(row) >= 2
    ]
    rows = [(ts, price) for ts, price in rows if ts is not None and price is not None]
    if len(rows) < 2:
        return {}, ["coingecko_4h_market_chart: fewer than 2 usable rows"]
    rows.sort(key=lambda item: item[0])
    current_ts, current_price = rows[-1]
    target_ts = current_ts - 4 * 60 * 60 * 1000
    past_ts, price_4h_ago = min(rows, key=lambda item: abs(item[0] - target_ts))
    sampled_at = datetime.fromtimestamp(current_ts / 1000, UTC).isoformat().replace("+00:00", "Z")
    past_at = datetime.fromtimestamp(past_ts / 1000, UTC).isoformat().replace("+00:00", "Z")
    return {
        "price_now": current_price,
        "price_4h_ago": price_4h_ago,
        "price_change_4h_pct": percent_change(current_price, price_4h_ago),
        "four_hour_source": "coingecko_market_chart_approx",
        "four_hour_sampled_at": sampled_at,
        "four_hour_past_sampled_at": past_at,
    }, []


async def fetch_4h_market_snapshot(settings: Settings, asset: str) -> LayerResult:
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        snapshot, cg_errors = await _coingecko_4h_snapshot(client, settings, asset)
        errors.extend(cg_errors)
        source = "coingecko"
        if not snapshot:
            snapshot, bybit_errors = await _bybit_4h_snapshot(client, asset)
            if bybit_errors and not all(is_http_forbidden_error(error) for error in bybit_errors):
                errors.extend(bybit_errors)
            source = "bybit" if snapshot else "unavailable"
        direction = classify_4h_direction(
            asset,
            snapshot.get("price_change_4h_pct"),
            settings.price_4h_up_threshold_pct,
            settings.price_4h_down_threshold_pct,
        )
    data = {
        "asset": asset,
        **snapshot,
        **direction,
        "up_threshold_pct": settings.price_4h_up_threshold_pct,
        "down_threshold_pct": settings.price_4h_down_threshold_pct,
    }
    return LayerResult(layer="market_4h", source=source, data=data, errors=errors)


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


def _spot_formats(asset: str) -> dict[str, str]:
    return {
        "compact": ASSET_META[asset]["symbol"],
        "gate": f"{asset}_USDT",
        "okx": f"{asset}-USDT",
    }


def _provider_payload(
    *,
    provider: str,
    symbol: str,
    turnover: float | None = None,
    base_volume: float | None = None,
    last_price: float | None = None,
    error: str | None = None,
    unit_note: str | None = None,
) -> dict:
    payload = {
        "provider": provider,
        "symbol": symbol,
        "spot_turnover_24h": turnover,
        "spot_volume_24h_base": base_volume,
        "last_price": last_price,
    }
    if error:
        payload["error"] = error
    if unit_note:
        payload["unit_note"] = unit_note
    return payload


async def _bitget_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = _spot_formats(asset)["compact"]
    data, error = await get_json(
        client,
        f"{BITGET}/api/v2/spot/market/tickers",
        params={"symbol": symbol},
        source="bitget_spot_ticker",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "bitget_spot_ticker: empty response"]
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return {}, [f"bitget_spot_ticker: {data.get('msg') or 'empty result'}"]
    row = rows[0]
    turnover = safe_float(row.get("quoteVolume")) or safe_float(row.get("usdtVolume"))
    return _provider_payload(
        provider="bitget",
        symbol=symbol,
        turnover=turnover,
        base_volume=safe_float(row.get("baseVolume")),
        last_price=safe_float(row.get("lastPr")) or safe_float(row.get("close")),
    ), []


async def _gate_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = _spot_formats(asset)["gate"]
    data, error = await get_json(
        client,
        f"{GATE}/spot/tickers",
        params={"currency_pair": symbol},
        source="gate_spot_ticker",
    )
    if error or not isinstance(data, list) or not data:
        return {}, [error or "gate_spot_ticker: empty response"]
    row = data[0]
    return _provider_payload(
        provider="gate",
        symbol=symbol,
        turnover=safe_float(row.get("quote_volume")),
        base_volume=safe_float(row.get("base_volume")),
        last_price=safe_float(row.get("last")),
    ), []


async def _okx_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = _spot_formats(asset)["okx"]
    data, error = await get_json(
        client,
        f"{OKX}/api/v5/market/ticker",
        params={"instId": symbol},
        source="okx_spot_ticker",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "okx_spot_ticker: empty response"]
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return {}, [f"okx_spot_ticker: {data.get('msg') or 'empty result'}"]
    row = rows[0]
    return _provider_payload(
        provider="okx",
        symbol=symbol,
        turnover=safe_float(row.get("volCcy24h")),
        base_volume=safe_float(row.get("vol24h")),
        last_price=safe_float(row.get("last")),
    ), []


async def _binance_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    symbol = _spot_formats(asset)["compact"]
    data, error = await get_json(
        client,
        f"{BINANCE}/api/v3/ticker/24hr",
        params={"symbol": symbol},
        source="binance_spot_ticker",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "binance_spot_ticker: empty response"]
    return _provider_payload(
        provider="binance",
        symbol=symbol,
        turnover=safe_float(data.get("quoteVolume")),
        base_volume=safe_float(data.get("volume")),
        last_price=safe_float(data.get("lastPrice")),
    ), []


async def _replacement_spot_ticker(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    provider_calls = (
        ("bitget_spot", "bitget_spot_available", _bitget_spot_ticker),
        ("gate_spot", "gate_spot_available", _gate_spot_ticker),
        ("okx_spot", "okx_spot_available", _okx_spot_ticker),
        ("binance_spot", "binance_spot_available", _binance_spot_ticker),
    )
    diagnostics: dict = {data_key: {} for data_key, _ in SPOT_PROVIDER_FIELDS}
    diagnostics.update({flag_key: False for _, flag_key in SPOT_PROVIDER_FIELDS})
    errors: list[str] = []
    selected: dict | None = None
    selected_key: str | None = None

    for data_key, flag_key, fetcher in provider_calls:
        payload, provider_errors = await fetcher(client, asset)
        if payload:
            diagnostics[data_key] = payload
            diagnostics[flag_key] = payload.get("spot_turnover_24h") is not None
            if selected is None and payload.get("spot_turnover_24h") is not None:
                selected = payload
                selected_key = data_key
                break
        else:
            error = provider_errors[0] if provider_errors else f"{data_key}: unavailable"
            diagnostics[data_key] = {"provider": data_key.removesuffix("_spot"), "error": error}
            errors.extend(provider_errors)

    if selected is None:
        return diagnostics, errors

    diagnostics.update(
        {
            "spot_turnover_24h": selected.get("spot_turnover_24h"),
            "spot_volume_24h_base": selected.get("spot_volume_24h_base"),
            "spot_turnover_source": selected_key,
        }
    )
    return diagnostics, []


async def fetch_market(settings: Settings, asset: str) -> LayerResult:
    notes: list[str] = []
    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        primary, errors = await _coingecko(client, settings, asset)
        source = "coingecko"
        if not primary:
            primary, fallback_errors = await _coinpaprika(client, asset)
            errors.extend(fallback_errors)
            source = "coinpaprika" if primary else "unavailable"
        technicals, chart_errors = await _coingecko_market_chart(client, settings, asset)
        if not technicals:
            technicals, bybit_errors = await _bybit_klines(client, asset)
            if bybit_errors and not all(is_http_forbidden_error(error) for error in bybit_errors):
                errors.extend(bybit_errors)
            errors.extend(chart_errors)
        spot_ticker, spot_errors = await _replacement_spot_ticker(client, asset)
        if spot_errors and not spot_ticker.get("spot_turnover_24h"):
            errors.extend(spot_errors)

    merged = {"asset": asset, **primary, **technicals, **spot_ticker}
    turnover_24h = merged.get("spot_turnover_24h") or merged.get("volume_24h")
    merged["volume_ratio_vs_7d"] = round_float(
        (turnover_24h / merged["volume_7d_avg"])
        if turnover_24h is not None and merged.get("volume_7d_avg")
        else None
    )
    merged["volume_ratio_source"] = (
        f"{merged.get('spot_turnover_source')}_turnover_vs_7d_avg_volume"
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
        merged["note"] = "EMA/7d volume use CoinGecko market chart when available, with Bybit only as an optional last-resort fallback."
    return LayerResult(layer="market", source=source, data=merged, errors=errors)
