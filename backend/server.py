from __future__ import annotations

import asyncio
import hmac
import threading
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.compliance import REFUSAL_MARKDOWN, is_trading_advice_request
from backend.config import get_settings
from backend.data_onchain import normalize_alchemy_webhook
from backend.feishu import alchemy_ingest_summary, send_feishu_text
from backend.liquidations import run_bybit_liquidation_collector
from backend.models import ReportRequest
from backend.orchestrator import run_report_job
from backend.storage import Storage


SETTINGS = get_settings()
STORAGE = Storage(SETTINGS.db_path, SETTINGS.onchain_events_json_path)


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


async def _start_report_job(report_id: str, request: ReportRequest) -> None:
    await run_report_job(SETTINGS, STORAGE, report_id, request)


@asynccontextmanager
async def lifespan(_: FastAPI):
    _start_liquidation_collector()
    yield


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


def main() -> None:
    print(f"Crypto Research Agent FastAPI backend running on http://{SETTINGS.host}:{SETTINGS.port}")
    print(f"SQLite database: {SETTINGS.db_path}")
    print(f"On-chain JSON archive: {SETTINGS.onchain_events_json_path}")
    uvicorn.run("backend.server:app", host=SETTINGS.host, port=SETTINGS.port, reload=False)


if __name__ == "__main__":
    main()
