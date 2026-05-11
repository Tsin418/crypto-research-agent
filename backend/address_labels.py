from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


LABEL_PATH = Path(__file__).resolve().parent.parent / "data" / "address_labels.json"


@lru_cache(maxsize=1)
def load_address_labels() -> dict:
    if not LABEL_PATH.exists():
        return {"ETH": {}, "BTC": {}}
    try:
        return json.loads(LABEL_PATH.read_text())
    except json.JSONDecodeError:
        return {"ETH": {}, "BTC": {}}


def get_address_label(asset: str, address: str | None) -> dict | None:
    if not address:
        return None
    labels = load_address_labels().get(asset, {})
    return labels.get(address.lower()) or labels.get(address)


def apply_transfer_labels(event: dict) -> dict:
    asset = event.get("asset")
    from_address = event.get("from_label")
    to_address = event.get("to_label")
    from_label = get_address_label(asset, from_address)
    to_label = get_address_label(asset, to_address)
    if from_label:
        event["from_label"] = from_label.get("label", from_address)
        event["from_label_type"] = from_label.get("type")
    if to_label:
        event["to_label"] = to_label.get("label", to_address)
        event["to_label_type"] = to_label.get("type")
    if to_label and to_label.get("type") == "exchange":
        event["direction"] = "potential_sell_pressure"
    elif from_label and from_label.get("type") == "exchange":
        event["direction"] = "accumulation_or_custody_outflow"
    return event
