from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from backend.storage import Storage


BYBIT_LINEAR_WS = "wss://stream.bybit.com/v5/public/linear"
SYMBOL_TO_ASSET = {"BTCUSDT": "BTC", "ETHUSDT": "ETH"}


def normalize_bybit_liquidation(item: dict[str, Any]) -> dict[str, Any] | None:
    symbol = item.get("s") or item.get("symbol")
    if symbol not in SYMBOL_TO_ASSET:
        return None
    price = _float(item.get("p") or item.get("price"))
    quantity = _float(item.get("v") or item.get("qty") or item.get("quantity"))
    if price is None or quantity is None:
        return None
    raw_side = str(item.get("S") or item.get("side") or "").lower()
    # Bybit liquidation stream reports the liquidation order side. A Sell order closes a long;
    # a Buy order closes a short.
    side = "long" if raw_side == "sell" else "short" if raw_side == "buy" else "unknown"
    timestamp_ms = int(item.get("T") or item.get("time") or time.time() * 1000)
    return {
        "asset": SYMBOL_TO_ASSET[symbol],
        "symbol": symbol,
        "side": side,
        "price": price,
        "quantity": quantity,
        "notional": round(price * quantity, 2),
        "timestamp_ms": timestamp_ms,
        "source": "bybit_all_liquidation_ws",
        "raw": item,
    }


def _float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def run_bybit_liquidation_collector(storage: Storage) -> None:
    try:
        import websockets
    except ImportError:
        return

    while True:
        try:
            async with websockets.connect(BYBIT_LINEAR_WS, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({"op": "subscribe", "args": ["allLiquidation.BTCUSDT", "allLiquidation.ETHUSDT"]}))
                async for message in ws:
                    payload = json.loads(message)
                    data = payload.get("data") or []
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        event = normalize_bybit_liquidation(item)
                        if not event:
                            continue
                        event_id = f"bybit_liq:{event['symbol']}:{event['timestamp_ms']}:{event['side']}:{event['price']}:{event['quantity']}"
                        storage.save_liquidation_event(event_id, event["asset"], event["symbol"], event)
        except Exception:
            await asyncio.sleep(5)
