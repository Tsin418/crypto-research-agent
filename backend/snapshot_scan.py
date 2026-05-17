from __future__ import annotations

import asyncio
from typing import Any

from backend.config import Settings
from backend.data_derivatives import fetch_derivatives
from backend.data_etf import fetch_etf_flow
from backend.data_history import enrich_with_history, save_layer_metric_snapshots
from backend.data_market import fetch_4h_market_snapshot, fetch_market
from backend.data_news import fetch_news
from backend.data_onchain import fetch_onchain
from backend.http_client import reset_current_report_id, set_api_call_recorder, set_current_report_id
from backend.models import LayerResult
from backend.storage import Storage
from backend.utils import iso_now


SNAPSHOT_SCAN_TYPE = "scheduled_snapshot"
SUPPORTED_ASSETS = {"BTC", "ETH"}


def _asset_list(assets: list[str] | tuple[str, ...]) -> list[str]:
    normalized = [asset.strip().upper() for asset in assets if asset and asset.strip()]
    return [asset for asset in normalized if asset in SUPPORTED_ASSETS]


def _snapshot_payload(layer: LayerResult) -> dict[str, Any]:
    return {"data": layer.data, "errors": layer.errors}


async def _fetch_asset_layers(settings: Settings, storage: Storage, asset: str) -> list[LayerResult]:
    market_4h_task = fetch_4h_market_snapshot(settings, asset)
    market_task = fetch_market(settings, asset)
    derivatives_task = fetch_derivatives(settings, asset, storage)
    news_task = fetch_news(settings, asset, "24h", llm=None)
    onchain_task = fetch_onchain(settings, asset, storage)

    market_4h, market, derivatives, news, onchain = await asyncio.gather(
        market_4h_task,
        market_task,
        derivatives_task,
        news_task,
        onchain_task,
    )
    etf = await fetch_etf_flow(asset, news=news.data)

    market.data = enrich_with_history(storage, asset, "market", market.data)
    derivatives.data = enrich_with_history(storage, asset, "derivatives", derivatives.data)
    onchain.data = enrich_with_history(storage, asset, "onchain", onchain.data)
    etf.data = enrich_with_history(storage, asset, "etf_flow", etf.data)
    return [market_4h, market, derivatives, news, onchain, etf]


async def _scan_one_asset(settings: Settings, storage: Storage, asset: str) -> dict[str, Any]:
    layers = await _fetch_asset_layers(settings, storage, asset)
    saved_layers: list[str] = []
    metric_layers: list[str] = []
    errors: dict[str, list[str]] = {}

    for layer in layers:
        storage.save_scheduled_snapshot(
            asset=asset,
            layer=layer.layer,
            source=layer.source,
            raw_json=_snapshot_payload(layer),
            scan_type=SNAPSHOT_SCAN_TYPE,
        )
        saved_layers.append(layer.layer)
        if layer.errors:
            errors[layer.layer] = layer.errors

    for layer in layers:
        if layer.layer not in {"market", "derivatives", "onchain", "etf_flow"}:
            continue
        save_layer_metric_snapshots(
            storage,
            asset,
            layer.layer,
            layer.data,
            source=layer.source,
            report_id=None,
        )
        metric_layers.append(layer.layer)

    return {
        "asset": asset,
        "status": "completed",
        "saved_layers": saved_layers,
        "metric_layers": metric_layers,
        "errors": errors,
    }


async def run_snapshot_scan(settings: Settings, storage: Storage, assets: list[str] | tuple[str, ...]) -> dict[str, Any]:
    selected_assets = _asset_list(assets)
    if not selected_assets:
        return {
            "scan_type": SNAPSHOT_SCAN_TYPE,
            "generated_at": iso_now(),
            "status": "skipped",
            "reason": "no supported assets requested",
            "assets": [],
            "results": [],
        }

    token = set_current_report_id(None)
    set_api_call_recorder(storage.save_api_call_log)
    results: list[dict[str, Any]] = []
    try:
        for asset in selected_assets:
            try:
                results.append(await _scan_one_asset(settings, storage, asset))
            except Exception as exc:
                results.append(
                    {
                        "asset": asset,
                        "status": "failed",
                        "saved_layers": [],
                        "metric_layers": [],
                        "errors": {"snapshot_scan": [f"{type(exc).__name__}: {exc}"]},
                    }
                )
    finally:
        reset_current_report_id(token)

    status = "completed" if all(item["status"] == "completed" for item in results) else "partial_failure"
    return {
        "scan_type": SNAPSHOT_SCAN_TYPE,
        "generated_at": iso_now(),
        "status": status,
        "assets": selected_assets,
        "results": results,
    }
