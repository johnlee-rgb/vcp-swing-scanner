"""VCP Swing Scanner.

Practical end-of-day Streamlit scanner for US swing-trading preparation.
The app uses daily yfinance data only. It is designed around VCP / J Law /
Minervini-style routines: scan a focused universe, filter weak names, score
trend and timing separately, then produce a next-day trade plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from io import StringIO
import re
import smtplib
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
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

US_PRO_EXTRA = [
    "UNH", "JNJ", "ABBV", "MRK", "PFE", "ABT", "AMGN", "GILD", "BIIB", "ILMN", "HCA", "CI", "ELV",
    "TMO", "DHR", "ZTS", "A", "EW", "RMD", "PODD", "MCK", "CAH", "COR", "HUM", "CNC", "CVS",
    "PG", "KO", "PEP", "COKE", "MDLZ", "MNST", "CL", "KMB", "CAG", "KHC", "GIS", "HSY", "MCD",
    "YUM", "DPZ", "WING", "TXRH", "DRI", "CMG", "CAVA", "SBUX", "TGT", "LOW", "TJX", "ROST",
    "F", "GM", "RIVN", "LCID", "NIO", "LI", "XPEV", "TM", "HMC", "RACE", "AZO", "ORLY", "GPC",
    "DIS", "CMCSA", "WBD", "PARA", "TTWO", "EA", "RBLX", "PINS", "SNAP", "RDDT", "MTCH", "BMBL",
    "T", "VZ", "TMUS", "CHTR", "LUMN", "AMT", "CCI", "EQIX", "DLR", "PLD", "O", "SPG", "WELL",
    "PSA", "EXR", "AVB", "EQR", "VICI", "GLPI", "CPT", "ARE", "CBRE", "JLL", "AON", "MMC",
    "TRV", "PGR", "ALL", "AIG", "MET", "PRU", "AFL", "TFC", "USB", "PNC", "COF", "DFS", "SYF",
    "FIS", "FI", "GPN", "ADP", "PAYX", "BR", "FICO", "SPGI", "MCO", "NDAQ", "MKTX", "CBOE",
    "LIN", "APD", "SHW", "ECL", "DD", "DOW", "FCX", "NEM", "GOLD", "AA", "CLF", "STLD", "NUE",
    "X", "RS", "CMC", "MOS", "CF", "ALB", "SQM", "LAC", "LTHM", "ENPH", "SEDG", "FSLR", "RUN",
    "NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "PEG", "ED", "EIX", "PCG", "FE", "AES",
    "DAL", "UAL", "AAL", "LUV", "ALK", "JBLU", "FDX", "UPS", "XPO", "CHRW", "ODFL", "SAIA",
    "NSC", "CSX", "UNP", "CP", "CNI", "KSU", "WAB", "LII", "CARR", "TT", "JCI", "MAS", "BLDR",
    "LEN", "DHI", "PHM", "TOL", "NVR", "KBH", "MTH", "TREX", "OC", "HD", "LOW", "POOL",
    "LULU", "ONON", "BIRK", "SKX", "CROX", "RL", "TPR", "CPRI", "LEVI", "GAP", "ANF", "AEO",
    "W", "CHWY", "ETSY", "EBAY", "BABA", "JD", "PDD", "BIDU", "TME", "VIPS", "GRAB", "CPNG",
    "ROKU", "TTD", "MGNI", "PUBM", "APPS", "U", "RBLX", "Unity", "AI", "SOUN", "BBAI", "SERV",
]

US_PRO_UNIVERSE = list(dict.fromkeys(MARKET_LEADERS_BASE + US_PRO_EXTRA))[:500]

HK_PRO_UNIVERSE = [
    "0700.HK", "9988.HK", "3690.HK", "1810.HK", "0388.HK", "0005.HK", "0939.HK", "1398.HK",
    "3988.HK", "2318.HK", "1299.HK", "0941.HK", "0883.HK", "0857.HK", "0386.HK", "0688.HK",
    "2628.HK", "2319.HK", "2388.HK", "0011.HK", "0002.HK", "0003.HK", "0006.HK", "0012.HK",
    "0016.HK", "0027.HK", "0066.HK", "0101.HK", "0175.HK", "0201.HK", "0267.HK", "0288.HK",
    "0291.HK", "0316.HK", "0322.HK", "0358.HK", "0384.HK", "0390.HK", "0669.HK", "0683.HK",
    "0708.HK", "0762.HK", "0823.HK", "0836.HK", "0868.HK", "0881.HK", "0960.HK", "0968.HK",
    "0981.HK", "0986.HK", "1024.HK", "1044.HK", "1088.HK", "1093.HK", "1109.HK", "1113.HK",
    "1177.HK", "1209.HK", "1211.HK", "1336.HK", "1378.HK", "1368.HK", "1448.HK", "1548.HK",
    "1658.HK", "1688.HK", "1766.HK", "1772.HK", "1800.HK", "1876.HK", "1918.HK", "1928.HK",
    "1929.HK", "1997.HK", "2007.HK", "2015.HK", "2020.HK", "2269.HK", "2313.HK", "2331.HK",
    "2333.HK", "2359.HK", "2382.HK", "2386.HK", "2600.HK", "2601.HK", "2618.HK", "2688.HK",
    "2899.HK", "3323.HK", "3328.HK", "3333.HK", "3618.HK", "3669.HK", "3759.HK", "3800.HK",
    "6030.HK", "6060.HK", "6618.HK", "6690.HK", "6862.HK", "9618.HK", "9633.HK", "9868.HK",
    "9888.HK", "9901.HK", "9992.HK", "9999.HK", "1024.HK", "2018.HK", "9995.HK", "9698.HK",
]
HK_PRO_UNIVERSE = list(dict.fromkeys(HK_PRO_UNIVERSE))
COMBINED_PRO_UNIVERSE = list(dict.fromkeys(US_PRO_UNIVERSE + HK_PRO_UNIVERSE))[:800]

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
    "US Pro Market Scan",
    "HK Pro Market Scan",
    "Combined US + HK Scan",
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
    "US Pro Market Scan": ["QQQ", "SPY"],
    "HK Pro Market Scan": ["2800.HK", "^HSI"],
    "Combined US + HK Scan": ["QQQ", "2800.HK"],
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
HK_MARKET_TICKERS = ["^HSI", "2800.HK", "3033.HK", "3067.HK"]
ALL_CONTEXT_TICKERS = list(dict.fromkeys(MARKET_TICKERS + HK_MARKET_TICKERS))
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


DISPLAY_SECTOR_FALLBACK = {
    "AAPL": ("Technology", "Consumer Electronics", "Mega Cap Tech"),
    "MSFT": ("Technology", "Software Infrastructure", "AI / Cloud"),
    "NVDA": ("Technology", "Semiconductors", "AI Semiconductor"),
    "AMD": ("Technology", "Semiconductors", "AI Semiconductor"),
    "AVGO": ("Technology", "Semiconductors", "AI Semiconductor"),
    "TSM": ("Technology", "Semiconductors", "AI Semiconductor"),
    "DELL": ("Technology", "Computer Hardware", "AI Infrastructure"),
    "VRT": ("Industrials", "Electrical Equipment", "AI Infrastructure"),
    "SMCI": ("Technology", "Computer Hardware", "AI Infrastructure"),
    "AMZN": ("Consumer Cyclical", "Internet Retail", "Cloud / Consumer"),
    "META": ("Communication Services", "Internet Content", "Mega Cap Tech"),
    "GOOGL": ("Communication Services", "Internet Content", "Mega Cap Tech"),
    "GOOG": ("Communication Services", "Internet Content", "Mega Cap Tech"),
    "TSLA": ("Consumer Cyclical", "Auto Manufacturers", "EV / Growth"),
    "STLD": ("Basic Materials", "Steel", "Cyclical Materials"),
    "NUE": ("Basic Materials", "Steel", "Cyclical Materials"),
    "AA": ("Basic Materials", "Aluminum", "Cyclical Materials"),
    "FCX": ("Basic Materials", "Copper", "Cyclical Materials"),
    "CNC": ("Healthcare", "Healthcare Plans", "Managed Care"),
    "ELV": ("Healthcare", "Healthcare Plans", "Managed Care"),
    "HUM": ("Healthcare", "Healthcare Plans", "Managed Care"),
    "MRK": ("Healthcare", "Drug Manufacturers", "Healthcare"),
    "CVS": ("Healthcare", "Healthcare Plans", "Managed Care"),
    "MNST": ("Consumer Defensive", "Beverages", "Consumer Defensive"),
    "DAL": ("Industrials", "Airlines", "Airlines"),
    "AAL": ("Industrials", "Airlines", "Airlines"),
    "LUV": ("Industrials", "Airlines", "Airlines"),
    "CNI": ("Industrials", "Railroads", "Transportation"),
    "CROX": ("Consumer Cyclical", "Footwear", "Consumer Cyclical"),
    "ODFL": ("Industrials", "Trucking", "Transportation"),
    "XPO": ("Industrials", "Trucking", "Transportation"),
    "CARR": ("Industrials", "Building Products", "Industrials"),
    "MTCH": ("Communication Services", "Internet Content", "Internet"),
    "LUMN": ("Communication Services", "Telecom", "Telecom"),
    "ETSY": ("Consumer Cyclical", "Internet Retail", "Internet Retail"),
    "DXCM": ("Healthcare", "Medical Devices", "Healthcare"),
    "ILMN": ("Healthcare", "Diagnostics & Research", "Healthcare"),
    "A": ("Healthcare", "Diagnostics & Research", "Healthcare"),
    "CMC": ("Basic Materials", "Steel", "Cyclical Materials"),
}


SECTOR_ETF_DISPLAY_FALLBACK = {
    "SMH": ("Technology", "Semiconductors", "AI Semiconductor"),
    "SOXX": ("Technology", "Semiconductors", "AI Semiconductor"),
    "XLK": ("Technology", "Technology", "Technology"),
    "XLY": ("Consumer Cyclical", "Consumer Discretionary", "Consumer Cyclical"),
    "XLF": ("Financial Services", "Financials", "Financials"),
    "XLV": ("Healthcare", "Healthcare", "Healthcare"),
    "XLI": ("Industrials", "Industrials", "Industrials"),
    "XLE": ("Energy", "Energy", "Energy"),
    "IBB": ("Healthcare", "Biotechnology", "Biotech"),
    "ITA": ("Industrials", "Aerospace & Defense", "Aerospace / Defense"),
    "SPY": ("Market", "Broad Market", "Broad Market"),
}


def display_sector_metadata(ticker: str, sector_etf: str) -> dict:
    """Return display-only sector fields without affecting scanner scoring."""
    clean_ticker = str(ticker).upper().strip().split(".")[0]
    sector, industry, theme = DISPLAY_SECTOR_FALLBACK.get(
        clean_ticker,
        SECTOR_ETF_DISPLAY_FALLBACK.get(sector_etf, ("N/A", "N/A", sector_etf or "N/A")),
    )
    return {
        "Sector": sector,
        "Industry": industry,
        "Theme": theme,
        "Sector / Industry": f"{sector} / {industry}" if sector != "N/A" or industry != "N/A" else "N/A",
        "Theme Group": theme,
    }


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


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def download_earnings_data(tickers: Tuple[str, ...]) -> Dict[str, dict]:
    """Fetch best-effort earnings metadata without assuming yfinance fields exist."""
    today = pd.Timestamp.today().normalize()
    output: Dict[str, dict] = {}
    for ticker in tickers:
        item = {
            "next_date": None,
            "days_to_earnings": None,
            "last_date": None,
            "eps_estimate": "N/A",
            "revenue_estimate": "N/A",
            "last_eps_surprise_pct": "N/A",
            "last_revenue_surprise_pct": "N/A",
        }
        try:
            yf_ticker = yf.Ticker(ticker)
            calendar = None
            try:
                calendar = yf_ticker.get_calendar()
            except Exception:
                calendar = getattr(yf_ticker, "calendar", None)
            if isinstance(calendar, dict):
                raw_date = calendar.get("Earnings Date") or calendar.get("EarningsDate")
                if isinstance(raw_date, (list, tuple)) and raw_date:
                    raw_date = raw_date[0]
                if raw_date is not None:
                    parsed = pd.to_datetime(raw_date, errors="coerce")
                    if pd.notna(parsed):
                        item["next_date"] = parsed.normalize().strftime("%Y-%m-%d")
                item["eps_estimate"] = calendar.get("Earnings Average", "N/A")
                item["revenue_estimate"] = calendar.get("Revenue Average", "N/A")

            earnings = yf_ticker.get_earnings_dates(limit=8)
            if earnings is not None and not earnings.empty:
                dates = pd.to_datetime(earnings.index).tz_localize(None).normalize()
                future_dates = [date for date in dates if date >= today]
                past_dates = [date for date in dates if date < today]
                if future_dates and item["next_date"] is None:
                    item["next_date"] = min(future_dates).strftime("%Y-%m-%d")
                if past_dates:
                    item["last_date"] = max(past_dates).strftime("%Y-%m-%d")
                latest_past_rows = earnings.loc[dates < today]
                if latest_past_rows is not None and not latest_past_rows.empty:
                    last_row = latest_past_rows.iloc[0]
                    surprise = last_row.get("Surprise(%)", last_row.get("Surprise (%)", np.nan))
                    if pd.notna(surprise):
                        item["last_eps_surprise_pct"] = round(float(surprise), 2)
        except Exception:
            pass

        if item["next_date"]:
            days = (pd.Timestamp(item["next_date"]) - today).days
            item["days_to_earnings"] = max(days, 0)
        output[ticker] = item
    return output


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


def calculate_hk_market_score(market_data: Dict[str, pd.DataFrame]) -> Tuple[int, str, List[str]]:
    """Score HK market context from HSI and liquid HK ETFs."""
    score = 0
    details: List[str] = []
    for ticker in ("^HSI", "2800.HK", "3033.HK", "3067.HK"):
        data = market_data.get(ticker)
        if data is None or data.empty:
            details.append(f"{ticker}: no data")
            continue
        latest = data.iloc[-1]
        passes = bool(latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"])
        score += int(passes)
        details.append(f"{ticker} {'above' if passes else 'not above'} MA20/MA50")
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


def classify_earnings_risk(earnings_info: dict) -> Tuple[str, bool]:
    """Classify next earnings risk using calendar days."""
    days = earnings_info.get("days_to_earnings")
    if days is None:
        return "N/A", False
    if days <= 7:
        return "HIGH RISK", True
    if days <= 14:
        return "MEDIUM RISK", False
    return "LOW RISK", False


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


def detect_breakout_alert(data: pd.DataFrame, pivot: PivotInfo, volume_confirmation: str) -> str:
    """Classify the current relationship to the pivot for alerts and ranking."""
    close = latest_value(data, "Close")
    if pd.isna(close) or pd.isna(pivot.pivot):
        return "NO BREAKOUT"
    if close > pivot.pivot and volume_confirmation == "YES":
        return "CONFIRMED BREAKOUT"
    if 0 <= pivot.distance_pct <= 3:
        return "NEAR BREAKOUT"
    if close > pivot.pivot:
        return "BREAKOUT IN PROGRESS"
    return "NO BREAKOUT"


def calculate_earnings_setup(
    data: pd.DataFrame,
    trend_score: int,
    rs_score: float,
    sector_score: int,
    earnings_info: dict,
) -> Tuple[int, str, str]:
    """Score pre/post-earnings momentum and assign an earnings strategy."""
    latest = data.iloc[-1]
    score = 0
    if trend_score >= 5:
        score += 2
    if rs_score >= 6:
        score += 2
    if len(data) >= 15 and data["Volume"].tail(5).mean() > data["Volume"].iloc[-15:-5].mean():
        score += 2
    if latest["Close"] > latest["MA10"] and latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"]:
        score += 2
    if sector_score >= 2:
        score += 1
    surprise = earnings_info.get("last_eps_surprise_pct")
    if isinstance(surprise, (int, float)) and surprise > 0:
        score += 1

    if score >= 8:
        label = "Strong earnings momentum"
    elif score >= 6:
        label = "Positive setup"
    elif score >= 4:
        label = "Neutral"
    else:
        label = "Weak / risky"

    days = earnings_info.get("days_to_earnings")
    if days is not None and days <= 7:
        strategy = "WATCH AFTER EARNINGS" if score >= 7 else "AVOID BEFORE EARNINGS"
    elif score >= 8:
        strategy = "PRE-EARNINGS MOMENTUM TRADE"
    else:
        strategy = "WATCH AFTER EARNINGS"
    return min(score, 10), label, strategy


def detect_post_earnings_label(data: pd.DataFrame, earnings_info: dict) -> str:
    """Detect basic post-earnings gap behavior when earnings occurred recently."""
    last_date = earnings_info.get("last_date")
    if not last_date:
        return "NO RECENT EARNINGS"
    date = pd.Timestamp(last_date)
    recent_index = data.index[data.index >= date]
    if len(recent_index) == 0 or len(recent_index) > 10:
        return "NO RECENT EARNINGS"

    pos = data.index.get_loc(recent_index[0])
    if pos == 0:
        return "NO RECENT EARNINGS"
    earnings_day = data.iloc[pos]
    previous_close = data.iloc[pos - 1]["Close"]
    latest = data.iloc[-1]
    gap_pct = (earnings_day["Open"] - previous_close) / previous_close * 100 if previous_close else 0
    high_hold = latest["Close"] >= earnings_day["High"]
    ma_hold = latest["Close"] >= latest["MA10"] or latest["Close"] >= latest["MA20"]
    strong_volume = earnings_day["Volume"] > 1.5 * earnings_day.get("AvgVol20", np.nan)

    if gap_pct >= 2:
        return "EARNINGS GAP UP HOLDING" if high_hold and ma_hold and strong_volume else "EARNINGS GAP UP FAILING"
    if gap_pct <= -2:
        return "EARNINGS GAP DOWN RECOVERING" if ma_hold else "EARNINGS GAP DOWN WEAK"
    return "NO RECENT EARNINGS"


def ai_trade_label(row: pd.Series) -> str:
    """Summarize why an AI top-pick card is interesting or risky."""
    if row.get("Earnings Risk") == "HIGH RISK":
        return "EARNINGS RISK"
    if row.get("Action Label") == "EXTENDED":
        return "TOO EXTENDED"
    if row.get("Trade") == "YES":
        return "BEST BUY SETUP"
    if row.get("Action Label") == "PULLBACK ENTRY":
        return "PULLBACK SETUP"
    return "WATCH FOR BREAKOUT"


def classify_setup_category(
    vcp_status: str,
    action: str,
    breakout_alert: str,
    trend_score: int,
    technical_score: int,
    rs_score: float,
    risk_pct: float,
    extended: bool,
) -> str:
    """Group setups for display and momentum-breakout handling."""
    if action == "FAILED" or extended or risk_pct > 10:
        return "High Risk"
    if vcp_status in {"VALID VCP", "EARLY VCP"} and breakout_alert in {"BREAKOUT IN PROGRESS", "CONFIRMED BREAKOUT", "NEAR BREAKOUT"}:
        return "VCP Breakout"
    if (
        trend_score >= 8
        and technical_score >= 8
        and rs_score >= 8
        and breakout_alert in {"BREAKOUT IN PROGRESS", "CONFIRMED BREAKOUT"}
        and risk_pct <= 10
    ):
        return "Momentum Breakout"
    if action == "PULLBACK ENTRY":
        return "Pullback Setup"
    if vcp_status == "EARLY VCP" or action == "WATCH":
        return "Early Base"
    return "High Risk"


def build_ai_trading_notes(row: dict) -> str:
    """Create compact rule-based notes for table, cards, and alerts."""
    return (
        f"{row['ticker']} {row['Action Label']} | {row['VCP Status']} | "
        f"Final {row['Final Score']}/100 | {row['Breakout Alert']} | "
        f"Risk {row['Risk %']}% | Earnings {row['Earnings Risk']}"
    )


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
    earnings_risk_label: str = "N/A",
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
        if earnings_risk_label == "HIGH RISK":
            return "YES", "Watch only - earnings soon"
        return "YES", "Strong trend, tightening, risk too high now"
    if volume_confirmation != "YES":
        if earnings_risk_label == "HIGH RISK":
            return "YES", "Watch only - earnings soon"
        return "YES", "Near pivot, waiting for volume confirmation"
    if earnings_risk_label == "HIGH RISK":
        return "YES", "Watch only - earnings soon"
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
    earnings_info: dict,
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
    earnings_label, earnings_risk = classify_earnings_risk(earnings_info)
    volume_confirmation, volume_note = calculate_volume_confirmation(data, action, pivot)
    breakout_alert = detect_breakout_alert(data, pivot, volume_confirmation)
    earnings_setup_score, earnings_setup_label, earnings_strategy = calculate_earnings_setup(
        data, trend_score, rs_score, sector_score, earnings_info
    )
    post_earnings_label = detect_post_earnings_label(data, earnings_info)
    display_sector = display_sector_metadata(ticker, sector_etf)
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
        earnings_risk_label=earnings_label,
    )
    setup_category = classify_setup_category(
        vcp_status=vcp.status,
        action=action,
        breakout_alert=breakout_alert,
        trend_score=trend_score,
        technical_score=technical_score,
        rs_score=rs_score,
        risk_pct=risk_pct,
        extended=extended,
    )
    if setup_category == "Momentum Breakout":
        trade = "YES"
        trade_reason = "Momentum Breakout Candidate"
        watchlist_flag = "NO"
        watchlist_reason = "Already Trade YES"
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

    row = {
        "ticker": ticker,
        "Sector / Industry": display_sector["Sector / Industry"],
        "Sector": display_sector["Sector"],
        "Industry": display_sector["Industry"],
        "Theme": display_sector["Theme"],
        "Theme Group": display_sector["Theme Group"],
        "Setup Category": setup_category,
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
        "Breakout Alert": breakout_alert,
        "Earnings Date": earnings_info.get("next_date") or "N/A",
        "Days to Earnings": earnings_info.get("days_to_earnings") if earnings_info.get("days_to_earnings") is not None else "N/A",
        "Earnings Risk": earnings_label,
        "EPS Estimate": earnings_info.get("eps_estimate", "N/A"),
        "Revenue Estimate": earnings_info.get("revenue_estimate", "N/A"),
        "Last EPS Surprise %": earnings_info.get("last_eps_surprise_pct", "N/A"),
        "Last Revenue Surprise %": earnings_info.get("last_revenue_surprise_pct", "N/A"),
        "Earnings Trend": earnings_setup_label,
        "Earnings Setup Score": earnings_setup_score,
        "Earnings Strategy": earnings_strategy,
        "Post-Earnings Label": post_earnings_label,
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
        "Company Name": "N/A",
        "_pivot": pivot,
        "_vcp": vcp,
    }
    row["AI Trading Notes"] = build_ai_trading_notes(row)
    return row


def style_scan_table(row: pd.Series) -> List[str]:
    """Color rows by action label for fast visual review."""
    if row["Trade"] == "YES":
        return ["background-color: #064e3b; color: #dcfce7; font-weight: 800"] * len(row)
    if row["WATCHLIST FLAG"] == "YES":
        return ["background-color: #1e3a8a; color: #dbeafe; font-weight: 700"] * len(row)

    colors = {
        "READY": "background-color: #14532d; color: #dcfce7; font-weight: 700",
        "PULLBACK ENTRY": "background-color: #172554; color: #dbeafe; font-weight: 700",
        "WATCH": "background-color: #422006; color: #fef9c3",
        "EXTENDED": "background-color: #7c2d12; color: #ffedd5",
        "FAILED": "background-color: #7f1d1d; color: #fee2e2",
    }
    return [colors.get(row["Action Label"], "")] * len(row)


def round_display_values(frame: pd.DataFrame) -> pd.DataFrame:
    """Round displayed prices, levels, scores, and percentages without changing calculations."""
    rounded = frame.copy()
    two_decimal_columns = [
        "close",
        "Pivot",
        "Distance to Pivot %",
        "Entry Trigger",
        "Stop Loss",
        "Risk %",
        "Target 2R",
        "Target 3R",
        "RR Ratio",
        "Final Score",
        "RS Score",
        "Sector Spread %",
        "MA10 Distance %",
        "MA20 Distance %",
    ]
    for column in two_decimal_columns:
        if column in rounded.columns:
            converted = pd.to_numeric(rounded[column], errors="coerce")
            if converted.notna().any():
                rounded[column] = converted.round(2).where(converted.notna(), rounded[column])
    return rounded


def escape_pdf_text(value: object) -> str:
    """Escape text for the app's lightweight built-in PDF export."""
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def dataframe_to_simple_pdf(frame: pd.DataFrame, title: str) -> bytes:
    """Create a compact text PDF without adding dependencies or touching scanner logic."""
    export = frame.fillna("N/A").astype(str)
    lines = [title, ""]
    lines.append(" | ".join(export.columns))
    lines.append("-" * 120)
    for _, row in export.iterrows():
        lines.append(" | ".join(str(row[column])[:44] for column in export.columns))

    pages = [lines[index : index + 42] for index in range(0, len(lines), 42)] or [[title]]
    objects: List[str] = []
    page_refs: List[int] = []
    font_obj_num = 3

    for page_lines in pages:
        content_lines = ["BT", "/F1 7 Tf", "36 792 Td", "9 TL"]
        for line in page_lines:
            content_lines.append(f"({escape_pdf_text(line)}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        content = "\n".join(content_lines)
        content_obj_num = len(objects) + 4
        page_obj_num = len(objects) + 5
        objects.append(
            f"{content_obj_num} 0 obj\n<< /Length {len(content.encode('latin-1', errors='ignore'))} >>\n"
            f"stream\n{content}\nendstream\nendobj\n"
        )
        objects.append(
            f"{page_obj_num} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 842 595] "
            f"/Contents {content_obj_num} 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> >>\n"
            "endobj\n"
        )
        page_refs.append(page_obj_num)

    base_objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        f"2 0 obj\n<< /Type /Pages /Kids [{' '.join(f'{ref} 0 R' for ref in page_refs)}] /Count {len(page_refs)} >>\nendobj\n",
        "3 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n",
    ]
    all_objects = base_objects + objects
    pdf = "%PDF-1.4\n"
    offsets = [0]
    for obj in all_objects:
        offsets.append(len(pdf.encode("latin-1", errors="ignore")))
        pdf += obj
    xref_pos = len(pdf.encode("latin-1", errors="ignore"))
    pdf += f"xref\n0 {len(all_objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += f"trailer\n<< /Size {len(all_objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    return pdf.encode("latin-1", errors="ignore")


def trade_plan_text(row: pd.Series) -> str:
    """Build a selected-row trade plan export from May scanner fields."""
    return "\n".join(
        [
            f"Ticker: {row.get('ticker', 'N/A')}",
            f"Sector / Industry: {row.get('Sector / Industry', 'N/A')}",
            f"Theme: {row.get('Theme', 'N/A')}",
            f"Setup Category: {row.get('Setup Category', 'N/A')}",
            f"Action: {row.get('Action Label', 'N/A')}",
            f"Trade: {row.get('Trade', 'N/A')} - {row.get('Trade Reason', 'N/A')}",
            f"Watchlist: {row.get('WATCHLIST FLAG', 'N/A')} - {row.get('Watchlist Reason', 'N/A')}",
            f"Final Score: {row.get('Final Score', 'N/A')}",
            f"Entry Trigger: {row.get('Entry Trigger', 'N/A')}",
            f"Stop Loss: {row.get('Stop Loss', 'N/A')}",
            f"Risk %: {row.get('Risk %', 'N/A')}",
            f"Target 2R: {row.get('Target 2R', 'N/A')}",
            f"Target 3R: {row.get('Target 3R', 'N/A')}",
            f"RS Score: {row.get('RS Score', 'N/A')}",
            f"VCP: {row.get('VCP Status', 'N/A')} ({row.get('Contractions', 'N/A')})",
            f"Earnings: {row.get('Earnings Risk', 'N/A')}",
            f"Notes: {row.get('Notes', 'N/A')}",
        ]
    )


def focus_summary_frame(frame: pd.DataFrame, reason_column: str) -> pd.DataFrame:
    """Build a compact top-five focus table for the daily summary."""
    if frame.empty:
        return pd.DataFrame()

    summary = frame.head(5).copy()
    summary["Reason"] = summary[reason_column]
    columns = [
        "ticker",
        "Setup Category",
        "Action Label",
        "Final Score",
        "Pivot",
        "Distance to Pivot %",
        "Entry Trigger",
        "Stop Loss",
        "Risk %",
        "RR Score",
        "Reason",
    ]
    return round_display_values(summary[columns])


def show_focus_group(title: str, frame: pd.DataFrame, reason_column: str) -> None:
    """Render one daily focus group as a small top-five table."""
    st.markdown(f"**{title}**")
    focus = focus_summary_frame(frame, reason_column)
    if focus.empty:
        st.caption("No current matches.")
    else:
        st.dataframe(focus, width="stretch", hide_index=True, height=220)


def select_ai_top_5(results: pd.DataFrame) -> pd.DataFrame:
    """Rule-based Top 5 ranking for alerts and top-pick cards."""
    if results.empty:
        return pd.DataFrame()
    ranked = results.copy()
    breakout_priority = {
        "CONFIRMED BREAKOUT": 0,
        "NEAR BREAKOUT": 1,
        "BREAKOUT IN PROGRESS": 2,
        "NO BREAKOUT": 3,
    }
    ranked["trade sort"] = np.where(ranked["Trade"] == "YES", 0, 1)
    ranked["watchlist sort"] = np.where(ranked["WATCHLIST FLAG"] == "YES", 0, 1)
    ranked["breakout sort"] = ranked["Breakout Alert"].map(breakout_priority).fillna(9)
    ranked["earnings sort"] = np.where(ranked["Earnings Risk"] == "HIGH RISK", 1, 0)
    ranked = ranked.sort_values(
        ["trade sort", "watchlist sort", "breakout sort", "Final Score", "RS Score", "Tightness Score", "Risk %", "earnings sort"],
        ascending=[True, True, True, False, False, False, True, True],
    )
    return ranked.head(5)


def alert_message(row: pd.Series) -> str:
    """Build the requested alert message format."""
    return (
        f"Ticker: {row.get('ticker', 'N/A')}\n"
        f"Action: {row.get('Action Label', 'N/A')}\n"
        f"Final Score: {row.get('Final Score', 'N/A')}\n"
        f"Pivot: {row.get('Pivot', 'N/A')}\n"
        f"Entry Trigger: {row.get('Entry Trigger', 'N/A')}\n"
        f"Stop Loss: {row.get('Stop Loss', 'N/A')}\n"
        f"Risk %: {row.get('Risk %', 'N/A')}\n"
        f"Target 2R: {row.get('Target 2R', 'N/A')}\n"
        f"Target 3R: {row.get('Target 3R', 'N/A')}\n"
        f"Breakout Alert: {row.get('Breakout Alert', 'N/A')}\n"
        f"Earnings Date: {row.get('Earnings Date', 'N/A')}\n"
        f"Earnings Risk: {row.get('Earnings Risk', 'N/A')}\n"
        f"AI Trading Notes: {row.get('AI Trading Notes', 'N/A')}"
    )


def send_telegram_message(token: str, chat_id: str, message: str) -> Tuple[bool, str]:
    """Send Telegram alert if credentials are present."""
    if not token or not chat_id:
        return False, "Telegram credentials missing."
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        return response.ok, "Telegram alert sent." if response.ok else response.text
    except Exception as exc:
        return False, f"Telegram error: {exc}"


def send_email_message(sender: str, password: str, recipient: str, message: str) -> Tuple[bool, str]:
    """Send email alert with common SMTP defaults."""
    if not sender or not password or not recipient:
        return False, "Email credentials missing."
    smtp_host = "smtp.gmail.com"
    smtp_port = 587
    try:
        email = EmailMessage()
        email["Subject"] = "VCP Swing Scanner Alert"
        email["From"] = sender
        email["To"] = recipient
        email.set_content(message)
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(email)
        return True, "Email alert sent."
    except Exception as exc:
        return False, f"Email error: {exc}"


def get_secret(name: str, default: str = "") -> str:
    """Read a Streamlit secret if available."""
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


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
            marker_color=np.where(chart_data["Close"] >= chart_data["Open"], "#22c55e", "#ef4444"),
            opacity=0.22,
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
                font=dict(size=11, color="#e5e7eb"),
                bgcolor="#111827",
                bordercolor="#334155",
            )

    figure.update_layout(
        title=f"{ticker} daily setup chart",
        height=600,
        margin=dict(l=12, r=12, t=48, b=24),
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="Price", gridcolor="#1f2937"),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
        legend=dict(orientation="h", y=1.02, x=0),
        template="plotly_dark",
        paper_bgcolor="#020617",
        plot_bgcolor="#0f172a",
        font=dict(color="#e5e7eb"),
        hovermode="x unified",
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
    tickers = tickers[:500]
    is_hk_scan = any(ticker.endswith(".HK") for ticker in tickers) or "HK" in mode
    context_tickers = ALL_CONTEXT_TICKERS if is_hk_scan else MARKET_TICKERS
    all_tickers = tuple(sorted(set(tickers + context_tickers)))
    raw_data = download_daily_data(all_tickers, period="18mo")

    spy_raw = raw_data.get("^HSI") if is_hk_scan and raw_data.get("^HSI") is not None else raw_data.get("SPY")
    indicator_data = {ticker: add_indicators(frame, spy_raw) for ticker, frame in raw_data.items()}
    market_data = {ticker: indicator_data[ticker] for ticker in context_tickers if ticker in indicator_data}
    if is_hk_scan:
        market_data["SPY"] = market_data.get("^HSI", pd.DataFrame())
        market_data["QQQ"] = market_data.get("2800.HK", pd.DataFrame())
    if is_hk_scan and mode == "HK Pro Market Scan":
        market_score, market_status, market_details = calculate_hk_market_score(market_data)
    else:
        market_score, market_status, market_details = calculate_market_score(market_data)
    sector_score, sector_details = calculate_sector_score(mode, market_data)
    market_caps = download_market_caps(tuple(tickers))
    earnings_data = download_earnings_data(tuple(tickers))

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
                    earnings_info=earnings_data.get(ticker, {}),
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


POSITIVE_IPO_KEYWORDS = (
    "oversubscribed", "hot ipo", "strong demand", "cornerstone", "ai", "semiconductor", "profitable",
    "tencent", "blackrock", "gic", "temasek", "hillhouse", "strong debut", "growth",
)
NEGATIVE_IPO_KEYWORDS = (
    "weak demand", "loss-making", "loss making", "cut valuation", "delayed listing", "regulatory risk",
    "low subscription", "poor grey market", "high valuation", "down round", "lawsuit", "cash burn",
)


def keyword_sentiment_score(text: str) -> int:
    """Lightweight IPO news sentiment from positive and negative keywords."""
    lowered = text.lower()
    positive_hits = sum(keyword in lowered for keyword in POSITIVE_IPO_KEYWORDS)
    negative_hits = sum(keyword in lowered for keyword in NEGATIVE_IPO_KEYWORDS)
    if positive_hits > negative_hits:
        return 1
    if negative_hits > positive_hits:
        return -1
    return 0


def ipo_score_label(score: float) -> str:
    """Translate a 0-10 IPO score into a subscription recommendation."""
    if score >= 8:
        return "STRONG SUBSCRIBE"
    if score >= 6:
        return "SMALL BET"
    return "AVOID"


def ipo_strategy_label(grey_market_premium_pct: float) -> str:
    """Choose IPO posture from grey-market premium bands."""
    if grey_market_premium_pct > 20:
        return "SCALP"
    if grey_market_premium_pct >= 10:
        return "FAST SWING"
    return "RISKY"


def grey_market_assessment(grey_price, ipo_price):
    """Calculate grey-market premium and classify first-day IPO risk posture."""
    grey_value = parse_price_midpoint(grey_price)
    ipo_value = parse_price_midpoint(ipo_price)
    if grey_value is None or ipo_value is None or ipo_value <= 0:
        return None, "Grey market unavailable"

    premium = (grey_value - ipo_value) / ipo_value * 100
    if premium >= 20:
        label = "HOT (SCALP)"
    elif premium >= 10:
        label = "STRONG"
    elif premium > 0:
        label = "WEAK POSITIVE"
    else:
        label = "NEGATIVE RISK"
    return round(premium, 2), label


def open_decision(open_price, ipo_price, vol_ratio, first_5m_high):
    """Classify IPO open behavior from opening gap and early volume confirmation."""
    open_value = parse_price_midpoint(open_price)
    ipo_value = parse_price_midpoint(ipo_price)
    volume_ratio = parse_first_number(vol_ratio) or 0
    _ = first_5m_high
    if open_value is None or ipo_value is None or ipo_value <= 0:
        return "Await open data"

    gap = (open_value - ipo_value) / ipo_value * 100
    if gap >= 15 and volume_ratio >= 1.5:
        return "OPEN STRONG -> HOLD / SCALE OUT"
    if gap >= 10:
        return "TAKE PROFIT PARTIAL"
    if gap > 0:
        return "SCALP ONLY"
    return "AVOID / CUT FAST"


def ipo_win_probability(grey_premium, oversub, sector_score, inst_score, sentiment_score):
    """Estimate IPO win probability from grey premium, demand, theme, institutions, and sentiment."""
    grey_premium = parse_first_number(grey_premium) or 0
    oversub = parse_first_number(oversub) or 0
    sector_score = parse_first_number(sector_score) or 0
    inst_score = parse_first_number(inst_score) or 0
    sentiment_score = parse_first_number(sentiment_score) or 0

    score = 0
    if grey_premium >= 20:
        score += 3
    elif grey_premium >= 10:
        score += 2
    elif grey_premium > 0:
        score += 1

    if oversub >= 50:
        score += 3
    elif oversub >= 20:
        score += 2
    elif oversub > 5:
        score += 1

    score += min(sector_score, 2)
    score += min(inst_score, 1)
    score += min(sentiment_score, 1)

    win_rate = 0.3 + (score / 10) * 0.5
    return round(win_rate * 100, 1)


def parse_first_number(value: object) -> float | None:
    """Extract the first numeric value from messy IPO source text."""
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def parse_price_midpoint(value: object) -> float | None:
    """Parse offer price or price range into a midpoint."""
    if value is None or pd.isna(value):
        return None
    numbers = [float(match) for match in re.findall(r"\d+(?:\.\d+)?", str(value).replace(",", ""))]
    if not numbers:
        return None
    return sum(numbers[:2]) / min(len(numbers), 2)


def format_price(value: float | None) -> str:
    """Format optional IPO price values."""
    return "N/A" if value is None or pd.isna(value) else f"{value:.2f}"


def ipo_theme_score(theme_text: str) -> int:
    """Score IPO theme heat out of 20."""
    text = theme_text.lower()
    hot = ("ai", "semiconductor", "robotics", "biotech", "platform", "cloud", "cyber", "ev", "battery")
    medium = ("health", "software", "consumer", "fintech", "energy", "industrial")
    if any(word in text for word in hot):
        return 20
    if any(word in text for word in medium):
        return 12
    return 6


def ipo_oversubscription_score(value: object) -> int:
    """Score IPO demand from oversubscription multiple out of 15."""
    multiple = parse_first_number(value)
    if multiple is None:
        return 6
    if multiple > 100:
        return 15
    if multiple >= 30:
        return 12
    if multiple >= 10:
        return 8
    return 3


def ipo_institutional_score(text: str) -> int:
    """Score cornerstone quality out of 15."""
    lowered = text.lower()
    top_names = ("blackrock", "hillhouse", "tencent", "alibaba", "gic", "temasek", "fidelity", "sovereign")
    if any(name in lowered for name in top_names):
        return 15
    if lowered and lowered != "n/a":
        return 8
    return 4


def ipo_underwriter_score(text: str) -> int:
    """Score sponsor or underwriter quality out of 10."""
    lowered = text.lower()
    top_names = ("goldman", "morgan stanley", "jpmorgan", "ubs", "cicc", "citic", "huatai", "bofa", "merrill")
    if any(name in lowered for name in top_names):
        return 10
    if lowered and lowered != "n/a":
        return 5
    return 3


def ipo_financial_score(text: str) -> int:
    """Simple financial-quality proxy out of 10."""
    lowered = text.lower()
    if "profitable" in lowered or "profit" in lowered and "loss" not in lowered:
        return 10
    if "growth" in lowered or "revenue" in lowered:
        return 7
    if "loss" in lowered:
        return 3
    return 5


def ipo_supply_score(shares_or_cap_text: str) -> int:
    """Simple supply-pressure proxy out of 10."""
    number = parse_first_number(shares_or_cap_text)
    if number is None:
        return 6
    if number < 50:
        return 10
    if number < 200:
        return 7
    return 4


def ipo_grey_score(premium_pct: float | None) -> int:
    """Score grey-market performance out of 5."""
    if premium_pct is None or pd.isna(premium_pct):
        return 2
    if premium_pct > 15:
        return 5
    if premium_pct >= 0:
        return 3
    return 0


def ipo_action_from_score(score: int) -> str:
    """Map 0-100 IPO score to application action."""
    if score >= 80:
        return "APPLY"
    if score >= 65:
        return "SMALL APPLY"
    if score >= 50:
        return "WATCH GREY MARKET"
    return "SKIP"


def ipo_first_day_plan(offer_price: float | None, grey_price: float | None, premium_pct: float | None) -> dict:
    """Generate first-day entry, stop, targets, and open strategy."""
    entry = grey_price or offer_price or 0
    if entry <= 0:
        return {"entry": "N/A", "stop loss": "N/A", "TP1": "N/A", "TP2": "N/A", "TP3": "N/A", "first day strategy": "Data unavailable"}

    stop_candidates = [entry * 0.93]
    if offer_price:
        stop_candidates.append(offer_price * 0.99)
    stop_loss = min(stop_candidates)
    tp1 = entry * 1.12
    tp2 = entry * 1.28
    tp3 = entry * 1.50

    if premium_pct is not None and premium_pct > 20:
        strategy = "Take profit quickly on open spike"
    elif premium_pct is not None and premium_pct >= 10:
        strategy = "Scalp / quick trade only"
    elif premium_pct is not None and premium_pct < 0:
        strategy = "Do not chase"
    else:
        strategy = "Wait for open strength and VWAP hold"

    return {
        "entry": round(entry, 2),
        "stop loss": round(stop_loss, 2),
        "TP1": round(tp1, 2),
        "TP2": round(tp2, 2),
        "TP3": round(tp3, 2),
        "first day strategy": strategy,
    }


def live_news_summary(*parts: str) -> Tuple[str, int]:
    """Summarize available source text and score keyword sentiment."""
    text = " ".join(part for part in parts if part and part != "N/A")
    score = keyword_sentiment_score(text)
    if not text.strip():
        return "News unavailable", score
    return text[:220], score


def score_live_ipo(record: dict) -> dict:
    """Normalize, score, and enrich one live IPO record."""
    offer_price = parse_price_midpoint(record.get("offer price"))
    grey_price = parse_price_midpoint(record.get("grey market price"))
    assessed_premium, grey_label = grey_market_assessment(record.get("grey market price"), record.get("offer price"))
    premium = record.get("grey market premium %")
    if premium is None:
        premium = assessed_premium
    premium = round(float(premium), 2) if premium is not None and not pd.isna(premium) else None
    open_proxy = record.get("expected open price") or record.get("grey market price")
    open_behavior = (
        open_decision(
            open_proxy,
            record.get("offer price"),
            record.get("opening volume ratio", 0),
            record.get("first 5m high", "N/A"),
        )
        if parse_price_midpoint(open_proxy) is not None
        else "Await open data"
    )

    news_summary, sentiment = live_news_summary(
        record.get("latest news summary", ""),
        record.get("theme", ""),
        record.get("cornerstone investors", ""),
        record.get("sponsor / underwriter", ""),
    )
    theme_points = ipo_theme_score(record.get("theme", "") + " " + record.get("company", ""))
    sector_probability_score = 2 if theme_points >= 20 else 1 if theme_points >= 12 else 0
    institutional_probability_score = 1 if (
        ipo_institutional_score(record.get("cornerstone investors", "")) >= 8
        or ipo_underwriter_score(record.get("sponsor / underwriter", "")) >= 5
    ) else 0
    win_probability = ipo_win_probability(
        premium or 0,
        record.get("oversubscription"),
        sector_probability_score,
        institutional_probability_score,
        sentiment,
    )
    score = (
        theme_points
        + 8
        + ipo_oversubscription_score(record.get("oversubscription"))
        + ipo_institutional_score(record.get("cornerstone investors", ""))
        + ipo_underwriter_score(record.get("sponsor / underwriter", ""))
        + ipo_financial_score(news_summary)
        + ipo_supply_score(record.get("shares offered", "") or record.get("minimum subscription amount", ""))
        + ipo_grey_score(premium)
    )
    score = int(max(0, min(score + sentiment * 3, 100)))
    plan = ipo_first_day_plan(offer_price, grey_price, premium)

    enriched = {
        "ticker": record.get("ticker", "N/A"),
        "company": record.get("company", "N/A"),
        "market": record.get("market", "N/A"),
        "status": record.get("status", "Data unavailable"),
        "offer price": record.get("offer price", "N/A"),
        "lot size": record.get("lot size", "N/A"),
        "minimum subscription amount": record.get("minimum subscription amount", "N/A"),
        "application deadline": record.get("application deadline", "N/A"),
        "listing date": record.get("listing date", record.get("expected IPO date", "N/A")),
        "sponsor / underwriter": record.get("sponsor / underwriter", "N/A"),
        "theme": record.get("theme", "N/A"),
        "cornerstone investors": record.get("cornerstone investors", "N/A"),
        "oversubscription": record.get("oversubscription", "N/A"),
        "cornerstone quality": "Strong" if ipo_institutional_score(record.get("cornerstone investors", "")) >= 12 else "Average",
        "grey market price": format_price(grey_price),
        "grey market premium %": "Grey market unavailable" if premium is None else round(premium, 2),
        "grey market label": grey_label,
        "grey market source": record.get("grey market source", "N/A"),
        "last updated": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
        "IPO score": score,
        "Win Probability %": win_probability,
        "action": ipo_action_from_score(score),
        "open decision": open_behavior,
        "latest news headline": record.get("latest news headline", news_summary),
        "latest news summary": news_summary,
        **plan,
    }
    return enriched


def unavailable_ipo_row(market: str, reason: str) -> dict:
    """Return a safe placeholder row when live IPO sources fail."""
    return score_live_ipo(
        {
            "ticker": "N/A",
            "company": f"{market} IPO data unavailable",
            "market": market,
            "status": reason,
            "offer price": "N/A",
            "theme": "N/A",
            "latest news summary": reason,
        }
    )


def manual_fallback_ipo_rows(market: str, reason: str) -> pd.DataFrame:
    """Return editable-looking fallback rows with all common IPO fields."""
    templates = [
        ("Manual IPO 1", "applying / upcoming"),
        ("Manual IPO 2", "grey market / upcoming"),
        ("Manual IPO 3", "watchlist"),
    ]
    rows = []
    for index, (company, status) in enumerate(templates, start=1):
        rows.append(
            score_live_ipo(
                {
                    "ticker": f"MANUAL{index}",
                    "company": company,
                    "market": market,
                    "status": f"{status} - live data unavailable",
                    "offer price": "N/A",
                    "lot size": "N/A",
                    "minimum subscription amount": "N/A",
                    "application deadline": "N/A",
                    "listing date": "N/A",
                    "sponsor / underwriter": "N/A",
                    "cornerstone investors": "N/A",
                    "oversubscription": "N/A",
                    "theme": "Manual fallback",
                    "latest news summary": reason,
                    "grey market price": "N/A",
                    "grey market source": "Grey market unavailable",
                }
            )
        )
    return pd.DataFrame(rows)


def source_debug(name: str, ok: bool, count: int = 0, error: str = "") -> dict:
    """Build a source debug entry."""
    return {"source": name, "ok": ok, "count": count, "error": error}


def safe_read_html_tables(html: str) -> List[pd.DataFrame]:
    """Read HTML tables with multiple parsers so lxml failure is not fatal."""
    tables: List[pd.DataFrame] = []
    for flavor in ("lxml", "html5lib", "bs4"):
        try:
            tables = pd.read_html(StringIO(html), flavor=flavor)
            if tables:
                return tables
        except Exception:
            continue
    return tables


def clean_hk_ticker(text: str) -> str:
    """Extract a Hong Kong ticker from source text."""
    match = re.search(r"\b(\d{4,5})\.?\s*(?:HK|HKG)[A-Za-z]*\b", text, flags=re.IGNORECASE)
    return f"{match.group(1)[-4:]}.HK" if match else "N/A"


def clean_ipo_text(value: object, default: str = "N/A") -> str:
    """Return a compact text value while preserving clear missing fields."""
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "n/a", "-"}:
        return default
    return re.sub(r"\s+", " ", text)


def clean_hk_company_name(text: str, ticker: str) -> str:
    """Remove ticker and quote-page noise from a Hong Kong IPO company field."""
    company = clean_ipo_text(text)
    if company == "N/A":
        return company
    company = re.sub(r"\bGrey Market Today\b|\bMarket Today\b|\bDetail Quote\b", "", company, flags=re.IGNORECASE)
    company = re.sub(r"\b\d{4,5}\.?(?:HK|HKG)?[A-Za-z]*\b", "", company, flags=re.IGNORECASE)
    if ticker != "N/A":
        company = company.replace(ticker.replace(".HK", ""), "")
    return clean_ipo_text(company)


def value_by_keywords(row: pd.Series, keywords: Tuple[str, ...], default: str = "N/A") -> str:
    """Find a row value whose column name matches one of the keywords."""
    for column, value in row.items():
        column_text = str(column).lower()
        cleaned = clean_ipo_text(value)
        if any(keyword in column_text for keyword in keywords) and cleaned != "N/A":
            return cleaned
    return default


def looks_like_hk_ipo_table(table: pd.DataFrame) -> bool:
    """Detect source tables that contain actual IPO rows, not page navigation."""
    if table.empty or table.shape[1] < 2:
        return False

    columns_text = " ".join(str(column).lower() for column in table.columns)
    sample_text = " ".join(str(value).lower() for value in table.head(6).to_numpy().flatten())
    haystack = f"{columns_text} {sample_text}"

    chrome_keywords = (
        "real-time futures",
        "local indices",
        "world indices",
        "top 20",
        "interactive chart",
        "company announcement",
        "short selling",
        "sitemap",
        "disclaimer",
    )
    strong_ipo_keywords = (
        "offer price",
        "listing price",
        "lot size",
        "entry fee",
        "closing date",
        "grey market date",
        "listing date",
        "over-sub",
        "sponsor",
        "ipo listing",
    )
    if any(keyword in haystack for keyword in chrome_keywords) and not any(keyword in haystack for keyword in strong_ipo_keywords):
        return False

    signal_count = sum(keyword in haystack for keyword in strong_ipo_keywords)
    has_company_signal = any(keyword in columns_text for keyword in ("name", "company", "stock"))
    has_hk_code = bool(re.search(r"\b\d{4,5}\.?\s*(?:hk|hkg)\b", haystack))
    has_code_column = "code" in columns_text
    has_summary_price = "offer price" in columns_text or "listing price" in columns_text or "ipo price" in columns_text
    has_summary_dates = "listing date" in columns_text or "ipo listing" in columns_text
    return signal_count >= 2 and has_company_signal and (has_code_column or has_hk_code) and (has_summary_price or has_summary_dates)


def looks_like_ipo_row(joined: str, ticker: str, company: str) -> bool:
    """Keep only rows with enough IPO-specific information to be actionable."""
    text = joined.lower()
    if company == "N/A" and ticker == "N/A":
        return False
    if any(keyword in text for keyword in ("last update:", "sitemap", "disclaimer", "no related information")):
        return False
    row_signals = sum(
        keyword in text
        for keyword in (
            "grey market",
            "listing",
            "offer",
            "health care",
            "biotechnology",
            "hardware",
            "software",
            "sponsor",
            "lot",
            "entry fee",
        )
    )
    has_date = bool(re.search(r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}", text))
    has_price = bool(re.search(r"\b\d+(?:\.\d+)?(?:\s*-\s*\d+(?:\.\d+)?)?\b", text))
    return row_signals >= 1 and (ticker != "N/A" or has_date or has_price)


def normalize_hk_ipo_table(table: pd.DataFrame, source_name: str, source_url: str) -> List[dict]:
    """Convert a messy HK IPO HTML table into scored IPO records."""
    table = table.fillna("N/A")
    if isinstance(table.columns, pd.MultiIndex):
        table.columns = [" ".join(str(part) for part in column if str(part) != "nan") for column in table.columns]
    if not looks_like_hk_ipo_table(table):
        return []

    records: List[dict] = []
    for _, row in table.head(40).iterrows():
        values = [clean_ipo_text(value) for value in row.tolist()]
        joined = " | ".join(values)
        if len(joined) < 10:
            continue
        ticker = clean_hk_ticker(joined)
        company = value_by_keywords(row, ("company", "name", "stock"), values[0] if values else "N/A")
        company = clean_hk_company_name(company, ticker)
        if not looks_like_ipo_row(joined, ticker, company):
            continue
        offer_price = value_by_keywords(row, ("offer price", "listing price", "ipo price", "price range"), "N/A")
        lot_size = value_by_keywords(row, ("lot size", "board lot"), "N/A")
        minimum = value_by_keywords(row, ("entry fee", "minimum subscription", "subscription amount"), "N/A")
        deadline = value_by_keywords(row, ("closing date", "application deadline", "deadline"), "N/A")
        listing = value_by_keywords(row, ("listing date", "debut date", "ipo listing"), "N/A")
        sponsor = value_by_keywords(row, ("sponsor", "underwriter", "bookrunner"), "N/A")
        industry = value_by_keywords(row, ("industry", "sector", "business"), joined)
        oversub = value_by_keywords(row, ("over-sub", "oversub", "oversubscription"), "N/A")
        grey = value_by_keywords(row, ("phillip grey market", "futu (hk) grey market", "grey market price", "gray market price", "暗盤價"), "N/A")
        records.append(
            score_live_ipo(
                {
                    "ticker": ticker,
                    "company": company,
                    "market": "HK",
                    "status": "applying / upcoming",
                    "offer price": offer_price,
                    "lot size": lot_size,
                    "minimum subscription amount": minimum,
                    "application deadline": deadline,
                    "listing date": listing,
                    "sponsor / underwriter": sponsor,
                    "cornerstone investors": value_by_keywords(row, ("cornerstone", "investor"), "N/A"),
                    "oversubscription": oversub,
                    "theme": industry,
                    "latest news summary": f"{source_name}: {joined[:180]}",
                    "grey market price": grey,
                    "grey market source": "Grey market unavailable" if grey == "N/A" else source_name,
                }
            )
        )
    return records


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_us_live_ipos() -> pd.DataFrame:
    """Best-effort US IPO calendar fetch from Nasdaq public calendar endpoint."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/ipos",
    }
    date_key = pd.Timestamp.today().strftime("%Y-%m")
    try:
        response = requests.get(
            f"https://api.nasdaq.com/api/ipo/calendar?date={date_key}",
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", {}).get("priced", {}).get("rows", [])
        rows += payload.get("data", {}).get("upcoming", {}).get("rows", [])
        records = []
        for row in rows:
            company = row.get("companyName") or row.get("name") or "N/A"
            ticker = row.get("proposedTickerSymbol") or row.get("symbol") or "N/A"
            price_range = row.get("proposedSharePrice") or row.get("price") or "N/A"
            records.append(
                score_live_ipo(
                    {
                        "ticker": ticker,
                        "company": company,
                        "market": "US",
                        "status": "upcoming",
                        "offer price": price_range,
                        "listing date": row.get("expectedPriceDate") or row.get("pricedDate") or "N/A",
                        "application deadline": "N/A",
                        "shares offered": row.get("sharesOffered", "N/A"),
                        "sponsor / underwriter": row.get("underwriters", "N/A"),
                        "theme": row.get("sector") or row.get("industry") or "N/A",
                        "latest news summary": f"{company} IPO calendar entry from Nasdaq.",
                    }
                )
            )
        return pd.DataFrame(records) if records else pd.DataFrame([unavailable_ipo_row("US", "Data unavailable")])
    except Exception as exc:
        return pd.DataFrame([unavailable_ipo_row("US", f"Data unavailable: {exc}")])


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_hk_live_ipos() -> Tuple[pd.DataFrame, dict]:
    """Best-effort HK IPO scrape with ordered fallbacks and visible debug metadata."""
    sources = [
        ("HKEX new listings", "https://www.hkexnews.hk/app/appindex.html"),
        ("AAStocks IPO Center", "https://www.aastocks.com/en/stocks/market/ipo/upcomingipo/company-summary"),
        ("ETNet IPO Center", "https://www.etnet.com.hk/www/eng/stocks/ipo/ipo.php"),
        ("Investing.com IPO Calendar", "https://www.investing.com/ipo-calendar/"),
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36"}
    failed: List[dict] = []
    last_updated = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    for source_name, url in sources:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            tables = safe_read_html_tables(response.text)
            records: List[dict] = []
            for table in tables:
                records.extend(normalize_hk_ipo_table(table, source_name, url))
            deduped = list({(record["ticker"], record["company"]): record for record in records}.values())
            if deduped:
                debug = {
                    "source_used": source_name,
                    "last_updated": last_updated,
                    "count": len(deduped),
                    "failed_sources": failed,
                }
                return pd.DataFrame(deduped), debug
            failed.append(source_debug(source_name, False, 0, "No usable IPO rows found"))
        except Exception as exc:
            failed.append(source_debug(source_name, False, 0, str(exc)))

    try:
        import feedparser

        feed = feedparser.parse("https://finance.yahoo.com/rss/ipo")
        records = []
        for entry in feed.entries[:10]:
            title = entry.get("title", "N/A")
            records.append(
                score_live_ipo(
                    {
                        "ticker": "N/A",
                        "company": title[:80],
                        "market": "HK",
                        "status": "news watch",
                        "offer price": "N/A",
                        "theme": title,
                        "latest news summary": title,
                        "grey market price": "N/A",
                        "grey market source": "Grey market unavailable",
                    }
                )
            )
        if records:
            debug = {
                "source_used": "Yahoo Finance / RSS news search",
                "last_updated": last_updated,
                "count": len(records),
                "failed_sources": failed,
            }
            return pd.DataFrame(records), debug
        failed.append(source_debug("Yahoo Finance / RSS news search", False, 0, "No feed entries"))
    except Exception as exc:
        failed.append(source_debug("Yahoo Finance / RSS news search", False, 0, str(exc)))

    reason = "All live sources failed; using manual fallback table."
    debug = {
        "source_used": "Manual fallback table",
        "last_updated": last_updated,
        "count": 3,
        "failed_sources": failed,
    }
    return manual_fallback_ipo_rows("HK", reason), debug


def render_status_card(title: str, value: str, tone: str, detail: str = "") -> None:
    """Render a dark IPO summary card with green, yellow, or red accent color."""
    colors = {"green": "#22c55e", "yellow": "#eab308", "red": "#ef4444"}
    color = colors.get(tone, "#94a3b8")
    st.markdown(
        f"""
        <div style="background:#111827;border:1px solid #243244;border-left:5px solid {color};
                    border-radius:10px;padding:14px 16px;margin-bottom:10px;">
            <div style="color:#94a3b8;font-size:13px;">{title}</div>
            <div style="color:{color};font-size:24px;font-weight:800;">{value}</div>
            <div style="color:#cbd5e1;font-size:13px;">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_ipo_manual_calculator() -> None:
    """Render the manual IPO scoring and trading-plan calculator."""
    st.markdown(
        """
        <style>
        .ipo-panel {
            background: #0f172a;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 18px;
            color: #e5e7eb;
        }
        .ipo-panel h3 { color: #f8fafc; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.caption("Manual IPO planning module with grey-market pricing, scoring, risk, and strategy labels.")

    input_col, score_col = st.columns([1, 1])
    with input_col:
        st.subheader("IPO Input")
        ipo_name = st.text_input("IPO name", value="Example AI Robotics IPO")
        ipo_ticker = st.text_input("Ticker", value="IPOX").upper()
        price_low, price_high = st.columns(2)
        listing_low = price_low.number_input("Listing price lower", min_value=0.0, value=10.0, step=0.1)
        listing_high = price_high.number_input("Listing price upper", min_value=0.0, value=12.0, step=0.1)
        lot_size = st.number_input("Lot size", min_value=1, value=100, step=10)
        min_subscription = st.number_input("Minimum subscription amount", min_value=0.0, value=1200.0, step=100.0)
        lots = st.number_input("Number of lots", min_value=1, value=1, step=1)

        st.subheader("Grey Market")
        grey_low, grey_high = st.columns(2)
        grey_market_lower = grey_low.number_input("Grey market price lower", min_value=0.0, value=13.0, step=0.1)
        grey_market_upper = grey_high.number_input("Grey market price upper", min_value=0.0, value=15.0, step=0.1)
        expected_open = st.number_input("Expected open price", min_value=0.0, value=14.0, step=0.1)
        st.subheader("Opening Behavior")
        opening_volume_ratio = st.number_input("Opening volume ratio vs normal", min_value=0.0, value=1.5, step=0.1)
        first_5m_high = st.number_input("First 5-minute high", min_value=0.0, value=14.5, step=0.1)

    with score_col:
        st.subheader("IPO Scoring Inputs")
        revenue_growth = st.slider("Revenue growth %", min_value=-50, max_value=300, value=40, step=5)
        profitability = st.selectbox("Profitability", ["Profitable", "Near breakeven", "Loss making"])
        industry = st.selectbox("Industry", ["AI", "Biotech", "Cybersecurity", "Cloud", "Consumer", "Industrial", "Other"])
        oversubscription = st.number_input("Oversubscription multiplier", min_value=0.0, value=10.0, step=1.0)
        news_text = st.text_area(
            "News / sentiment keywords",
            value="strong demand, AI, oversubscribed",
            help="Positive: oversubscribed, hot IPO, AI, strong demand. Negative: loss making, weak demand, cut valuation.",
            height=100,
        )
        social_buzz = st.slider("Social buzz score", min_value=1, max_value=3, value=2)
        cornerstone = st.selectbox("Cornerstone investors", ["Strong", "Some", "None"])
        underwriter = st.selectbox("Underwriter strength", ["Goldman / Morgan Stanley / JPM", "Major bank", "Regional / unknown"])
        similar_performance = st.selectbox("Similar IPO past performance", ["Strong", "Mixed", "Weak"])

    listing_reference = (listing_low + listing_high) / 2 if listing_high > 0 else listing_low
    grey_entry = (grey_market_lower + grey_market_upper) / 2 if grey_market_upper > 0 else grey_market_lower
    grey_entry = grey_entry if grey_entry > 0 else expected_open
    expected_return_pct = ((expected_open - listing_reference) / listing_reference * 100) if listing_reference > 0 else 0
    assessed_grey_premium, grey_market_label = grey_market_assessment(grey_entry, listing_reference)
    grey_market_premium_pct = assessed_grey_premium if assessed_grey_premium is not None else 0
    risk_low_pct = ((grey_market_lower - listing_reference) / listing_reference * 100) if listing_reference > 0 else 0
    risk_high_pct = ((grey_market_upper - listing_reference) / listing_reference * 100) if listing_reference > 0 else 0

    fundamentals_score = 0.0
    fundamentals_score += 1 if revenue_growth >= 50 else 0.5 if revenue_growth >= 20 else 0
    fundamentals_score += 1 if profitability == "Profitable" else 0.5 if profitability == "Near breakeven" else 0
    fundamentals_score += 1 if industry in {"AI", "Biotech", "Cybersecurity", "Cloud"} else 0.5 if industry == "Industrial" else 0

    news_score = keyword_sentiment_score(news_text)
    sentiment_score = 0.0
    sentiment_score += 2 if oversubscription > 50 else 1 if oversubscription >= 10 else 0
    sentiment_score += 1 if news_score > 0 else 0.5 if news_score == 0 else 0
    sentiment_score += social_buzz / 3

    institutional_score = 0.0
    institutional_score += 1 if cornerstone == "Strong" else 0.5 if cornerstone == "Some" else 0
    institutional_score += 1 if underwriter == "Goldman / Morgan Stanley / JPM" else 0.5 if underwriter == "Major bank" else 0

    technical_ipo_score = {"Strong": 2.0, "Mixed": 1.0, "Weak": 0.0}[similar_performance]
    ipo_score = round(min(fundamentals_score + sentiment_score + institutional_score + technical_ipo_score, 10), 1)
    recommendation = ipo_score_label(ipo_score)

    entry_price = grey_entry
    breakout_level = expected_open * 1.03
    stop_loss = min(entry_price * 0.93, listing_reference * 0.99) if listing_reference > 0 else entry_price * 0.93
    risk_pct = ((entry_price - stop_loss) / entry_price * 100) if entry_price > 0 else 0
    tp1 = entry_price * 1.15
    tp2 = entry_price * 1.30
    tp3 = entry_price * 1.50
    shares = lots * lot_size
    total_capital = max(min_subscription * lots, shares * entry_price)
    max_risk = max(entry_price - stop_loss, 0) * shares
    reward_tp1 = max(tp1 - entry_price, 0) * shares
    reward_tp2 = max(tp2 - entry_price, 0) * shares
    reward_tp3 = max(tp3 - entry_price, 0) * shares
    strategy_label = ipo_strategy_label(grey_market_premium_pct)
    open_behavior = open_decision(expected_open, listing_reference, opening_volume_ratio, first_5m_high)
    sector_probability_score = 2 if industry in {"AI", "Biotech", "Cybersecurity", "Cloud"} else 1 if industry in {"Industrial", "Consumer"} else 0
    institutional_probability_score = 1 if cornerstone != "None" or underwriter != "Regional / unknown" else 0
    win_probability = ipo_win_probability(
        grey_market_premium_pct,
        oversubscription,
        sector_probability_score,
        institutional_probability_score,
        news_score,
    )

    tone = "green" if recommendation == "STRONG SUBSCRIBE" else "yellow" if recommendation == "SMALL BET" else "red"
    win_tone = "green" if win_probability >= 65 else "yellow" if win_probability >= 50 else "red"
    strategy_detail = "Flip Strategy: sell into open spike. Hold Strategy: only if price holds breakout level with strong volume."
    if strategy_label == "FAST SWING":
        strategy_detail = "Fast Swing: hold only while price stays above breakout or grey-market support."
    elif strategy_label == "RISKY":
        strategy_detail = "Risky: weak grey-market premium. Reduce size or avoid until price confirms."

    st.subheader("IPO Output Panel")
    summary_cols = st.columns(6)
    with summary_cols[0]:
        render_status_card("IPO Score", f"{ipo_score}/10", tone, recommendation)
    with summary_cols[1]:
        render_status_card("Win Probability", f"{win_probability:.1f}%", win_tone, "Grey premium + demand model")
    with summary_cols[2]:
        render_status_card("Grey Market", grey_market_label, "green" if grey_market_premium_pct >= 10 else "yellow" if grey_market_premium_pct > 0 else "red", f"{grey_market_premium_pct:.2f}% premium")
    with summary_cols[3]:
        render_status_card("Risk", f"{risk_pct:.2f}%", "red" if risk_pct > 8 else "yellow")
    with summary_cols[4]:
        render_status_card("Strategy Label", strategy_label, tone, strategy_detail)
    with summary_cols[5]:
        open_tone = "green" if open_behavior == "OPEN STRONG -> HOLD / SCALE OUT" else "yellow" if open_behavior in {"TAKE PROFIT PARTIAL", "SCALP ONLY"} else "red"
        render_status_card("Open Decision", open_behavior, open_tone, "Gap + opening volume rule")

    plan_col, risk_col = st.columns([1.2, 1])
    with plan_col:
        st.markdown("### Trading Plan")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Plan Item": "IPO", "Value": f"{ipo_name} ({ipo_ticker})"},
                    {"Plan Item": "Grey market entry price", "Value": f"{entry_price:.2f}"},
                    {"Plan Item": "IPO open breakout level", "Value": f"{breakout_level:.2f}"},
                    {"Plan Item": "Stop loss", "Value": f"{stop_loss:.2f}"},
                    {"Plan Item": "TP1", "Value": f"{tp1:.2f} (+15%)"},
                    {"Plan Item": "TP2", "Value": f"{tp2:.2f} (+30%)"},
                    {"Plan Item": "TP3", "Value": f"{tp3:.2f} (+50%, strong momentum only)"},
                    {"Plan Item": "Open Decision", "Value": open_behavior},
                    {"Plan Item": "Flip Strategy", "Value": "Sell into open spike or failed breakout."},
                    {"Plan Item": "Hold Strategy", "Value": "Only if strong trend holds above breakout level."},
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    with risk_col:
        st.markdown("### Risk Calculation")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Metric": "Lots", "Value": f"{lots}"},
                    {"Metric": "Shares", "Value": f"{shares}"},
                    {"Metric": "Total capital used", "Value": f"{total_capital:.2f}"},
                    {"Metric": "Max risk", "Value": f"{max_risk:.2f}"},
                    {"Metric": "Reward at TP1", "Value": f"{reward_tp1:.2f}"},
                    {"Metric": "Reward at TP2", "Value": f"{reward_tp2:.2f}"},
                    {"Metric": "Reward at TP3", "Value": f"{reward_tp3:.2f}"},
                    {"Metric": "Grey market premium", "Value": f"{grey_market_premium_pct:.2f}%"},
                    {"Metric": "Grey market assessment", "Value": grey_market_label},
                    {"Metric": "Expected open return", "Value": f"{expected_return_pct:.2f}%"},
                    {"Metric": "Opening volume ratio", "Value": f"{opening_volume_ratio:.2f}x"},
                    {"Metric": "First 5-minute high", "Value": f"{first_5m_high:.2f}"},
                    {"Metric": "IPO win probability", "Value": f"{win_probability:.1f}%"},
                    {"Metric": "Grey market risk range", "Value": f"{risk_low_pct:.2f}% to {risk_high_pct:.2f}%"},
                    {"Metric": "Keyword sentiment", "Value": f"{news_score}"},
                ]
            ),
            width="stretch",
            hide_index=True,
        )

    st.caption("IPO module is for planning only. Confirm allotment, live prices, fees, liquidity, and exchange rules before trading.")


LIVE_IPO_COLUMNS = [
    "ticker",
    "company",
    "market",
    "status",
    "offer price",
    "lot size",
    "minimum subscription amount",
    "application deadline",
    "listing date",
    "sponsor / underwriter",
    "theme",
    "cornerstone investors",
    "oversubscription",
    "cornerstone quality",
    "grey market price",
    "grey market premium %",
    "grey market label",
    "grey market source",
    "IPO score",
    "Win Probability %",
    "action",
    "open decision",
    "entry",
    "stop loss",
    "TP1",
    "TP2",
    "first day strategy",
    "latest news headline",
    "latest news summary",
    "last updated",
]


def live_ipo_summary_cards(data: pd.DataFrame, market: str) -> None:
    """Show top IPO cards for the live IPO watchlist."""
    if data.empty:
        st.info("Data unavailable")
        return
    valid = data[data["ticker"] != "N/A"].copy()
    source = valid if not valid.empty else data
    best = source.sort_values("IPO score", ascending=False).iloc[0]
    grey_numeric = pd.to_numeric(source["grey market premium %"], errors="coerce")
    grey_winner = source.loc[grey_numeric.idxmax()] if grey_numeric.notna().any() else None
    high_risk = source.sort_values("IPO score", ascending=True).iloc[0]

    cards = st.columns(5)
    with cards[0]:
        render_status_card("Best IPO to apply", best["ticker"], "green" if best["IPO score"] >= 80 else "yellow", best["action"])
    with cards[1]:
        render_status_card(f"Hottest {market} IPO", best["company"][:24], "green", f"Score {best['IPO score']}")
    with cards[2]:
        if market == "HK" and grey_winner is not None:
            render_status_card("Grey market winner", grey_winner["ticker"], "green", f"{grey_winner['grey market premium %']}%")
        else:
            render_status_card("Grey market winner", "N/A", "yellow", "Grey market unavailable")
    with cards[3]:
        render_status_card("High risk IPO", high_risk["ticker"], "red", high_risk["action"])
    with cards[4]:
        render_status_card("Live source", "Best effort", "yellow", "Confirm with broker/prospectus")


def render_ipo_debug(debug: dict | None) -> None:
    """Show visible live IPO source diagnostics."""
    if not debug:
        return
    with st.expander("Live IPO source debug", expanded=True):
        st.write(f"Source used: {debug.get('source_used', 'N/A')}")
        st.write(f"Last updated: {debug.get('last_updated', 'N/A')}")
        st.write(f"Number of IPOs found: {debug.get('count', 0)}")
        failed = debug.get("failed_sources", [])
        if failed:
            st.write("Failed sources:")
            st.dataframe(pd.DataFrame(failed), width="stretch", hide_index=True)
        else:
            st.caption("No failed sources before the selected source.")


def render_live_ipo_table(market: str, data: pd.DataFrame, debug: dict | None = None) -> None:
    """Render filters, grey-market override, and the live IPO table."""
    st.subheader(f"{market} IPO Live Watchlist")
    if data.empty:
        st.warning("Data unavailable")
        return

    render_ipo_debug(debug)
    live_ipo_summary_cards(data, market)

    filter_cols = st.columns(5)
    only_applying = filter_cols[0].checkbox("Show only applying IPOs", value=False, key=f"{market}_ipo_applying")
    only_hk = filter_cols[1].checkbox("Show only HK IPOs", value=(market == "HK"), key=f"{market}_ipo_hk")
    only_us = filter_cols[2].checkbox("Show only US IPOs", value=(market == "US"), key=f"{market}_ipo_us")
    only_apply = filter_cols[3].checkbox("Show only APPLY / SMALL APPLY", value=False, key=f"{market}_ipo_apply")
    only_grey = filter_cols[4].checkbox("Show only grey market available", value=False, key=f"{market}_ipo_grey")

    display = data.copy()
    if only_applying:
        display = display[display["status"].str.contains("applying", case=False, na=False)]
    if only_hk:
        display = display[display["market"] == "HK"]
    if only_us:
        display = display[display["market"] == "US"]
    if only_apply:
        display = display[display["action"].isin(["APPLY", "SMALL APPLY"])]
    if only_grey:
        display = display[pd.to_numeric(display["grey market premium %"], errors="coerce").notna()]

    if market == "HK" and not data.empty:
        with st.expander("Manual grey market override"):
            tickers = data["ticker"].tolist()
            selected = st.selectbox("IPO ticker", tickers, key=f"{market}_grey_ticker")
            override_price = st.number_input("Grey market price override", min_value=0.0, value=0.0, step=0.01, key=f"{market}_grey_price")
            override_source = st.text_input("Grey market source", value="Manual override", key=f"{market}_grey_source")
            if st.button("Apply grey market override", key=f"{market}_grey_apply") and override_price > 0:
                mask = display["ticker"] == selected
                offer = parse_price_midpoint(display.loc[mask, "offer price"].iloc[0]) if mask.any() else None
                premium = ((override_price - offer) / offer * 100) if offer else None
                display.loc[mask, "grey market price"] = f"{override_price:.2f}"
                display.loc[mask, "grey market premium %"] = round(premium, 2) if premium is not None else "N/A"
                display.loc[mask, "grey market source"] = override_source

    if display.empty:
        st.info("No IPOs match the current filters.")
    else:
        st.dataframe(display.reindex(columns=LIVE_IPO_COLUMNS, fill_value="N/A"), width="stretch", hide_index=True)

    st.caption(
        "IPO data, grey market price, news and sentiment may be delayed or inaccurate. "
        "Always confirm with broker or official prospectus before applying or trading."
    )


def render_ipo_scanner() -> None:
    """Render live IPO discovery plus the existing manual calculator."""
    st.caption("Automatic IPO discovery is best-effort. Manual override remains available when live data is unavailable.")
    hk_tab, us_tab, manual_tab = st.tabs(["HK IPO Live", "US IPO Live", "IPO Manual Calculator"])

    with hk_tab:
        hk_data, hk_debug = fetch_hk_live_ipos()
        render_live_ipo_table("HK", hk_data, hk_debug)

    with us_tab:
        us_data = fetch_us_live_ipos()
        render_live_ipo_table("US", us_data)

    with manual_tab:
        render_ipo_manual_calculator()


def combined_session_results() -> pd.DataFrame:
    """Combine latest scan outputs from any scanner tab."""
    frames = []
    for key in ("us_results", "hk_results", "swing_results"):
        frame = st.session_state.get(key)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["ticker"], keep="first")


def render_top_5_trades() -> None:
    """Render AI selected top five trades as rule-based cards."""
    st.subheader("AI Selected Top 5 Trades")
    results = combined_session_results()
    if results.empty:
        st.info("Run a US or HK scan first, then return here for Top 5 picks.")
        return

    picks = select_ai_top_5(results)
    cols = st.columns(5)
    for index, (_, row) in enumerate(picks.iterrows()):
        with cols[index % 5]:
            label = ai_trade_label(row)
            tone = "red" if label in {"TOO EXTENDED", "EARNINGS RISK"} else "green" if label == "BEST BUY SETUP" else "yellow"
            render_status_card(row["ticker"], label, tone, f"Final {row['Final Score']} | {row['Action Label']}")
            st.write(f"Company: {row.get('Company Name', 'N/A')}")
            st.write(f"Theme: {row.get('Sector ETF', 'N/A')}")
            st.write(f"Close: {row.get('close', 'N/A')}")
            st.write(f"VCP: {row.get('VCP Status', 'N/A')}")
            st.write(f"Pivot: {row.get('Pivot', 'N/A')}")
            st.write(f"Entry: {row.get('Entry Trigger', 'N/A')}")
            st.write(f"Stop: {row.get('Stop Loss', 'N/A')}")
            st.write(f"Risk: {row.get('Risk %', 'N/A')}%")
            st.write(f"2R / 3R: {row.get('Target 2R', 'N/A')} / {row.get('Target 3R', 'N/A')}")
            st.write(f"Earnings: {row.get('Earnings Date', 'N/A')} ({row.get('Earnings Risk', 'N/A')})")
            st.caption(row.get("AI Trading Notes", ""))


def render_alerts() -> None:
    """Render Telegram and email alert settings plus send buttons."""
    st.subheader("Breakout Alert System")
    results = combined_session_results()
    with st.sidebar:
        st.header("Alert Settings")
        enable_telegram = st.toggle("Enable Telegram alert", value=False, key="alert_telegram_on")
        telegram_token = st.text_input("Telegram bot token", value=get_secret("telegram_bot_token"), type="password", key="telegram_token")
        telegram_chat_id = st.text_input("Telegram chat ID", value=get_secret("telegram_chat_id"), key="telegram_chat_id")
        enable_email = st.toggle("Enable Email alert", value=False, key="alert_email_on")
        smtp_email = st.text_input("SMTP email", value=get_secret("smtp_email"), key="smtp_email")
        smtp_password = st.text_input("SMTP password", value=get_secret("smtp_password"), type="password", key="smtp_password")
        recipient_email = st.text_input("Recipient email", value=get_secret("recipient_email"), key="recipient_email")

    if results.empty:
        st.info("Run a scan first. Alerts use the latest US/HK scanner results.")
        return

    picks = select_ai_top_5(results)
    st.write("Today alert candidates:")
    st.dataframe(round_display_values(picks[["ticker", "Action Label", "Final Score", "Breakout Alert", "Earnings Date", "Earnings Risk", "AI Trading Notes"]]), width="stretch", hide_index=True)

    def send_message(message: str) -> None:
        sent_any = False
        if enable_telegram:
            ok, status = send_telegram_message(telegram_token, telegram_chat_id, message)
            st.success(status) if ok else st.warning(status)
            sent_any = sent_any or ok
        if enable_email:
            ok, status = send_email_message(smtp_email, smtp_password, recipient_email, message)
            st.success(status) if ok else st.warning(status)
            sent_any = sent_any or ok
        if not sent_any and not (enable_telegram or enable_email):
            st.info("Enable Telegram or Email alert first. Missing credentials are ignored safely.")

    if st.button("Send Test Alert", type="secondary"):
        sample = picks.iloc[0] if not picks.empty else results.iloc[0]
        send_message("TEST ALERT\n\n" + alert_message(sample))

    if st.button("Send Today's Top 5 Alert", type="primary"):
        message = "\n\n---\n\n".join(alert_message(row) for _, row in picks.iterrows())
        send_message(message)


def render_settings() -> None:
    """Render app settings and operational notes."""
    st.subheader("Settings")
    st.write("Alert credentials can be typed in the Alerts sidebar or provided via Streamlit secrets:")
    st.code(
        "telegram_bot_token = '...'\ntelegram_chat_id = '...'\nsmtp_email = '...'\nsmtp_password = '...'\nrecipient_email = '...'",
        language="toml",
    )
    st.write("The app skips failed tickers and missing yfinance earnings data instead of crashing.")


def render_swing_scanner(
    title: str = "Swing Scanner",
    mode_options: List[str] | None = None,
    default_mode: str = "Market Leaders 300",
    key_prefix: str = "swing",
) -> None:
    """Render the Streamlit swing scanner tab."""
    st.subheader(title)
    st.caption("Daily end-of-day scanner for VCP / J Law / Minervini-style swing-trading preparation.")
    mode_options = mode_options or SCAN_MODES
    default_index = mode_options.index(default_mode) if default_mode in mode_options else 0

    with st.sidebar:
        st.header(f"{title} Controls")
        scan_mode = st.selectbox("Scan Mode", mode_options, index=default_index, key=f"{key_prefix}_scan_mode")
        custom_tickers = st.text_area(
            "Custom tickers",
            value="AAPL, MSFT, NVDA, AMD, META, TSLA",
            height=120,
            disabled=scan_mode != "Custom Input",
            key=f"{key_prefix}_custom_tickers",
        )

        preset_tickers = PRESET_UNIVERSES.get(scan_mode, [])
        if scan_mode == "US Pro Market Scan":
            preset_tickers = US_PRO_UNIVERSE
        elif scan_mode == "HK Pro Market Scan":
            preset_tickers = HK_PRO_UNIVERSE
        elif scan_mode == "Combined US + HK Scan":
            preset_tickers = COMBINED_PRO_UNIVERSE
        tickers = normalize_tickers(custom_tickers) if scan_mode == "Custom Input" else preset_tickers

        st.caption(f"{len(tickers)} tickers selected. Preset scans are capped at 500 symbols.")
        is_hk_mode = "HK" in scan_mode
        min_price_default = 1.0 if is_hk_mode else 10.0
        min_price = st.number_input("Minimum price", min_value=0.0, value=min_price_default, step=1.0, key=f"{key_prefix}_min_price")
        min_market_cap_b = st.number_input("Minimum market cap ($B)", min_value=0.0, value=5.0, step=0.5, key=f"{key_prefix}_min_cap")
        min_dollar_volume_m = st.number_input("Minimum avg turnover / dollar volume ($M)", min_value=0.0, value=20.0, step=5.0, key=f"{key_prefix}_min_dv")
        include_small_caps = st.checkbox("Include small caps", value=False, key=f"{key_prefix}_small_caps") if is_hk_mode else False

        st.divider()
        show_all = st.checkbox("Show all", value=False, key=f"{key_prefix}_show_all")
        show_full_diagnostics = st.checkbox("Show full diagnostics", value=False, key=f"{key_prefix}_diagnostics")
        only_ready_pullback = st.checkbox("Show only READY / PULLBACK", value=False, key=f"{key_prefix}_ready")
        only_trade_watchlist = st.checkbox("Show only Trade + Watchlist", value=False, key=f"{key_prefix}_trade_watch")
        hide_extended = st.checkbox("Hide EXTENDED", value=False, key=f"{key_prefix}_hide_extended")
        run_scan = st.button("Run Scan", type="primary", width="stretch", key=f"{key_prefix}_run")

    if run_scan:
        if not tickers:
            st.info("Choose a preset universe or enter custom tickers.")
            return

        with st.spinner("Downloading daily data and preparing trade plans..."):
            results, indicator_data, summary = scan_universe(
                tickers=tickers,
                mode=scan_mode,
                min_price=min_price,
                min_market_cap=(0 if include_small_caps else min_market_cap_b * 1_000_000_000),
                min_dollar_volume=min_dollar_volume_m * 1_000_000,
            )
            st.session_state[f"{key_prefix}_results"] = results
            st.session_state[f"{key_prefix}_indicator_data"] = indicator_data
            st.session_state[f"{key_prefix}_summary"] = summary
            st.session_state[f"{key_prefix}_last_scan_mode"] = scan_mode

    if f"{key_prefix}_results" not in st.session_state:
        st.info("Choose a scan mode, adjust the filters, then run the scan for your daily watchlist.")
        st.caption(
            "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
            "Confirm live price and volume in your broker before trading."
        )
        return

    results = st.session_state.get(f"{key_prefix}_results", pd.DataFrame())
    indicator_data = st.session_state.get(f"{key_prefix}_indicator_data", {})
    summary = st.session_state.get(f"{key_prefix}_summary", {})
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
        "Setup Category",
        "WATCHLIST FLAG",
        "Watchlist Reason",
        "Breakout Alert",
        "Earnings Date",
        "Days to Earnings",
        "Earnings Setup Score",
        "AI Trading Notes",
    }

    if not results.empty and not required_result_columns.issubset(results.columns):
        st.session_state.pop(f"{key_prefix}_results", None)
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
    metric_cols[4].metric("Mode", st.session_state.get(f"{key_prefix}_last_scan_mode", scan_mode))

    dashboard_cols = st.columns(6)
    dashboard_cols[0].metric("Trade YES", int((results["Trade"] == "YES").sum()))
    dashboard_cols[1].metric("Watchlist", int((results["WATCHLIST FLAG"] == "YES").sum()))
    dashboard_cols[2].metric("Near Breakouts", int((results["Breakout Alert"] == "NEAR BREAKOUT").sum()))
    dashboard_cols[3].metric("Confirmed Breakouts", int((results["Breakout Alert"] == "CONFIRMED BREAKOUT").sum()))
    dashboard_cols[4].metric("Earnings Risk", int((results["Earnings Risk"] == "HIGH RISK").sum()))
    best_sector = results.groupby("Sector ETF")["Final Score"].mean().sort_values(ascending=False).index[0] if not results.empty else "N/A"
    dashboard_cols[5].metric("Best Sector", best_sector)
    high_earnings_count = int((results["Earnings Risk"] == "HIGH RISK").sum())
    if high_earnings_count:
        st.warning(f"Earnings risk active: {high_earnings_count} stocks report within 7 days.")

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
        ["trade sort", "watchlist sort", "Final Score", "Tightness Score"],
        ascending=[True, True, False, False],
    )

    compact_columns = [
        "ticker",
        "Sector / Industry",
        "Theme",
        "Setup Category",
        "close",
        "Final Score",
        "Trade",
        "WATCHLIST FLAG",
        "Action Label",
        "Breakout Alert",
        "Earnings Date",
        "Earnings Risk",
        "Earnings Setup Score",
        "Trend Score",
        "Technical Score",
        "RS Score",
        "Tightness Score",
        "RR Score",
        "Pivot",
        "Entry Trigger",
        "Stop Loss",
        "Risk %",
        "Target 2R",
        "Target 3R",
        "AI Trading Notes",
    ]
    diagnostic_columns = compact_columns + [
        "Sector",
        "Industry",
        "Theme Group",
        "market cap",
        "avg dollar volume",
        "RSI",
        "Sector Score",
        "Sector ETF",
        "Sector Leadership",
        "Market Score",
        "VCP Status",
        "Contractions",
        "Distance to Pivot %",
        "Tightness Label",
        "RR Ratio",
        "Volume Confirmation",
        "Trade Reason",
        "Watchlist Reason",
        "Days to Earnings",
        "EPS Estimate",
        "Revenue Estimate",
        "Last EPS Surprise %",
        "Last Revenue Surprise %",
        "Earnings Trend",
        "Earnings Strategy",
        "Post-Earnings Label",
        "Notes",
    ]
    display_columns = diagnostic_columns if show_full_diagnostics else compact_columns

    focus_source = results.copy()
    focus_source["trade sort"] = np.where(focus_source["Trade"] == "YES", 0, 1)
    focus_source["watchlist sort"] = np.where(focus_source["WATCHLIST FLAG"] == "YES", 0, 1)

    trade_focus = focus_source[focus_source["Trade"] == "YES"].sort_values(
        ["Final Score", "Tightness Score"],
        ascending=[False, False],
    )
    watchlist_focus = focus_source[
        (focus_source["WATCHLIST FLAG"] == "YES") & (focus_source["Trade"] != "YES")
    ].sort_values(
        ["Final Score", "Tightness Score"],
        ascending=[False, False],
    )
    pullback_focus = focus_source[focus_source["Action Label"] == "PULLBACK ENTRY"].copy()
    if not pullback_focus.empty:
        pullback_focus["Pullback Reason"] = pullback_focus["Trade Reason"]
        pullback_focus.loc[pullback_focus["WATCHLIST FLAG"] == "YES", "Pullback Reason"] = pullback_focus[
            "Watchlist Reason"
        ]
        pullback_focus.loc[pullback_focus["Trade"] == "YES", "Pullback Reason"] = pullback_focus["Trade Reason"]
        pullback_focus = pullback_focus.sort_values(
            ["trade sort", "watchlist sort", "Final Score", "Tightness Score"],
            ascending=[True, True, False, False],
        )

    st.subheader("Daily Focus Summary")
    focus_cols = st.columns(3)
    with focus_cols[0]:
        show_focus_group("Trade YES", trade_focus, "Trade Reason")
    with focus_cols[1]:
        show_focus_group("Watchlist Setups", watchlist_focus, "Watchlist Reason")
    with focus_cols[2]:
        show_focus_group("Best Pullback Candidates", pullback_focus, "Pullback Reason")

    st.subheader("Best Setups")
    if visible.empty:
        st.info("No rows match the current display filters.")
    else:
        table_display = round_display_values(visible[display_columns])
        st.dataframe(
            table_display.style.apply(style_scan_table, axis=1),
            width="stretch",
            hide_index=True,
        )

    selectable = visible if not visible.empty else results
    selected_ticker = st.selectbox("Review ticker", selectable["ticker"].tolist(), key=f"{key_prefix}_review")
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
        st.write(f"Sector / Industry: {selected_row.get('Sector / Industry', 'N/A')}")
        st.write(f"Theme: {selected_row.get('Theme', 'N/A')}")
        st.write(f"Setup Category: {selected_row.get('Setup Category', 'N/A')}")
        st.write(selected_row["Notes"])

    export_frame = round_display_values(visible[display_columns] if not visible.empty else results[display_columns])
    export_cols = st.columns(3)
    export_cols[0].download_button(
        "Download CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name=f"{key_prefix}_vcp_scan.csv",
        mime="text/csv",
        width="stretch",
    )
    export_cols[1].download_button(
        "Download PDF",
        data=dataframe_to_simple_pdf(export_frame, f"{title} Export"),
        file_name=f"{key_prefix}_vcp_scan.pdf",
        mime="application/pdf",
        width="stretch",
    )
    export_cols[2].download_button(
        "Export Trade Plan",
        data=trade_plan_text(selected_row).encode("utf-8"),
        file_name=f"{selected_ticker}_trade_plan.txt",
        mime="text/plain",
        width="stretch",
    )

    st.caption(
        "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
        "Confirm live price and volume in your broker before trading."
    )


def main() -> None:
    """Render the IPO + Swing Pro Scanner app."""
    st.set_page_config(page_title="IPO + Swing Pro Scanner", page_icon="IPO", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background: #020617; color: #e5e7eb; }
        [data-testid="stSidebar"] { background: #0f172a; }
        [data-testid="stMetric"] {
            background: #111827;
            border: 1px solid #1e293b;
            border-radius: 10px;
            padding: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("IPO + Swing Pro Scanner")
    st.caption("Daily swing-trading scanner plus IPO grey-market scoring and trade planning.")

    us_tab, hk_tab, ipo_tab, top5_tab, alerts_tab, settings_tab = st.tabs(
        ["US Scanner", "HK Scanner", "IPO Scanner", "Top 5 Trades", "Alerts", "Settings"]
    )
    with us_tab:
        render_swing_scanner(
            title="US Scanner",
            mode_options=[
                "US Pro Market Scan",
                "Combined US + HK Scan",
                "AI / Semiconductor",
                "AI Infrastructure / Power",
                "Cloud / Software",
                "Cybersecurity",
                "Data Center / Networking",
                "Energy / Oil & Gas",
                "Defense / Aerospace",
                "Financials / Fintech",
                "Consumer Growth",
                "Biotech / Healthcare Growth",
                "Industrials / Infrastructure",
                "Crypto / Blockchain Stocks",
                "Market Leaders 300",
                "Custom Input",
            ],
            default_mode="US Pro Market Scan",
            key_prefix="us",
        )
    with hk_tab:
        render_swing_scanner(
            title="HK Scanner",
            mode_options=["HK Pro Market Scan", "Combined US + HK Scan", "Custom Input"],
            default_mode="HK Pro Market Scan",
            key_prefix="hk",
        )
    with ipo_tab:
        render_ipo_scanner()
    with top5_tab:
        render_top_5_trades()
    with alerts_tab:
        render_alerts()
    with settings_tab:
        render_settings()


if __name__ == "__main__":
    main()
