from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


LABEL_PATH = Path(__file__).resolve().parent.parent / "data" / "address_labels.json"


@lru_cache(maxsize=1)
def load_address_labels() -> dict:
    if not LABEL_PATH.exists():
        return {}
    try:
        return json.loads(LABEL_PATH.read_text())
    except json.JSONDecodeError:
        return {}


def get_address_label(asset: str, address: str | None) -> dict | None:
    if not address:
        return None
    labels = load_address_labels()
    # Nested format: {"ETH": {"0x...": {...}}, "BTC": {"bc1...": {...}}}
    if asset in labels and isinstance(labels[asset], dict):
        return labels[asset].get(address.lower()) or labels[asset].get(address)
    # Flat format: {"0x...": {"label": "...", "entity_type": "...", "chain": "..."}}
    entry = labels.get(address.lower()) or labels.get(address)
    if isinstance(entry, dict):
        chain = str(entry.get("chain", "")).upper()
        if chain == asset.upper():
            return entry
    return None


def _entity_type(entry: dict | None) -> str | None:
    if not entry:
        return None
    return entry.get("entity_type") or entry.get("type")


def apply_transfer_labels(event: dict) -> dict:
    asset = event.get("asset")
    from_address = event.get("from_label")
    to_address = event.get("to_label")
    from_label = get_address_label(asset, from_address)
    to_label = get_address_label(asset, to_address)

    from_type = _entity_type(from_label)
    to_type = _entity_type(to_label)

    if from_label:
        event["from_label"] = from_label.get("label", from_address)
        event["from_entity_type"] = from_type
    if to_label:
        event["to_label"] = to_label.get("label", to_address)
        event["to_entity_type"] = to_type

    # Determine label coverage
    labels_available = sum([from_label is not None, to_label is not None])
    if labels_available == 2:
        event["entity_label_coverage"] = "full"
    elif labels_available == 1:
        event["entity_label_coverage"] = "partial"
    else:
        event["entity_label_coverage"] = "none"

    if to_type == "exchange" and from_type == "exchange":
        event["direction"] = "exchange_internal_transfer"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False
    elif to_type == "exchange" and from_type != "exchange":
        event["direction"] = "potential_sell_pressure"
        event["direction_confidence"] = "medium"
        event["direction_confirmed"] = True
        event["sell_pressure_evidence"] = True
    elif from_type == "exchange" and to_type != "exchange":
        event["direction"] = "accumulation_or_custody_outflow"
        event["direction_confidence"] = "medium"
        event["direction_confirmed"] = True
        event["sell_pressure_evidence"] = False
    elif to_type == "issuer" or from_type == "issuer" or to_type == "treasury" or from_type == "treasury":
        event["direction"] = "issuer_or_treasury_movement"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False
    elif to_type == "custody" or from_type == "custody":
        event["direction"] = "custodian_movement"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False
    elif to_type == "bridge" or from_type == "bridge":
        event["direction"] = "bridge_movement"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False
    elif from_label is None and to_label is None:
        event["direction"] = "unknown_transfer"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False
    else:
        event["direction"] = "large_transfer_with_partial_labels"
        event["direction_confidence"] = "low"
        event["direction_confirmed"] = False
        event["sell_pressure_evidence"] = False

    # Add a human-readable note about unconfirmed transfers
    if not event.get("direction_confirmed"):
        event["direction_note"] = "Direction unknown. Not evidence of sell pressure without confirmed wallet labels."

    return event
