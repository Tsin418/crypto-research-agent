from __future__ import annotations

import asyncio

from backend.config import Settings
from backend.snapshot_scan import SNAPSHOT_SCAN_TYPE, run_snapshot_scan
from backend.storage import Storage


async def safe_run_once(settings: Settings, storage: Storage) -> dict:
    assets = list(settings.snapshot_scheduler_assets)
    run_id = storage.start_scheduler_run(scan_type=SNAPSHOT_SCAN_TYPE, assets=assets)
    try:
        result = await run_snapshot_scan(settings, storage, assets)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        storage.complete_scheduler_run(run_id, status="failed", error_message=error)
        return {"status": "failed", "error": error}

    status = "completed" if result.get("status") == "completed" else "partial_failure"
    error_message = None
    if status != "completed":
        error_message = "; ".join(
            f"{item.get('asset')}: {item.get('errors')}"
            for item in result.get("results", [])
            if item.get("status") != "completed"
        )[:1000]
    storage.complete_scheduler_run(run_id, status=status, error_message=error_message)
    return result


async def run_snapshot_scheduler(settings: Settings, storage: Storage) -> None:
    if not settings.snapshot_scheduler_enabled:
        return

    interval_seconds = max(1, settings.snapshot_scheduler_interval_minutes) * 60
    if settings.snapshot_scheduler_run_on_startup:
        await safe_run_once(settings, storage)

    while True:
        await asyncio.sleep(interval_seconds)
        await safe_run_once(settings, storage)
