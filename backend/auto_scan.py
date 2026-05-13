from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.attribution import build_attribution
from backend.config import Settings
from backend.data_derivatives import fetch_derivatives
from backend.data_market import fetch_4h_market_snapshot, fetch_market
from backend.data_news import fetch_news
from backend.data_onchain import fetch_onchain
from backend.http_client import reset_current_report_id, set_api_call_recorder, set_current_report_id
from backend.llm import DeepSeekClient
from backend.models import AutoScanRequest, Intent, LayerResult, ReportRequest, ResearchContext, StoredReport
from backend.report import generate_chinese_auto_report
from backend.risk import compute_risk
from backend.signals import extract_normalized_signals
from backend.storage import Storage
from backend.utils import iso_now


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _is_cache_fresh(report: StoredReport | None, ttl_minutes: int) -> bool:
    updated_at = _parse_iso(report.updated_at if report else None)
    if updated_at is None:
        return False
    return datetime.now(UTC) - updated_at <= timedelta(minutes=ttl_minutes)


def _report_payload(report: StoredReport) -> dict[str, Any]:
    top_news = report.top_news_json or {
        "title": report.top_news_title or "",
        "url": report.top_news_url or "",
        "source": report.top_news_source or "",
        "reason_zh": "",
    }
    return {
        "report_id": report.report_id,
        "asset": report.asset,
        "price_now": report.price_now,
        "price_change_4h_pct": report.price_change_4h_pct,
        "price_change_24h_pct": report.price_change_24h_pct,
        "direction": report.direction,
        "direction_label_zh": report.direction_label_zh,
        "trigger_reason": report.trigger_reason,
        "top_news": top_news,
        "report_markdown": report.report_markdown or "",
        "created_at": report.created_at,
        "updated_at": report.updated_at,
    }


async def _build_auto_context(settings: Settings, storage: Storage, asset: str, time_window: str) -> ResearchContext:
    llm = DeepSeekClient(settings)
    market_4h_task = fetch_4h_market_snapshot(settings, asset)
    market_task = fetch_market(settings, asset)
    derivatives_task = fetch_derivatives(settings, asset, storage)
    news_task = fetch_news(settings, asset, "24h", llm)
    onchain_task = fetch_onchain(settings, asset, storage)
    market_4h, market, derivatives, news, onchain = await asyncio.gather(
        market_4h_task,
        market_task,
        derivatives_task,
        news_task,
        onchain_task,
    )
    merged_market = {
        **market.data,
        **{key: value for key, value in market_4h.data.items() if value is not None},
    }
    notes = [note for note in (market.data.get("note"), market_4h.data.get("note")) if note]
    if notes:
        merged_market["note"] = " ".join(notes)
    market_layer = LayerResult(
        layer="market",
        source=f"{market_4h.source}/{market.source}",
        data=merged_market,
        errors=[*market_4h.errors, *market.errors],
    )
    risk = compute_risk(market_layer.data, derivatives.data, news.data, onchain.data)
    attribution = build_attribution(asset, market_layer.data, derivatives.data, news.data, onchain.data)
    request = ReportRequest(query=f"{asset} 过去4小时中文市场研究", asset=asset, time_window=time_window)
    return ResearchContext(
        request=request,
        intent=Intent(asset=asset, mode="state_scan", time_window=time_window, user_intent=request.query),
        market=market_layer,
        derivatives=derivatives,
        news=news,
        onchain=onchain,
        risk=risk,
        attribution=attribution,
    )


async def _generate_asset_report(settings: Settings, storage: Storage, asset: str, time_window: str) -> StoredReport:
    report_id = str(uuid.uuid4())
    storage.create_report(report_id, f"{asset} 过去4小时中文市场研究")
    token = set_current_report_id(report_id)
    set_api_call_recorder(storage.save_api_call_log)
    try:
        llm = DeepSeekClient(settings)
        context = await _build_auto_context(settings, storage, asset, time_window)
        for layer in (context.market, context.derivatives, context.news, context.onchain):
            storage.save_snapshot(
                report_id,
                layer.layer,
                layer.source,
                {"data": layer.data, "errors": layer.errors},
            )
        storage.save_snapshot(report_id, "risk", "internal_rules", context.risk)
        storage.save_snapshot(report_id, "attribution", "internal_rules", context.attribution)
        storage.save_normalized_signals(report_id, extract_normalized_signals(context))
        markdown = await generate_chinese_auto_report(context, llm)
        market = context.market.data
        top_news = context.news.data.get("top_news") or {}
        storage.complete_report(
            report_id,
            asset=context.intent.asset,
            mode=context.intent.mode,
            time_window=context.intent.time_window,
            report_markdown=markdown,
            risk_score=context.risk["risk_score"],
            risk_level=context.risk["risk_level"],
            price_now=market.get("price_now"),
            price_change_4h_pct=market.get("price_change_4h_pct"),
            price_change_24h_pct=market.get("price_change_24h_pct"),
            direction=market.get("direction"),
            direction_label_zh=market.get("direction_label_zh"),
            trigger_reason=market.get("trigger_reason"),
            top_news=top_news,
        )
    except Exception as exc:
        storage.fail_report(report_id, f"{type(exc).__name__}: {str(exc)}")
        raise
    finally:
        reset_current_report_id(token)
    report = storage.get_report(report_id)
    if report is None:
        raise RuntimeError("generated report was not persisted")
    return report


async def run_auto_scan(settings: Settings, storage: Storage, request: AutoScanRequest) -> dict[str, Any]:
    assets = [asset for asset in request.assets if asset in {"BTC", "ETH"}] or ["BTC", "ETH"]
    reports: list[StoredReport] = []
    cache_flags: list[bool] = []
    for asset in assets:
        cached = storage.get_latest_report(asset, request.time_window)
        if not request.force_refresh and _is_cache_fresh(cached, settings.report_cache_ttl_minutes):
            reports.append(cached)  # type: ignore[arg-type]
            cache_flags.append(True)
            continue
        generated = await _generate_asset_report(settings, storage, asset, request.time_window)
        reports.append(generated)
        cache_flags.append(False)
    return {
        "generated_at": iso_now(),
        "cache_hit": all(cache_flags) if cache_flags else False,
        "reports": [_report_payload(report) for report in reports],
    }


def stored_report_payload(report: StoredReport) -> dict[str, Any]:
    return _report_payload(report)
