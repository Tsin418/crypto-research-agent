from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    if load_dotenv is not None:
        load_dotenv(ROOT_DIR / ".env")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _tuple_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    values = tuple(item.strip().upper() for item in raw.split(",") if item.strip())
    return values or default


@dataclass(frozen=True)
class Settings:
    deepseek_api_key: str
    deepseek_model: str
    coingecko_api_key: str
    coingecko_plan: str
    coinalyze_api_key: str
    bybit_api_key: str
    bybit_api_secret: str
    binance_api_key: str
    binance_api_secret: str
    etherscan_api_key: str
    etherscan_watch_addresses: tuple[str, ...]
    alchemy_webhook_secret: str
    eth_large_transfer_threshold_eth: int
    btc_large_transfer_threshold_btc: int
    btc_blocks_to_scan: int
    btc_txs_per_block_page_limit: int
    beaconchain_api_key: str
    bybit_liquidation_collector_enabled: bool
    feishu_webhook_url: str
    onchain_events_json_path: Path
    host: str
    port: int
    db_path: Path
    http_timeout_seconds: int
    price_4h_up_threshold_pct: float
    price_4h_down_threshold_pct: float
    market_scan_cache_ttl_minutes: int
    report_cache_ttl_minutes: int
    snapshot_scheduler_enabled: bool
    snapshot_scheduler_interval_minutes: int
    snapshot_scheduler_assets: tuple[str, ...]
    snapshot_scheduler_run_on_startup: bool


def get_settings() -> Settings:
    _load_dotenv()
    db_path = Path(os.getenv("DB_PATH", "./data/research_agent.sqlite3"))
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    onchain_events_json_path = Path(os.getenv("ONCHAIN_EVENTS_JSON_PATH", "./data/onchain_events.jsonl"))
    if not onchain_events_json_path.is_absolute():
        onchain_events_json_path = ROOT_DIR / onchain_events_json_path
    watch_addresses = tuple(
        item.strip()
        for item in os.getenv("ETHERSCAN_WATCH_ADDRESSES", "").split(",")
        if item.strip()
    )
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        coingecko_api_key=os.getenv("COINGECKO_API_KEY", ""),
        coingecko_plan=os.getenv("COINGECKO_PLAN", "demo"),
        coinalyze_api_key=os.getenv("COINALYZE_API_KEY", ""),
        bybit_api_key=os.getenv("BYBIT_API_KEY", ""),
        bybit_api_secret=os.getenv("BYBIT_API_SECRET", ""),
        binance_api_key=os.getenv("BINANCE_API_KEY", ""),
        binance_api_secret=os.getenv("BINANCE_API_SECRET", ""),
        etherscan_api_key=os.getenv("ETHERSCAN_API_KEY", ""),
        etherscan_watch_addresses=watch_addresses,
        alchemy_webhook_secret=os.getenv("ALCHEMY_WEBHOOK_SECRET", ""),
        eth_large_transfer_threshold_eth=_int_env("ETH_LARGE_TRANSFER_THRESHOLD_ETH", 500),
        btc_large_transfer_threshold_btc=_int_env("BTC_LARGE_TRANSFER_THRESHOLD_BTC", 100),
        btc_blocks_to_scan=_int_env("BTC_BLOCKS_TO_SCAN", 3),
        btc_txs_per_block_page_limit=_int_env("BTC_TXS_PER_BLOCK_PAGE_LIMIT", 4),
        beaconchain_api_key=os.getenv("BEACONCHAIN_API_KEY", ""),
        bybit_liquidation_collector_enabled=_bool_env("BYBIT_LIQUIDATION_COLLECTOR_ENABLED", True),
        feishu_webhook_url=os.getenv("FEISHU_WEBHOOK_URL", ""),
        onchain_events_json_path=onchain_events_json_path,
        host=os.getenv("HOST", "127.0.0.1"),
        port=_int_env("PORT", 8000),
        db_path=db_path,
        http_timeout_seconds=_int_env("HTTP_TIMEOUT_SECONDS", 12),
        price_4h_up_threshold_pct=_float_env("PRICE_4H_UP_THRESHOLD_PCT", 1.0),
        price_4h_down_threshold_pct=_float_env("PRICE_4H_DOWN_THRESHOLD_PCT", -1.0),
        market_scan_cache_ttl_minutes=_int_env("MARKET_SCAN_CACHE_TTL_MINUTES", 2),
        report_cache_ttl_minutes=_int_env("REPORT_CACHE_TTL_MINUTES", 15),
        snapshot_scheduler_enabled=_bool_env("SNAPSHOT_SCHEDULER_ENABLED", False),
        snapshot_scheduler_interval_minutes=_int_env("SNAPSHOT_SCHEDULER_INTERVAL_MINUTES", 2),
        snapshot_scheduler_assets=_tuple_env("SNAPSHOT_SCHEDULER_ASSETS", ("BTC", "ETH")),
        snapshot_scheduler_run_on_startup=_bool_env("SNAPSHOT_SCHEDULER_RUN_ON_STARTUP", False),
    )
