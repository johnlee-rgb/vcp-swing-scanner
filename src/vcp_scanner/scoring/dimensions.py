"""Checkpoint 2 dimensional scores for leadership, setup, entry, sector, and data quality."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


NOT_AVAILABLE = "NOT_AVAILABLE"
UNKNOWN = "UNKNOWN"


def _latest(data: pd.DataFrame, column: str) -> float:
    if data is None or data.empty or column not in data:
        return np.nan
    value = data.iloc[-1].get(column, np.nan)
    return float(value) if pd.notna(value) else np.nan


def period_return(data: pd.DataFrame | None, days: int) -> float:
    if data is None or len(data) <= days or "Close" not in data:
        return np.nan
    latest = data["Close"].iloc[-1]
    prior = data["Close"].iloc[-days - 1]
    if pd.isna(latest) or pd.isna(prior) or prior == 0:
        return np.nan
    return float((latest / prior - 1) * 100)


def _score_from_return(value: float) -> float | None:
    if pd.isna(value):
        return None
    if value >= 25:
        return 100
    if value >= 15:
        return 85
    if value >= 5:
        return 70
    if value >= 0:
        return 55
    if value >= -10:
        return 35
    return 15


def _score_from_distance_from_high(distance_pct: float) -> float | None:
    if pd.isna(distance_pct):
        return None
    if distance_pct <= 5:
        return 100
    if distance_pct <= 10:
        return 85
    if distance_pct <= 20:
        return 65
    if distance_pct <= 35:
        return 40
    return 20


def _weighted_average(parts: list[tuple[float | None, float]]) -> float | str:
    valid = [(score, weight) for score, weight in parts if score is not None and pd.notna(score)]
    if not valid:
        return NOT_AVAILABLE
    total_weight = sum(weight for _, weight in valid)
    return round(sum(float(score) * weight for score, weight in valid) / total_weight, 1)


def score_leadership(
    data: pd.DataFrame,
    spy_data: pd.DataFrame | None,
    qqq_data: pd.DataFrame | None,
    sector_data: pd.DataFrame | None,
    rs_score: float,
    trend_score: int,
) -> dict:
    """Score stock leadership without using current entry timing."""
    returns = {
        "Return 1M %": period_return(data, 21),
        "Return 3M %": period_return(data, 63),
        "Return 6M %": period_return(data, 126),
        "Return 12M %": period_return(data, 252),
    }
    spy_spread = returns["Return 3M %"] - period_return(spy_data, 63)
    qqq_spread = returns["Return 3M %"] - period_return(qqq_data, 63)
    sector_spread = returns["Return 3M %"] - period_return(sector_data, 63)

    close = _latest(data, "Close")
    high52 = _latest(data, "High52W")
    distance_high = (high52 - close) / high52 * 100 if pd.notna(high52) and high52 else np.nan
    ma_structure_ok = bool(
        pd.notna(close)
        and close > _latest(data, "MA50")
        and _latest(data, "MA50") > _latest(data, "MA150")
        and _latest(data, "MA150") > _latest(data, "MA200")
    )
    higher_low = False
    if data is not None and len(data) >= 35:
        higher_low = bool(data["Low"].tail(10).min() > data["Low"].iloc[-25:-10].min())

    relative_parts = []
    for spread in (spy_spread, qqq_spread, sector_spread):
        if pd.notna(spread):
            relative_parts.append(100 if spread >= 10 else 80 if spread >= 3 else 55 if spread >= -3 else 25)
    relative_score = round(sum(relative_parts) / len(relative_parts), 1) if relative_parts else None

    score = _weighted_average(
        [
            ((rs_score / 10) * 100 if pd.notna(rs_score) else None, 0.30),
            (relative_score, 0.20),
            (_score_from_return(returns["Return 3M %"]), 0.15),
            (_score_from_return(returns["Return 6M %"]), 0.10),
            (_score_from_distance_from_high(distance_high), 0.10),
            ((trend_score / 7) * 100 if trend_score is not None else None, 0.10),
            (100 if ma_structure_ok else 35, 0.03),
            (100 if higher_low else 45, 0.02),
        ]
    )

    missing = []
    if pd.isna(spy_spread):
        missing.append("SPY relative return")
    if pd.isna(qqq_spread):
        missing.append("QQQ relative return")
    if pd.isna(sector_spread):
        missing.append("sector relative return")

    return {
        "Leadership Score": score,
        "Leadership Label": score_label(score),
        "RS vs SPY 3M %": round(spy_spread, 2) if pd.notna(spy_spread) else NOT_AVAILABLE,
        "RS vs QQQ 3M %": round(qqq_spread, 2) if pd.notna(qqq_spread) else NOT_AVAILABLE,
        "RS vs Sector 3M %": round(sector_spread, 2) if pd.notna(sector_spread) else NOT_AVAILABLE,
        **{key: round(value, 2) if pd.notna(value) else NOT_AVAILABLE for key, value in returns.items()},
        "Distance From 52W High %": round(distance_high, 2) if pd.notna(distance_high) else NOT_AVAILABLE,
        "MA Structure OK": "YES" if ma_structure_ok else "NO",
        "Higher Low Structure": "YES" if higher_low else "NO",
        "Leadership Missing Components": "; ".join(missing) if missing else "None",
    }


def score_setup_quality(
    data: pd.DataFrame,
    vcp_status: str,
    tightness_score: int,
    pivot_tests: int,
    volume_contraction: bool,
) -> dict:
    """Score generic setup quality separately from current entry timing."""
    range_tight = None
    atr_compression = None
    distribution_pressure = None
    support_quality = None

    if data is not None and len(data) >= 50:
        range_tight = bool(data["RangePct"].tail(5).mean() < data["RangePct"].iloc[-20:-5].mean())
        atr14 = _latest(data, "ATR14")
        atr50 = data["ATR14"].tail(50).mean() if "ATR14" in data else np.nan
        atr_compression = bool(pd.notna(atr14) and pd.notna(atr50) and atr14 < atr50)
        recent = data.tail(10)
        distribution_pressure = int(
            ((recent["Close"] < recent["Close"].shift(1)) & (recent["Volume"] > recent["AvgVol20"])).sum()
        )
        support_quality = float((data.tail(20)["Close"] > data.tail(20)["MA20"]).mean())

    score = _weighted_average(
        [
            ((tightness_score / 5) * 100 if tightness_score is not None else None, 0.25),
            (100 if vcp_status == "VALID VCP" else 75 if vcp_status == "EARLY VCP" else 45, 0.20),
            (100 if volume_contraction else 40, 0.15),
            (100 if range_tight else 45 if range_tight is not None else None, 0.10),
            (100 if atr_compression else 45 if atr_compression is not None else None, 0.10),
            (min(pivot_tests, 4) / 4 * 100 if pivot_tests is not None else None, 0.10),
            (100 if distribution_pressure is not None and distribution_pressure <= 1 else 40 if distribution_pressure is not None else None, 0.05),
            (support_quality * 100 if support_quality is not None else None, 0.05),
        ]
    )

    return {
        "Setup Quality Score": score,
        "Setup Quality Label": score_label(score),
        "ATR Compression": "YES" if atr_compression else "NO" if atr_compression is not None else NOT_AVAILABLE,
        "Range Contraction": "YES" if range_tight else "NO" if range_tight is not None else NOT_AVAILABLE,
        "Distribution Days 10D": distribution_pressure if distribution_pressure is not None else NOT_AVAILABLE,
        "Support Quality 20D %": round(support_quality * 100, 1) if support_quality is not None else NOT_AVAILABLE,
    }


def score_entry_quality(
    data: pd.DataFrame,
    setup_state: str,
    action: str,
    entry: float,
    stop: float,
    risk_pct: float,
    rr_ratio: float | None,
    volume_confirmation: str,
    stale_pivot: bool,
) -> dict:
    """Score whether the current entry is attractive right now."""
    if data is None or data.empty or pd.isna(entry) or entry <= 0:
        return {
            "Entry Quality Score": NOT_AVAILABLE,
            "Entry Quality Label": NOT_AVAILABLE,
            "Entry Quality Missing Components": "entry/data",
        }

    close = _latest(data, "Close")
    ma10 = _latest(data, "MA10")
    ma20 = _latest(data, "MA20")
    atr14 = _latest(data, "ATR14")
    distance_from_entry = (close - entry) / entry * 100 if pd.notna(close) else np.nan
    ma10_extension = (close - ma10) / ma10 * 100 if pd.notna(close) and pd.notna(ma10) and ma10 else np.nan
    ma20_extension = (close - ma20) / ma20 * 100 if pd.notna(close) and pd.notna(ma20) and ma20 else np.nan
    atr_extension = (close - ma10) / atr14 if pd.notna(close) and pd.notna(ma10) and pd.notna(atr14) and atr14 else np.nan

    risk_score = None
    if pd.notna(risk_pct):
        risk_score = 100 if risk_pct <= 6 else 85 if risk_pct <= 8 else 70 if risk_pct <= 10 else 45 if risk_pct <= 12 else 20
    distance_score = None
    if pd.notna(distance_from_entry):
        abs_distance = abs(distance_from_entry)
        distance_score = 100 if abs_distance <= 2 else 80 if abs_distance <= 5 else 45 if abs_distance <= 10 else 15
    extension_score = None
    if pd.notna(ma10_extension) and pd.notna(ma20_extension):
        max_extension = max(ma10_extension, ma20_extension)
        extension_score = 100 if max_extension <= 3 else 80 if max_extension <= 6 else 45 if max_extension <= 10 else 15
    state_score = {
        "READY_TO_TRIGGER": 90,
        "BREAKOUT_CONFIRMED": 85,
        "PULLBACK_ENTRY": 80,
        "BASE_BUILDING": 55,
        "EXTENDED": 20,
        "BREAKOUT_FAILED": 15,
        "FAILED": 5,
    }.get(setup_state, 45)
    rr_score = None
    if rr_ratio is not None and pd.notna(rr_ratio):
        rr_score = 100 if rr_ratio >= 2.5 else 85 if rr_ratio >= 2 else 60 if rr_ratio >= 1.5 else 25
    volume_score = 85 if volume_confirmation == "YES" else 45

    score = _weighted_average(
        [
            (risk_score, 0.25),
            (distance_score, 0.20),
            (extension_score, 0.20),
            (state_score, 0.15),
            (rr_score, 0.10),
            (volume_score, 0.10),
        ]
    )
    if stale_pivot and isinstance(score, (int, float)):
        score = min(score, 45.0)
    if action == "EXTENDED" and isinstance(score, (int, float)):
        score = min(score, 35.0)

    missing = []
    if rr_score is None:
        missing.append("structural RR")
    if pd.isna(ma10_extension) or pd.isna(ma20_extension):
        missing.append("MA extension")

    return {
        "Entry Quality Score": score,
        "Entry Quality Label": score_label(score),
        "Distance From Entry %": round(distance_from_entry, 2) if pd.notna(distance_from_entry) else NOT_AVAILABLE,
        "ATR Extension": round(atr_extension, 2) if pd.notna(atr_extension) else NOT_AVAILABLE,
        "Entry Quality Missing Components": "; ".join(missing) if missing else "None",
    }


def score_sector_leadership(sector_etf: str | None, sector_data: pd.DataFrame | None, sector_spread: float | None) -> dict:
    if not sector_etf:
        return {
            "Sector Leadership Status": UNKNOWN,
            "Sector Trend": UNKNOWN,
            "Sector Relative Performance": NOT_AVAILABLE,
        }
    if sector_data is None or sector_data.empty:
        return {
            "Sector Leadership Status": UNKNOWN,
            "Sector Trend": UNKNOWN,
            "Sector Relative Performance": NOT_AVAILABLE,
        }
    latest = sector_data.iloc[-1]
    trend_ok = bool(latest.get("Close", np.nan) > latest.get("MA20", np.nan) and latest.get("Close", np.nan) > latest.get("MA50", np.nan))
    if sector_spread is None or pd.isna(sector_spread):
        status = "SECTOR TREND OK" if trend_ok else "SECTOR WEAK"
    elif sector_spread >= 5 and trend_ok:
        status = "STOCK LEADING SECTOR"
    elif sector_spread <= -5:
        status = "STOCK LAGGING SECTOR"
    else:
        status = "SECTOR NEUTRAL"
    return {
        "Sector Leadership Status": status,
        "Sector Trend": "UP" if trend_ok else "DOWN",
        "Sector Relative Performance": round(sector_spread, 2) if sector_spread is not None and pd.notna(sector_spread) else NOT_AVAILABLE,
    }


def score_data_completeness(
    data: pd.DataFrame | None,
    benchmark_data: Dict[str, pd.DataFrame],
    sector_etf: str | None,
    sector_data: pd.DataFrame | None,
    market_cap: float | None,
    earnings_info: Dict[str, Any],
) -> dict:
    checks = {
        "OHLCV": data is not None and not data.empty and {"Open", "High", "Low", "Close", "Volume"}.issubset(data.columns),
        "benchmark data": any(benchmark_data.get(symbol) is not None and not benchmark_data.get(symbol).empty for symbol in ("SPY", "QQQ", "^HSI")),
        "sector mapping": bool(sector_etf),
        "sector history": sector_data is not None and not sector_data.empty,
        "market cap": market_cap is not None and pd.notna(market_cap),
        "earnings information": bool(earnings_info) and any(value not in (None, "N/A") for value in earnings_info.values()),
    }
    available = sum(1 for value in checks.values() if value)
    if available == len(checks):
        state = "COMPLETE"
    elif checks["OHLCV"] and available >= 3:
        state = "PARTIAL"
    else:
        state = "INSUFFICIENT"
    return {
        "Data Completeness": state,
        "Data Completeness Detail": "; ".join(f"{key}: {'YES' if value else 'NO'}" for key, value in checks.items()),
    }


def apply_rs_percentile(results: pd.DataFrame, min_count: int = 5) -> pd.DataFrame:
    output = results.copy()
    if output.empty or "RS Score" not in output or len(output) < min_count:
        output["RS Percentile"] = NOT_AVAILABLE
        return output
    rs_numeric = pd.to_numeric(output["RS Score"], errors="coerce")
    if rs_numeric.notna().sum() < min_count:
        output["RS Percentile"] = NOT_AVAILABLE
        return output
    output["RS Percentile"] = (rs_numeric.rank(pct=True) * 100).round(1).where(rs_numeric.notna(), NOT_AVAILABLE)
    return output


def score_label(score: float | str) -> str:
    if score == NOT_AVAILABLE or score == UNKNOWN or pd.isna(score):
        return NOT_AVAILABLE
    score = float(score)
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"
