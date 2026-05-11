from __future__ import annotations

import json
import re
import time
from typing import Any

import httpx

from backend.config import Settings
from backend.http_client import record_api_call


class DeepSeekClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def available(self) -> bool:
        return bool(self.settings.deepseek_api_key)

    async def chat(self, system: str, user: str, *, temperature: float = 0.1) -> str | None:
        if not self.available:
            return None
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        started = time.perf_counter()
        status_code: int | None = None
        error_message: str | None = None
        try:
            async with httpx.AsyncClient(timeout=self.settings.http_timeout_seconds) as client:
                response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers=headers,
                    json=payload,
                )
                status_code = response.status_code
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            error_message = f"deepseek: {type(exc).__name__}: {str(exc)[:180]}"
            return None
        finally:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_api_call("deepseek", "https://api.deepseek.com/chat/completions", status_code, latency_ms, error_message)

    async def json_chat(self, system: str, user: str) -> dict[str, Any] | None:
        content = await self.chat(system, user, temperature=0.0)
        if not content:
            return None
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if not match:
                return None
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
