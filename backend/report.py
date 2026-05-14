from __future__ import annotations

import json
import re

from backend.llm import DeepSeekClient
from backend.models import DISCLAIMER, ResearchContext


CHINESE_DISCLAIMER = "本报告仅用于研究和信息参考，不构成任何投资建议。"


def _sanitize_error_message(raw: str) -> str:
    """Convert raw HTTP/network errors into user-friendly summaries."""
    raw_lower = raw.lower()
    if "403" in raw_lower or "forbidden" in raw_lower:
        return "blocked in current deployment environment"
    if "401" in raw_lower or "unauthorized" in raw_lower:
        return "authentication required"
    if "404" in raw_lower or "not found" in raw_lower:
        return "endpoint unavailable"
    if "timeout" in raw_lower or "timed out" in raw_lower:
        return "request timed out"
    if "cors" in raw_lower:
        return "CORS error"
    if "dns" in raw_lower or "name resolution" in raw_lower or "getaddrinfo" in raw_lower:
        return "DNS resolution failed"
    if "connection" in raw_lower or "refused" in raw_lower or "reset" in raw_lower:
        return "connection failed"
    if "rate limit" in raw_lower or "429" in raw_lower:
        return "rate limited"
    # Strip URLs and long exception names
    if len(raw) > 80:
        return "data source error"
    return raw


def _summarize_layer_errors(layer_name: str, errors: list[str]) -> str:
    """Produce a user-friendly data-limits line for a layer's errors."""
    provider = layer_name.replace("_", " ").title()
    cleaned = [_sanitize_error_message(e) for e in errors[:3]]
    unique = list(dict.fromkeys(cleaned))
    if len(unique) == 1:
        return f"- {provider}: {unique[0]}."
    return f"- {provider}: {'; '.join(unique)}."

FORBIDDEN_PATTERNS = (
    r"\bbuy\b.*\bnow\b",
    r"\bsell\b.*\bimmediately\b",
    r"\bguaranteed\b",
    r"\buse\s+\d+x\b",
    r"\byou should enter\b",
)


def sanitize_report(markdown: str) -> str:
    sanitized = markdown
    for pattern in FORBIDDEN_PATTERNS:
        sanitized = re.sub(pattern, "[removed: trading instruction]", sanitized, flags=re.IGNORECASE)
    if DISCLAIMER not in sanitized:
        sanitized = sanitized.rstrip() + f"\n\n## Disclaimer\n{DISCLAIMER}\n"
    return sanitized


def sanitize_chinese_report(markdown: str) -> str:
    sanitized = markdown
    for pattern in FORBIDDEN_PATTERNS + (r"买入", r"卖出", r"持有", r"加杠杆"):
        sanitized = re.sub(pattern, "[已移除：交易建议]", sanitized, flags=re.IGNORECASE)
    if CHINESE_DISCLAIMER not in sanitized:
        sanitized = sanitized.rstrip() + f"\n\n## 风险提示\n{CHINESE_DISCLAIMER}\n"
    return sanitized


def _market_lines(context: ResearchContext) -> list[str]:
    market = context.market.data
    derivatives = context.derivatives.data
    onchain = context.onchain.data
    tw = (context.intent.time_window or "24h") if context.intent else "24h"
    target_change = (
        market.get("price_change_4h_pct") if tw == "4h"
        else market.get("price_change_7d_pct") if tw == "7d"
        else market.get("price_change_24h_pct")
    )
    lines = [
        f"- Price: ${market.get('price_now'):,.2f}" if market.get("price_now") else "- Price: unavailable",
        f"- 1h / 4h / 24h / 7d Change: {market.get('price_change_1h_pct')}% / {market.get('price_change_4h_pct')}% / {market.get('price_change_24h_pct')}% / {market.get('price_change_7d_pct')}%",
        f"- Target window ({tw}) change: {target_change}%",
        f"- 24h Volume: {market.get('volume_24h')}",
        f"- 24h Volume: {market.get('volume_24h')}",
        f"- Volume vs 7d: {market.get('volume_ratio_vs_7d')}",
        f"- EMA20 / EMA50 / EMA200: {market.get('ema_20')} / {market.get('ema_50')} / {market.get('ema_200')}",
        f"- Funding Rate: {derivatives.get('funding_rate_now')}",
        f"- Open Interest 24h Change: {derivatives.get('open_interest_change_24h_pct')}%",
        f"- 24h Tracked Liquidations Long / Short: {derivatives.get('long_liquidations_24h')} / {derivatives.get('short_liquidations_24h')}",
        f"- Put/Call Ratio: {derivatives.get('put_call_ratio')}",
        f"- Stablecoin 24h Supply Change: {onchain.get('stablecoin_supply_change_24h')}",
        f"- On-chain Signal: {onchain.get('onchain_signal')}",
    ]
    # Spot CVD（近似值）
    spot_bias = market.get("spot_flow_bias")
    if spot_bias and spot_bias != "unavailable":
        cvd_4h = market.get("spot_cvd_approx_4h")
        lines.append(f"- Spot CVD Approx (4h): {cvd_4h} (bias={spot_bias}, method={market.get('method', 'tick_rule')})")

    # EMA 位置关系
    for period in (20, 50, 200):
        vs_ema = market.get(f"price_vs_ema{period}")
        ema_val = market.get(f"ema_{period}")
        if vs_ema and vs_ema != "unknown" and ema_val is not None:
            lines.append(f"- Price vs EMA{period}: {vs_ema} (EMA{period}=${ema_val:,.2f})")

    if context.macro:
        macro = context.macro.data
        lines.append(f"- Macro Signal: {macro.get('macro_signal')} ({macro.get('macro_confidence')})")

    # ETF 流量行
    if context.etf:
        etf = context.etf.data
        etf_latest = etf.get("btc_etf_net_flow_usd_m") or etf.get("net_flow_usd_m_latest")
        if etf_latest is not None:
            lines.append(f"- BTC ETF Net Flow (latest): {etf_latest}M USD ({etf.get('flow_direction', 'unknown')}, intensity={etf.get('flow_intensity', 'unknown')})")
        elif etf.get("is_stale"):
            lines.append("- BTC ETF Flow: stale cache, not reliable for this report.")

    return lines


def _risk_lines(risk: dict) -> list[str]:
    max_score = risk.get("risk_max_score", 15)
    breakdown = risk.get("risk_breakdown", {})
    lines = [f"Risk Score: {risk['risk_score']}/{max_score} - {risk['risk_level']}"]
    for key, label in (
        ("liquidity_risk", "Liquidity Risk"),
        ("leverage_risk", "Leverage Risk"),
        ("news_risk", "News Risk"),
        ("onchain_risk", "On-chain Risk"),
        ("macro_risk", "Macro Risk"),
    ):
        if key in breakdown:
            lines.append(f"- {label}: {breakdown[key]}/3")
    lines.append(f"- Summary: {risk.get('risk_summary')}")
    return lines


def _evidence_quality_lines(context: ResearchContext) -> list[str]:
    lines = [
        "- Strong: labeled exchange inflow (not internal transfer), direct market data, or official source.",
        "- Medium: public API with partial context, or single labeled exchange inflow.",
        "- Weak: unlabeled large transfer, exchange internal transfer, or price commentary.",
    ]
    onchain = context.onchain.data
    if onchain.get("onchain_evidence_quality"):
        lines.append(f"- On-chain evidence quality: {onchain.get('onchain_evidence_quality')}.")
        if onchain.get("exchange_internal_count"):
            lines.append(f"- {onchain.get('exchange_internal_count')} exchange internal transfers excluded from inflow count.")
    etf = context.etf.data if context.etf else {}
    if etf and (etf.get("flow_direction") == "unavailable" or etf.get("is_stale")):
        lines.append("- Data limitation: ETF flow data is unavailable or stale; this report does not treat ETF flows as confirmed evidence.")
    lines.extend(
        [
            "- Methodology label: tracked liquidation, not full-market liquidation.",
            "- Methodology label: spot CVD approximation, not exact CVD.",
            "- Methodology label: stablecoin supply proxy, not direct buying pressure.",
            "- On-chain wording rule: never describe unknown transfers as 'whale selling' without confirmed exchange destination.",
        ]
    )
    return lines


def _driver_lines(item: dict, index: int) -> list[str]:
    lines = [
        f"### {index}. {item['driver']}",
        f"- Confidence: {item.get('confidence')}",
        f"- Causality level: {item.get('causality_level')}",
        f"- Interpretation: {item.get('explanation')}",
    ]
    for label, key in (
        ("Supporting evidence", "supporting_evidence"),
        ("Counter-evidence", "counter_evidence"),
        ("Missing evidence", "missing_evidence"),
    ):
        values = item.get(key) or []
        if values:
            lines.append(f"- {label}:")
            lines.extend([f"  - {value}" for value in values[:4]])
    return lines


def _data_quality_lines(attr: dict) -> list[str]:
    data_quality = attr.get("data_quality") or {}
    lines = [f"- Overall score: {attr.get('overall_data_quality_score')}"]
    for name, section in data_quality.items():
        status = str(section.get("status", "unknown")).replace("_", " ").title()
        missing = section.get("missing_fields") or []
        detail = f" - {', '.join(missing[:2])}" if missing else ""
        if section.get("stale"):
            detail = f"{detail}; stale cache"
        if section.get("approximate"):
            detail = f"{detail}; approximate"
        lines.append(f"- {name.replace('_', ' ').title()}: {status}{detail}")
    return lines


def _layer_data_quality_lines(context: ResearchContext) -> list[str]:
    lines: list[str] = []
    layers = [context.market, context.derivatives, context.news, context.onchain]
    if context.etf is not None:
        layers.append(context.etf)
    for layer in layers:
        quality = layer.data.get("data_quality") or {}
        if not quality:
            continue
        label = layer.layer.replace("_", " ").title()
        freshness = quality.get("freshness", "unknown")
        confidence = quality.get("confidence", "unknown")
        warnings = quality.get("warnings") or []
        warning_text = f" Warning: {warnings[0]}" if warnings else ""
        lines.append(f"- {label}: freshness={freshness}, confidence={confidence}.{warning_text}")
    return lines


def _trace_summary_lines(attr: dict) -> list[str]:
    summary = attr.get("trace_summary") or {}
    return [
        f"- {summary.get('candidates_evaluated', 0)} candidates evaluated.",
        f"- {summary.get('promoted_to_primary', 0)} promoted to primary.",
        f"- {summary.get('post_move_news_blocked', 0)} blocked from primary due to post-move timing.",
        f"- {summary.get('downgraded_due_to_missing_data', 0)} downgraded or caveated due to missing data.",
    ]


def _factor_lines(context: ResearchContext) -> tuple[list[str], list[str]]:
    bullish: list[str] = []
    bearish: list[str] = []
    market = context.market.data
    derivatives = context.derivatives.data
    onchain = context.onchain.data
    news_events = context.news.data.get("events", [])
    if (market.get("price_change_24h_pct") or 0) > 1:
        bullish.append("Positive 24h price momentum.")
    if market.get("market_signal") in {"uptrend_intact", "short_term_strength"}:
        bullish.append(f"Market signal is {market.get('market_signal')}.")
    if (market.get("price_change_24h_pct") or 0) < -1:
        bearish.append("Negative 24h price momentum.")
    if derivatives.get("derivatives_signal") in {"leverage_flush", "crowded_longs_under_pressure", "sentiment_flip_bearish"}:
        bearish.append(f"Derivatives signal is {derivatives.get('derivatives_signal')}.")
    if onchain.get("onchain_signal") in {"large_transfer_cluster", "exchange_inflow_pressure", "liquidity_contraction"}:
        bearish.append(f"On-chain signal is {onchain.get('onchain_signal')}.")
    for event in news_events[:5]:
        if event.get("direction") == "bullish":
            bullish.append(f"{event.get('title')} ({event.get('impact_level')})")
        elif event.get("direction") == "bearish":
            bearish.append(f"{event.get('title')} ({event.get('impact_level')})")

    # ETF factors
    if context.etf:
        etf = context.etf.data
        etf_dir = etf.get("flow_direction")
        etf_intensity = etf.get("flow_intensity")
        if etf_dir == "inflow" and etf_intensity == "high":
            bullish.append(f"BTC ETF high inflow ({etf.get('btc_etf_net_flow_usd_m')}M USD).")
        elif etf_dir == "outflow" and etf_intensity == "high":
            bearish.append(f"BTC ETF high outflow ({abs(etf.get('btc_etf_net_flow_usd_m') or 0)}M USD).")
        elif etf_dir == "outflow":
            bearish.append(f"BTC ETF outflow detected ({etf.get('btc_etf_net_flow_usd_m')}M USD).")

    # Macro factors
    if context.macro:
        macro = context.macro.data
        macro_signal = macro.get("macro_signal")
        if macro_signal == "risk_off":
            bearish.append("Macro risk-off signal (QQQ down, VIX up).")
        elif macro_signal == "risk_on":
            bullish.append("Macro risk-on signal (QQQ up, DXY down).")
        elif macro_signal == "rates_pressure":
            bearish.append(f"US10Y yield rising ({macro.get('us10y_change_bp')} bp), pressuring risk assets.")
        elif macro_signal == "dollar_pressure":
            bearish.append(f"DXY strengthening ({macro.get('dxy_change_24h_pct')}%), pressuring crypto.")

    return bullish or ["No clearly bullish factor is confirmed."], bearish or ["No clearly bearish factor is confirmed."]


def local_report(context: ResearchContext) -> str:
    risk = context.risk
    attr = context.attribution
    mode = context.intent.mode
    title = {
        "event_attribution": "Market Attribution Report",
        "state_scan": "Market State Scan",
        "risk_watch": "Risk Watch Report",
    }.get(mode, "Market Research Report")
    lines = [f"# {context.intent.asset} {title}", "", "## TL;DR", attr["event_summary"]]

    lines.extend(["", "## Market Snapshot", *_market_lines(context)])

    if mode == "risk_watch":
        lines.extend(["", "## Risk Score", *_risk_lines(risk)])
        lines.extend(["", "## Key Risks"])
        for item in attr["primary_drivers"] + attr["secondary_drivers"]:
            lines.append(f"- {item['driver']}: {item['explanation']}")
        lines.extend(
            [
                "",
                "## Watchlist",
                "- Whether funding and open interest become more extreme.",
                "- Whether high-impact bearish news clusters continue.",
                "- Whether large on-chain transfers increase.",
                "- Whether price loses nearby EMA levels.",
            ]
        )
    elif mode == "state_scan":
        bullish, bearish = _factor_lines(context)
        lines.extend(["", "## Bullish Factors", *[f"- {item}" for item in bullish]])
        lines.extend(["", "## Bearish Factors", *[f"- {item}" for item in bearish]])
        lines.extend(["", "## Risk Score", *_risk_lines(risk)])
        lines.extend(["", "## Watchlist", "- Whether price holds EMA20/EMA50.", "- Whether derivatives positioning confirms or fades.", "- Whether relevant news flow changes direction."])
    else:
        lines.extend(["", "## 1. Market Move Summary", attr["event_summary"]])
        lines.extend(["", "## 2. Most Plausible Drivers"])
        for index, item in enumerate(attr["primary_drivers"], 1):
            lines.extend(_driver_lines(item, index))
        lines.extend(["", "## 3. Secondary Drivers"])
        if attr["secondary_drivers"]:
            for index, item in enumerate(attr["secondary_drivers"], 1):
                lines.extend(_driver_lines(item, index))
        else:
            lines.append("No secondary driver has enough evidence yet.")
        lines.extend(["", "## 4. Alternative Explanations"])
        if attr.get("alternative_explanations"):
            for item in attr["alternative_explanations"]:
                lines.append(f"- {item.get('explanation')} Why not primary: {item.get('why_not_primary')}")
        else:
            lines.append("- No material alternative explanation was supported by the current data.")
        lines.extend(["", "## 5. Data Quality", *_data_quality_lines(attr), *_layer_data_quality_lines(context)])
        lines.extend(["", "## 6. Attribution Trace Summary", *_trace_summary_lines(attr)])
        lines.extend(["", "## Noise / Unsupported Claims"])
        if attr["noise"]:
            for index, item in enumerate(attr["noise"], 1):
                lines.extend([f"{index}. {item['driver']}", item["reason"]])
        else:
            lines.append("No unsupported claim cluster was detected.")
        lines.extend(["", "## Risk Watch", *_risk_lines(risk)])
        lines.extend(["", "## Watchlist", "- Whether price reclaims or loses EMA20/EMA50.", "- Whether funding and open interest normalize.", "- Whether high-impact news continues in the same direction.", "- Whether large on-chain transfers or exchange inflows increase."])

    if mode != "event_attribution":
        lines.extend(["", "## Data Quality", *_data_quality_lines(attr), *_layer_data_quality_lines(context)])

    lines.extend(["", "## Data Limits"])
    layers = [context.market, context.derivatives, context.news, context.onchain]
    if context.etf is not None:
        layers.append(context.etf)
    any_errors = False
    for layer in layers:
        if layer.errors:
            any_errors = True
            lines.append(_summarize_layer_errors(layer.layer, layer.errors))
    if any_errors:
        lines.append("- Attribution confidence has been reduced where data is limited.")
    else:
        lines.append("- No source-level errors were recorded for this report.")

    # Spot CVD 近似说明
    spot_bias_dl = context.market.data.get("spot_flow_bias")
    if spot_bias_dl and spot_bias_dl != "unavailable":
        lines.append("- Spot CVD is an approximation from public trades (not exchange-wide CVD). Treat direction with caution.")

    lines.extend(["", "## Evidence Quality", *_evidence_quality_lines(context)])

    lines.extend(["", "## Disclaimer", DISCLAIMER])
    return "\n".join(lines)


async def generate_report(context: ResearchContext, llm: DeepSeekClient) -> str:
    mode_instruction = {
        "event_attribution": "Use Market Move Summary, Most Plausible Drivers, Secondary Drivers, Alternative Explanations, Data Quality, Attribution Trace Summary, Risk Watch, Data Limits, Disclaimer.",
        "state_scan": "Use TL;DR, Market Snapshot, Bullish Factors, Bearish Factors, Risk Score, Watchlist, Data Quality, Data Limits, Disclaimer. Do not force Primary/Secondary/Noise sections.",
        "risk_watch": "Use TL;DR, Market Snapshot, Risk Score, Key Risks, Watchlist, Data Quality, Data Limits, Disclaimer. Make Risk Score the center of the report.",
    }.get(context.intent.mode, "Use the standard research report format.")
    system = (
        "You are a crypto research analyst. Generate a structured research report "
        "based only on the provided JSON data. Do not invent data. Do not make buy, "
        "sell, hold, leverage, or personalized investment recommendations. Explain each claim with evidence. "
        "Use explicit methodology labels where relevant: tracked liquidation, not full-market liquidation; "
        "spot CVD approximation, not exact CVD; ETF flow best effort, may be stale; "
        "stablecoin supply proxy, not direct buying pressure. "
        "On-chain transfer wording rules: never write 'whale is selling' unless the destination "
        "is a confirmed labeled exchange address AND the evidence is strong. "
        "Prefer: 'A large transfer to a labeled exchange address may indicate potential sell-side preparation, "
        "but attribution confidence is limited.' "
        "Exchange-to-exchange transfers are internal venue flow with low attribution confidence. "
        "If macro context is available (risk_on/risk_off/rates_pressure/dollar_pressure), include it "
        "as a supporting or counter factor. If ETF flow data is available, include it in the relevant section. "
        "If spot CVD approximation is available, mention it with the explicit caveat that it is not exact CVD. "
        f"Mode-specific format: {mode_instruction} Always include the exact disclaimer."
    )
    payload = context.model_dump()
    payload["required_disclaimer"] = DISCLAIMER
    content = await llm.chat(system, json.dumps(payload, ensure_ascii=True), temperature=0.2)
    if not content:
        content = local_report(context)
    return sanitize_report(content)


def local_chinese_auto_report(context: ResearchContext) -> str:
    asset = context.intent.asset
    market = context.market.data
    derivatives = context.derivatives.data
    news = context.news.data
    onchain = context.onchain.data
    top_news = news.get("top_news") or {}
    direction_label = market.get("direction_label_zh") or "震荡"
    change_4h = market.get("price_change_4h_pct")
    change_text = f"{change_4h:.2f}%" if isinstance(change_4h, (int, float)) else "当前数据不足以确认"
    lines = [
        f"# {asset} 4小时市场异动分析",
        "",
        "## 一句话结论",
        f"{asset} 当前自动判断为{direction_label}，4小时变化为 {change_text}。{market.get('trigger_reason') or '当前数据不足以确认。'}",
        "",
        "## 4小时市场表现",
        f"- 当前价格：{market.get('price_now') or '当前数据不足以确认'}",
        f"- 4小时变化：{change_text}",
        f"- 24小时变化：{market.get('price_change_24h_pct') if market.get('price_change_24h_pct') is not None else '当前数据不足以确认'}",
        f"- 成交量：{market.get('volume_24h') or market.get('spot_turnover_24h') or '当前数据不足以确认'}",
    ]
    spot_bias_cn = market.get("spot_flow_bias")
    if spot_bias_cn and spot_bias_cn != "unavailable":
        bias_label = "买盘主导" if spot_bias_cn == "buy_pressure" else "卖盘主导" if spot_bias_cn == "sell_pressure" else "中性"
        lines.append(f"- 现货主动成交方向（近似CVD）：{bias_label}（方法={market.get('method', 'tick_rule')}，非精确CVD）")
    lines.extend([
        "",
        "## 可能驱动因素",
        (
            f"价格在 4 小时内变化 {change_text}，24 小时变化为 "
            f"{market.get('price_change_24h_pct') if market.get('price_change_24h_pct') is not None else '当前数据不足以确认'}。"
            "需要结合新闻、衍生品和链上数据继续确认驱动因素。"
        ),
        "",
        "## 新闻事件",
        f"- 标题：{top_news.get('title') or '当前数据不足以确认'}",
        f"- 来源：{top_news.get('source') or '当前数据不足以确认'}",
        f"- 链接：{top_news.get('url') or '当前数据不足以确认'}",
        f"- 影响判断：{top_news.get('reason_zh') or top_news.get('reason') or '当前数据不足以确认'}",
        "",
        "## 衍生品信号",
        f"- Funding Rate：{derivatives.get('funding_rate_now') if derivatives.get('funding_rate_now') is not None else '当前数据不足以确认'}",
        f"- Open Interest 24小时变化：{derivatives.get('open_interest_change_24h_pct') if derivatives.get('open_interest_change_24h_pct') is not None else '当前数据不足以确认'}",
        f"- 24小时已追踪多头/空头清算：{derivatives.get('long_liquidations_24h')} / {derivatives.get('short_liquidations_24h')}（不是全市场清算）",
        "",
        "## 宏观背景",
    ])
    if context.macro:
        macro = context.macro.data
        macro_signal = macro.get("macro_signal", "unavailable")
        macro_confidence = macro.get("macro_confidence", "low")
        lines.append(f"- 宏观信号：{macro_signal}（置信度={macro_confidence}）")
        qqq = macro.get("qqq_change_24h_pct") or macro.get("nasdaq_change_24h_pct")
        dxy = macro.get("dxy_change_24h_pct")
        vix = macro.get("vix_change_24h_pct")
        us10y = macro.get("us10y_change_bp")
        if qqq is not None:
            lines.append(f"- QQQ/Nasdaq 24h变化：{qqq:.2f}%")
        if dxy is not None:
            lines.append(f"- DXY 24h变化：{dxy:.2f}%")
        if vix is not None:
            lines.append(f"- VIX 24h变化：{vix:.2f}%")
        if us10y is not None:
            lines.append(f"- US10Y 变化：{us10y:.1f} bp")
    else:
        lines.append("- 宏观数据不可用")
    lines.extend([
        "",
        "## 链上信号",
        onchain.get("onchain_signal") or "当前数据不足以确认。",
        f"- 链上证据质量：{onchain.get('onchain_evidence_quality') or '当前数据不足以确认'}",
        f"- 已标记交易所转入笔数：{onchain.get('exchange_inflow_count') if onchain.get('exchange_inflow_count') is not None else '当前数据不足以确认'}",
        f"- 交易所内部转账笔数（不计入流入）：{onchain.get('exchange_internal_count') if onchain.get('exchange_internal_count') is not None else '当前数据不足以确认'}",
        f"- 大额转账笔数：{onchain.get('large_transfer_count') if onchain.get('large_transfer_count') is not None else '当前数据不足以确认'}",
        "注意：仅当目标地址为已标记的交易所地址时才标记为潜在卖压，交易所之间转账为内部调拨，未标记转账不得描述为鲸鱼卖出。",
        "",
        "## 数据质量",
        f"- 市场数据：{(market.get('data_quality') or {}).get('confidence', 'unknown')}",
        f"- 衍生品数据：{(derivatives.get('data_quality') or {}).get('confidence', 'unknown')}，清算为已追踪样本，不代表全市场。",
        f"- 新闻数据：{(news.get('data_quality') or {}).get('confidence', 'unknown')}",
        f"- 链上数据：{(onchain.get('data_quality') or {}).get('confidence', 'unknown')}，稳定币供应变化是流动性代理，不等于直接买盘。",
        "",
        "## 多空因素",
        "### 偏多因素",
        "- 当前数据不足以确认。" if not context.attribution.get("primary_drivers") else f"- {context.attribution['primary_drivers'][0].get('driver')}: {context.attribution['primary_drivers'][0].get('explanation')}",
        "### 偏空因素",
        f"- 新闻方向：{top_news.get('direction') or '当前数据不足以确认'}",
        "",
        "## 接下来观察",
        "- 4小时价格变化是否继续超过阈值。",
        "- Funding Rate、Open Interest 与清算结构是否同步变化。",
        "- 核心新闻是否出现后续确认或反转。",
        "",
        "## 风险提示",
        CHINESE_DISCLAIMER,
    ])
    return "\n".join(lines)


async def generate_chinese_auto_report(context: ResearchContext, llm: DeepSeekClient) -> str:
    system = (
        "你是一名加密货币市场研究分析师。请基于给定 JSON 数据生成中文研究报告。\n"
        "要求：\n"
        "1. 只使用输入数据，不要编造数据。\n"
        "2. 不要给出买入、卖出、持有、加杠杆等交易建议。\n"
        "3. 不要使用英文标题，除非是 BTC、ETH、ETF、Funding Rate 等行业术语。\n"
        "4. 报告面向个人研究使用，风格简洁、清晰、偏投研。\n"
        "5. 如果数据不足，请明确说明\u201c当前数据不足以确认\u201d。\n"
        "6. 必须包含风险提示。\n"
        "7. 涉及清算、CVD、ETF、稳定币供应时，必须说明：清算是已追踪样本不是全市场；spot CVD 是近似值不是精确 CVD；ETF flow 是 best effort 且可能滞后；稳定币供应是流动性代理不是直接买盘。\n"
        "8. 链上大额转账措辞规则：除非目标地址是已确认的交易所地址且证据确凿，否则绝对不要写\u201c鲸鱼在卖\u201d。应优先使用：\u201c一笔大额转账至已标记的交易所地址可能表明潜在的卖盘准备，但归因置信度有限。\u201d交易所之间的转账为内部调拨，归因置信度低。\n"
        "9. 如果提供了宏观背景数据（macro_signal、DXY、VIX、US10Y等），在报告中增加\u201c宏观背景\u201d段落。\n"
        "10. 如果提供了 ETF 流量数据，在\u201c衍生品信号\u201d段落中引用。\n"
        "11. 如果提供了 Spot CVD 近似数据，引用时明确标注\u201c近似CVD，非精确交易所CVD\u201d。"
    )
    user = {
        "required_format": (
            "# BTC/ETH 4小时市场异动分析\n"
            "## 一句话结论\n## 4小时市场表现\n## 可能驱动因素\n"
            "## 新闻事件\n## 衍生品信号\n## 链上信号\n## 数据质量\n"
            "## 多空因素\n### 偏多因素\n### 偏空因素\n## 接下来观察\n## 风险提示"
        ),
        "context": context.model_dump(),
        "required_disclaimer": CHINESE_DISCLAIMER,
    }
    content = await llm.chat(system, json.dumps(user, ensure_ascii=False), temperature=0.2)
    if not content:
        content = local_chinese_auto_report(context)
    return sanitize_chinese_report(content)
