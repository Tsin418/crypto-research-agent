from __future__ import annotations

from typing import Any

import httpx

from backend.http_client import get_json
from backend.models import LayerResult
from backend.utils import safe_float


OKX = "https://www.okx.com"
GATE = "https://api.gateio.ws/api/v4"
MIN_TRADE_SAMPLE = 5


def _symbol_formats(asset: str) -> dict[str, str]:
    return {"okx": f"{asset}-USDT", "gate": f"{asset}_USDT"}


def _side_sign(side: str | None) -> int | None:
    normalized = (side or "").lower()
    if normalized in {"buy", "bid"}:
        return 1
    if normalized in {"sell", "ask"}:
        return -1
    return None


def _trade_value(trade: dict[str, Any], *, price_key: str, amount_key: str, side_key: str | None = None) -> dict[str, Any] | None:
    price = safe_float(trade.get(price_key))
    amount = safe_float(trade.get(amount_key))
    if price is None or amount is None:
        return None
    return {
        "price": price,
        "amount": amount,
        "quote_volume": price * amount,
        "side": trade.get(side_key) if side_key else None,
    }


def _compute_flow(trades: list[dict[str, Any]], *, method_hint: str) -> dict[str, Any]:
    signed_total = 0.0
    buy_volume = 0.0
    sell_volume = 0.0
    previous_price: float | None = None
    previous_sign = 1
    method = method_hint

    for trade in trades:
        quote_volume = trade["quote_volume"]
        sign = _side_sign(trade.get("side"))
        if sign is None:
            method = "tick_rule"
            price = trade["price"]
            if previous_price is None or price == previous_price:
                sign = previous_sign
            elif price > previous_price:
                sign = 1
            else:
                sign = -1
        previous_price = trade["price"]
        previous_sign = sign
        signed_total += quote_volume * sign
        if sign > 0:
            buy_volume += quote_volume
        else:
            sell_volume += quote_volume

    total_volume = buy_volume + sell_volume
    if len(trades) < MIN_TRADE_SAMPLE or total_volume <= 0:
        bias = "unavailable"
        confidence = "low"
    elif signed_total > total_volume * 0.08:
        bias = "buy_pressure"
        confidence = "medium"
    elif signed_total < -total_volume * 0.08:
        bias = "sell_pressure"
        confidence = "medium"
    else:
        bias = "neutral"
        confidence = "medium"

    return {
        "spot_cvd_approx_1h": round(signed_total, 2),
        "spot_cvd_approx_4h": round(signed_total, 2),
        "spot_buy_volume_approx_1h": round(buy_volume, 2),
        "spot_sell_volume_approx_1h": round(sell_volume, 2),
        "spot_flow_bias": bias,
        "spot_flow_confidence": confidence,
        "method": method,
        "trade_sample_size": len(trades),
        "note": "Approximate CVD from public trades; not exchange-wide aggregate CVD.",
    }


async def _okx_trades(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _symbol_formats(asset)["okx"]
    data, error = await get_json(
        client,
        f"{OKX}/api/v5/market/trades",
        params={"instId": symbol},
        source="okx_public_trades",
    )
    if error or not isinstance(data, dict):
        return {}, [error or "okx_public_trades: empty response"]
    rows = data.get("data")
    if not isinstance(rows, list) or not rows:
        return {}, [f"okx_public_trades: {data.get('msg') or 'empty result'}"]
    trades = [
        parsed
        for row in rows
        if isinstance(row, dict)
        for parsed in [_trade_value(row, price_key="px", amount_key="sz", side_key="side")]
        if parsed is not None
    ]
    if not trades:
        return {}, ["okx_public_trades: no usable trades"]
    return {"asset": asset, "provider": "okx", "symbol": symbol, **_compute_flow(trades, method_hint="reported_side")}, []


async def _gate_trades(client: httpx.AsyncClient, asset: str) -> tuple[dict[str, Any], list[str]]:
    symbol = _symbol_formats(asset)["gate"]
    data, error = await get_json(
        client,
        f"{GATE}/spot/trades",
        params={"currency_pair": symbol, "limit": 1000},
        source="gate_public_trades",
    )
    if error or not isinstance(data, list):
        return {}, [error or "gate_public_trades: empty response"]
    trades = [
        parsed
        for row in data
        if isinstance(row, dict)
        for parsed in [_trade_value(row, price_key="price", amount_key="amount", side_key="side")]
        if parsed is not None
    ]
    if not trades:
        return {}, ["gate_public_trades: no usable trades"]
    return {"asset": asset, "provider": "gate", "symbol": symbol, **_compute_flow(trades, method_hint="reported_side")}, []


async def fetch_spot_flow(client: httpx.AsyncClient, asset: str) -> LayerResult:
    errors: list[str] = []
    for fetcher in (_okx_trades, _gate_trades):
        payload, provider_errors = await fetcher(client, asset)
        if payload:
            return LayerResult(layer="spot_flow", source=payload["provider"], data=payload, errors=errors)
        errors.extend(provider_errors)
    return LayerResult(
        layer="spot_flow",
        source="unavailable",
        data={
            "asset": asset,
            "provider": "unavailable",
            "symbol": None,
            "spot_cvd_approx_1h": None,
            "spot_cvd_approx_4h": None,
            "spot_buy_volume_approx_1h": None,
            "spot_sell_volume_approx_1h": None,
            "spot_flow_bias": "unavailable",
            "spot_flow_confidence": "low",
            "method": "unavailable",
            "note": "Approximate CVD unavailable from configured free public trade feeds.",
        },
        errors=errors,
    )
