from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any


ASSET_META = {
    "BTC": {
        "coingecko_id": "bitcoin",
        "coinpaprika_id": "btc-bitcoin",
        "symbol": "BTCUSDT",
        "name_terms": ("btc", "bitcoin"),
    },
    "ETH": {
        "coingecko_id": "ethereum",
        "coinpaprika_id": "eth-ethereum",
        "symbol": "ETHUSDT",
        "name_terms": ("eth", "ethereum", "ether"),
    },
}


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_now() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def iso_from_ms(ms: str | int | float | None) -> str | None:
    if ms in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(float(ms) / 1000, UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OSError):
        return None


def parse_feed_date(value: Any) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, str):
            dt = parsedate_to_datetime(value)
        else:
            dt = datetime(*value[:6], tzinfo=UTC)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def round_float(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def percent_change(now: float | None, past: float | None) -> float | None:
    if now is None or past in (None, 0):
        return None
    return round(((now - past) / past) * 100, 2)


def ema(values: list[float], period: int) -> float | None:
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    current = sum(values[:period]) / period
    for price in values[period:]:
        current = (price - current) * multiplier + current
    return round(current, 2)


def window_to_timedelta(window: str) -> timedelta:
    return {
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
    }.get(window, timedelta(hours=24))


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)
