from __future__ import annotations

import httpx

from backend.config import Settings
from backend.http_client import get_json


BEACONCHAIN = "https://beaconcha.in/api/v1"


async def fetch_eth_staking_queue(client: httpx.AsyncClient, settings: Settings) -> tuple[dict, list[str]]:
    if not settings.beaconchain_api_key:
        return {}, ["beaconcha.in: BEACONCHAIN_API_KEY not configured"]
    headers = {"apikey": settings.beaconchain_api_key}
    data, error = await get_json(
        client,
        f"{BEACONCHAIN}/validators/queue",
        headers=headers,
        source="beaconchain_validators_queue",
    )
    if error:
        return {}, [error]
    if not isinstance(data, dict):
        return {}, ["beaconchain_validators_queue: empty response"]
    payload = data.get("data") if isinstance(data.get("data"), dict) else data.get("data") or {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    staking_inflow = payload.get("beaconchain_entering") or payload.get("entering") or payload.get("validatorscount")
    unstaking_queue = payload.get("beaconchain_exiting") or payload.get("exiting") or payload.get("validatorscount_exit")
    return {
        "eth_staking_queue": payload,
        "eth_staking_inflow": staking_inflow,
        "eth_unstaking_queue": unstaking_queue,
        "staking_source": "beaconcha_in_api",
    }, []
