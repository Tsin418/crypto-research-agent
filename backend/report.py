from __future__ import annotations

import json
import re

from backend.llm import DeepSeekClient
from backend.models import DISCLAIMER, ResearchContext


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
    for layer in (context.market, context.derivatives, context.news, context.onchain):
        if layer.errors:
            lines.append(f"- {layer.layer}: {'; '.join(layer.errors[:2])}")
    if not any(layer.errors for layer in (context.market, context.derivatives, context.news, context.onchain)):
        lines.append("- No source-level errors were recorded for this report.")

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
