from __future__ import annotations

from typing import Any


def _signal(layer: str, name: str, value: Any, direction: str, impact: str, confidence: float, severity: str | None = None) -> dict[str, Any]:
    return {
        "layer": layer,
        "signal_name": name,
        "signal_value": "" if value is None else str(value),
        "direction": direction,
        "severity": severity,
        "impact_level": impact,
        "confidence": confidence,
    }


def extract_normalized_signals(context, time_window: str = "24h") -> list[dict[str, Any]]:
    market = context.market.data
    derivatives = context.derivatives.data
    news = context.news.data
    onchain = context.onchain.data
    etf = context.etf.data if context.etf else {}
    macro = context.macro.data if context.macro else {}
    risk = context.risk
    signals: list[dict[str, Any]] = []

    # ===== Market 层 =====
    market_direction = "neutral"
    target_change = (
        market.get("price_change_4h_pct") if time_window == "4h"
        else market.get("price_change_7d_pct") if time_window == "7d"
        else market.get("price_change_24h_pct")
    )
    if target_change is not None:
        if target_change > 1:
            market_direction = "bullish"
        elif target_change < -1:
            market_direction = "bearish"
    signals.append(_signal("market", "market_signal", market.get("market_signal"), market_direction, "medium", 0.72))
    signals.append(_signal("market", "volume_ratio_vs_7d", market.get("volume_ratio_vs_7d"), "neutral", "medium", 0.66))

    # EMA 位置信号
    for period in (20, 50, 200):
        vs_ema = market.get(f"price_vs_ema{period}")
        if vs_ema and vs_ema != "unknown":
            direction = "bullish" if vs_ema == "above" else "bearish" if vs_ema == "below" else "neutral"
            signals.append(_signal("market", f"price_vs_ema{period}", vs_ema, direction, "low", 0.55))

    # Spot CVD 信号
    spot_bias = market.get("spot_flow_bias")
    if spot_bias and spot_bias != "unavailable":
        cvd_dir = "bullish" if spot_bias == "buy_pressure" else "bearish" if spot_bias == "sell_pressure" else "neutral"
        signals.append(_signal("market", "spot_flow_bias", spot_bias, cvd_dir, "medium", 0.55))
        cvd_4h = market.get("spot_cvd_approx_4h")
        if cvd_4h is not None:
            signals.append(_signal("market", "spot_cvd_approx_4h", f"{cvd_4h:,.0f}", cvd_dir, "low", 0.45))

    # ===== Derivatives 层 =====
    derivative_signal = derivatives.get("derivatives_signal")
    derivative_direction = "neutral"
    if derivative_signal in {"leverage_flush", "crowded_longs_under_pressure", "sentiment_flip_bearish"}:
        derivative_direction = "bearish"
    signals.append(_signal("derivatives", "derivatives_signal", derivative_signal, derivative_direction, "medium", 0.7))
    signals.append(_signal("derivatives", "funding_rate_now", derivatives.get("funding_rate_now"), "neutral", "medium", 0.65))
    signals.append(_signal("derivatives", "open_interest_change_24h_pct", derivatives.get("open_interest_change_24h_pct"), "neutral", "medium", 0.65))
    signals.append(_signal("derivatives", "put_call_ratio", derivatives.get("put_call_ratio"), "bearish" if (derivatives.get("put_call_ratio") or 0) >= 1.2 else "neutral", "medium", 0.62))

    # Put/Call Volume Ratio
    pc_vol = derivatives.get("put_call_volume_ratio")
    if pc_vol is not None:
        signals.append(_signal("derivatives", "put_call_volume_ratio", pc_vol, "bearish" if pc_vol >= 1.2 else "neutral", "medium", 0.62))

    signals.append(_signal("derivatives", "liquidation_bias", derivatives.get("liquidation_bias"), "bearish" if derivatives.get("liquidation_bias") == "long_flush" else "neutral", "medium", 0.66))

    # 清算事件笔数
    long_count = derivatives.get("long_liquidation_events_24h")
    short_count = derivatives.get("short_liquidation_events_24h")
    if long_count is not None or short_count is not None:
        signals.append(_signal("derivatives", "liquidation_events_24h", f"long={long_count or 0}, short={short_count or 0}", "neutral", "low", 0.52))

    # ===== News 层 =====
    for event in news.get("events", [])[:8]:
        signals.append(
            _signal(
                "news",
                event.get("category", "news_event"),
                event.get("title"),
                event.get("direction", "neutral"),
                event.get("impact_level", "low"),
                float(event.get("confidence") or 0.55),
            )
        )

    # ===== ETF 层 =====
    if etf:
        etf_latest = etf.get("btc_etf_net_flow_usd_m") or etf.get("net_flow_usd_m_latest")
        etf_dir = etf.get("flow_direction", "unavailable")
        if etf_latest is not None:
            sig_dir = "bullish" if etf_dir == "inflow" else "bearish" if etf_dir == "outflow" else "neutral"
            signals.append(_signal("etf_flow", "btc_etf_net_flow_usd_m", f"{etf_latest}M", sig_dir, "medium", 0.65))
        signals.append(_signal("etf_flow", "etf_flow_signal", etf.get("etf_flow_signal", "unavailable"), "neutral", "low", 0.5))
        if etf.get("flow_intensity"):
            signals.append(_signal("etf_flow", "flow_intensity", etf.get("flow_intensity"), "neutral", "low", 0.5))

    # ===== On-chain 层 =====
    onchain_signal = onchain.get("onchain_signal")
    onchain_direction = "neutral"
    if onchain_signal in {"exchange_inflow_pressure", "liquidity_contraction", "large_transfer_cluster"}:
        onchain_direction = "bearish"
    signals.append(_signal("onchain", "onchain_signal", onchain_signal, onchain_direction, "medium", 0.62))
    signals.append(_signal("onchain", "stablecoin_supply_change_24h", onchain.get("stablecoin_supply_change_24h"), "bearish" if (onchain.get("stablecoin_supply_change_24h") or 0) < 0 else "bullish" if (onchain.get("stablecoin_supply_change_24h") or 0) > 0 else "neutral", "medium", 0.68))

    # 链上证据质量
    evidence_quality = onchain.get("onchain_evidence_quality")
    if evidence_quality:
        signals.append(_signal("onchain", "onchain_evidence_quality", evidence_quality, "neutral", "low", 0.55))
    exchange_inflow_cnt = onchain.get("exchange_inflow_count")
    if exchange_inflow_cnt is not None:
        signals.append(_signal("onchain", "exchange_inflow_count", exchange_inflow_cnt, "bearish" if exchange_inflow_cnt > 0 else "neutral", "medium", 0.6))
    large_transfer_cnt = onchain.get("large_transfer_count")
    if large_transfer_cnt is not None:
        signals.append(_signal("onchain", "large_transfer_count", large_transfer_cnt, "neutral", "low", 0.52))

    # ===== Macro 层 =====
    if macro:
        macro_signal = macro.get("macro_signal", "unavailable")
        macro_dir = "bearish" if macro_signal in ("risk_off", "rates_pressure", "dollar_pressure") else "bullish" if macro_signal == "risk_on" else "neutral"
        signals.append(_signal("macro", "macro_signal", macro_signal, macro_dir, "high", 0.72))
        signals.append(_signal("macro", "macro_confidence", macro.get("macro_confidence", "low"), "neutral", "low", 0.55))

    # ===== Risk 层 =====
    signals.append(_signal("risk", "risk_score", risk.get("risk_score"), "neutral", "high", 0.86, severity=risk.get("risk_level", "neutral")))
    if risk.get("risk_confidence") is not None:
        signals.append(_signal("risk", "risk_confidence", risk.get("risk_confidence"), "neutral", "medium", 0.75))
    if risk.get("data_coverage"):
        signals.append(_signal("risk", "data_coverage", str(risk.get("data_coverage")), "neutral", "low", 0.60))
    for dim_name in ("liquidity_risk", "leverage_risk", "news_risk", "onchain_risk", "macro_risk"):
        dim_score = risk.get("risk_breakdown", {}).get(dim_name)
        if dim_score is not None:
            signals.append(_signal("risk", dim_name, dim_score, "neutral", "medium", 0.75))

    return signals
