from __future__ import annotations

from typing import Any

import httpx

from backend.config import Settings


def _truncate(text: str, limit: int = 1800) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n...truncated"


async def send_feishu_text(settings: Settings, text: str) -> bool:
    if not settings.feishu_webhook_url:
        return False
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": _truncate(text)},
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            response = await client.post(settings.feishu_webhook_url, json=payload)
            response.raise_for_status()
        return True
    except Exception:
        return False


def alchemy_ingest_summary(stored_events: list[dict[str, Any]]) -> str:
    total = sum(float(event.get("amount") or 0) for event in stored_events)
    hashes = [event.get("hash") for event in stored_events[:5] if event.get("hash")]
    lines = [
        "Alchemy on-chain webhook summary",
        f"Stored large ETH transfers: {len(stored_events)}",
        f"Total amount: {round(total, 4)} ETH",
    ]
    if hashes:
        lines.append("Sample tx hashes: " + ", ".join(hashes))
    return "\n".join(lines)


def report_summary(report_id: str, asset: str, risk_level: str, risk_score: int, markdown: str) -> str:
    first_lines = [line.strip() for line in markdown.splitlines() if line.strip()]
    preview = "\n".join(first_lines[:8])
    return "\n".join(
        [
            "Crypto research report completed",
            f"Report ID: {report_id}",
            f"Asset: {asset}",
            f"Risk: {risk_level} ({risk_score}/10)",
            "",
            preview,
        ]
    )
