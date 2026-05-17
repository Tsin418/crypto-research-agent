from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Asset = Literal["BTC", "ETH"]
Mode = Literal["event_attribution", "state_scan", "risk_watch"]


DISCLAIMER = (
    "This report is for research and educational purposes only. It is not "
    "financial advice, investment advice, or a recommendation to buy, sell, "
    "or hold any asset. Crypto assets are highly volatile, and users should "
    "make independent decisions based on their own research and risk tolerance."
)


class ReportRequest(BaseModel):
    query: str = Field(min_length=1)
    asset: Asset | None = None
    time_window: str | None = None


class AutoScanRequest(BaseModel):
    assets: list[Asset] = Field(default_factory=lambda: ["BTC", "ETH"])
    time_window: str = "4h"
    force_refresh: bool = False


class MarketScanRequest(BaseModel):
    assets: list[Asset] = Field(default_factory=lambda: ["BTC", "ETH"])
    force_refresh: bool = False


class MarketScanRecord(BaseModel):
    asset: Asset
    price_now: float | None = None
    price_change_4h_pct: float | None = None
    direction: Literal["rising", "falling", "neutral"]
    direction_label_zh: Literal["上涨", "下跌", "震荡"]
    created_at: str


class Intent(BaseModel):
    asset: Asset
    mode: Mode
    time_window: str = "24h"
    user_intent: str


class LayerResult(BaseModel):
    layer: str
    source: str
    data: dict[str, Any]
    errors: list[str] = Field(default_factory=list)


class ResearchContext(BaseModel):
    request: ReportRequest
    intent: Intent
    market: LayerResult
    derivatives: LayerResult
    news: LayerResult
    onchain: LayerResult
    etf: LayerResult | None = None
    macro: LayerResult | None = None
    risk: dict[str, Any]
    attribution: dict[str, Any]


class StoredReport(BaseModel):
    report_id: str
    status: Literal["processing", "completed", "failed"]
    user_query: str
    asset: str | None = None
    mode: str | None = None
    time_window: str | None = None
    report_markdown: str | None = None
    risk_score: int | None = None
    risk_level: str | None = None
    price_now: float | None = None
    price_change_4h_pct: float | None = None
    price_change_24h_pct: float | None = None
    direction: str | None = None
    direction_label_zh: str | None = None
    trigger_reason: str | None = None
    top_news_title: str | None = None
    top_news_url: str | None = None
    top_news_source: str | None = None
    top_news_json: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str
