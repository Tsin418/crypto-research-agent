from __future__ import annotations

import asyncio
import hmac
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.auto_scan import run_auto_scan, stored_report_payload
from backend.compliance import REFUSAL_MARKDOWN, is_trading_advice_request
from backend.config import get_settings
from backend.data_market import fetch_4h_market_snapshot
from backend.data_onchain import normalize_alchemy_webhook
from backend.feishu import alchemy_ingest_summary, send_feishu_text
from backend.liquidations import run_bybit_liquidation_collector
from backend.models import AutoScanRequest, MarketScanRecord, MarketScanRequest, ReportRequest
from backend.orchestrator import run_report_job
from backend.scheduler import run_snapshot_scheduler
from backend.storage import Storage
from backend.utils import iso_now


SETTINGS = get_settings()
STORAGE = Storage(SETTINGS.db_path, SETTINGS.onchain_events_json_path)
_snapshot_scheduler_task: asyncio.Task | None = None


def _is_authorized_webhook(
    *,
    query_secret: str | None,
    header_secret: str | None,
    authorization: str | None,
) -> bool:
    secret = SETTINGS.alchemy_webhook_secret
    if not secret:
        return True
    candidates = (
        header_secret or "",
        authorization or "",
        f"Bearer {query_secret or ''}",
        query_secret or "",
    )
    expected = (secret, f"Bearer {secret}")
    return any(hmac.compare_digest(candidate, value) for candidate in candidates for value in expected)


def _start_liquidation_collector() -> None:
    if not SETTINGS.bybit_liquidation_collector_enabled:
        return

    def runner() -> None:
        asyncio.run(run_bybit_liquidation_collector(STORAGE))

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def _start_snapshot_scheduler() -> None:
    global _snapshot_scheduler_task
    if not SETTINGS.snapshot_scheduler_enabled or _snapshot_scheduler_task is not None:
        return
    _snapshot_scheduler_task = asyncio.create_task(run_snapshot_scheduler(SETTINGS, STORAGE))


async def _start_report_job(report_id: str, request: ReportRequest) -> None:
    await run_report_job(SETTINGS, STORAGE, report_id, request)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _is_market_scan_cache_fresh(scan: MarketScanRecord | None) -> bool:
    created_at = _parse_iso(scan.created_at if scan else None)
    if created_at is None:
        return False
    ttl = timedelta(minutes=SETTINGS.market_scan_cache_ttl_minutes)
    return datetime.now(UTC) - created_at <= ttl


async def _get_or_create_market_scan(asset: str, force_refresh: bool) -> MarketScanRecord:
    cached = STORAGE.get_latest_market_scan(asset)
    if cached is not None and not force_refresh and _is_market_scan_cache_fresh(cached):
        return cached

    snapshot = await fetch_4h_market_snapshot(SETTINGS, asset)
    data = snapshot.data
    if data.get("price_now") is None or data.get("price_change_4h_pct") is None:
        detail = "; ".join(snapshot.errors) or f"{asset} market data unavailable"
        raise HTTPException(status_code=502, detail=detail)

    return STORAGE.save_market_scan(
        asset=asset,
        price_now=data.get("price_now"),
        price_change_4h_pct=data.get("price_change_4h_pct"),
        direction=data.get("direction") or "neutral",
        direction_label_zh=data.get("direction_label_zh") or "震荡",
        raw_json={"source": snapshot.source, "data": data, "errors": snapshot.errors},
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _start_liquidation_collector()
    _start_snapshot_scheduler()
    try:
        yield
    finally:
        if _snapshot_scheduler_task is not None:
            _snapshot_scheduler_task.cancel()


app = FastAPI(title="Crypto Research Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Webhook-Secret"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "Crypto Research Agent API",
        "dashboard": "Open the Vite frontend URL, not the backend API root.",
    }


@app.post("/api/webhooks/alchemy", status_code=202)
async def alchemy_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    secret: str | None = None,
    x_webhook_secret: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    if not _is_authorized_webhook(
        query_secret=secret,
        header_secret=x_webhook_secret,
        authorization=authorization,
    ):
        raise HTTPException(status_code=401, detail="unauthorized webhook")
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid json: {exc}") from exc

    events = normalize_alchemy_webhook(payload, SETTINGS.eth_large_transfer_threshold_eth)
    for index, event in enumerate(events):
        event_id = f"alchemy:{event.get('hash') or 'unknown'}:{event.get('amount')}:{index}"
        STORAGE.save_onchain_event(event_id, "ETH", "alchemy_webhook", event)

    if events and SETTINGS.feishu_webhook_url:
        background_tasks.add_task(send_feishu_text, SETTINGS, alchemy_ingest_summary(events))
    return {
        "status": "accepted",
        "stored_events": len(events),
        "json_archive": str(SETTINGS.onchain_events_json_path),
    }


@app.post("/api/research/report", status_code=202)
async def create_report(request: ReportRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    report_id = str(uuid.uuid4())
    STORAGE.create_report(report_id, request.query)
    if is_trading_advice_request(request.query):
        STORAGE.complete_report(
            report_id,
            asset=request.asset or "UNKNOWN",
            mode="refusal",
            time_window=request.time_window or "n/a",
            report_markdown=REFUSAL_MARKDOWN,
            risk_score=0,
            risk_level="n/a",
        )
        return {"report_id": report_id, "status": "completed", "refused": True}
    background_tasks.add_task(_start_report_job, report_id, request)
    return {"report_id": report_id, "status": "processing"}


@app.post("/api/research/auto-scan")
async def auto_scan(request: AutoScanRequest) -> dict[str, Any]:
    return await run_auto_scan(SETTINGS, STORAGE, request)


@app.post("/api/research/market-scan")
async def market_scan(request: MarketScanRequest) -> dict[str, Any]:
    assets = request.assets or ["BTC", "ETH"]
    results = []
    for asset in assets:
        scan = await _get_or_create_market_scan(asset, request.force_refresh)
        results.append(scan.model_dump())
    return {"generated_at": iso_now(), "results": results}


@app.get("/api/research/market-scans")
async def list_market_scans(asset: str | None = None, limit: int = 20) -> dict[str, Any]:
    if asset is not None and asset not in {"BTC", "ETH"}:
        raise HTTPException(status_code=400, detail="asset must be BTC or ETH")
    scans = STORAGE.list_market_scans(asset, limit)
    return {"results": [scan.model_dump() for scan in scans]}


@app.get("/api/research/source-health")
async def source_health(lookback_hours: int = 24) -> dict[str, Any]:
    lookback_hours = max(1, min(lookback_hours, 168))
    return {
        "generated_at": iso_now(),
        "lookback_hours": lookback_hours,
        "sources": STORAGE.get_source_health(lookback_hours),
    }


@app.get("/api/research/reports")
async def list_reports(asset: str | None = None, limit: int = 20) -> dict[str, Any]:
    if asset is not None and asset not in {"BTC", "ETH"}:
        raise HTTPException(status_code=400, detail="asset must be BTC or ETH")
    reports = STORAGE.list_reports(asset, limit)
    return {"reports": [report.model_dump() for report in reports]}


@app.get("/api/research/latest")
async def latest_report(asset: str = "BTC") -> dict[str, Any]:
    if asset not in {"BTC", "ETH"}:
        raise HTTPException(status_code=400, detail="asset must be BTC or ETH")
    report = STORAGE.get_latest_report(asset, "4h") or STORAGE.get_latest_report(asset)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return stored_report_payload(report)


@app.get("/api/research/report/{report_id}")
async def get_report(report_id: str):
    report = STORAGE.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return report


@app.get("/api/research/report/{report_id}/data")
async def get_report_data(report_id: str) -> dict[str, Any]:
    report = STORAGE.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {
        "report_id": report_id,
        "snapshots": STORAGE.get_snapshots(report_id),
        "normalized_signals": STORAGE.get_normalized_signals(report_id),
        "api_call_logs": STORAGE.get_api_call_logs(report_id),
    }


@app.get("/api/research/report/{report_id}/trace")
async def get_report_trace(report_id: str) -> dict[str, Any]:
    report = STORAGE.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    snapshots = STORAGE.get_snapshots(report_id)
    attribution = snapshots.get("attribution", {}).get("data", {})
    payload = attribution.get("data", attribution)
    return {
        "report_id": report_id,
        "attribution_trace": payload.get("attribution_trace", []),
        "trace_summary": payload.get("trace_summary", {}),
        "data_quality": payload.get("data_quality", {}),
        "alternative_explanations": payload.get("alternative_explanations", []),
    }


def main() -> None:
    print(f"Crypto Research Agent FastAPI backend running on http://{SETTINGS.host}:{SETTINGS.port}")
    print(f"SQLite database: {SETTINGS.db_path}")
    print(f"On-chain JSON archive: {SETTINGS.onchain_events_json_path}")
    uvicorn.run("backend.server:app", host=SETTINGS.host, port=SETTINGS.port, reload=False)


if __name__ == "__main__":
    main()
