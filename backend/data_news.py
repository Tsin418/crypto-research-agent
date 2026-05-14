from __future__ import annotations

import asyncio
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

ASSET_NEWS_TERMS = {
    "BTC": (
        "bitcoin",
        "btc",
        "spot bitcoin etf",
        "etf",
        "miner",
        "microstrategy",
        "fed",
        "cpi",
        "rate cut",
        "dollar",
        "treasury",
    ),
    "ETH": (
        "ethereum",
        "eth",
        "staking",
        "restaking",
        "validator",
        "l2",
        "gas",
        "etf",
        "foundation",
        "pectra",
    ),
}


KEYWORDS = {
    "etf_flow": ("etf", "ibit", "gbtc", "net outflow", "net inflow", "spot bitcoin etf"),
    "regulation_policy": ("sec", "lawsuit", "regulation", "ban", "approval", "cftc"),
    "macro_data": ("cpi", "fomc", "fed", "rate cut", "nfp", "inflation", "treasury", "dollar"),
    "security_event": ("hack", "exploit", "bridge", "vulnerability", "drain"),
    "project_event": ("upgrade", "fork", "staking", "restaking", "dencun", "pectra"),
    "exchange_event": ("withdrawal suspended", "listing", "delisting", "exchange"),
}

SOURCE_WEIGHT = {
    "official_regulatory": 1.3,
    "exchange_announcement": 1.2,
    "The Block": 1.1,
    "CoinDesk": 1.1,
    "Wu Blockchain": 1.0,
    "PANews": 0.9,
    "Decrypt": 0.8,
    "CoinTelegraph": 0.8,
    "Bitcoin Magazine": 0.8,
    "unknown": 0.7,
}

CATEGORY_PRIOR = {
    "macro_data": 1.2,
    "regulation_policy": 1.2,
    "security_event": 1.2,
    "etf_flow": 1.1,
    "exchange_event": 1.0,
    "project_event": 0.7,
    "market_commentary": 0.4,
}

BEARISH = ("outflow", "hack", "exploit", "lawsuit", "ban", "sell-off", "liquidation", "drop", "falls")
BULLISH = ("inflow", "approval", "rally", "surge", "upgrade", "accumulation", "record high", "gains")


def news_weight_trace(source: str | None, category: str | None) -> dict:
    source_name = source or "unknown"
    category_name = category or "market_commentary"
    source_weight = SOURCE_WEIGHT.get(source_name, SOURCE_WEIGHT["unknown"])
    category_prior = CATEGORY_PRIOR.get(category_name, 0.7)
    return {
        "source_weight": source_weight,
        "category_prior": category_prior,
        "news_weight_trace": {
            "source": source_name,
            "source_weight": source_weight,
            "category": category_name,
            "category_prior": category_prior,
        },
    }


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
    result = {
        "category": category,
        "asset_related": related,
        "direction": direction,
        "impact_level": impact_level,
        "confidence": 0.72 if category != "market_commentary" else 0.55,
    }
    result.update(news_weight_trace(None, category))
    return result


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _normalized_title(title: str) -> str:
    normalized = re.sub(r"https?://\S+", "", title.lower())
    normalized = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", normalized)
    stopwords = {"the", "a", "an", "to", "of", "and", "in", "on", "for", "with", "as"}
    return " ".join(word for word in normalized.split() if word not in stopwords)


def _has_cjk(text: str | None) -> bool:
    return bool(text and re.search(r"[\u4e00-\u9fff]", text))


def dedupe_news_events(events: list[dict]) -> list[dict]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    deduped: list[dict] = []
    for event in events:
        url = (event.get("url") or "").split("?")[0].rstrip("/")
        title_key = _normalized_title(event.get("title") or "")
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        deduped.append(event)
    return deduped


def _fallback_top_news(events: list[dict], asset: str) -> dict:
    if not events:
        return {
            "title": "当前未发现高相关核心新闻",
            "url": "",
            "source": "",
            "published_at": None,
            "related_assets": [asset],
            "impact_level": "low",
            "direction": "neutral",
            "reason_zh": "RSS 源中暂未发现足够相关且可确认的核心事件。",
        }
    impact_rank = {"high": 3, "medium": 2, "low": 1}
    direction_rank = {"bearish": 2, "bullish": 2, "neutral": 1}
    event = max(
        events,
        key=lambda item: (
            impact_rank.get(item.get("impact_level"), 0),
            direction_rank.get(item.get("direction"), 0),
            item.get("published_at") or "",
        ),
    )
    return {
        "title": event.get("title") or "",
        "url": event.get("url") or "",
        "source": event.get("source") or "",
        "published_at": event.get("published_at"),
        "related_assets": event.get("asset_related") or event.get("related_assets") or [asset],
        "impact_level": event.get("impact_level") or "low",
        "direction": event.get("direction") or "neutral",
        "reason_zh": event.get("reason_zh") if _has_cjk(event.get("reason_zh")) else "按影响等级、资产相关性和发布时间自动选择。",
    }


async def select_top_news_event(llm, events: list[dict], asset: str) -> dict:
    deduped = dedupe_news_events(
        [
            event
            for event in events
            if contains_any(
                f"{event.get('title', '')} {event.get('summary', '')}",
                ASSET_NEWS_TERMS.get(asset, ASSET_META[asset]["name_terms"]),
            )
        ]
    )
    fallback = _fallback_top_news(deduped, asset)
    if llm is None or not getattr(llm, "available", False) or not deduped:
        return fallback
    system = (
        "你会收到一组来自不同媒体的加密货币新闻。请完成：\n"
        "1. 判断哪些新闻实际上是同一个事件，进行去重。\n"
        "2. 从去重后的事件中，选出对指定资产影响最大的一个事件。\n"
        "3. 返回 JSON，不要返回 Markdown。\n\n"
        "选择标准：\n"
        "- 优先选择直接影响 BTC/ETH 价格、ETF、监管、宏观利率、交易所、黑客攻击、重大链上事件的新闻。\n"
        "- 如果只是普通价格评论，优先级较低。\n"
        "- 如果多个媒体报道同一事件，只保留信息最完整、链接最可靠的一条。\n\n"
        "输出 JSON：\n"
        "{\"title\":\"...\",\"url\":\"...\",\"source\":\"...\",\"published_at\":\"...\","
        "\"related_assets\":[\"BTC\"],\"impact_level\":\"high|medium|low\","
        "\"direction\":\"bullish|bearish|neutral\",\"reason_zh\":\"...\"}"
    )
    parsed = await llm.json_chat(
        system,
        json.dumps({"asset": asset, "news": deduped[:16]}, ensure_ascii=False),
    )
    if not isinstance(parsed, dict):
        return fallback
    impact = parsed.get("impact_level") if parsed.get("impact_level") in {"high", "medium", "low"} else fallback["impact_level"]
    direction = parsed.get("direction") if parsed.get("direction") in {"bullish", "bearish", "neutral"} else fallback["direction"]
    related_assets = parsed.get("related_assets")
    if not isinstance(related_assets, list):
        related_assets = fallback["related_assets"]
    reason_zh = parsed.get("reason_zh")
    if not _has_cjk(reason_zh):
        reason_zh = f"该事件被判定为{impact}影响，方向为{direction}；当前中文原因不足以进一步确认。"
    return {
        "title": parsed.get("title") or fallback["title"],
        "url": parsed.get("url") or fallback["url"],
        "source": parsed.get("source") or fallback["source"],
        "published_at": parsed.get("published_at") or fallback["published_at"],
        "related_assets": [item for item in related_assets if item in {"BTC", "ETH"}] or [asset],
        "impact_level": impact,
        "direction": direction,
        "reason_zh": reason_zh or fallback["reason_zh"],
    }


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
    result = {
        "category": category,
        "asset_related": [asset for asset in related if asset in {"BTC", "ETH"}] or fallback["asset_related"],
        "direction": direction,
        "impact_level": impact,
        "summary": parsed.get("summary") or event.get("summary", ""),
        "reason": parsed.get("reason", "LLM classification applied."),
        "confidence": float(parsed.get("confidence") or max(float(fallback.get("confidence", 0.55)), 0.76)),
    }
    result.update(news_weight_trace(event.get("source"), category))
    return result


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
        async def _fetch_source(source: str, url: str) -> tuple[list[dict], list[str]]:
            source_events: list[dict] = []
            source_errors: list[str] = []
            xml, error = await get_text(client, url, source=f"rss:{source}")
            if error:
                return source_events, [error]
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
                classification.update(news_weight_trace(source, classification.get("category")))
                source_events.append(
                    {
                        "title": title,
                        "source": source,
                        "url": getattr(entry, "link", ""),
                        "published_at": published_at,
                        "summary": summary[:320],
                        **classification,
                    }
                )
            return source_events, source_errors

        source_results = await asyncio.gather(
            *[_fetch_source(source, url) for source, url in RSS_FEEDS.items()]
        )
        for source_events, source_errors in source_results:
            events.extend(source_events)
            errors.extend(source_errors)

    deduped = dedupe_news_events(events)
    deduped = deduped[:12]
    etf_flow = None
    if asset == "BTC":
        etf_flow, etf_errors = await fetch_btc_etf_flow()
        errors.extend(etf_errors)

    refined: list[dict] = []
    semaphore = asyncio.Semaphore(4)

    async def _classify_one(event: dict) -> dict:
        fallback = {
            "category": event.get("category"),
            "asset_related": event.get("asset_related"),
            "direction": event.get("direction"),
            "impact_level": event.get("impact_level"),
            "confidence": event.get("confidence"),
        }
        async with semaphore:
            return await classify_news_with_llm(llm, event, fallback)

    classifications = await asyncio.gather(*[_classify_one(event) for event in deduped])
    deduped = [
        {
            **event,
            **classification,
            **news_weight_trace(event.get("source"), classification.get("category") or event.get("category")),
        }
        for event, classification in zip(deduped, classifications)
    ]
    top_news = await select_top_news_event(llm, deduped, asset)
    return LayerResult(
        layer="news",
        source="rss",
        data={"events": deduped, "top_news": top_news, "news_signal": _signal(deduped), "etf_flow": etf_flow},
        errors=errors,
    )
