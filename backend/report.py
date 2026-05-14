from __future__ import annotations

import json
import re

from backend.llm import DeepSeekClient
from backend.models import DISCLAIMER, ResearchContext


CHINESE_DISCLAIMER = "本报告仅用于研究和信息参考，不构成任何投资建议。"

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
    lines = [
        f"- Price: ${market.get('price_now'):,.2f}" if market.get("price_now") else "- Price: unavailable",
        f"- 1h / 24h / 7d Change: {market.get('price_change_1h_pct')}% / {market.get('price_change_24h_pct')}% / {market.get('price_change_7d_pct')}%",
        f"- 24h Volume: {market.get('volume_24h')}",
        f"- Volume vs 7d: {market.get('volume_ratio_vs_7d')}",
        f"- EMA20 / EMA50 / EMA200: {market.get('ema_20')} / {market.get('ema_50')} / {market.get('ema_200')}",
        f"- Funding Rate: {derivatives.get('funding_rate_now')}",
        f"- Open Interest 24h Change: {derivatives.get('open_interest_change_24h_pct')}%",
        f"- 24h Liquidations Long / Short: {derivatives.get('long_liquidations_24h')} / {derivatives.get('short_liquidations_24h')}",
        f"- Put/Call Ratio: {derivatives.get('put_call_ratio')}",
        f"- Stablecoin 24h Supply Change: {onchain.get('stablecoin_supply_change_24h')}",
        f"- On-chain Signal: {onchain.get('onchain_signal')}",
    ]
    return lines


def _risk_lines(risk: dict) -> list[str]:
    return [
        f"Risk Score: {risk['risk_score']}/12 - {risk['risk_level']}",
        f"- Liquidity Risk: {risk['risk_breakdown']['liquidity_risk']}/3",
        f"- Leverage Risk: {risk['risk_breakdown']['leverage_risk']}/3",
        f"- News Risk: {risk['risk_breakdown']['news_risk']}/3",
        f"- On-chain Risk: {risk['risk_breakdown']['onchain_risk']}/3",
        f"- Summary: {risk.get('risk_summary')}",
    ]


def _evidence_quality_lines(context: ResearchContext) -> list[str]:
    lines = [
        "- Strong: labeled exchange inflow, direct market data, or official source.",
        "- Medium: public API with partial context.",
        "- Weak: unlabeled large transfer or price commentary.",
    ]
    if context.onchain.data.get("onchain_evidence_quality"):
        lines.append(f"- On-chain evidence quality: {context.onchain.data.get('onchain_evidence_quality')}.")
    etf = context.etf.data if context.etf else {}
    if etf and (etf.get("flow_direction") == "unavailable" or etf.get("is_stale")):
        lines.append("- Data limitation: ETF flow data is unavailable or stale; this report does not treat ETF flows as confirmed evidence.")
    return lines


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
        lines.extend(["", "## Primary Drivers"])
        for index, item in enumerate(attr["primary_drivers"], 1):
            lines.extend([f"{index}. {item['driver']}", item["explanation"]])
        lines.extend(["", "## Secondary Drivers"])
        if attr["secondary_drivers"]:
            for index, item in enumerate(attr["secondary_drivers"], 1):
                lines.extend([f"{index}. {item['driver']}", item["explanation"]])
        else:
            lines.append("No secondary driver has enough evidence yet.")
        lines.extend(["", "## Noise / Unsupported Claims"])
        if attr["noise"]:
            for index, item in enumerate(attr["noise"], 1):
                lines.extend([f"{index}. {item['driver']}", item["reason"]])
        else:
            lines.append("No unsupported claim cluster was detected.")
        lines.extend(["", "## Risk Score", *_risk_lines(risk)])
        lines.extend(["", "## Watchlist", "- Whether price reclaims or loses EMA20/EMA50.", "- Whether funding and open interest normalize.", "- Whether high-impact news continues in the same direction.", "- Whether large on-chain transfers or exchange inflows increase."])

    lines.extend(["", "## Data Limits"])
    layers = [context.market, context.derivatives, context.news, context.onchain]
    if context.etf is not None:
        layers.append(context.etf)
    for layer in layers:
        if layer.errors:
            lines.append(f"- {layer.layer}: {'; '.join(layer.errors[:2])}")
    if not any(layer.errors for layer in layers):
        lines.append("- No source-level errors were recorded for this report.")

    lines.extend(["", "## Evidence Quality", *_evidence_quality_lines(context)])

    lines.extend(["", "## Disclaimer", DISCLAIMER])
    return "\n".join(lines)


async def generate_report(context: ResearchContext, llm: DeepSeekClient) -> str:
    mode_instruction = {
        "event_attribution": "Use TL;DR, Market Snapshot, Primary Drivers, Secondary Drivers, Noise / Unsupported Claims, Risk Score, Watchlist, Data Limits, Disclaimer.",
        "state_scan": "Use TL;DR, Market Snapshot, Bullish Factors, Bearish Factors, Risk Score, Watchlist, Data Limits, Disclaimer. Do not force Primary/Secondary/Noise sections.",
        "risk_watch": "Use TL;DR, Market Snapshot, Risk Score, Key Risks, Watchlist, Data Limits, Disclaimer. Make Risk Score the center of the report.",
    }.get(context.intent.mode, "Use the standard research report format.")
    system = (
        "You are a crypto research analyst. Generate a structured research report "
        "based only on the provided JSON data. Do not invent data. Do not make buy, "
        "sell, hold, leverage, or personalized investment recommendations. Explain each claim with evidence. "
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
        f"- 24小时多头/空头清算：{derivatives.get('long_liquidations_24h')} / {derivatives.get('short_liquidations_24h')}",
        "",
        "## 链上信号",
        onchain.get("onchain_signal") or "当前数据不足以确认。",
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
    ]
    return "\n".join(lines)


async def generate_chinese_auto_report(context: ResearchContext, llm: DeepSeekClient) -> str:
    system = (
        "你是一名加密货币市场研究分析师。请基于给定 JSON 数据生成中文研究报告。\n"
        "要求：\n"
        "1. 只使用输入数据，不要编造数据。\n"
        "2. 不要给出买入、卖出、持有、加杠杆等交易建议。\n"
        "3. 不要使用英文标题，除非是 BTC、ETH、ETF、Funding Rate 等行业术语。\n"
        "4. 报告面向个人研究使用，风格简洁、清晰、偏投研。\n"
        "5. 如果数据不足，请明确说明“当前数据不足以确认”。\n"
        "6. 必须包含风险提示。"
    )
    user = {
        "required_format": (
            "# BTC/ETH 4小时市场异动分析\n"
            "## 一句话结论\n## 4小时市场表现\n## 可能驱动因素\n"
            "## 新闻事件\n## 衍生品信号\n## 链上信号\n## 多空因素\n"
            "### 偏多因素\n### 偏空因素\n## 接下来观察\n## 风险提示"
        ),
        "context": context.model_dump(),
        "required_disclaimer": CHINESE_DISCLAIMER,
    }
    content = await llm.chat(system, json.dumps(user, ensure_ascii=False), temperature=0.2)
    if not content:
        content = local_chinese_auto_report(context)
    return sanitize_chinese_report(content)
