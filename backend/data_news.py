from __future__ import annotations

import json
import re
from datetime import UTC, datetime

import feedparser
import httpx

from backend.config import Settings
from backend.data_etf import fetch_btc_etf_flow
from backend.http_client import get_text
from backend.models import LayerResult
from backend.utils import ASSET_META, contains_any, parse_feed_date, utc_now, window_to_timedelta


RSS_FEEDS = {
    "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "CoinTelegraph": "https://cointelegraph.com/rss",
    "Decrypt": "https://decrypt.co/feed",
    "The Block": "https://www.theblock.co/rss.xml",
    "PANews": "https://www.panewslab.com/rss.xml",
    "Bitcoin Magazine": "https://bitcoinmagazine.com/.rss/full/",
    "Wu Blockchain": "https://wublock.substack.com/feed",
}


KEYWORDS = {
    "etf_flow": ("etf", "ibit", "gbtc", "net outflow", "net inflow", "spot bitcoin etf"),
    "regulation_policy": ("sec", "lawsuit", "regulation", "ban", "approval", "cftc"),
    "macro_data": ("cpi", "fomc", "fed", "rate cut", "nfp", "inflation", "treasury", "dollar"),
    "security_event": ("hack", "exploit", "bridge", "vulnerability", "drain"),
    "project_event": ("upgrade", "fork", "staking", "restaking", "dencun", "pectra"),
    "exchange_event": ("withdrawal suspended", "listing", "delisting", "exchange"),
}

BEARISH = ("outflow", "hack", "exploit", "lawsuit", "ban", "sell-off", "liquidation", "drop", "falls")
BULLISH = ("inflow", "approval", "rally", "surge", "upgrade", "accumulation", "record high", "gains")


def classify_news(title: str, summary: str, asset: str) -> dict:
    text = f"{title} {summary}".lower()
    category = "market_commentary"
    for candidate, terms in KEYWORDS.items():
        if any(term in text for term in terms):
            category = candidate
            break
    if any(term in text for term in BEARISH):
        direction = "bearish"
    elif any(term in text for term in BULLISH):
        direction = "bullish"
    else:
        direction = "neutral"
    high_categories = {"etf_flow", "regulation_policy", "macro_data", "security_event"}
    impact_level = "high" if category in high_categories and direction != "neutral" else "medium"
    if category == "market_commentary" and direction == "neutral":
        impact_level = "low"
    related = [asset]
    other = "ETH" if asset == "BTC" else "BTC"
    if contains_any(text, ASSET_META[other]["name_terms"]):
        related.append(other)
    return {
        "category": category,
        "asset_related": related,
        "direction": direction,
        "impact_level": impact_level,
        "confidence": 0.72 if category != "market_commentary" else 0.55,
    }


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


async def classify_news_with_llm(llm, event: dict, fallback: dict) -> dict:
    if llm is None or not getattr(llm, "available", False):
        return fallback
    system = (
        "You are a crypto news classifier. Return JSON only. "
        "category must be one of regulation_policy, macro_data, etf_flow, "
        "exchange_event, security_event, project_event, market_commentary. "
        "direction must be bullish, bearish, or neutral. impact_level must be high, medium, or low. "
        "related_assets must contain BTC, ETH, or both. Include reason as one concise sentence."
    )
    user = json.dumps(
        {
            "title": event.get("title"),
            "summary": event.get("summary"),
            "source": event.get("source"),
            "published_at": event.get("published_at"),
            "fallback_classification": fallback,
        },
        ensure_ascii=True,
    )
    parsed = await llm.json_chat(system, user)
    if not parsed:
        return fallback
    allowed_categories = {
        "regulation_policy",
        "macro_data",
        "etf_flow",
        "exchange_event",
        "security_event",
        "project_event",
        "market_commentary",
    }
    category = parsed.get("category") if parsed.get("category") in allowed_categories else fallback["category"]
    direction = parsed.get("direction") if parsed.get("direction") in {"bullish", "bearish", "neutral"} else fallback["direction"]
    impact = parsed.get("impact_level") if parsed.get("impact_level") in {"high", "medium", "low"} else fallback["impact_level"]
    related = parsed.get("related_assets") or parsed.get("asset_related") or fallback["asset_related"]
    if not isinstance(related, list):
        related = fallback["asset_related"]
    return {
        "category": category,
        "asset_related": [asset for asset in related if asset in {"BTC", "ETH"}] or fallback["asset_related"],
        "direction": direction,
        "impact_level": impact,
        "summary": parsed.get("summary") or event.get("summary", ""),
        "reason": parsed.get("reason", "LLM classification applied."),
        "confidence": float(parsed.get("confidence") or max(float(fallback.get("confidence", 0.55)), 0.76)),
    }


def _signal(events: list[dict]) -> str:
    high_bearish = [event for event in events if event["impact_level"] == "high" and event["direction"] == "bearish"]
    high_bullish = [event for event in events if event["impact_level"] == "high" and event["direction"] == "bullish"]
    if len(high_bearish) >= 2:
        return "high_impact_bearish_news_cluster"
    if high_bearish:
        return "single_high_impact_bearish_news"
    if high_bullish:
        return "high_impact_bullish_news"
    if events:
        return "mixed_or_low_impact_news"
    return "no_relevant_news_found"


async def fetch_news(settings: Settings, asset: str, time_window: str, llm=None) -> LayerResult:
    cutoff = utc_now() - window_to_timedelta(time_window)
    events: list[dict] = []
    errors: list[str] = []
    terms = ASSET_META[asset]["name_terms"]
    macro_terms = ("fed", "cpi", "fomc", "sec", "etf")

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        for source, url in RSS_FEEDS.items():
            xml, error = await get_text(client, url, source=f"rss:{source}")
            if error:
                errors.append(error)
                continue
            feed = feedparser.parse(xml)
            for entry in feed.entries[:30]:
                title = strip_html(getattr(entry, "title", ""))
                summary = strip_html(getattr(entry, "summary", ""))
                combined = f"{title} {summary}"
                if not contains_any(combined, terms + macro_terms):
                    continue
                published_at = parse_feed_date(getattr(entry, "published", None) or getattr(entry, "updated", None))
                if published_at:
                    published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00")).astimezone(UTC)
                    if published_dt < cutoff:
                        continue
                classification = classify_news(title, summary, asset)
                events.append(
                    {
                        "title": title,
                        "source": source,
                        "url": getattr(entry, "link", ""),
                        "published_at": published_at,
                        "summary": summary[:320],
                        **classification,
                    }
                )

    seen: set[str] = set()
    deduped: list[dict] = []
    for event in events:
        key = event["url"] or event["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(event)
    deduped = deduped[:12]
    etf_flow = None
    if asset == "BTC":
        etf_flow, etf_errors = await fetch_btc_etf_flow()
        errors.extend(etf_errors)

    refined: list[dict] = []
    for event in deduped:
        fallback = {
            "category": event.get("category"),
            "asset_related": event.get("asset_related"),
            "direction": event.get("direction"),
            "impact_level": event.get("impact_level"),
            "confidence": event.get("confidence"),
        }
        refined_classification = await classify_news_with_llm(llm, event, fallback)
        event = {**event, **refined_classification}
        refined.append(event)
    deduped = refined
    return LayerResult(
        layer="news",
        source="rss",
        data={"events": deduped, "news_signal": _signal(deduped), "etf_flow": etf_flow},
        errors=errors,
    )
