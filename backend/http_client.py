from __future__ import annotations

import contextvars
import time
from typing import Any, Callable

import httpx


ApiCallRecorder = Callable[..., None]
_api_call_recorder: ApiCallRecorder | None = None
_current_report_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_report_id", default=None)


def is_http_forbidden_error(error: str | None) -> bool:
    if not error:
        return False
    lowered = error.lower()
    return "403" in lowered and "forbidden" in lowered


def set_api_call_recorder(recorder: ApiCallRecorder | None) -> None:
    global _api_call_recorder
    _api_call_recorder = recorder


def set_current_report_id(report_id: str | None):
    return _current_report_id.set(report_id)


def reset_current_report_id(token) -> None:
    _current_report_id.reset(token)


def record_api_call(source: str, url: str, status_code: int | None, latency_ms: int, error: str | None) -> None:
    _record_call(source, url, status_code, latency_ms, error)


def _record_call(source: str, url: str, status_code: int | None, latency_ms: int, error: str | None) -> None:
    if _api_call_recorder is None:
        return
    try:
        _api_call_recorder(
            provider=source.split(":", 1)[0],
            endpoint=url,
            status_code=status_code,
            latency_ms=latency_ms,
            error_message=error,
            report_id=_current_report_id.get(),
        )
    except Exception:
        return


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    source: str,
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    started = time.perf_counter()
    status_code: int | None = None
    headers = dict(headers) if headers else {}
    if "user-agent" not in {k.lower() for k in headers.keys()}:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        headers["Accept-Language"] = "en-US,en;q=0.9"
    try:
        response = await client.get(url, params=params, headers=headers, follow_redirects=True)
        status_code = response.status_code
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:
        error = f"{source}: {type(exc).__name__}: {str(exc)[:180]}"
        return None, error
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error_message = None
        if status_code is None or (status_code and status_code >= 400):
            error_message = f"HTTP status {status_code}" if status_code else "request failed"
        _record_call(source, url, status_code, latency_ms, error_message)


async def get_text(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    source: str,
) -> tuple[str | None, str | None]:
    started = time.perf_counter()
    status_code: int | None = None
    headers = dict(headers) if headers else {}
    if "user-agent" not in {k.lower() for k in headers.keys()}:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
        headers["Accept-Language"] = "en-US,en;q=0.9"
    try:
        response = await client.get(url, headers=headers, follow_redirects=True)
        status_code = response.status_code
        response.raise_for_status()
        return response.text, None
    except Exception as exc:
        error = f"{source}: {type(exc).__name__}: {str(exc)[:180]}"
        return None, error
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error_message = None
        if status_code is None or (status_code and status_code >= 400):
            error_message = f"HTTP status {status_code}" if status_code else "request failed"
        _record_call(source, url, status_code, latency_ms, error_message)


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    source: str,
) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    started = time.perf_counter()
    status_code: int | None = None
    headers = dict(headers) if headers else {}
    if "user-agent" not in {k.lower() for k in headers.keys()}:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        headers["Accept"] = "application/json,text/plain,*/*"
        headers["Accept-Language"] = "en-US,en;q=0.9"
    try:
        response = await client.post(url, json=json_body, headers=headers, follow_redirects=True)
        status_code = response.status_code
        response.raise_for_status()
        return response.json(), None
    except Exception as exc:
        error = f"{source}: {type(exc).__name__}: {str(exc)[:180]}"
        return None, error
    finally:
        latency_ms = int((time.perf_counter() - started) * 1000)
        error_message = None
        if status_code is None or (status_code and status_code >= 400):
            error_message = f"HTTP status {status_code}" if status_code else "request failed"
        _record_call(source, url, status_code, latency_ms, error_message)
