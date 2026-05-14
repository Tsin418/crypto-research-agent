from __future__ import annotations

from typing import Any

import httpx

from backend.address_labels import apply_transfer_labels
from backend.config import Settings
from backend.data_quality import layer_quality, metric_meta
from backend.data_liquidity import fetch_stablecoin_supply
from backend.data_staking import fetch_eth_staking_queue
from backend.http_client import get_json
from backend.models import LayerResult
from backend.utils import iso_from_ms, safe_float


ETHERSCAN = "https://api.etherscan.io/api"
MEMPOOL = "https://mempool.space/api"
SATOSHIS_PER_BTC = 100_000_000
WEI_PER_ETH = 1_000_000_000_000_000_000


def _event_id(source: str, event: dict[str, Any], index: int = 0) -> str:
    tx_hash = event.get("hash") or event.get("tx_hash") or "unknown"
    amount = event.get("amount") or "unknown"
    to_label = event.get("to_label") or "unknown"
    return f"{source}:{tx_hash}:{amount}:{to_label}:{index}"


def normalize_alchemy_webhook(payload: dict[str, Any], threshold_eth: int) -> list[dict[str, Any]]:
    """Normalize Alchemy Address Activity webhook payloads into transfer events."""
    event = payload.get("event", payload)
    activities = event.get("activity") or payload.get("activity") or []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(activities):
        asset = str(item.get("asset") or item.get("rawContract", {}).get("symbol") or "ETH").upper()
        if asset not in {"ETH", "WETH"}:
            continue
        amount = safe_float(item.get("value"))
        if amount is None:
            raw_value = item.get("rawContract", {}).get("value")
            try:
                amount = int(str(raw_value), 16) / WEI_PER_ETH if raw_value else None
            except (TypeError, ValueError):
                amount = None
        if amount is None or amount < threshold_eth:
            continue
        normalized.append(
            apply_transfer_labels({
                "amount": round(amount, 8),
                "asset": "ETH",
                "from_label": item.get("fromAddress") or item.get("from") or "unknown_address",
                "to_label": item.get("toAddress") or item.get("to") or "unknown_address",
                "timestamp": payload.get("createdAt") or event.get("createdAt"),
                "direction": "large_eth_transfer",
                "hash": item.get("hash") or item.get("transactionHash"),
                "source": "alchemy_webhook",
                "category": item.get("category"),
                "raw": item,
            })
        )
    return normalized


def _onchain_signal(asset: str, transfers: list[dict], stablecoin_supply_change: float | None) -> str:
    exchange_inflows = [tx for tx in transfers if tx.get("direction") == "potential_sell_pressure"]
    large_transfers = [
        tx for tx in transfers
        if tx.get("direction") in (
            "large_eth_transfer", "large_btc_transfer", "unknown_transfer",
            "large_transfer_with_partial_labels", "exchange_internal_transfer",
            "custodian_movement", "bridge_movement",
        )
    ]
    if len(exchange_inflows) >= 2:
        return "exchange_inflow_pressure"
    if len(large_transfers) >= 3:
        return "large_transfer_cluster"
    if large_transfers:
        return "large_transfer_activity"
    if stablecoin_supply_change is not None and stablecoin_supply_change < 0:
        return "liquidity_contraction"
    if asset == "ETH":
        return "eth_onchain_data_limited"
    return "btc_onchain_data_limited"


def _evidence_quality(transfers: list[dict], stablecoin_supply_change: float | None) -> dict[str, Any]:
    exchange_inflows = [tx for tx in transfers if tx.get("direction") == "potential_sell_pressure"]
    exchange_internal = [tx for tx in transfers if tx.get("direction") == "exchange_internal_transfer"]
    large_transfers = [
        tx for tx in transfers
        if tx.get("direction") in (
            "large_eth_transfer", "large_btc_transfer", "unknown_transfer",
            "large_transfer_with_partial_labels",
        )
    ]
    if len(exchange_inflows) >= 2:
        return {
            "onchain_evidence_quality": "strong",
            "onchain_primary_eligible": True,
            "exchange_inflow_count": len(exchange_inflows),
            "large_transfer_count": len(large_transfers),
            "exchange_internal_count": len(exchange_internal),
        }
    if len(exchange_inflows) == 1:
        return {
            "onchain_evidence_quality": "medium",
            "onchain_primary_eligible": False,
            "exchange_inflow_count": len(exchange_inflows),
            "large_transfer_count": len(large_transfers),
            "exchange_internal_count": len(exchange_internal),
        }
    if large_transfers:
        return {
            "onchain_evidence_quality": "weak",
            "onchain_primary_eligible": False,
            "exchange_inflow_count": 0,
            "large_transfer_count": len(large_transfers),
            "exchange_internal_count": len(exchange_internal),
        }
    if stablecoin_supply_change is not None and stablecoin_supply_change < 0:
        return {
            "onchain_evidence_quality": "medium",
            "onchain_primary_eligible": False,
            "exchange_inflow_count": 0,
            "large_transfer_count": 0,
            "exchange_internal_count": len(exchange_internal),
        }
    return {
        "onchain_evidence_quality": "unknown",
        "onchain_primary_eligible": False,
        "exchange_inflow_count": 0,
        "large_transfer_count": 0,
        "exchange_internal_count": len(exchange_internal),
    }


async def _etherscan_gas(client: httpx.AsyncClient, settings: Settings) -> tuple[dict | None, list[str]]:
    if not settings.etherscan_api_key:
        return None, ["etherscan: API key not configured"]
    data, error = await get_json(
        client,
        ETHERSCAN,
        params={"module": "gastracker", "action": "gasoracle", "apikey": settings.etherscan_api_key},
        source="etherscan_gas_oracle",
    )
    if error:
        return None, [error]
    if isinstance(data, dict):
        return data.get("result"), []
    return None, ["etherscan_gas_oracle: empty response"]


async def _etherscan_watch_address_transfers(
    client: httpx.AsyncClient,
    settings: Settings,
) -> tuple[list[dict], list[str]]:
    if not settings.etherscan_api_key or not settings.etherscan_watch_addresses:
        return [], []
    transfers: list[dict] = []
    errors: list[str] = []
    for address in settings.etherscan_watch_addresses[:20]:
        data, error = await get_json(
            client,
            ETHERSCAN,
            params={
                "module": "account",
                "action": "txlist",
                "address": address,
                "startblock": 0,
                "endblock": 99999999,
                "page": 1,
                "offset": 25,
                "sort": "desc",
                "apikey": settings.etherscan_api_key,
            },
            source="etherscan_txlist",
        )
        if error:
            errors.append(error)
            continue
        if not isinstance(data, dict) or not isinstance(data.get("result"), list):
            continue
        for tx in data["result"]:
            amount = safe_float(tx.get("value"))
            if amount is None:
                continue
            amount_eth = amount / WEI_PER_ETH
            if amount_eth < settings.eth_large_transfer_threshold_eth:
                continue
            transfers.append(
                apply_transfer_labels({
                    "amount": round(amount_eth, 8),
                    "asset": "ETH",
                    "from_label": tx.get("from") or "unknown_address",
                    "to_label": tx.get("to") or "unknown_address",
                    "timestamp": iso_from_ms(int(tx.get("timeStamp", 0)) * 1000),
                    "direction": "large_eth_transfer",
                    "hash": tx.get("hash"),
                    "source": "etherscan_watch_address",
                    "watched_address": address,
                })
            )
    return transfers, errors


async def _mempool_large_btc_transfers(client: httpx.AsyncClient, settings: Settings) -> tuple[list[dict], dict | None, list[str]]:
    errors: list[str] = []
    transfers: list[dict] = []
    mempool_state: dict | None = None
    state, error = await get_json(client, f"{MEMPOOL}/mempool", source="mempool_space_mempool")
    if error:
        errors.append(error)
    elif isinstance(state, dict):
        mempool_state = state

    blocks, error = await get_json(client, f"{MEMPOOL}/blocks", source="mempool_space_blocks")
    if error:
        errors.append(error)
        return transfers, mempool_state, errors
    if not isinstance(blocks, list):
        errors.append("mempool_space_blocks: empty response")
        return transfers, mempool_state, errors

    threshold_sats = settings.btc_large_transfer_threshold_btc * SATOSHIS_PER_BTC
    for block in blocks[: settings.btc_blocks_to_scan]:
        block_hash = block.get("id")
        if not block_hash:
            continue
        timestamp = iso_from_ms(int(block.get("timestamp", 0)) * 1000) if block.get("timestamp") else None
        for page in range(settings.btc_txs_per_block_page_limit):
            txs, error = await get_json(
                client,
                f"{MEMPOOL}/block/{block_hash}/txs/{page * 25}",
                source="mempool_space_block_txs",
            )
            if error:
                errors.append(error)
                break
            if not isinstance(txs, list) or not txs:
                break
            for tx in txs:
                vin = tx.get("vin") or []
                if vin and vin[0].get("is_coinbase"):
                    continue
                for vout_index, output in enumerate(tx.get("vout") or []):
                    value = output.get("value")
                    if not isinstance(value, int) or value < threshold_sats:
                        continue
                    transfers.append(
                        apply_transfer_labels({
                            "amount": round(value / SATOSHIS_PER_BTC, 8),
                            "asset": "BTC",
                            "from_label": "unknown_input_cluster",
                            "to_label": output.get("scriptpubkey_address") or output.get("scriptpubkey_type") or "unknown_output",
                            "timestamp": timestamp,
                            "direction": "large_btc_transfer",
                            "hash": tx.get("txid"),
                            "source": "mempool_space_block_scan",
                            "block_height": block.get("height"),
                            "vout_index": vout_index,
                        })
                    )
            if len(transfers) >= 50:
                return transfers, mempool_state, errors
    return transfers, mempool_state, errors


async def fetch_onchain(settings: Settings, asset: str, storage: Any | None = None) -> LayerResult:
    errors: list[str] = []
    gas: dict | None = None
    btc_mempool: dict | None = None
    stablecoins: dict = {}
    staking: dict = {}
    transfers: list[dict] = []

    if asset == "ETH" and storage is not None:
        transfers.extend(storage.get_recent_onchain_events("ETH", limit=50))

    async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
        stablecoins, stable_errors = await fetch_stablecoin_supply(client)
        errors.extend(stable_errors)
        if asset == "ETH":
            gas, gas_errors = await _etherscan_gas(client, settings)
            errors.extend(gas_errors)
            watched, watch_errors = await _etherscan_watch_address_transfers(client, settings)
            errors.extend(watch_errors)
            transfers.extend(watched)
            staking, staking_errors = await fetch_eth_staking_queue(client, settings)
            errors.extend(staking_errors)
        elif asset == "BTC":
            btc_transfers, btc_mempool, btc_errors = await _mempool_large_btc_transfers(client, settings)
            errors.extend(btc_errors)
            transfers.extend(btc_transfers)

    quality = _evidence_quality(transfers, stablecoins.get("stablecoin_supply_change_24h"))
    evidence_quality = quality.get("onchain_evidence_quality")
    quality_warnings = [
        "Exchange netflow is unavailable; transfer direction uses limited address labels.",
        "Stablecoin supply change is a liquidity proxy, not direct buying pressure.",
        "Exchange-to-exchange transfers are internal/venue flow with low attribution confidence.",
        "Issuer or treasury movements are not direct buying pressure.",
        "Do not describe unknown wallet transfers as confirmed whale selling without labeled exchange destination.",
    ]
    if evidence_quality in {"weak", "unknown", None}:
        quality_warnings.append("Unknown transfers are low confidence and should not be described as confirmed whale intent.")
    if errors:
        quality_warnings.append("Some on-chain providers failed or returned incomplete data.")
    data = {
        "asset": asset,
        "exchange_netflow_24h": None,
        "exchange_netflow_7d": None,
        "large_transfers": transfers[:50],
        "large_transfer_threshold": (
            f">= {settings.eth_large_transfer_threshold_eth} ETH"
            if asset == "ETH"
            else f">= {settings.btc_large_transfer_threshold_btc} BTC"
        ),
        "miner_net_position_change": None,
        "stablecoin_supply_change_24h": stablecoins.get("stablecoin_supply_change_24h"),
        "stablecoin_supply_change_7d": stablecoins.get("stablecoin_supply_change_7d"),
        "stablecoin_supply_usd": stablecoins.get("stablecoin_supply_usd"),
        "stablecoins": stablecoins.get("stablecoin_assets"),
        "eth_gas_oracle": gas,
        "btc_mempool": btc_mempool,
        "eth_staking_inflow": staking.get("eth_staking_inflow"),
        "eth_unstaking_queue": staking.get("eth_unstaking_queue"),
        "eth_staking_queue": staking.get("eth_staking_queue"),
        "restaking_related_event": None,
        "onchain_signal": _onchain_signal(asset, transfers, stablecoins.get("stablecoin_supply_change_24h")),
        **quality,
        "note": "ETH/EVM large transfers use Alchemy webhook events plus optional Etherscan watch addresses. BTC large transfers use mempool.space latest block scans.",
    }
    data["data_quality"] = layer_quality(
        freshness="fresh" if transfers or stablecoins else "unknown",
        confidence={"strong": "high", "medium": "medium", "weak": "low", "unknown": "low"}.get(evidence_quality, "low"),
        methodology="Large-transfer scan plus stablecoin supply proxy; address-label coverage is limited and exchange netflow is unavailable.",
        warnings=quality_warnings,
    )
    data["stablecoin_supply_change_24h_meta"] = metric_meta(
        methodology="DeFiLlama stablecoin supply delta used as a broad liquidity proxy.",
        confidence=0.55 if stablecoins.get("stablecoin_supply_change_24h") is not None else 0.2,
        source="defillama_stablecoins",
        warning="Stablecoin supply proxy, not direct buying pressure.",
    )
    data["exchange_inflow_count_meta"] = metric_meta(
        methodology="Counts only transfers classified as potential sell pressure by available local labels and rules.",
        confidence=0.5 if quality.get("exchange_inflow_count") else 0.25,
        source="local_address_labels_and_transfer_rules",
        warning="Limited label coverage; unknown transfers remain low confidence.",
    )
    return LayerResult(layer="onchain", source="etherscan/alchemy_webhooks/mempool.space", data=data, errors=errors)
