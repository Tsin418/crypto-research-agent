from __future__ import annotations

import asyncio

from backend.attribution import build_attribution
from backend.config import Settings
from backend.data_derivatives import fetch_derivatives
from backend.data_etf import fetch_etf_flow
from backend.data_history import enrich_with_history, save_layer_metric_snapshots
from backend.data_macro import fetch_macro_context
from backend.data_market import fetch_market
from backend.data_news import fetch_news
from backend.data_onchain import fetch_onchain
from backend.feishu import report_summary, send_feishu_text
from backend.http_client import reset_current_report_id, set_api_call_recorder, set_current_report_id
from backend.intent import parse_intent
from backend.llm import DeepSeekClient
from backend.models import ReportRequest, ResearchContext
from backend.report import generate_report
from backend.risk import compute_risk
from backend.signals import extract_normalized_signals
from backend.storage import Storage


def target_price_change(market_data: dict, time_window: str) -> float | None:
    """Return the price change that matches the selected time window."""
    if time_window == "4h":
        return market_data.get("price_change_4h_pct")
    if time_window == "7d":
        return market_data.get("price_change_7d_pct")
    return market_data.get("price_change_24h_pct")


async def build_research_context(settings: Settings, request: ReportRequest, storage: Storage) -> ResearchContext:
    llm = DeepSeekClient(settings)
    intent = await parse_intent(request, llm)
    time_window = intent.time_window or "24h"
    market_task = fetch_market(settings, intent.asset)
    derivatives_task = fetch_derivatives(settings, intent.asset, storage)
    news_task = fetch_news(settings, intent.asset, time_window, llm)
    onchain_task = fetch_onchain(settings, intent.asset, storage)
    market, derivatives, news, onchain = await asyncio.gather(
        market_task,
        derivatives_task,
        news_task,
        onchain_task,
    )
    etf = await fetch_etf_flow(intent.asset, news=news.data)
    macro = await fetch_macro_context(settings, target_price_change(market.data, time_window))
    market.data = enrich_with_history(storage, intent.asset, "market", market.data)
    derivatives.data = enrich_with_history(storage, intent.asset, "derivatives", derivatives.data)
    onchain.data = enrich_with_history(storage, intent.asset, "onchain", onchain.data)
    etf.data = enrich_with_history(storage, intent.asset, "etf_flow", etf.data)
    risk = compute_risk(market.data, derivatives.data, news.data, onchain.data, etf.data, macro.data, time_window)
    attribution = build_attribution(intent.asset, market.data, derivatives.data, news.data, onchain.data, etf.data, macro.data, time_window)
    return ResearchContext(
        request=request,
        intent=intent,
        market=market,
        derivatives=derivatives,
        news=news,
        onchain=onchain,
        etf=etf,
        macro=macro,
        risk=risk,
        attribution=attribution,
    )


async def run_report_job(settings: Settings, storage: Storage, report_id: str, request: ReportRequest) -> None:
    token = set_current_report_id(report_id)
    set_api_call_recorder(storage.save_api_call_log)
    try:
        llm = DeepSeekClient(settings)
        context = await build_research_context(settings, request, storage)
        for layer in (context.market, context.derivatives, context.news, context.onchain, context.etf, context.macro):
            if layer is None:
                continue
            storage.save_snapshot(
                report_id,
                layer.layer,
                layer.source,
                {"data": layer.data, "errors": layer.errors},
            )
        for layer in (context.market, context.derivatives, context.onchain, context.etf):
            if layer is None:
                continue
            save_layer_metric_snapshots(
                storage,
                context.intent.asset,
                layer.layer,
                layer.data,
                source=layer.source,
                report_id=report_id,
            )
        storage.save_snapshot(report_id, "risk", "internal_rules", context.risk)
        storage.save_snapshot(report_id, "attribution", "internal_rules", context.attribution)
        storage.save_normalized_signals(report_id, extract_normalized_signals(context, context.intent.time_window or "24h"))
        markdown = await generate_report(context, llm)
        storage.complete_report(
            report_id,
            asset=context.intent.asset,
            mode=context.intent.mode,
            time_window=context.intent.time_window,
            report_markdown=markdown,
            risk_score=context.risk["risk_score"],
            risk_level=context.risk["risk_level"],
            price_now=context.market.data.get("price_now"),
            price_change_4h_pct=context.market.data.get("price_change_4h_pct"),
            price_change_24h_pct=context.market.data.get("price_change_24h_pct"),
            direction=context.market.data.get("direction"),
            direction_label_zh=context.market.data.get("direction_label_zh"),
            trigger_reason=context.market.data.get("trigger_reason"),
            top_news=context.news.data.get("top_news"),
        )
        await send_feishu_text(
            settings,
            report_summary(
                report_id,
                context.intent.asset,
                context.risk["risk_level"],
                context.risk["risk_score"],
                markdown,
            ),
        )
    except Exception as exc:
        storage.fail_report(report_id, f"{type(exc).__name__}: {str(exc)}")
    finally:
        reset_current_report_id(token)
