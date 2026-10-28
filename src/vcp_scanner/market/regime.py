"""Broad market regime scoring kept separate from sector strength."""

from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd


def _latest_bool(data: pd.DataFrame | None, expression: str) -> bool | None:
    if data is None or data.empty:
        return None
    latest = data.iloc[-1]
    try:
        if expression == "above_ma20_ma50":
            return bool(latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"])
        if expression == "ma20_rising":
            clean = data["MA20"].dropna()
            return bool(len(clean) > 5 and clean.iloc[-1] > clean.iloc[-6])
    except Exception:
        return None
    return None


def calculate_market_regime(market_data: Dict[str, pd.DataFrame]) -> dict:
    """Return broad market regime without using sector ETFs as universal votes."""
    components: dict[str, object] = {}
    votes = 0
    available = 0

    for ticker in ("SPY", "QQQ", "IWM"):
        trend_ok = _latest_bool(market_data.get(ticker), "above_ma20_ma50")
        slope_ok = _latest_bool(market_data.get(ticker), "ma20_rising")
        components[f"{ticker} above MA20/50"] = "UNKNOWN" if trend_ok is None else trend_ok
        components[f"{ticker} MA20 rising"] = "UNKNOWN" if slope_ok is None else slope_ok
        if trend_ok is not None:
            available += 1
            votes += int(trend_ok)
        if slope_ok is not None:
            available += 1
            votes += int(slope_ok)

    vix_data = market_data.get("^VIX")
    vix_close = np.nan
    vix_ok = None
    if vix_data is not None and not vix_data.empty:
        vix_close = vix_data.iloc[-1].get("Close", np.nan)
        if pd.notna(vix_close):
            vix_ok = bool(vix_close < 22)
            available += 1
            votes += int(vix_ok)
    components["VIX below 22"] = "UNKNOWN" if vix_ok is None else vix_ok

    if available == 0:
        regime = "UNKNOWN"
        score = "NOT_AVAILABLE"
    else:
        ratio = votes / available
        if ratio >= 0.67:
            regime = "RISK_ON"
        elif ratio >= 0.4:
            regime = "MIXED"
        else:
            regime = "RISK_OFF"
        score = round(ratio * 100, 1)

    return {
        "Market Regime": regime,
        "Market Regime Score": score,
        "Market Regime Components": "; ".join(f"{key}: {value}" for key, value in components.items()),
    }

