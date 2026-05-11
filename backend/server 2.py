from __future__ import annotations

import asyncio
import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from backend.compliance import REFUSAL_MARKDOWN, is_trading_advice_request
from backend.config import get_settings
from backend.data_onchain import normalize_alchemy_webhook
from backend.models import ReportRequest
from backend.liquidations import run_bybit_liquidation_collector
from backend.orchestrator import run_report_job
from backend.storage import Storage


SETTINGS = get_settings()
STORAGE = Storage(SETTINGS.db_path)


def _json_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)



def _is_authorized_webhook(handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> bool:
    secret = SETTINGS.alchemy_webhook_secret
    if not secret:
        return True
    header_secret = handler.headers.get("X-Webhook-Secret", "")
    auth = handler.headers.get("Authorization", "")
    query_secret = query.get("secret", [""])[0]
    return header_secret == secret or auth == f"Bearer {secret}" or query_secret == secret


def _handle_alchemy_webhook(handler: BaseHTTPRequestHandler, parsed) -> None:
    query = parse_qs(parsed.query)
    if not _is_authorized_webhook(handler, query):
        _send_json(handler, 401, {"error": "unauthorized webhook"})
        return
    try:
        payload = _json_body(handler)
    except json.JSONDecodeError as exc:
        _send_json(handler, 400, {"error": "invalid json", "details": str(exc)})
        return
    events = normalize_alchemy_webhook(payload, SETTINGS.eth_large_transfer_threshold_eth)
    for index, event in enumerate(events):
        event_id = f"alchemy:{event.get('hash') or 'unknown'}:{event.get('amount')}:{index}"
        STORAGE.save_onchain_event(event_id, "ETH", "alchemy_webhook", event)
    _send_json(handler, 202, {"status": "accepted", "stored_events": len(events)})

def _start_liquidation_collector() -> None:
    if not SETTINGS.bybit_liquidation_collector_enabled:
        return

    def runner() -> None:
        asyncio.run(run_bybit_liquidation_collector(STORAGE))

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


def _start_job(report_id: str, request: ReportRequest) -> None:
    def runner() -> None:
        asyncio.run(run_report_job(SETTINGS, STORAGE, report_id, request))

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()


class Handler(BaseHTTPRequestHandler):
    server_version = "CryptoResearchAgent/0.1"

    def do_OPTIONS(self) -> None:
        _send_json(self, 200, {"ok": True})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/health":
            _send_json(self, 200, {"status": "ok"})
            return

        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["api", "research", "report"]:
            report = STORAGE.get_report(parts[3])
            if report is None:
                _send_json(self, 404, {"error": "report not found"})
                return
            _send_json(self, 200, report.model_dump())
            return

        if len(parts) == 5 and parts[:3] == ["api", "research", "report"] and parts[4] == "data":
            report = STORAGE.get_report(parts[3])
            if report is None:
                _send_json(self, 404, {"error": "report not found"})
                return
            _send_json(
                self,
                200,
                {
                    "report_id": parts[3],
                    "snapshots": STORAGE.get_snapshots(parts[3]),
                    "normalized_signals": STORAGE.get_normalized_signals(parts[3]),
                    "api_call_logs": STORAGE.get_api_call_logs(parts[3]),
                },
            )
            return

        _send_json(self, 404, {"error": "not found"})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/api/webhooks/alchemy":
            _handle_alchemy_webhook(self, parsed)
            return
        if path != "/api/research/report":
            _send_json(self, 404, {"error": "not found"})
            return
        try:
            request = ReportRequest(**_json_body(self))
        except (ValidationError, json.JSONDecodeError) as exc:
            _send_json(self, 400, {"error": "invalid request", "details": str(exc)})
            return

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
            _send_json(self, 200, {"report_id": report_id, "status": "completed", "refused": True})
            return
        _start_job(report_id, request)
        _send_json(self, 202, {"report_id": report_id, "status": "processing"})

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    _start_liquidation_collector()
    server = ThreadingHTTPServer((SETTINGS.host, SETTINGS.port), Handler)
    print(f"Crypto Research Agent backend running on http://{SETTINGS.host}:{SETTINGS.port}")
    print(f"SQLite database: {SETTINGS.db_path}")
    server.serve_forever()


if __name__ == "__main__":
    main()
