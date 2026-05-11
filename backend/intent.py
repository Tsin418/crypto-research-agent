from __future__ import annotations

import json
import re

from backend.llm import DeepSeekClient
from backend.models import Intent, ReportRequest


def _heuristic_intent(request: ReportRequest) -> Intent:
    text = request.query.lower()
    asset = request.asset
    if asset is None:
        if re.search(r"\beth\b|ethereum|ether", text):
            asset = "ETH"
        else:
            asset = "BTC"

    if any(term in text for term in ("risk", "watch", "注意", "风险")):
        mode = "risk_watch"
    elif any(term in text for term in ("state", "current", "scan", "现在", "当前", "状态")):
        mode = "state_scan"
    else:
        mode = "event_attribution"

    if request.time_window:
        time_window = request.time_window
    elif any(term in text for term in ("刚刚", "sudden", "just now", "1h")):
        time_window = "1h"
    elif re.search(r"(?<!\d)4\s*h\b|(?<!\d)4\s+hours?\b", text):
        time_window = "4h"
    elif re.search(r"(?<!\d)7\s*d\b", text) or "week" in text or "一周" in text:
        time_window = "7d"
    else:
        time_window = "24h"

    return Intent(
        asset=asset,
        mode=mode,
        time_window=time_window,
        user_intent=request.query[:120],
    )


async def parse_intent(request: ReportRequest, llm: DeepSeekClient) -> Intent:
    fallback = _heuristic_intent(request)
    system = (
        "You are an intent parser for a BTC/ETH crypto research assistant. "
        "Return JSON only with asset, mode, time_window, user_intent. "
        "asset must be BTC or ETH. mode must be event_attribution, state_scan, or risk_watch."
    )
    user = json.dumps(
        {
            "query": request.query,
            "asset_hint": request.asset,
            "time_window_hint": request.time_window,
        },
        ensure_ascii=True,
    )
    parsed = await llm.json_chat(system, user)
    if not parsed:
        return fallback
    try:
        return Intent(**{**fallback.model_dump(), **parsed})
    except Exception:
        return fallback
