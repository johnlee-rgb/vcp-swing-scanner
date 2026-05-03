"""VCP Swing Scanner.

Practical end-of-day Streamlit scanner for US swing-trading preparation.
The app uses daily yfinance data only. It is designed around VCP / J Law /
Minervini-style routines: scan a focused universe, filter weak names, score
trend and timing separately, then produce a next-day trade plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf


PRESET_UNIVERSES = {
    "AI / Semiconductor": [
        "NVDA",
        "AMD",
        "AVGO",
        "MU",
        "WDC",
        "SMCI",
        "VRT",
        "ANET",
        "ARM",
        "NVTS",
        "MRVL",
        "TXN",
        "INTC",
        "TSM",
        "ASML",
        "LRCX",
        "KLAC",
        "AMAT",
        "ON",
        "MPWR",
        "MCHP",
        "QCOM",
        "ADI",
        "NXPI",
        "TER",
        "COHR",
        "AEHR",
    ],
    "AI Infrastructure / Power": [
        "VST",
        "CEG",
        "NRG",
        "ETN",
        "PWR",
        "GEV",
        "ABB",
        "SI",
        "HUBB",
        "EME",
        "FIX",
        "POWL",
        "BE",
        "FLNC",
        "CLS",
        "DELL",
        "HPE",
        "MOD",
        "ATKR",
        "AYI",
        "GNRC",
        "WCC",
        "APG",
    ],
    "Cloud / Software": [
        "MSFT",
        "ORCL",
        "CRM",
        "NOW",
        "ADBE",
        "SNOW",
        "DDOG",
        "NET",
        "MDB",
        "TEAM",
        "WDAY",
        "INTU",
        "SHOP",
        "HUBS",
        "ZS",
        "ESTC",
        "CFLT",
        "PATH",
        "DOCN",
        "BILL",
        "APP",
        "PLTR",
        "FROG",
        "GTLB",
    ],
    "Cybersecurity": [
        "PANW",
        "CRWD",
        "ZS",
        "FTNT",
        "OKTA",
        "S",
        "NET",
        "CHKP",
        "CYBR",
        "TENB",
        "QLYS",
        "RPD",
        "VRNS",
        "GEN",
        "SAIL",
        "IOT",
        "AKAM",
        "OSPN",
        "RDWR",
        "BB",
    ],
    "Data Center / Networking": [
        "ANET",
        "VRT",
        "SMCI",
        "DELL",
        "HPE",
        "CSCO",
        "JNPR",
        "NTAP",
        "WDC",
        "STX",
        "PSTG",
        "GLW",
        "CIEN",
        "LITE",
        "COHR",
        "CLS",
        "FN",
        "APH",
        "TEL",
        "ARW",
        "SNX",
        "JBL",
    ],
    "Robotics / Automation": [
        "ISRG",
        "TER",
        "ROK",
        "AME",
        "EMR",
        "HON",
        "ABB",
        "SYM",
        "ZBRA",
        "CGNX",
        "IRBT",
        "HLX",
        "PATH",
        "TRMB",
        "DE",
        "CAT",
        "PCAR",
        "ETN",
        "PH",
        "DOV",
    ],
    "Nuclear / Uranium": [
        "CCJ",
        "CEG",
        "VST",
        "BWXT",
        "LEU",
        "SMR",
        "OKLO",
        "UEC",
        "UUUU",
        "DNN",
        "NXE",
        "URG",
        "LTBR",
        "NNE",
        "FLR",
        "J",
        "GEV",
        "PWR",
        "NEE",
        "SO",
    ],
    "Energy / Oil & Gas": [
        "XOM",
        "CVX",
        "OXY",
        "SLB",
        "HAL",
        "APA",
        "MPC",
        "DVN",
        "COP",
        "EOG",
        "FANG",
        "PR",
        "MTDR",
        "CHRD",
        "PBF",
        "VLO",
        "PSX",
        "LBRT",
        "HP",
        "NBR",
        "KMI",
        "WMB",
        "LNG",
        "AR",
        "RRC",
        "TALO",
        "CNX",
    ],
    "Defense / Aerospace": [
        "RTX",
        "LMT",
        "NOC",
        "GD",
        "BA",
        "HWM",
        "TDG",
        "HEI",
        "AXON",
        "KTOS",
        "AVAV",
        "TXT",
        "LHX",
        "LDOS",
        "HII",
        "CW",
        "MRCY",
        "SPR",
        "ACHR",
        "JOBY",
    ],
    "Financials / Fintech": [
        "JPM",
        "BAC",
        "WFC",
        "C",
        "GS",
        "MS",
        "SCHW",
        "BLK",
        "AXP",
        "V",
        "MA",
        "PYPL",
        "SQ",
        "COIN",
        "HOOD",
        "SOFI",
        "AFRM",
        "NU",
        "UPST",
        "ALLY",
        "ICE",
        "CME",
    ],
    "Biotech / Healthcare Growth": [
        "LLY",
        "NVO",
        "REGN",
        "VRTX",
        "ISRG",
        "TMO",
        "DHR",
        "BSX",
        "SYK",
        "MDT",
        "DXCM",
        "IDXX",
        "ALNY",
        "EXAS",
        "MRNA",
        "BMRN",
        "ARGX",
        "HALO",
        "INSM",
        "VEEV",
    ],
    "Consumer Growth": [
        "AMZN",
        "TSLA",
        "NFLX",
        "META",
        "UBER",
        "DASH",
        "RBLX",
        "MELI",
        "CAVA",
        "CMG",
        "SHAK",
        "LULU",
        "DECK",
        "ELF",
        "ULTA",
        "NKE",
        "SBUX",
        "BKNG",
        "ABNB",
        "SPOT",
        "DUOL",
        "SE",
    ],
    "Industrials / Infrastructure": [
        "CAT",
        "DE",
        "URI",
        "PWR",
        "EME",
        "FIX",
        "ETN",
        "HUBB",
        "PH",
        "ITW",
        "DOV",
        "GEV",
        "J",
        "FLR",
        "VMC",
        "MLM",
        "EXP",
        "TEX",
        "AGCO",
        "WCC",
        "APG",
        "GVA",
    ],
    "Crypto / Blockchain Stocks": [
        "COIN",
        "HOOD",
        "MSTR",
        "MARA",
        "RIOT",
        "CLSK",
        "IREN",
        "CIFR",
        "HUT",
        "BTDR",
        "WULF",
        "BITF",
        "CORZ",
        "CAN",
        "HIVE",
        "GLXY",
        "PYPL",
        "SQ",
        "IBKR",
        "BKKT",
    ],
    "Growth Leaders": [
        "TSLA",
        "META",
        "MSFT",
        "AAPL",
        "AMZN",
        "NFLX",
        "SHOP",
        "SNOW",
        "PANW",
        "CRWD",
        "PLTR",
        "APP",
        "NOW",
        "DDOG",
        "NET",
        "COIN",
        "HOOD",
        "RBLX",
        "UBER",
        "DASH",
    ],
}

MARKET_LEADERS_BASE = [
    "NVDA",
    "MSFT",
    "AAPL",
    "AMZN",
    "META",
    "GOOGL",
    "GOOG",
    "AVGO",
    "TSLA",
    "BRK-B",
    "JPM",
    "LLY",
    "V",
    "MA",
    "NFLX",
    "ORCL",
    "COST",
    "HD",
    "WMT",
    "PLTR",
    "AMD",
    "CRM",
    "NOW",
    "ADBE",
    "PANW",
    "CRWD",
    "APP",
    "COIN",
    "HOOD",
    "UBER",
    "SHOP",
    "SNOW",
    "DDOG",
    "NET",
    "ANET",
    "VRT",
    "SMCI",
    "DELL",
    "MU",
    "ARM",
    "MRVL",
    "LRCX",
    "KLAC",
    "AMAT",
    "ASML",
    "TSM",
    "QCOM",
    "TXN",
    "INTC",
    "VST",
    "CEG",
    "GEV",
    "ETN",
    "PWR",
    "HUBB",
    "EME",
    "FIX",
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "SLB",
    "HAL",
    "MPC",
    "VLO",
    "PSX",
    "LNG",
    "RTX",
    "LMT",
    "NOC",
    "GD",
    "BA",
    "HWM",
    "TDG",
    "AXON",
    "AVAV",
    "BAC",
    "WFC",
    "GS",
    "MS",
    "SCHW",
    "AXP",
    "PYPL",
    "SQ",
    "SOFI",
    "NU",
    "NVO",
    "REGN",
    "VRTX",
    "ISRG",
    "TMO",
    "DHR",
    "BSX",
    "SYK",
    "DXCM",
    "MELI",
    "CAVA",
    "CMG",
    "LULU",
    "DECK",
    "ELF",
    "BKNG",
    "ABNB",
    "SPOT",
    "DUOL",
    "CAT",
    "DE",
    "URI",
    "PH",
    "ITW",
    "VMC",
    "MLM",
    "CCJ",
    "BWXT",
    "LEU",
    "OKLO",
    "SMR",
    "MSTR",
    "MARA",
    "RIOT",
    "CLSK",
    "IREN",
]

for ticker_list in PRESET_UNIVERSES.values():
    for symbol in ticker_list:
        if symbol not in MARKET_LEADERS_BASE:
            MARKET_LEADERS_BASE.append(symbol)

PRESET_UNIVERSES["Market Leaders 300"] = MARKET_LEADERS_BASE[:300]

SCAN_MODES = [
    "AI / Semiconductor",
    "AI Infrastructure / Power",
    "Cloud / Software",
    "Cybersecurity",
    "Data Center / Networking",
    "Robotics / Automation",
    "Nuclear / Uranium",
    "Energy / Oil & Gas",
    "Defense / Aerospace",
    "Financials / Fintech",
    "Biotech / Healthcare Growth",
    "Consumer Growth",
    "Industrials / Infrastructure",
    "Crypto / Blockchain Stocks",
    "Market Leaders 300",
    "Custom Input",
]

SECTOR_ETFS_BY_MODE = {
    "AI / Semiconductor": ["SMH", "XLK"],
    "AI Infrastructure / Power": ["XLU", "XLK"],
    "Cloud / Software": ["XLK", "QQQ"],
    "Cybersecurity": ["XLK", "QQQ"],
    "Data Center / Networking": ["XLK", "SMH"],
    "Robotics / Automation": ["XLI", "XLK"],
    "Nuclear / Uranium": ["XLU", "XLE"],
    "Energy / Oil & Gas": ["XLE"],
    "Defense / Aerospace": ["ITA", "XLI"],
    "Financials / Fintech": ["XLF", "QQQ"],
    "Biotech / Healthcare Growth": ["XLV", "IBB"],
    "Consumer Growth": ["XLY", "QQQ"],
    "Industrials / Infrastructure": ["XLI"],
    "Crypto / Blockchain Stocks": ["QQQ", "XLF"],
    "Growth Leaders": ["QQQ", "XLK"],
    "Market Leaders 300": ["QQQ", "SPY"],
    "Custom Input": ["SPY"],
}

SECTOR_ETF_BY_TICKER: Dict[str, str] = {}
for universe_name, universe_tickers in PRESET_UNIVERSES.items():
    primary_etf = SECTOR_ETFS_BY_MODE.get(universe_name, ["SPY"])[0]
    for symbol in universe_tickers:
        SECTOR_ETF_BY_TICKER.setdefault(symbol, primary_etf)

MARKET_TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "SMH",
    "XLK",
    "XLE",
    "XLF",
    "XLV",
    "XLU",
    "XLI",
    "XLY",
    "IBB",
    "ITA",
    "^VIX",
]
ACTION_ORDER = {"READY": 0, "PULLBACK ENTRY": 1, "WATCH": 2, "EXTENDED": 3, "FAILED": 4}


@dataclass
class PivotInfo:
    """Resistance and breakout information for one ticker."""

    pivot: float
    distance_pct: float
    trigger: float
    label: str
    tests: int


@dataclass
class VcpInfo:
    """Contraction summary used for VCP classification and chart labels."""

    status: str
    count: int
    contractions: List[float]
    final_pct: float | None
    volume_contraction: bool
    label_points: List[dict]


def normalize_tickers(raw_tickers: str) -> List[str]:
    """Parse comma, space, or newline-separated tickers into clean symbols."""
    raw = raw_tickers.replace("\n", ",").replace(" ", ",")
    tickers = [ticker.strip().upper() for ticker in raw.split(",")]
    return sorted({ticker for ticker in tickers if ticker})


def format_large_number(value: float | int | None) -> str:
    """Display market cap and dollar volume in compact human-readable form."""
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


@st.cache_data(ttl=60 * 30, show_spinner=False)
def download_daily_data(tickers: Tuple[str, ...], period: str = "18mo") -> Dict[str, pd.DataFrame]:
    """Download daily OHLCV data and return one cleaned DataFrame per ticker."""
    if not tickers:
        return {}

    raw = yf.download(
        list(tickers),
        period=period,
        interval="1d",
        auto_adjust=False,
        group_by="ticker",
        progress=False,
        threads=True,
    )

    data: Dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            frame = raw[ticker].copy() if isinstance(raw.columns, pd.MultiIndex) else raw.copy()
        except (KeyError, TypeError):
            continue

        frame = frame.rename(columns=str.title)
        usable_columns = [column for column in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if column in frame]
        if "Close" not in usable_columns:
            continue

        frame = frame[usable_columns].dropna(subset=["Close"])
        if not frame.empty:
            frame.index = pd.to_datetime(frame.index)
            data[ticker] = frame

    return data


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def download_market_caps(tickers: Tuple[str, ...]) -> Dict[str, float | None]:
    """Fetch market caps from yfinance and tolerate missing metadata."""
    caps: Dict[str, float | None] = {}
    for ticker in tickers:
        try:
            fast_info = yf.Ticker(ticker).fast_info
            caps[ticker] = getattr(fast_info, "market_cap", None) or fast_info.get("marketCap")
        except Exception:
            caps[ticker] = None
    return caps


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def download_next_earnings_dates(tickers: Tuple[str, ...]) -> Dict[str, str | None]:
    """Fetch the next known earnings date and tolerate missing calendar data."""
    earnings_dates: Dict[str, str | None] = {}
    today = pd.Timestamp.today().normalize()

    for ticker in tickers:
        next_date: pd.Timestamp | None = None
        try:
            earnings = yf.Ticker(ticker).get_earnings_dates(limit=8)
            if earnings is not None and not earnings.empty:
                dates = pd.to_datetime(earnings.index).tz_localize(None).normalize()
                future_dates = [date for date in dates if date >= today]
                next_date = min(future_dates) if future_dates else None
        except Exception:
            next_date = None

        earnings_dates[ticker] = next_date.strftime("%Y-%m-%d") if next_date is not None else None

    return earnings_dates


def add_indicators(frame: pd.DataFrame, spy_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add moving averages, RSI, ATR, volume, ranges, and relative strength."""
    data = frame.copy()
    close = data["Close"]

    for window in (10, 20, 50, 150, 200):
        data[f"MA{window}"] = close.rolling(window).mean()

    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = losses.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    data["RSI14"] = 100 - (100 / (1 + rs))

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - previous_close).abs(),
            (data["Low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["ATR14"] = true_range.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()

    data["AvgVol20"] = data["Volume"].rolling(20).mean()
    data["AvgVol50"] = data["Volume"].rolling(50).mean()
    data["AvgDollarVol50"] = (data["Close"] * data["Volume"]).rolling(50).mean()
    data["High52W"] = data["High"].rolling(252, min_periods=120).max()
    data["Low52W"] = data["Low"].rolling(252, min_periods=120).min()
    data["High20"] = data["High"].rolling(20).max()
    data["Low10"] = data["Low"].rolling(10).min()
    data["RangePct"] = (data["High"] - data["Low"]) / data["Close"]

    if spy_frame is not None and not spy_frame.empty:
        spy_close = spy_frame["Close"].reindex(data.index).ffill()
        data["RSLine"] = close / spy_close
        data["RSSlope30"] = data["RSLine"].pct_change(30) * 100
    else:
        data["RSLine"] = np.nan
        data["RSSlope30"] = np.nan

    return data


def is_rising(series: pd.Series, lookback: int = 5) -> bool:
    """Return True when the latest value is above the value several sessions ago."""
    clean = series.dropna()
    if len(clean) <= lookback:
        return False
    return bool(clean.iloc[-1] > clean.iloc[-lookback - 1])


def latest_value(data: pd.DataFrame, column: str) -> float:
    """Safely read the latest numeric value from an indicator column."""
    value = data.iloc[-1].get(column, np.nan)
    return float(value) if pd.notna(value) else np.nan


def period_return(data: pd.DataFrame | None, days: int) -> float:
    """Return percentage performance over a trading-day lookback."""
    if data is None or len(data) <= days:
        return np.nan
    latest = data["Close"].iloc[-1]
    prior = data["Close"].iloc[-days - 1]
    if pd.isna(latest) or pd.isna(prior) or prior == 0:
        return np.nan
    return float((latest / prior - 1) * 100)


def calculate_market_score(market_data: Dict[str, pd.DataFrame]) -> Tuple[int, str, List[str]]:
    """Score broad conditions using SPY, QQQ, SMH, and VIX."""
    score = 0
    details: List[str] = []

    for ticker in ("SPY", "QQQ", "SMH"):
        data = market_data.get(ticker)
        if data is None or data.empty:
            details.append(f"{ticker}: no data")
            continue
        latest = data.iloc[-1]
        passes = bool(latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"])
        score += int(passes)
        details.append(f"{ticker} {'above' if passes else 'not above'} MA20/MA50")

    vix_data = market_data.get("^VIX")
    if vix_data is not None and not vix_data.empty:
        vix = latest_value(vix_data, "Close")
        vix_passes = bool(vix < 20)
        score += int(vix_passes)
        details.append(f"VIX {vix:.1f} {'below' if vix_passes else 'at/above'} 20")
    else:
        details.append("VIX: no data")

    if score >= 3:
        status = "BULLISH"
    elif score == 2:
        status = "NEUTRAL"
    else:
        status = "RISKY"

    return score, status, details


def calculate_sector_score(mode: str, market_data: Dict[str, pd.DataFrame]) -> Tuple[int, str]:
    """Score the relevant sector ETF basket for the chosen scan mode."""
    etfs = SECTOR_ETFS_BY_MODE.get(mode, ["SPY"])
    per_etf_scores: List[int] = []
    notes: List[str] = []

    for etf in etfs:
        data = market_data.get(etf)
        if data is None or data.empty:
            notes.append(f"{etf}: no data")
            continue

        latest = data.iloc[-1]
        etf_score = 0
        if latest["Close"] > latest["MA20"]:
            etf_score += 1
        if latest["Close"] > latest["MA50"]:
            etf_score += 1
        if latest.get("RSSlope30", np.nan) > 0:
            etf_score += 1

        per_etf_scores.append(etf_score)
        notes.append(f"{etf}: {etf_score}/3")

    return (max(per_etf_scores) if per_etf_scores else 0), " | ".join(notes)


def score_trend(data: pd.DataFrame) -> Tuple[int, List[str]]:
    """Minervini-style trend template score, max 7."""
    latest = data.iloc[-1]
    score = 0
    notes: List[str] = []

    if latest["Close"] > latest["MA50"] and latest["Close"] > latest["MA150"] and latest["Close"] > latest["MA200"]:
        score += 1
        notes.append("Price above MA50/150/200")
    if latest["MA50"] > latest["MA150"] and latest["MA50"] > latest["MA200"]:
        score += 1
        notes.append("MA50 leadership")
    if latest["MA150"] > latest["MA200"]:
        score += 1
        notes.append("MA150 above MA200")
    if is_rising(data["MA200"], lookback=20):
        score += 1
        notes.append("MA200 rising")
    if latest["Close"] >= latest["Low52W"] * 1.25:
        score += 1
        notes.append("25% above 52-week low")
    if latest["Close"] >= latest["High52W"] * 0.75:
        score += 1
        notes.append("Within 25% of 52-week high")
    if latest.get("RSSlope30", np.nan) > 0:
        score += 1
        notes.append("RS improving vs SPY")

    return score, notes


def has_higher_low_structure(data: pd.DataFrame) -> bool:
    """Approximate recent higher lows across the last 10 to 20 trading days."""
    if len(data) < 35:
        return False
    recent_low = data["Low"].tail(10).min()
    prior_low = data["Low"].iloc[-25:-10].min()
    return bool(recent_low > prior_low)


def has_volume_contraction(data: pd.DataFrame) -> bool:
    """Compare the latest 10-day volume against the previous 10-day volume."""
    if len(data) < 25:
        return False
    latest_10 = data["Volume"].tail(10).mean()
    previous_10 = data["Volume"].iloc[-20:-10].mean()
    return bool(latest_10 < previous_10)


def has_tight_range(data: pd.DataFrame) -> bool:
    """Check whether the latest 5-day range is tighter than the prior 10 days."""
    if len(data) < 16:
        return False
    return bool(data["RangePct"].tail(5).mean() < data["RangePct"].iloc[-15:-5].mean())


def detect_pivot(data: pd.DataFrame) -> PivotInfo:
    """Find a practical resistance pivot over the last 20 to 60 sessions."""
    lookback = data.tail(60).copy()
    latest_close = latest_value(data, "Close")

    if len(lookback) < 20 or pd.isna(latest_close):
        pivot = latest_value(data, "High20")
        return PivotInfo(pivot, np.nan, pivot * 1.001, "Insufficient data", 0)

    # Use closes to avoid one-day wick extremes, but allow legitimate highs when tested.
    close_candidate = float(lookback["Close"].iloc[:-1].max())
    high_candidate = float(lookback["High"].iloc[:-1].max())
    high_day = lookback["High"].iloc[:-1].idxmax()
    after_high = lookback.loc[high_day:].head(4)
    immediate_reversal = bool((after_high["Close"] < high_candidate * 0.94).any())
    pivot = close_candidate if immediate_reversal else max(close_candidate, high_candidate)

    tests = int(((lookback["High"] >= pivot * 0.985) & (lookback["High"] <= pivot * 1.015)).sum())
    if tests < 2:
        tested_closes = lookback["Close"].iloc[:-1].nlargest(min(5, len(lookback) - 1))
        pivot = float(tested_closes.median())
        tests = int((lookback["Close"] >= pivot * 0.985).sum())

    distance_pct = (pivot - latest_close) / latest_close * 100
    if latest_close > pivot:
        label = "Breakout in progress"
    elif distance_pct <= 3:
        label = "Near pivot"
    else:
        label = "Building below pivot"

    return PivotInfo(
        pivot=round(pivot, 2),
        distance_pct=round(distance_pct, 2),
        trigger=round(pivot * 1.001, 2),
        label=label,
        tests=tests,
    )


def find_swing_points(data: pd.DataFrame, lookback: int = 60, width: int = 2) -> List[dict]:
    """Detect simple swing highs and lows from recent daily bars."""
    recent = data.tail(lookback)
    points: List[dict] = []

    for index in range(width, len(recent) - width):
        window = recent.iloc[index - width : index + width + 1]
        row = recent.iloc[index]
        date = recent.index[index]

        if row["High"] == window["High"].max():
            points.append({"type": "H", "date": date, "price": float(row["High"]), "volume": float(row["Volume"])})
        if row["Low"] == window["Low"].min():
            points.append({"type": "L", "date": date, "price": float(row["Low"]), "volume": float(row["Volume"])})

    return points


def detect_vcp(data: pd.DataFrame, pivot: PivotInfo) -> VcpInfo:
    """Classify VCP quality from shrinking swing high-to-low contractions."""
    points = find_swing_points(data)
    contractions: List[float] = []
    label_points: List[dict] = []

    last_high: dict | None = None
    for point in points:
        if point["type"] == "H":
            last_high = point
        elif point["type"] == "L" and last_high and point["date"] > last_high["date"]:
            drawdown = (last_high["price"] - point["price"]) / last_high["price"] * 100
            if 2 <= drawdown <= 45:
                contractions.append(round(drawdown, 1))
                label_points.append(
                    {
                        "date": point["date"],
                        "price": point["price"],
                        "text": f"{drawdown:.1f}%",
                    }
                )
                last_high = None

    contractions = contractions[-4:]
    label_points = label_points[-4:]
    count = len(contractions)
    decreasing = count >= 2 and all(later < earlier for earlier, later in zip(contractions, contractions[1:]))
    latest_smaller = count >= 2 and contractions[-1] < contractions[-2]
    volume_contraction = has_volume_contraction(data)
    above_ma50_ratio = float((data.tail(60)["Close"] > data.tail(60)["MA50"]).mean()) if len(data) >= 60 else 0
    near_pivot = pivot.distance_pct <= 5 or pivot.label == "Breakout in progress"
    final_pct = contractions[-1] if contractions else None

    if count >= 2 and decreasing and volume_contraction and near_pivot and above_ma50_ratio >= 0.65:
        status = "VALID VCP"
    elif count >= 2 and latest_smaller and above_ma50_ratio >= 0.5:
        status = "EARLY VCP"
    else:
        status = "NOT VCP"

    return VcpInfo(status, count, contractions, final_pct, volume_contraction, label_points)


def score_technical(data: pd.DataFrame, pivot: PivotInfo) -> Tuple[int, List[str]]:
    """VCP and entry-timing score, max 8."""
    latest = data.iloc[-1]
    previous = data.iloc[-2] if len(data) >= 2 else latest
    score = 0
    notes: List[str] = []

    if latest["Close"] > latest["MA10"] and latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"]:
        score += 1
        notes.append("Price above MA10/20/50")
    if is_rising(data["MA10"]):
        score += 1
        notes.append("MA10 rising")
    if has_higher_low_structure(data):
        score += 1
        notes.append("Higher lows")
    if has_volume_contraction(data):
        score += 1
        notes.append("10-day volume contraction")
    if pivot.distance_pct <= 5 or pivot.label == "Breakout in progress":
        score += 1
        notes.append("Within 5% of pivot")
    if latest["Low"] >= latest["MA10"] or (latest["Close"] >= latest["MA10"] and previous["Close"] >= previous["MA10"]):
        score += 1
        notes.append("Holding MA10")
    if has_tight_range(data):
        score += 1
        notes.append("Tight 5-day range")
    if latest.get("RSSlope30", np.nan) > 0:
        score += 1
        notes.append("RS line improving")

    return score, notes


def detect_extension(data: pd.DataFrame) -> Tuple[bool, float, float, str]:
    """Detect chase risk when price is stretched far above short MAs."""
    latest = data.iloc[-1]
    ma10_distance = (latest["Close"] - latest["MA10"]) / latest["MA10"] * 100
    ma20_distance = (latest["Close"] - latest["MA20"]) / latest["MA20"] * 100
    extended = bool(ma10_distance > 10 or ma20_distance > 15 or latest["RSI14"] > 85)

    if extended:
        warning = f"Extended: {ma10_distance:.1f}% above MA10, {ma20_distance:.1f}% above MA20"
    else:
        warning = f"OK: {ma10_distance:.1f}% above MA10, {ma20_distance:.1f}% above MA20"
    return extended, round(ma10_distance, 2), round(ma20_distance, 2), warning


def choose_action_label(
    data: pd.DataFrame,
    trend_score: int,
    technical_score: int,
    pivot: PivotInfo,
    vcp: VcpInfo,
    extended: bool,
) -> str:
    """Convert setup conditions into the next practical action bucket."""
    latest = data.iloc[-1]
    rs_falling = latest.get("RSSlope30", np.nan) < 0
    support_broken = latest["Close"] < latest["Low10"] or latest["Close"] < latest["MA50"]
    near_ma10 = abs(latest["Close"] - latest["MA10"]) / latest["Close"] <= 0.03
    near_ma20 = abs(latest["Close"] - latest["MA20"]) / latest["Close"] <= 0.04
    holds_support = latest["Close"] > min(latest["MA10"], latest["MA20"])
    near_pivot = pivot.distance_pct <= 5 or pivot.label == "Breakout in progress"
    forming_base = vcp.status in {"VALID VCP", "EARLY VCP"} or near_pivot or has_higher_low_structure(data)

    if support_broken or (latest["Close"] < latest["MA50"] and rs_falling):
        return "FAILED"
    if extended and trend_score >= 5:
        return "EXTENDED"
    if trend_score >= 5 and technical_score >= 6 and vcp.status in {"VALID VCP", "EARLY VCP"} and near_pivot:
        return "READY"
    if trend_score >= 5 and (near_ma10 or near_ma20) and holds_support:
        return "PULLBACK ENTRY"
    if trend_score >= 4 and technical_score >= 4 and forming_base:
        return "WATCH"
    return "FAILED" if latest["Close"] < latest["MA50"] else "WATCH"


def build_trade_plan(data: pd.DataFrame, action: str, pivot: PivotInfo) -> Tuple[float, float, float, float, float, str]:
    """Calculate entry, stop, risk, 2R, 3R, and invalidation notes."""
    latest = data.iloc[-1]
    previous = data.iloc[-2] if len(data) >= 2 else latest
    atr = latest["ATR14"] if pd.notna(latest["ATR14"]) else latest["Close"] * 0.03

    if action == "READY":
        entry = pivot.trigger
    elif action == "PULLBACK ENTRY":
        entry = max(float(previous["High"]), float(latest["MA10"]), float(latest["MA20"]))
    else:
        entry = pivot.trigger if pivot.label != "Breakout in progress" else float(previous["High"])

    structure_support = min(float(latest["Low10"]), float(latest["MA10"]), float(latest["MA20"]))
    stop = structure_support - 0.5 * float(atr)
    stop = max(stop, 0.01)
    risk_dollars = max(entry - stop, 0.01)
    risk_pct = risk_dollars / entry * 100 if entry > 0 else np.nan
    target_2r = entry + 2 * risk_dollars
    target_3r = entry + 3 * risk_dollars
    invalidation = "Close below MA20, close below recent structure low, or high-volume failed breakout."

    return (
        round(entry, 2),
        round(stop, 2),
        round(risk_pct, 2),
        round(target_2r, 2),
        round(target_3r, 2),
        invalidation,
    )


def calculate_rr_score(entry: float, stop: float, target_2r: float) -> Tuple[float | None, str]:
    """Classify risk/reward quality from the planned entry, stop, and 2R target."""
    risk = entry - stop
    if risk <= 0:
        return None, "Invalid"

    rr_ratio = (target_2r - entry) / risk
    if rr_ratio >= 2.5:
        rr_score = "A+"
    elif rr_ratio >= 2.0:
        rr_score = "A"
    elif rr_ratio >= 1.5:
        rr_score = "B"
    else:
        rr_score = "C"
    return round(rr_ratio, 2), rr_score


def contractions_generally_decrease(contractions: List[float]) -> bool:
    """Allow one small imperfection while still rewarding a tightening pattern."""
    if len(contractions) < 2:
        return False
    decreases = sum(later < earlier for earlier, later in zip(contractions, contractions[1:]))
    return decreases >= max(1, len(contractions) - 2)


def calculate_tightness(data: pd.DataFrame, vcp: VcpInfo) -> Tuple[int, str]:
    """Score final contraction quality and recent quietness from 0 to 5."""
    score = 0
    latest_contraction = vcp.final_pct

    if latest_contraction is not None and latest_contraction <= 10:
        score += 2
    if latest_contraction is not None and latest_contraction <= 6:
        score += 1
    if contractions_generally_decrease(vcp.contractions):
        score += 1
    if has_tight_range(data):
        score += 1
    if has_volume_contraction(data):
        score += 1

    score = min(score, 5)
    if score == 5:
        label = "Excellent"
    elif score == 4:
        label = "Good"
    elif score == 3:
        label = "Acceptable"
    else:
        label = "Loose"
    return score, label


def calculate_rs_score(data: pd.DataFrame, spy_data: pd.DataFrame | None, qqq_data: pd.DataFrame | None) -> float:
    """Score relative strength against SPY and QQQ over 1M, 3M, and 6M."""
    score = 0.0
    weights = {21: 2.0, 63: 1.5, 126: 1.5}

    for days, weight in weights.items():
        stock_return = period_return(data, days)
        for benchmark in (spy_data, qqq_data):
            benchmark_return = period_return(benchmark, days)
            if pd.isna(stock_return) or pd.isna(benchmark_return):
                continue
            outperformance = stock_return - benchmark_return
            if outperformance > 0:
                score += weight
            elif outperformance > -2:
                score += weight * 0.5

    return round(min(score, 10.0), 1)


def calculate_sector_leadership(data: pd.DataFrame, sector_data: pd.DataFrame | None) -> Tuple[str, float | None]:
    """Label whether the stock is outperforming its mapped sector ETF."""
    stock_return = period_return(data, 63)
    sector_return = period_return(sector_data, 63)
    if pd.isna(stock_return) or pd.isna(sector_return):
        return "N/A", None

    spread = stock_return - sector_return
    if spread >= 5:
        label = "Leader"
    elif spread <= -5:
        label = "Laggard"
    else:
        label = "Average"
    return label, round(spread, 1)


def detect_earnings_risk(next_earnings_date: str | None) -> Tuple[str, bool]:
    """Flag earnings risk when the next date is within seven trading days."""
    if not next_earnings_date:
        return "N/A", False

    today = pd.Timestamp.today().normalize()
    earnings_date = pd.Timestamp(next_earnings_date).normalize()
    if earnings_date < today:
        return next_earnings_date, False

    trading_days = len(pd.bdate_range(today, earnings_date)) - 1
    return ("EARNINGS RISK" if trading_days <= 7 else next_earnings_date), trading_days <= 7


def calculate_volume_confirmation(data: pd.DataFrame, action: str, pivot: PivotInfo) -> Tuple[str, str]:
    """Confirm volume for breakout setups and pullback setups."""
    latest = data.iloc[-1]
    avg_vol20 = latest.get("AvgVol20", np.nan)
    if pd.isna(avg_vol20) or avg_vol20 <= 0:
        return "NO", "No 20-day volume baseline"

    breakout_volume = latest["Volume"] > 1.5 * avg_vol20
    pullback_volume_contracts = has_volume_contraction(data)
    near_breakout = action == "READY" or pivot.label == "Breakout in progress" or pivot.distance_pct <= 2

    if near_breakout:
        return ("YES", "Breakout volume >1.5x avg") if breakout_volume else ("NO", "Breakout volume below 1.5x avg")
    if action == "PULLBACK ENTRY":
        return ("YES", "Pullback volume contracting") if pullback_volume_contracts else ("NO", "Pullback volume not contracting")
    return ("YES", "Volume contracting") if pullback_volume_contracts else ("NO", "No volume confirmation")


def calculate_final_score(
    trend_score: int,
    technical_score: int,
    rs_score: float,
    sector_score: int,
    market_score: int,
    tightness_score: int,
) -> float:
    """Blend the core decision inputs into a 0-100 score."""
    score = (
        (trend_score / 7) * 25
        + (technical_score / 8) * 25
        + (rs_score / 10) * 20
        + (sector_score / 3) * 10
        + (market_score / 4) * 10
        + (tightness_score / 5) * 10
    )
    return round(min(max(score, 0), 100), 1)


def decide_trade(
    action: str,
    technical_score: int,
    trend_score: int,
    final_score: float,
    risk_pct: float,
    rr_score: str,
    extended: bool,
    earnings_risk: bool,
    volume_confirmation: str,
) -> Tuple[str, str]:
    """Return the final YES/NO decision and the first practical blocker."""
    if action not in {"READY", "PULLBACK ENTRY"}:
        return "NO", f"{action.title()} setup"
    if extended or action == "EXTENDED":
        return "NO", "Extended"
    if earnings_risk:
        return "NO", "Earnings risk"
    if final_score < 75:
        return "NO", "Final score below 75"
    if technical_score < 6 or trend_score < 5:
        return "NO", "Trend or technical score too low"
    if pd.isna(risk_pct) or risk_pct > 10:
        return "NO", "Risk too high"
    if rr_score not in {"A+", "A"}:
        return "NO", "RR below A"
    if volume_confirmation != "YES":
        return "NO", "Volume confirmation missing"
    return "YES", "Final score >=75, good RR, risk below 10%"


def decide_watchlist_flag(
    trade: str,
    vcp_status: str,
    trend_score: int,
    technical_score: int,
    tightness_score: int,
    extended: bool,
    risk_pct: float,
    rr_score: str,
    volume_contraction: bool,
    pivot: PivotInfo,
    volume_confirmation: str,
    market_score: int,
    sector_score: int,
) -> Tuple[str, str]:
    """Flag high-potential setups that need a better entry or confirmation."""
    if trade == "YES":
        return "NO", "Already Trade YES"
    if vcp_status not in {"EARLY VCP", "VALID VCP"}:
        return "NO", "Not VCP structure"
    if trend_score < 7:
        return "NO", "Weak trend"
    if technical_score < 6:
        return "NO", "Technical score below 6"
    if tightness_score < 3:
        return "NO", "Loose"
    if extended:
        return "NO", "Extended"
    if not (risk_pct > 10 or rr_score not in {"A+", "A"}):
        return "NO", "Entry already acceptable"
    if not volume_contraction:
        return "NO", "No volume contraction"

    near_below_pivot = 0 <= pivot.distance_pct <= 8
    slightly_above_without_volume = pivot.distance_pct < 0 and pivot.distance_pct >= -3 and volume_confirmation != "YES"
    if not (near_below_pivot or slightly_above_without_volume):
        return "NO", "Not near pivot"
    if market_score < 3:
        return "NO", "Weak market score"
    if sector_score < 2:
        return "NO", "Weak sector score"

    if risk_pct > 10:
        return "YES", "Strong trend, tightening, risk too high now"
    if volume_confirmation != "YES":
        return "YES", "Near pivot, waiting for volume confirmation"
    return "YES", "Early VCP, good structure, waiting for better entry"


def passes_prefilters(
    latest: pd.Series,
    market_cap: float | None,
    min_price: float,
    min_market_cap: float,
    min_dollar_volume: float,
) -> Tuple[bool, str]:
    """Apply quality filters while allowing unavailable market cap to pass."""
    failures: List[str] = []
    avg_volume = latest.get("AvgVol50", np.nan)
    avg_dollar_volume = latest.get("AvgDollarVol50", np.nan)

    if latest["Close"] <= min_price:
        failures.append("price below minimum")
    if market_cap is not None and market_cap <= min_market_cap:
        failures.append("market cap below minimum")
    if pd.notna(avg_volume) and avg_volume <= 1_000_000:
        failures.append("average volume below 1M")
    if pd.notna(avg_dollar_volume) and avg_dollar_volume <= min_dollar_volume:
        failures.append("dollar volume below minimum")

    return not failures, "; ".join(failures)


def build_scan_row(
    ticker: str,
    data: pd.DataFrame,
    market_cap: float | None,
    next_earnings_date: str | None,
    market_score: int,
    sector_score: int,
    benchmark_data: Dict[str, pd.DataFrame],
    sector_etf: str,
) -> dict:
    """Build the output row and stash chart-specific detail fields."""
    latest = data.iloc[-1]
    pivot = detect_pivot(data)
    vcp = detect_vcp(data, pivot)
    trend_score, trend_notes = score_trend(data)
    technical_score, technical_notes = score_technical(data, pivot)
    extended, ma10_distance, ma20_distance, extension_note = detect_extension(data)
    action = choose_action_label(data, trend_score, technical_score, pivot, vcp, extended)
    entry, stop, risk_pct, target_2r, target_3r, invalidation = build_trade_plan(data, action, pivot)
    rr_ratio, rr_score = calculate_rr_score(entry, stop, target_2r)
    tightness_score, tightness_label = calculate_tightness(data, vcp)
    rs_score = calculate_rs_score(data, benchmark_data.get("SPY"), benchmark_data.get("QQQ"))
    sector_leadership, sector_spread = calculate_sector_leadership(data, benchmark_data.get(sector_etf))
    earnings_label, earnings_risk = detect_earnings_risk(next_earnings_date)
    volume_confirmation, volume_note = calculate_volume_confirmation(data, action, pivot)
    final_score = calculate_final_score(
        trend_score=trend_score,
        technical_score=technical_score,
        rs_score=rs_score,
        sector_score=sector_score,
        market_score=market_score,
        tightness_score=tightness_score,
    )
    trade, trade_reason = decide_trade(
        action=action,
        technical_score=technical_score,
        trend_score=trend_score,
        final_score=final_score,
        risk_pct=risk_pct,
        rr_score=rr_score,
        extended=extended,
        earnings_risk=earnings_risk,
        volume_confirmation=volume_confirmation,
    )
    watchlist_flag, watchlist_reason = decide_watchlist_flag(
        trade=trade,
        vcp_status=vcp.status,
        trend_score=trend_score,
        technical_score=technical_score,
        tightness_score=tightness_score,
        extended=extended,
        risk_pct=risk_pct,
        rr_score=rr_score,
        volume_contraction=vcp.volume_contraction,
        pivot=pivot,
        volume_confirmation=volume_confirmation,
        market_score=market_score,
        sector_score=sector_score,
    )
    contraction_text = " -> ".join(f"{value:g}%" for value in vcp.contractions) if vcp.contractions else "N/A"

    notes = "; ".join(
        [
            pivot.label,
            extension_note,
            volume_note,
            f"Sector {sector_etf}: {sector_leadership}",
            f"Earnings: {earnings_label}",
            *trend_notes[:2],
            *technical_notes[:3],
            invalidation,
        ]
    )

    return {
        "ticker": ticker,
        "close": round(float(latest["Close"]), 2),
        "market cap": format_large_number(market_cap),
        "market cap raw": market_cap,
        "avg dollar volume": format_large_number(latest.get("AvgDollarVol50")),
        "avg dollar volume raw": latest.get("AvgDollarVol50"),
        "RSI": round(float(latest["RSI14"]), 1),
        "RS Score": rs_score,
        "Trend Score": trend_score,
        "Technical Score": technical_score,
        "Sector Score": sector_score,
        "Sector ETF": sector_etf,
        "Sector Leadership": sector_leadership,
        "Sector Spread %": sector_spread if sector_spread is not None else "N/A",
        "Market Score": market_score,
        "Final Score": final_score,
        "VCP Status": vcp.status,
        "Contractions": contraction_text,
        "contraction count": vcp.count,
        "final contraction %": vcp.final_pct,
        "volume contraction": "Yes" if vcp.volume_contraction else "No",
        "Pivot": pivot.pivot,
        "Distance to Pivot %": pivot.distance_pct,
        "Action Label": action,
        "Tightness Score": tightness_score,
        "Tightness Label": tightness_label,
        "RR Ratio": rr_ratio if rr_ratio is not None else "Invalid",
        "RR Score": rr_score,
        "Volume Confirmation": volume_confirmation,
        "Earnings Risk": earnings_label,
        "Trade": trade,
        "Trade Reason": trade_reason,
        "WATCHLIST FLAG": watchlist_flag,
        "Watchlist Reason": watchlist_reason,
        "Entry Trigger": entry,
        "Stop Loss": stop,
        "Risk %": risk_pct,
        "Target 2R": target_2r,
        "Target 3R": target_3r,
        "MA10 Distance %": ma10_distance,
        "MA20 Distance %": ma20_distance,
        "Notes": notes,
        "_pivot": pivot,
        "_vcp": vcp,
    }


def style_scan_table(row: pd.Series) -> List[str]:
    """Color rows by action label for fast visual review."""
    if row["Trade"] == "YES":
        return ["background-color: #86efac; color: #052e16; font-weight: 800"] * len(row)
    if row["WATCHLIST FLAG"] == "YES":
        return ["background-color: #dbeafe; color: #1e3a8a; font-weight: 700"] * len(row)

    colors = {
        "READY": "background-color: #dcfce7; color: #14532d; font-weight: 700",
        "PULLBACK ENTRY": "background-color: #dbeafe; color: #1e3a8a; font-weight: 700",
        "WATCH": "background-color: #fef9c3; color: #713f12",
        "EXTENDED": "background-color: #fed7aa; color: #7c2d12",
        "FAILED": "background-color: #fee2e2; color: #7f1d1d",
    }
    return [colors.get(row["Action Label"], "")] * len(row)


def make_chart(ticker: str, data: pd.DataFrame, row: pd.Series) -> go.Figure:
    """Create selected ticker chart with levels and VCP labels."""
    chart_data = data.tail(140)
    figure = go.Figure()

    figure.add_trace(
        go.Candlestick(
            x=chart_data.index,
            open=chart_data["Open"],
            high=chart_data["High"],
            low=chart_data["Low"],
            close=chart_data["Close"],
            name="Price",
        )
    )

    for ma, color in (("MA10", "#2563eb"), ("MA20", "#f59e0b"), ("MA50", "#16a34a")):
        figure.add_trace(
            go.Scatter(
                x=chart_data.index,
                y=chart_data[ma],
                mode="lines",
                line=dict(width=1.7, color=color),
                name=ma,
            )
        )

    figure.add_trace(
        go.Bar(
            x=chart_data.index,
            y=chart_data["Volume"],
            marker_color="#94a3b8",
            opacity=0.35,
            name="Volume",
            yaxis="y2",
        )
    )

    level_specs = [
        ("Pivot", row["Pivot"], "#111827"),
        ("Entry", row["Entry Trigger"], "#2563eb"),
        ("Stop", row["Stop Loss"], "#dc2626"),
        ("2R", row["Target 2R"], "#16a34a"),
        ("3R", row["Target 3R"], "#15803d"),
    ]
    for label, value, color in level_specs:
        if pd.notna(value):
            figure.add_hline(y=value, line_dash="dash", line_color=color, annotation_text=label)

    vcp: VcpInfo = row["_vcp"]
    for point in vcp.label_points:
        if point["date"] in chart_data.index:
            figure.add_annotation(
                x=point["date"],
                y=point["price"],
                text=point["text"],
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=28,
                font=dict(size=11, color="#334155"),
            )

    figure.update_layout(
        title=f"{ticker} daily setup chart",
        height=600,
        margin=dict(l=12, r=12, t=48, b=24),
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
        legend=dict(orientation="h", y=1.02, x=0),
        template="plotly_white",
    )
    return figure


def scan_universe(
    tickers: List[str],
    mode: str,
    min_price: float,
    min_market_cap: float,
    min_dollar_volume: float,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], dict]:
    """Download, filter, score, and return scanner results."""
    tickers = tickers[:300]
    all_tickers = tuple(sorted(set(tickers + MARKET_TICKERS)))
    raw_data = download_daily_data(all_tickers, period="18mo")

    spy_raw = raw_data.get("SPY")
    indicator_data = {ticker: add_indicators(frame, spy_raw) for ticker, frame in raw_data.items()}
    market_data = {ticker: indicator_data[ticker] for ticker in MARKET_TICKERS if ticker in indicator_data}
    market_score, market_status, market_details = calculate_market_score(market_data)
    sector_score, sector_details = calculate_sector_score(mode, market_data)
    market_caps = download_market_caps(tuple(tickers))
    earnings_dates = download_next_earnings_dates(tuple(tickers))

    rows: List[dict] = []
    rejected: List[str] = []
    progress = st.progress(0, text="Scoring stocks...")

    for index, ticker in enumerate(tickers):
        progress.progress((index + 1) / max(len(tickers), 1), text=f"Scoring {ticker}...")
        data = indicator_data.get(ticker)
        if data is None or len(data.dropna(subset=["MA200", "RSI14", "ATR14", "AvgDollarVol50"])) < 1:
            rejected.append(f"{ticker}: insufficient daily history")
            continue

        latest = data.iloc[-1]
        market_cap = market_caps.get(ticker)
        passes, reason = passes_prefilters(latest, market_cap, min_price, min_market_cap, min_dollar_volume)
        if not passes:
            rejected.append(f"{ticker}: {reason}")
            continue

        try:
            sector_etf = SECTOR_ETF_BY_TICKER.get(ticker, SECTOR_ETFS_BY_MODE.get(mode, ["SPY"])[0])
            rows.append(
                build_scan_row(
                    ticker=ticker,
                    data=data,
                    market_cap=market_cap,
                    next_earnings_date=earnings_dates.get(ticker),
                    market_score=market_score,
                    sector_score=sector_score,
                    benchmark_data=market_data,
                    sector_etf=sector_etf,
                )
            )
        except Exception as exc:
            rejected.append(f"{ticker}: scoring failed ({exc})")

    progress.empty()
    results = pd.DataFrame(rows)
    summary = {
        "market_score": market_score,
        "market_status": market_status,
        "market_details": market_details,
        "sector_score": sector_score,
        "sector_details": sector_details,
        "rejected": rejected,
        "scanned": len(tickers),
    }
    return results, indicator_data, summary


def main() -> None:
    """Render the Streamlit app."""
    st.set_page_config(page_title="VCP Swing Scanner", page_icon="VCP", layout="wide")
    st.title("VCP Swing Scanner")
    st.caption("Daily end-of-day scanner for VCP / J Law / Minervini-style swing-trading preparation.")

    with st.sidebar:
        st.header("Scanner")
        scan_mode = st.selectbox("Scan Mode", SCAN_MODES)
        custom_tickers = st.text_area(
            "Custom tickers",
            value="AAPL, MSFT, NVDA, AMD, META, TSLA",
            height=120,
            disabled=scan_mode != "Custom Input",
        )

        preset_tickers = PRESET_UNIVERSES.get(scan_mode, [])
        tickers = normalize_tickers(custom_tickers) if scan_mode == "Custom Input" else preset_tickers

        st.caption(f"{len(tickers)} tickers selected. Preset scans are capped at 300 symbols.")
        min_price = st.number_input("Minimum price", min_value=0.0, value=10.0, step=1.0)
        min_market_cap_b = st.number_input("Minimum market cap ($B)", min_value=0.0, value=5.0, step=0.5)
        min_dollar_volume_m = st.number_input("Minimum avg dollar volume ($M)", min_value=0.0, value=20.0, step=5.0)

        st.divider()
        show_all = st.checkbox("Show all", value=False)
        only_ready_pullback = st.checkbox("Show only READY / PULLBACK", value=False)
        only_trade_watchlist = st.checkbox("Show only Trade + Watchlist", value=False)
        hide_extended = st.checkbox("Hide EXTENDED", value=False)
        run_scan = st.button("Run Scan", type="primary", width="stretch")

    if run_scan:
        if not tickers:
            st.info("Choose a preset universe or enter custom tickers.")
            return

        with st.spinner("Downloading daily data and preparing trade plans..."):
            results, indicator_data, summary = scan_universe(
                tickers=tickers,
                mode=scan_mode,
                min_price=min_price,
                min_market_cap=min_market_cap_b * 1_000_000_000,
                min_dollar_volume=min_dollar_volume_m * 1_000_000,
            )
            st.session_state["results"] = results
            st.session_state["indicator_data"] = indicator_data
            st.session_state["summary"] = summary
            st.session_state["scan_mode"] = scan_mode

    if "results" not in st.session_state:
        st.info("Choose a scan mode, adjust the filters, then run the scan for your daily watchlist.")
        st.caption(
            "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
            "Confirm live price and volume in your broker before trading."
        )
        return

    results = st.session_state.get("results", pd.DataFrame())
    indicator_data = st.session_state.get("indicator_data", {})
    summary = st.session_state.get("summary", {})
    required_result_columns = {
        "Trade",
        "Trade Reason",
        "RR Ratio",
        "RR Score",
        "Tightness Score",
        "Tightness Label",
        "RS Score",
        "Sector Leadership",
        "Volume Confirmation",
        "Earnings Risk",
        "Final Score",
        "WATCHLIST FLAG",
        "Watchlist Reason",
    }

    if not results.empty and not required_result_columns.issubset(results.columns):
        st.session_state.pop("results", None)
        st.info("The scanner was upgraded with new decision fields. Run a fresh scan to rebuild the table.")
        return

    market_score = summary.get("market_score", 0)
    market_status = summary.get("market_status", "N/A")
    sector_score = summary.get("sector_score", 0)

    metric_cols = st.columns(5)
    metric_cols[0].metric("Market Status", market_status)
    metric_cols[1].metric("Market Score", f"{market_score}/4")
    metric_cols[2].metric("Sector Score", f"{sector_score}/3")
    metric_cols[3].metric("Stocks Passed", len(results))
    metric_cols[4].metric("Mode", st.session_state.get("scan_mode", scan_mode))

    with st.expander("Market and filter details", expanded=True):
        st.write("Market:", " | ".join(summary.get("market_details", [])) or "No market data yet.")
        st.write("Sector:", summary.get("sector_details", "No sector data yet."))
        rejected = summary.get("rejected", [])
        if rejected:
            st.caption(f"Filtered or skipped: {len(rejected)}")
            st.write(rejected[:25])

    if results.empty:
        st.warning("No stocks passed the quality filters. Loosen the sidebar thresholds or use a different universe.")
        st.markdown(
            "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
            "Confirm live price and volume in your broker before trading."
        )
        return

    visible = results.copy()
    if not show_all:
        visible = visible[
            (visible["Trend Score"] >= 4)
            & (visible["Technical Score"] >= 4)
            & (visible["Action Label"] != "FAILED")
        ]
    if only_ready_pullback:
        visible = visible[visible["Action Label"].isin(["READY", "PULLBACK ENTRY"])]
    if only_trade_watchlist:
        visible = visible[(visible["Trade"] == "YES") | (visible["WATCHLIST FLAG"] == "YES")]
    if hide_extended:
        visible = visible[visible["Action Label"] != "EXTENDED"]

    visible["trade sort"] = np.where(visible["Trade"] == "YES", 0, 1)
    visible["watchlist sort"] = np.where(visible["WATCHLIST FLAG"] == "YES", 0, 1)
    visible = visible.sort_values(
        ["trade sort", "watchlist sort", "Tightness Score", "Trend Score"],
        ascending=[True, True, False, False],
    )

    display_columns = [
        "ticker",
        "close",
        "market cap",
        "avg dollar volume",
        "RSI",
        "RS Score",
        "Trend Score",
        "Technical Score",
        "Sector Score",
        "Sector Leadership",
        "Market Score",
        "Final Score",
        "VCP Status",
        "Contractions",
        "Pivot",
        "Distance to Pivot %",
        "Action Label",
        "Tightness Score",
        "Tightness Label",
        "RR Ratio",
        "RR Score",
        "Volume Confirmation",
        "Earnings Risk",
        "Trade",
        "WATCHLIST FLAG",
        "Trade Reason",
        "Watchlist Reason",
        "Entry Trigger",
        "Stop Loss",
        "Risk %",
        "Target 2R",
        "Target 3R",
        "Notes",
    ]

    st.subheader("Best Setups")
    if visible.empty:
        st.info("No rows match the current display filters.")
    else:
        st.dataframe(
            visible[display_columns].style.apply(style_scan_table, axis=1),
            width="stretch",
            hide_index=True,
        )

    selectable = visible if not visible.empty else results
    selected_ticker = st.selectbox("Review ticker", selectable["ticker"].tolist())
    selected_row = results[results["ticker"] == selected_ticker].iloc[0]
    selected_data = indicator_data.get(selected_ticker)

    chart_col, plan_col = st.columns([2, 1])
    with chart_col:
        if selected_data is not None and not selected_data.empty:
            st.plotly_chart(make_chart(selected_ticker, selected_data, selected_row), width="stretch")

    with plan_col:
        st.subheader("Trade Plan")
        st.metric("Action", selected_row["Action Label"])
        st.metric("Trade", selected_row["Trade"], selected_row["Trade Reason"])
        st.metric("Watchlist", selected_row["WATCHLIST FLAG"], selected_row["Watchlist Reason"])
        st.metric("Final Score", f"{selected_row['Final Score']:.1f}/100")
        st.metric("Entry Trigger", f"${selected_row['Entry Trigger']:.2f}")
        st.metric("Stop Loss", f"${selected_row['Stop Loss']:.2f}", f"Risk {selected_row['Risk %']:.2f}%")
        st.metric("Targets", f"2R ${selected_row['Target 2R']:.2f}", f"3R ${selected_row['Target 3R']:.2f}")
        st.write(f"RS Score: {selected_row['RS Score']}/10")
        st.write(f"Sector: {selected_row['Sector Leadership']} vs {selected_row['Sector ETF']}")
        st.write(f"Volume confirmation: {selected_row['Volume Confirmation']}")
        st.write(f"Earnings: {selected_row['Earnings Risk']}")
        st.write(f"RR: {selected_row['RR Ratio']} ({selected_row['RR Score']})")
        st.write(f"Tightness: {selected_row['Tightness Score']}/5, {selected_row['Tightness Label']}")
        st.write(f"VCP: {selected_row['VCP Status']} ({selected_row['Contractions']})")
        st.write(f"Pivot: ${selected_row['Pivot']:.2f}, distance {selected_row['Distance to Pivot %']:.2f}%")
        st.write(f"MA distance: MA10 {selected_row['MA10 Distance %']:.2f}%, MA20 {selected_row['MA20 Distance %']:.2f}%")
        st.write(selected_row["Notes"])

    st.caption(
        "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
        "Confirm live price and volume in your broker before trading."
    )


if __name__ == "__main__":
    main()
