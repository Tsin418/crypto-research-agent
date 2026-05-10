from __future__ import annotations

import httpx

from backend.http_client import get_json
from backend.utils import round_float, safe_float


DERIBIT = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"


def _option_type(instrument_name: str) -> str | None:
    if instrument_name.endswith("-P"):
        return "put"
    if instrument_name.endswith("-C"):
        return "call"
    return None


async def fetch_deribit_put_call(client: httpx.AsyncClient, asset: str) -> tuple[dict, list[str]]:
    data, error = await get_json(
        client,
        DERIBIT,
        params={"currency": asset, "kind": "option"},
        source="deribit_options_summary",
    )
    if error:
        return {}, [error]
    if not isinstance(data, dict) or not isinstance(data.get("result"), list):
        return {}, ["deribit_options_summary: empty response"]

    put_oi = call_oi = put_volume = call_volume = 0.0
    for row in data["result"]:
        option_type = _option_type(str(row.get("instrument_name", "")))
        if option_type is None:
            continue
        open_interest = safe_float(row.get("open_interest")) or 0.0
        volume = safe_float(row.get("volume")) or 0.0
        if option_type == "put":
            put_oi += open_interest
            put_volume += volume
        else:
            call_oi += open_interest
            call_volume += volume

    return {
        "put_open_interest": round_float(put_oi, 4),
        "call_open_interest": round_float(call_oi, 4),
        "put_call_ratio": round_float(put_oi / call_oi if call_oi else None, 4),
        "put_volume": round_float(put_volume, 4),
        "call_volume": round_float(call_volume, 4),
        "put_call_volume_ratio": round_float(put_volume / call_volume if call_volume else None, 4),
        "options_source": "deribit_public_api",
    }, []
