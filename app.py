"""VCP Swing Scanner.

Practical end-of-day Streamlit scanner for US swing-trading preparation.
The app uses daily yfinance data only. It is designed around VCP / J Law /
Minervini-style routines: scan a focused universe, filter weak names, score
trend and timing separately, then produce a next-day trade plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dt_time
from email.message import EmailMessage
from io import StringIO
import re
import smtplib
import time
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from bs4 import BeautifulSoup


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

UNIVERSE_SECTOR_FALLBACKS = {
    "AI / Semiconductor": ("Technology", "Semiconductors"),
    "AI Infrastructure / Power": ("Utilities", "AI infrastructure / power"),
    "Cloud / Software": ("Technology", "Software - Application"),
    "Cybersecurity": ("Technology", "Cybersecurity"),
    "Data Center / Networking": ("Technology", "Data center / networking"),
    "Robotics / Automation": ("Industrials", "Robotics / automation"),
    "Nuclear / Uranium": ("Energy", "Nuclear / uranium"),
    "Energy / Oil & Gas": ("Energy", "Oil & gas"),
    "Defense / Aerospace": ("Industrials", "Aerospace & defense"),
    "Financials / Fintech": ("Financial Services", "Financials / fintech"),
    "Biotech / Healthcare Growth": ("Healthcare", "Biotechnology / healthcare growth"),
    "Consumer Growth": ("Consumer Cyclical", "Consumer growth"),
    "Industrials / Infrastructure": ("Industrials", "Infrastructure"),
    "Crypto / Blockchain Stocks": ("Financial Services", "Crypto / digital assets"),
    "Growth Leaders": ("Technology", "Growth leaders"),
}

MANUAL_SECTOR_MAP: Dict[str, Tuple[str, str]] = {}
for universe_name, universe_tickers in PRESET_UNIVERSES.items():
    fallback_sector = UNIVERSE_SECTOR_FALLBACKS.get(universe_name)
    if fallback_sector:
        for symbol in universe_tickers:
            MANUAL_SECTOR_MAP.setdefault(symbol, fallback_sector)
for symbol in MARKET_LEADERS_BASE:
    MANUAL_SECTOR_MAP.setdefault(symbol, ("Technology", "Market leader"))
COMMON_SECTOR_OVERRIDES = {
    "NVDA": ("Technology", "Semiconductors"),
    "AMD": ("Technology", "Semiconductors"),
    "AVGO": ("Technology", "Semiconductors"),
    "TSM": ("Technology", "Semiconductors"),
    "ASML": ("Technology", "Semiconductor Equipment"),
    "LRCX": ("Technology", "Semiconductor Equipment"),
    "MU": ("Technology", "Memory Semiconductors"),
    "DELL": ("Technology", "Computer Hardware / AI Infrastructure"),
    "VRT": ("Industrials", "Electrical Equipment / Data Center Infrastructure"),
    "MS": ("Financial Services", "Capital Markets"),
    "WELL": ("Real Estate", "Healthcare REIT"),
    "CNC": ("Healthcare", "Healthcare Plans"),
    "MNST": ("Consumer Defensive", "Beverages - Non-Alcoholic"),
    "ELV": ("Healthcare", "Healthcare Plans"),
    "HUM": ("Healthcare", "Healthcare Plans"),
    "CVS": ("Healthcare", "Healthcare Plans / Pharmacy"),
    "MRK": ("Healthcare", "Drug Manufacturers - General"),
    "STLD": ("Basic Materials", "Steel"),
    "DAL": ("Industrials", "Airlines"),
    "CNI": ("Industrials", "Railroads"),
    "CROX": ("Consumer Cyclical", "Footwear & Accessories"),
    "NUE": ("Basic Materials", "Steel"),
    "AA": ("Basic Materials", "Aluminum"),
    "TGT": ("Consumer Defensive", "Discount Stores"),
    "FCX": ("Basic Materials", "Copper"),
}
for symbol, metadata in COMMON_SECTOR_OVERRIDES.items():
    MANUAL_SECTOR_MAP.setdefault(symbol, metadata)

MARKET_TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "SOXX",
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
TRADE_HISTORY_FILE = "trade_signals_history.csv"
POSITIONS_FILE = "positions.csv"
TRADE_HISTORY_COLUMNS = [
    "timestamp",
    "scan date",
    "scanner type",
    "ticker",
    "sector / industry",
    "leader quality label",
    "sector leadership status",
    "trade tier",
    "setup type",
    "signal state",
    "watch type",
    "trade",
    "professional score",
    "adjusted final score",
    "institutional quality score",
    "entry quality score",
    "healthy pullback score",
    "institutional tightness score",
    "breakout quality score",
    "RS score",
    "risk %",
    "close",
    "pivot",
    "entry trigger",
    "stop loss",
    "TP1",
    "TP2",
    "TP3",
    "ideal TP",
    "TP type",
    "decision reason",
]
SCANNER_TO_HISTORY_COLUMNS = {
    "ticker": "ticker",
    "Sector / Industry": "sector / industry",
    "Leader Quality Label": "leader quality label",
    "Sector Leadership Status": "sector leadership status",
    "Trade Tier": "trade tier",
    "Setup Type": "setup type",
    "Signal State": "signal state",
    "Watch Type": "watch type",
    "Trade": "trade",
    "Professional Score": "professional score",
    "Adjusted Final Score": "adjusted final score",
    "Institutional Quality Score": "institutional quality score",
    "Entry Quality Score": "entry quality score",
    "Healthy Pullback Score": "healthy pullback score",
    "Institutional Tightness Score": "institutional tightness score",
    "Breakout Quality Score": "breakout quality score",
    "RS Score": "RS score",
    "Risk %": "risk %",
    "close": "close",
    "Pivot": "pivot",
    "Entry Trigger": "entry trigger",
    "Stop Loss": "stop loss",
    "TP1": "TP1",
    "TP2": "TP2",
    "TP3": "TP3",
    "Ideal TP": "ideal TP",
    "TP Type": "TP type",
    "Decision Reason": "decision reason",
}
POSITION_STORAGE_COLUMNS = [
    "position_id",
    "ticker",
    "entry_date",
    "entry_price",
    "position_size",
    "fees",
    "broker",
    "account",
    "original_thesis_source",
    "original_signal_state",
    "original_setup_type",
    "original_trade_tier",
    "original_professional_score",
    "original_entry_trigger",
    "original_stop_loss",
    "original_tp1",
    "original_tp2",
    "original_tp3",
    "original_ideal_tp",
    "original_decision_reason",
    "notes",
    "created_at",
    "updated_at",
    "current_stop_loss_override",
    "manual_tp_override",
]


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


def format_count_number(value: float | int | None) -> str:
    """Display share volume in compact M/B form without currency symbols."""
    if value is None or pd.isna(value):
        return "N/A"
    value = float(value)
    if abs(value) >= 1_000_000_000:
        return f"{value / 1_000_000_000:.1f}B"
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    return f"{value:,.0f}"


def market_session_status(now: datetime | None = None) -> Tuple[str, str, str]:
    """Return NY-market session status plus human-readable NY/local timestamps."""
    ny_tz = ZoneInfo("America/New_York")
    local_tz = ZoneInfo("Asia/Singapore")
    ny_now = now.astimezone(ny_tz) if now is not None else datetime.now(ny_tz)
    local_now = ny_now.astimezone(local_tz)

    if ny_now.weekday() >= 5:
        status = "MARKET CLOSED"
    elif dt_time(4, 0) <= ny_now.time() < dt_time(9, 30):
        status = "PREMARKET"
    elif dt_time(9, 30) <= ny_now.time() < dt_time(16, 0):
        status = "REGULAR HOURS"
    elif dt_time(16, 0) <= ny_now.time() < dt_time(20, 0):
        status = "AFTER HOURS"
    else:
        status = "MARKET CLOSED"

    return status, ny_now.strftime("%Y-%m-%d %H:%M %Z"), local_now.strftime("%Y-%m-%d %H:%M %Z")


def clear_market_data_cache() -> None:
    """Clear market-data caches so the next scan downloads fresh bars and metadata."""
    for cached_func in (download_daily_data, download_market_caps, download_earnings_data):
        try:
            cached_func.clear()
        except Exception:
            pass


def safe_fast_info_get(fast_info, *keys: str):
    """Read yfinance fast_info values across object and mapping variants."""
    for key in keys:
        try:
            value = getattr(fast_info, key)
            if value is not None:
                return value
        except Exception:
            pass
        try:
            value = fast_info.get(key)
            if value is not None:
                return value
        except Exception:
            pass
    return None


def fetch_live_quote(ticker: str, include_info: bool = False) -> dict:
    """Fetch best-effort latest quote metadata without relying on stale OHLCV cache."""
    quote = {
        "current_price": np.nan,
        "previous_close": np.nan,
        "percent_change": np.nan,
        "premarket_price": np.nan,
        "afterhours_price": np.nan,
        "day_volume": np.nan,
        "avg_volume": np.nan,
        "year_high": np.nan,
        "quote_time": "N/A",
        "quote_source": "yfinance fast_info",
    }
    for attempt in range(3):
        try:
            yf_ticker = yf.Ticker(ticker)
            fast_info = yf_ticker.fast_info
            current = safe_fast_info_get(fast_info, "last_price", "lastPrice", "regular_market_price")
            previous = safe_fast_info_get(fast_info, "previous_close", "previousClose", "regular_market_previous_close")
            quote["current_price"] = float(current) if current is not None and pd.notna(current) else np.nan
            quote["previous_close"] = float(previous) if previous is not None and pd.notna(previous) else np.nan
            quote["day_volume"] = safe_fast_info_get(fast_info, "last_volume", "lastVolume", "day_volume")
            quote["avg_volume"] = safe_fast_info_get(fast_info, "ten_day_average_volume", "three_month_average_volume")
            quote["year_high"] = safe_fast_info_get(fast_info, "year_high", "yearHigh")
            quote["quote_time"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M %Z")

            if include_info:
                try:
                    info = yf_ticker.info or {}
                    quote["premarket_price"] = info.get("preMarketPrice", np.nan)
                    quote["afterhours_price"] = info.get("postMarketPrice", np.nan)
                    regular_time = info.get("regularMarketTime")
                    if regular_time:
                        quote["quote_time"] = datetime.fromtimestamp(
                            int(regular_time), tz=ZoneInfo("America/New_York")
                        ).strftime("%Y-%m-%d %H:%M %Z")
                    quote["quote_source"] = "yfinance fast_info + info"
                except Exception:
                    pass

            if pd.notna(quote["current_price"]) and pd.notna(quote["previous_close"]) and quote["previous_close"]:
                quote["percent_change"] = (quote["current_price"] / quote["previous_close"] - 1) * 100
            return quote
        except Exception:
            if attempt < 2:
                time.sleep(0.4 * (attempt + 1))
    quote["quote_source"] = "yfinance quote failed"
    return quote


def download_live_quotes(tickers: Tuple[str, ...]) -> Dict[str, dict]:
    """Fetch current quote metadata for all scanned tickers."""
    return {ticker: fetch_live_quote(ticker, include_info=False) for ticker in tickers}


@st.cache_data(ttl=60, show_spinner=False)
def download_daily_data(tickers: Tuple[str, ...], period: str = "1y", force_token: str = "") -> Dict[str, pd.DataFrame]:
    """Download daily OHLCV data and return one cleaned DataFrame per ticker."""
    if not tickers:
        return {}

    raw = pd.DataFrame()
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            raw = yf.download(
                list(tickers),
                period=period,
                interval="1d",
                auto_adjust=True,
                prepost=True,
                group_by="ticker",
                progress=False,
                threads=True,
            )
            if raw is not None and not raw.empty:
                break
        except Exception as exc:
            last_error = exc
        if attempt < 2:
            time.sleep(0.75 * (attempt + 1))

    if raw is None or raw.empty:
        if last_error:
            st.warning(f"Market data fetch failed after 3 tries: {last_error}")
        return {}

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
            if frame.index.tz is not None:
                frame.index = frame.index.tz_convert(None)
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


def classify_sector_group(ticker: str, sector: str, industry: str) -> str:
    """Map yfinance sector/industry into a compact scanner filter group."""
    text = f"{sector} {industry} {ticker}".lower()
    crypto_symbols = {"COIN", "HOOD", "MSTR", "MARA", "RIOT", "CLSK", "IREN", "HUT", "BTBT", "WULF", "CIFR", "CORZ"}
    if ticker.upper() in crypto_symbols or any(term in text for term in ("crypto", "bitcoin", "blockchain", "digital assets")):
        return "Crypto / Digital Assets"
    if any(term in text for term in ("semiconductor", "semiconductors", "chip", "integrated circuits")):
        return "Semiconductors"
    if any(term in text for term in ("technology", "software", "internet", "information technology", "communication equipment")):
        return "Technology"
    if any(term in text for term in ("energy", "oil", "gas", "uranium", "coal")):
        return "Energy"
    if any(term in text for term in ("utilities", "utility", "electric", "power")):
        return "Utilities"
    if any(term in text for term in ("healthcare", "health care", "biotech", "biotechnology", "pharmaceutical", "medical")):
        return "Healthcare"
    if any(term in text for term in ("financial", "bank", "capital markets", "insurance", "credit")):
        return "Financials"
    if any(term in text for term in ("industrial", "aerospace", "defense", "construction", "machinery", "infrastructure")):
        return "Industrials"
    if any(term in text for term in ("consumer", "retail", "restaurant", "apparel", "auto", "entertainment")):
        return "Consumer"
    if any(term in text for term in ("real estate", "reit")):
        return "Real Estate"
    if any(term in text for term in ("materials", "chemical", "metals", "mining", "steel", "gold")):
        return "Materials"
    return "Other"


def classify_theme_group(ticker: str, sector: str, industry: str) -> str:
    """Map names into the trading themes used by the sector rotation engine."""
    symbol = ticker.upper()
    text = f"{sector} {industry} {symbol}".lower()
    if symbol in PRESET_UNIVERSES.get("AI / Semiconductor", []) or any(term in text for term in ("semiconductor", "chip", "ai")):
        return "AI / Semis"
    if symbol in PRESET_UNIVERSES.get("AI Infrastructure / Power", []) or any(term in text for term in ("power", "electric", "utility", "grid")):
        return "Power / Utilities"
    if symbol in PRESET_UNIVERSES.get("Nuclear / Uranium", []) or any(term in text for term in ("nuclear", "uranium")):
        return "Nuclear / Uranium"
    if symbol in PRESET_UNIVERSES.get("Energy / Oil & Gas", []) or any(term in text for term in ("oil", "gas", "energy")):
        return "Energy"
    if symbol in PRESET_UNIVERSES.get("Financials / Fintech", []) or any(term in text for term in ("bank", "financial", "fintech", "capital markets")):
        return "Financials"
    if symbol in PRESET_UNIVERSES.get("Biotech / Healthcare Growth", []) or any(term in text for term in ("health", "biotech", "pharma")):
        return "Healthcare"
    if symbol in PRESET_UNIVERSES.get("Crypto / Blockchain Stocks", []) or any(term in text for term in ("crypto", "bitcoin", "blockchain")):
        return "Crypto"
    return classify_sector_group(ticker, sector, industry)


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def fetch_sector_industry_one(ticker: str) -> dict:
    """Fetch one ticker's sector/industry metadata and cache it for seven days."""
    fallback_sector, fallback_industry = MANUAL_SECTOR_MAP.get(ticker.upper(), ("N/A", "N/A"))
    if ticker.endswith(".HK") and fallback_sector == "N/A":
        fallback_sector, fallback_industry = "Hong Kong", "HK liquid leader"
    sector = "N/A"
    industry = "N/A"
    try:
        info = yf.Ticker(ticker).info or {}
        sector = info.get("sector") or "N/A"
        industry = info.get("industry") or "N/A"
    except Exception:
        pass
    if sector == "N/A":
        sector = fallback_sector
    if industry == "N/A":
        industry = fallback_industry

    if sector == "N/A" and industry == "N/A":
        display = "N/A"
    elif sector == "N/A":
        display = industry
    elif industry == "N/A":
        display = sector
    else:
        display = f"{sector} / {industry}"

    return {
        "sector": sector,
        "industry": industry,
        "sector_industry": display,
        "sector_group": classify_sector_group(ticker, sector, industry),
        "theme_group": classify_theme_group(ticker, sector, industry),
    }


@st.cache_data(ttl=60 * 60 * 24 * 7, show_spinner=False)
def download_sector_industry(tickers: Tuple[str, ...]) -> Dict[str, dict]:
    """Fetch sector/industry metadata from yfinance and cache it for seven days."""
    return {ticker: fetch_sector_industry_one(ticker) for ticker in tickers}


def fallback_sector_industry_one(ticker: str) -> dict:
    """Return instant manual sector metadata without touching yfinance."""
    sector, industry = MANUAL_SECTOR_MAP.get(ticker.upper(), ("N/A", "N/A"))
    if ticker.endswith(".HK") and sector == "N/A":
        sector, industry = "Hong Kong", "HK liquid leader"
    if sector == "N/A" and industry == "N/A":
        display = "N/A"
    elif sector == "N/A":
        display = industry
    elif industry == "N/A":
        display = sector
    else:
        display = f"{sector} / {industry}"
    return {
        "sector": sector,
        "industry": industry,
        "sector_industry": display,
        "sector_group": classify_sector_group(ticker, sector, industry),
        "theme_group": classify_theme_group(ticker, sector, industry),
    }


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


def synchronize_frame_with_quote(frame: pd.DataFrame, quote: dict, session_status: str) -> Tuple[pd.DataFrame, bool]:
    """Apply the latest quote to the newest candle so chart and table do not drift apart."""
    if frame.empty:
        return frame, False
    current_price = quote.get("current_price", np.nan)
    if pd.isna(current_price) or current_price <= 0:
        return frame, False

    data = frame.copy()
    latest_index = data.index[-1]
    latest_close = float(data.iloc[-1]["Close"])
    mismatch_pct = abs(current_price / latest_close - 1) * 100 if latest_close else 0
    should_apply = session_status in {"PREMARKET", "REGULAR HOURS", "AFTER HOURS"} or mismatch_pct > 0.5
    if not should_apply:
        return data, False

    data.loc[latest_index, "Close"] = float(current_price)
    if "High" in data:
        data.loc[latest_index, "High"] = max(float(data.loc[latest_index, "High"]), float(current_price))
    if "Low" in data:
        data.loc[latest_index, "Low"] = min(float(data.loc[latest_index, "Low"]), float(current_price))
    day_volume = quote.get("day_volume", np.nan)
    if "Volume" in data and pd.notna(day_volume) and float(day_volume) > 0:
        data.loc[latest_index, "Volume"] = float(day_volume)
    return data, True


def is_data_stale(latest_index: pd.Timestamp) -> Tuple[bool, str]:
    """Warn if the latest candle is older than one NY trading day."""
    latest_date = pd.Timestamp(latest_index).tz_localize(None).normalize()
    today_ny = pd.Timestamp.now(tz=ZoneInfo("America/New_York")).tz_localize(None).normalize()
    trading_days = len(pd.bdate_range(latest_date, today_ny)) - 1
    if trading_days > 1:
        return True, "Data stale - refresh required"
    return False, "Fresh"


def chart_sync_status(chart_close: float, quote_price: float) -> Tuple[str, float]:
    """Compare the displayed chart close against the fetched quote."""
    if pd.isna(chart_close) or pd.isna(quote_price) or chart_close <= 0:
        return "N/A", np.nan
    mismatch_pct = abs(quote_price / chart_close - 1) * 100
    if mismatch_pct > 2:
        return "Chart sync error", round(mismatch_pct, 2)
    return "Synced", round(mismatch_pct, 2)


def market_day_fraction(session_status: str) -> float:
    """Approximate how much of the regular NY trading day has elapsed."""
    if session_status in {"MARKET CLOSED", "AFTER HOURS"}:
        return 1.0
    if session_status == "PREMARKET":
        return 0.05
    now = datetime.now(ZoneInfo("America/New_York"))
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
    elapsed = (now - open_time).total_seconds()
    total = (close_time - open_time).total_seconds()
    return float(min(max(elapsed / total, 0.05), 1.0))


def calculate_intraday_volume_metrics(latest: pd.Series, quote_info: dict, session_status: str) -> Tuple[float, float, str]:
    """Estimate RVOL from current day volume versus expected 20-session volume at this time of day."""
    avg_vol20 = latest.get("AvgVol20", np.nan)
    current_volume = quote_info.get("day_volume", np.nan)
    if pd.isna(current_volume) or float(current_volume) <= 0:
        current_volume = latest.get("Volume", np.nan)
    if pd.isna(avg_vol20) or float(avg_vol20) <= 0 or pd.isna(current_volume):
        return np.nan, np.nan, "N/A"

    fraction = market_day_fraction(session_status)
    expected_intraday_volume = max(float(avg_vol20) * fraction, 1.0)
    intraday_ratio = float(current_volume) / expected_intraday_volume
    rvol = float(current_volume) / float(avg_vol20) if session_status in {"MARKET CLOSED", "AFTER HOURS"} else intraday_ratio

    if rvol > 2:
        label = "INSTITUTIONAL ACTIVITY"
    elif rvol >= 1.5:
        label = "STRONG"
    elif rvol >= 1:
        label = "NORMAL"
    else:
        label = "WEAK"
    return round(rvol, 2), round(intraday_ratio, 2), label


def detect_live_breakout_status(
    latest: pd.Series,
    pivot: PivotInfo,
    rvol: float,
    intraday_volume_ratio: float,
    rs_score: float,
    setup_grade: str,
) -> str:
    """Classify intraday breakout trigger quality from synchronized quote and volume."""
    if pd.isna(pivot.pivot) or latest["Close"] <= pivot.pivot:
        if latest["Close"] < latest["MA10"] or latest["Close"] < latest["MA20"]:
            return "FAILED BREAKOUT"
        return "NO BREAKOUT"
    price_above_key_mas = latest["Close"] > latest["MA10"] and latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"]
    strong_volume = pd.notna(intraday_volume_ratio) and intraday_volume_ratio > 1.5 and pd.notna(rvol) and rvol > 2
    if strong_volume and price_above_key_mas and score_at_least(rs_score, 7) and setup_grade in {"A+", "A"}:
        return "LIVE BREAKOUT"
    return "BREAKOUT STARTING"


def classify_current_setup_status(data: pd.DataFrame, pivot: PivotInfo, extended: bool, breakout_alert: str) -> str:
    """Summarize the current chart state from the latest synchronized candle."""
    latest = data.iloc[-1]
    previous = data.iloc[-2] if len(data) >= 2 else latest
    if latest["Close"] < latest["MA50"] or latest["Close"] < latest["Low10"]:
        return "FAILED BREAKOUT"
    if extended:
        return "EXTENDED"
    if breakout_alert == "CONFIRMED BREAKOUT":
        return "ACTIVE BREAKOUT"
    if breakout_alert in {"NEAR BREAKOUT", "BREAKOUT IN PROGRESS"}:
        return "EARLY BREAKOUT"
    if abs(latest["Close"] - latest["MA10"]) / latest["Close"] <= 0.03 and latest["Close"] >= latest["MA10"]:
        return "PULLBACK TO MA10"
    if abs(latest["Close"] - latest["MA20"]) / latest["Close"] <= 0.04 and latest["Close"] >= latest["MA20"]:
        return "PULLBACK TO MA20"
    if latest["Close"] <= pivot.pivot and latest["Close"] >= previous["Low"]:
        return "BASE BUILDING"
    return "BASE BUILDING"


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


def distribution_days_count(data: pd.DataFrame, lookback: int = 25) -> int:
    """Count recent institutional selling days from price down plus higher volume."""
    if data is None or data.empty or len(data) < 3:
        return 0
    recent = data.tail(lookback + 1).copy()
    price_change = recent["Close"].pct_change() * 100
    volume_up = recent["Volume"] > recent["Volume"].shift(1)
    distribution = (price_change <= -0.2) & volume_up
    return int(distribution.tail(lookback).sum())


def detect_follow_through_day(data: pd.DataFrame) -> bool:
    """Approximate IBD-style follow-through from a strong index up day on rising volume."""
    if data is None or data.empty or len(data) < 10:
        return False
    recent = data.tail(10).copy()
    pct = recent["Close"].pct_change() * 100
    volume_up = recent["Volume"] > recent["Volume"].shift(1)
    close_above_ma10 = recent["Close"] > recent["MA10"]
    return bool(((pct >= 1.2) & volume_up & close_above_ma10).tail(10).any())


def calculate_market_environment(market_data: Dict[str, pd.DataFrame], is_hk_scan: bool = False) -> dict:
    """Classify the broader market as confirmed uptrend, under pressure, or correction."""
    primary_symbol = "^HSI" if is_hk_scan else "SPY"
    fallback_symbol = "2800.HK" if is_hk_scan else "QQQ"
    primary = first_valid_frame(market_data.get(primary_symbol), market_data.get(fallback_symbol))
    growth = first_valid_frame(market_data.get("3033.HK"), market_data.get("QQQ")) if is_hk_scan else first_valid_frame(market_data.get("QQQ"))
    small = first_valid_frame(market_data.get("3067.HK"), market_data.get("IWM")) if is_hk_scan else first_valid_frame(market_data.get("IWM"))
    semis = first_valid_frame(market_data.get("SOXX"), market_data.get("SMH"))

    if primary is None or primary.empty:
        return {
            "status": "UPTREND UNDER PRESSURE",
            "distribution_days": 0,
            "follow_through_day": False,
            "details": "Market data unavailable; use reduced confidence.",
        }

    latest = primary.iloc[-1]
    primary_above = bool(latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"])
    primary_below_ma50 = bool(latest["Close"] < latest["MA50"])
    primary_below_ma200 = bool(latest["Close"] < latest["MA200"]) if pd.notna(latest.get("MA200", np.nan)) else False
    dist = distribution_days_count(primary)
    ftd = detect_follow_through_day(primary)
    growth_above = False
    if growth is not None and not growth.empty:
        g_latest = growth.iloc[-1]
        growth_above = bool(g_latest["Close"] > g_latest["MA20"] and g_latest["Close"] > g_latest["MA50"])
    breadth_ok = False
    if small is not None and not small.empty:
        s_latest = small.iloc[-1]
        breadth_ok = bool(s_latest["Close"] > s_latest["MA20"])
    semis_ok = False
    if semis is not None and not semis.empty:
        semi_latest = semis.iloc[-1]
        semis_ok = bool(semi_latest["Close"] > semi_latest["MA20"] and semi_latest["Close"] > semi_latest["MA50"])

    if primary_below_ma50 and (primary_below_ma200 or dist >= 5):
        status = "CORRECTION"
    elif primary_above and growth_above and dist <= 3:
        status = "CONFIRMED UPTREND"
    else:
        status = "UPTREND UNDER PRESSURE"

    details = (
        f"{primary_symbol if is_hk_scan else 'SPY'} {'above' if primary_above else 'below'} MA20/MA50 | "
        f"Growth {'healthy' if growth_above else 'mixed'} | "
        f"Breadth {'ok' if breadth_ok else 'weak'} | "
        f"Semis {'supportive' if semis_ok else 'mixed'} | "
        f"Distribution days {dist} | Follow-through day {'Yes' if ftd else 'No'}"
    )
    return {
        "status": status,
        "distribution_days": dist,
        "follow_through_day": ftd,
        "details": details,
    }


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
    extended = bool(ma10_distance > 12 or (latest["RSI14"] > 85 and ma10_distance > 8))

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


def build_trade_plan(data: pd.DataFrame, action: str, pivot: PivotInfo) -> Tuple[float, float, float, float, float, float, str]:
    """Calculate entry, stop, risk, 1R, 2R, 3R, and invalidation notes."""
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
    target_1r = entry + risk_dollars
    target_2r = entry + 2 * risk_dollars
    target_3r = entry + 3 * risk_dollars
    invalidation = "Close below MA20, close below recent structure low, or high-volume failed breakout."

    return (
        round(entry, 2),
        round(stop, 2),
        round(risk_pct, 2),
        round(target_1r, 2),
        round(target_2r, 2),
        round(target_3r, 2),
        invalidation,
    )


def round_number_resistance(price: float) -> float:
    """Find the next common round-number resistance above a planned entry."""
    if price <= 20:
        step = 1
    elif price <= 100:
        step = 5
    elif price <= 500:
        step = 10
    else:
        step = 25
    level = np.ceil(price / step) * step
    if level <= price * 1.005:
        level += step
    return float(level)


def detect_nearest_resistance(data: pd.DataFrame, entry: float) -> float:
    """Estimate the nearest overhead resistance using highs, swings, gaps, and round numbers."""
    latest = data.iloc[-1]
    candidates: List[float] = []
    current_close = float(latest.get("Close", entry))

    for column in ("High20", "High52W"):
        value = latest.get(column, np.nan)
        if pd.notna(value):
            candidates.append(float(value))

    if len(data) >= 50:
        candidates.append(float(data["High"].tail(50).max()))

    for point in find_swing_points(data, lookback=120):
        if point["type"] == "H":
            candidates.append(float(point["price"]))

    if len(data) >= 2:
        recent = data.tail(120)
        previous_low = recent["Low"].shift(1)
        gap_down = recent["High"] < previous_low * 0.98
        candidates.extend(float(value) for value in previous_low[gap_down].dropna().tolist())

    candidates.append(round_number_resistance(max(entry, current_close)))
    minimum_overhead = max(entry, current_close) * 1.005
    overhead = sorted({round(value, 2) for value in candidates if pd.notna(value) and value > minimum_overhead})
    if overhead:
        return overhead[0]

    fallback = max(float(latest.get("High52W", entry * 1.1)), round_number_resistance(max(entry, current_close)))
    return round(fallback, 2)


def risk_note(risk_pct: float, aggressive_mode: bool) -> str:
    """Label risk quality so borderline setups are obvious."""
    if pd.isna(risk_pct):
        return "Invalid risk"
    if risk_pct <= 8:
        return "Preferred risk"
    if risk_pct <= 10:
        return "Borderline risk"
    return "Aggressive risk allowed" if aggressive_mode else "Risk above 10%"


ACTIONABLE_SIGNAL_STATES = {"BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}
SIGNAL_STATE_PRIORITY = {
    "BUY NOW": 0,
    "EARLY POSITION": 1,
    "BUY ON BREAKOUT": 2,
    "WATCH": 3,
    "WAIT PULLBACK": 4,
    "EXTENDED DO NOT CHASE": 5,
    "REJECT": 6,
}
TRADE_TIER_PRIORITY = {
    "Tier 1 - Immediate Action": 0,
    "Tier 2 - High Quality, Wait Better Entry": 1,
    "Tier 3 - Leadership Watchlist": 2,
    "Tier 4 - Avoid / Reject": 3,
}
DECISION_PREFIX_BY_STATE = {
    "BUY NOW": "BUY NOW:",
    "EARLY POSITION": "EARLY POSITION:",
    "BUY ON BREAKOUT": "BUY ON BREAKOUT:",
    "WATCH": "WATCH:",
    "WAIT PULLBACK": "WAIT PULLBACK:",
    "EXTENDED DO NOT CHASE": "EXTENDED:",
    "REJECT": "REJECT:",
}
PROTECTED_SETUP_TYPES = {
    "MOMENTUM BREAKOUT EXCEPTION",
    "TRUE VCP",
    "VALID VCP",
    "EARLY VCP",
    "PULLBACK TO MA10",
    "PULLBACK TO MA20",
    "HEALTHY PULLBACK WATCH",
    "POST-BREAKOUT DIGESTION",
}

PRACTICAL_TP_NOTE = "TP2 selected as practical swing target; TP3 is runner only."

TIMING_SCORE_CAPS = {
    "IDEAL ENTRY ZONE": 100,
    "NEAR PIVOT": 92,
    "MA10 PULLBACK": 88,
    "BREAKOUT CONFIRMED": 88,
    "MA20 PULLBACK": 82,
    "HEALTHY PULLBACK": 82,
    "EXTENDED - WAIT": 55,
    "TOO LATE": 40,
    "FAILED SETUP": 30,
}
STAGE_SCORE_ADJUSTMENTS = {
    "EARLY STAGE 2": 12,
    "MID STAGE 2": 5,
    "LATE STAGE 2": -12,
    "CLIMAX / PARABOLIC": -25,
    "FAILED STAGE": -30,
    "STAGE 1 / NOT READY": -20,
}
STAGE_SORT_PRIORITY = {
    "EARLY STAGE 2": 0,
    "MID STAGE 2": 1,
    "LATE STAGE 2": 2,
    "CLIMAX / PARABOLIC": 3,
    "FAILED STAGE": 4,
    "STAGE 1 / NOT READY": 5,
}


def risk_bucket_state(
    risk_pct: float,
    *,
    strong_leader: bool = False,
    extended: bool = False,
) -> Tuple[str | None, str | None]:
    """Translate entry risk into a non-hard-reject signal downgrade."""
    if pd.isna(risk_pct):
        return "REJECT", "REJECT: invalid risk calculation."
    if risk_pct <= 10:
        return None, None
    if risk_pct <= 12:
        return "WATCH", "WATCH: good setup but risk slightly above preferred 10%."
    if risk_pct <= 15:
        return "WAIT PULLBACK", "WAIT PULLBACK: risk above ideal range, wait for tighter entry."
    if risk_pct <= 25 and strong_leader:
        return (
            "EXTENDED DO NOT CHASE" if extended else "WAIT PULLBACK",
            "WAIT PULLBACK: strong leader but stop distance too wide.",
        )
    if risk_pct <= 25:
        return "WAIT PULLBACK", "WAIT PULLBACK: risk above ideal range, wait for tighter entry."
    return "REJECT", "REJECT: risk above 25%."


def recalculate_ideal_tp(
    *,
    entry: float,
    stop: float,
    target_2r: float,
    target_3r: float,
    nearest_resistance: float,
    current_close: float,
    signal_state: str,
) -> Tuple[float, str, float]:
    """Return a valid upside target above entry, and above close for actionable rows."""
    risk_per_share = max(float(entry) - float(stop), 0.01)
    minimum_target = float(entry) + 1.5 * risk_per_share
    if signal_state in ACTIONABLE_SIGNAL_STATES:
        minimum_target = max(minimum_target, float(current_close) * 1.005)

    measured_move_target = float(entry) + max(float(current_close) - float(entry), risk_per_share) * 1.5
    atr_multiple_target = max(float(entry), float(current_close)) + 2 * risk_per_share
    round_resistance = round_number_resistance(max(float(entry), float(current_close)))

    candidates = [
        float(target_2r),
        float(target_3r),
        measured_move_target,
        atr_multiple_target,
        round_resistance,
    ]
    if pd.notna(nearest_resistance):
        candidates.append(float(nearest_resistance))

    valid_targets = [value for value in candidates if pd.notna(value) and value > minimum_target]
    if not valid_targets:
        fallback = float(entry) + 2 * risk_per_share
        if signal_state in ACTIONABLE_SIGNAL_STATES and fallback <= float(current_close):
            fallback = float(current_close) + 2 * risk_per_share
        ideal_tp = fallback
    else:
        ideal_tp = max(valid_targets)

    ideal_r = round((ideal_tp - float(entry)) / risk_per_share, 2)
    return round(float(ideal_tp), 2), "Recalculated: validated target above entry/current price", ideal_r


def validate_ideal_tp(
    *,
    ideal_tp: float,
    ideal_tp_reason: str,
    ideal_r: float,
    entry: float,
    stop: float,
    target_2r: float,
    target_3r: float,
    nearest_resistance: float,
    current_close: float,
    signal_state: str,
) -> Tuple[float, str, float]:
    """Prevent long-side targets from landing below entry or current price."""
    invalid = pd.isna(ideal_tp) or ideal_tp <= entry
    if signal_state in ACTIONABLE_SIGNAL_STATES and pd.notna(current_close):
        invalid = invalid or ideal_tp <= current_close
    minimum_r = (ideal_tp - entry) / max(entry - stop, 0.01) if pd.notna(ideal_tp) else 0
    invalid = invalid or minimum_r < 1.5
    if not invalid:
        return round(float(ideal_tp), 2), ideal_tp_reason, round(float(ideal_r), 2)

    fixed_tp, fixed_reason, fixed_r = recalculate_ideal_tp(
        entry=entry,
        stop=stop,
        target_2r=target_2r,
        target_3r=target_3r,
        nearest_resistance=nearest_resistance,
        current_close=current_close,
        signal_state=signal_state,
    )
    return fixed_tp, fixed_reason if not ideal_tp_reason else f"{fixed_reason}; {ideal_tp_reason}", fixed_r


def enforce_tp_ladder(entry: float, stop: float, tp1: float, tp2: float, tp3: float) -> Tuple[float, float, float]:
    """Keep practical long targets ordered above entry."""
    risk_per_share = max(float(entry) - float(stop), 0.01)
    tp1 = max(float(tp1), float(entry) + 1.5 * risk_per_share)
    tp2 = max(float(tp2), tp1 + 0.5 * risk_per_share, float(entry) + 2.0 * risk_per_share)
    tp3 = max(float(tp3), tp2 + 0.5 * risk_per_share, float(entry) + 3.0 * risk_per_share)
    return round(tp1, 2), round(tp2, 2), round(tp3, 2)


def calculate_trader_tp_plan(
    *,
    entry: float,
    stop: float,
    current_close: float,
    nearest_resistance: float,
    recent_high: float,
    institutional_quality_score: int,
    rs_score: float,
    sector_score: int,
    sector_leadership_status: str = "NEUTRAL SECTOR",
    market_environment: str = "",
    extended: bool = False,
    volatility_controlled: bool = True,
) -> Tuple[float, float, float, float, str, str, float]:
    """Build trader-style TP1/TP2/TP3 where TP2 is usually the swing plan."""
    risk_per_share = max(float(entry) - float(stop), 0.01)
    target_15r = float(entry) + 1.5 * risk_per_share
    target_2r = float(entry) + 2.0 * risk_per_share
    target_25r = float(entry) + 2.5 * risk_per_share
    target_3r = float(entry) + 3.0 * risk_per_share
    major_resistance = nearest_resistance if pd.notna(nearest_resistance) and nearest_resistance > entry else round_number_resistance(max(entry, current_close))
    breakout_extension = recent_high * 1.02 if pd.notna(recent_high) and recent_high > entry else target_2r
    measured_move = float(entry) + max(float(current_close) - float(entry), risk_per_share) * 1.25

    tp1_candidates = [target_15r, target_2r, major_resistance, breakout_extension]
    tp1_valid = [value for value in tp1_candidates if pd.notna(value) and value > entry]
    tp1 = min(tp1_valid, key=lambda value: abs(value - target_15r)) if tp1_valid else target_15r
    if tp1 > target_2r * 1.05:
        tp1 = target_2r

    tp2_candidates = [target_2r, target_25r, target_3r, measured_move]
    if major_resistance > tp1:
        tp2_candidates.append(major_resistance)
    tp2_valid = [value for value in tp2_candidates if pd.notna(value) and value > tp1]
    tp2 = min(tp2_valid, key=lambda value: abs(value - target_25r)) if tp2_valid else target_2r

    runner_allowed = (
        institutional_quality_score >= 9
        and score_at_least(rs_score, 9)
        and sector_leadership_status == "LEADING SECTOR"
        and market_environment == "CONFIRMED UPTREND"
        and not extended
        and volatility_controlled
    )
    tp3_base = max(target_3r, tp2 + 0.5 * risk_per_share, recent_high * 1.08 if pd.notna(recent_high) else target_3r)
    tp3 = tp3_base if runner_allowed else max(target_3r, tp2 + 0.5 * risk_per_share)
    tp1, tp2, tp3 = enforce_tp_ladder(entry, stop, tp1, tp2, tp3)

    ideal_tp = tp3 if runner_allowed else tp2
    tp_type = "RUNNER TP" if runner_allowed else "PRACTICAL SWING TP"
    if ideal_tp > entry * 1.35:
        tp_type = "RUNNER TP" if runner_allowed else "TOO FAR / USE TRAILING STOP"
        ideal_tp = tp2
    ideal_r = round((ideal_tp - entry) / risk_per_share, 2)
    return tp1, tp2, tp3, round(ideal_tp, 2), tp_type, PRACTICAL_TP_NOTE, ideal_r


def calculate_ideal_tp_plan(
    entry: float,
    stop: float,
    target_1r: float,
    target_2r: float,
    target_3r: float,
    nearest_resistance: float,
    current_close: float,
    ma10: float,
    prior_day_low: float,
    two_day_low: float,
    ma10_distance: float,
    setup_grade: str,
    explosive_score: int,
    rs_score: float,
    volume_confirmation: str,
    extended: bool,
    risk_pct: float,
    rsi: float,
    earnings_risk_label: str,
    watchlist_flag: str = "NO",
) -> Tuple[float, str, str, float, int, float]:
    """Choose a realistic TP zone and score whether enough upside exists before resistance."""
    risk_per_share = max(entry - stop, 0.01)
    resistance_r = (nearest_resistance - entry) / risk_per_share if nearest_resistance > entry else 0
    strong_momentum = setup_grade in {"A+", "A"} and explosive_score >= 8 and rs_score >= 7 and volume_confirmation == "YES"

    if setup_grade == "Reject":
        ideal_tp = min(target_1r, nearest_resistance) if nearest_resistance > entry else target_1r
        reason = "Rejected setup; do not plan an upside trade"
        sell_strategy = "AVOID / NO TRADE"
    elif watchlist_flag == "YES":
        ideal_tp = min(target_2r, nearest_resistance) if nearest_resistance > entry else target_2r
        reason = "Watchlist only; wait for a clean entry before using targets"
        sell_strategy = "WAIT FOR ENTRY"
    elif earnings_risk_label == "HIGH RISK":
        ideal_tp = min(target_1r, nearest_resistance) if nearest_resistance > entry else target_1r
        reason = "Earnings risk soon"
        sell_strategy = "TAKE 1R FAST"
    elif extended or risk_pct > 12 or rsi > 80:
        ideal_tp = min(target_1r, nearest_resistance) if nearest_resistance > entry else target_1r
        reason = "Extended; take profit faster"
        sell_strategy = "QUICK SCALP"
    elif nearest_resistance < target_1r:
        ideal_tp = nearest_resistance if nearest_resistance > entry else target_1r
        reason = "Nearest resistance before 1R; upside too limited"
        sell_strategy = "QUICK SCALP"
    elif strong_momentum:
        ideal_tp = target_3r
        reason = "Strong momentum setup; allow runner"
        sell_strategy = "HOLD TO 3R IF VOLUME HOLDS"
    elif target_1r <= nearest_resistance <= target_2r:
        ideal_tp = nearest_resistance
        reason = "Nearest resistance before 2R"
        sell_strategy = "TAKE 1R FAST"
    elif target_2r < nearest_resistance <= target_3r:
        ideal_tp = min(nearest_resistance, target_2r)
        reason = "Resistance near 2R-3R zone"
        sell_strategy = "SELL INTO 2R"
    elif setup_grade == "B":
        ideal_tp = min(target_2r, nearest_resistance) if nearest_resistance > entry else target_1r
        reason = "Lower quality setup; take profit earlier"
        sell_strategy = "SELL INTO 2R" if ideal_tp >= target_2r * 0.98 else "TAKE 1R FAST"
    elif setup_grade in {"A+", "A"}:
        ideal_tp = min(target_3r, nearest_resistance) if nearest_resistance > entry else target_2r
        reason = "High quality setup; allow larger target"
        sell_strategy = "PARTIAL AT 2R, TRAIL REST" if ideal_tp >= target_2r else "SELL INTO 2R"
    else:
        ideal_tp = min(target_1r, nearest_resistance) if nearest_resistance > entry else target_1r
        reason = "Limited upside before resistance"
        sell_strategy = "QUICK SCALP"

    ideal_tp, reason, ideal_r = validate_ideal_tp(
        ideal_tp=ideal_tp,
        ideal_tp_reason=reason,
        ideal_r=round((ideal_tp - entry) / risk_per_share, 2),
        entry=entry,
        stop=stop,
        target_2r=target_2r,
        target_3r=target_3r,
        nearest_resistance=nearest_resistance,
        current_close=current_close,
        signal_state="WATCH" if setup_grade != "Reject" else "REJECT",
    )
    if ma10_distance > 15:
        trail_stop = prior_day_low
    elif current_close >= target_2r:
        trail_stop = max(ma10, two_day_low)
    elif current_close >= target_1r:
        trail_stop = max(ma10, prior_day_low)
    else:
        trail_stop = max(stop, min(ma10, prior_day_low))

    tp_score = 0
    if nearest_resistance >= target_2r:
        tp_score += 2
    elif nearest_resistance >= target_1r:
        tp_score += 1
    if nearest_resistance >= target_3r:
        tp_score += 2
    elif nearest_resistance >= target_2r:
        tp_score += 1
    if setup_grade in {"A+", "A"}:
        tp_score += 2
    elif setup_grade == "B":
        tp_score += 1
    if explosive_score >= 8:
        tp_score += 1
    if volume_confirmation == "YES":
        tp_score += 1
    if earnings_risk_label not in {"HIGH RISK", "MEDIUM RISK"}:
        tp_score += 1
    if nearest_resistance < target_1r:
        tp_score -= 2
    if risk_pct > 10:
        tp_score -= 2
    elif risk_pct > 8:
        tp_score -= 1
    if earnings_risk_label == "HIGH RISK":
        tp_score -= 2
    elif earnings_risk_label == "MEDIUM RISK":
        tp_score -= 1
    if setup_grade == "Reject":
        tp_score -= 3
    if extended:
        tp_score -= 2

    return round(float(ideal_tp), 2), reason, sell_strategy, round(float(trail_stop), 2), int(min(max(tp_score, 0), 10)), ideal_r


def resistance_breakout_plan(data: pd.DataFrame, nearest_resistance: float) -> Tuple[float, float, float, float, float, float]:
    """Build an alternate plan for A/A+ setups that need to clear overhead resistance first."""
    latest = data.iloc[-1]
    atr = float(latest["ATR14"]) if pd.notna(latest["ATR14"]) else float(latest["Close"]) * 0.03
    entry = round(float(nearest_resistance) * 1.003, 2)
    support = min(float(latest["MA10"]), float(latest["Low10"]))
    stop = round(max(support - 0.25 * atr, 0.01), 2)
    risk = max(entry - stop, 0.01)
    target_1r = round(entry + risk, 2)
    target_2r = round(entry + 2 * risk, 2)
    target_3r = round(entry + 3 * risk, 2)
    return entry, stop, target_1r, target_2r, target_3r, round(risk / entry * 100, 2)


def classify_vcp_label(
    vcp_status: str,
    action: str,
    current_setup_status: str,
    resistance_breakout_mode: str,
) -> str:
    """Provide a clear human-readable VCP/pattern label while preserving raw VCP Status."""
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        return "RESISTANCE BREAKOUT WATCH"
    if action == "MOMENTUM BREAKOUT":
        return "Momentum Breakout Candidate"
    if action == "EXTENDED" or current_setup_status == "EXTENDED":
        return "EXTENDED"
    if action == "FAILED" or current_setup_status == "FAILED BREAKOUT":
        return "FAILED"
    if vcp_status in {"VALID VCP", "EARLY VCP"}:
        return vcp_status
    if action == "PULLBACK ENTRY":
        return "PULLBACK SETUP"
    if action == "WATCH" or current_setup_status == "BASE BUILDING":
        return "BASE BUILDING"
    return "NOT VCP"


def build_decision_reason(
    trade: str,
    watchlist_flag: str,
    trade_reason: str,
    watchlist_reason: str,
    setup_grade: str,
    vcp_label: str,
    rs_score: float,
    risk_pct: float,
    ideal_r: float,
    resistance_breakout_mode: str,
    ideal_tp_reason: str,
) -> str:
    """Explain the decision in one direct sentence."""
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        return "WATCH: resistance blocks 1R; needs clean breakout above resistance before swing entry"
    if vcp_label == "Momentum Breakout Candidate":
        status = "YES" if trade == "YES" else "WATCH"
        volume_text = "volume confirmed" if trade == "YES" else "needs volume confirmation"
        return f"{status}: momentum breakout candidate, RS {rs_score:g}, explosive score strong, {volume_text}"
    if trade == "YES":
        risk_text = "risk <= 8%" if pd.notna(risk_pct) and risk_pct <= 8 else "borderline risk"
        return f"YES: {setup_grade} setup, {vcp_label.lower()}, RS {rs_score:g}, {risk_text}, TP {ideal_r:g}R"
    if "resistance before 1R" in ideal_tp_reason.lower() or "reward too limited" in trade_reason.lower():
        return "NO: resistance before 1R"
    if "extended" in trade_reason.lower():
        return "NO: extended"
    if "risk" in trade_reason.lower():
        return "NO: risk too high"
    if watchlist_flag == "YES":
        return f"WATCH: {watchlist_reason}"
    return f"NO: {trade_reason}"


def clean_why_selected(
    why_selected: str,
    trade: str,
    trade_reason: str,
    watchlist_flag: str,
    vcp_status: str,
    resistance_breakout_mode: str,
) -> str:
    """Avoid contradictory selected/rejected wording when Trade is NO."""
    selected_text = why_selected.lower().startswith("selected because")
    if trade == "YES" or not selected_text:
        return why_selected
    if "Momentum breakout candidate" in why_selected:
        return why_selected
    if why_selected == "Momentum breakout candidate despite not being pure VCP":
        return why_selected
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        return "Watchlist only: needs clean breakout above resistance before swing entry"
    if watchlist_flag == "YES" and vcp_status in {"VALID VCP", "EARLY VCP"}:
        return "Watchlist only: valid/early VCP but no clean entry yet"
    return f"Not selected yet: {trade_reason}"


def classify_setup_type(
    vcp_status: str,
    action: str,
    current_setup_status: str,
    resistance_breakout_mode: str,
    momentum_breakout_candidate: bool,
    latest: pd.Series,
    healthy_pullback_label: str = "",
    institutional_tightness_score: int = 0,
) -> str:
    """Separate pattern classification from the raw VCP detector."""
    if momentum_breakout_candidate:
        return "MOMENTUM BREAKOUT EXCEPTION"
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        return "RESISTANCE BREAKOUT WATCH"
    if action == "EXTENDED" or current_setup_status == "EXTENDED":
        return "EXTENDED"
    if action == "FAILED" or current_setup_status == "FAILED BREAKOUT":
        if healthy_pullback_label == "HEALTHY PULLBACK":
            return "HEALTHY PULLBACK WATCH"
        return "FAILED"
    close = float(latest["Close"])
    pivot_value = float(latest.get("Pivot", np.nan)) if pd.notna(latest.get("Pivot", np.nan)) else np.nan
    if healthy_pullback_label == "HEALTHY PULLBACK":
        return "HEALTHY PULLBACK WATCH"
    if pd.notna(pivot_value) and close > pivot_value and close >= min(float(latest["MA10"]), float(latest["MA20"])):
        return "POST-BREAKOUT DIGESTION"
    if pd.notna(pivot_value) and close < pivot_value and close > min(float(latest["MA10"]), float(latest["MA20"])):
        return "PULLBACK TO MA10" if close >= float(latest["MA10"]) else "PULLBACK TO MA20"
    if pd.notna(pivot_value) and 0 <= (pivot_value - close) / close * 100 <= 3 and institutional_tightness_score >= 7:
        return "RESISTANCE BREAKOUT WATCH"
    if vcp_status == "VALID VCP":
        return "TRUE VCP"
    if vcp_status == "EARLY VCP":
        return "EARLY VCP"
    if action == "PULLBACK ENTRY":
        ma10_gap = abs(close - float(latest["MA10"])) / close * 100 if close else np.nan
        ma20_gap = abs(close - float(latest["MA20"])) / close * 100 if close else np.nan
        return "PULLBACK TO MA10" if pd.notna(ma10_gap) and ma10_gap <= 3 else "PULLBACK TO MA20" if pd.notna(ma20_gap) and ma20_gap <= 5 else "PULLBACK TO MA20"
    return "BASE BUILDING"


def determine_signal_state(
    *,
    setup_grade: str,
    final_score: float,
    rs_score: float,
    explosive_score: int,
    risk_pct: float,
    latest: pd.Series,
    ma10_rising: bool,
    breakout_alert: str,
    volume_confirmation: str,
    earnings_risk_label: str,
    vcp_status: str,
    pivot: PivotInfo,
    higher_low_structure: bool,
    volume_contraction: bool,
    ma10_distance: float,
    rsi: float,
    action: str,
    momentum_breakout_candidate: bool,
    resistance_breakout_mode: str,
    resistance_distance_pct: float,
    technical_score: int,
    trend_score: int,
    tightness_score: int,
    breakout_quality_score: int,
    rvol: float,
    market_environment: str,
    live_breakout_status: str,
    stage_label: str,
    live_mode: bool = False,
) -> Tuple[str, str, str, str, str]:
    """Map scanner evidence into J Law / Minervini-style signal states."""
    price_above_key_mas = bool(latest["Close"] > latest["MA10"] and latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"])
    avg_vol20 = latest.get("AvgVol20", np.nan)
    exceptional_volume = pd.notna(avg_vol20) and avg_vol20 > 0 and latest["Volume"] >= 1.3 * avg_vol20
    volume_confirmed = volume_confirmation == "YES" or exceptional_volume
    risk_ok = pd.notna(risk_pct) and risk_pct <= 10
    rs_buy_ok = score_at_least(rs_score, 7)
    rs_momentum_ok = score_at_least(rs_score, 8)
    setup_a = setup_grade in {"A+", "A"}
    breakout_state = breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}
    near_pivot = pd.notna(pivot.distance_pct) and 0 <= pivot.distance_pct <= 5
    near_resistance = pd.notna(resistance_distance_pct) and -1 <= resistance_distance_pct <= 5
    structure_valid = action not in {"FAILED"} and latest["Close"] >= latest["MA50"]

    market_correction = live_mode and market_environment == "CORRECTION"
    rvol_confirmed = pd.notna(rvol) and rvol > 2
    strong_setup = final_score >= 85 and score_at_least(rs_score, 8) and structure_valid
    protected_structure = (
        momentum_breakout_candidate
        or vcp_status in {"VALID VCP", "EARLY VCP"}
        or action == "PULLBACK ENTRY"
    )

    if pd.notna(ma10_distance) and ma10_distance > 12:
        if strong_setup or protected_structure:
            return (
                "WAIT PULLBACK",
                "NO",
                "YES",
                "WAIT PULLBACK: setup is strong but entry is stretched; wait for MA10/MA20 support.",
                "WAIT PULLBACK: setup is strong but entry is stretched; wait for MA10/MA20 support.",
            )
        return (
            "EXTENDED DO NOT CHASE",
            "NO",
            "NO",
            "EXTENDED DO NOT CHASE: price too far above MA10.",
            "EXTENDED: wait for pullback, do not chase.",
        )
    risk_state, risk_reason = risk_bucket_state(
        risk_pct,
        strong_leader=strong_setup or momentum_breakout_candidate,
        extended=bool(pd.notna(ma10_distance) and ma10_distance > 12),
    )
    if risk_state == "REJECT":
        return (
            "REJECT",
            "NO",
            "NO",
            risk_reason,
            risk_reason,
        )
    if risk_state in {"WAIT PULLBACK", "EXTENDED DO NOT CHASE"}:
        return (
            risk_state,
            "NO",
            "YES" if risk_state == "WAIT PULLBACK" else "NO",
            risk_reason,
            risk_reason,
        )
    if pd.notna(rsi) and rsi > 85 and not exceptional_volume:
        if strong_setup or protected_structure:
            return (
                "WAIT PULLBACK",
                "NO",
                "YES",
                "WAIT PULLBACK: strong leader is stretched; wait for a tighter entry.",
                "WAIT PULLBACK: strong leader is stretched; wait for a tighter entry.",
            )
        return (
            "EXTENDED DO NOT CHASE",
            "NO",
            "NO",
            "EXTENDED DO NOT CHASE: RSI is stretched without exceptional volume.",
            "EXTENDED: wait for pullback, do not chase.",
        )

    earnings_strong_setup = (
        earnings_risk_label == "HIGH RISK"
        and final_score >= 85
        and rs_buy_ok
        and explosive_score >= 7
        and structure_valid
        and (breakout_state or near_pivot or near_resistance or action == "PULLBACK ENTRY")
    )
    if earnings_strong_setup:
        return (
            "WATCH",
            "NO",
            "YES",
            "WATCH: strong setup but earnings risk high; consider smaller size or wait after earnings.",
            "WATCH: strong setup but earnings risk high; consider smaller size or wait after earnings.",
        )
    if earnings_risk_label == "HIGH RISK" and setup_grade not in {"A+", "A", "B"}:
        return (
            "REJECT",
            "NO",
            "NO",
            "REJECT: earnings risk high and setup quality below B.",
            "REJECT: earnings risk high and setup quality below B.",
        )

    borderline_risk = pd.notna(risk_pct) and 10 < risk_pct <= 12
    if borderline_risk and structure_valid and setup_grade != "Reject":
        borderline_state = "BUY ON BREAKOUT" if breakout_state or near_pivot or near_resistance else "WATCH"
        borderline_reason = (
            "BUY ON BREAKOUT: good setup but risk slightly above preferred 10%; wait for clean trigger."
            if borderline_state == "BUY ON BREAKOUT"
            else "WATCH: good setup but risk slightly above preferred 10%."
        )
        return (
            borderline_state,
            "NO",
            "YES",
            borderline_reason,
            borderline_reason,
        )

    momentum_base = (
        final_score >= 90
        and rs_momentum_ok
        and explosive_score >= 8
        and (not live_mode or breakout_quality_score >= 7)
        and trend_score >= 7
        and technical_score >= 7
        and price_above_key_mas
        and ma10_rising
        and breakout_state
        and risk_ok
        and pd.notna(ma10_distance)
        and ma10_distance <= 12
        and earnings_risk_label != "HIGH RISK"
        and stage_label not in {"STAGE 3 RISK", "STAGE 4"}
    )
    if momentum_base:
        if (volume_confirmed or momentum_breakout_candidate or (live_mode and live_breakout_status == "LIVE BREAKOUT")) and not market_correction:
            return (
                "BUY NOW",
                "YES",
                "NO",
                "BUY NOW: Momentum breakout exception, high RS, strong volume, risk controlled.",
                "BUY NOW: momentum breakout exception, high RS, strong volume, risk controlled.",
            )
        return (
            "BUY ON BREAKOUT",
            "NO",
            "YES",
            "BUY ON BREAKOUT: high RS momentum setup, wait for clean breakout with volume.",
            "BUY ON BREAKOUT: high RS momentum setup, wait for clean breakout with volume.",
        )

    common_buy = (
        setup_a
        and final_score >= 85
        and rs_buy_ok
        and explosive_score >= 7
        and (not live_mode or breakout_quality_score >= 7)
        and risk_ok
        and price_above_key_mas
        and ma10_rising
        and breakout_state
        and (volume_confirmed or (live_mode and (rvol_confirmed or live_breakout_status == "LIVE BREAKOUT")))
        and earnings_risk_label != "HIGH RISK"
        and not market_correction
        and stage_label not in {"STAGE 3 RISK", "STAGE 4"}
    )
    vcp_breakout = vcp_status in {"VALID VCP", "EARLY VCP"} and latest["Close"] >= pivot.pivot and volume_confirmed
    pullback_entry = (
        action == "PULLBACK ENTRY"
        and (latest["Close"] > latest["MA10"] or latest["Close"] >= latest["MA20"])
        and higher_low_structure
        and volume_contraction
        and volume_confirmed
    )
    if common_buy and (vcp_breakout or pullback_entry):
        return (
            "BUY NOW",
            "YES",
            "NO",
            "BUY NOW: A+ setup, RS strong, breakout confirmed with volume, risk controlled.",
            "BUY NOW: A+ setup, RS strong, breakout confirmed with volume, risk controlled.",
        )

    buy_on_breakout = (
        setup_a
        and final_score >= 85
        and rs_buy_ok
        and explosive_score >= 7
        and (not live_mode or breakout_quality_score >= 6)
        and risk_ok
        and (near_pivot or near_resistance or resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH")
        and not (volume_confirmed or (live_mode and rvol_confirmed))
        and structure_valid
        and stage_label not in {"STAGE 4"}
    )
    if buy_on_breakout:
        return (
            "BUY ON BREAKOUT",
            "NO",
            "YES",
            "BUY ON BREAKOUT: near pivot, wait for volume confirmation.",
            "BUY ON BREAKOUT: near pivot, wait for volume confirmation.",
        )

    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        return (
            "WATCH",
            "NO",
            "YES",
            "WATCH: resistance blocks clean entry; wait for breakout above resistance.",
            "WATCH: good setup, wait for trigger.",
        )
    if action == "EXTENDED":
        return (
            "WAIT PULLBACK",
            "NO",
            "YES",
            "WATCH - Pullback: wait for MA10/MA20 support confirmation.",
            "WATCH - Pullback: wait for MA10/MA20 support confirmation.",
        )
    watchlist_quality = (
        structure_valid
        and setup_grade != "Reject"
        and tightness_score >= 3
        and volume_contraction
        and (near_pivot or near_resistance or vcp_status in {"VALID VCP", "EARLY VCP"})
        and (score_at_least(rs_score, 6) or pd.isna(numeric_or_na(rs_score)))
        and stage_label not in {"STAGE 4"}
    )
    if watchlist_quality:
        return (
            "WATCH",
            "NO",
            "YES",
            "WATCH: good setup, wait for trigger.",
            "WATCH: good setup, wait for trigger.",
        )
    return (
        "REJECT",
        "NO",
        "NO",
        "REJECT: weak RS, broken structure, or poor risk/reward.",
        "REJECT: weak RS, broken structure, or poor risk/reward.",
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


def calculate_explosive_score(data: pd.DataFrame, pivot: PivotInfo, higher_low_structure: bool) -> Tuple[int, str]:
    """Score near-term breakout potential from compression, pivot pressure, and RS trend."""
    latest = data.iloc[-1]
    score = 0

    if len(data) >= 20:
        latest_5_vol = data["Volume"].tail(5).mean()
        previous_5_vol = data["Volume"].iloc[-10:-5].mean()
        latest_10_vol = data["Volume"].tail(10).mean()
        previous_10_vol = data["Volume"].iloc[-20:-10].mean()
        if latest_5_vol < previous_5_vol * 0.9 and latest_10_vol < previous_10_vol:
            score += 2
        elif latest_5_vol < previous_5_vol or latest_10_vol < previous_10_vol * 1.03:
            score += 1

    if len(data) >= 10:
        close_band_pct = (data["Close"].tail(5).max() - data["Close"].tail(5).min()) / latest["Close"] * 100
        range_contracting = has_tight_range(data)
        if close_band_pct <= 3 and range_contracting:
            score += 2
        elif close_band_pct <= 5 or range_contracting:
            score += 1

    if higher_low_structure:
        recent_low = data["Low"].tail(10).min()
        prior_low = data["Low"].iloc[-25:-10].min() if len(data) >= 25 else np.nan
        if pd.notna(prior_low) and recent_low >= prior_low * 1.03:
            score += 2
        else:
            score += 1

    distance = pivot.distance_pct
    if pd.notna(distance):
        if pivot.label == "Breakout in progress" or 0 <= distance <= 5:
            score += 2
        elif -3 <= distance < 0 or 5 < distance <= 10:
            score += 1

    rs_slope = latest.get("RSSlope30", np.nan)
    if pd.notna(rs_slope):
        if rs_slope >= 5:
            score += 2
        elif rs_slope >= -1:
            score += 1

    score = int(min(max(score, 0), 10))
    if score >= 8:
        label = "HIGH EXPLOSION POTENTIAL"
    elif score >= 6:
        label = "READY BUT NEED VOLUME"
    else:
        label = "LOW MOMENTUM"
    return score, label


def calculate_healthy_pullback_score(data: pd.DataFrame, pivot: PivotInfo) -> Tuple[int, str, bool]:
    """Score whether a leader is digesting normally instead of breaking down."""
    latest = data.iloc[-1]
    score = 0
    close = float(latest["Close"])
    avg_vol20 = float(latest.get("AvgVol20", np.nan)) if pd.notna(latest.get("AvgVol20", np.nan)) else np.nan
    recent_high_volume = float(data["Volume"].tail(20).max()) if len(data) >= 20 else float(latest["Volume"])
    lighter_than_breakout = bool(pd.notna(recent_high_volume) and latest["Volume"] < recent_high_volume * 0.75)

    if close >= float(latest["MA10"]):
        score += 2
    if close >= float(latest["MA20"]):
        score += 2
    if lighter_than_breakout:
        score += 2
    if pd.notna(avg_vol20) and latest["Volume"] < avg_vol20:
        score += 1
    daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    if close >= float(latest["Low"]) + 0.5 * daily_range:
        score += 1
    rsi = latest.get("RSI14", np.nan)
    if pd.notna(rsi) and 50 <= rsi <= 75:
        score += 1
    if pd.notna(pivot.pivot) and close >= pivot.pivot * 0.97:
        score += 1

    heavy_volume = pd.notna(avg_vol20) and latest["Volume"] > avg_vol20 * 1.15
    red_candle = close < float(latest["Open"])
    body_pct = abs(close - float(latest["Open"])) / max(close, 0.01) * 100
    recent_structure_low = float(data["Low"].iloc[-21:-1].min()) if len(data) > 21 else np.nan
    if close < float(latest["MA20"]) and heavy_volume:
        score -= 3
    if pd.notna(recent_structure_low) and close < recent_structure_low:
        score -= 2
    if red_candle and heavy_volume and body_pct >= 3:
        score -= 2
    if pd.notna(pivot.pivot) and data["High"].tail(10).max() > pivot.pivot * 1.02 and close < pivot.pivot and heavy_volume:
        score -= 2

    score = int(min(max(score, 0), 10))
    if score >= 8:
        label = "HEALTHY PULLBACK"
    elif score >= 6:
        label = "NORMAL DIGESTION"
    elif score >= 3:
        label = "WARNING PULLBACK"
    else:
        label = "FAILED PULLBACK"
    return score, label, lighter_than_breakout


def calculate_institutional_tightness_score(data: pd.DataFrame, pivot: PivotInfo) -> Tuple[int, str]:
    """Score tight institutional accumulation from price range and volume behavior."""
    latest = data.iloc[-1]
    score = 0
    closes = data["Close"].tail(5)
    ranges = data["RangePct"].tail(10)
    avg_vol20 = latest.get("AvgVol20", np.nan)

    if len(closes) >= 3 and (closes.tail(3).max() - closes.tail(3).min()) / max(float(latest["Close"]), 0.01) * 100 <= 2:
        score += 2
    if len(ranges) >= 10 and ranges.tail(5).mean() < ranges.head(5).mean():
        score += 2
    if has_volume_contraction(data):
        score += 2
    if latest["Close"] >= latest["MA10"]:
        score += 1
    if pd.notna(pivot.pivot) and latest["Close"] >= pivot.pivot * 0.97:
        score += 1
    small_candles = int((data["RangePct"].tail(5) <= data["RangePct"].tail(20).mean()).sum()) if len(data) >= 20 else 0
    if small_candles >= 3:
        score += 1
    if distribution_days_count(data, lookback=5) == 0:
        score += 1

    wide_candles = int((data["RangePct"].tail(5) > data["RangePct"].tail(20).mean() * 1.6).sum()) if len(data) >= 20 else 0
    high_volume_red = int(((data["Close"].tail(5) < data["Open"].tail(5)) & (data["Volume"].tail(5) > avg_vol20)).sum()) if pd.notna(avg_vol20) else 0
    if wide_candles >= 2:
        score -= 2
    if high_volume_red >= 2:
        score -= 2
    if latest["Close"] < latest["MA10"] and pd.notna(avg_vol20) and latest["Volume"] > avg_vol20:
        score -= 2
    if pd.notna(pivot.pivot) and latest["Close"] < pivot.pivot * 0.98 and pd.notna(avg_vol20) and latest["Volume"] > avg_vol20:
        score -= 2

    score = int(min(max(score, 0), 10))
    if score >= 8:
        label = "TIGHT LEADER"
    elif score >= 6:
        label = "TIGHT BASE"
    elif score >= 4:
        label = "LOOSE BUT STRONG"
    else:
        label = "WIDE AND RISKY"
    return score, label


def detect_stage_analysis(data: pd.DataFrame) -> str:
    """Classify the longer-term stage using MA150/MA200 and trend maturity."""
    if len(data) < 210:
        return "BASE BUILDING"
    latest = data.iloc[-1]
    close = latest["Close"]
    ma150 = latest["MA150"]
    ma200 = latest["MA200"]
    ma200_rising = is_rising(data["MA200"], lookback=20)
    high52 = latest.get("High52W", np.nan)
    days_above_ma50 = int((data["Close"].tail(80) > data["MA50"].tail(80)).sum())

    if close < ma150 and close < ma200:
        return "STAGE 4"
    if close > ma150 and close > ma200 and ma150 > ma200 and ma200_rising:
        if days_above_ma50 < 35:
            return "EARLY STAGE 2"
        if pd.notna(high52) and close >= high52 * 0.95 and latest["RSI14"] > 75:
            return "LATE STAGE 2"
        return "MID STAGE 2"
    if close > ma150 and not ma200_rising:
        return "STAGE 3 RISK"
    return "STAGE 1 BASE"


def classify_stage_label(
    data: pd.DataFrame,
    pivot: PivotInfo,
    character_change_flag: str,
    current_setup_status: str,
) -> str:
    """Classify stage maturity for timing-aware ranking."""
    if data.empty:
        return "STAGE 1 / NOT READY"
    latest = data.iloc[-1]
    close = float(latest.get("Close", np.nan))
    ma10 = float(latest.get("MA10", np.nan))
    ma20 = float(latest.get("MA20", np.nan))
    ma50 = float(latest.get("MA50", np.nan))
    ma150 = float(latest.get("MA150", np.nan))
    ma200 = float(latest.get("MA200", np.nan))
    rsi = float(latest.get("RSI14", np.nan))
    ma20_distance = (close / ma20 - 1) * 100 if pd.notna(close) and pd.notna(ma20) and ma20 > 0 else np.nan
    ma10_distance = (close / ma10 - 1) * 100 if pd.notna(close) and pd.notna(ma10) and ma10 > 0 else np.nan
    pivot_distance = abs((close / pivot.pivot - 1) * 100) if pd.notna(pivot.pivot) and pivot.pivot else np.nan
    recent_move = data["Close"].pct_change(10).iloc[-1] * 100 if len(data) >= 11 else np.nan
    volatility_expanding = (
        len(data) >= 20
        and pd.notna(data["RangePct"].tail(5).mean())
        and data["RangePct"].tail(5).mean() > data["RangePct"].tail(20).mean() * 1.5
    )

    if character_change_flag == "CHARACTER CHANGE" or current_setup_status in {"FAILED", "FAILED BREAKOUT"}:
        return "FAILED STAGE"
    if pd.isna(close) or pd.isna(ma50) or close < ma50:
        return "STAGE 1 / NOT READY"
    if pd.notna(ma20_distance) and ma20_distance > 25 and pd.notna(rsi) and rsi > 75:
        return "CLIMAX / PARABOLIC"
    if pd.notna(recent_move) and recent_move > 20 and volatility_expanding:
        return "CLIMAX / PARABOLIC"
    if (pd.notna(ma20_distance) and ma20_distance > 18) or (pd.notna(ma10_distance) and ma10_distance > 12):
        return "LATE STAGE 2"
    if pd.notna(ma20_distance) and ma20_distance > 15:
        return "LATE STAGE 2"
    major_uptrend = (
        pd.notna(ma50)
        and pd.notna(ma150)
        and pd.notna(ma200)
        and close > ma50 > ma150 > ma200
    )
    if major_uptrend and pd.notna(pivot_distance) and pivot_distance <= 5 and (pd.isna(ma10_distance) or ma10_distance <= 10):
        return "EARLY STAGE 2"
    if major_uptrend or (pd.notna(ma150) and pd.notna(ma200) and close > ma150 and close > ma200):
        return "MID STAGE 2"
    return "STAGE 1 / NOT READY"


def stage_score_adjustment(stage_label: str) -> int:
    """Return the configured score adjustment for stage maturity."""
    return STAGE_SCORE_ADJUSTMENTS.get(stage_label, 0)


def timing_score_cap(entry_timing: str) -> int:
    """Return the maximum final score allowed by entry timing."""
    return TIMING_SCORE_CAPS.get(entry_timing, 100)


def strip_executable_prefix(text: str) -> str:
    """Remove executable-grade wording before applying the signal-state prefix."""
    cleaned = str(text or "").strip()
    for prefix in ("A - EXECUTABLE NOW:", "B - WATCHLIST:", "C - AVOID:"):
        if cleaned.startswith(prefix):
            return cleaned[len(prefix):].strip()
    return cleaned


def calculate_quality_score(
    *,
    institutional_quality_score: int,
    rs_score: float,
    trend_score: int,
    sector_score: int,
    theme_weight: int,
    leader_label: str,
) -> float:
    """Raw stock quality score: leadership, RS, trend, sector, sponsorship."""
    rs_component = min(max(float(rs_score), 0), 10) if pd.notna(rs_score) else 0
    trend_component = min(max(float(trend_score) * 1.25, 0), 10)
    sector_component = min(max(float(sector_score) * 2, 0), 10)
    theme_component = min(max(float(theme_weight), 0), 10)
    leadership_bonus = 6 if leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"} else 3 if leader_label == "MOMENTUM LEADER" else 0
    score = (
        institutional_quality_score * 10 * 0.35
        + rs_component * 10 * 0.25
        + trend_component * 10 * 0.20
        + sector_component * 10 * 0.10
        + theme_component * 10 * 0.10
        + leadership_bonus
    )
    return round(min(max(score, 0), 100), 1)


def calculate_execution_score(
    *,
    entry_quality_score: int,
    tradeability_score: int,
    vcp_tightness_score: int,
    ma10_efficiency_score: int,
    risk_pct: float,
    ma10_distance: float,
    ma20_distance: float,
    character_change_flag: str,
) -> float:
    """Execution score: timing, stop distance, tightness, and extension risk."""
    score = (
        entry_quality_score * 10 * 0.35
        + tradeability_score * 10 * 0.25
        + vcp_tightness_score * 10 * 0.20
        + ma10_efficiency_score * 10 * 0.20
    )
    if pd.notna(risk_pct):
        if risk_pct > 15:
            score = min(score, 60)
        elif risk_pct > 12:
            score = min(score, 72)
        elif risk_pct > 10:
            score = min(score, 82)
    if pd.notna(ma10_distance) and ma10_distance > 12:
        score = min(score, 65)
    if pd.notna(ma20_distance) and ma20_distance > 18:
        score = min(score, 60)
    if character_change_flag == "CHARACTER CHANGE":
        score = min(score, 35)
    return round(min(max(score, 0), 100), 1)


def classify_pullback_quality(
    data: pd.DataFrame,
    pivot: PivotInfo,
    risk_pct: float,
    ma10_distance: float,
    ma20_distance: float,
    character_change_flag: str,
) -> str:
    """Label pullback structure without changing the scan universe."""
    if data.empty:
        return "NOT PULLBACK"
    latest = data.iloc[-1]
    close = float(latest.get("Close", np.nan))
    ma10 = float(latest.get("MA10", np.nan))
    ma20 = float(latest.get("MA20", np.nan))
    rsi = float(latest.get("RSI14", np.nan))
    avg_vol20 = latest.get("AvgVol20", np.nan)
    recent = data.tail(7)
    volume_controlled = pd.isna(avg_vol20) or float(latest.get("Volume", 0)) <= float(avg_vol20) * 1.1
    weak_close = float(latest.get("Close", 0)) < (float(latest.get("Low", 0)) + (float(latest.get("High", 0)) - float(latest.get("Low", 0))) * 0.35)
    wide_red = (
        float(latest.get("Close", 0)) < float(latest.get("Open", 0))
        and pd.notna(latest.get("RangePct", np.nan))
        and len(data) >= 20
        and float(latest.get("RangePct", 0)) > float(data["RangePct"].tail(20).mean()) * 1.4
    )
    tight_flag = (
        len(recent) >= 3
        and (recent["Close"].max() - recent["Close"].min()) / max(close, 0.01) * 100 <= 4
        and recent["Volume"].tail(3).mean() <= recent["Volume"].mean()
    )
    recently_extended = len(data) >= 10 and ((data["Close"].tail(10) / data["MA20"].tail(10) - 1) * 100).max() > 20

    if character_change_flag == "CHARACTER CHANGE":
        return "CLIMAX PULLBACK" if recently_extended else "HIGH RISK PULLBACK"
    if recently_extended and pd.notna(rsi) and rsi > 75 and (wide_red or weak_close):
        return "CLIMAX PULLBACK"
    if wide_red or weak_close or (pd.notna(risk_pct) and risk_pct > 12):
        return "HIGH RISK PULLBACK"
    if pd.notna(close) and pd.notna(ma10) and abs(ma10_distance) <= 3 and close >= ma10 and volume_controlled and pd.notna(rsi) and rsi > 50:
        return "CLEAN MA10 PULLBACK"
    if pd.notna(close) and pd.notna(ma20) and abs(ma20_distance) <= 4 and close >= ma20 * 0.98 and volume_controlled and pd.notna(rsi) and rsi > 45:
        return "CLEAN MA20 RESET"
    if tight_flag:
        return "TIGHT FLAG"
    return "NOT PULLBACK"


def calculate_vcp_tightness_score(data: pd.DataFrame, vcp: VcpInfo, current_setup_status: str) -> int:
    """Score VCP-style tightness from range, ATR proxy, volume, and close behavior."""
    if data.empty:
        return 0
    score = 0
    if vcp.contractions and len(vcp.contractions) >= 2 and vcp.contractions[-1] < vcp.contractions[0]:
        score += 2
    if len(data) >= 20:
        recent_range = data["RangePct"].tail(5).mean()
        prior_range = data["RangePct"].tail(20).head(10).mean()
        if pd.notna(recent_range) and pd.notna(prior_range) and recent_range < prior_range:
            score += 2
        if int((data["RangePct"].tail(10) > data["RangePct"].tail(20).mean() * 1.5).sum()) <= 1:
            score += 1
    if has_volume_contraction(data) or vcp.volume_contraction:
        score += 2
    closes = data["Close"].tail(5)
    if len(closes) >= 3 and (closes.max() - closes.min()) / max(float(closes.iloc[-1]), 0.01) * 100 <= 3:
        score += 2
    if current_setup_status not in {"FAILED", "FAILED BREAKOUT"}:
        score += 1
    else:
        score -= 3
    return int(min(max(score, 0), 10))


def calculate_tradeability_score(
    latest: pd.Series,
    risk_pct: float,
    stop: float,
    ma10_distance: float,
) -> int:
    """Score whether the stop, volatility, and liquidity make the setup tradable."""
    score = 0
    if pd.notna(risk_pct):
        if risk_pct <= 8:
            score += 4
        elif risk_pct <= 10:
            score += 3
        elif risk_pct <= 12:
            score += 2
        elif risk_pct <= 15:
            score += 1
        elif risk_pct > 25:
            score -= 3
    range_pct = latest.get("RangePct", np.nan)
    if pd.notna(range_pct):
        if float(range_pct) <= 3:
            score += 2
        elif float(range_pct) <= 5:
            score += 1
        elif float(range_pct) > 8:
            score -= 2
    close = float(latest.get("Close", np.nan))
    ma10 = float(latest.get("MA10", np.nan))
    ma20 = float(latest.get("MA20", np.nan))
    avg_dollar_volume = latest.get("AvgDollarVol50", np.nan)
    if pd.notna(stop) and pd.notna(ma10) and pd.notna(ma20) and stop <= max(ma10, ma20) * 1.01:
        score += 1
    if pd.notna(ma10_distance) and abs(ma10_distance) <= 8:
        score += 1
    if pd.notna(avg_dollar_volume) and float(avg_dollar_volume) >= 50_000_000:
        score += 2
    elif pd.notna(avg_dollar_volume) and float(avg_dollar_volume) >= 20_000_000:
        score += 1
    if pd.notna(close) and pd.notna(stop) and stop >= close:
        score -= 3
    return int(min(max(score, 0), 10))


def detect_institutional_action(data: pd.DataFrame) -> str:
    """Detect accumulation, support, or distribution from price/volume behavior."""
    if len(data) < 30:
        return "N/A"
    recent = data.tail(20)
    closes = recent["Close"]
    ma10 = recent["MA10"]
    support_ma10 = int(((recent["Low"] <= ma10 * 1.01) & (closes >= ma10)).sum())
    tight_closes = (closes.tail(5).max() - closes.tail(5).min()) / closes.iloc[-1] * 100 <= 3
    low_volume_pullbacks = has_volume_contraction(data)
    pct_change = data["Close"].pct_change() * 100
    accumulation_days = int(((pct_change.tail(20) >= 0.4) & (data["Volume"].tail(20) > data["Volume"].shift(1).tail(20))).sum())
    distribution_days = distribution_days_count(data, lookback=20)
    avg_vol20 = data.iloc[-1].get("AvgVol20", np.nan)
    pocket_pivot = bool(
        pd.notna(avg_vol20)
        and data.iloc[-1]["Close"] > data.iloc[-1]["MA10"]
        and data.iloc[-1]["Volume"] > 1.2 * avg_vol20
        and data.iloc[-1]["Close"] > data.iloc[-2]["High"]
    )

    if distribution_days >= 4 and accumulation_days <= 2:
        return "DISTRIBUTION"
    if pocket_pivot or (support_ma10 >= 3 and tight_closes and accumulation_days >= 3):
        return "ACCUMULATION"
    if support_ma10 >= 2 and low_volume_pullbacks:
        return "SUPPORTING ACTION"
    return "NEUTRAL"


def calculate_breakout_quality_score(
    data: pd.DataFrame,
    pivot: PivotInfo,
    rvol: float,
    rs_score: float,
    market_environment: str,
    extended: bool,
    stage_label: str,
    institutional_tightness_score: int = 0,
    sector_leadership_status: str = "NEUTRAL SECTOR",
    ma10_distance: float = np.nan,
) -> int:
    """Score the quality of a breakout trigger from 0 to 10."""
    latest = data.iloc[-1]
    score = 0
    avg_vol20 = latest.get("AvgVol20", np.nan)
    daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    close_position = (float(latest["Close"]) - float(latest["Low"])) / daily_range
    upper_wick_pct = (float(latest["High"]) - max(float(latest["Open"]), float(latest["Close"]))) / daily_range
    close_band_pct = (
        (data["Close"].tail(5).max() - data["Close"].tail(5).min()) / latest["Close"] * 100
        if len(data) >= 5 and latest["Close"]
        else np.nan
    )
    if close_position >= 0.75:
        score += 2
    elif close_position >= 0.5:
        score += 1
    if pd.notna(close_band_pct) and close_band_pct <= 3:
        score += 2
    elif pd.notna(close_band_pct) and close_band_pct <= 5:
        score += 1

    if institutional_tightness_score >= 7 or has_volume_contraction(data):
        score += 2
    if pd.notna(rvol) and rvol > 2:
        score += 2
    elif pd.notna(rvol) and rvol >= 1.5:
        score += 1
    elif pd.notna(avg_vol20) and latest["Volume"] > avg_vol20 * 1.25:
        score += 2
    if pivot.label == "Breakout in progress" or (pd.notna(pivot.distance_pct) and -2 <= pivot.distance_pct <= 5):
        score += 1
    if score_at_least(rs_score, 7):
        score += 1
    if sector_leadership_status == "LEADING SECTOR":
        score += 1
    if market_environment == "CONFIRMED UPTREND":
        score += 1

    wide_candle = bool(latest.get("RangePct", np.nan) > data["RangePct"].tail(20).mean() * 1.8) if len(data) >= 20 else False
    if extended or (pd.notna(ma10_distance) and ma10_distance > 12):
        score -= 2
    if wide_candle:
        score -= 2
    if close_position < 0.5:
        score -= 2
    if upper_wick_pct >= 0.4:
        score -= 2
    if pd.notna(rvol) and rvol < 1:
        score -= 2
    elif pd.notna(avg_vol20) and latest["Volume"] < avg_vol20 and pivot.label == "Breakout in progress":
        score -= 2
    if pd.notna(latest.get("RSI14", np.nan)) and latest["RSI14"] > 85 and pd.notna(ma10_distance) and ma10_distance > 8:
        score -= 2
    if stage_label in {"LATE STAGE 2", "STAGE 3 RISK", "STAGE 4"}:
        score -= 1
    return int(min(max(score, 0), 10))


def calculate_eod_breakout_quality_score(
    data: pd.DataFrame | None,
    pivot: PivotInfo,
    rs_score: float,
    tightness_score: int,
    volume_dry_up: bool,
    stage_label: str,
    institutional_action: str,
    risk_pct: float,
    setup_grade: str,
    vcp_status: str,
    setup_type: str,
    institutional_tightness_score: int = 0,
    sector_leadership_status: str = "NEUTRAL SECTOR",
) -> int:
    """Score EOD breakout quality without requiring intraday RVOL."""
    score = 0
    latest = data.iloc[-1] if isinstance(data, pd.DataFrame) and not data.empty else None
    if latest is not None:
        daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
        close_position = (float(latest["Close"]) - float(latest["Low"])) / daily_range
        upper_wick_pct = (float(latest["High"]) - max(float(latest["Open"]), float(latest["Close"]))) / daily_range
        avg_vol20 = latest.get("AvgVol20", np.nan)
        if close_position >= 0.75:
            score += 2
        elif close_position >= 0.5:
            score += 1
        if upper_wick_pct >= 0.4:
            score -= 2
        if close_position < 0.5:
            score -= 2
        if pd.notna(avg_vol20) and pivot.label == "Breakout in progress" and latest["Volume"] < avg_vol20:
            score -= 2
        if pd.notna(avg_vol20) and pivot.label == "Breakout in progress" and latest["Volume"] > avg_vol20 * 1.25:
            score += 2
        ma10_distance = (latest["Close"] - latest["MA10"]) / latest["MA10"] * 100 if latest["MA10"] else np.nan
        if pd.notna(latest.get("RSI14", np.nan)) and latest["RSI14"] > 85 and pd.notna(ma10_distance) and ma10_distance > 8:
            score -= 2
        avg_range20 = data["RangePct"].tail(20).mean() if isinstance(data, pd.DataFrame) and len(data) >= 20 else np.nan
        if pd.notna(avg_range20) and latest.get("RangePct", np.nan) > avg_range20 * 1.8:
            score -= 2
    distance = pivot.distance_pct
    if pd.notna(distance):
        if pivot.label == "Breakout in progress" or -3 <= distance <= 3:
            score += 2
        elif 3 < distance <= 5:
            score += 1

    if score_at_least(rs_score, 8):
        score += 2
    elif score_at_least(rs_score, 6):
        score += 1

    if institutional_tightness_score >= 8:
        score += 2
    elif institutional_tightness_score >= 6:
        score += 1
    if tightness_score >= 4:
        score += 2
    elif tightness_score >= 3:
        score += 1
    if volume_dry_up:
        score += 1

    if vcp_status == "VALID VCP" or setup_type == "TRUE VCP":
        score += 2
    elif vcp_status == "EARLY VCP" or setup_type in {"EARLY VCP", "BASE BUILDING", "PULLBACK TO MA10", "PULLBACK TO MA20"}:
        score += 1

    if stage_label in {"EARLY STAGE 2", "MID STAGE 2"}:
        score += 1
    elif stage_label in {"STAGE 3 RISK", "STAGE 4"}:
        score -= 2

    if institutional_action in {"ACCUMULATION", "SUPPORTING ACTION"}:
        score += 1
    elif institutional_action == "DISTRIBUTION":
        score -= 1

    if pd.notna(risk_pct):
        if risk_pct <= 8:
            score += 1
        elif risk_pct > 10:
            score -= 1

    if setup_grade == "A+":
        score += 2
    elif setup_grade == "A":
        score += 1
    elif setup_grade == "C":
        score -= 1
    elif setup_grade == "Reject":
        score -= 2
    if sector_leadership_status == "LEADING SECTOR":
        score += 1
    elif sector_leadership_status in {"LAGGING SECTOR", "CYCLICAL RISK"}:
        score -= 1

    return int(min(max(score, 0), 10))


def determine_watch_type(
    *,
    signal_state: str,
    setup_type: str,
    action: str,
    breakout_alert: str,
    volume_confirmation: str,
    earnings_risk_label: str,
    resistance_breakout_mode: str,
    pivot: PivotInfo,
    healthy_pullback_label: str = "",
    institutional_tightness_score: int = 0,
    setup_type_label: str = "",
) -> str:
    """Classify why a non-BUY-NOW setup belongs on the watchlist."""
    if signal_state == "BUY NOW":
        return "NONE"
    if earnings_risk_label == "HIGH RISK" and signal_state in {"WATCH", "BUY ON BREAKOUT", "WAIT PULLBACK"}:
        return "EARNINGS RISK WATCH"
    if healthy_pullback_label == "HEALTHY PULLBACK" or setup_type in {"HEALTHY PULLBACK WATCH"}:
        return "HEALTHY PULLBACK"
    if institutional_tightness_score >= 7:
        return "TIGHT BASE"
    if setup_type == "POST-BREAKOUT DIGESTION":
        return "POST-BREAKOUT DIGESTION"
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH" or setup_type == "RESISTANCE BREAKOUT WATCH":
        return "RESISTANCE BREAKOUT WATCH"
    if setup_type == "MOMENTUM BREAKOUT EXCEPTION" or action == "MOMENTUM BREAKOUT":
        return "MOMENTUM WATCH"
    if setup_type == "PULLBACK TO MA10":
        return "WAIT MA10 SUPPORT"
    if setup_type == "PULLBACK TO MA20" or signal_state == "WAIT PULLBACK":
        return "WAIT MA20 SUPPORT"
    if signal_state == "EXTENDED DO NOT CHASE":
        return "EXTENDED RESET"
    if signal_state == "BUY ON BREAKOUT" and volume_confirmation != "YES":
        return "WAIT VOLUME"
    if breakout_alert == "NEAR BREAKOUT" or (pd.notna(pivot.distance_pct) and -1 <= pivot.distance_pct <= 5):
        return "NEAR PIVOT"
    return "NONE"


def earnings_intelligence_label(earnings_label: str, post_earnings_label: str) -> str:
    """Summarize earnings context into one tradable label."""
    if earnings_label == "HIGH RISK":
        return "EARNINGS RISK HIGH"
    if earnings_label == "MEDIUM RISK":
        return "EARNINGS SOON"
    if post_earnings_label in {"EARNINGS GAP UP HOLDING", "EARNINGS GAP DOWN RECOVERING"}:
        return "POST-EARNINGS BREAKOUT"
    return "NO EARNINGS EDGE"


def first_valid_frame(*frames: pd.DataFrame | None) -> pd.DataFrame | None:
    """Return the first non-empty dataframe from a list of optional benchmark frames."""
    for frame in frames:
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame
    return None


def select_rs_benchmarks(ticker: str, benchmark_data: Dict[str, pd.DataFrame]) -> Tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Use HK benchmarks for HK tickers and US benchmarks for US tickers."""
    if ticker.endswith(".HK"):
        primary = first_valid_frame(benchmark_data.get("^HSI"), benchmark_data.get("SPY"))
        fallback = first_valid_frame(benchmark_data.get("2800.HK"), benchmark_data.get("QQQ"), primary)
        return primary, fallback
    return first_valid_frame(benchmark_data.get("SPY")), first_valid_frame(benchmark_data.get("QQQ"))


def numeric_or_na(value: float | int | str | None) -> float:
    """Convert optional display values to a numeric value, preserving missing data as NaN."""
    converted = pd.to_numeric(value, errors="coerce")
    return float(converted) if pd.notna(converted) else np.nan


def score_at_least(value: float | int | str | None, threshold: float) -> bool:
    """Check numeric thresholds without treating missing RS as zero."""
    numeric = numeric_or_na(value)
    return bool(pd.notna(numeric) and numeric >= threshold)


def format_score(value: float | int | str | None) -> str:
    """Format optional scores for human-readable decision text."""
    numeric = numeric_or_na(value)
    return "N/A" if pd.isna(numeric) else f"{numeric:g}"


def calculate_rs_score(data: pd.DataFrame, spy_data: pd.DataFrame | None, qqq_data: pd.DataFrame | None) -> float:
    """Score relative strength against the right benchmarks over 1M, 3M, and 6M."""
    score = 0.0
    weights = {21: 2.0, 63: 1.5, 126: 1.5}
    comparisons = 0

    for days, weight in weights.items():
        stock_return = period_return(data, days)
        for benchmark in (spy_data, qqq_data):
            benchmark_return = period_return(benchmark, days)
            if pd.isna(stock_return) or pd.isna(benchmark_return):
                continue
            comparisons += 1
            outperformance = stock_return - benchmark_return
            if outperformance > 0:
                score += weight
            elif outperformance > -2:
                score += weight * 0.5

    if comparisons == 0:
        return np.nan
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


def is_momentum_breakout_candidate(
    final_score: float,
    rs_score: float,
    explosive_score: int,
    trend_score: int,
    technical_score: int,
    breakout_alert: str,
    latest: pd.Series,
    volume_dry_up: bool,
    volume_confirmation: str,
    risk_pct: float,
    ma10_distance: float,
    earnings_risk_label: str,
    ma10_rising: bool,
    breakout_quality_score: int = 0,
    rvol: float = np.nan,
    live_mode: bool = False,
) -> bool:
    """Allow exceptional high-momentum breakouts even when they are not pure VCPs."""
    price_above_key_mas = latest["Close"] > latest["MA10"] and latest["Close"] > latest["MA20"] and latest["Close"] > latest["MA50"]
    avg_vol20 = latest.get("AvgVol20", np.nan)
    exceptional_volume = pd.notna(avg_vol20) and avg_vol20 > 0 and latest["Volume"] >= 1.3 * avg_vol20
    volume_ok = volume_dry_up or volume_confirmation == "YES" or exceptional_volume or (pd.notna(rvol) and rvol >= 1.5)
    return bool(
        final_score >= 90
        and score_at_least(rs_score, 8)
        and explosive_score >= 8
        and trend_score >= 7
        and technical_score >= 7
        and breakout_alert in {"BREAKOUT IN PROGRESS", "CONFIRMED BREAKOUT"}
        and price_above_key_mas
        and ma10_rising
        and volume_ok
        and (not live_mode or breakout_quality_score >= 7)
        and pd.notna(risk_pct)
        and risk_pct <= 10
        and pd.notna(ma10_distance)
        and ma10_distance <= 12
        and earnings_risk_label != "HIGH RISK"
    )


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
    if row.get("Signal State") == "BUY ON BREAKOUT":
        return "WATCH FOR BREAKOUT"
    if row.get("Setup Type") == "MOMENTUM BREAKOUT EXCEPTION":
        return "MOMENTUM BREAKOUT"
    if row.get("Action Label") == "EXTENDED":
        return "TOO EXTENDED"
    if row.get("Trade") == "YES":
        return "BEST BUY SETUP"
    if row.get("Action Label") == "PULLBACK ENTRY":
        return "PULLBACK SETUP"
    return "WATCH FOR BREAKOUT"


def build_ai_trading_notes(row: dict) -> str:
    """Create compact rule-based notes for table, cards, and alerts."""
    return (
        f"{row['ticker']} {row.get('Signal State', row['Action Label'])} | {row.get('Setup Quality Grade', 'N/A')} | "
        f"{row.get('Setup Type', 'N/A')} | {row['VCP Status']} | "
        f"Final {row['Final Score']}/100 | BQ {row.get('Breakout Quality Score', 'N/A')}/10 | "
        f"RVOL {row.get('RVOL', 'N/A')} | {row.get('Live Breakout Status', row['Breakout Alert'])} | "
        f"Risk {row['Risk %']}% | TP quality {row.get('TP Quality Score', 'N/A')}/10 | Earnings {row['Earnings Risk']}"
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
    rs_component = 5.0 if pd.isna(rs_score) else float(rs_score)
    score = (
        (trend_score / 7) * 25
        + (technical_score / 8) * 25
        + (rs_component / 10) * 20
        + (sector_score / 3) * 10
        + (market_score / 4) * 10
        + (tightness_score / 5) * 10
    )
    return round(min(max(score, 0), 100), 1)


INSTITUTIONAL_LEADER_TICKERS = {
    "NVDA", "AVGO", "TSM", "ASML", "AMD", "MSFT", "AAPL", "AMZN", "META", "GOOGL", "GOOG",
    "DELL", "SMCI", "ANET", "ARM", "LRCX", "KLAC", "AMAT", "PANW", "CRWD", "NOW", "TSLA",
}
STRONG_MIDCAP_LEADER_TICKERS = {"VRT", "APP", "PLTR", "NET", "DDOG", "SNOW", "COIN", "HOOD", "GEV", "VST", "CEG"}
CYCLICAL_SECTOR_GROUPS = {"Energy", "Materials"}
DEFENSIVE_SECTOR_GROUPS = {"Healthcare", "Utilities", "Consumer", "Real Estate"}
CYCLICAL_INDUSTRY_TERMS = ("steel", "commodity", "mining", "metal", "oil", "gas", "materials", "coal")
LEADING_THEME_GROUPS = {
    "AI / Semis",
    "Power / Utilities",
    "Nuclear / Uranium",
    "Energy",
    "Financials",
    "Industrials",
    "Crypto",
    "Semiconductors",
    "Technology",
}


def sector_leadership_status_and_weight(
    *,
    sector_info: dict,
    sector_leadership: str,
    sector_score: int,
    rs_score: float,
) -> Tuple[str, int]:
    """Classify sector context without extra data fetches."""
    sector_group = sector_info.get("sector_group", "Other")
    theme_group = sector_info.get("theme_group", sector_group)
    industry_text = f"{sector_info.get('sector', '')} {sector_info.get('industry', '')} {theme_group}".lower()

    cyclical = sector_group in CYCLICAL_SECTOR_GROUPS or any(term in industry_text for term in CYCLICAL_INDUSTRY_TERMS)
    leading_theme = theme_group in {"AI / Semis", "Semiconductors", "Technology", "Power / Utilities"} or sector_group in {"Semiconductors", "Technology"}

    if cyclical and not (sector_leadership == "Leader" and sector_score >= 3):
        return "CYCLICAL RISK", -3
    if leading_theme and sector_leadership == "Leader" and sector_score >= 3:
        return "LEADING SECTOR", 8
    if sector_leadership == "Leader" and sector_score >= 3:
        return "LEADING SECTOR", 5
    if sector_score >= 2 or (leading_theme and score_at_least(rs_score, 7)):
        return "IMPROVING SECTOR", 3
    if sector_group in DEFENSIVE_SECTOR_GROUPS and not score_at_least(rs_score, 8):
        return "LAGGING SECTOR", -2
    if sector_leadership == "Laggard":
        return "LAGGING SECTOR", -3
    return "NEUTRAL SECTOR", 0


def calculate_theme_weight(ticker: str, sector_info: dict, sector_leadership: str, sector_score: int, rs_score: float) -> int:
    """Score current institutional theme strength without new data fetches."""
    symbol = ticker.upper()
    sector_group = sector_info.get("sector_group", "Other")
    theme_group = sector_info.get("theme_group", sector_group)
    industry_text = f"{sector_info.get('sector', '')} {sector_info.get('industry', '')} {theme_group}".lower()
    score = 4
    hot_terms = ("ai", "semiconductor", "data center", "power", "electrical", "nuclear", "uranium", "cyber", "cloud")
    if theme_group in {"AI / Semis", "Semiconductors", "Technology", "Power / Utilities", "Nuclear / Uranium"} or any(term in industry_text for term in hot_terms):
        score += 4
    elif sector_group in {"Financials", "Industrials"} and (sector_leadership == "Leader" or sector_score >= 2):
        score += 3
    elif sector_leadership == "Leader" or sector_score >= 2:
        score += 2
    if symbol in INSTITUTIONAL_LEADER_TICKERS or symbol in STRONG_MIDCAP_LEADER_TICKERS:
        score += 1
    if sector_group in DEFENSIVE_SECTOR_GROUPS and not score_at_least(rs_score, 8):
        score -= 2
    if sector_group in CYCLICAL_SECTOR_GROUPS and sector_leadership != "Leader":
        score -= 2
    return int(min(max(score, 0), 10))


def calculate_institutional_quality_score(
    *,
    ticker: str,
    sector_info: dict,
    sector_leadership: str,
    sector_score: int,
    latest: pd.Series,
    rs_score: float,
    trend_score: int,
    stage_label: str,
    volume_confirmation: str,
    ma10_distance: float,
    rsi: float,
    theme_weight: int = 0,
) -> int:
    """Score whether institutions are likely to support the setup, without extra API calls."""
    symbol = ticker.upper()
    sector_group = sector_info.get("sector_group", "Other")
    theme_group = sector_info.get("theme_group", sector_group)
    industry_text = f"{sector_info.get('sector', '')} {sector_info.get('industry', '')} {theme_group}".lower()
    score = 0

    if theme_group in LEADING_THEME_GROUPS or sector_group in {"Semiconductors", "Technology", "Energy", "Financials", "Industrials"}:
        score += 2
    elif sector_leadership == "Leader" or sector_score >= 2:
        score += 1

    if symbol in INSTITUTIONAL_LEADER_TICKERS:
        score += 2
    elif symbol in STRONG_MIDCAP_LEADER_TICKERS or (score_at_least(rs_score, 7) and trend_score >= 7):
        score += 1

    avg_dollar_volume = latest.get("AvgDollarVol50", np.nan)
    if pd.notna(avg_dollar_volume) and avg_dollar_volume >= 500_000_000:
        score += 2
    elif pd.notna(avg_dollar_volume) and avg_dollar_volume >= 50_000_000:
        score += 1

    catalyst_terms = ("ai", "data center", "semiconductor", "cloud", "cyber", "nuclear", "power", "bitcoin", "crypto")
    if any(term in industry_text for term in catalyst_terms) or symbol in INSTITUTIONAL_LEADER_TICKERS:
        score += 2
    elif trend_score >= 6 and score_at_least(rs_score, 6):
        score += 1

    if theme_group in LEADING_THEME_GROUPS or sector_leadership == "Leader":
        score += 2
    elif sector_score >= 2:
        score += 1

    if sector_group in CYCLICAL_SECTOR_GROUPS and sector_leadership != "Leader" and sector_score < 3:
        score -= 2
    if stage_label in {"LATE STAGE 2", "STAGE 3 RISK"}:
        score -= 2
    if pd.notna(rsi) and rsi > 85 and pd.notna(ma10_distance) and ma10_distance > 8:
        score -= 2
    if volume_confirmation != "YES" and latest.get("Close", np.nan) > latest.get("MA10", np.inf):
        score -= 1
    if sector_group in DEFENSIVE_SECTOR_GROUPS and theme_group not in LEADING_THEME_GROUPS and sector_leadership != "Leader":
        score -= 1
    if theme_weight >= 8:
        score += 1
    elif theme_weight <= 3:
        score -= 1

    return int(min(max(score, 0), 10))


def leader_quality_label(
    *,
    ticker: str,
    sector_info: dict,
    rs_score: float,
    trend_score: int,
    sector_leadership: str,
    sector_score: int,
    institutional_quality_score: int,
) -> str:
    """Classify market leadership context separately from chart quality."""
    symbol = ticker.upper()
    sector_group = sector_info.get("sector_group", "Other")
    theme_group = sector_info.get("theme_group", sector_group)
    strong_rs_trend = score_at_least(rs_score, 7) and trend_score >= 7
    if symbol in INSTITUTIONAL_LEADER_TICKERS and strong_rs_trend and institutional_quality_score >= 7:
        return "INSTITUTIONAL LEADER"
    if (sector_leadership == "Leader" or sector_score >= 3 or sector_group == "Semiconductors") and strong_rs_trend:
        return "SECTOR LEADER"
    if score_at_least(rs_score, 8) and trend_score >= 6:
        return "MOMENTUM LEADER"
    if sector_group in CYCLICAL_SECTOR_GROUPS or theme_group in {"Energy", "Materials"}:
        return "CYCLICAL BREAKOUT"
    if sector_group in DEFENSIVE_SECTOR_GROUPS:
        return "DEFENSIVE WATCH"
    return "LAGGARD / AVOID" if not score_at_least(rs_score, 5) else "MOMENTUM LEADER"


def adjusted_final_score(
    final_score: float,
    institutional_quality_score: int,
    sector_score: int,
    market_score: int,
    sector_leadership_weight: int = 0,
    institutional_tightness_score: int = 0,
    theme_weight: int = 0,
) -> float:
    """Blend chart score with institutional and market context for ranking."""
    tightness_boost = 4 if institutional_tightness_score >= 8 else 2 if institutional_tightness_score >= 7 else 0
    score = (
        float(final_score) * 0.65
        + institutional_quality_score * 3
        + sector_score * 1.5
        + market_score
        + sector_leadership_weight
        + tightness_boost
        + theme_weight * 0.8
    )
    return round(min(max(score, 0), 100), 1)


def calculate_ma10_efficiency_score(data: pd.DataFrame) -> int:
    """Score how efficiently price is respecting MA10 support."""
    if data is None or len(data) < 3:
        return 0
    latest = data.iloc[-1]
    score = 0
    close = float(latest["Close"])
    ma10 = float(latest.get("MA10", np.nan))
    avg_vol20 = latest.get("AvgVol20", np.nan)
    daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    close_position = (close - float(latest["Low"])) / daily_range
    if pd.notna(ma10) and close >= ma10:
        score += 3
    if pd.notna(ma10) and abs(close / ma10 - 1) <= 0.03:
        score += 2
    if pd.notna(avg_vol20) and latest["Volume"] < avg_vol20:
        score += 2
    if close_position >= 0.55:
        score += 2
    recent = data.tail(5)
    high_volume_red = ((recent["Close"] < recent["Open"]) & (recent["Volume"] > recent["AvgVol20"] * 1.2)).sum() if "AvgVol20" in recent else 0
    if high_volume_red == 0:
        score += 1
    if pd.notna(ma10) and close < ma10 and pd.notna(avg_vol20) and latest["Volume"] > avg_vol20 * 1.2:
        score -= 4
    if close_position < 0.35:
        score -= 2
    if high_volume_red >= 2:
        score -= 2
    return int(min(max(score, 0), 10))


def detect_character_change(data: pd.DataFrame, pivot: PivotInfo, breakout_alert: str, current_setup_status: str) -> str:
    """Flag whether a pullback is normal or has changed character."""
    if data is None or len(data) < 3:
        return "NONE"
    latest = data.iloc[-1]
    close = float(latest["Close"])
    ma10 = float(latest.get("MA10", np.nan))
    ma20 = float(latest.get("MA20", np.nan))
    avg_vol20 = latest.get("AvgVol20", np.nan)
    daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    close_position = (close - float(latest["Low"])) / daily_range
    heavy_volume = pd.notna(avg_vol20) and latest["Volume"] > avg_vol20 * 1.3
    recent = data.tail(5)
    distribution_days = ((recent["Close"] < recent["Open"]) & (recent["Volume"] > recent["AvgVol20"] * 1.2)).sum() if "AvgVol20" in recent else 0
    if (pd.notna(ma20) and close < ma20 and heavy_volume) or current_setup_status == "FAILED BREAKOUT" or (breakout_alert == "FAILED BREAKOUT") or (close_position < 0.3 and distribution_days >= 2):
        return "CHARACTER CHANGE"
    if pd.notna(ma10) and close < ma10 and heavy_volume:
        return "CAUTION"
    if pd.notna(ma10) and close >= ma10 * 0.98 and (not heavy_volume):
        return "NORMAL PULLBACK"
    if pd.notna(ma20) and close >= ma20 and (not heavy_volume):
        return "NORMAL PULLBACK"
    return "NONE"


def entry_timing_label(
    *,
    latest: pd.Series,
    pivot: PivotInfo,
    risk_pct: float,
    ma10_distance: float,
    rsi: float,
    setup_type: str,
    breakout_alert: str,
    character_change_flag: str,
) -> str:
    """Describe the entry timing separately from stock quality."""
    if character_change_flag == "CHARACTER CHANGE" or setup_type == "FAILED":
        return "FAILED SETUP"
    close = float(latest["Close"])
    ma10 = float(latest.get("MA10", np.nan))
    ma20 = float(latest.get("MA20", np.nan))
    daily_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    upper_wick = (float(latest["High"]) - max(float(latest["Open"]), close)) / daily_range
    wide_candle = bool(latest.get("RangePct", np.nan) > 6)
    if (pd.notna(ma10_distance) and ma10_distance > 15) or (pd.notna(rsi) and rsi > 85 and wide_candle):
        return "TOO LATE"
    if (pd.notna(ma10_distance) and ma10_distance > 10) or (pd.notna(risk_pct) and risk_pct > 12):
        return "EXTENDED - WAIT"
    if breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}:
        return "BREAKOUT CONFIRMED"
    if pd.notna(risk_pct) and risk_pct <= 8 and pd.notna(pivot.distance_pct) and 0 <= pivot.distance_pct <= 5 and upper_wick < 0.35:
        return "IDEAL ENTRY ZONE"
    if pd.notna(ma10) and abs(close / ma10 - 1) <= 0.03:
        return "MA10 PULLBACK"
    if pd.notna(ma20) and abs(close / ma20 - 1) <= 0.03:
        return "MA20 PULLBACK"
    if pd.notna(pivot.distance_pct) and 0 <= pivot.distance_pct <= 5:
        return "NEAR PIVOT"
    return "EXTENDED - WAIT" if pd.notna(ma10_distance) and ma10_distance > 8 else "NEAR PIVOT"


def executable_score_and_grade(
    *,
    entry_quality_score: int,
    risk_pct: float,
    healthy_pullback_score: int,
    institutional_tightness_score: int,
    ma10_efficiency_score: int,
    institutional_quality_score: int,
    theme_weight: int,
    breakout_quality_score: int,
    ma10_distance: float,
    pivot: PivotInfo,
    volume_dry_up: bool,
    breakout_alert: str,
    signal_state: str,
    hard_reject: bool,
    character_change_flag: str,
    latest: pd.Series,
    leader_label: str,
) -> Tuple[float, str, str]:
    """Grade tradability now, separate from long-term stock quality."""
    risk_component = 10
    if pd.notna(risk_pct):
        if risk_pct <= 8:
            risk_component = 10
        elif risk_pct <= 10:
            risk_component = 8
        elif risk_pct <= 12:
            risk_component = 6
        elif risk_pct <= 15:
            risk_component = 4
        elif risk_pct <= 25:
            risk_component = 2
        else:
            risk_component = 0
    tight_pullback_component = max(healthy_pullback_score, institutional_tightness_score, ma10_efficiency_score)
    sector_inst_component = min(10, institutional_quality_score * 0.65 + theme_weight * 0.35)
    raw = (
        entry_quality_score * 10 * 0.30
        + risk_component * 10 * 0.20
        + tight_pullback_component * 10 * 0.20
        + sector_inst_component * 10 * 0.15
        + breakout_quality_score * 10 * 0.15
    )
    bonus = 0
    if healthy_pullback_score >= 7 and volume_dry_up and ma10_efficiency_score >= 7:
        bonus += 15
    if pd.notna(pivot.distance_pct) and 0 <= pivot.distance_pct <= 5 and volume_dry_up:
        bonus += 10
    latest_range = max(float(latest["High"]) - float(latest["Low"]), 0.01)
    close_position = (float(latest["Close"]) - float(latest["Low"])) / latest_range
    if breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"} and close_position >= 0.65 and pd.notna(risk_pct) and risk_pct <= 10:
        bonus += 15
    score = raw + bonus
    if pd.notna(ma10_distance) and ma10_distance > 12:
        score = min(score, 65)
    if pd.notna(risk_pct) and risk_pct > 15:
        score = min(score, 60)
    if pd.notna(risk_pct) and risk_pct > 25:
        score = min(score, 40)
    if character_change_flag == "CHARACTER CHANGE":
        score = min(score, 35)
    if float(latest.get("Close", np.nan)) < float(latest.get("MA50", np.nan)):
        score = min(score, 30)
    score = round(min(max(score, 0), 100), 1)
    if character_change_flag == "CHARACTER CHANGE" or hard_reject or score < 50:
        grade = "C - AVOID"
        reason = "C - AVOID: late-stage or damaged setup with poor reward/risk."
    elif score >= 75 and pd.notna(risk_pct) and risk_pct <= 10 and signal_state in {"BUY NOW", "BUY ON BREAKOUT", "WATCH"} and not (pd.notna(ma10_distance) and ma10_distance > 10):
        grade = "A - EXECUTABLE NOW"
        reason = "A - EXECUTABLE NOW: clean setup near pivot/MA support, strong theme, risk controlled."
    else:
        grade = "B - WATCHLIST"
        if pd.notna(ma10_distance) and ma10_distance > 10:
            reason = "B - WATCHLIST: high quality stock but entry is extended; wait for MA10 pullback."
        elif pd.notna(risk_pct) and risk_pct > 10:
            reason = "B - WATCHLIST: strong setup but risk is above ideal range; wait for tighter entry."
        else:
            reason = "B - WATCHLIST: good stock, but wait for trigger or confirmation."
    if (
        leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}
        and grade == "C - AVOID"
        and not hard_reject
        and character_change_flag != "CHARACTER CHANGE"
        and pd.notna(risk_pct)
        and risk_pct <= 25
        and signal_state in {"WATCH", "WAIT PULLBACK", "EXTENDED DO NOT CHASE"}
    ):
        grade = "B - WATCHLIST"
        reason = "B - WATCHLIST: institutional leader, but entry timing is not executable yet."
    return score, grade, reason


def calibrate_executable_grade(
    *,
    executable_grade: str,
    executable_score: float,
    executable_reason: str,
    signal_state: str,
    trade: str,
    watchlist_flag: str,
    risk_pct: float,
    entry_timing: str,
    leader_label: str,
    character_change_flag: str,
    hard_reject: bool,
    setup_type: str,
    breakout_alert: str,
    rs_score: float,
    sector_leadership_status: str,
) -> Tuple[str, str]:
    """Keep executable grade aligned with the final displayed signal state."""
    grade = executable_grade
    reason = executable_reason
    risk_ok = pd.notna(risk_pct) and risk_pct <= 10
    clean_timing = entry_timing in {"IDEAL ENTRY ZONE", "NEAR PIVOT", "BREAKOUT CONFIRMED"}
    clean_ma10_trigger = entry_timing == "MA10 PULLBACK" and breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}
    buy_now_ok = signal_state == "BUY NOW" and trade == "YES"
    laggard = leader_label == "LAGGARD / AVOID"
    weak_laggard = laggard and (
        (pd.notna(rs_score) and rs_score < 7)
        or sector_leadership_status in {"LAGGING SECTOR", "CYCLICAL RISK"}
        or character_change_flag == "CHARACTER CHANGE"
    )

    a_allowed = (
        buy_now_ok
        and risk_ok
        and (clean_timing or clean_ma10_trigger)
        and not laggard
        and character_change_flag != "CHARACTER CHANGE"
        and not hard_reject
    )

    if signal_state == "REJECT" or hard_reject or character_change_flag == "CHARACTER CHANGE":
        grade = "C - AVOID"
        reason = "C - AVOID: hard reject, failed setup, or character change."
    elif weak_laggard and signal_state == "REJECT":
        grade = "C - AVOID"
        reason = "C - AVOID: laggard profile with weak RS, poor sector, or damaged structure."
    elif signal_state in {"BUY ON BREAKOUT", "WATCH"}:
        grade = "B - WATCHLIST"
        if signal_state == "BUY ON BREAKOUT":
            reason = "B - WATCHLIST: near breakout trigger, but wait for confirmation before execution."
        elif setup_type == "HEALTHY PULLBACK WATCH" and leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}:
            reason = "B - WATCHLIST: healthy MA10 pullback in leading stock; wait for trigger or breakout confirmation."
        else:
            reason = "B - WATCHLIST: good stock, but wait for trigger or confirmation."
    elif signal_state == "WAIT PULLBACK":
        if (pd.notna(risk_pct) and risk_pct > 25) or entry_timing in {"TOO LATE", "FAILED SETUP"}:
            grade = "C - AVOID"
            reason = "C - AVOID: entry is too late or risk is too wide."
        else:
            grade = "B - WATCHLIST"
            reason = "B - WATCHLIST: quality may be present, but wait for pullback or tighter risk."
    elif signal_state == "EXTENDED DO NOT CHASE":
        grade = "B - WATCHLIST" if not laggard and not (pd.notna(risk_pct) and risk_pct > 25) else "C - AVOID"
        reason = (
            "B - WATCHLIST: high quality stock but entry is extended; wait for MA10 pullback."
            if grade == "B - WATCHLIST"
            else "C - AVOID: extended laggard or risk too wide."
        )
    elif grade == "A - EXECUTABLE NOW" and not a_allowed:
        grade = "B - WATCHLIST"
        reason = (
            "B - WATCHLIST: good setup, but not actionable today without a BUY NOW state."
            if grade == "B - WATCHLIST"
            else "B - WATCHLIST: laggard profile is not executable today."
        )
    elif laggard and grade == "A - EXECUTABLE NOW":
        grade = "B - WATCHLIST"
        reason = "B - WATCHLIST: structure may be acceptable, but laggard quality prevents executable A grade."

    if grade == "A - EXECUTABLE NOW":
        reason = "A - EXECUTABLE NOW: clean actionable setup, signal aligned, risk controlled."
    elif grade == "B - WATCHLIST" and not reason.startswith("B - WATCHLIST:"):
        reason = f"B - WATCHLIST: {reason.split(':', 1)[-1].strip()}"
    elif grade == "C - AVOID" and not reason.startswith("C - AVOID:"):
        reason = f"C - AVOID: {reason.split(':', 1)[-1].strip()}"
    return grade, reason



def calculate_entry_quality_score(
    *,
    latest: pd.Series,
    pivot: PivotInfo,
    risk_pct: float,
    ma10_distance: float,
    rsi: float,
    institutional_tightness_score: int,
    setup_type: str,
    breakout_alert: str,
    stage_label: str,
) -> Tuple[int, str]:
    """Score whether the entry is actionable now, separate from stock quality."""
    score = 0
    close = float(latest["Close"])
    distance = pivot.distance_pct
    if pd.notna(distance) and 0 <= distance <= 5:
        score += 2
    if close >= float(latest["MA10"]) or close >= float(latest["MA20"]):
        score += 2
    if pd.notna(risk_pct) and risk_pct <= 8:
        score += 2
    elif pd.notna(risk_pct) and risk_pct <= 10:
        score += 1
    if institutional_tightness_score >= 7:
        score += 2
    elif institutional_tightness_score >= 5:
        score += 1
    if breakout_alert in {"NEAR BREAKOUT", "CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"} or setup_type in {"PULLBACK TO MA10", "PULLBACK TO MA20", "HEALTHY PULLBACK WATCH"}:
        score += 1

    daily_range = max(float(latest.get("High", close)) - float(latest.get("Low", close)), 0.01)
    upper_wick_pct = (float(latest.get("High", close)) - max(float(latest.get("Open", close)), close)) / daily_range
    wide_loose = bool(latest.get("RangePct", np.nan) > 6)
    if pd.notna(ma10_distance):
        if ma10_distance > 18:
            score -= 2
        elif ma10_distance > 12:
            score -= 1
        elif ma10_distance > 8:
            score -= 0.5
    if pd.notna(risk_pct):
        if risk_pct > 20:
            score -= 4
        elif risk_pct > 15:
            score -= 3
        elif risk_pct > 12:
            score -= 2
        elif risk_pct > 10:
            score -= 1
    if pd.notna(distance) and (distance < -8 or distance > 10):
        score -= 1
    if pd.notna(rsi) and rsi > 85 and pd.notna(ma10_distance) and ma10_distance > 10 and upper_wick_pct >= 0.35:
        score -= 2
    if wide_loose:
        score -= 1
    if stage_label in {"LATE STAGE 2", "STAGE 3 RISK"}:
        score -= 1

    score = int(min(max(score, 0), 10))
    if score >= 8:
        label = "CLEAN ENTRY"
    elif score >= 5:
        label = "WAIT BETTER ENTRY"
    elif score >= 3:
        label = "WATCH ONLY ENTRY"
    else:
        label = "POOR ENTRY"
    return score, label


def risk_reward_efficiency_score(risk_pct: float, ideal_r: float, tp_type: str) -> int:
    """Score whether the reward plan is practical for the current stop distance."""
    score = 0
    if pd.notna(risk_pct):
        if risk_pct <= 8:
            score += 4
        elif risk_pct <= 10:
            score += 3
        elif risk_pct <= 12:
            score += 2
        elif risk_pct <= 15:
            score += 1
    if pd.notna(ideal_r):
        if ideal_r >= 2.5:
            score += 3
        elif ideal_r >= 2:
            score += 2
        elif ideal_r >= 1.5:
            score += 1
    if tp_type == "PRACTICAL SWING TP":
        score += 3
    elif tp_type == "RUNNER TP":
        score += 2
    return int(min(max(score, 0), 10))


def calculate_professional_score(
    *,
    institutional_quality_score: int,
    leader_label: str,
    sector_leadership_status: str,
    rs_score: float,
    market_score: int,
    entry_quality_score: int,
    institutional_tightness_score: int,
    healthy_pullback_score: int,
    tightness_score: int,
    vcp_status: str,
    risk_pct: float,
    ideal_r: float,
    tp_type: str,
    signal_state: str,
    hard_reject: bool,
    price_above_ma20: bool = False,
) -> float:
    """Weighted professional score that avoids high quality alone inflating to 100."""
    institutional_component = institutional_quality_score
    if leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}:
        institutional_component += 1
    if sector_leadership_status == "LEADING SECTOR":
        institutional_component += 1
    if score_at_least(rs_score, 8):
        institutional_component += 1
    if market_score >= 3:
        institutional_component += 1
    institutional_component = min(institutional_component, 10)

    setup_component = max(
        institutional_tightness_score,
        healthy_pullback_score,
        min(10, tightness_score * 2),
        8 if vcp_status in {"VALID VCP", "EARLY VCP"} else 0,
    )
    rr_component = risk_reward_efficiency_score(risk_pct, ideal_r, tp_type)
    score = (
        institutional_component * 10 * 0.40
        + entry_quality_score * 10 * 0.25
        + setup_component * 10 * 0.20
        + rr_component * 10 * 0.15
    )

    if entry_quality_score < 6:
        score = min(score, 86)
    if pd.notna(risk_pct) and risk_pct > 12:
        score = min(score, 88)
    if pd.notna(risk_pct) and risk_pct > 15:
        score = min(score, 82)
    if signal_state == "EXTENDED DO NOT CHASE":
        score = min(score, 85)
    if hard_reject:
        score = min(score, 59)
    if leader_label == "LAGGARD / AVOID":
        score = min(score, 75)
    if (
        not hard_reject
        and institutional_quality_score >= 8
        and score_at_least(rs_score, 8)
        and price_above_ma20
    ):
        score = max(score, 68)
    return round(min(max(score, 0), 100), 1)


def determine_trade_tier(
    *,
    professional_score: float,
    adjusted_score: float,
    entry_quality_score: int,
    risk_pct: float,
    rs_score: float,
    signal_state: str,
    leader_label: str,
    sector_leadership_status: str,
    setup_type: str,
    hard_reject: bool,
    extended: bool,
    institutional_quality_score: int = 0,
    price_above_ma20: bool = False,
) -> Tuple[str, str]:
    """Convert score quality into a trading tier without over-rejecting leaders."""
    failed_setup = setup_type in {"FAILED", "FAILED BREAKOUT"} or signal_state == "REJECT"
    strong_leader = (
        leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER", "MOMENTUM LEADER"}
        or sector_leadership_status in {"LEADING SECTOR", "IMPROVING SECTOR"}
        or (institutional_quality_score >= 8 and score_at_least(rs_score, 8) and price_above_ma20)
    )
    if hard_reject:
        return "Tier 4 - Avoid / Reject", "TIER 4: avoid; hard reject condition triggered."
    if (
        professional_score >= 88
        and entry_quality_score >= 7
        and pd.notna(risk_pct)
        and risk_pct <= 10
        and score_at_least(rs_score, 7)
        and signal_state in {"BUY NOW", "BUY ON BREAKOUT"}
        and not extended
    ):
        return "Tier 1 - Immediate Action", "TIER 1: institutional leader with clean entry near pivot, risk controlled."
    if strong_leader and professional_score >= 72 and not failed_setup:
        if extended:
            return "Tier 2 - High Quality, Wait Better Entry", "TIER 2: strong institutional leader but too far from pivot/MA10; wait for reset."
        return "Tier 2 - High Quality, Wait Better Entry", "TIER 2: strong leader but entry timing not ideal; wait for MA10/MA20 pullback."
    if strong_leader and professional_score >= 68 and not hard_reject:
        return "Tier 2 - High Quality, Wait Better Entry", "TIER 2: strong leader but entry timing not ideal; wait for MA10/MA20 pullback."
    if professional_score >= 60 and not hard_reject:
        return "Tier 3 - Leadership Watchlist", "TIER 3: leadership watchlist; setup not ready."
    if not hard_reject and not failed_setup:
        return "Tier 3 - Leadership Watchlist", "TIER 3: leadership watchlist; setup not ready."
    return "Tier 4 - Avoid / Reject", "TIER 4: avoid; hard reject condition triggered."


def hard_reject_check(
    *,
    latest: pd.Series,
    trend_score: int,
    risk_pct: float,
    action: str,
    current_setup_status: str,
    breakout_alert: str,
    volume_confirmation: str,
    earnings_risk_label: str,
    setup_grade: str = "C",
) -> Tuple[bool, str]:
    """Only reject when there is a real structural or risk failure."""
    if pd.isna(risk_pct):
        return True, "REJECT: invalid risk calculation."
    if risk_pct > 25:
        return True, "REJECT: risk above 25%."
    if latest.get("Close", np.nan) < latest.get("MA50", np.nan):
        return True, "REJECT: price below MA50; structure broken."
    if action == "FAILED" or current_setup_status == "FAILED BREAKOUT":
        return True, "REJECT: failed breakout / broken structure."
    if trend_score < 3 and latest.get("Close", np.nan) < latest.get("MA150", np.nan):
        return True, "REJECT: trend template failed."
    if breakout_alert == "FAILED BREAKOUT" and volume_confirmation == "YES":
        return True, "REJECT: failed breakout on heavy volume."
    if earnings_risk_label == "HIGH RISK" and setup_grade not in {"A+", "A", "B"}:
        return True, "REJECT: earnings risk high for a new entry."
    avg_dollar_volume = latest.get("AvgDollarVol50", np.nan)
    if pd.notna(avg_dollar_volume) and avg_dollar_volume < 20_000_000:
        return True, "REJECT: liquidity too low."
    recent_structure_low = latest.get("RecentStructureLow", np.nan)
    if pd.notna(recent_structure_low) and latest.get("Close", np.nan) < recent_structure_low:
        return True, "REJECT: price below recent structure low."
    return False, ""


def institutional_decision_reason(
    *,
    signal_state: str,
    ticker: str,
    leader_label: str,
    setup_type: str,
    sector_group: str,
    breakout_alert: str,
    rs_score: float,
    risk_pct: float,
    volume_confirmation: str,
    institutional_quality_score: int,
    earnings_risk_label: str = "N/A",
) -> str:
    """Generate a specific final decision reason without generic false rejection wording."""
    if signal_state == "BUY NOW":
        if leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}:
            return f"BUY NOW: institutional {sector_group.lower()} leader, breakout confirmed, strong RS, risk controlled."
        if leader_label == "CYCLICAL BREAKOUT":
            return "BUY NOW: strong technical breakout, but cyclical sector; monitor RSI and volume."
        return "BUY NOW: strong setup, breakout confirmed, RS strong, risk controlled."
    if setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        prefix = "BUY ON BREAKOUT" if signal_state == "BUY ON BREAKOUT" else "WATCH"
        return f"{prefix}: high RS leader, not pure VCP but valid momentum setup."
    if signal_state == "BUY ON BREAKOUT":
        if pd.notna(risk_pct) and risk_pct > 10:
            return "BUY ON BREAKOUT: good setup but risk slightly above preferred 10%; wait for clean trigger."
        return "BUY ON BREAKOUT: near pivot, strong RS, wait for breakout volume."
    if signal_state == "WATCH":
        if earnings_risk_label == "HIGH RISK":
            return "WATCH: strong setup but earnings risk high; consider smaller size or wait after earnings."
        if pd.notna(risk_pct) and 10 < risk_pct <= 12:
            return "WATCH: good setup but risk slightly above preferred 10%."
        return "WATCH: good institutional/technical context, wait for clean trigger."
    if signal_state == "WAIT PULLBACK":
        if pd.notna(risk_pct) and risk_pct > 15:
            return "WAIT PULLBACK: strong leader but stop distance too wide."
        if pd.notna(risk_pct) and risk_pct > 12:
            return "WAIT PULLBACK: risk above ideal range, wait for tighter entry."
        return "WAIT PULLBACK: strong leader but stop distance too wide; wait for tighter MA10/MA20 entry."
    if signal_state == "EXTENDED DO NOT CHASE":
        return "EXTENDED: do not chase; wait for base or MA10 reset."
    return "REJECT: actual hard reject condition triggered."


def apply_institutional_decision_layer(
    *,
    signal_state: str,
    trade: str,
    watchlist_flag: str,
    quality_grade: str,
    decision_reason: str,
    setup_type: str,
    vcp_status: str,
    final_score: float,
    adjusted_score: float,
    institutional_quality_score: int,
    rs_score: float,
    risk_pct: float,
    breakout_quality_score: int,
    breakout_alert: str,
    volume_confirmation: str,
    hard_reject: bool,
    hard_reject_reason: str,
    momentum_breakout_candidate: bool,
    ma10_distance: float,
    rsi: float,
    leader_label: str,
) -> Tuple[str, str, str, str, str]:
    """Apply final hierarchy so generic reject cannot overwrite high-quality setups."""
    protected = (
        (score_at_least(rs_score, 8) and final_score >= 85 and pd.notna(risk_pct) and risk_pct <= 12)
        or vcp_status in {"VALID VCP", "EARLY VCP"}
        or setup_type in PROTECTED_SETUP_TYPES
        or momentum_breakout_candidate
    )
    institutional_leader = (
        leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}
        and score_at_least(rs_score, 8)
        and final_score >= 85
        and institutional_quality_score >= 7
        and adjusted_score >= 85
    )
    if hard_reject:
        return "REJECT", "NO", "NO", "Reject", hard_reject_reason

    risk_state, risk_reason = risk_bucket_state(
        risk_pct,
        strong_leader=institutional_leader,
        extended=bool(pd.notna(ma10_distance) and ma10_distance > 12),
    )
    if risk_state in {"WAIT PULLBACK", "EXTENDED DO NOT CHASE"}:
        signal_state = risk_state
        trade = "NO"
        watchlist_flag = "YES" if signal_state == "WAIT PULLBACK" else "NO"
        if quality_grade == "Reject" and (protected or institutional_leader):
            quality_grade = "B"
        decision_reason = risk_reason
    elif risk_state == "WATCH" and signal_state == "BUY NOW":
        signal_state = "BUY ON BREAKOUT" if breakout_alert in {"NEAR BREAKOUT", "CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"} else "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "BUY ON BREAKOUT: good setup but risk slightly above preferred 10%; wait for clean trigger." if signal_state == "BUY ON BREAKOUT" else risk_reason

    if signal_state == "REJECT" and protected:
        if pd.notna(risk_pct) and risk_pct > 12:
            signal_state = "WAIT PULLBACK"
        elif breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS", "NEAR BREAKOUT"}:
            signal_state = "BUY ON BREAKOUT"
        else:
            signal_state = "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        if quality_grade == "Reject":
            quality_grade = "A" if setup_type == "MOMENTUM BREAKOUT EXCEPTION" or vcp_status in {"VALID VCP", "EARLY VCP"} else "B"

    if signal_state == "BUY NOW":
        buy_now_ok = (
            pd.notna(risk_pct)
            and risk_pct <= 10
            and score_at_least(rs_score, 7)
            and final_score >= 85
            and adjusted_score >= 85
            and breakout_quality_score >= 6
        )
        if setup_type == "MOMENTUM BREAKOUT EXCEPTION" or momentum_breakout_candidate:
            buy_now_ok = (
                buy_now_ok
                and score_at_least(rs_score, 8)
                and final_score >= 90
                and institutional_quality_score >= 6
                and breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}
                and pd.notna(ma10_distance)
                and ma10_distance <= 12
            )
        if not buy_now_ok:
            signal_state = "BUY ON BREAKOUT" if breakout_alert in {"NEAR BREAKOUT", "CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"} else "WATCH"
            trade = "NO"
            watchlist_flag = "YES"

    if signal_state == "BUY NOW":
        trade = "YES"
        watchlist_flag = "NO"
    elif signal_state in {"BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}:
        trade = "NO"
        watchlist_flag = "YES"
    elif signal_state == "EXTENDED DO NOT CHASE":
        trade = "NO"
        watchlist_flag = "NO"

    if pd.notna(rsi) and rsi > 85 and leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"} and volume_confirmation == "YES" and signal_state == "EXTENDED DO NOT CHASE":
        signal_state = "WAIT PULLBACK"
        trade = "NO"
        watchlist_flag = "YES"

    return signal_state, trade, watchlist_flag, quality_grade, decision_reason


def decision_engine_regression_checks() -> None:
    """Document the final hierarchy invariants for future tests."""
    assert not hard_reject_check(
        latest=pd.Series({"Close": 100, "MA50": 90, "MA150": 80, "AvgDollarVol50": 100_000_000}),
        trend_score=7,
        risk_pct=9,
        action="READY",
        current_setup_status="ACTIVE BREAKOUT",
        breakout_alert="CONFIRMED BREAKOUT",
        volume_confirmation="YES",
        earnings_risk_label="LOW RISK",
    )[0]
    adjusted = adjusted_final_score(90, 8, 3, 3)
    assert adjusted >= 85
    dell_tp, _, _ = validate_ideal_tp(
        ideal_tp=220,
        ideal_tp_reason="invalid old resistance",
        ideal_r=0.25,
        entry=217.4,
        stop=207.4,
        target_2r=237.4,
        target_3r=247.4,
        nearest_resistance=220,
        current_close=238.8,
        signal_state="WATCH",
    )
    assert dell_tp > 238.8 and dell_tp > 217.4
    assert reason_with_signal_prefix("BUY NOW", "WATCH: old mismatch").startswith("BUY NOW:")
    test_rows = pd.DataFrame(
        [
            {
                "ticker": "STLD",
                "Signal State": "BUY NOW",
                "Trade": "YES",
                "WATCHLIST FLAG": "NO",
                "Decision Reason": "BUY NOW: strong setup.",
                "Earnings Risk": "HIGH RISK",
                "Days to Earnings": 2,
                "Final Score": 100,
                "Adjusted Final Score": 100,
                "Institutional Quality Score": 8,
                "RS Score Raw": 10,
                "Risk %": 7.47,
                "Setup Type": "TRUE VCP",
                "VCP Status": "VALID VCP",
                "Hard Reject": "NO",
                "Entry Trigger": 100,
                "Stop Loss": 93,
                "Target 2R": 114,
                "Target 3R": 121,
                "Nearest Resistance": 121,
                "Current Price": 101,
                "Ideal TP": 121,
                "Ideal TP Reason": "ok",
                "Ideal TP R": 3,
            },
            {
                "ticker": "LEADER",
                "Signal State": "REJECT",
                "Trade": "NO",
                "WATCHLIST FLAG": "NO",
                "Decision Reason": "REJECT: generic not VCP.",
                "Earnings Risk": "LOW RISK",
                "Days to Earnings": 30,
                "Final Score": 90,
                "Adjusted Final Score": 90,
                "Institutional Quality Score": 8,
                "RS Score Raw": 8,
                "Risk %": 11,
                "Setup Type": "BASE BUILDING",
                "VCP Status": "NOT VCP",
                "Hard Reject": "NO",
                "Entry Trigger": 100,
                "Stop Loss": 90,
                "Target 2R": 120,
                "Target 3R": 130,
                "Nearest Resistance": 130,
                "Current Price": 101,
                "Ideal TP": 130,
                "Ideal TP Reason": "ok",
                "Ideal TP R": 3,
            },
        ]
    )
    fixed = validate_scan_results(test_rows)
    assert fixed.loc[0, "Signal State"] == "WATCH"
    assert fixed.loc[0, "Watch Type"] if "Watch Type" in fixed.columns else True
    assert fixed.loc[1, "Signal State"] != "REJECT"
    ranking = pd.DataFrame(
        {
            "Signal State": ["REJECT", "EXTENDED DO NOT CHASE", "WATCH", "BUY NOW"],
            "Adjusted Final Score": [100, 99, 80, 70],
            "Institutional Quality Score": [10, 9, 2, 1],
            "RS Sort": [10, 9, 2, 1],
            "Breakout Quality Score": [10, 9, 2, 1],
            "Risk %": [1, 1, 1, 1],
        }
    )
    ranked_states = ranking.assign(
        signal_sort=ranking["Signal State"].map(SIGNAL_STATE_PRIORITY).fillna(9)
    ).sort_values(
        ["signal_sort", "Adjusted Final Score", "Institutional Quality Score", "RS Sort", "Breakout Quality Score", "Risk %"],
        ascending=[True, False, False, False, False, True],
    )["Signal State"].tolist()
    assert ranked_states[0] == "BUY NOW" and ranked_states[-1] == "REJECT"
    tp1, tp2, tp3, ideal, tp_type, tp_reason, _ = calculate_trader_tp_plan(
        entry=240,
        stop=228,
        current_close=242,
        nearest_resistance=268,
        recent_high=270,
        institutional_quality_score=9,
        rs_score=9,
        sector_score=8,
        market_environment="UPTREND UNDER PRESSURE",
        extended=False,
    )
    assert 240 < tp1 < tp2 < tp3
    assert ideal == tp2 and tp_type == "PRACTICAL SWING TP" and "TP2 selected" in tp_reason
    dates = pd.date_range("2026-01-01", periods=25)
    pullback_data = pd.DataFrame(
        {
            "Open": [100 + i * 0.8 for i in range(25)],
            "High": [102 + i * 0.8 for i in range(25)],
            "Low": [99 + i * 0.8 for i in range(25)],
            "Close": [101 + i * 0.8 for i in range(25)],
            "Volume": [2_000_000] * 20 + [900_000, 850_000, 800_000, 780_000, 760_000],
            "MA10": [98 + i * 0.75 for i in range(25)],
            "MA20": [96 + i * 0.7 for i in range(25)],
            "AvgVol20": [1_500_000] * 25,
            "RSI14": [62] * 25,
            "RangePct": [2] * 25,
        },
        index=dates,
    )
    hp_score, hp_label, lighter = calculate_healthy_pullback_score(pullback_data, PivotInfo(118, 1, 119, "Near pivot", 3))
    tight_score, tight_label = calculate_institutional_tightness_score(pullback_data, PivotInfo(118, 1, 119, "Near pivot", 3))
    assert hp_score >= 7 and hp_label in {"HEALTHY PULLBACK", "NORMAL DIGESTION"} and lighter
    assert tight_score >= 6 and tight_label in {"TIGHT LEADER", "TIGHT BASE"}
    semi_status, semi_weight = sector_leadership_status_and_weight(
        sector_info={"sector_group": "Semiconductors", "theme_group": "AI / Semis", "sector": "Technology", "industry": "Semiconductors"},
        sector_leadership="Leader",
        sector_score=3,
        rs_score=9,
    )
    steel_status, steel_weight = sector_leadership_status_and_weight(
        sector_info={"sector_group": "Materials", "theme_group": "Materials", "sector": "Steel", "industry": "Steel"},
        sector_leadership="Average",
        sector_score=1,
        rs_score=9,
    )
    assert semi_status == "LEADING SECTOR" and semi_weight > steel_weight and steel_status == "CYCLICAL RISK"
    entry_score, entry_label = calculate_entry_quality_score(
        latest=pd.Series({"Close": 100, "MA10": 99, "MA20": 96, "RangePct": 2, "RSI14": 60}),
        pivot=PivotInfo(102, 2, 102.5, "Near pivot", 3),
        risk_pct=7.5,
        ma10_distance=1,
        rsi=60,
        institutional_tightness_score=8,
        setup_type="RESISTANCE BREAKOUT WATCH",
        breakout_alert="NEAR BREAKOUT",
        stage_label="MID STAGE 2",
    )
    assert entry_score >= 8 and entry_label == "CLEAN ENTRY"
    poor_entry_score, _ = calculate_entry_quality_score(
        latest=pd.Series({"Close": 130, "MA10": 100, "MA20": 94, "RangePct": 8, "RSI14": 88}),
        pivot=PivotInfo(100, -30, 100.5, "Extended", 1),
        risk_pct=16,
        ma10_distance=30,
        rsi=88,
        institutional_tightness_score=2,
        setup_type="EXTENDED",
        breakout_alert="NO BREAKOUT",
        stage_label="LATE STAGE 2",
    )
    inflated = calculate_professional_score(
        institutional_quality_score=10,
        leader_label="INSTITUTIONAL LEADER",
        sector_leadership_status="LEADING SECTOR",
        rs_score=10,
        market_score=4,
        entry_quality_score=poor_entry_score,
        institutional_tightness_score=8,
        healthy_pullback_score=8,
        tightness_score=5,
        vcp_status="VALID VCP",
        risk_pct=16,
        ideal_r=3,
        tp_type="PRACTICAL SWING TP",
        signal_state="EXTENDED DO NOT CHASE",
        hard_reject=False,
    )
    assert inflated <= 82
    tier, _ = determine_trade_tier(
        professional_score=80,
        adjusted_score=95,
        entry_quality_score=5,
        risk_pct=14,
        rs_score=9,
        signal_state="WAIT PULLBACK",
        leader_label="INSTITUTIONAL LEADER",
        sector_leadership_status="LEADING SECTOR",
        setup_type="HEALTHY PULLBACK WATCH",
        hard_reject=False,
        extended=False,
    )
    assert tier == "Tier 2 - High Quality, Wait Better Entry"


def reason_with_signal_prefix(signal_state: str, decision_reason: str) -> str:
    """Keep the final explanation aligned with the displayed signal state."""
    expected_prefix = DECISION_PREFIX_BY_STATE.get(signal_state, "REJECT:")
    text = str(decision_reason or "").strip()
    if text.startswith(expected_prefix):
        return text

    for prefix in DECISION_PREFIX_BY_STATE.values():
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break
    if text.startswith("-"):
        text = text[1:].strip()

    default_reason = {
        "BUY NOW": "breakout confirmed, strong RS, risk controlled.",
        "EARLY POSITION": "high-quality leader; pilot position allowed before full breakout confirmation.",
        "BUY ON BREAKOUT": "near trigger, wait for clean confirmation.",
        "WATCH": "good setup, wait for trigger.",
        "WAIT PULLBACK": "risk or extension requires a tighter entry.",
        "EXTENDED DO NOT CHASE": "wait for pullback, do not chase.",
        "REJECT": "hard reject or weak setup condition triggered.",
    }.get(signal_state, "hard reject or weak setup condition triggered.")
    return f"{expected_prefix} {text or default_reason}"


def finalize_signal_outputs(
    *,
    signal_state: str,
    trade: str,
    watchlist_flag: str,
    decision_reason: str,
    earnings_risk_label: str,
    days_to_earnings: int | str | None,
    trade_tier: str = "",
) -> Tuple[str, str, str, str]:
    """Enforce one final decision hierarchy before row creation."""
    days_numeric = numeric_or_na(days_to_earnings)
    if (
        signal_state == "BUY NOW"
        and earnings_risk_label == "HIGH RISK"
        and pd.notna(days_numeric)
        and days_numeric <= 3
    ):
        signal_state = "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "WATCH: strong setup but earnings risk high; consider smaller size or wait after earnings."

    if trade == "YES" and signal_state not in {"BUY NOW", "EARLY POSITION"} and trade_tier in {"", "Tier 1 - Immediate Action"}:
        signal_state = "BUY NOW"
    if signal_state == "BUY NOW":
        trade = "YES"
        watchlist_flag = "NO"
    elif signal_state == "EARLY POSITION":
        trade = "YES"
        watchlist_flag = "YES"
    elif signal_state in {"BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}:
        trade = "NO"
        watchlist_flag = "YES"
    elif signal_state in {"EXTENDED DO NOT CHASE", "REJECT"}:
        trade = "NO"
        watchlist_flag = "NO"

    return signal_state, trade, watchlist_flag, reason_with_signal_prefix(signal_state, decision_reason)


def action_readiness_label(
    *,
    trade_tier: str,
    signal_state: str,
    professional_score: float,
    entry_quality_score: float,
) -> str:
    """Summarize how close a row is to executable action without changing score or tier."""
    if trade_tier == "Tier 4 - Avoid / Reject":
        return "AVOID"
    if signal_state == "BUY NOW":
        return "READY NOW"
    if signal_state == "EARLY POSITION":
        return "NEAR TIER 1"
    if signal_state == "BUY ON BREAKOUT":
        return "WAIT TRIGGER"
    if signal_state == "WAIT PULLBACK":
        return "WAIT PULLBACK"
    if (
        trade_tier == "Tier 2 - High Quality, Wait Better Entry"
        and pd.notna(professional_score)
        and professional_score >= 80
        and pd.notna(entry_quality_score)
        and entry_quality_score >= 5
    ):
        return "NEAR TIER 1"
    return "WAIT TRIGGER" if signal_state == "WATCH" else "AVOID"


def buy_setup_explainability(
    *,
    adjusted_score: float,
    professional_score: float,
    rs_score: float,
    risk_pct: float,
    leader_label: str,
    stage_label: str,
    character_change_flag: str,
    earnings_risk_label: str,
    days_to_earnings: int | str | None,
    setup_type: str,
    ma10_distance: float,
    ma20_distance: float,
    hard_reject: bool,
    final_score: float,
    breakout_alert: str,
    volume_confirmation: str,
    setup_quality_grade: str,
    pullback_quality: str,
) -> Dict[str, object]:
    """Explain why a row can or cannot be acted on without adding new data calls."""
    leader_ok = leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER", "MOMENTUM LEADER"}
    bad_stage = stage_label in {"CLIMAX / PARABOLIC", "FAILED STAGE", "STAGE 1 / NOT READY"}
    days_numeric = numeric_or_na(days_to_earnings)
    earnings_block = earnings_risk_label == "HIGH RISK" and pd.notna(days_numeric) and days_numeric <= 7
    rs_value = numeric_or_na(rs_score)
    risk_value = numeric_or_na(risk_pct)
    adjusted_value = numeric_or_na(adjusted_score)
    professional_value = numeric_or_na(professional_score)
    final_value = numeric_or_na(final_score)
    ma10_value = numeric_or_na(ma10_distance)
    ma20_value = numeric_or_na(ma20_distance)
    strict_blockers: List[str] = []
    if hard_reject:
        strict_blockers.append("Hard reject")
    if character_change_flag == "CHARACTER CHANGE":
        strict_blockers.append("Character Change")
    if stage_label in {"FAILED STAGE", "CLIMAX / PARABOLIC"}:
        strict_blockers.append(stage_label)
    if pd.notna(risk_value) and risk_value > 18:
        strict_blockers.append("Risk > 18%")
    if pd.notna(rs_value) and rs_value < 4:
        strict_blockers.append("Weak RS")
    if pd.notna(final_value) and final_value < 60:
        strict_blockers.append("Final Score < 60")
    if earnings_block:
        strict_blockers.append("Earnings Risk")

    setup_quality_ok = setup_quality_grade not in {"C", "Reject"}
    pullback_quality_ok = pullback_quality != "HIGH RISK PULLBACK"
    criteria = [
        ("Adjusted Final Score >= 90", "Adjusted Final Score below 90", pd.notna(adjusted_value) and adjusted_value >= 90),
        ("Professional Score >= 85", "Professional Score below 85", pd.notna(professional_value) and professional_value >= 85),
        ("RS >= 8", "RS below 8", pd.notna(rs_value) and rs_value >= 8),
        ("Risk <= 12%", "Risk above 12%", pd.notna(risk_value) and risk_value <= 12),
        ("Institutional/Sector/Momentum Leader", "Leader quality not eligible", leader_ok),
        ("Stage 2 / not failed", "Stage is failed, climactic, or not ready", not bad_stage),
        ("No character change", "Character change detected", character_change_flag != "CHARACTER CHANGE"),
        ("No near earnings risk", "High earnings risk within 7 trading days", not earnings_block),
        ("Setup Quality Grade above C", "Setup Quality Grade is C or Reject", setup_quality_ok),
        ("Pullback quality acceptable", "Pullback Quality is HIGH RISK PULLBACK", pullback_quality_ok),
    ]
    passed = [pass_label for pass_label, _, ok in criteria if ok]
    failed = [fail_label for _, fail_label, ok in criteria if not ok]
    actionable_buy_zone = not strict_blockers and not failed

    early_setup_ok = setup_type in {
        "EARLY VCP",
        "VALID VCP",
        "TRUE VCP",
        "BASE BUILDING",
        "PULLBACK TO MA10",
        "HEALTHY PULLBACK WATCH",
        "RESISTANCE BREAKOUT WATCH",
        "POST-BREAKOUT DIGESTION",
    }
    early_extended_ok = (
        (pd.isna(ma10_value) or ma10_value <= 12)
        and (pd.isna(ma20_value) or ma20_value <= 18)
    )
    early_criteria = [
        ("Adjusted Final Score below 85", pd.notna(adjusted_value) and adjusted_value >= 85),
        ("Professional Score below 80", pd.notna(professional_value) and professional_value >= 80),
        ("RS below 7", pd.notna(rs_value) and rs_value >= 7),
        ("Risk above 13%", pd.notna(risk_value) and risk_value <= 13),
        ("Leader quality not eligible", leader_ok),
        ("Setup does not support pilot entry", early_setup_ok),
        ("Too extended for pilot entry", early_extended_ok),
        ("Hard reject, character change, or earnings risk", not hard_reject and character_change_flag != "CHARACTER CHANGE" and not earnings_block),
    ]
    early_failed = [label for label, ok in early_criteria if not ok]
    early_position_zone = not strict_blockers and not early_failed
    breakout_confirmed = breakout_alert in {"CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}
    volume_confirmed = volume_confirmation == "YES"
    volume_only_block = (not actionable_buy_zone) and len(failed) == 0 and not volume_confirmed

    missing_condition = "None"
    if len(failed) == 1:
        missing_condition = failed[0]
    elif volume_only_block:
        missing_condition = "Volume confirmation missing"
    elif len(early_failed) == 1:
        missing_condition = early_failed[0]

    suggested_action = "None"
    if missing_condition == "Volume confirmation missing":
        suggested_action = "pilot buy or wait for breakout volume"
    elif "Risk" in missing_condition:
        suggested_action = "wait pullback to lower risk"
    elif "extended" in missing_condition.lower() or "Not too extended" == missing_condition:
        suggested_action = "wait MA10/MA20 reset"
    elif missing_condition != "None":
        suggested_action = "watch for the missing condition to improve"

    return {
        "actionable_buy_zone": actionable_buy_zone,
        "early_position_zone": early_position_zone,
        "passed": passed,
        "failed": failed,
        "blocked_by": strict_blockers or ["None"],
        "downgrade_reason": "None",
        "upgrade_reason": "Actionable Buy Zone" if actionable_buy_zone else "Early Position" if early_position_zone else "None",
        "missing_condition": missing_condition,
        "suggested_action": suggested_action,
        "breakout_confirmed": breakout_confirmed,
        "volume_confirmed": volume_confirmed,
    }


def execution_confidence_for_signal(signal_state: str, breakout_alert: str, volume_confirmation: str) -> str:
    """Separate execution confidence from the final signal state."""
    if signal_state == "BUY NOW" and volume_confirmation == "YES" and breakout_alert == "CONFIRMED BREAKOUT":
        return "HIGH"
    if signal_state in {"BUY NOW", "EARLY POSITION"}:
        return "MEDIUM"
    return "LOW"


def scanner_verdict_for_signal(signal_state: str, decision_reason: str) -> str:
    """Provide a user-facing verdict with the same prefix as the signal state."""
    return reason_with_signal_prefix(signal_state, decision_reason)


def validate_scan_results(frame: pd.DataFrame) -> pd.DataFrame:
    """Repair final consistency before display and export without changing the UI flow."""
    if frame.empty:
        return frame
    fixed = frame.copy()
    for idx, row in fixed.iterrows():
        signal_state = str(row.get("Signal State", "REJECT"))
        trade = str(row.get("Trade", "NO"))
        watchlist_flag = str(row.get("WATCHLIST FLAG", "NO"))
        decision_reason = str(row.get("Decision Reason", ""))
        hard_reject = str(row.get("Hard Reject", "NO")) == "YES"
        risk_pct = numeric_or_na(row.get("Risk %"))
        rs_score = numeric_or_na(row.get("RS Score Raw", row.get("RS Score")))
        final_score = numeric_or_na(row.get("Final Score"))
        setup_type = str(row.get("Setup Type", ""))
        leader_label_value = str(row.get("Leader Quality Label", ""))
        institutional_quality = numeric_or_na(row.get("Institutional Quality Score"))
        entry_quality = numeric_or_na(row.get("Entry Quality Score"))
        professional_score = numeric_or_na(row.get("Professional Score", row.get("Adjusted Final Score")))
        trade_tier = str(row.get("Trade Tier", ""))
        entry_timing_value = str(row.get("Entry Timing Label", ""))
        stage_label_value = str(row.get("Stage Label", ""))
        character_change_value = str(row.get("Character Change Flag", "NONE"))
        tradeability_score = numeric_or_na(row.get("Tradeability Score"))
        price_above_ma20 = numeric_or_na(row.get("close")) >= numeric_or_na(row.get("MA20", row.get("close"))) if pd.notna(numeric_or_na(row.get("close"))) else False

        if pd.notna(final_score):
            capped_final_score = min(float(final_score), timing_score_cap(entry_timing_value))
            if character_change_value == "CHARACTER CHANGE" or stage_label_value == "FAILED STAGE":
                capped_final_score = min(capped_final_score, 45)
            fixed.at[idx, "Final Score"] = round(float(capped_final_score), 1)
            final_score = capped_final_score

        if character_change_value == "CHARACTER CHANGE" or stage_label_value == "FAILED STAGE":
            hard_reject = True
            signal_state = "REJECT"
            trade = "NO"
            watchlist_flag = "NO"
            trade_tier = "Tier 4 - Avoid / Reject"
            professional_score = min(professional_score, 45) if pd.notna(professional_score) else 45
            decision_reason = "Character change detected: wait for structure to rebuild."

        if pd.notna(tradeability_score) and tradeability_score < 5 and signal_state == "BUY NOW":
            signal_state = "WAIT PULLBACK" if leader_label_value in {"INSTITUTIONAL LEADER", "MOMENTUM LEADER", "SECTOR LEADER"} else "WATCH"
            trade = "NO"
            watchlist_flag = "YES"
            decision_reason = "Tradeability is not clean enough for BUY NOW; wait for tighter risk/reward."
        if signal_state == "BUY NOW" and (
            str(row.get("Setup Quality Grade", "")) in {"C", "Reject"}
            or str(row.get("Pullback Quality", "")) == "HIGH RISK PULLBACK"
        ):
            signal_state = "EARLY POSITION" if leader_label_value in {"INSTITUTIONAL LEADER", "MOMENTUM LEADER", "SECTOR LEADER"} else "BUY ON BREAKOUT"
            trade = "YES" if signal_state == "EARLY POSITION" else "NO"
            watchlist_flag = "YES"
            decision_reason = "Quality guard blocks full BUY NOW; pilot position only or wait for breakout confirmation."

        protected = (
            (pd.notna(rs_score) and pd.notna(final_score) and rs_score >= 8 and final_score >= 85 and pd.notna(risk_pct) and risk_pct <= 12)
            or (pd.notna(institutional_quality) and institutional_quality >= 8 and pd.notna(rs_score) and rs_score >= 8 and price_above_ma20)
            or setup_type in PROTECTED_SETUP_TYPES
            or str(row.get("VCP Status", "")) in {"VALID VCP", "EARLY VCP"}
        )
        adjusted_score_value = numeric_or_na(row.get("Adjusted Final Score"))
        protected_high_quality_leader = (
            leader_label_value in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}
            and pd.notna(rs_score)
            and rs_score >= 8
            and pd.notna(adjusted_score_value)
            and adjusted_score_value >= 80
            and not hard_reject
        )
        if signal_state == "REJECT" and protected_high_quality_leader:
            if entry_timing_value in {"EXTENDED - WAIT", "TOO LATE"} or stage_label_value in {"LATE STAGE 2", "CLIMAX / PARABOLIC"}:
                signal_state = "WAIT PULLBACK"
                decision_reason = "WAIT PULLBACK: high-quality leader, but entry is extended; wait for MA10/MA20 reset or tight base."
            else:
                signal_state = "WATCH"
                decision_reason = "WATCH: good high-quality leader, but no clean trigger yet."
        if signal_state == "REJECT" and protected and not hard_reject:
            if pd.notna(risk_pct) and risk_pct > 12:
                signal_state = "WAIT PULLBACK"
                decision_reason = "WAIT PULLBACK: risk above ideal range, wait for tighter entry."
            else:
                signal_state = "WATCH"
                decision_reason = "WATCH: good institutional/technical context, wait for clean trigger."

        if pd.isna(entry_quality):
            entry_quality = 5
        if pd.isna(professional_score):
            professional_score = numeric_or_na(row.get("Adjusted Final Score"))
        if pd.isna(professional_score):
            professional_score = 0
        strong_leader_floor = (
            pd.notna(institutional_quality)
            and institutional_quality >= 8
            and pd.notna(rs_score)
            and rs_score >= 8
            and price_above_ma20
            and not hard_reject
        )
        if entry_quality < 6:
            professional_score = min(professional_score, 86)
        if pd.notna(risk_pct) and risk_pct > 15:
            professional_score = min(professional_score, 82)
        elif pd.notna(risk_pct) and risk_pct > 12:
            professional_score = min(professional_score, 88)
        if hard_reject:
            professional_score = min(professional_score, 59)
            trade_tier = "Tier 4 - Avoid / Reject"
        if strong_leader_floor:
            professional_score = max(professional_score, 68)
        if not hard_reject and trade_tier not in TRADE_TIER_PRIORITY:
            if professional_score >= 88 and entry_quality >= 7 and pd.notna(risk_pct) and risk_pct <= 10 and signal_state in {"BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT"}:
                trade_tier = "Tier 1 - Immediate Action"
            elif professional_score >= 72:
                trade_tier = "Tier 2 - High Quality, Wait Better Entry"
            elif professional_score >= 60:
                trade_tier = "Tier 3 - Leadership Watchlist"
            elif strong_leader_floor:
                trade_tier = "Tier 3 - Leadership Watchlist"
            else:
                trade_tier = "Tier 4 - Avoid / Reject"
        if not hard_reject and signal_state in {"BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"} and trade_tier == "Tier 4 - Avoid / Reject":
            trade_tier = "Tier 2 - High Quality, Wait Better Entry" if strong_leader_floor or professional_score >= 68 else "Tier 3 - Leadership Watchlist"
        if (
            leader_label_value == "LAGGARD / AVOID"
            and trade_tier == "Tier 2 - High Quality, Wait Better Entry"
            and not (pd.notna(rs_score) and rs_score >= 7 and pd.notna(entry_quality) and entry_quality >= 8)
        ):
            trade_tier = "Tier 3 - Leadership Watchlist"
        if trade_tier == "Tier 2 - High Quality, Wait Better Entry" and signal_state == "BUY ON BREAKOUT" and entry_quality < 7:
            signal_state = "WATCH"
            decision_reason = "WATCH: near trigger but entry quality is not clean enough for breakout action yet."

        if trade_tier == "Tier 1 - Immediate Action":
            if signal_state == "BUY NOW":
                trade = "YES"
            elif signal_state == "EARLY POSITION":
                trade = "YES"
                watchlist_flag = "YES"
            elif signal_state not in {"BUY ON BREAKOUT", "BUY NOW"}:
                signal_state = "BUY ON BREAKOUT"
            decision_reason = "TIER 1: institutional leader with clean entry near pivot, risk controlled."
        elif trade_tier == "Tier 2 - High Quality, Wait Better Entry":
            if signal_state in {"BUY NOW", "EARLY POSITION"}:
                trade = "YES"
                watchlist_flag = "YES" if signal_state == "EARLY POSITION" else "NO"
            else:
                trade = "NO"
                watchlist_flag = "YES"
                decision_reason = "TIER 2: strong leader but entry timing not ideal; wait for MA10/MA20 pullback."
        elif trade_tier == "Tier 3 - Leadership Watchlist":
            trade = "NO"
            watchlist_flag = "YES"
            if signal_state in {"BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT"}:
                signal_state = "WATCH"
            elif signal_state == "REJECT" and not hard_reject:
                signal_state = "WATCH"
            decision_reason = "TIER 3: leadership watchlist; setup not ready."
        elif trade_tier == "Tier 4 - Avoid / Reject" and hard_reject:
            signal_state = "REJECT"
            trade = "NO"
            watchlist_flag = "NO"
            decision_reason = "TIER 4: avoid; hard reject condition triggered."
        elif trade_tier == "Tier 4 - Avoid / Reject" and not hard_reject:
            trade_tier = "Tier 3 - Leadership Watchlist"
            signal_state = "WATCH" if signal_state == "REJECT" else signal_state
            trade = "NO"
            watchlist_flag = "YES"
            decision_reason = "TIER 3: leadership watchlist; setup not ready."

        signal_state, trade, watchlist_flag, decision_reason = finalize_signal_outputs(
            signal_state=signal_state,
            trade=trade,
            watchlist_flag=watchlist_flag,
            decision_reason=decision_reason,
            earnings_risk_label=str(row.get("Earnings Risk", "N/A")),
            days_to_earnings=row.get("Days to Earnings"),
            trade_tier=trade_tier,
        )
        executable_score = numeric_or_na(row.get("Executable Score"))
        if pd.isna(executable_score):
            executable_score = 0
        executable_grade, decision_reason = calibrate_executable_grade(
            executable_grade=str(row.get("Executable Grade", "C - AVOID")),
            executable_score=executable_score,
            executable_reason=str(row.get("Decision Reason", decision_reason)),
            signal_state=signal_state,
            trade=trade,
            watchlist_flag=watchlist_flag,
            risk_pct=risk_pct,
            entry_timing=entry_timing_value,
            leader_label=leader_label_value,
            character_change_flag=character_change_value,
            hard_reject=hard_reject,
            setup_type=setup_type,
            breakout_alert=str(row.get("Breakout Alert", "")),
            rs_score=rs_score,
            sector_leadership_status=str(row.get("Sector Leadership Status", "")),
        )
        if character_change_value == "CHARACTER CHANGE":
            executable_grade = "C - AVOID"
            executable_score = min(float(executable_score), 45)
            decision_reason = "C - AVOID: Character change detected: wait for structure to rebuild."
        reason_detail = strip_executable_prefix(decision_reason)
        if executable_grade == "C - AVOID" and signal_state != "REJECT":
            executable_grade = "B - WATCHLIST"
            if signal_state == "WATCH":
                reason_detail = "good setup or leader context, but no clean trigger yet."
            elif signal_state == "WAIT PULLBACK":
                reason_detail = "quality may be present, but wait for pullback or tighter risk."
            else:
                reason_detail = "wait for confirmation before execution."
        if signal_state == "BUY ON BREAKOUT" and trade != "YES":
            reason_detail = "near breakout trigger; wait for confirmation before execution."
        decision_reason = reason_with_signal_prefix(signal_state, reason_detail)

        entry = numeric_or_na(row.get("Entry Trigger"))
        stop = numeric_or_na(row.get("Stop Loss"))
        tp1 = numeric_or_na(row.get("TP1", row.get("Target 1R")))
        tp2 = numeric_or_na(row.get("TP2", row.get("Target 2R")))
        tp3 = numeric_or_na(row.get("TP3", row.get("Target 3R")))
        target_2r = numeric_or_na(row.get("Target 2R", tp2))
        target_3r = numeric_or_na(row.get("Target 3R", tp3))
        ideal_tp = numeric_or_na(row.get("Ideal TP"))
        ideal_r = numeric_or_na(row.get("Ideal TP R"))
        nearest_resistance = numeric_or_na(row.get("Nearest Resistance"))
        current_close = numeric_or_na(row.get("Current Price", row.get("close")))
        if all(pd.notna(value) for value in [entry, stop, target_2r, target_3r, current_close]):
            if pd.isna(tp1) or pd.isna(tp2) or pd.isna(tp3):
                tp1, tp2, tp3 = target_2r, target_2r, target_3r
            tp1, tp2, tp3 = enforce_tp_ladder(entry, stop, tp1, tp2, tp3)
            if pd.isna(nearest_resistance):
                nearest_resistance = tp2
            fixed_tp, fixed_reason, fixed_r = validate_ideal_tp(
                ideal_tp=ideal_tp,
                ideal_tp_reason=str(row.get("Ideal TP Reason", "")),
                ideal_r=ideal_r if pd.notna(ideal_r) else 0,
                entry=entry,
                stop=stop,
                target_2r=tp2,
                target_3r=tp3,
                nearest_resistance=nearest_resistance,
                current_close=current_close,
                signal_state=signal_state,
            )
            fixed.at[idx, "TP1"] = tp1
            fixed.at[idx, "TP2"] = tp2
            fixed.at[idx, "TP3"] = tp3
            fixed.at[idx, "Ideal TP"] = fixed_tp
            fixed.at[idx, "Ideal TP Reason"] = fixed_reason
            fixed.at[idx, "Ideal TP R"] = fixed_r
            current_tp_type = row.get("TP Type", "PRACTICAL SWING TP") or "PRACTICAL SWING TP"
            fixed.at[idx, "TP Type"] = (
                "RUNNER TP"
                if fixed_tp > entry * 1.35 and current_tp_type == "RUNNER TP"
                else "TOO FAR / USE TRAILING STOP"
                if fixed_tp > entry * 1.35
                else current_tp_type
            )

        fixed.at[idx, "Signal State"] = signal_state
        fixed.at[idx, "Trade"] = trade
        fixed.at[idx, "WATCHLIST FLAG"] = watchlist_flag
        if hard_reject:
            fixed.at[idx, "Hard Reject"] = "YES"
        fixed.at[idx, "Decision Reason"] = decision_reason
        fixed.at[idx, "Trade Reason"] = decision_reason
        fixed.at[idx, "Watchlist Reason"] = "Already Trade YES" if trade == "YES" else decision_reason
        fixed.at[idx, "Execution Confidence"] = execution_confidence_for_signal(
            signal_state,
            str(row.get("Breakout Alert", "")),
            str(row.get("Volume Confirmation", "")),
        )
        fixed.at[idx, "Scanner Verdict"] = scanner_verdict_for_signal(signal_state, decision_reason)
        for explain_col in ["Buy Criteria Passed", "Buy Criteria Failed", "Blocked By", "Downgrade Reason", "Upgrade Reason", "Missing Condition", "Suggested Action"]:
            if explain_col not in fixed.columns or not str(row.get(explain_col, "")).strip():
                fixed.at[idx, explain_col] = "None"
        fixed.at[idx, "Executable Grade"] = executable_grade
        fixed.at[idx, "Executable Score"] = round(float(executable_score), 1)
        fixed.at[idx, "Professional Score"] = round(float(professional_score), 1)
        fixed.at[idx, "Entry Quality Score"] = int(entry_quality)
        if "Quality Score" not in fixed.columns or pd.isna(numeric_or_na(row.get("Quality Score"))):
            quality_fallback = max(
                numeric_or_na(row.get("Institutional Quality Score", 0)) * 10 if pd.notna(numeric_or_na(row.get("Institutional Quality Score", 0))) else 0,
                numeric_or_na(row.get("Adjusted Final Score", 0)) if pd.notna(numeric_or_na(row.get("Adjusted Final Score", 0))) else 0,
            )
            fixed.at[idx, "Quality Score"] = round(float(min(max(quality_fallback, 0), 100)), 1)
        if "Execution Score" not in fixed.columns or pd.isna(numeric_or_na(row.get("Execution Score"))):
            execution_fallback = (
                int(entry_quality) * 6
                + (numeric_or_na(row.get("Tradeability Score", 0)) if pd.notna(numeric_or_na(row.get("Tradeability Score", 0))) else 0) * 4
            )
            fixed.at[idx, "Execution Score"] = round(float(min(max(execution_fallback, 0), 100)), 1)
        fixed.at[idx, "Trade Tier"] = trade_tier
        fixed.at[idx, "Action Readiness Label"] = action_readiness_label(
            trade_tier=trade_tier,
            signal_state=signal_state,
            professional_score=professional_score,
            entry_quality_score=entry_quality,
        )
        if row.get("Healthy Pullback Label") == "HEALTHY PULLBACK" and signal_state in {"WATCH", "WAIT PULLBACK"}:
            fixed.at[idx, "Watch Type"] = "HEALTHY PULLBACK"
        elif numeric_or_na(row.get("Institutional Tightness Score")) >= 7 and signal_state in {"WATCH", "BUY ON BREAKOUT"}:
            fixed.at[idx, "Watch Type"] = "TIGHT BASE"
        elif signal_state == "REJECT" and not str(row.get("Hard Reject Reason", "")):
            fixed.at[idx, "Hard Reject Reason"] = "REJECT: hard reject reason unavailable; rerun scan."
        fixed.at[idx, "signal sort"] = SIGNAL_STATE_PRIORITY.get(signal_state, 9)
        fixed.at[idx, "tier sort"] = TRADE_TIER_PRIORITY.get(trade_tier, 9)
    return fixed


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
    vcp_status: str,
    breakout_alert: str,
    rs_score: float,
    sector_leadership: str,
    sector_score: int,
    price_above_ma10: bool,
    holding_ma20: bool,
    ma10_rising: bool,
    higher_low_structure: bool,
    volume_contraction: bool,
    aggressive_mode: bool = False,
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
    if pd.isna(risk_pct):
        return "NO", "Risk invalid"
    if risk_pct > 10 and not aggressive_mode:
        return "NO", "Risk too high"
    if rr_score not in {"A+", "A"}:
        return "NO", "RR below A"
    if volume_confirmation != "YES":
        return "NO", "Volume confirmation missing"
    true_vcp_priority = (
        vcp_status in {"EARLY VCP", "VALID VCP"}
        or breakout_alert in {"NEAR BREAKOUT", "CONFIRMED BREAKOUT"}
        or (action == "PULLBACK ENTRY" and rs_score >= 6)
    )
    if not true_vcp_priority:
        return "NO", "Not VCP, near breakout, or strong-RS pullback"
    if vcp_status == "NOT VCP" and rs_score < 5:
        return "NO", "Not VCP and weak relative strength"
    if rs_score < 6 and not (breakout_alert == "CONFIRMED BREAKOUT" and volume_confirmation == "YES"):
        return "NO", "RS Score below 6"
    if not (sector_leadership == "Leader" or sector_score >= 3):
        return "NO", "Weak sector leadership"
    if action == "PULLBACK ENTRY":
        valid_pullback = (
            (price_above_ma10 or holding_ma20)
            and ma10_rising
            and higher_low_structure
            and (risk_pct <= 10 or aggressive_mode)
            and rs_score >= 6
            and volume_contraction
        )
        if not valid_pullback:
            return "NO", "Pullback lacks MA support, RS, higher lows, or volume contraction"
    if vcp_status == "NOT VCP" and rs_score < 5 and trend_score < 7:
        return "NO", "Not VCP, weak RS, and trend below 7"
    return "YES", "Final score >=75, good RR, risk below 10%"


def setup_quality_grade(
    action: str,
    trade: str,
    vcp_status: str,
    breakout_alert: str,
    rs_score: float,
    trend_score: int,
    risk_pct: float,
    extended: bool,
    sector_leadership: str,
    sector_score: int,
    tightness_score: int,
    volume_confirmation: str,
) -> Tuple[str, str]:
    """Grade whether a row is a true VCP/Minervini-style setup or a lower-quality lookalike."""
    near_pivot = breakout_alert in {"NEAR BREAKOUT", "CONFIRMED BREAKOUT", "BREAKOUT IN PROGRESS"}
    strong_sector = sector_leadership == "Leader" or sector_score >= 3
    strong_leader = rs_score >= 7 and trend_score >= 7 and strong_sector
    vcp_like = vcp_status in {"VALID VCP", "EARLY VCP"}

    if action in {"FAILED", "EXTENDED"} or extended or pd.isna(risk_pct) or risk_pct > 12:
        why = "rejected because extended" if extended or action == "EXTENDED" else "rejected because failed structure or poor risk"
        return "Reject", why
    if vcp_status == "NOT VCP" and rs_score < 5:
        return "C", "rejected because not VCP and RS weak"
    if vcp_status == "NOT VCP" and rs_score < 5 and trend_score < 7:
        return "C", "rejected because not VCP, RS weak, and trend below 7"
    if vcp_like and strong_leader and near_pivot and risk_pct <= 8:
        return "A+", "selected because true VCP near pivot"
    if (vcp_like or near_pivot) and rs_score >= 6 and risk_pct <= 10:
        if volume_confirmation != "YES":
            return "A", "watch only because structure good but no volume confirmation"
        return "A", "selected because valid VCP or early VCP with strong RS"
    if action == "PULLBACK ENTRY" and rs_score >= 6 and risk_pct <= 10 and tightness_score >= 3:
        return "B", "selected because pullback to MA10/MA20 with low risk"
    if rs_score < 5 or vcp_status == "NOT VCP":
        return "C", "rejected because not VCP and RS weak"
    return "B", "watch only because structure good but no volume confirmation"


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
    sector_info: dict,
    quote_info: dict,
    sync_info: dict,
    scan_timestamps: dict,
    market_score: int,
    sector_score: int,
    benchmark_data: Dict[str, pd.DataFrame],
    sector_etf: str,
    market_environment: str = "UPTREND UNDER PRESSURE",
    live_mode: bool = False,
    aggressive_mode: bool = False,
) -> dict:
    """Build the output row and stash chart-specific detail fields."""
    latest = data.iloc[-1]
    pivot = detect_pivot(data)
    vcp = detect_vcp(data, pivot)
    trend_score, trend_notes = score_trend(data)
    technical_score, technical_notes = score_technical(data, pivot)
    extended, ma10_distance, ma20_distance, extension_note = detect_extension(data)
    action = choose_action_label(data, trend_score, technical_score, pivot, vcp, extended)
    entry, stop, risk_pct, target_1r, target_2r, target_3r, invalidation = build_trade_plan(data, action, pivot)
    rr_ratio, rr_score = calculate_rr_score(entry, stop, target_2r)
    tightness_score, tightness_label = calculate_tightness(data, vcp)
    rs_primary, rs_fallback = select_rs_benchmarks(ticker, benchmark_data)
    rs_score = calculate_rs_score(data, rs_primary, rs_fallback)
    sector_leadership, sector_spread = calculate_sector_leadership(data, benchmark_data.get(sector_etf))
    earnings_label, earnings_risk = classify_earnings_risk(earnings_info)
    volume_confirmation, volume_note = calculate_volume_confirmation(data, action, pivot)
    breakout_alert = detect_breakout_alert(data, pivot, volume_confirmation)
    current_setup_status = classify_current_setup_status(data, pivot, extended, breakout_alert)
    earnings_setup_score, earnings_setup_label, earnings_strategy = calculate_earnings_setup(
        data, trend_score, rs_score, sector_score, earnings_info
    )
    post_earnings_label = detect_post_earnings_label(data, earnings_info)
    price_above_ma10 = bool(latest["Close"] > latest["MA10"])
    holding_ma20 = bool(latest["Close"] >= latest["MA20"] and latest["Low"] >= latest["MA20"] * 0.98)
    ma10_rising = is_rising(data["MA10"])
    higher_low_structure = has_higher_low_structure(data)
    explosive_score, explosive_label = calculate_explosive_score(data, pivot, higher_low_structure)
    final_score = calculate_final_score(
        trend_score=trend_score,
        technical_score=technical_score,
        rs_score=rs_score,
        sector_score=sector_score,
        market_score=market_score,
        tightness_score=tightness_score,
    )
    if live_mode:
        rvol, intraday_volume_ratio, rvol_label = calculate_intraday_volume_metrics(
            latest, quote_info, scan_timestamps.get("session_status", "MARKET CLOSED")
        )
    else:
        rvol, intraday_volume_ratio, rvol_label = np.nan, np.nan, "EOD only"
    stage_label = detect_stage_analysis(data)
    institutional_action = detect_institutional_action(data)
    healthy_pullback_score, healthy_pullback_label, lighter_pullback_volume = calculate_healthy_pullback_score(data, pivot)
    institutional_tightness_score, institutional_tightness_label = calculate_institutional_tightness_score(data, pivot)
    sector_leadership_status, sector_leadership_weight = sector_leadership_status_and_weight(
        sector_info=sector_info,
        sector_leadership=sector_leadership,
        sector_score=sector_score,
        rs_score=rs_score,
    )
    theme_weight = calculate_theme_weight(ticker, sector_info, sector_leadership, sector_score, rs_score)
    institutional_quality_score = calculate_institutional_quality_score(
        ticker=ticker,
        sector_info=sector_info,
        sector_leadership=sector_leadership,
        sector_score=sector_score,
        latest=latest,
        rs_score=rs_score,
        trend_score=trend_score,
        stage_label=stage_label,
        volume_confirmation=volume_confirmation,
        ma10_distance=ma10_distance,
        rsi=float(latest["RSI14"]),
        theme_weight=theme_weight,
    )
    if sector_leadership_status == "CYCLICAL RISK" and (float(latest["RSI14"]) > 85 or extended):
        institutional_quality_score = max(institutional_quality_score - 2, 0)
    leader_label = leader_quality_label(
        ticker=ticker,
        sector_info=sector_info,
        rs_score=rs_score,
        trend_score=trend_score,
        sector_leadership=sector_leadership,
        sector_score=sector_score,
        institutional_quality_score=institutional_quality_score,
    )
    adjusted_score = adjusted_final_score(
        final_score,
        institutional_quality_score,
        sector_score,
        market_score,
        sector_leadership_weight=sector_leadership_weight,
        institutional_tightness_score=institutional_tightness_score,
        theme_weight=theme_weight,
    )
    breakout_quality_score = calculate_breakout_quality_score(
        data=data,
        pivot=pivot,
        rvol=rvol,
        rs_score=rs_score,
        market_environment=market_environment,
        extended=extended,
        stage_label=stage_label,
        institutional_tightness_score=institutional_tightness_score,
        sector_leadership_status=sector_leadership_status,
        ma10_distance=ma10_distance,
    )
    earnings_intelligence = earnings_intelligence_label(earnings_label, post_earnings_label)
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
        vcp_status=vcp.status,
        breakout_alert=breakout_alert,
        rs_score=rs_score,
        sector_leadership=sector_leadership,
        sector_score=sector_score,
        price_above_ma10=price_above_ma10,
        holding_ma20=holding_ma20,
        ma10_rising=ma10_rising,
        higher_low_structure=higher_low_structure,
        volume_contraction=vcp.volume_contraction,
        aggressive_mode=aggressive_mode,
    )
    momentum_breakout_candidate = is_momentum_breakout_candidate(
        final_score=final_score,
        rs_score=rs_score,
        explosive_score=explosive_score,
        trend_score=trend_score,
        technical_score=technical_score,
        breakout_alert=breakout_alert,
        latest=latest,
        volume_dry_up=vcp.volume_contraction,
        volume_confirmation=volume_confirmation,
        risk_pct=risk_pct,
        ma10_distance=ma10_distance,
        earnings_risk_label=earnings_label,
        ma10_rising=ma10_rising,
        breakout_quality_score=breakout_quality_score,
        rvol=rvol,
        live_mode=live_mode,
    )
    if momentum_breakout_candidate:
        action = "MOMENTUM BREAKOUT"
        trade = "YES" if volume_confirmation == "YES" else "WATCH"
        trade_reason = "Momentum breakout with volume confirmation" if volume_confirmation == "YES" else "Momentum breakout needs volume confirmation"
    quality_grade, why_selected = setup_quality_grade(
        action=action,
        trade=trade,
        vcp_status=vcp.status,
        breakout_alert=breakout_alert,
        rs_score=rs_score,
        trend_score=trend_score,
        risk_pct=risk_pct,
        extended=extended,
        sector_leadership=sector_leadership,
        sector_score=sector_score,
        tightness_score=tightness_score,
        volume_confirmation=volume_confirmation,
    )
    if momentum_breakout_candidate:
        quality_grade = "A+" if volume_confirmation == "YES" else "A"
        why_selected = "Momentum breakout candidate despite not being pure VCP"
    if quality_grade == "Reject" and trade == "YES":
        trade = "NO"
        trade_reason = why_selected
    if (not momentum_breakout_candidate) and vcp.status == "NOT VCP" and rs_score < 5 and explosive_score < 6:
        trade = "NO"
        quality_grade = "Reject"
        trade_reason = "Low momentum + not VCP"
        why_selected = "Low momentum + not VCP"
    if (not momentum_breakout_candidate) and tightness_score < 3 and not vcp.volume_contraction:
        trade = "NO"
        quality_grade = "Reject"
        trade_reason = "No compression = no breakout energy"
        why_selected = "No compression = no breakout energy"
    if (not momentum_breakout_candidate) and quality_grade == "C" and vcp.status == "NOT VCP" and rs_score < 5:
        trade = "NO"
        trade_reason = "Not VCP and weak relative strength"
    latest_with_pivot = latest.copy()
    latest_with_pivot["Pivot"] = pivot.pivot
    if not live_mode:
        provisional_setup_type = classify_setup_type(
            vcp_status=vcp.status,
            action=action,
            current_setup_status=current_setup_status,
            resistance_breakout_mode="NO",
            momentum_breakout_candidate=momentum_breakout_candidate,
            latest=latest_with_pivot,
            healthy_pullback_label=healthy_pullback_label,
            institutional_tightness_score=institutional_tightness_score,
        )
        breakout_quality_score = calculate_eod_breakout_quality_score(
            data=data,
            pivot=pivot,
            rs_score=rs_score,
            tightness_score=tightness_score,
            volume_dry_up=vcp.volume_contraction,
            stage_label=stage_label,
            institutional_action=institutional_action,
            risk_pct=risk_pct,
            setup_grade=quality_grade,
            vcp_status=vcp.status,
            setup_type=provisional_setup_type,
            institutional_tightness_score=institutional_tightness_score,
            sector_leadership_status=sector_leadership_status,
        )
    live_breakout_status = (
        detect_live_breakout_status(
            latest=latest,
            pivot=pivot,
            rvol=rvol,
            intraday_volume_ratio=intraday_volume_ratio,
            rs_score=rs_score,
            setup_grade=quality_grade,
        )
        if live_mode
        else "EOD ONLY"
    )
    if live_mode and live_breakout_status == "LIVE BREAKOUT" and quality_grade in {"A+", "A"}:
        volume_confirmation = "YES"
        breakout_alert = "CONFIRMED BREAKOUT"
        current_setup_status = "ACTIVE BREAKOUT"
    nearest_resistance = detect_nearest_resistance(data, entry)
    resistance_blocks_1r = nearest_resistance > entry and nearest_resistance < target_1r
    resistance_distance_pct = (nearest_resistance - float(latest["Close"])) / float(latest["Close"]) * 100
    resistance_breakout_mode = (
        "RESISTANCE BREAKOUT WATCH"
        if (
            quality_grade in {"A+", "A"}
            and explosive_score >= 8
            and rs_score >= 6
            and resistance_blocks_1r
            and -1 <= resistance_distance_pct <= 5
        )
        else "NO"
    )
    rb_entry, rb_stop, rb_1r, rb_2r, rb_3r, rb_risk_pct = resistance_breakout_plan(data, nearest_resistance)
    ideal_tp, ideal_tp_reason, sell_strategy, trail_stop, tp_quality_score, ideal_r = calculate_ideal_tp_plan(
        entry=entry,
        stop=stop,
        target_1r=target_1r,
        target_2r=target_2r,
        target_3r=target_3r,
        nearest_resistance=nearest_resistance,
        current_close=float(latest["Close"]),
        ma10=float(latest["MA10"]),
        prior_day_low=float(data["Low"].iloc[-2]) if len(data) >= 2 else float(latest["Low"]),
        two_day_low=float(data["Low"].tail(2).min()),
        ma10_distance=ma10_distance,
        setup_grade=quality_grade,
        explosive_score=explosive_score,
        rs_score=rs_score,
        volume_confirmation=volume_confirmation,
        extended=extended,
        risk_pct=risk_pct,
        rsi=float(latest["RSI14"]),
        earnings_risk_label=earnings_label,
    )
    sector_context_score = min(10, sector_score * 2 + (2 if sector_leadership_status == "LEADING SECTOR" else 1 if sector_leadership_status == "IMPROVING SECTOR" else 0))
    avg_range20_for_tp = data["RangePct"].tail(20).mean() if len(data) >= 20 else np.nan
    volatility_controlled_for_tp = (
        pd.isna(avg_range20_for_tp)
        or pd.isna(latest.get("RangePct", np.nan))
        or float(latest.get("RangePct", 0)) <= float(avg_range20_for_tp) * 1.3
    )
    practical_tp1, practical_tp2, practical_tp3, ideal_tp, tp_type, practical_tp_reason, ideal_r = calculate_trader_tp_plan(
        entry=entry,
        stop=stop,
        current_close=float(latest["Close"]),
        nearest_resistance=nearest_resistance,
        recent_high=float(latest.get("High52W", np.nan)),
        institutional_quality_score=institutional_quality_score,
        rs_score=rs_score,
        sector_score=sector_context_score,
        sector_leadership_status=sector_leadership_status,
        market_environment=market_environment,
        extended=extended,
        volatility_controlled=volatility_controlled_for_tp,
    )
    ideal_tp_reason = practical_tp_reason
    risk_quality_note = risk_note(risk_pct, aggressive_mode)
    if trade == "YES" and risk_pct > 10 and not aggressive_mode:
        trade = "NO"
        trade_reason = "Risk too high"
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        trade = "NO"
        trade_reason = "Needs breakout above resistance"
        practical_tp1, practical_tp2, practical_tp3 = enforce_tp_ladder(rb_entry, rb_stop, rb_1r, rb_2r, rb_3r)
        ideal_tp = practical_tp2
        tp_type = "PRACTICAL SWING TP"
        ideal_tp_reason = f"Needs clean breakout above resistance before swing entry; {PRACTICAL_TP_NOTE}"
        sell_strategy = "WATCH / SCALP ONLY"
        trail_stop = rb_stop
        ideal_r = round((ideal_tp - rb_entry) / max(rb_entry - rb_stop, 0.01), 2)
        tp_quality_score = max(tp_quality_score, 6)
    if trade == "YES" and (not momentum_breakout_candidate) and ideal_r < 1.8:
        trade = "NO"
        trade_reason = "Reward too limited before resistance"
        why_selected = "rejected because reward is too limited before resistance"
    if trade == "YES" and (not momentum_breakout_candidate) and tp_quality_score < 5:
        trade = "NO"
        trade_reason = "TP quality too low"
        why_selected = "rejected because upside before resistance is too limited"
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
    if trade == "NO" and watchlist_flag == "YES":
        sell_strategy = "WAIT FOR ENTRY"
        if ideal_tp_reason.startswith("Watchlist only") is False:
            ideal_tp_reason = f"{ideal_tp_reason}; watchlist only"
    elif trade == "NO" and quality_grade == "Reject":
        sell_strategy = "AVOID / NO TRADE"
    if resistance_breakout_mode == "RESISTANCE BREAKOUT WATCH":
        watchlist_flag = "YES"
        watchlist_reason = "Needs clean breakout above resistance before swing entry"
        sell_strategy = "WATCH / SCALP ONLY"
    if momentum_breakout_candidate and trade == "WATCH":
        watchlist_flag = "YES"
        watchlist_reason = "Momentum breakout candidate needs volume confirmation"
        sell_strategy = "WAIT FOR ENTRY"
    elif momentum_breakout_candidate and trade == "YES":
        watchlist_flag = "NO"
        watchlist_reason = "Already Trade YES"
        sell_strategy = "HOLD TO 3R IF VOLUME HOLDS" if explosive_score >= 9 else "PARTIAL AT 2R, TRAIL REST"
    setup_type = classify_setup_type(
        vcp_status=vcp.status,
        action=action,
        current_setup_status=current_setup_status,
        resistance_breakout_mode=resistance_breakout_mode,
        momentum_breakout_candidate=momentum_breakout_candidate,
        latest=latest_with_pivot,
        healthy_pullback_label=healthy_pullback_label,
        institutional_tightness_score=institutional_tightness_score,
    )
    signal_state, signal_trade, signal_watchlist, signal_why, signal_decision = determine_signal_state(
        setup_grade=quality_grade,
        final_score=final_score,
        rs_score=rs_score,
        explosive_score=explosive_score,
        risk_pct=risk_pct,
        latest=latest,
        ma10_rising=ma10_rising,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        earnings_risk_label=earnings_label,
        vcp_status=vcp.status,
        pivot=pivot,
        higher_low_structure=higher_low_structure,
        volume_contraction=vcp.volume_contraction,
        ma10_distance=ma10_distance,
        rsi=float(latest["RSI14"]),
        action=action,
        momentum_breakout_candidate=momentum_breakout_candidate,
        resistance_breakout_mode=resistance_breakout_mode,
        resistance_distance_pct=resistance_distance_pct,
        technical_score=technical_score,
        trend_score=trend_score,
        tightness_score=tightness_score,
        breakout_quality_score=breakout_quality_score,
        rvol=rvol,
        market_environment=market_environment,
        live_breakout_status=live_breakout_status,
        stage_label=stage_label,
        live_mode=live_mode,
    )
    trade = signal_trade
    watchlist_flag = signal_watchlist
    why_selected = signal_why
    decision_reason = signal_decision
    trade_reason = signal_decision
    watchlist_reason = signal_why if watchlist_flag == "YES" else "Already Trade YES" if trade == "YES" else signal_why
    if signal_state == "REJECT":
        quality_grade = "Reject"
        sell_strategy = "AVOID / NO TRADE"
    if signal_state == "EXTENDED DO NOT CHASE":
        action = "EXTENDED"
        setup_type = "EXTENDED"
        sell_strategy = "AVOID / NO TRADE"
    if setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        action = "MOMENTUM BREAKOUT"
        quality_grade = "A+" if trade == "YES" else "A"
    if signal_state in {"BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}:
        sell_strategy = "WAIT FOR ENTRY"
    if signal_state == "BUY NOW" and setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        sell_strategy = "HOLD TO 3R IF VOLUME HOLDS" if explosive_score >= 9 else "PARTIAL AT 2R, TRAIL REST"

    latest_for_reject = latest.copy()
    prior_lows = data["Low"].iloc[-21:-1] if len(data) > 21 else data["Low"].iloc[:-1]
    latest_for_reject["RecentStructureLow"] = float(prior_lows.min()) if not prior_lows.empty else np.nan
    hard_reject, hard_reject_reason = hard_reject_check(
        latest=latest_for_reject,
        trend_score=trend_score,
        risk_pct=risk_pct,
        action=action,
        current_setup_status=current_setup_status,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        earnings_risk_label=earnings_label,
        setup_grade=quality_grade,
    )
    signal_state, trade, watchlist_flag, quality_grade, decision_reason = apply_institutional_decision_layer(
        signal_state=signal_state,
        trade=trade,
        watchlist_flag=watchlist_flag,
        quality_grade=quality_grade,
        decision_reason=decision_reason,
        setup_type=setup_type,
        vcp_status=vcp.status,
        final_score=final_score,
        adjusted_score=adjusted_score,
        institutional_quality_score=institutional_quality_score,
        rs_score=rs_score,
        risk_pct=risk_pct,
        breakout_quality_score=breakout_quality_score,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        hard_reject=hard_reject,
        hard_reject_reason=hard_reject_reason,
        momentum_breakout_candidate=momentum_breakout_candidate,
        ma10_distance=ma10_distance,
        rsi=float(latest["RSI14"]),
        leader_label=leader_label,
    )
    strong_institutional_pullback = (
        leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}
        and healthy_pullback_score >= 7
        and (price_above_ma10 or holding_ma20)
        and lighter_pullback_volume
        and score_at_least(rs_score, 7)
    )
    decision_reason_override = ""
    if strong_institutional_pullback and not hard_reject:
        signal_state = "WAIT PULLBACK" if pd.notna(risk_pct) and risk_pct > 10 else "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        quality_grade = "A" if quality_grade == "Reject" else quality_grade
        decision_reason_override = "WATCH: healthy pullback, holding MA10 with lighter volume; wait for rebound trigger."
    if sector_leadership_status == "CYCLICAL RISK" and leader_label == "CYCLICAL BREAKOUT" and not hard_reject:
        if signal_state == "BUY NOW":
            signal_state = "WATCH"
            trade = "NO"
            watchlist_flag = "YES"
        decision_reason_override = "WATCH: strong technical breakout but cyclical sector; monitor volume and RSI."
    decision_reason = hard_reject_reason if hard_reject else decision_reason_override or institutional_decision_reason(
        signal_state=signal_state,
        ticker=ticker,
        leader_label=leader_label,
        setup_type=setup_type,
        sector_group=sector_info.get("sector_group", "Other"),
        breakout_alert=breakout_alert,
        rs_score=rs_score,
        risk_pct=risk_pct,
        volume_confirmation=volume_confirmation,
        institutional_quality_score=institutional_quality_score,
        earnings_risk_label=earnings_label,
    )
    trade_reason = decision_reason
    watchlist_reason = decision_reason if watchlist_flag == "YES" else "Already Trade YES" if trade == "YES" else decision_reason
    if signal_state in {"BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}:
        sell_strategy = "WAIT FOR ENTRY"
    elif signal_state == "REJECT":
        sell_strategy = "AVOID / NO TRADE"
    elif signal_state == "BUY NOW" and setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        sell_strategy = "HOLD TO 3R IF VOLUME HOLDS" if explosive_score >= 9 else "PARTIAL AT 2R, TRAIL REST"

    vcp_label = classify_vcp_label(vcp.status, action, current_setup_status, resistance_breakout_mode)
    if setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        vcp_label = "Momentum Breakout Candidate"
    if setup_type == "RESISTANCE BREAKOUT WATCH":
        vcp_label = "RESISTANCE BREAKOUT WATCH"

    if setup_type == "RESISTANCE BREAKOUT WATCH":
        entry_type = "RESISTANCE BREAKOUT WATCH"
    elif setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        entry_type = "MOMENTUM BREAKOUT"
    elif action == "READY" and vcp.status in {"VALID VCP", "EARLY VCP"}:
        entry_type = "VCP BREAKOUT"
    elif action == "PULLBACK ENTRY":
        entry_type = "PULLBACK ENTRY"
    elif action == "EXTENDED":
        entry_type = "EXTENDED DO NOT CHASE"
    else:
        entry_type = "NO TRADE"

    watch_type = determine_watch_type(
        signal_state=signal_state,
        setup_type=setup_type,
        action=action,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        earnings_risk_label=earnings_label,
        resistance_breakout_mode=resistance_breakout_mode,
        pivot=pivot,
        healthy_pullback_label=healthy_pullback_label,
        institutional_tightness_score=institutional_tightness_score,
    )
    if watch_type == "MOMENTUM WATCH" or setup_type == "MOMENTUM BREAKOUT EXCEPTION":
        prefix = DECISION_PREFIX_BY_STATE.get(signal_state, "WATCH:").rstrip(":")
        decision_reason = f"{prefix}: high RS leader, not pure VCP but valid momentum setup"
    elif watch_type == "HEALTHY PULLBACK":
        decision_reason = "WATCH: healthy pullback, holding MA10 with lighter volume; wait for rebound trigger."
    elif watch_type == "TIGHT BASE":
        decision_reason = "WATCH: tight institutional base; wait for breakout volume."
    elif watch_type == "POST-BREAKOUT DIGESTION":
        decision_reason = "WATCH: post-breakout digestion; wait for rebound trigger."
    elif signal_state == "BUY ON BREAKOUT":
        decision_reason = "BUY ON BREAKOUT: near pivot, strong RS, wait for breakout volume."
    elif signal_state == "WATCH" and watch_type in {"WAIT MA10 SUPPORT", "WAIT MA20 SUPPORT"}:
        decision_reason = "WATCH: pullback setup; wait for MA10/MA20 support confirmation"
    elif signal_state == "EXTENDED DO NOT CHASE":
        decision_reason = "EXTENDED: do not chase; wait for base or MA10 reset."

    signal_state, trade, watchlist_flag, decision_reason = finalize_signal_outputs(
        signal_state=signal_state,
        trade=trade,
        watchlist_flag=watchlist_flag,
        decision_reason=decision_reason,
        earnings_risk_label=earnings_label,
        days_to_earnings=earnings_info.get("days_to_earnings"),
    )
    watch_type = determine_watch_type(
        signal_state=signal_state,
        setup_type=setup_type,
        action=action,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        earnings_risk_label=earnings_label,
        resistance_breakout_mode=resistance_breakout_mode,
        pivot=pivot,
        healthy_pullback_label=healthy_pullback_label,
        institutional_tightness_score=institutional_tightness_score,
    )
    if watch_type == "EARNINGS RISK WATCH" and signal_state == "WATCH":
        decision_reason = "WATCH: strong setup but earnings risk high; consider smaller size or wait after earnings."
    decision_reason = reason_with_signal_prefix(signal_state, decision_reason)
    trade_reason = decision_reason
    watchlist_reason = "Already Trade YES" if trade == "YES" else decision_reason
    if signal_state in {"BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"}:
        sell_strategy = "WAIT FOR ENTRY"
    elif signal_state == "REJECT":
        sell_strategy = "AVOID / NO TRADE"
    elif signal_state == "EXTENDED DO NOT CHASE":
        sell_strategy = "AVOID / NO TRADE"
    practical_tp1, practical_tp2, practical_tp3 = enforce_tp_ladder(entry, stop, practical_tp1, practical_tp2, practical_tp3)
    ideal_tp, ideal_tp_reason, ideal_r = validate_ideal_tp(
        ideal_tp=ideal_tp,
        ideal_tp_reason=ideal_tp_reason,
        ideal_r=ideal_r,
        entry=entry,
        stop=stop,
        target_2r=practical_tp2,
        target_3r=practical_tp3,
        nearest_resistance=nearest_resistance,
        current_close=float(latest["Close"]),
        signal_state=signal_state,
    )
    if ideal_tp > entry * 1.35:
        tp_type = "RUNNER TP" if tp_type == "RUNNER TP" else "TOO FAR / USE TRAILING STOP"
    if PRACTICAL_TP_NOTE not in decision_reason and signal_state in ACTIONABLE_SIGNAL_STATES:
        decision_reason = f"{decision_reason} {PRACTICAL_TP_NOTE}"
        trade_reason = decision_reason
        watchlist_reason = "Already Trade YES" if trade == "YES" else decision_reason

    entry_quality_score, entry_quality_label = calculate_entry_quality_score(
        latest=latest,
        pivot=pivot,
        risk_pct=risk_pct,
        ma10_distance=ma10_distance,
        rsi=float(latest["RSI14"]),
        institutional_tightness_score=institutional_tightness_score,
        setup_type=setup_type,
        breakout_alert=breakout_alert,
        stage_label=stage_label,
    )
    professional_score = calculate_professional_score(
        institutional_quality_score=institutional_quality_score,
        leader_label=leader_label,
        sector_leadership_status=sector_leadership_status,
        rs_score=rs_score,
        market_score=market_score,
        entry_quality_score=entry_quality_score,
        institutional_tightness_score=institutional_tightness_score,
        healthy_pullback_score=healthy_pullback_score,
        tightness_score=tightness_score,
        vcp_status=vcp.status,
        risk_pct=risk_pct,
        ideal_r=ideal_r,
        tp_type=tp_type,
        signal_state=signal_state,
        hard_reject=hard_reject,
        price_above_ma20=bool(float(latest["Close"]) >= float(latest["MA20"])),
    )
    trade_tier, tier_reason = determine_trade_tier(
        professional_score=professional_score,
        adjusted_score=adjusted_score,
        entry_quality_score=entry_quality_score,
        risk_pct=risk_pct,
        rs_score=rs_score,
        signal_state=signal_state,
        leader_label=leader_label,
        sector_leadership_status=sector_leadership_status,
        setup_type=setup_type,
        hard_reject=hard_reject,
        extended=extended,
        institutional_quality_score=institutional_quality_score,
        price_above_ma20=bool(float(latest["Close"]) >= float(latest["MA20"])),
    )
    if trade_tier == "Tier 1 - Immediate Action":
        if signal_state == "BUY NOW":
            trade = "YES"
            watchlist_flag = "NO"
        elif signal_state in {"WATCH", "WAIT PULLBACK"} and breakout_alert in {"NEAR BREAKOUT", "BREAKOUT IN PROGRESS", "CONFIRMED BREAKOUT"}:
            signal_state = "BUY ON BREAKOUT"
            trade = "NO"
            watchlist_flag = "YES"
        decision_reason = tier_reason
    elif trade_tier == "Tier 2 - High Quality, Wait Better Entry":
        if extended:
            signal_state = "EXTENDED DO NOT CHASE"
        elif signal_state == "BUY NOW" or entry_quality_score < 8 or (pd.notna(risk_pct) and risk_pct > 10):
            signal_state = "WAIT PULLBACK" if (pd.notna(risk_pct) and risk_pct > 12) or extended else "WATCH"
        trade = "NO"
        watchlist_flag = "NO" if signal_state == "EXTENDED DO NOT CHASE" else "YES"
        decision_reason = tier_reason
    elif trade_tier == "Tier 3 - Leadership Watchlist":
        if signal_state in {"BUY NOW", "BUY ON BREAKOUT"}:
            signal_state = "WATCH"
        elif signal_state == "REJECT" and not hard_reject:
            signal_state = "WATCH"
        trade = "NO"
        watchlist_flag = "YES" if signal_state in {"WATCH", "WAIT PULLBACK", "BUY ON BREAKOUT"} else "NO"
        decision_reason = tier_reason
    else:
        if hard_reject:
            signal_state = "REJECT"
            trade = "NO"
            watchlist_flag = "NO"
            decision_reason = tier_reason

    if (
        leader_label == "LAGGARD / AVOID"
        and trade_tier == "Tier 2 - High Quality, Wait Better Entry"
        and not (score_at_least(rs_score, 7) and entry_quality_score >= 8)
    ):
        trade_tier = "Tier 3 - Leadership Watchlist"
        if signal_state in {"BUY NOW", "BUY ON BREAKOUT"}:
            signal_state = "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "TIER 3: leadership watchlist; setup not ready."
    if trade_tier == "Tier 2 - High Quality, Wait Better Entry" and signal_state == "BUY ON BREAKOUT" and entry_quality_score < 7:
        signal_state = "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "WATCH: near trigger but entry quality is not clean enough for breakout action yet."

    signal_state, trade, watchlist_flag, decision_reason = finalize_signal_outputs(
        signal_state=signal_state,
        trade=trade,
        watchlist_flag=watchlist_flag,
            decision_reason=decision_reason,
            earnings_risk_label=earnings_label,
            days_to_earnings=earnings_info.get("days_to_earnings"),
            trade_tier=trade_tier,
        )
    if PRACTICAL_TP_NOTE not in decision_reason and signal_state in ACTIONABLE_SIGNAL_STATES:
        decision_reason = f"{decision_reason} {PRACTICAL_TP_NOTE}"
    professional_score = calculate_professional_score(
        institutional_quality_score=institutional_quality_score,
        leader_label=leader_label,
        sector_leadership_status=sector_leadership_status,
        rs_score=rs_score,
        market_score=market_score,
        entry_quality_score=entry_quality_score,
        institutional_tightness_score=institutional_tightness_score,
        healthy_pullback_score=healthy_pullback_score,
        tightness_score=tightness_score,
        vcp_status=vcp.status,
        risk_pct=risk_pct,
        ideal_r=ideal_r,
        tp_type=tp_type,
        signal_state=signal_state,
        hard_reject=hard_reject,
        price_above_ma20=bool(float(latest["Close"]) >= float(latest["MA20"])),
    )
    watch_type = determine_watch_type(
        signal_state=signal_state,
        setup_type=setup_type,
        action=action,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        earnings_risk_label=earnings_label,
        resistance_breakout_mode=resistance_breakout_mode,
        pivot=pivot,
        healthy_pullback_label=healthy_pullback_label,
        institutional_tightness_score=institutional_tightness_score,
    )
    ma10_efficiency_score = calculate_ma10_efficiency_score(data)
    character_change_flag = detect_character_change(data, pivot, breakout_alert, current_setup_status)
    entry_timing = entry_timing_label(
        latest=latest,
        pivot=pivot,
        risk_pct=risk_pct,
        ma10_distance=ma10_distance,
        rsi=float(latest["RSI14"]),
        setup_type=setup_type,
        breakout_alert=breakout_alert,
        character_change_flag=character_change_flag,
    )
    stage_maturity_label = classify_stage_label(data, pivot, character_change_flag, current_setup_status)
    pullback_quality = classify_pullback_quality(
        data=data,
        pivot=pivot,
        risk_pct=risk_pct,
        ma10_distance=ma10_distance,
        ma20_distance=ma20_distance,
        character_change_flag=character_change_flag,
    )
    vcp_tightness_score = calculate_vcp_tightness_score(data, vcp, current_setup_status)
    tradeability_score = calculate_tradeability_score(
        latest=latest,
        risk_pct=risk_pct,
        stop=stop,
        ma10_distance=ma10_distance,
    )

    final_score = int(min(max(final_score + stage_score_adjustment(stage_maturity_label), 0), 100))
    final_score = min(final_score, timing_score_cap(entry_timing))
    if character_change_flag == "CHARACTER CHANGE":
        final_score = min(final_score, 45)
    adjusted_score = adjusted_final_score(
        final_score,
        institutional_quality_score,
        sector_score,
        market_score,
        sector_leadership_weight=sector_leadership_weight,
        institutional_tightness_score=institutional_tightness_score,
        theme_weight=theme_weight,
    )

    high_quality_leader = leader_label in {"INSTITUTIONAL LEADER", "MOMENTUM LEADER", "SECTOR LEADER"}
    protected_high_quality_leader = (
        leader_label in {"INSTITUTIONAL LEADER", "SECTOR LEADER"}
        and score_at_least(rs_score, 8)
        and pd.notna(adjusted_score)
        and adjusted_score >= 80
        and not hard_reject
    )
    extended_timing = entry_timing in {"EXTENDED - WAIT", "TOO LATE"} or stage_maturity_label in {"LATE STAGE 2", "CLIMAX / PARABOLIC"}
    if character_change_flag == "CHARACTER CHANGE" or stage_maturity_label == "FAILED STAGE":
        hard_reject = True
        signal_state = "REJECT"
        trade = "NO"
        watchlist_flag = "NO"
        decision_reason = "Character change or failed stage detected: wait for structure to rebuild."
        sell_strategy = "AVOID / NO TRADE"
    elif high_quality_leader and extended_timing and not hard_reject:
        signal_state = "WAIT PULLBACK"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "High-quality leader, but entry is extended. Wait for MA10/MA20 reset or tight base."
        sell_strategy = "WAIT FOR ENTRY"
    elif tradeability_score < 5 and signal_state == "BUY NOW":
        signal_state = "WAIT PULLBACK" if high_quality_leader else "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = "Tradeability is not clean enough for BUY NOW; wait for tighter risk/reward."
    elif protected_high_quality_leader and signal_state == "REJECT":
        signal_state = "WAIT PULLBACK" if extended_timing else "WATCH"
        trade = "NO"
        watchlist_flag = "YES"
        decision_reason = (
            "High-quality leader, but entry is extended. Wait for MA10/MA20 reset or tight base."
            if extended_timing
            else "Good high-quality leader, but no clean trigger yet."
        )

    buy_explainability = buy_setup_explainability(
        adjusted_score=adjusted_score,
        professional_score=professional_score,
        rs_score=rs_score,
        risk_pct=risk_pct,
        leader_label=leader_label,
        stage_label=stage_maturity_label,
        character_change_flag=character_change_flag,
        earnings_risk_label=earnings_label,
        days_to_earnings=earnings_info.get("days_to_earnings"),
        setup_type=setup_type,
        ma10_distance=ma10_distance,
        ma20_distance=ma20_distance,
        hard_reject=hard_reject,
        final_score=final_score,
        breakout_alert=breakout_alert,
        volume_confirmation=volume_confirmation,
        setup_quality_grade=quality_grade,
        pullback_quality=pullback_quality,
    )
    quality_guard_blocks_buy_now = quality_grade in {"C", "Reject"} or pullback_quality == "HIGH RISK PULLBACK"
    if buy_explainability["actionable_buy_zone"] and not extended_timing and not quality_guard_blocks_buy_now:
        signal_state = "BUY NOW"
        trade = "YES"
        watchlist_flag = "NO"
        if buy_explainability["breakout_confirmed"] and buy_explainability["volume_confirmed"]:
            decision_reason = "confirmed breakout with volume and controlled risk."
        else:
            decision_reason = "high-quality leader in actionable buy zone; no need to wait for perfect breakout."
    elif buy_explainability["early_position_zone"] and not extended_timing:
        signal_state = "EARLY POSITION"
        trade = "YES"
        watchlist_flag = "YES"
        if quality_guard_blocks_buy_now:
            decision_reason = "quality guard blocks full BUY NOW; pilot position only or wait for breakout confirmation."
        else:
            decision_reason = "high-quality leader; pilot position allowed before full breakout confirmation."
    elif signal_state == "BUY NOW":
        if high_quality_leader and extended_timing:
            signal_state = "WAIT PULLBACK"
            decision_reason = "high-quality leader, but entry is extended or risk/reward is not clean enough; wait for MA10/MA20 reset."
        elif entry_timing in {"NEAR PIVOT", "BREAKOUT CONFIRMED"} and pd.notna(risk_pct) and risk_pct <= 12:
            signal_state = "BUY ON BREAKOUT"
            decision_reason = "near trigger; wait for breakout volume or confirmation."
        else:
            signal_state = "WATCH"
            decision_reason = "quality setup but no trigger yet."
        trade = "NO"
        watchlist_flag = "YES"

    signal_state, trade, watchlist_flag, decision_reason = finalize_signal_outputs(
        signal_state=signal_state,
        trade=trade,
        watchlist_flag=watchlist_flag,
        decision_reason=decision_reason,
        earnings_risk_label=earnings_label,
        days_to_earnings=earnings_info.get("days_to_earnings"),
        trade_tier=trade_tier,
    )
    professional_score = calculate_professional_score(
        institutional_quality_score=institutional_quality_score,
        leader_label=leader_label,
        sector_leadership_status=sector_leadership_status,
        rs_score=rs_score,
        market_score=market_score,
        entry_quality_score=entry_quality_score,
        institutional_tightness_score=institutional_tightness_score,
        healthy_pullback_score=healthy_pullback_score,
        tightness_score=tightness_score,
        vcp_status=vcp.status,
        risk_pct=risk_pct,
        ideal_r=ideal_r,
        tp_type=tp_type,
        signal_state=signal_state,
        hard_reject=hard_reject,
        price_above_ma20=bool(float(latest["Close"]) >= float(latest["MA20"])),
    )
    trade_tier, tier_reason = determine_trade_tier(
        professional_score=professional_score,
        adjusted_score=adjusted_score,
        entry_quality_score=entry_quality_score,
        risk_pct=risk_pct,
        rs_score=rs_score,
        signal_state=signal_state,
        leader_label=leader_label,
        sector_leadership_status=sector_leadership_status,
        setup_type=setup_type,
        hard_reject=hard_reject,
        extended=extended_timing,
        institutional_quality_score=institutional_quality_score,
        price_above_ma20=bool(float(latest["Close"]) >= float(latest["MA20"])),
    )
    if not hard_reject and high_quality_leader and extended_timing and trade_tier == "Tier 4 - Avoid / Reject":
        trade_tier = "Tier 2 - High Quality, Wait Better Entry"
    if signal_state in {"BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"} and trade_tier == "Tier 4 - Avoid / Reject":
        trade_tier = "Tier 2 - High Quality, Wait Better Entry" if high_quality_leader else "Tier 3 - Leadership Watchlist"
    quality_score = calculate_quality_score(
        institutional_quality_score=institutional_quality_score,
        rs_score=rs_score,
        trend_score=trend_score,
        sector_score=sector_score,
        theme_weight=theme_weight,
        leader_label=leader_label,
    )
    execution_score = calculate_execution_score(
        entry_quality_score=entry_quality_score,
        tradeability_score=tradeability_score,
        vcp_tightness_score=vcp_tightness_score,
        ma10_efficiency_score=ma10_efficiency_score,
        risk_pct=risk_pct,
        ma10_distance=ma10_distance,
        ma20_distance=ma20_distance,
        character_change_flag=character_change_flag,
    )

    executable_score, executable_grade, executable_reason = executable_score_and_grade(
        entry_quality_score=entry_quality_score,
        risk_pct=risk_pct,
        healthy_pullback_score=healthy_pullback_score,
        institutional_tightness_score=institutional_tightness_score,
        ma10_efficiency_score=ma10_efficiency_score,
        institutional_quality_score=institutional_quality_score,
        theme_weight=theme_weight,
        breakout_quality_score=breakout_quality_score,
        ma10_distance=ma10_distance,
        pivot=pivot,
        volume_dry_up=vcp.volume_contraction,
        breakout_alert=breakout_alert,
        signal_state=signal_state,
        hard_reject=hard_reject,
        character_change_flag=character_change_flag,
        latest=latest,
        leader_label=leader_label,
    )
    executable_grade, executable_reason = calibrate_executable_grade(
        executable_grade=executable_grade,
        executable_score=executable_score,
        executable_reason=executable_reason,
        signal_state=signal_state,
        trade=trade,
        watchlist_flag=watchlist_flag,
        risk_pct=risk_pct,
        entry_timing=entry_timing,
        leader_label=leader_label,
        character_change_flag=character_change_flag,
        hard_reject=hard_reject,
        setup_type=setup_type,
        breakout_alert=breakout_alert,
        rs_score=rs_score,
        sector_leadership_status=sector_leadership_status,
    )
    if character_change_flag == "CHARACTER CHANGE":
        executable_grade = "C - AVOID"
        executable_score = min(float(executable_score), 45)
        executable_reason = "C - AVOID: Character change detected: wait for structure to rebuild."
        trade = "NO"
        watchlist_flag = "NO" if signal_state == "REJECT" else "YES"
        sell_strategy = "AVOID / NO TRADE" if signal_state == "REJECT" else "WAIT FOR ENTRY"
    elif high_quality_leader and extended_timing and executable_grade == "B - WATCHLIST":
        executable_reason = "B - WATCHLIST: High-quality leader, but entry is extended. Wait for MA10/MA20 reset or tight base."
    signal_reason_detail = strip_executable_prefix(executable_reason)
    if signal_state == "BUY ON BREAKOUT":
        signal_reason_detail = "near trigger; wait for breakout confirmation before execution."
    elif signal_state == "BUY NOW" and buy_explainability.get("actionable_buy_zone"):
        if buy_explainability.get("breakout_confirmed") and buy_explainability.get("volume_confirmed"):
            signal_reason_detail = "confirmed breakout with volume and controlled risk."
        else:
            signal_reason_detail = "high-quality leader in actionable buy zone; no need to wait for perfect breakout."
    elif signal_state == "EARLY POSITION":
        signal_reason_detail = "high-quality leader; pilot position allowed before full breakout confirmation."
    elif signal_state == "WATCH" and signal_reason_detail.lower().startswith(("hard reject", "failed setup", "character change", "entry is too late")):
        signal_reason_detail = "good setup or leader context, but no clean trigger yet."
    elif signal_state == "WAIT PULLBACK" and high_quality_leader and extended_timing:
        signal_reason_detail = "high-quality leader, but entry is extended; wait for MA10/MA20 reset or tight base."
    elif signal_state == "REJECT" and not hard_reject:
        signal_reason_detail = "weak setup condition triggered."
    decision_reason = reason_with_signal_prefix(
        signal_state,
        f"{signal_reason_detail} Entry timing: {entry_timing}. Stage: {stage_maturity_label}. Stock quality: {leader_label}, theme {theme_weight}/10.",
    )
    execution_confidence = execution_confidence_for_signal(signal_state, breakout_alert, volume_confirmation)
    scanner_verdict = scanner_verdict_for_signal(signal_state, decision_reason)
    buy_criteria_passed = "; ".join(buy_explainability.get("passed", [])) or "None"
    buy_criteria_failed = "; ".join(buy_explainability.get("failed", [])) or "None"
    blocked_by = "; ".join(buy_explainability.get("blocked_by", ["None"])) or "None"
    downgrade_reason = str(buy_explainability.get("downgrade_reason", "None"))
    upgrade_reason = str(buy_explainability.get("upgrade_reason", "None"))
    missing_condition = str(buy_explainability.get("missing_condition", "None"))
    suggested_action = str(buy_explainability.get("suggested_action", "None"))
    action_readiness = action_readiness_label(
        trade_tier=trade_tier,
        signal_state=signal_state,
        professional_score=professional_score,
        entry_quality_score=entry_quality_score,
    )
    trade_reason = decision_reason
    watchlist_reason = "Already Trade YES" if trade == "YES" else decision_reason

    contraction_text = " -> ".join(f"{value:g}%" for value in vcp.contractions) if vcp.contractions else "N/A"
    latest_candle = pd.Timestamp(data.index[-1])
    data_stale, stale_warning = is_data_stale(latest_candle)
    quote_price = quote_info.get("current_price", np.nan)
    sync_warning, sync_mismatch_pct = chart_sync_status(float(latest["Close"]), quote_price)
    rel_volume = (
        float(latest["Volume"]) / float(latest["AvgVol20"])
        if pd.notna(latest.get("AvgVol20", np.nan)) and float(latest["AvgVol20"]) > 0
        else np.nan
    )
    distance_from_high = (
        (float(latest["Close"]) / float(latest["High52W"]) - 1) * 100
        if pd.notna(latest.get("High52W", np.nan)) and float(latest["High52W"]) > 0
        else np.nan
    )

    notes = "; ".join(
        [
            pivot.label,
            extension_note,
            volume_note,
            f"Sector {sector_etf}: {sector_leadership}",
            f"Market: {market_environment}",
            f"RVOL: {rvol_label}",
            f"Stage: {stage_label}",
            f"Institutional action: {institutional_action}",
            f"Earnings: {earnings_label}",
            f"TP: {ideal_tp_reason}",
            stale_warning,
            sync_warning,
            *trend_notes[:2],
            *technical_notes[:3],
            invalidation,
        ]
    )

    row = {
        "ticker": ticker,
        "Sector / Industry": sector_info.get("sector_industry", "N/A"),
        "Sector Group": sector_info.get("sector_group", "Other"),
        "Theme Group": sector_info.get("theme_group", sector_info.get("sector_group", "Other")),
        "Sector Raw": sector_info.get("sector", "N/A"),
        "Industry Raw": sector_info.get("industry", "N/A"),
        "close": round(float(latest["Close"]), 2),
        "Current Price": round(float(quote_price), 2) if pd.notna(quote_price) else round(float(latest["Close"]), 2),
        "% Change": round(float(quote_info.get("percent_change", np.nan)), 2) if pd.notna(quote_info.get("percent_change", np.nan)) else "N/A",
        "Premarket Price": round(float(quote_info.get("premarket_price", np.nan)), 2) if pd.notna(quote_info.get("premarket_price", np.nan)) else "N/A",
        "Afterhours Price": round(float(quote_info.get("afterhours_price", np.nan)), 2) if pd.notna(quote_info.get("afterhours_price", np.nan)) else "N/A",
        "Today's Volume": format_count_number(latest.get("Volume")),
        "Relative Volume": round(rvol, 2) if pd.notna(rvol) else "N/A",
        "RVOL": round(rvol, 2) if pd.notna(rvol) else "N/A",
        "RVOL Label": rvol_label,
        "Intraday Volume Ratio": round(intraday_volume_ratio, 2) if pd.notna(intraday_volume_ratio) else "N/A",
        "52-week high": round(float(latest["High52W"]), 2) if pd.notna(latest.get("High52W", np.nan)) else "N/A",
        "Distance From High %": round(distance_from_high, 2) if pd.notna(distance_from_high) else "N/A",
        "market cap": format_large_number(market_cap),
        "market cap raw": market_cap,
        "avg dollar volume": format_large_number(latest.get("AvgDollarVol50")),
        "avg dollar volume raw": latest.get("AvgDollarVol50"),
        "RSI": round(float(latest["RSI14"]), 1),
        "RS Score": round(float(rs_score), 1) if pd.notna(rs_score) else "N/A",
        "RS Score Raw": round(float(rs_score), 1) if pd.notna(rs_score) else np.nan,
        "Trend Score": trend_score,
        "Technical Score": technical_score,
        "Sector Score": sector_score,
        "Sector ETF": sector_etf,
        "Sector Leadership": sector_leadership,
        "Sector Leadership Status": sector_leadership_status,
        "Sector Leadership Weight": sector_leadership_weight,
        "Sector Spread %": sector_spread if sector_spread is not None else "N/A",
        "Market Score": market_score,
        "Market Environment": market_environment,
        "Final Score": final_score,
        "Adjusted Final Score": adjusted_score,
        "Professional Score": professional_score,
        "Quality Score": quality_score,
        "Execution Score": execution_score,
        "Institutional Quality Score": institutional_quality_score,
        "Theme Weight": theme_weight,
        "Executable Grade": executable_grade,
        "Executable Score": executable_score,
        "Entry Timing Label": entry_timing,
        "MA10 Efficiency Score": ma10_efficiency_score,
        "Character Change Flag": character_change_flag,
        "Stage Label": stage_maturity_label,
        "Pullback Quality": pullback_quality,
        "VCP Tightness Score": vcp_tightness_score,
        "Tradeability Score": tradeability_score,
        "Entry Quality Score": entry_quality_score,
        "Entry Quality Label": entry_quality_label,
        "Trade Tier": trade_tier,
        "Action Readiness Label": action_readiness,
        "Execution Confidence": execution_confidence,
        "Buy Criteria Passed": buy_criteria_passed,
        "Buy Criteria Failed": buy_criteria_failed,
        "Blocked By": blocked_by,
        "Downgrade Reason": downgrade_reason,
        "Upgrade Reason": upgrade_reason,
        "Scanner Verdict": scanner_verdict,
        "Missing Condition": missing_condition,
        "Suggested Action": suggested_action,
        "Healthy Pullback Score": healthy_pullback_score,
        "Healthy Pullback Label": healthy_pullback_label,
        "Institutional Tightness Score": institutional_tightness_score,
        "Institutional Tightness Label": institutional_tightness_label,
        "Leader Quality Label": leader_label,
        "Breakout Quality Score": breakout_quality_score,
        "Stage Analysis": stage_label,
        "Institutional Action": institutional_action,
        "VCP Status": vcp.status,
        "VCP Label": vcp_label,
        "Setup Type": setup_type,
        "Signal State": signal_state,
        "Watch Type": watch_type,
        "Contractions": contraction_text,
        "contraction count": vcp.count,
        "final contraction %": vcp.final_pct,
        "volume contraction": "Yes" if vcp.volume_contraction else "No",
        "Volume Dry-Up": "Yes" if vcp.volume_contraction else "No",
        "Pivot": pivot.pivot,
        "Distance to Pivot %": pivot.distance_pct,
        "Action Label": action,
        "Tightness Score": tightness_score,
        "Tightness Label": tightness_label,
        "Explosive Score": explosive_score,
        "Explosive Label": explosive_label,
        "Setup Quality Grade": quality_grade,
        "RR Ratio": rr_ratio if rr_ratio is not None else "Invalid",
        "RR Score": rr_score,
        "Volume Confirmation": volume_confirmation,
        "Breakout Alert": breakout_alert,
        "Live Breakout Status": live_breakout_status,
        "Alert Event": "LIVE BREAKOUT" if live_breakout_status == "LIVE BREAKOUT" else "TRADE YES" if trade == "YES" else breakout_alert,
        "Current Setup Status": current_setup_status,
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
        "Earnings Intelligence": earnings_intelligence,
        "Trade": trade,
        "Trade Reason": trade_reason,
        "Entry Type": entry_type,
        "Decision Reason": decision_reason,
        "Why Selected": why_selected,
        "WATCHLIST FLAG": watchlist_flag,
        "Watchlist Reason": watchlist_reason,
        "Entry Trigger": entry,
        "Stop Loss": stop,
        "Risk %": risk_pct,
        "Risk Note": risk_quality_note,
        "Target 1R": target_1r,
        "Target 2R": target_2r,
        "Target 3R": target_3r,
        "TP1": practical_tp1,
        "TP2": practical_tp2,
        "TP3": practical_tp3,
        "Nearest Resistance": nearest_resistance,
        "Resistance Blocked": "YES" if resistance_blocks_1r else "NO",
        "Resistance Breakout Mode": resistance_breakout_mode,
        "Breakout Above Resistance Trigger": rb_entry,
        "Resistance Breakout Entry": rb_entry,
        "Resistance Breakout Stop": rb_stop,
        "Resistance Breakout 1R": rb_1r,
        "Resistance Breakout 2R": rb_2r,
        "Resistance Breakout 3R": rb_3r,
        "Resistance Breakout Risk %": rb_risk_pct,
        "Ideal TP": ideal_tp,
        "TP Type": tp_type,
        "Ideal TP Reason": ideal_tp_reason,
        "Sell Strategy": sell_strategy,
        "Trail Stop Level": trail_stop,
        "TP Quality Score": tp_quality_score,
        "Ideal TP R": ideal_r,
        "MA10": round(float(latest["MA10"]), 2),
        "MA20": round(float(latest["MA20"]), 2),
        "MA10 Distance %": ma10_distance,
        "MA20 Distance %": ma20_distance,
        "1D Return %": round(period_return(data, 1), 2) if pd.notna(period_return(data, 1)) else "N/A",
        "1W Return %": round(period_return(data, 5), 2) if pd.notna(period_return(data, 5)) else "N/A",
        "Last Updated": scan_timestamps.get("market_timestamp", "N/A"),
        "Local Last Updated": scan_timestamps.get("local_timestamp", "N/A"),
        "Market Session": scan_timestamps.get("session_status", "N/A"),
        "Latest Candle Date": latest_candle.strftime("%Y-%m-%d"),
        "Dataframe Last Index": str(data.index[-1]),
        "Fetched Rows": int(len(data)),
        "Quote Source": quote_info.get("quote_source", "N/A"),
        "Quote Time": quote_info.get("quote_time", "N/A"),
        "Quote Applied To Candle": "YES" if sync_info.get(ticker, False) else "NO",
        "Data Stale": "YES" if data_stale else "NO",
        "Data Warning": stale_warning,
        "Chart Sync": sync_warning,
        "Chart/Quote Mismatch %": sync_mismatch_pct if pd.notna(sync_mismatch_pct) else "N/A",
        "Notes": notes,
        "Company Name": "N/A",
        "Hard Reject": "YES" if hard_reject else "NO",
        "Hard Reject Reason": hard_reject_reason,
        "_pivot": pivot,
        "_vcp": vcp,
    }
    row["AI Trading Notes"] = build_ai_trading_notes(row)
    return row


def style_scan_table(row: pd.Series) -> List[str]:
    """Color rows by signal state for fast visual review."""
    if row.get("Live Breakout Status") == "LIVE BREAKOUT":
        return ["background-color: #22c55e; color: #052e16; font-weight: 900"] * len(row)
    colors = {
        "BUY NOW": "background-color: #86efac; color: #052e16; font-weight: 800",
        "EARLY POSITION": "background-color: #a7f3d0; color: #064e3b; font-weight: 760",
        "BUY ON BREAKOUT": "background-color: #bbf7d0; color: #14532d; font-weight: 750",
        "WATCH": "background-color: #fef9c3; color: #713f12; font-weight: 650",
        "WAIT PULLBACK": "background-color: #dbeafe; color: #1e3a8a; font-weight: 650",
        "EXTENDED DO NOT CHASE": "background-color: #fed7aa; color: #7c2d12",
        "REJECT": "background-color: #fee2e2; color: #7f1d1d",
        "READY": "background-color: #dcfce7; color: #14532d; font-weight: 700",
        "PULLBACK ENTRY": "background-color: #dbeafe; color: #1e3a8a; font-weight: 700",
        "EXTENDED": "background-color: #fed7aa; color: #7c2d12",
        "FAILED": "background-color: #fee2e2; color: #7f1d1d",
    }
    return [colors.get(row.get("Signal State"), colors.get(row.get("Action Label"), ""))] * len(row)


def style_rvol_cell(value: object) -> str:
    """Color RVOL cells by institutional activity band."""
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return ""
    if numeric > 2:
        return "background-color: #22c55e; color: #052e16; font-weight: 900"
    if numeric >= 1.5:
        return "background-color: #bbf7d0; color: #14532d; font-weight: 700"
    if numeric < 1:
        return "background-color: #e5e7eb; color: #374151"
    return ""


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
        "Target 1R",
        "Target 2R",
        "Target 3R",
        "TP1",
        "TP2",
        "TP3",
        "Nearest Resistance",
        "Breakout Above Resistance Trigger",
        "Resistance Breakout Entry",
        "Resistance Breakout Stop",
        "Resistance Breakout 1R",
        "Resistance Breakout 2R",
        "Resistance Breakout 3R",
        "Resistance Breakout Risk %",
        "Ideal TP",
        "Trail Stop Level",
        "Ideal TP R",
        "RR Ratio",
        "RVOL",
        "Relative Volume",
        "Intraday Volume Ratio",
        "Final Score",
        "Professional Score",
        "Quality Score",
        "Execution Score",
        "Executable Score",
        "Theme Weight",
        "MA10 Efficiency Score",
        "VCP Tightness Score",
        "Tradeability Score",
        "Entry Quality Score",
        "Breakout Quality Score",
        "RS Score",
        "RS Score Raw",
        "Avg RS Score",
        "Avg Explosive Score",
        "Avg Final Score",
        "Avg Breakout Quality",
        "Avg Today %",
        "Avg Week %",
        "1D Return %",
        "1W Return %",
        "Sector Spread %",
        "MA10 Distance %",
        "MA20 Distance %",
        "current price",
        "gain %",
        "unrealized P/L",
        "current R multiple",
        "distance from MA10",
        "distance from MA20",
        "current RSI",
        "current volume vs 20-day average",
        "highest price since entry",
        "lowest price since entry",
        "pullback from high %",
        "suggested stop loss today",
        "updated TP1",
        "updated TP2",
        "updated TP3",
        "updated ideal TP",
    ]
    for column in two_decimal_columns:
        if column in rounded.columns:
            converted = pd.to_numeric(rounded[column], errors="coerce")
            if converted.notna().any():
                rounded[column] = converted.round(2).where(converted.notna(), rounded[column])
    return rounded


def focus_summary_frame(frame: pd.DataFrame, reason_column: str) -> pd.DataFrame:
    """Build a compact top-five focus table for the daily summary."""
    if frame.empty:
        return pd.DataFrame()

    summary = frame.head(5).copy()
    summary["Reason"] = summary[reason_column]
    columns = [
        "ticker",
        "Sector / Industry",
        "VCP Status",
        "VCP Label",
        "Setup Type",
        "Signal State",
        "Executable Grade",
        "Executable Score",
        "Entry Timing Label",
        "Stage Label",
        "Pullback Quality",
        "Trade Tier",
        "Action Readiness Label",
        "Setup Quality Grade",
        "Action Label",
        "Breakout Alert",
        "Live Breakout Status",
        "Professional Score",
        "Quality Score",
        "Execution Score",
        "Entry Quality Score",
        "Final Score",
        "VCP Tightness Score",
        "Tradeability Score",
        "Breakout Quality Score",
        "RS Score",
        "RVOL",
        "Explosive Score",
        "Pivot",
        "Distance to Pivot %",
        "Entry Trigger",
        "Stop Loss",
        "Risk %",
        "RR Score",
        "Ideal TP",
        "TP Quality Score",
        "Decision Reason",
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


def escape_pdf_text(value: str) -> str:
    """Escape text for a tiny built-in PDF export."""
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def dataframe_to_simple_pdf(frame: pd.DataFrame, title: str) -> bytes:
    """Create a basic text PDF without adding heavyweight dependencies."""
    export = frame.fillna("N/A").astype(str)
    lines = [title, ""]
    lines.append(" | ".join(export.columns))
    lines.append("-" * 120)
    for _, row in export.iterrows():
        lines.append(" | ".join(str(row[column])[:40] for column in export.columns))

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
        objects.append(f"{content_obj_num} 0 obj\n<< /Length {len(content.encode('latin-1', errors='ignore'))} >>\nstream\n{content}\nendstream\nendobj\n")
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


def select_ai_top_5(results: pd.DataFrame) -> pd.DataFrame:
    """Rule-based Top 5 ranking for alerts and top-pick cards."""
    if results.empty:
        return pd.DataFrame()
    ranked = results.copy()
    if "Setup Quality Grade" not in ranked:
        ranked["Setup Quality Grade"] = "C"
    if "Why Selected" not in ranked:
        ranked["Why Selected"] = "Run a fresh scan for upgraded setup-quality explanations"
    if "volume contraction" not in ranked:
        ranked["volume contraction"] = "No"
    if "Explosive Score" not in ranked:
        ranked["Explosive Score"] = 0
    if "Explosive Label" not in ranked:
        ranked["Explosive Label"] = "LOW MOMENTUM"
    if "TP Quality Score" not in ranked:
        ranked["TP Quality Score"] = 0
    if "Ideal TP R" not in ranked:
        ranked["Ideal TP R"] = 0
    if "Breakout Quality Score" not in ranked:
        ranked["Breakout Quality Score"] = 0
    if "Adjusted Final Score" not in ranked:
        ranked["Adjusted Final Score"] = ranked.get("Final Score", 0)
    if "Professional Score" not in ranked:
        ranked["Professional Score"] = ranked.get("Adjusted Final Score", ranked.get("Final Score", 0))
    if "Entry Quality Score" not in ranked:
        ranked["Entry Quality Score"] = 0
    if "Trade Tier" not in ranked:
        ranked["Trade Tier"] = "Tier 4 - Avoid / Reject"
    if "Institutional Quality Score" not in ranked:
        ranked["Institutional Quality Score"] = 0
    if "Leader Quality Label" not in ranked:
        ranked["Leader Quality Label"] = "LAGGARD / AVOID"
    if "RVOL" not in ranked:
        ranked["RVOL"] = 0
    if "WATCHLIST FLAG" not in ranked:
        ranked["WATCHLIST FLAG"] = "NO"
    if "Institutional Tightness Score" not in ranked:
        ranked["Institutional Tightness Score"] = 0
    if "Healthy Pullback Score" not in ranked:
        ranked["Healthy Pullback Score"] = 0
    if "Sector Leadership Status" not in ranked:
        ranked["Sector Leadership Status"] = "NEUTRAL SECTOR"
    ranked["RS Sort"] = pd.to_numeric(ranked.get("RS Score Raw", ranked.get("RS Score")), errors="coerce")
    ranked["RVOL Sort"] = pd.to_numeric(ranked.get("RVOL"), errors="coerce").fillna(0)
    setup_priority = {"A+": 0, "A": 1, "B": 2, "C": 3, "Reject": 4}
    breakout_priority = {
        "CONFIRMED BREAKOUT": 0,
        "NEAR BREAKOUT": 1,
        "BREAKOUT IN PROGRESS": 2,
        "NO BREAKOUT": 3,
    }
    vcp_mask = ranked["VCP Status"].isin(["VALID VCP", "EARLY VCP"])
    strong_pullback_mask = (ranked["Action Label"] == "PULLBACK ENTRY") & (ranked["RS Sort"] >= 6)
    momentum_mask = ranked.get("Setup Type", pd.Series("", index=ranked.index)) == "MOMENTUM BREAKOUT EXCEPTION"
    sector_mask = (ranked["Sector Leadership"] == "Leader") | (ranked["Sector Score"] >= 3)
    candidate_mask = (
        (vcp_mask | strong_pullback_mask | momentum_mask)
        & (ranked["RS Sort"] >= 6)
        & sector_mask
        & (ranked["Trade"] == "YES")
        & (ranked["Risk %"] <= 10)
        & (ranked["volume contraction"] == "Yes")
        & (ranked["Setup Quality Grade"].isin(["A+", "A"]))
        & (ranked["Explosive Score"] >= 7)
        & (ranked["Breakout Quality Score"] >= 7)
        & (ranked["TP Quality Score"] >= 7)
        & (ranked["Ideal TP R"] >= 1.8)
        & (ranked["Earnings Risk"] != "HIGH RISK")
    )
    ranked = ranked[candidate_mask].copy()
    if ranked.empty:
        return ranked
    ranked["trade sort"] = np.where(ranked["Trade"] == "YES", 0, 1)
    ranked["tier sort"] = ranked["Trade Tier"].map(TRADE_TIER_PRIORITY).fillna(9)
    ranked["signal sort"] = ranked["Signal State"].map(SIGNAL_STATE_PRIORITY).fillna(9)
    ranked["watchlist sort"] = np.where(ranked["WATCHLIST FLAG"] == "YES", 0, 1)
    ranked["quality sort"] = ranked["Setup Quality Grade"].map(setup_priority).fillna(9)
    ranked["vcp sort"] = np.where(ranked["VCP Status"].isin(["VALID VCP", "EARLY VCP"]), 0, 1)
    ranked["breakout sort"] = ranked["Breakout Alert"].map(breakout_priority).fillna(9)
    ranked["earnings sort"] = np.where(ranked["Earnings Risk"] == "HIGH RISK", 1, 0)
    ranked["sector status sort"] = ranked["Sector Leadership Status"].map(
        {"LEADING SECTOR": 0, "IMPROVING SECTOR": 1, "NEUTRAL SECTOR": 2, "CYCLICAL RISK": 3, "LAGGING SECTOR": 4}
    ).fillna(3)
    ranked["execution quality sort"] = (
        pd.to_numeric(ranked.get("Entry Quality Score"), errors="coerce").fillna(0)
        + pd.to_numeric(ranked.get("Institutional Tightness Score"), errors="coerce").fillna(0)
        + pd.to_numeric(ranked.get("Healthy Pullback Score"), errors="coerce").fillna(0)
        + pd.to_numeric(ranked.get("Breakout Quality Score"), errors="coerce").fillna(0)
        - (pd.to_numeric(ranked.get("MA10 Distance %"), errors="coerce").fillna(0).clip(lower=0) / 3)
    )
    ranked = ranked.sort_values(
        [
            "tier sort",
            "signal sort",
            "quality sort",
            "trade sort",
            "vcp sort",
            "breakout sort",
            "Professional Score",
            "Entry Quality Score",
            "Adjusted Final Score",
            "Institutional Quality Score",
            "sector status sort",
            "execution quality sort",
            "Institutional Tightness Score",
            "Healthy Pullback Score",
            "Breakout Quality Score",
            "RVOL Sort",
            "Explosive Score",
            "TP Quality Score",
            "Ideal TP R",
            "RS Sort",
            "Tightness Score",
            "Risk %",
            "Final Score",
            "earnings sort",
        ],
        ascending=[True, True, True, True, True, True, False, False, False, False, True, False, False, False, False, False, False, False, False, False, False, True, False, True],
    )
    return ranked.head(5)


def normalize_uploaded_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize uploaded CSV/export headers while preserving readable columns."""
    normalized = frame.copy()
    normalized.columns = [str(column).strip() for column in normalized.columns]
    return normalized


def scanner_frame_to_history(frame: pd.DataFrame, scanner_type: str) -> pd.DataFrame:
    """Convert a scanner result table into the compact trade history archive schema."""
    if frame.empty:
        return pd.DataFrame(columns=TRADE_HISTORY_COLUMNS)
    archived = pd.DataFrame(index=frame.index)
    now = datetime.now(ZoneInfo("Asia/Singapore"))
    archived["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S %Z")
    archived["scan date"] = now.strftime("%Y-%m-%d")
    archived["scanner type"] = scanner_type
    for source, target in SCANNER_TO_HISTORY_COLUMNS.items():
        archived[target] = frame[source] if source in frame.columns else "N/A"
    return archived[TRADE_HISTORY_COLUMNS]


def append_trade_signal_history(frame: pd.DataFrame, scanner_type: str) -> None:
    """Append every completed scanner run to trade_signals_history.csv."""
    archive_rows = scanner_frame_to_history(frame, scanner_type)
    if archive_rows.empty:
        return
    try:
        existing = pd.read_csv(TRADE_HISTORY_FILE) if pd.io.common.file_exists(TRADE_HISTORY_FILE) else pd.DataFrame()
        combined = pd.concat([existing, archive_rows], ignore_index=True)
        combined.to_csv(TRADE_HISTORY_FILE, index=False)
    except Exception:
        pass


def load_trade_signal_history() -> pd.DataFrame:
    """Load saved trade-signal history if available."""
    try:
        if pd.io.common.file_exists(TRADE_HISTORY_FILE):
            return pd.read_csv(TRADE_HISTORY_FILE)
    except Exception:
        pass
    return pd.DataFrame(columns=TRADE_HISTORY_COLUMNS)


def parse_uploaded_scanner_export(uploaded_file) -> pd.DataFrame:
    """Read scanner CSV exports, and best-effort parse the app's simple PDF export."""
    if uploaded_file is None:
        return pd.DataFrame()
    name = uploaded_file.name.lower()
    try:
        if name.endswith(".csv"):
            return normalize_uploaded_columns(pd.read_csv(uploaded_file))
        if name.endswith(".pdf"):
            text = uploaded_file.getvalue().decode("latin-1", errors="ignore")
            lines = [line.replace("\\(", "(").replace("\\)", ")") for line in re.findall(r"\((.*?)\) Tj", text)]
            table_lines = [line for line in lines if "|" in line]
            if len(table_lines) < 2:
                return pd.DataFrame()
            header = [part.strip() for part in table_lines[0].split("|")]
            rows = []
            for line in table_lines[1:]:
                parts = [part.strip() for part in line.split("|")]
                if len(parts) == len(header):
                    rows.append(dict(zip(header, parts)))
            return normalize_uploaded_columns(pd.DataFrame(rows))
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def normalize_positions_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Accept simple manual position CSV fields and normalize for analysis."""
    if frame.empty:
        return pd.DataFrame()
    normalized = frame.copy()
    normalized.columns = [str(column).strip().lower().replace(" ", "_") for column in normalized.columns]
    aliases = {
        "symbol": "ticker",
        "entry": "entry_price",
        "shares": "position_size",
        "qty": "position_size",
        "quantity": "position_size",
        "date": "entry_date",
        "commission": "fees",
        "fee": "fees",
    }
    normalized = normalized.rename(columns={key: value for key, value in aliases.items() if key in normalized.columns})
    for column in [
        "position_id",
        "ticker",
        "entry_date",
        "entry_price",
        "position_size",
        "notes",
        "broker",
        "account",
        "fees",
        "current_stop_loss_override",
        "manual_tp_override",
    ]:
        if column not in normalized.columns:
            normalized[column] = "" if column in {"position_id", "ticker", "entry_date", "notes", "broker", "account"} else np.nan
    normalized["ticker"] = normalized["ticker"].astype(str).str.upper().str.strip()
    normalized["entry_date"] = pd.to_datetime(normalized["entry_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ["entry_price", "position_size", "fees", "current_stop_loss_override", "manual_tp_override"]:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    normalized = normalized.dropna(subset=["ticker", "entry_price", "position_size"])
    normalized = normalized[normalized["ticker"].astype(str).str.len() > 0]
    return normalized


def load_positions_file() -> pd.DataFrame:
    """Load persisted positions, tolerating missing or older files."""
    try:
        if pd.io.common.file_exists(POSITIONS_FILE):
            loaded = pd.read_csv(POSITIONS_FILE)
            for column in POSITION_STORAGE_COLUMNS:
                if column not in loaded.columns:
                    loaded[column] = "" if column not in {"entry_price", "position_size", "fees", "current_stop_loss_override", "manual_tp_override"} else np.nan
            return loaded[POSITION_STORAGE_COLUMNS]
    except Exception:
        pass
    return pd.DataFrame(columns=POSITION_STORAGE_COLUMNS)


def save_positions_file(frame: pd.DataFrame) -> None:
    """Persist positions to positions.csv without crashing the app."""
    try:
        saved = frame.copy()
        for column in POSITION_STORAGE_COLUMNS:
            if column not in saved.columns:
                saved[column] = "" if column not in {"entry_price", "position_size", "fees", "current_stop_loss_override", "manual_tp_override"} else np.nan
        saved[POSITION_STORAGE_COLUMNS].to_csv(POSITIONS_FILE, index=False)
    except Exception:
        pass


def position_duplicate_exists(frame: pd.DataFrame, ticker: str, entry_date: str, entry_price: float) -> bool:
    """Detect duplicate position by ticker + entry date + entry price."""
    if frame.empty:
        return False
    dates = pd.to_datetime(frame.get("entry_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    prices = pd.to_numeric(frame.get("entry_price"), errors="coerce").round(4)
    return bool(
        (
            (frame.get("ticker", "").astype(str).str.upper() == str(ticker).upper())
            & (dates == pd.to_datetime(entry_date, errors="coerce").strftime("%Y-%m-%d"))
            & (prices == round(float(entry_price), 4))
        ).any()
    )


def build_position_record(
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    position_size: float,
    fees: float = 0.0,
    broker: str = "",
    account: str = "",
    notes: str = "",
    stop_override: float = np.nan,
    tp_override: float = np.nan,
    history: pd.DataFrame | None = None,
    uploaded_export: pd.DataFrame | None = None,
    current_fallback: pd.DataFrame | None = None,
) -> dict:
    """Create a persisted position row and snapshot the original thesis at save time."""
    now = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S %Z")
    thesis, thesis_source = match_original_thesis(
        ticker,
        entry_date,
        history if history is not None else pd.DataFrame(),
        uploaded_export if uploaded_export is not None else pd.DataFrame(),
        current_fallback if current_fallback is not None else pd.DataFrame(),
    )
    parsed_entry_date = pd.to_datetime(entry_date, errors="coerce")
    safe_entry_date = parsed_entry_date.strftime("%Y-%m-%d") if pd.notna(parsed_entry_date) else datetime.now().strftime("%Y-%m-%d")
    position_id = f"{str(ticker).upper()}-{safe_entry_date.replace('-', '')}-{round(float(entry_price), 4)}-{int(time.time())}"
    return {
        "position_id": position_id,
        "ticker": str(ticker).upper().strip(),
        "entry_date": safe_entry_date,
        "entry_price": float(entry_price),
        "position_size": float(position_size),
        "fees": float(fees) if pd.notna(fees) else 0.0,
        "broker": broker,
        "account": account,
        "original_thesis_source": thesis_source,
        "original_signal_state": thesis.get("signal state", "N/A"),
        "original_setup_type": thesis.get("setup type", "N/A"),
        "original_trade_tier": thesis.get("trade tier", "N/A"),
        "original_professional_score": thesis.get("professional score", "N/A"),
        "original_entry_trigger": thesis.get("entry trigger", "N/A"),
        "original_stop_loss": thesis.get("stop loss", np.nan),
        "original_tp1": thesis.get("TP1", "N/A"),
        "original_tp2": thesis.get("TP2", "N/A"),
        "original_tp3": thesis.get("TP3", "N/A"),
        "original_ideal_tp": thesis.get("ideal TP", "N/A"),
        "original_decision_reason": thesis.get("decision reason", "N/A"),
        "notes": notes,
        "created_at": now,
        "updated_at": now,
        "current_stop_loss_override": stop_override if pd.notna(stop_override) and float(stop_override) > 0 else np.nan,
        "manual_tp_override": tp_override if pd.notna(tp_override) and float(tp_override) > 0 else np.nan,
    }


def thesis_from_saved_position(position: pd.Series) -> Tuple[pd.Series, str]:
    """Use saved original thesis snapshot as the first source for persisted positions."""
    source = position.get("original_thesis_source", "")
    if not source:
        return pd.Series(dtype=object), ""
    return pd.Series(
        {
            "signal state": position.get("original_signal_state", "N/A"),
            "setup type": position.get("original_setup_type", "N/A"),
            "trade tier": position.get("original_trade_tier", "N/A"),
            "professional score": position.get("original_professional_score", "N/A"),
            "entry trigger": position.get("original_entry_trigger", "N/A"),
            "stop loss": position.get("original_stop_loss", np.nan),
            "TP1": position.get("original_tp1", "N/A"),
            "TP2": position.get("original_tp2", "N/A"),
            "TP3": position.get("original_tp3", "N/A"),
            "ideal TP": position.get("original_ideal_tp", "N/A"),
            "decision reason": position.get("original_decision_reason", "N/A"),
        }
    ), str(source)


def extract_futu_screenshot_details(uploaded_file) -> Tuple[dict, str]:
    """Best-effort OCR extraction for broker screenshots; always safe to fail."""
    details = {"ticker": "", "stock_name": "", "direction": "", "quantity": np.nan, "price": np.nan, "amount": np.nan, "trade_date": "", "trade_time": "", "fees": np.nan}
    try:
        from PIL import Image
        import pytesseract

        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        text = pytesseract.image_to_string(image)
        upper = text.upper()
        ticker_match = re.search(r"\b[A-Z]{1,5}(?:\.[A-Z]{1,3})?\b", upper)
        if ticker_match:
            details["ticker"] = ticker_match.group(0)
        direction_match = re.search(r"\b(BUY|SELL|BOUGHT|SOLD)\b", upper)
        if direction_match:
            details["direction"] = direction_match.group(0)
        numbers = [float(value.replace(",", "")) for value in re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?", text)]
        if numbers:
            details["price"] = numbers[0]
        if len(numbers) > 1:
            details["quantity"] = numbers[1]
        if len(numbers) > 2:
            details["amount"] = numbers[2]
        date_match = re.search(r"(20\d{2}[-/]\d{1,2}[-/]\d{1,2})", text)
        if date_match:
            details["trade_date"] = pd.to_datetime(date_match.group(1), errors="coerce").strftime("%Y-%m-%d")
        time_match = re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text)
        if time_match:
            details["trade_time"] = time_match.group(0)
        return details, "OCR attempted. Please confirm the extracted position details manually."
    except Exception:
        return details, "Screenshot uploaded. Please confirm position details manually."


def detect_uploaded_file_type(uploaded_file) -> Tuple[str, str, pd.DataFrame, dict]:
    """Classify unified My Positions uploads into scanner export, position CSV, or screenshot."""
    name = uploaded_file.name
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if extension == "csv":
        try:
            frame = normalize_uploaded_columns(pd.read_csv(uploaded_file))
            lowered = {str(column).strip().lower().replace(" ", "_") for column in frame.columns}
            position_cols = {"ticker", "entry_date", "entry_price", "position_size"}
            scanner_markers = {"signal_state", "setup_type", "entry_trigger", "stop_loss", "professional_score", "trade_tier"}
            if position_cols.issubset(lowered):
                return "Position CSV", "loaded", frame, {}
            if "ticker" in lowered and len(scanner_markers.intersection(lowered)) >= 3:
                return "Scanner Export CSV", "loaded", frame, {}
            return "Unsupported / unreadable", "failed: CSV columns not recognized. Required position columns: ticker, entry_date, entry_price, position_size.", frame, {}
        except Exception as exc:
            return "Unsupported / unreadable", f"failed: {exc}", pd.DataFrame(), {}
    if extension == "pdf":
        frame = parse_uploaded_scanner_export(uploaded_file)
        if frame.empty:
            return "Scanner Export PDF", "failed: PDF could not be parsed", pd.DataFrame(), {}
        return "Scanner Export PDF", "loaded", frame, {}
    if extension in {"png", "jpg", "jpeg", "webp"}:
        extracted, status = extract_futu_screenshot_details(uploaded_file)
        return "Futu Screenshot", "needs confirmation", pd.DataFrame(), {"extracted": extracted, "status": status, "file": uploaded_file}
    return "Unsupported / unreadable", "failed: unsupported file type", pd.DataFrame(), {}


def history_like_from_scanner_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Convert uploaded scanner CSV/PDF rows to history-like lower-case fields."""
    if frame.empty:
        return pd.DataFrame(columns=TRADE_HISTORY_COLUMNS)
    converted = pd.DataFrame(index=frame.index)
    converted["timestamp"] = "Uploaded export"
    converted["scan date"] = pd.Timestamp.today().strftime("%Y-%m-%d")
    converted["scanner type"] = "Uploaded Scanner Export"
    for source, target in SCANNER_TO_HISTORY_COLUMNS.items():
        converted[target] = frame[source] if source in frame.columns else frame.get(target, "N/A")
    return converted[TRADE_HISTORY_COLUMNS]


def match_original_thesis(
    ticker: str,
    entry_date: str,
    history: pd.DataFrame,
    uploaded_export: pd.DataFrame,
    current_fallback: pd.DataFrame,
) -> Tuple[pd.Series, str]:
    """Find the closest available original thesis for a position."""
    symbol = str(ticker).upper()
    entry_dt = pd.to_datetime(entry_date, errors="coerce")

    def closest(frame: pd.DataFrame, source: str) -> Tuple[pd.Series, str] | None:
        if frame.empty or "ticker" not in frame.columns:
            return None
        matches = frame[frame["ticker"].astype(str).str.upper() == symbol].copy()
        if matches.empty:
            return None
        if "scan date" in matches.columns and pd.notna(entry_dt):
            scan_dates = pd.to_datetime(matches["scan date"], errors="coerce")
            matches["_date_before_or_same"] = scan_dates <= entry_dt
            matches["_date_diff"] = (scan_dates - entry_dt).abs()
            matches = matches.sort_values(["_date_before_or_same", "_date_diff"], ascending=[False, True], na_position="last")
        return matches.iloc[0], source

    for frame, source in [
        (history, "Trade History Archive"),
        (uploaded_export, "Uploaded Scanner Export"),
        (scanner_frame_to_history(current_fallback, "Current Scanner Fallback"), "Current Scanner Fallback"),
    ]:
        result = closest(frame, source)
        if result is not None:
            return result
    return pd.Series(dtype=object), "Manual Entry"


def calculate_position_management_row(position: pd.Series, thesis: pd.Series, thesis_source: str, data: pd.DataFrame | None, quote: dict | None = None) -> dict:
    """Calculate daily active-position management fields from daily OHLCV."""
    ticker = str(position.get("ticker", "")).upper()
    entry_price = float(position.get("entry_price", np.nan))
    position_size = float(position.get("position_size", np.nan))
    entry_date = str(position.get("entry_date", ""))
    latest = data.iloc[-1] if data is not None and not data.empty else pd.Series(dtype=object)
    since_entry = data[data.index >= pd.to_datetime(entry_date, errors="coerce")] if data is not None and not data.empty else pd.DataFrame()
    if since_entry.empty and data is not None:
        since_entry = data.tail(1)

    current_price = float(latest.get("Close", entry_price)) if pd.notna(latest.get("Close", np.nan)) else entry_price
    original_stop = numeric_or_na(position.get("current_stop_loss_override"))
    if pd.isna(original_stop):
        original_stop = numeric_or_na(thesis.get("stop loss"))
    if pd.isna(original_stop) or original_stop <= 0:
        original_stop = entry_price * 0.92
    risk_per_share = max(entry_price - float(original_stop), 0.01)
    gain_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else np.nan
    fees = numeric_or_na(position.get("fees", position.get("commission")))
    unrealized_pl = (current_price - entry_price) * position_size - (fees if pd.notna(fees) else 0)
    current_r = (current_price - entry_price) / risk_per_share
    days_held = (pd.Timestamp.today().normalize() - pd.to_datetime(entry_date, errors="coerce")).days if pd.notna(pd.to_datetime(entry_date, errors="coerce")) else np.nan
    ma10 = numeric_or_na(latest.get("MA10"))
    ma20 = numeric_or_na(latest.get("MA20"))
    ma50 = numeric_or_na(latest.get("MA50"))
    rsi = numeric_or_na(latest.get("RSI14"))
    avg_vol20 = numeric_or_na(latest.get("AvgVol20"))
    vol_ratio = float(latest.get("Volume", np.nan)) / avg_vol20 if pd.notna(avg_vol20) and avg_vol20 > 0 else np.nan
    highest_since_entry = float(since_entry["High"].max()) if not since_entry.empty and "High" in since_entry else current_price
    lowest_since_entry = float(since_entry["Low"].min()) if not since_entry.empty and "Low" in since_entry else current_price
    pullback_from_high = (current_price / highest_since_entry - 1) * 100 if highest_since_entry > 0 else np.nan
    prior_day_low = float(data["Low"].iloc[-2]) if data is not None and len(data) >= 2 else current_price
    two_day_low = float(data["Low"].tail(2).min()) if data is not None and len(data) >= 2 else prior_day_low
    heavy_down = bool(pd.notna(vol_ratio) and vol_ratio >= 1.3 and current_price < float(latest.get("Open", current_price)))
    below_ma10 = pd.notna(ma10) and current_price < ma10
    below_ma20 = pd.notna(ma20) and current_price < ma20
    distance_ma10 = (current_price / ma10 - 1) * 100 if pd.notna(ma10) and ma10 > 0 else np.nan
    distance_ma20 = (current_price / ma20 - 1) * 100 if pd.notna(ma20) and ma20 > 0 else np.nan
    pivot = numeric_or_na(thesis.get("pivot"))

    if current_price <= original_stop or (below_ma20 and heavy_down) or (pd.notna(pivot) and current_price < pivot and current_price < entry_price):
        thesis_status = "FAILED"
    elif below_ma10 and heavy_down:
        thesis_status = "WEAKENING"
    elif below_ma10:
        thesis_status = "NEEDS CONFIRMATION"
    elif current_price > entry_price and (pd.isna(ma10) or current_price >= ma10) and (pd.isna(ma20) or current_price >= ma20):
        thesis_status = "PLAYING OUT" if current_r >= 0.8 else "STILL VALID"
    else:
        thesis_status = "STILL VALID"

    suggested_stop = float(original_stop)
    suggested_action = "HOLD"
    if current_r >= 2:
        suggested_stop = max(suggested_stop, ma10 if pd.notna(ma10) else entry_price, two_day_low)
        suggested_action = "HOLD / TRAIL STOP"
    elif current_r >= 1.5:
        suggested_stop = max(suggested_stop, entry_price, prior_day_low)
        suggested_action = "MOVE STOP UP"
    elif current_r >= 1:
        suggested_stop = max(suggested_stop, entry_price, ma10 if pd.notna(ma10) else entry_price)
        suggested_action = "MOVE STOP UP"
    if pd.notna(distance_ma10) and distance_ma10 > 12:
        suggested_stop = max(suggested_stop, two_day_low, prior_day_low)
        suggested_action = "TAKE PARTIAL" if current_r >= 1 else "HOLD / TRAIL STOP"
    if below_ma10 and heavy_down:
        suggested_action = "REDUCE"
    if thesis_status == "FAILED":
        suggested_action = "EXIT"
        suggested_stop = current_price
    if thesis_status == "STILL VALID" and pd.notna(vol_ratio) and vol_ratio < 1 and (below_ma10 or abs(distance_ma10) <= 3 if pd.notna(distance_ma10) else False):
        suggested_action = "ADD ON WATCH"

    original_tp1 = numeric_or_na(thesis.get("TP1"))
    original_tp2 = numeric_or_na(thesis.get("TP2"))
    original_tp3 = numeric_or_na(thesis.get("TP3"))
    manual_tp = numeric_or_na(position.get("manual_tp_override"))
    updated_tp1 = max(original_tp1 if pd.notna(original_tp1) else entry_price + 1.5 * risk_per_share, current_price) if current_r >= 1 else (original_tp1 if pd.notna(original_tp1) else entry_price + 1.5 * risk_per_share)
    updated_tp2 = max(original_tp2 if pd.notna(original_tp2) else entry_price + 2.5 * risk_per_share, updated_tp1 + 0.5 * risk_per_share)
    updated_tp3 = max(original_tp3 if pd.notna(original_tp3) else entry_price + 3 * risk_per_share, highest_since_entry * 1.03, updated_tp2 + 0.5 * risk_per_share)
    updated_ideal = manual_tp if pd.notna(manual_tp) and manual_tp > current_price else updated_tp2
    if current_price >= updated_tp3:
        tp_status = "TRAIL RUNNER"
        suggested_action = "HOLD / TRAIL STOP"
    elif current_price >= updated_tp2:
        tp_status = "TP2 HIT"
        suggested_action = "TAKE PARTIAL" if suggested_action not in {"EXIT", "REDUCE"} else suggested_action
    elif current_price >= updated_tp1:
        tp_status = "TP1 HIT"
        suggested_action = "TAKE PARTIAL" if suggested_action not in {"EXIT", "REDUCE"} else suggested_action
    else:
        tp_status = "NOT HIT"

    if thesis_source == "Manual Entry":
        explanation = "Original thesis unavailable. This analysis uses manual entry and current daily data only."
    elif thesis_status == "FAILED":
        explanation = "Original thesis failed. Price broke stop / MA20 with volume."
    elif tp_status in {"TP1 HIT", "TP2 HIT"}:
        explanation = f"Stock reached {tp_status.replace(' HIT', '')}. Consider partial profit and move stop up."
    elif thesis_status == "PLAYING OUT":
        explanation = "Original breakout thesis is working. Price is above entry and holding MA10/MA20. Continue to trail stop."
    elif thesis_status == "NEEDS CONFIRMATION":
        explanation = "Original thesis still valid but momentum is cooling. Wait for rebound or reduce if MA10 breaks."
    else:
        explanation = "Original thesis still valid. Manage as an existing position, not a new entry."
    if thesis_source == "Current Scanner Fallback":
        explanation = f"Original thesis unavailable. This analysis uses current scanner fallback only. {explanation}"

    quote = quote or {}
    premarket_price = numeric_or_na(quote.get("premarket_price"))
    afterhours_price = numeric_or_na(quote.get("afterhours_price"))
    external_price = afterhours_price if pd.notna(afterhours_price) else premarket_price
    external_label = "After-hours" if pd.notna(afterhours_price) else "Pre-market" if pd.notna(premarket_price) else "N/A"
    external_move_pct = (external_price / current_price - 1) * 100 if pd.notna(external_price) and current_price > 0 else np.nan
    alert_status = "NORMAL"
    alert_reason = "After-hours data unavailable."
    if pd.notna(external_move_pct):
        alert_reason = f"{external_label} move {external_move_pct:.2f}%."
        if abs(external_move_pct) >= 3:
            alert_status = "WARNING"
        if external_price <= suggested_stop or (pd.notna(ma10) and external_price < ma10):
            alert_status = "ACTION NEEDED"
            alert_reason = f"{external_label} price is below stop/MA10."
        elif external_price >= updated_tp2:
            alert_status = "WATCH"
            alert_reason = f"{external_label} price is above TP2."
        elif external_price >= updated_tp1:
            alert_status = "WATCH"
            alert_reason = f"{external_label} price is above TP1."
        elif pd.notna(pivot) and external_price < pivot:
            alert_status = "WARNING"
            alert_reason = f"{external_label} price is below pivot."

    return {
        "ticker": ticker,
        "entry date": entry_date,
        "entry price": round(entry_price, 2),
        "position size": position_size,
        "current price": round(current_price, 2),
        "gain %": round(gain_pct, 2) if pd.notna(gain_pct) else np.nan,
        "unrealized P/L": round(unrealized_pl, 2),
        "current R multiple": round(current_r, 2),
        "days held": days_held,
        "distance from MA10": round(distance_ma10, 2) if pd.notna(distance_ma10) else np.nan,
        "distance from MA20": round(distance_ma20, 2) if pd.notna(distance_ma20) else np.nan,
        "current RSI": round(rsi, 1) if pd.notna(rsi) else np.nan,
        "current volume vs 20-day average": round(vol_ratio, 2) if pd.notna(vol_ratio) else np.nan,
        "highest price since entry": round(highest_since_entry, 2),
        "lowest price since entry": round(lowest_since_entry, 2),
        "pullback from high %": round(pullback_from_high, 2) if pd.notna(pullback_from_high) else np.nan,
        "original thesis source": thesis_source,
        "original signal": thesis.get("signal state", "N/A"),
        "original setup type": thesis.get("setup type", "N/A"),
        "original trade tier": thesis.get("trade tier", "N/A"),
        "original professional score": thesis.get("professional score", "N/A"),
        "original entry trigger": thesis.get("entry trigger", "N/A"),
        "original stop loss": round(float(original_stop), 2),
        "original TP1": thesis.get("TP1", "N/A"),
        "original TP2": thesis.get("TP2", "N/A"),
        "original TP3": thesis.get("TP3", "N/A"),
        "original ideal TP": thesis.get("ideal TP", "N/A"),
        "original TP type": thesis.get("TP type", "N/A"),
        "original decision reason": thesis.get("decision reason", "N/A"),
        "thesis status": thesis_status,
        "suggested stop loss today": round(float(suggested_stop), 2),
        "updated TP1": round(float(updated_tp1), 2),
        "updated TP2": round(float(updated_tp2), 2),
        "updated TP3": round(float(updated_tp3), 2),
        "updated ideal TP": round(float(updated_ideal), 2),
        "TP status": tp_status,
        "suggested action": suggested_action,
        "after-hours / pre-market price": round(float(external_price), 2) if pd.notna(external_price) else "N/A",
        "after-hours / pre-market move %": round(float(external_move_pct), 2) if pd.notna(external_move_pct) else "N/A",
        "after-hours alert": alert_status,
        "after-hours alert reason": alert_reason,
        "original thesis vs current action": explanation,
        "notes": position.get("notes", ""),
        "_data": data,
        "_ma10": ma10,
        "_ma20": ma20,
        "_ma50": ma50,
    }


def alert_message(row: pd.Series) -> str:
    """Build the requested alert message format."""
    return (
        f"Ticker: {row.get('ticker', 'N/A')}\n"
        f"Sector / Industry: {row.get('Sector / Industry', 'N/A')}\n"
        f"Action: {row.get('Action Label', 'N/A')}\n"
        f"Signal State: {row.get('Signal State', 'N/A')}\n"
        f"Setup Type: {row.get('Setup Type', 'N/A')}\n"
        f"Entry Type: {row.get('Entry Type', 'N/A')}\n"
        f"Live Breakout Status: {row.get('Live Breakout Status', 'N/A')}\n"
        f"RVOL: {row.get('RVOL', 'N/A')}\n"
        f"Breakout Quality Score: {row.get('Breakout Quality Score', 'N/A')}\n"
        f"Market Environment: {row.get('Market Environment', 'N/A')}\n"
        f"VCP Status: {row.get('VCP Status', 'N/A')}\n"
        f"Decision Reason: {row.get('Decision Reason', 'N/A')}\n"
        f"Final Score: {row.get('Final Score', 'N/A')}\n"
        f"Pivot: {row.get('Pivot', 'N/A')}\n"
        f"Entry Trigger: {row.get('Entry Trigger', 'N/A')}\n"
        f"Stop Loss: {row.get('Stop Loss', 'N/A')}\n"
        f"Risk %: {row.get('Risk %', 'N/A')}\n"
        f"Target 1R: {row.get('Target 1R', 'N/A')}\n"
        f"Target 2R: {row.get('Target 2R', 'N/A')}\n"
        f"Target 3R: {row.get('Target 3R', 'N/A')}\n"
        f"Ideal TP: {row.get('Ideal TP', 'N/A')}\n"
        f"Ideal TP Reason: {row.get('Ideal TP Reason', 'N/A')}\n"
        f"Sell Strategy: {row.get('Sell Strategy', 'N/A')}\n"
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
        ("1R", row.get("Target 1R", np.nan), "#22c55e"),
        ("2R", row["Target 2R"], "#16a34a"),
        ("3R", row["Target 3R"], "#15803d"),
        ("Resistance", row.get("Nearest Resistance", np.nan), "#9333ea"),
        ("Resistance BO", row.get("Breakout Above Resistance Trigger", np.nan), "#7c3aed"),
        ("Ideal TP", row.get("Ideal TP", np.nan), "#0f766e"),
        ("Trail", row.get("Trail Stop Level", np.nan), "#ea580c"),
    ]
    for label, value, color in level_specs:
        if pd.notna(value):
            figure.add_hline(y=value, line_dash="dash", line_color=color, annotation_text=label)
    resistance = row.get("Nearest Resistance", np.nan)
    if pd.notna(resistance):
        figure.add_hrect(
            y0=float(resistance) * 0.995,
            y1=float(resistance) * 1.005,
            fillcolor="#9333ea",
            opacity=0.08,
            line_width=0,
            annotation_text="Resistance zone",
            annotation_position="top left",
        )

    earnings_date = row.get("Earnings Date", "N/A")
    if earnings_date != "N/A":
        parsed_earnings = pd.to_datetime(earnings_date, errors="coerce")
        if pd.notna(parsed_earnings) and chart_data.index.min() <= parsed_earnings <= chart_data.index.max():
            figure.add_vline(
                x=parsed_earnings,
                line_dash="dot",
                line_color="#be123c",
                annotation_text="Earnings",
            )

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
    live_mode: bool = False,
    include_earnings: bool = False,
    fetch_market_caps: bool = False,
    use_live_sector_metadata: bool = False,
    max_tickers: int = 50,
    aggressive_mode: bool = False,
) -> Tuple[pd.DataFrame, Dict[str, pd.DataFrame], dict]:
    """Download, filter, score, and return scanner results."""
    tickers = tickers[:max_tickers]
    session_status, market_timestamp, local_timestamp = market_session_status()
    force_token = datetime.now(ZoneInfo("America/New_York")).isoformat()
    is_hk_scan = any(ticker.endswith(".HK") for ticker in tickers) or "HK" in mode
    context_tickers = ALL_CONTEXT_TICKERS if is_hk_scan else MARKET_TICKERS
    all_tickers = tuple(sorted(set(tickers + context_tickers)))
    raw_data = download_daily_data(all_tickers, period="1y", force_token=force_token)
    quote_data = download_live_quotes(all_tickers) if live_mode else {}
    quote_applied: Dict[str, bool] = {}
    synchronized_raw: Dict[str, pd.DataFrame] = {}
    for symbol, frame in raw_data.items():
        synchronized, applied = synchronize_frame_with_quote(frame, quote_data.get(symbol, {}), session_status)
        synchronized_raw[symbol] = synchronized
        quote_applied[symbol] = applied
    raw_data = synchronized_raw

    us_benchmark_raw = first_valid_frame(raw_data.get("SPY"))
    hk_benchmark_raw = first_valid_frame(raw_data.get("^HSI"), raw_data.get("2800.HK"))
    indicator_data = {
        ticker: add_indicators(frame, hk_benchmark_raw if ticker.endswith(".HK") else us_benchmark_raw)
        for ticker, frame in raw_data.items()
    }
    market_data = {ticker: indicator_data[ticker] for ticker in context_tickers if ticker in indicator_data}
    if is_hk_scan and mode == "HK Pro Market Scan":
        market_score, market_status, market_details = calculate_hk_market_score(market_data)
    else:
        market_score, market_status, market_details = calculate_market_score(market_data)
    market_environment = calculate_market_environment(market_data, is_hk_scan=is_hk_scan and mode == "HK Pro Market Scan")
    sector_score, sector_details = calculate_sector_score(mode, market_data)
    market_caps = download_market_caps(tuple(tickers)) if fetch_market_caps else {ticker: None for ticker in tickers}
    earnings_data = download_earnings_data(tuple(tickers)) if include_earnings else {ticker: {} for ticker in tickers}
    scan_timestamps = {
        "market_timestamp": market_timestamp,
        "local_timestamp": local_timestamp,
        "session_status": session_status,
    }

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
            sector_info = fetch_sector_industry_one(ticker) if use_live_sector_metadata else fallback_sector_industry_one(ticker)
            rows.append(
                build_scan_row(
                    ticker=ticker,
                    data=data,
                    market_cap=market_cap,
                    earnings_info=earnings_data.get(ticker, {}),
                    sector_info=sector_info,
                    quote_info=quote_data.get(ticker, {}),
                    sync_info=quote_applied,
                    scan_timestamps=scan_timestamps,
                    market_score=market_score,
                    sector_score=sector_score,
                    benchmark_data=market_data,
                    sector_etf=sector_etf,
                    market_environment=market_environment.get("status", "UPTREND UNDER PRESSURE"),
                    live_mode=live_mode,
                    aggressive_mode=aggressive_mode,
                )
            )
        except Exception as exc:
            rejected.append(f"{ticker}: scoring failed ({exc})")

    progress.empty()
    results = pd.DataFrame(rows)
    summary = {
        "market_score": market_score,
        "market_status": market_status,
        "market_environment": market_environment.get("status", "UPTREND UNDER PRESSURE"),
        "market_environment_details": market_environment.get("details", ""),
        "distribution_days": market_environment.get("distribution_days", 0),
        "follow_through_day": market_environment.get("follow_through_day", False),
        "live_mode": live_mode,
        "scan_limit": max_tickers,
        "market_details": market_details,
        "market_timestamp": market_timestamp,
        "local_timestamp": local_timestamp,
        "session_status": session_status,
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

IPO_DATA = [
    {
        "ticker": "07666.HK",
        "company": "齊泰科技",
        "market": "HK",
        "status": "applying",
        "offer_price": "10.50",
        "lot_size": 500,
        "minimum_subscription_amount": 5302.95,
        "application_deadline": "2026-05-08",
        "listing_date": "2026-05-15",
        "industry": "AI / biotech platform",
        "sponsor": "N/A",
        "cornerstone_investors": "N/A",
        "oversubscription": "N/A",
        "grey_market_price": "N/A",
        "grey_market_premium": "N/A",
        "latest_news": "Manual fallback IPO row. Confirm official prospectus and broker data.",
        "source": "manual fallback",
    },
    {
        "ticker": "01236.HK",
        "company": "Ldrobot",
        "market": "HK",
        "status": "applying",
        "offer_price": "24-30",
        "lot_size": 200,
        "minimum_subscription_amount": 6060.51,
        "application_deadline": "2026-05-06",
        "listing_date": "2026-05-11",
        "industry": "AI / robotics / advanced hardware",
        "sponsor": "N/A",
        "cornerstone_investors": "N/A",
        "oversubscription": "N/A",
        "grey_market_price": "N/A",
        "grey_market_premium": "N/A",
        "latest_news": "Manual fallback IPO row. Confirm official prospectus and broker data.",
        "source": "manual fallback",
    },
    {
        "ticker": "USIPO1",
        "company": "Manual US IPO Watchlist",
        "market": "US",
        "status": "manual input",
        "offer_price": "N/A",
        "lot_size": "N/A",
        "minimum_subscription_amount": "N/A",
        "application_deadline": "N/A",
        "listing_date": "N/A",
        "industry": "Manual fallback",
        "sponsor": "N/A",
        "cornerstone_investors": "N/A",
        "oversubscription": "N/A",
        "grey_market_price": "N/A",
        "grey_market_premium": "N/A",
        "latest_news": "Use the manual override table to add a US IPO candidate.",
        "source": "manual fallback",
    },
]

MANUAL_IPO_INPUT_COLUMNS = [
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
    "industry / theme",
    "cornerstone investors",
    "oversubscription",
    "grey market price",
    "grey market premium %",
    "latest news summary",
    "source",
]


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


def ipo_trade_plan(entry, strength_label):
    """Create IPO stop and targets from grey-market strength."""
    entry_value = parse_price_midpoint(entry)
    if entry_value is None or entry_value <= 0:
        return None, None, None, None

    if strength_label == "HOT (SCALP)":
        sl = entry_value * 0.92
        tp1 = entry_value * 1.15
        tp2 = entry_value * 1.30
        tp3 = entry_value * 1.50
    elif strength_label == "STRONG":
        sl = entry_value * 0.93
        tp1 = entry_value * 1.12
        tp2 = entry_value * 1.25
        tp3 = entry_value * 1.40
    else:
        sl = entry_value * 0.95
        tp1 = entry_value * 1.08
        tp2 = entry_value * 1.15
        tp3 = entry_value * 1.25
    return round(sl, 2), round(tp1, 2), round(tp2, 2), round(tp3, 2)


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

    if premium_pct is not None and premium_pct >= 20:
        strength_label = "HOT (SCALP)"
    elif premium_pct is not None and premium_pct >= 10:
        strength_label = "STRONG"
    elif premium_pct is not None and premium_pct > 0:
        strength_label = "WEAK POSITIVE"
    elif premium_pct is not None:
        strength_label = "NEGATIVE RISK"
    else:
        _, strength_label = grey_market_assessment(grey_price, offer_price)
    stop_loss, tp1, tp2, tp3 = ipo_trade_plan(entry, strength_label)

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
        "stop loss": stop_loss,
        "TP1": tp1,
        "TP2": tp2,
        "TP3": tp3,
        "first day strategy": strategy,
    }


def simulated_grey_market_range(score: int, offer_price: float | None) -> Tuple[str, float | None]:
    """Estimate a grey-market range when no live grey price is available."""
    if score >= 80:
        low_pct, high_pct = 10, 30
    elif score >= 65:
        low_pct, high_pct = 0, 15
    elif score >= 50:
        low_pct, high_pct = -5, 8
    else:
        low_pct, high_pct = -15, 5

    if offer_price is None or offer_price <= 0:
        return f"{low_pct}% to +{high_pct}% (simulation, not live grey market)", None

    low_price = offer_price * (1 + low_pct / 100)
    high_price = offer_price * (1 + high_pct / 100)
    mid_price = (low_price + high_price) / 2
    low_text = f"{low_pct}%" if low_pct < 0 else f"+{low_pct}%"
    high_text = f"+{high_pct}%"
    return (
        f"{low_price:.2f}-{high_price:.2f} ({low_text} to {high_text}; simulation, not live grey market)",
        round(mid_price, 2),
    )


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
    premium = parse_first_number(record.get("grey market premium %"))
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
    simulated_range, simulated_open = simulated_grey_market_range(score, offer_price)
    expected_open_price = grey_price or parse_price_midpoint(record.get("expected open price")) or simulated_open or offer_price
    plan_premium = premium
    if plan_premium is None and expected_open_price and offer_price:
        plan_premium = (expected_open_price - offer_price) / offer_price * 100
    plan = ipo_first_day_plan(offer_price, expected_open_price, plan_premium)
    open_behavior = (
        open_decision(
            expected_open_price,
            offer_price,
            record.get("opening volume ratio", 0),
            record.get("first 5m high", "N/A"),
        )
        if expected_open_price is not None and offer_price is not None
        else "Await open data"
    )

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
        "theme": record.get("theme", record.get("industry / theme", "N/A")),
        "industry / theme": record.get("industry / theme", record.get("theme", "N/A")),
        "cornerstone investors": record.get("cornerstone investors", "N/A"),
        "oversubscription": record.get("oversubscription", "N/A"),
        "cornerstone quality": "Strong" if ipo_institutional_score(record.get("cornerstone investors", "")) >= 12 else "Average",
        "grey market price": format_price(grey_price),
        "grey market premium %": "Grey market unavailable" if premium is None else round(premium, 2),
        "grey market label": grey_label,
        "grey market source": record.get("grey market source", "N/A"),
        "simulated grey market range": "Live grey market available" if premium is not None else simulated_range,
        "expected open price": format_price(expected_open_price),
        "source": record.get("source", record.get("grey market source", "N/A")),
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
    fallback = fallback_ipo_dataframe(market)
    if not fallback.empty:
        fallback["latest news summary"] = fallback["latest news summary"].replace("N/A", reason)
    return fallback


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


def standardize_ipo_record(record: dict) -> dict:
    """Map official, RSS, scraped, and manual IPO fields into one schema."""
    aliases = {
        "offer price": ("offer price", "offer_price", "price range", "price_range", "ipo price", "listing price"),
        "lot size": ("lot size", "lot_size", "board lot"),
        "minimum subscription amount": ("minimum subscription amount", "minimum_subscription_amount", "entry fee"),
        "application deadline": ("application deadline", "application_deadline", "closing date", "deadline"),
        "listing date": ("listing date", "listing_date", "expected IPO date", "expected_ipo_date", "priced date"),
        "sponsor / underwriter": ("sponsor / underwriter", "sponsor", "underwriter", "underwriters", "bookrunner"),
        "industry / theme": ("industry / theme", "industry", "theme", "sector", "business"),
        "cornerstone investors": ("cornerstone investors", "cornerstone_investors", "cornerstone"),
        "grey market price": ("grey market price", "grey_market_price", "grey price", "gray market price"),
        "grey market premium %": ("grey market premium %", "grey_market_premium", "grey market premium"),
        "latest news summary": ("latest news summary", "latest news", "latest_news", "news", "headline"),
    }

    def pick(*keys: str, default: str = "N/A") -> str:
        for key in keys:
            value = record.get(key)
            cleaned = clean_ipo_text(value)
            if cleaned != "N/A":
                return cleaned
        return default

    standardized = {
        "ticker": pick("ticker", "symbol"),
        "company": pick("company", "company name", "name"),
        "market": pick("market", "exchange", default="HK"),
        "status": pick("status", default="upcoming"),
        "oversubscription": pick("oversubscription", "over-sub", "subscription"),
        "source": pick("source", default="N/A"),
        "last updated": pick("last updated", "last_updated", default=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")),
    }
    for target, keys in aliases.items():
        standardized[target] = pick(*keys)
    standardized["theme"] = standardized["industry / theme"]
    standardized["latest news headline"] = standardized["latest news summary"]
    standardized["grey market source"] = (
        standardized["source"] if standardized["grey market price"] != "N/A" else "Grey market unavailable"
    )
    if standardized["company"] == "N/A" and standardized["ticker"] != "N/A":
        standardized["company"] = standardized["ticker"]
    if standardized["ticker"] == "N/A" and standardized["company"] == "N/A":
        standardized["company"] = "Manual IPO candidate"
    return standardized


def normalize_ipo_data(records: List[dict] | pd.DataFrame, fallback_market: str = "HK") -> pd.DataFrame:
    """Normalize and score IPO records from any source without crashing on missing fields."""
    if isinstance(records, pd.DataFrame):
        raw_records = records.fillna("N/A").to_dict("records")
    else:
        raw_records = records or []

    scored = []
    for raw in raw_records:
        try:
            standardized = standardize_ipo_record(raw)
            if standardized["market"] == "N/A":
                standardized["market"] = fallback_market
            scored.append(score_live_ipo(standardized))
        except Exception:
            continue
    return pd.DataFrame(scored)


def fallback_ipo_dataframe(market: str | None = None) -> pd.DataFrame:
    """Return built-in manual IPO rows, filtered by market when requested."""
    rows = IPO_DATA if market is None else [row for row in IPO_DATA if row.get("market") == market]
    if not rows:
        rows = [row for row in IPO_DATA if row.get("source") == "manual fallback"]
    return normalize_ipo_data(rows, fallback_market=market or "HK")


def merge_ipo_sources(*frames: pd.DataFrame) -> pd.DataFrame:
    """Merge IPO sources, dedupe by market/ticker/company, and keep useful rows."""
    usable = [frame for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not usable:
        return pd.DataFrame()
    merged = pd.concat(usable, ignore_index=True)
    merged = merged.replace("", "N/A").fillna("N/A")
    merged["_dedupe_key"] = (
        merged.get("market", "N/A").astype(str)
        + "|"
        + merged.get("ticker", "N/A").astype(str)
        + "|"
        + merged.get("company", "N/A").astype(str)
    )
    merged = merged.drop_duplicates("_dedupe_key", keep="first").drop(columns=["_dedupe_key"])
    return merged


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
                    "source": source_name,
                }
            )
        )
    return records


def fetch_html_ipo_tables(source_name: str, url: str, market: str, headers: dict) -> Tuple[pd.DataFrame, dict]:
    """Fetch an IPO-like HTML page and normalize any usable tables."""
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    records: List[dict] = []
    for table in safe_read_html_tables(response.text):
        if market == "HK":
            records.extend(normalize_hk_ipo_table(table, source_name, url))
        else:
            table = table.fillna("N/A")
            if isinstance(table.columns, pd.MultiIndex):
                table.columns = [" ".join(str(part) for part in column if str(part) != "nan") for column in table.columns]
            text = " ".join(str(value).lower() for value in table.head(8).to_numpy().flatten())
            cols = " ".join(str(column).lower() for column in table.columns)
            if not any(word in f"{cols} {text}" for word in ("ipo", "company", "exchange", "price", "listing", "underwriter")):
                continue
            for _, row in table.head(30).iterrows():
                joined = " | ".join(clean_ipo_text(value) for value in row.tolist())
                if re.search(r"\bno\s+(filed|amended|priced|ipo|deals?)\s+(deals?\s+)?found\b", joined, flags=re.IGNORECASE):
                    continue
                company = value_by_keywords(row, ("company", "name"), "N/A")
                ticker_match = re.search(r"\(([A-Z.]{1,8})\)", joined)
                ticker = ticker_match.group(1) if ticker_match else value_by_keywords(row, ("ticker", "symbol"), "N/A")
                if company == "N/A" and ticker == "N/A":
                    continue
                records.append(
                    standardize_ipo_record(
                        {
                            "ticker": ticker,
                            "company": company,
                            "market": market,
                            "status": "upcoming",
                            "offer price": value_by_keywords(row, ("price", "range"), "N/A"),
                            "listing date": value_by_keywords(row, ("listing", "date", "ipo"), "N/A"),
                            "sponsor / underwriter": value_by_keywords(row, ("underwriter", "sponsor"), "N/A"),
                            "industry / theme": value_by_keywords(row, ("sector", "industry", "exchange"), "N/A"),
                            "latest news summary": f"{source_name}: {joined[:180]}",
                            "source": source_name,
                        }
                    )
                )
    normalized = normalize_ipo_data(records, fallback_market=market)
    return normalized, source_debug(source_name, not normalized.empty, len(normalized), "" if not normalized.empty else "No usable IPO rows found")


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_ipo_news_rss(market: str = "HK") -> Tuple[pd.DataFrame, dict]:
    """Fetch lightweight IPO discovery rows from RSS/news feeds."""
    try:
        import feedparser

        feeds = [
            ("Yahoo Finance IPO RSS", "https://finance.yahoo.com/rss/ipo"),
            ("Yahoo Finance News RSS", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=IPO&region=US&lang=en-US"),
        ]
        records = []
        market_terms = ("hong kong", "hk", "h-share", "hkex") if market == "HK" else ("nasdaq", "nyse", "us ipo", "ipo")
        for source_name, url in feeds:
            feed = feedparser.parse(url)
            for entry in feed.entries[:12]:
                title = clean_ipo_text(entry.get("title", "N/A"))
                summary = clean_ipo_text(entry.get("summary", title))
                combined = f"{title} {summary}".lower()
                if not re.search(r"\bipo\b|initial public offering", combined):
                    continue
                if market == "HK" and not any(term in combined for term in market_terms):
                    continue
                records.append(
                    {
                        "ticker": "N/A",
                        "company": title[:80],
                        "market": market,
                        "status": "news watch",
                        "industry / theme": title,
                        "latest news summary": summary[:240],
                        "source": source_name,
                    }
                )
        normalized = normalize_ipo_data(records, fallback_market=market)
        return normalized, source_debug("Yahoo Finance / RSS news search", not normalized.empty, len(normalized), "" if not normalized.empty else "No IPO RSS entries")
    except Exception as exc:
        return pd.DataFrame(), source_debug("Yahoo Finance / RSS news search", False, 0, str(exc))


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_hk_ipo_live() -> Tuple[pd.DataFrame, dict]:
    """Hybrid HK IPO discovery using official pages, IPO centers, RSS, and built-in fallback data."""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36"}
    last_updated = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    sources = [
        ("HKEX New Listing Information", "https://www.hkex.com.hk/Listing/IPO/New-Listing-Information/Main-Board?sc_lang=en"),
        ("HKEX AP / PHIP / Application Proof", "https://www.hkexnews.hk/app/appindex.html"),
        ("HKEX Newly Listed Securities", "https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities?sc_lang=en"),
        ("AAStocks IPO Center", "https://www.aastocks.com/en/stocks/market/ipo/upcomingipo/company-summary"),
        ("ETNet IPO Center", "https://www.etnet.com.hk/www/eng/stocks/ipo/ipo.php"),
    ]
    frames: List[pd.DataFrame] = []
    failed: List[dict] = []
    health: List[dict] = []

    for source_name, url in sources:
        try:
            frame, status = fetch_html_ipo_tables(source_name, url, "HK", headers)
            health.append(status)
            if frame.empty:
                failed.append(status)
            else:
                frames.append(frame)
        except Exception as exc:
            status = source_debug(source_name, False, 0, str(exc))
            health.append(status)
            failed.append(status)

    rss_frame, rss_status = fetch_ipo_news_rss("HK")
    health.append(rss_status)
    if rss_frame.empty:
        failed.append(rss_status)
    else:
        frames.append(rss_frame)

    merged = merge_ipo_sources(*frames)
    source_used = "Hybrid HK live/RSS sources"
    if merged.empty:
        merged = fallback_ipo_dataframe("HK")
        source_used = "manual fallback"
        health.append(source_debug("IPO_DATA manual fallback", True, len(merged), "Automatic HK sources returned no usable rows"))

    debug = {
        "source_used": source_used,
        "last_updated": last_updated,
        "count": len(merged),
        "failed_sources": failed,
        "source_health": health,
    }
    return merged, debug


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_us_ipo_live() -> Tuple[pd.DataFrame, dict]:
    """Hybrid US IPO discovery using Nasdaq, NYSE/MarketWatch pages, RSS, and fallback rows."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/market-activity/ipos",
    }
    last_updated = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    frames: List[pd.DataFrame] = []
    failed: List[dict] = []
    health: List[dict] = []

    try:
        date_key = pd.Timestamp.today().strftime("%Y-%m")
        response = requests.get(f"https://api.nasdaq.com/api/ipo/calendar?date={date_key}", headers=headers, timeout=8)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", {}).get("priced", {}).get("rows", [])
        rows += payload.get("data", {}).get("upcoming", {}).get("rows", [])
        records = []
        for row in rows:
            company = row.get("companyName") or row.get("name") or "N/A"
            ticker = row.get("proposedTickerSymbol") or row.get("symbol") or "N/A"
            records.append(
                {
                    "ticker": ticker,
                    "company": company,
                    "market": "US",
                    "status": "upcoming",
                    "offer price": row.get("proposedSharePrice") or row.get("price") or "N/A",
                    "listing date": row.get("expectedPriceDate") or row.get("pricedDate") or "N/A",
                    "shares offered": row.get("sharesOffered", "N/A"),
                    "sponsor / underwriter": row.get("underwriters", "N/A"),
                    "industry / theme": row.get("sector") or row.get("industry") or "N/A",
                    "latest news summary": f"{company} IPO calendar entry from Nasdaq.",
                    "source": "Nasdaq IPO Calendar",
                }
            )
        frame = normalize_ipo_data(records, fallback_market="US")
        status = source_debug("Nasdaq IPO Calendar", not frame.empty, len(frame), "" if not frame.empty else "No Nasdaq IPO rows found")
        health.append(status)
        if frame.empty:
            failed.append(status)
        else:
            frames.append(frame)
    except Exception as exc:
        status = source_debug("Nasdaq IPO Calendar", False, 0, str(exc))
        health.append(status)
        failed.append(status)

    for source_name, url in [
        ("NYSE IPO Center", "https://www.nyse.com/ipo-center/filings"),
        ("MarketWatch IPO Calendar", "https://www.marketwatch.com/tools/ipo-calendar"),
    ]:
        try:
            frame, status = fetch_html_ipo_tables(source_name, url, "US", headers)
            health.append(status)
            if frame.empty:
                failed.append(status)
            else:
                frames.append(frame)
        except Exception as exc:
            status = source_debug(source_name, False, 0, str(exc))
            health.append(status)
            failed.append(status)

    rss_frame, rss_status = fetch_ipo_news_rss("US")
    health.append(rss_status)
    if rss_frame.empty:
        failed.append(rss_status)
    else:
        frames.append(rss_frame)

    merged = merge_ipo_sources(*frames)
    source_used = "Hybrid US live/RSS sources"
    if merged.empty:
        merged = fallback_ipo_dataframe("US")
        source_used = "manual fallback"
        health.append(source_debug("IPO_DATA manual fallback", True, len(merged), "Automatic US sources returned no usable rows"))

    debug = {
        "source_used": source_used,
        "last_updated": last_updated,
        "count": len(merged),
        "failed_sources": failed,
        "source_health": health,
    }
    return merged, debug


def fetch_hk_live_ipos() -> Tuple[pd.DataFrame, dict]:
    """Backward-compatible wrapper for the upgraded HK IPO fetcher."""
    return fetch_hk_ipo_live()


def fetch_us_live_ipos() -> pd.DataFrame:
    """Backward-compatible wrapper for older callers expecting only a DataFrame."""
    frame, _debug = fetch_us_ipo_live()
    return frame


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
    stop_loss, tp1, tp2, tp3 = ipo_trade_plan(entry_price, grey_market_label)
    stop_loss = stop_loss or 0
    tp1 = tp1 or 0
    tp2 = tp2 or 0
    tp3 = tp3 or 0
    risk_pct = ((entry_price - stop_loss) / entry_price * 100) if entry_price > 0 else 0
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
    "industry / theme",
    "cornerstone investors",
    "oversubscription",
    "cornerstone quality",
    "grey market price",
    "grey market premium %",
    "grey market label",
    "grey market source",
    "simulated grey market range",
    "IPO score",
    "Win Probability %",
    "action",
    "expected open price",
    "open decision",
    "entry",
    "stop loss",
    "TP1",
    "TP2",
    "TP3",
    "first day strategy",
    "latest news headline",
    "latest news summary",
    "source",
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

    cards = st.columns(6)
    with cards[0]:
        render_status_card("Best IPO to apply", best["ticker"], "green" if best["IPO score"] >= 80 else "yellow", best["action"])
    with cards[1]:
        render_status_card(f"Hottest {market} IPO", best["company"][:24], "green", f"Score {best['IPO score']}")
    with cards[2]:
        if grey_winner is not None:
            render_status_card("Grey market winner", grey_winner["ticker"], "green", f"{grey_winner['grey market premium %']}%")
        else:
            render_status_card("Grey market winner", "N/A", "yellow", "Grey market unavailable")
    with cards[3]:
        render_status_card("High risk IPO", high_risk["ticker"], "red", high_risk["action"])
    with cards[4]:
        us_rows = source[source["market"] == "US"] if "market" in source else pd.DataFrame()
        hottest_us = us_rows.sort_values("IPO score", ascending=False).iloc[0] if not us_rows.empty else None
        render_status_card("Hottest US IPO", hottest_us["ticker"] if hottest_us is not None else "N/A", "yellow", hottest_us["action"] if hottest_us is not None else "Use US IPO tab")
    with cards[5]:
        render_status_card("Data source status", "Hybrid", "yellow", "Live + RSS + manual fallback")


def render_ipo_debug(debug: dict | None) -> None:
    """Show visible live IPO source diagnostics."""
    if not debug:
        return
    with st.expander("Data Source Health", expanded=True):
        st.write(f"Source used: {debug.get('source_used', 'N/A')}")
        st.write(f"Last updated: {debug.get('last_updated', 'N/A')}")
        st.write(f"Number of IPOs found: {debug.get('count', 0)}")
        health = debug.get("source_health", [])
        if health:
            st.write("Source status:")
            st.dataframe(pd.DataFrame(health), width="stretch", hide_index=True)
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
        st.warning("Live data unavailable. Showing manual fallback IPO_DATA rows.")
        data = fallback_ipo_dataframe(market)

    render_ipo_debug(debug)

    with st.expander("Editable manual IPO override", expanded=False):
        st.caption("Add or edit upcoming IPOs here. Rows with a ticker or company are merged into the live table and scored automatically.")
        blank_row = {column: "N/A" for column in MANUAL_IPO_INPUT_COLUMNS}
        blank_row["market"] = market
        blank_row["source"] = "manual override"
        manual_seed = pd.DataFrame([blank_row])
        edited_manual = st.data_editor(
            manual_seed,
            num_rows="dynamic",
            width="stretch",
            hide_index=True,
            key=f"{market}_manual_ipo_editor",
        )
        manual_candidates = edited_manual[
            (edited_manual["ticker"].astype(str).str.strip().str.upper() != "N/A")
            | (edited_manual["company"].astype(str).str.strip().str.upper() != "N/A")
        ]
        if not manual_candidates.empty:
            manual_frame = normalize_ipo_data(manual_candidates, fallback_market=market)
            data = merge_ipo_sources(manual_frame, data)

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
        table_display = display.reindex(columns=LIVE_IPO_COLUMNS, fill_value="N/A").astype(str)
        st.dataframe(table_display, width="stretch", hide_index=True)

    st.caption(
        "IPO data, grey market price, news and sentiment may be delayed or inaccurate. "
        "Always confirm with broker or official prospectus before applying or trading."
    )


def render_ipo_scanner() -> None:
    """Render live IPO discovery plus the existing manual calculator."""
    st.caption("Automatic IPO discovery is best-effort. Manual override remains available when live data is unavailable.")
    hk_tab, us_tab, manual_tab = st.tabs(["HK IPO Live", "US IPO Live", "IPO Manual Calculator"])

    with hk_tab:
        if st.button("Load HK IPO Live Data", key="load_hk_ipo_live"):
            hk_data, hk_debug = fetch_hk_ipo_live()
            st.session_state["hk_ipo_live_data"] = hk_data
            st.session_state["hk_ipo_live_debug"] = hk_debug
        if "hk_ipo_live_data" in st.session_state:
            render_live_ipo_table("HK", st.session_state["hk_ipo_live_data"], st.session_state.get("hk_ipo_live_debug"))
        else:
            st.info("Live IPO scraping is optional. Click Load HK IPO Live Data when you want it.")

    with us_tab:
        if st.button("Load US IPO Live Data", key="load_us_ipo_live"):
            us_data, us_debug = fetch_us_ipo_live()
            st.session_state["us_ipo_live_data"] = us_data
            st.session_state["us_ipo_live_debug"] = us_debug
        if "us_ipo_live_data" in st.session_state:
            render_live_ipo_table("US", st.session_state["us_ipo_live_data"], st.session_state.get("us_ipo_live_debug"))
        else:
            st.info("Live IPO scraping is optional. Click Load US IPO Live Data when you want it.")

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
    if picks.empty:
        st.info("No clean trade today. Best action: wait.")
        return
    cols = st.columns(5)
    for index, (_, row) in enumerate(picks.iterrows()):
        with cols[index % 5]:
            label = ai_trade_label(row)
            tone = "red" if label in {"TOO EXTENDED", "EARNINGS RISK"} else "green" if label == "BEST BUY SETUP" else "yellow"
            render_status_card(row["ticker"], label, tone, f"Final {row['Final Score']} | {row['Action Label']}")
            st.write(f"Company: {row.get('Company Name', 'N/A')}")
            st.write(f"Sector / Industry: {row.get('Sector / Industry', 'N/A')}")
            st.write(f"Sector Group: {row.get('Sector Group', 'N/A')}")
            st.write(f"Theme ETF: {row.get('Sector ETF', 'N/A')}")
            st.write(f"Quality: {row.get('Setup Quality Grade', 'N/A')}")
            st.write(f"Signal: {row.get('Signal State', 'N/A')}")
            st.write(f"Setup Type: {row.get('Setup Type', 'N/A')}")
            st.write(f"Entry Type: {row.get('Entry Type', 'N/A')}")
            st.write(f"VCP: {row.get('VCP Status', 'N/A')} | {row.get('Contractions', 'N/A')}")
            st.write(f"RS/Trend/Tech: {row.get('RS Score', 'N/A')} / {row.get('Trend Score', 'N/A')} / {row.get('Technical Score', 'N/A')}")
            st.write(f"Breakout quality / RVOL: {row.get('Breakout Quality Score', 'N/A')}/10 / {row.get('RVOL', 'N/A')}x")
            st.write(f"Live status: {row.get('Live Breakout Status', 'N/A')}")
            st.write(f"Stage: {row.get('Stage Analysis', 'N/A')} | {row.get('Institutional Action', 'N/A')}")
            st.write(f"Explosive: {row.get('Explosive Score', 'N/A')}/10 - {row.get('Explosive Label', 'N/A')}")
            st.write(f"Close: {row.get('close', 'N/A')}")
            st.write(f"Pivot: {row.get('Pivot', 'N/A')}")
            st.write(f"Entry: {row.get('Entry Trigger', 'N/A')}")
            st.write(f"Stop: {row.get('Stop Loss', 'N/A')}")
            st.write(f"Risk: {row.get('Risk %', 'N/A')}%")
            st.write(f"Ideal TP: {row.get('Ideal TP', 'N/A')} ({row.get('Ideal TP Reason', 'N/A')})")
            st.write(f"1R / 2R / 3R: {row.get('Target 1R', 'N/A')} / {row.get('Target 2R', 'N/A')} / {row.get('Target 3R', 'N/A')}")
            st.write(f"Sell: {row.get('Sell Strategy', 'N/A')}")
            st.write(f"Earnings: {row.get('Earnings Date', 'N/A')} ({row.get('Earnings Risk', 'N/A')})")
            st.write(row.get("Decision Reason", row.get("Why Selected", "")))
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
    live_alerts = results[
        results.get("Live Breakout Status", pd.Series("", index=results.index)).isin(["LIVE BREAKOUT", "BREAKOUT STARTING"])
        | (results.get("Signal State", pd.Series("", index=results.index)) == "BUY NOW")
        | (results.get("Earnings Risk", pd.Series("", index=results.index)) == "HIGH RISK")
    ].copy()
    if not live_alerts.empty:
        st.write("Live trigger queue:")
        st.dataframe(
            round_display_values(
                live_alerts[
                    [
                        "ticker",
                        "Signal State",
                        "Live Breakout Status",
                        "Alert Event",
                        "Breakout Quality Score",
                        "RVOL",
                        "Pivot",
                        "Entry Trigger",
                        "Stop Loss",
                        "Risk %",
                        "Earnings Risk",
                        "Decision Reason",
                    ]
                ].head(15)
            ),
            width="stretch",
            hide_index=True,
        )
    if picks.empty:
        st.info("No clean trade today. Best action: wait.")
    else:
        st.dataframe(
            round_display_values(
                picks[
                    [
                        "ticker",
                        "Sector / Industry",
                        "VCP Status",
                        "Setup Type",
                        "Signal State",
                        "Live Breakout Status",
                        "Breakout Quality Score",
                        "RVOL",
                        "Contractions",
                        "Volume Dry-Up",
                        "RS Score",
                        "Final Score",
                        "Trend Score",
                        "Technical Score",
                        "Tightness Score",
                        "Entry Type",
                        "Setup Quality Grade",
                        "Explosive Score",
                        "Explosive Label",
                        "TP Quality Score",
                        "Ideal TP",
                        "Ideal TP Reason",
                        "Action Label",
                        "Breakout Alert",
                        "Earnings Date",
                        "Earnings Risk",
                        "Decision Reason",
                        "AI Trading Notes",
                    ]
                ]
            ),
            width="stretch",
            hide_index=True,
        )

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
        if picks.empty:
            st.info("No clean trade today. Best action: wait.")
            return
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


def make_position_chart(ticker: str, data: pd.DataFrame, row: pd.Series) -> go.Figure:
    """Chart an existing holding with original thesis and updated management levels."""
    chart_data = data.tail(160) if data is not None and not data.empty else pd.DataFrame()
    figure = go.Figure()
    if chart_data.empty:
        return figure
    chart_data = chart_data.copy()
    chart_data.index = pd.to_datetime(chart_data.index, errors="coerce")
    chart_data = chart_data[chart_data.index.notna()]
    if chart_data.empty:
        return figure
    if getattr(chart_data.index, "tz", None) is not None:
        chart_data.index = chart_data.index.tz_localize(None)
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
        if ma in chart_data.columns:
            figure.add_trace(go.Scatter(x=chart_data.index, y=chart_data[ma], mode="lines", line=dict(width=1.6, color=color), name=ma))
    figure.add_trace(
        go.Bar(x=chart_data.index, y=chart_data["Volume"], marker_color="#94a3b8", opacity=0.3, name="Volume", yaxis="y2")
    )
    levels = [
        ("Entry", row.get("entry price"), "#2563eb"),
        ("Original Stop", row.get("original stop loss"), "#dc2626"),
        ("Suggested Stop", row.get("suggested stop loss today"), "#ea580c"),
        ("TP1", row.get("updated TP1"), "#22c55e"),
        ("TP2", row.get("updated TP2"), "#16a34a"),
        ("TP3", row.get("updated TP3"), "#15803d"),
        ("Ideal TP", row.get("updated ideal TP"), "#0f766e"),
    ]
    for label, value, color in levels:
        numeric = numeric_or_na(value)
        if pd.notna(numeric):
            figure.add_hline(y=float(numeric), line_dash="dash", line_color=color, annotation_text=label)
    entry_dt = pd.to_datetime(row.get("entry date"), errors="coerce")
    if pd.notna(entry_dt):
        entry_dt = entry_dt.tz_localize(None) if getattr(entry_dt, "tzinfo", None) else entry_dt
        if chart_data.index.min() <= entry_dt <= chart_data.index.max():
            figure.add_vline(x=entry_dt, line_dash="dot", line_color="#7c3aed", annotation_text="Entry")
    figure.update_layout(
        title=f"{ticker} existing position management",
        height=600,
        margin=dict(l=12, r=12, t=48, b=24),
        xaxis_rangeslider_visible=False,
        yaxis=dict(title="Price"),
        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False, rangemode="tozero"),
        legend=dict(orientation="h", y=1.02, x=0),
        template="plotly_white",
    )
    return figure


def render_my_positions() -> None:
    """Render simplified active position manager and trade history matching."""
    st.subheader("My Positions")
    st.caption("Existing position management is separate from new-entry scanner signals.")
    if "positions_df" not in st.session_state:
        st.session_state["positions_df"] = load_positions_file()

    history = load_trade_signal_history()
    current_fallback = combined_session_results()
    uploaded_files = st.file_uploader(
        "Upload scanner export, positions CSV, or Futu screenshots",
        type=["csv", "pdf", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key="my_positions_unified_uploader",
    )
    scanner_export_frames: List[pd.DataFrame] = []
    position_csv_frames: List[Tuple[str, pd.DataFrame]] = []
    screenshot_items: List[dict] = []
    upload_summary = []
    for uploaded_file in uploaded_files or []:
        detected_type, status, frame, payload = detect_uploaded_file_type(uploaded_file)
        upload_summary.append({"filename": uploaded_file.name, "detected type": detected_type, "status": status})
        if detected_type.startswith("Scanner Export") and not frame.empty:
            scanner_export_frames.append(history_like_from_scanner_export(frame))
        elif detected_type == "Position CSV" and not frame.empty:
            position_csv_frames.append((uploaded_file.name, normalize_positions_frame(frame)))
        elif detected_type == "Futu Screenshot":
            payload["filename"] = uploaded_file.name
            screenshot_items.append(payload)

    uploaded_export = pd.concat(scanner_export_frames, ignore_index=True) if scanner_export_frames else pd.DataFrame()
    if upload_summary:
        summary_frame = pd.DataFrame(upload_summary)
        counts = summary_frame["detected type"].value_counts()
        st.write(
            f"Uploaded files: Scanner exports: {int(counts.get('Scanner Export CSV', 0) + counts.get('Scanner Export PDF', 0))} | "
            f"Position CSV files: {int(counts.get('Position CSV', 0))} | "
            f"Futu screenshots: {int(counts.get('Futu Screenshot', 0))} | "
            f"Unsupported / unreadable: {int(counts.get('Unsupported / unreadable', 0))}"
        )
        st.dataframe(summary_frame, width="stretch", hide_index=True)
    if not uploaded_export.empty:
        st.success(f"Loaded {len(uploaded_export)} uploaded scanner export rows.")

    if position_csv_frames:
        with st.expander("Position CSV Imports", expanded=True):
            for filename, frame in position_csv_frames:
                st.markdown(f"**{filename}**")
                if frame.empty:
                    st.warning("Required columns: ticker, entry_date, entry_price, position_size.")
                else:
                    st.dataframe(frame.head(20), width="stretch", hide_index=True)
            if st.button("Import Position CSV Files", type="primary"):
                records = []
                skipped = 0
                existing = st.session_state["positions_df"]
                for _, frame in position_csv_frames:
                    for _, uploaded_position in frame.iterrows():
                        if position_duplicate_exists(existing, uploaded_position["ticker"], uploaded_position["entry_date"], uploaded_position["entry_price"]):
                            skipped += 1
                            continue
                        records.append(
                            build_position_record(
                                ticker=uploaded_position["ticker"],
                                entry_date=uploaded_position["entry_date"],
                                entry_price=uploaded_position["entry_price"],
                                position_size=uploaded_position["position_size"],
                                fees=uploaded_position.get("fees", 0),
                                broker=uploaded_position.get("broker", ""),
                                account=uploaded_position.get("account", ""),
                                notes=uploaded_position.get("notes", ""),
                                stop_override=uploaded_position.get("current_stop_loss_override", np.nan),
                                tp_override=uploaded_position.get("manual_tp_override", np.nan),
                                history=history,
                                uploaded_export=uploaded_export,
                                current_fallback=current_fallback,
                            )
                        )
                if records:
                    st.session_state["positions_df"] = pd.concat([existing, pd.DataFrame(records)], ignore_index=True)
                    save_positions_file(st.session_state["positions_df"])
                st.success(f"Added {len(records)} positions. Skipped {skipped} duplicates.")

    if screenshot_items:
        st.markdown("**Futu Screenshot Confirmations**")
        confirmed_records = []
        for index, item in enumerate(screenshot_items):
            filename = item.get("filename", f"screenshot_{index}")
            extracted = item.get("extracted", {})
            status = item.get("status", "Screenshot uploaded. Please confirm details manually.")
            with st.expander(filename, expanded=index == 0):
                st.image(item.get("file"), caption=filename)
                st.info(status)
                cols = st.columns(5)
                default_date = pd.to_datetime(extracted.get("trade_date"), errors="coerce")
                key_base = f"screenshot_{index}_{filename}"
                s_ticker = cols[0].text_input("Ticker", value=str(extracted.get("ticker", "")), key=f"{key_base}_ticker")
                s_date = cols[1].date_input("Entry Date", value=default_date.date() if pd.notna(default_date) else datetime.now().date(), key=f"{key_base}_date")
                s_entry = cols[2].number_input("Entry Price", min_value=0.0, value=float(extracted.get("price")) if pd.notna(extracted.get("price")) else 0.0, step=0.01, key=f"{key_base}_entry")
                s_size = cols[3].number_input("Position Size", min_value=0.0, value=float(extracted.get("quantity")) if pd.notna(extracted.get("quantity")) else 0.0, step=1.0, key=f"{key_base}_size")
                s_fee = cols[4].number_input("Fees", min_value=0.0, value=float(extracted.get("fees")) if pd.notna(extracted.get("fees")) else 0.0, step=0.01, key=f"{key_base}_fee")
                s_notes = st.text_area("Notes", value=f"From Futu screenshot; manually confirmed. Direction: {extracted.get('direction', '')}; time: {extracted.get('trade_time', '')}", key=f"{key_base}_notes")
                if s_ticker and s_entry > 0 and s_size > 0:
                    confirmed_records.append((s_ticker, s_date.strftime("%Y-%m-%d"), s_entry, s_size, s_fee, s_notes))
                if st.button("Save This Position", key=f"{key_base}_save"):
                    existing = st.session_state["positions_df"]
                    if not s_ticker or s_entry <= 0 or s_size <= 0:
                        st.warning("Please confirm ticker, entry price, and position size before saving.")
                    elif position_duplicate_exists(existing, s_ticker, s_date.strftime("%Y-%m-%d"), s_entry):
                        st.warning("Duplicate position detected by ticker + entry date + entry price.")
                    else:
                        record = build_position_record(
                            ticker=s_ticker,
                            entry_date=s_date.strftime("%Y-%m-%d"),
                            entry_price=s_entry,
                            position_size=s_size,
                            fees=s_fee,
                            notes=s_notes,
                            history=history,
                            uploaded_export=uploaded_export,
                            current_fallback=current_fallback,
                        )
                        st.session_state["positions_df"] = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
                        save_positions_file(st.session_state["positions_df"])
                        st.success("Position saved to positions.csv.")
        if st.button("Save All Confirmed Positions", type="primary"):
            existing = st.session_state["positions_df"]
            records = []
            skipped = 0
            for s_ticker, s_date, s_entry, s_size, s_fee, s_notes in confirmed_records:
                if position_duplicate_exists(existing, s_ticker, s_date, s_entry):
                    skipped += 1
                    continue
                records.append(
                    build_position_record(
                        ticker=s_ticker,
                        entry_date=s_date,
                        entry_price=s_entry,
                        position_size=s_size,
                        fees=s_fee,
                        notes=s_notes,
                        history=history,
                        uploaded_export=uploaded_export,
                        current_fallback=current_fallback,
                    )
                )
            if records:
                st.session_state["positions_df"] = pd.concat([existing, pd.DataFrame(records)], ignore_index=True)
                save_positions_file(st.session_state["positions_df"])
            st.success(f"Saved {len(records)} confirmed screenshot positions. Skipped {skipped} duplicates.")

    with st.expander("Manual Input", expanded=not bool(uploaded_files)):
        with st.form("manual_position_form", clear_on_submit=False):
            cols = st.columns(4)
            ticker = cols[0].text_input("Ticker")
            entry_date = cols[1].date_input("Entry Date")
            entry_price = cols[2].number_input("Entry Price", min_value=0.0, step=0.01)
            position_size = cols[3].number_input("Position Size", min_value=0.0, step=1.0)
            opt_cols = st.columns(5)
            broker = opt_cols[0].text_input("Broker")
            account = opt_cols[1].text_input("Account")
            fees = opt_cols[2].number_input("Fees", min_value=0.0, step=0.01)
            stop_override = opt_cols[3].number_input("Current Stop Loss Override", min_value=0.0, step=0.01)
            tp_override = opt_cols[4].number_input("Manual TP Override", min_value=0.0, step=0.01)
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Save Position", type="primary")
        if submitted and ticker and entry_price > 0 and position_size > 0:
            existing = st.session_state["positions_df"]
            if position_duplicate_exists(existing, ticker, entry_date.strftime("%Y-%m-%d"), entry_price):
                st.warning("Duplicate position detected by ticker + entry date + entry price. Edit the existing position or change the entry details.")
            else:
                record = build_position_record(
                    ticker=ticker,
                    entry_date=entry_date.strftime("%Y-%m-%d"),
                    entry_price=entry_price,
                    position_size=position_size,
                    fees=fees,
                    broker=broker,
                    account=account,
                    notes=notes,
                    stop_override=stop_override,
                    tp_override=tp_override,
                    history=history,
                    uploaded_export=uploaded_export,
                    current_fallback=current_fallback,
                )
                st.session_state["positions_df"] = pd.concat([existing, pd.DataFrame([record])], ignore_index=True)
                save_positions_file(st.session_state["positions_df"])
                st.success("Position saved to positions.csv.")

    positions = normalize_positions_frame(st.session_state.get("positions_df", pd.DataFrame()))
    if positions.empty:
        st.info("Add a position manually, upload a positions CSV, or confirm a Futu screenshot position.")
        if not history.empty:
            st.caption(f"Trade history archive loaded: {len(history)} saved signal rows.")
        return

    with st.expander("Current Open Positions", expanded=False):
        edited_positions = st.data_editor(positions, width="stretch", hide_index=True, num_rows="dynamic")
        edit_cols = st.columns(3)
        if edit_cols[0].button("Edit Position"):
            st.info("Edit fields directly in the table, then click Save Changes.")
        if edit_cols[1].button("Save Changes"):
            saved_positions = edited_positions.copy()
            saved_positions["updated_at"] = datetime.now(ZoneInfo("Asia/Singapore")).strftime("%Y-%m-%d %H:%M:%S %Z")
            st.session_state["positions_df"] = saved_positions
            save_positions_file(saved_positions)
            positions = normalize_positions_frame(saved_positions)
            st.success("Positions updated in positions.csv.")
        delete_options = positions["position_id"].where(positions["position_id"].astype(str).str.len() > 0, positions["ticker"] + "-" + positions["entry_date"].astype(str)).tolist()
        delete_choice = edit_cols[2].selectbox("Delete Position", [""] + delete_options)
        if delete_choice and st.button("Delete Selected Position"):
            delete_mask = (positions["position_id"] == delete_choice) | ((positions["ticker"] + "-" + positions["entry_date"].astype(str)) == delete_choice)
            st.session_state["positions_df"] = positions[~delete_mask].copy()
            save_positions_file(st.session_state["positions_df"])
            positions = normalize_positions_frame(st.session_state["positions_df"])
            st.success("Position deleted.")
    if positions.empty:
        st.info("No saved positions remain.")
        return

    tickers = tuple(sorted(positions["ticker"].dropna().astype(str).str.upper().unique()))
    refresh_positions = st.button("Refresh Position Data", type="primary")
    with st.spinner("Updating open positions with daily data..."):
        force_token = datetime.now().isoformat() if refresh_positions else datetime.now().strftime("%Y-%m-%d")
        raw_data = download_daily_data(tickers, period="1y", force_token=force_token)
        quote_data = {ticker: fetch_live_quote(ticker, include_info=True) for ticker in tickers}
        indicator_data = {ticker: add_indicators(frame) for ticker, frame in raw_data.items() if frame is not None and not frame.empty}
        rows = []
        for _, position in positions.iterrows():
            thesis, thesis_source = thesis_from_saved_position(position)
            if thesis.empty:
                thesis, thesis_source = match_original_thesis(position["ticker"], position["entry_date"], history, uploaded_export, current_fallback)
            rows.append(calculate_position_management_row(position, thesis, thesis_source, indicator_data.get(position["ticker"]), quote_data.get(position["ticker"], {})))
        managed = pd.DataFrame(rows)

    card_cols = st.columns(10)
    card_cols[0].metric("Total open positions", len(managed))
    card_cols[1].metric("Total unrealized P/L", f"${pd.to_numeric(managed['unrealized P/L'], errors='coerce').sum():,.2f}")
    best = managed.sort_values("gain %", ascending=False).iloc[0]
    worst = managed.sort_values("gain %", ascending=True).iloc[0]
    card_cols[2].metric("Best performer", f"{best['ticker']} {best['gain %']}%")
    card_cols[3].metric("Worst performer", f"{worst['ticker']} {worst['gain %']}%")
    card_cols[4].metric("Above +1R", int((pd.to_numeric(managed["current R multiple"], errors="coerce") >= 1).sum()))
    card_cols[5].metric("Below entry", int((pd.to_numeric(managed["gain %"], errors="coerce") < 0).sum()))
    card_cols[6].metric("Need action", int(managed["suggested action"].isin(["TAKE PARTIAL", "MOVE STOP UP", "REDUCE", "EXIT"]).sum()))
    card_cols[7].metric("Near stop", int((managed["current price"].astype(float) <= managed["suggested stop loss today"].astype(float) * 1.03).sum()))
    card_cols[8].metric("Near TP", int((managed["TP status"] != "NOT HIT").sum()))
    card_cols[9].metric("After-hours alerts", int(managed["after-hours alert"].isin(["WATCH", "WARNING", "ACTION NEEDED"]).sum()))

    with st.expander("After-hours / Pre-market Alert Panel", expanded=True):
        alert_cols = ["ticker", "after-hours / pre-market price", "after-hours / pre-market move %", "after-hours alert", "after-hours alert reason", "suggested action"]
        st.dataframe(round_display_values(managed[alert_cols]), width="stretch", hide_index=True)

    with st.expander("Notification Settings", expanded=False):
        notify_cols = st.columns(3)
        enable_email = notify_cols[0].checkbox("Enable email alert", value=False, key="positions_email_alert")
        enable_telegram = notify_cols[1].checkbox("Enable Telegram alert", value=False, key="positions_telegram_alert")
        alert_threshold = notify_cols[2].number_input("Alert threshold %", min_value=0.0, value=3.0, step=0.5)
        near_stop_alert = st.checkbox("Alert when price near stop", value=True)
        near_tp_alert = st.checkbox("Alert when price near TP", value=True)
        after_hours_alert = st.checkbox("Alert when after-hours move exceeds threshold", value=True)
        if enable_email or enable_telegram:
            st.info("Configure Telegram and email credentials in Settings or Streamlit secrets. Missing credentials are ignored safely.")
        triggered = managed[
            ((managed["after-hours alert"].isin(["WARNING", "ACTION NEEDED"])) & after_hours_alert)
            | ((managed["current price"].astype(float) <= managed["suggested stop loss today"].astype(float) * 1.03) & near_stop_alert)
            | ((managed["TP status"] != "NOT HIT") & near_tp_alert)
            | (pd.to_numeric(managed["after-hours / pre-market move %"], errors="coerce").abs() >= alert_threshold)
        ]
        st.caption(f"{len(triggered)} positions currently meet notification rules.")

    export_columns = [
        "ticker",
        "entry date",
        "entry price",
        "current price",
        "gain %",
        "unrealized P/L",
        "current R multiple",
        "original thesis source",
        "original signal",
        "original setup type",
        "original stop loss",
        "original TP1",
        "original TP2",
        "original TP3",
        "thesis status",
        "suggested stop loss today",
        "updated TP1",
        "updated TP2",
        "updated TP3",
        "suggested action",
        "after-hours alert",
        "after-hours alert reason",
        "original thesis vs current action",
    ]
    display_columns = export_columns + [
        "position size",
        "days held",
        "distance from MA10",
        "distance from MA20",
        "current RSI",
        "current volume vs 20-day average",
        "highest price since entry",
        "pullback from high %",
        "updated ideal TP",
        "TP status",
        "after-hours / pre-market price",
        "after-hours / pre-market move %",
        "original trade tier",
        "original professional score",
        "original decision reason",
    ]
    st.dataframe(round_display_values(managed[display_columns]), width="stretch", hide_index=True)
    st.download_button("Export Positions CSV", data=managed[export_columns].to_csv(index=False).encode("utf-8"), file_name="positions_export.csv", mime="text/csv")
    st.download_button("Export Positions PDF", data=dataframe_to_simple_pdf(managed[export_columns], "Positions Export"), file_name="positions_export.pdf", mime="application/pdf")

    selected_ticker = st.selectbox("Chart holding", managed["ticker"].tolist(), key="position_chart_ticker")
    selected = managed[managed["ticker"] == selected_ticker].iloc[0]
    selected_data = selected.get("_data")
    if not isinstance(selected_data, pd.DataFrame) or selected_data.empty:
        st.warning("No chart data available for this position.")
    else:
        if pd.isna(pd.to_datetime(selected.get("entry date"), errors="coerce")):
            st.warning("Entry date is invalid or unavailable. Chart displayed without entry marker.")
        try:
            st.plotly_chart(make_position_chart(selected_ticker, selected_data, selected), width="stretch")
        except Exception:
            st.warning("Position chart could not be displayed. Please check entry date and ticker data.")
    st.caption("New Entry Signal and Existing Position Management are separate: an extended stock can be no-chase for new buyers while still being HOLD / TRAIL STOP for existing holders.")


def manage_active_position(
    entry_price: float,
    current_price: float,
    stop_loss: float,
    position_size: float,
    ma10: float | None,
    prior_day_low: float | None,
    heavy_volume_ma10_break: bool = False,
) -> dict:
    """Calculate active-position status and a rule-based management action."""
    risk_per_share = entry_price - stop_loss
    gain_pct = (current_price / entry_price - 1) * 100 if entry_price > 0 else np.nan
    current_r = (current_price - entry_price) / risk_per_share if risk_per_share > 0 else np.nan
    position_pl = (current_price - entry_price) * position_size
    ma10_value = ma10 if ma10 is not None and pd.notna(ma10) else np.nan
    prior_low_value = prior_day_low if prior_day_low is not None and pd.notna(prior_day_low) else np.nan
    extended_from_ma10 = (
        (current_price / ma10_value - 1) * 100
        if pd.notna(ma10_value) and ma10_value > 0
        else np.nan
    )

    suggested_action = "HOLD"
    action_reason = "Position has not reached 1R yet; keep original risk plan."
    suggested_stop = stop_loss
    partial_note = "No partial sale suggested yet."

    if heavy_volume_ma10_break or (pd.notna(ma10_value) and current_price < ma10_value):
        suggested_action = "EXIT POSITION"
        action_reason = "Breakout failed below MA10 on heavy or concerning volume; exit remaining position."
        suggested_stop = current_price
        partial_note = "Exit remaining shares."
    elif pd.notna(extended_from_ma10) and extended_from_ma10 > 15:
        suggested_action = "TRAIL MA10"
        suggested_stop = prior_low_value if pd.notna(prior_low_value) else max(stop_loss, ma10_value)
        action_reason = "Price is more than 15% above MA10; tighten stop to prior day low."
        partial_note = "Consider locking gains if position is outsized."
    elif pd.notna(current_r) and current_r >= 2:
        suggested_action = "TAKE PARTIAL"
        suggested_stop = max(stop_loss, ma10_value if pd.notna(ma10_value) else entry_price, entry_price)
        action_reason = "Position is above 2R; take partial and trail the rest."
        partial_note = "Take partial profits and trail remaining shares with MA10."
    elif pd.notna(current_r) and current_r >= 1.5:
        suggested_action = "TAKE PARTIAL"
        suggested_stop = max(stop_loss, ma10_value if pd.notna(ma10_value) else entry_price, entry_price)
        action_reason = "Position is above 1.5R; take 30-50% partial or trail by MA10."
        partial_note = "Take 30-50% partial, or trail all by MA10 if momentum is strong."
    elif pd.notna(current_r) and current_r >= 1:
        suggested_action = "MOVE STOP TO BREAKEVEN"
        suggested_stop = max(stop_loss, entry_price, ma10_value if pd.notna(ma10_value) else entry_price)
        action_reason = "Position reached 1R; move stop to breakeven or MA10."
        partial_note = "No partial required, but remove downside risk."

    return {
        "gain_pct": round(gain_pct, 2) if pd.notna(gain_pct) else np.nan,
        "current_r": round(current_r, 2) if pd.notna(current_r) else np.nan,
        "position_pl": round(position_pl, 2),
        "suggested_action": suggested_action,
        "action_reason": action_reason,
        "suggested_stop": round(float(suggested_stop), 2) if pd.notna(suggested_stop) else np.nan,
        "partial_note": partial_note,
        "extended_from_ma10": round(extended_from_ma10, 2) if pd.notna(extended_from_ma10) else np.nan,
    }


def render_position_management(selected_ticker: str, selected_row: pd.Series, selected_data: pd.DataFrame | None, key_prefix: str) -> None:
    """Render the active-position management calculator for the selected ticker."""
    latest = selected_data.iloc[-1] if selected_data is not None and not selected_data.empty else None
    prior = selected_data.iloc[-2] if selected_data is not None and len(selected_data) >= 2 else latest
    default_current = pd.to_numeric(selected_row.get("Current Price", selected_row.get("close", np.nan)), errors="coerce")
    if pd.isna(default_current):
        default_current = pd.to_numeric(selected_row.get("close", 0), errors="coerce")

    with st.expander("Position Management Mode", expanded=False):
        st.caption("For active positions only. Enter your actual fill, current price, stop, and share size.")
        input_cols = st.columns(4)
        entry_price = input_cols[0].number_input(
            "Entry price",
            min_value=0.0,
            value=float(selected_row.get("Entry Trigger", 0.0)),
            step=0.01,
            key=f"{key_prefix}_{selected_ticker}_pm_entry",
        )
        current_price = input_cols[1].number_input(
            "Current price",
            min_value=0.0,
            value=float(default_current) if pd.notna(default_current) else 0.0,
            step=0.01,
            key=f"{key_prefix}_{selected_ticker}_pm_current",
        )
        stop_loss = input_cols[2].number_input(
            "Stop loss",
            min_value=0.0,
            value=float(selected_row.get("Stop Loss", 0.0)),
            step=0.01,
            key=f"{key_prefix}_{selected_ticker}_pm_stop",
        )
        position_size = input_cols[3].number_input(
            "Position size",
            min_value=0.0,
            value=100.0,
            step=1.0,
            key=f"{key_prefix}_{selected_ticker}_pm_size",
        )

        ma10 = float(latest["MA10"]) if latest is not None and pd.notna(latest.get("MA10", np.nan)) else np.nan
        prior_day_low = float(prior["Low"]) if prior is not None and pd.notna(prior.get("Low", np.nan)) else np.nan
        heavy_volume_ma10_break = bool(
            latest is not None
            and pd.notna(latest.get("MA10", np.nan))
            and pd.notna(latest.get("AvgVol20", np.nan))
            and latest["Close"] < latest["MA10"]
            and latest["Volume"] > 1.3 * latest["AvgVol20"]
        )
        management = manage_active_position(
            entry_price,
            current_price,
            stop_loss,
            position_size,
            ma10,
            prior_day_low,
            heavy_volume_ma10_break,
        )

        metric_cols = st.columns(5)
        metric_cols[0].metric("Current gain %", f"{management['gain_pct']:.2f}%" if pd.notna(management["gain_pct"]) else "N/A")
        metric_cols[1].metric("Current R", f"{management['current_r']:.2f}R" if pd.notna(management["current_r"]) else "Invalid risk")
        metric_cols[2].metric("Suggested action", management["suggested_action"])
        metric_cols[3].metric("Suggested stop", f"${management['suggested_stop']:.2f}" if pd.notna(management["suggested_stop"]) else "N/A")
        metric_cols[4].metric("Open P/L", f"${management['position_pl']:,.2f}")

        st.write(management["action_reason"])
        st.write(management["partial_note"])
        ma10_text = f"MA10: ${ma10:.2f}" if pd.notna(ma10) else "MA10: N/A"
        prior_low_text = f"Prior day low: ${prior_day_low:.2f}" if pd.notna(prior_day_low) else "Prior day low: N/A"
        st.caption(f"{ma10_text} | {prior_low_text}")


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
        default_market = "HK" if "HK" in title else "US"
        market_options = ["US", "HK", "Combined"]
        market_choice = st.selectbox(
            "Market",
            market_options,
            index=market_options.index(default_market),
            key=f"{key_prefix}_market_choice",
        )
        scanner_mode_kind = st.selectbox(
            "Scanner Mode",
            ["EOD Swing Scanner", "Live Breakout Scanner"],
            index=0,
            key=f"{key_prefix}_scanner_mode_kind",
            help="EOD is the fast default for nightly planning. Live Breakout is optional and only runs when selected.",
        )
        scan_depth = st.selectbox(
            "Scan Depth",
            ["Quick Scan (50)", "Normal Scan (150)", "Full Scan (500)"],
            index=0,
            key=f"{key_prefix}_scan_depth",
        )
        custom_tickers = st.text_area(
            "Custom Tickers",
            value="",
            height=120,
            key=f"{key_prefix}_custom_tickers",
            help="Optional. If filled, these tickers replace the selected market universe.",
        )

        if market_choice == "US":
            scan_mode = "US Pro Market Scan"
            preset_tickers = US_PRO_UNIVERSE
        elif market_choice == "HK":
            scan_mode = "HK Pro Market Scan"
            preset_tickers = HK_PRO_UNIVERSE
        else:
            scan_mode = "Combined US + HK Scan"
            preset_tickers = COMBINED_PRO_UNIVERSE

        tickers = normalize_tickers(custom_tickers) if custom_tickers.strip() else preset_tickers
        max_tickers = 50 if scan_depth.startswith("Quick") else 150 if scan_depth.startswith("Normal") else 500
        live_mode = scanner_mode_kind == "Live Breakout Scanner"
        is_hk_mode = market_choice == "HK"
        min_price = 1.0 if is_hk_mode else 10.0
        min_market_cap_b = 5.0
        min_dollar_volume_m = 20.0
        include_small_caps = False
        aggressive_mode = False
        show_all = False
        sector_filter = "All"
        only_ready_pullback = False
        only_trade_watchlist = False
        hide_extended = False
        only_a_setups = False
        hide_low_rs_non_vcp = True
        only_true_vcp = False
        only_early_vcp = False
        only_watchlist = False
        hide_resistance_blocked = False
        hide_reject = False
        only_strong_pullbacks = False
        auto_refresh = False
        show_position_management = False

        st.caption(f"{len(tickers)} tickers selected. This run will scan up to {max_tickers} symbols.")
        run_label = "Run Live Scan" if live_mode else "Run EOD Scan"
        run_scan = st.button(run_label, type="primary", width="stretch", key=f"{key_prefix}_run")
        run_live_scan = bool(live_mode and run_scan)
        force_refresh = False

    show_full_diagnostics = st.checkbox("Show full diagnostics", value=False, key=f"{key_prefix}_diagnostics")
    show_avoid_list = st.checkbox("Show Avoid List", value=False, key=f"{key_prefix}_show_avoid")

    if auto_refresh:
        st.components.v1.html("<script>setTimeout(() => window.parent.location.reload(), 60000);</script>", height=0)

    should_run_scan = run_scan or run_live_scan or force_refresh or (
        auto_refresh and f"{key_prefix}_results" in st.session_state and st.session_state.get(f"{key_prefix}_last_scan_mode") == scan_mode
    )
    active_live_mode = bool(live_mode and run_live_scan)

    if should_run_scan:
        if not tickers:
            st.info("Choose a preset universe or enter custom tickers.")
            return

        with st.spinner("Downloading daily data and preparing trade plans..."):
            clear_market_data_cache()
            results, indicator_data, summary = scan_universe(
                tickers=tickers,
                mode=scan_mode,
                min_price=min_price,
                min_market_cap=(0 if include_small_caps else min_market_cap_b * 1_000_000_000),
                min_dollar_volume=min_dollar_volume_m * 1_000_000,
                live_mode=active_live_mode,
                include_earnings=scan_depth.startswith("Full"),
                fetch_market_caps=not scan_depth.startswith("Quick"),
                use_live_sector_metadata=scan_depth.startswith("Full"),
                max_tickers=max_tickers,
                aggressive_mode=aggressive_mode,
            )
            results = validate_scan_results(results)
            append_trade_signal_history(results, scan_mode)
            st.session_state[f"{key_prefix}_results"] = results
            st.session_state[f"{key_prefix}_indicator_data"] = indicator_data
            st.session_state[f"{key_prefix}_summary"] = summary
            st.session_state[f"{key_prefix}_last_scan_mode"] = scan_mode
            st.session_state[f"{key_prefix}_last_scanner_mode_kind"] = "Live Breakout Scanner" if active_live_mode else "EOD Swing Scanner"

    if f"{key_prefix}_results" not in st.session_state:
        st.info("Choose a scan mode, adjust the filters, then run the scan for your daily watchlist.")
        st.caption(
            "For education and trade planning only. Not financial advice. Data may be delayed or inaccurate. "
            "Confirm live price and volume in your broker before trading."
        )
        return

    results = validate_scan_results(st.session_state.get(f"{key_prefix}_results", pd.DataFrame()))
    st.session_state[f"{key_prefix}_results"] = results
    indicator_data = st.session_state.get(f"{key_prefix}_indicator_data", {})
    summary = st.session_state.get(f"{key_prefix}_summary", {})
    required_result_columns = {
        "Trade",
        "Trade Reason",
        "Entry Type",
        "Sector / Industry",
        "Sector Group",
        "Theme Group",
        "RR Ratio",
        "RR Score",
        "Tightness Score",
        "Tightness Label",
        "RS Score",
        "RS Score Raw",
        "Sector Leadership",
        "Sector Leadership Status",
        "Volume Confirmation",
        "Earnings Risk",
        "Final Score",
        "Adjusted Final Score",
        "Professional Score",
        "Quality Score",
        "Execution Score",
        "Institutional Quality Score",
        "Theme Weight",
        "Executable Grade",
        "Executable Score",
        "Entry Timing Label",
        "MA10 Efficiency Score",
        "Character Change Flag",
        "Stage Label",
        "Pullback Quality",
        "VCP Tightness Score",
        "Tradeability Score",
        "Entry Quality Score",
        "Trade Tier",
        "Action Readiness Label",
        "Execution Confidence",
        "Buy Criteria Passed",
        "Buy Criteria Failed",
        "Blocked By",
        "Downgrade Reason",
        "Upgrade Reason",
        "Scanner Verdict",
        "Missing Condition",
        "Suggested Action",
        "Healthy Pullback Score",
        "Healthy Pullback Label",
        "Institutional Tightness Score",
        "Institutional Tightness Label",
        "Leader Quality Label",
        "Explosive Score",
        "Explosive Label",
        "Setup Quality Grade",
        "Setup Type",
        "Signal State",
        "Watch Type",
        "VCP Status",
        "VCP Label",
        "Contractions",
        "Volume Dry-Up",
        "Why Selected",
        "Decision Reason",
        "WATCHLIST FLAG",
        "Watchlist Reason",
        "Breakout Alert",
        "Earnings Date",
        "Days to Earnings",
        "Earnings Setup Score",
        "Target 1R",
        "TP1",
        "TP2",
        "TP3",
        "Nearest Resistance",
        "Ideal TP",
        "TP Type",
        "Ideal TP Reason",
        "Sell Strategy",
        "Trail Stop Level",
        "TP Quality Score",
        "Ideal TP R",
        "Risk Note",
        "Resistance Blocked",
        "Resistance Breakout Mode",
        "Breakout Above Resistance Trigger",
        "Resistance Breakout Entry",
        "Resistance Breakout Stop",
        "Resistance Breakout 1R",
        "Resistance Breakout 2R",
        "Resistance Breakout 3R",
        "Resistance Breakout Risk %",
        "Current Price",
        "% Change",
        "Premarket Price",
        "Afterhours Price",
        "Today's Volume",
        "Relative Volume",
        "RVOL",
        "RVOL Label",
        "Intraday Volume Ratio",
        "Live Breakout Status",
        "Alert Event",
        "Breakout Quality Score",
        "Market Environment",
        "Stage Analysis",
        "Institutional Action",
        "Earnings Intelligence",
        "1D Return %",
        "1W Return %",
        "52-week high",
        "Distance From High %",
        "Current Setup Status",
        "Last Updated",
        "Local Last Updated",
        "Market Session",
        "Latest Candle Date",
        "Dataframe Last Index",
        "Fetched Rows",
        "Quote Source",
        "Quote Time",
        "Quote Applied To Candle",
        "Data Stale",
        "Data Warning",
        "Chart Sync",
        "Chart/Quote Mismatch %",
        "AI Trading Notes",
    }

    if not results.empty and not required_result_columns.issubset(results.columns):
        st.session_state.pop(f"{key_prefix}_results", None)
        st.info("The scanner was upgraded with new decision fields. Run a fresh scan to rebuild the table.")
        return

    market_score = summary.get("market_score", 0)
    market_status = summary.get("market_status", "N/A")
    market_environment = summary.get("market_environment", "UPTREND UNDER PRESSURE")
    market_environment_details = summary.get("market_environment_details", "")
    sector_score = summary.get("sector_score", 0)
    session_status = summary.get("session_status", "N/A")
    market_timestamp = summary.get("market_timestamp", "N/A")
    local_timestamp = summary.get("local_timestamp", "N/A")

    market_tone = "normal" if market_environment == "CONFIRMED UPTREND" else "inverse" if market_environment == "CORRECTION" else "off"
    st.metric("Current Market Status", market_environment, market_environment_details, delta_color=market_tone)
    metric_cols = st.columns(6)
    metric_cols[0].metric("Market Status", market_status)
    metric_cols[1].metric("Market Score", f"{market_score}/4")
    metric_cols[2].metric("Distribution Days", summary.get("distribution_days", 0))
    metric_cols[3].metric("Follow Through Day", "YES" if summary.get("follow_through_day", False) else "NO")
    metric_cols[4].metric("Stocks Passed", len(results))
    metric_cols[5].metric("Mode", st.session_state.get(f"{key_prefix}_last_scanner_mode_kind", "EOD Swing Scanner"))

    state_summary_cols = st.columns(7)
    state_summary_cols[0].metric("BUY NOW", int((results["Signal State"] == "BUY NOW").sum()))
    state_summary_cols[1].metric("EARLY POSITION", int((results["Signal State"] == "EARLY POSITION").sum()))
    state_summary_cols[2].metric("BUY ON BREAKOUT", int((results["Signal State"] == "BUY ON BREAKOUT").sum()))
    state_summary_cols[3].metric("WATCH", int((results["Signal State"] == "WATCH").sum()))
    state_summary_cols[4].metric("WAIT PULLBACK", int((results["Signal State"] == "WAIT PULLBACK").sum()))
    state_summary_cols[5].metric("EXTENDED", int((results["Signal State"] == "EXTENDED DO NOT CHASE").sum()))
    state_summary_cols[6].metric("REJECT", int((results["Signal State"] == "REJECT").sum()))

    buy_now_count = int((results["Signal State"] == "BUY NOW").sum())
    early_position_count = int((results["Signal State"] == "EARLY POSITION").sum())
    if buy_now_count:
        st.success("Best Action Today: There are actionable setups today.")
    elif early_position_count:
        st.info("Best Action Today: Only pilot-position setups today. Use smaller size.")
    else:
        st.info("Best Action Today: No clean entry today. Build watchlist and wait.")

    dashboard_cols = st.columns(7)
    dashboard_cols[0].metric("Trade YES", int((results["Trade"] == "YES").sum()))
    dashboard_cols[1].metric("Watchlist", int((results["WATCHLIST FLAG"] == "YES").sum()))
    dashboard_cols[2].metric("Live Breakouts", int((results["Live Breakout Status"] == "LIVE BREAKOUT").sum()))
    dashboard_cols[3].metric("Near Breakouts", int((results["Breakout Alert"] == "NEAR BREAKOUT").sum()))
    dashboard_cols[4].metric("Confirmed Breakouts", int((results["Breakout Alert"] == "CONFIRMED BREAKOUT").sum()))
    dashboard_cols[5].metric("Earnings Risk", int((results["Earnings Risk"] == "HIGH RISK").sum()))
    best_sector = results.groupby("Sector ETF")["Final Score"].mean().sort_values(ascending=False).index[0] if not results.empty else "N/A"
    dashboard_cols[6].metric("Best Sector", best_sector)
    high_earnings_count = int((results["Earnings Risk"] == "HIGH RISK").sum())
    if high_earnings_count:
        st.warning(f"Earnings risk active: {high_earnings_count} stocks report within 7 days.")
    extended_note = "Premarket data included" if session_status == "PREMARKET" else "Afterhours data included" if session_status == "AFTER HOURS" else session_status
    st.caption(f"Last updated: {market_timestamp} | Local: {local_timestamp} | Session: {session_status} | {extended_note}")
    stale_count = int((results["Data Stale"] == "YES").sum()) if "Data Stale" in results else 0
    sync_error_count = int((results["Chart Sync"] == "Chart sync error").sum()) if "Chart Sync" in results else 0
    if stale_count:
        st.warning(f"Data stale - refresh required: {stale_count} ticker(s) have latest candles older than one trading day.")
    if sync_error_count:
        st.error(f"Chart sync error: {sync_error_count} ticker(s) have quote/chart mismatch above 2%.")
    if int((results["Trade"] == "YES").sum()) == 0:
        st.warning("No BUY NOW today.")
        blocked_text = results.get("Blocked By", pd.Series("", index=results.index)).astype(str)
        failed_text = results.get("Buy Criteria Failed", pd.Series("", index=results.index)).astype(str)
        timing_text = results.get("Entry Timing Label", pd.Series("", index=results.index)).astype(str)
        blocker_counts = {
            "Risk > 12%": int(failed_text.str.contains("Risk <= 12%", case=False, na=False).sum()),
            "Extended MA10/MA20": int(timing_text.isin(["EXTENDED - WAIT", "TOO LATE"]).sum()),
            "Earnings Risk": int(blocked_text.str.contains("Earnings Risk", case=False, na=False).sum()),
            "Weak RS": int(failed_text.str.contains("RS >= 8", case=False, na=False).sum()),
            "Character Change": int(blocked_text.str.contains("Character Change", case=False, na=False).sum()),
            "Volume only": int(results.get("Missing Condition", pd.Series("", index=results.index)).astype(str).str.contains("Volume confirmation missing", case=False, na=False).sum()),
        }
        blocker_cols = st.columns(6)
        for col, (label, count) in zip(blocker_cols, blocker_counts.items()):
            col.metric(label, count)
        if blocker_counts["Volume only"]:
            st.warning("Scanner may be too strict if volume-only blocks many high-quality leaders.")

    qualified = results[
        (results["Setup Quality Grade"].isin(["A+", "A", "B"]))
        & (results["Action Label"] != "FAILED")
        & (results["Setup Quality Grade"] != "Reject")
    ].copy()
    if not qualified.empty:
        qualified["RS Summary Score"] = pd.to_numeric(qualified.get("RS Score Raw", qualified.get("RS Score")), errors="coerce")
        sector_summary = (
            qualified.groupby("Sector Group", dropna=False)
            .agg(
                qualified_setups=("ticker", "count"),
                buy_now_setups=("Signal State", lambda values: int((values == "BUY NOW").sum())),
                avg_today_return=("1D Return %", lambda values: pd.to_numeric(values, errors="coerce").mean()),
                avg_week_return=("1W Return %", lambda values: pd.to_numeric(values, errors="coerce").mean()),
                avg_rs_score=("RS Summary Score", "mean"),
                avg_explosive_score=("Explosive Score", "mean"),
                avg_final_score=("Final Score", "mean"),
            )
            .reset_index()
            .sort_values(["avg_week_return", "avg_rs_score", "buy_now_setups"], ascending=[False, False, False])
        )
        strongest_sector = sector_summary.iloc[0]["Sector Group"]
        strongest_today = sector_summary.sort_values("avg_today_return", ascending=False).iloc[0]["Sector Group"]
        strongest_week = sector_summary.sort_values("avg_week_return", ascending=False).iloc[0]["Sector Group"]
        st.subheader("Sector Strength Summary")
        st.caption(f"Strongest sector today: {strongest_today} | Strongest sector this week: {strongest_week} | Overall leadership: {strongest_sector}")
        st.dataframe(
            round_display_values(
                sector_summary.rename(
                    columns={
                        "Sector Group": "Sector",
                        "qualified_setups": "Qualified Setups",
                        "buy_now_setups": "BUY NOW Setups",
                        "avg_today_return": "Avg Today %",
                        "avg_week_return": "Avg Week %",
                        "avg_rs_score": "Avg RS Score",
                        "avg_explosive_score": "Avg Explosive Score",
                        "avg_final_score": "Avg Final Score",
                    }
                )
            ),
            width="stretch",
            hide_index=True,
        )
        theme_summary = (
            qualified.groupby("Theme Group", dropna=False)
            .agg(
                buy_now_setups=("Signal State", lambda values: int((values == "BUY NOW").sum())),
                avg_today_return=("1D Return %", lambda values: pd.to_numeric(values, errors="coerce").mean()),
                avg_week_return=("1W Return %", lambda values: pd.to_numeric(values, errors="coerce").mean()),
                avg_rs_score=("RS Summary Score", "mean"),
                avg_breakout_quality=("Breakout Quality Score", "mean"),
            )
            .reset_index()
            .sort_values(["avg_week_return", "avg_breakout_quality", "buy_now_setups"], ascending=[False, False, False])
        )
        st.caption("Sector rotation engine: strongest themes by week, breakout quality, and BUY NOW count.")
        st.dataframe(
            round_display_values(
                theme_summary.rename(
                    columns={
                        "Theme Group": "Theme",
                        "buy_now_setups": "BUY NOW Setups",
                        "avg_today_return": "Avg Today %",
                        "avg_week_return": "Avg Week %",
                        "avg_rs_score": "Avg RS Score",
                        "avg_breakout_quality": "Avg Breakout Quality",
                    }
                )
            ),
            width="stretch",
            hide_index=True,
        )

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
    visible["RS Sort"] = pd.to_numeric(visible.get("RS Score Raw", visible.get("RS Score")), errors="coerce")
    visible["RVOL Sort"] = pd.to_numeric(visible.get("RVOL"), errors="coerce")
    if not show_all:
        visible = visible[
            (visible["Trend Score"] >= 4)
            & (visible["Technical Score"] >= 4)
        ]
    if sector_filter != "All":
        visible = visible[visible["Sector Group"] == sector_filter]
    if only_ready_pullback:
        visible = visible[visible["Signal State"].isin(["BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT"]) | visible["Action Label"].isin(["PULLBACK ENTRY"])]
    if only_trade_watchlist:
        visible = visible[(visible["Trade"] == "YES") | (visible["WATCHLIST FLAG"] == "YES")]
    if hide_extended:
        visible = visible[visible["Signal State"] != "EXTENDED DO NOT CHASE"]
    if only_a_setups:
        visible = visible[visible["Setup Quality Grade"].isin(["A+", "A"])]
    if hide_low_rs_non_vcp:
        visible = visible[~((visible["VCP Status"] == "NOT VCP") & (visible["RS Sort"].notna()) & (visible["RS Sort"] < 5))]
    if only_true_vcp:
        visible = visible[visible["VCP Status"].isin(["VALID VCP", "EARLY VCP"])]
    if only_early_vcp:
        visible = visible[visible["VCP Status"] == "EARLY VCP"]
    if only_watchlist:
        visible = visible[visible["WATCHLIST FLAG"] == "YES"]
    if hide_resistance_blocked:
        visible = visible[visible["Resistance Blocked"] != "YES"]
    if hide_reject:
        visible = visible[(visible["Setup Quality Grade"] != "Reject") & (visible["Signal State"] != "REJECT")]
    if only_strong_pullbacks:
        visible = visible[(visible["Action Label"] == "PULLBACK ENTRY") & (visible["RS Sort"] >= 6)]

    signal_priority = SIGNAL_STATE_PRIORITY
    quality_priority = {"A+": 0, "A": 1, "B": 2, "C": 3, "Reject": 4}
    visible["tier sort"] = visible.get("Trade Tier", pd.Series("", index=visible.index)).map(TRADE_TIER_PRIORITY).fillna(9)
    visible["trade sort"] = np.where(visible["Trade"] == "YES", 0, 1)
    visible["signal sort"] = visible["Signal State"].map(signal_priority).fillna(9)
    visible["quality sort"] = visible["Setup Quality Grade"].map(quality_priority).fillna(9)
    visible["stage sort"] = visible.get("Stage Label", pd.Series("", index=visible.index)).map(STAGE_SORT_PRIORITY).fillna(9)
    visible["sector leadership sort"] = visible["Sector Leadership"].map({"Leader": 0, "Average": 1, "Laggard": 2}).fillna(3)
    visible["sector status sort"] = visible.get("Sector Leadership Status", pd.Series("", index=visible.index)).map(
        {"LEADING SECTOR": 0, "IMPROVING SECTOR": 1, "NEUTRAL SECTOR": 2, "CYCLICAL RISK": 3, "LAGGING SECTOR": 4}
    ).fillna(3)
    visible["executable sort"] = visible.get("Executable Grade", pd.Series("", index=visible.index)).map(
        {"A - EXECUTABLE NOW": 0, "B - WATCHLIST": 1, "C - AVOID": 2}
    ).fillna(3)
    visible["wait quality sort"] = np.where(
        (visible["Signal State"] == "WAIT PULLBACK")
        & (visible.get("Leader Quality Label", pd.Series("", index=visible.index)).isin(["INSTITUTIONAL LEADER", "SECTOR LEADER", "MOMENTUM LEADER"])),
        0,
        np.where(visible["Signal State"] == "WAIT PULLBACK", 1, 0),
    )
    visible["execution quality sort"] = (
        pd.to_numeric(visible.get("Entry Quality Score"), errors="coerce").fillna(0)
        + pd.to_numeric(visible.get("Institutional Tightness Score"), errors="coerce").fillna(0)
        + pd.to_numeric(visible.get("Healthy Pullback Score"), errors="coerce").fillna(0)
        + pd.to_numeric(visible.get("Breakout Quality Score"), errors="coerce").fillna(0)
        - (pd.to_numeric(visible.get("MA10 Distance %"), errors="coerce").fillna(0).clip(lower=0) / 3)
    )
    visible = visible.sort_values(
        [
            "trade sort",
            "signal sort",
            "Adjusted Final Score",
            "Professional Score",
            "RS Sort",
            "Risk %",
            "Breakout Quality Score",
        ],
        ascending=[True, True, False, False, False, True, False],
    )

    compact_columns = [
        "ticker",
        "Sector / Industry",
        "close",
        "Signal State",
        "Execution Confidence",
        "Setup Quality Grade",
        "Stage Label",
        "Pullback Quality",
        "VCP Tightness Score",
        "Tradeability Score",
        "Execution Score",
        "Quality Score",
        "Final Score",
        "RS Score",
        "Risk %",
        "Entry Trigger",
        "Stop Loss",
        "Ideal TP",
        "Decision Reason",
        "Scanner Verdict",
        "Buy Criteria Passed",
        "Buy Criteria Failed",
        "Blocked By",
        "Upgrade Reason",
        "Downgrade Reason",
        "Leader Quality Label",
        "Executable Grade",
        "Executable Score",
        "Entry Timing Label",
        "Trade",
        "Setup Type",
        "Watch Type",
        "Adjusted Final Score",
        "Institutional Quality Score",
        "Theme Weight",
        "MA10 Efficiency Score",
        "Character Change Flag",
        "Pivot",
        "Sector Leadership Status",
        "Trade Tier",
        "Action Readiness Label",
        "Missing Condition",
        "Suggested Action",
        "Professional Score",
        "Entry Quality Score",
        "Healthy Pullback Score",
        "Institutional Tightness Score",
        "Breakout Quality Score",
        "TP1",
        "TP2",
        "TP3",
        "TP Type",
    ]
    diagnostic_columns = compact_columns + [
        "% Change",
        "Sector Group",
        "Theme Group",
        "Sector Raw",
        "Industry Raw",
        "VCP Label",
        "Contractions",
        "Volume Dry-Up",
        "Trend Score",
        "Technical Score",
        "Tightness Score",
        "Healthy Pullback Label",
        "Institutional Tightness Label",
        "Sector Leadership Weight",
        "Final Score",
        "Explosive Score",
        "RS Score Raw",
        "Intraday Volume Ratio",
        "RVOL Label",
        "Alert Event",
        "Market Environment",
        "1D Return %",
        "1W Return %",
        "Entry Type",
        "Action Label",
        "Breakout Alert",
        "Current Price",
        "Current Setup Status",
        "Nearest Resistance",
        "Resistance Blocked",
        "Resistance Breakout Mode",
        "Breakout Above Resistance Trigger",
        "Ideal TP Reason",
        "Sell Strategy",
        "Trail Stop Level",
        "TP Quality Score",
        "Data Warning",
        "Chart Sync",
        "Why Selected",
        "Premarket Price",
        "Afterhours Price",
        "Today's Volume",
        "Relative Volume",
        "52-week high",
        "Distance From High %",
        "Explosive Label",
        "Earnings Date",
        "Earnings Risk",
        "Earnings Setup Score",
        "RR Score",
        "Pivot",
        "Resistance Breakout Entry",
        "Resistance Breakout Stop",
        "Resistance Breakout 1R",
        "Resistance Breakout 2R",
        "Resistance Breakout 3R",
        "Resistance Breakout Risk %",
        "Ideal TP R",
        "Risk Note",
        "AI Trading Notes",
        "market cap",
        "avg dollar volume",
        "RSI",
        "Sector Score",
        "Sector ETF",
        "Sector Leadership",
        "Market Score",
        "volume contraction",
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
        "Last Updated",
        "Local Last Updated",
        "Market Session",
        "Latest Candle Date",
        "Dataframe Last Index",
        "Fetched Rows",
        "Quote Source",
        "Quote Time",
        "Quote Applied To Candle",
        "Data Stale",
        "Chart/Quote Mismatch %",
        "Notes",
    ]
    compact_columns = list(dict.fromkeys(compact_columns))
    diagnostic_columns = list(dict.fromkeys(diagnostic_columns))
    display_columns = compact_columns
    export_columns = diagnostic_columns if show_full_diagnostics else compact_columns

    focus_source = results.copy()
    focus_source["RS Sort"] = pd.to_numeric(focus_source.get("RS Score Raw", focus_source.get("RS Score")), errors="coerce")
    focus_source["signal sort"] = focus_source["Signal State"].map(signal_priority).fillna(9)
    focus_source["trade sort"] = np.where(focus_source["Trade"] == "YES", 0, 1)
    focus_source["watchlist sort"] = np.where(focus_source["WATCHLIST FLAG"] == "YES", 0, 1)
    focus_source["quality sort"] = focus_source["Setup Quality Grade"].map(quality_priority).fillna(9)
    focus_source["tier sort"] = focus_source.get("Trade Tier", pd.Series("", index=focus_source.index)).map(TRADE_TIER_PRIORITY).fillna(9)
    focus_source["Professional Score Sort"] = pd.to_numeric(focus_source.get("Professional Score"), errors="coerce").fillna(0)
    focus_source["Entry Quality Sort"] = pd.to_numeric(focus_source.get("Entry Quality Score"), errors="coerce").fillna(0)
    focus_source["Final Score Sort"] = pd.to_numeric(focus_source.get("Final Score"), errors="coerce").fillna(0)
    focus_source["VCP Tightness Sort"] = pd.to_numeric(focus_source.get("VCP Tightness Score"), errors="coerce").fillna(0)
    focus_source["Tradeability Sort"] = pd.to_numeric(focus_source.get("Tradeability Score"), errors="coerce").fillna(0)

    buy_now_focus = focus_source[focus_source["Signal State"] == "BUY NOW"].sort_values(
        ["quality sort", "Final Score Sort", "VCP Tightness Sort", "Tradeability Sort", "RS Sort", "Risk %"],
        ascending=[True, False, False, False, False, True],
    )
    early_position_focus = focus_source[focus_source["Signal State"] == "EARLY POSITION"].sort_values(
        ["quality sort", "Professional Score Sort", "Entry Quality Sort", "RS Sort", "Risk %"],
        ascending=[True, False, False, False, True],
    )
    buy_breakout_focus = focus_source[focus_source["Signal State"] == "BUY ON BREAKOUT"].sort_values(
        ["quality sort", "Final Score Sort", "VCP Tightness Sort", "Tradeability Sort", "RS Sort", "Risk %"],
        ascending=[True, False, False, False, False, True],
    )
    watchlist_focus = focus_source[
        (focus_source["Signal State"] == "WATCH")
        & (focus_source["Setup Type"] != "MOMENTUM BREAKOUT EXCEPTION")
        & (focus_source["Setup Type"] != "RESISTANCE BREAKOUT WATCH")
    ].sort_values(
        ["quality sort", "Final Score Sort", "VCP Tightness Sort", "Tradeability Sort", "RS Sort", "Risk %"],
        ascending=[True, False, False, False, False, True],
    )
    healthy_pullback_focus = focus_source[
        focus_source.get("Pullback Quality", pd.Series("", index=focus_source.index)).isin(["CLEAN MA10 PULLBACK", "CLEAN MA20 RESET", "TIGHT FLAG"])
        | (focus_source.get("Healthy Pullback Label", pd.Series("", index=focus_source.index)) == "HEALTHY PULLBACK")
    ].sort_values(
        ["signal sort", "quality sort", "Final Score Sort", "VCP Tightness Sort", "Tradeability Sort", "RS Sort", "Risk %"],
        ascending=[True, True, False, False, False, False, True],
    )
    extended_focus = focus_source[
        focus_source["Signal State"].isin(["WAIT PULLBACK", "EXTENDED DO NOT CHASE"])
        & (
            focus_source.get("Entry Timing Label", pd.Series("", index=focus_source.index)).isin(["EXTENDED - WAIT", "TOO LATE"])
            | focus_source.get("Stage Label", pd.Series("", index=focus_source.index)).isin(["LATE STAGE 2", "CLIMAX / PARABOLIC"])
        )
    ].sort_values(
        ["quality sort", "Final Score Sort", "Institutional Quality Score", "RS Sort", "Risk %"],
        ascending=[True, False, False, False, True],
    )
    rejected_focus = focus_source[
        (focus_source["Signal State"] == "REJECT")
        | (focus_source["Setup Quality Grade"] == "Reject")
        | (focus_source["Action Label"] == "FAILED")
        | (focus_source.get("Executable Grade", pd.Series("", index=focus_source.index)) == "C - AVOID")
    ].sort_values(
        ["quality sort", "Risk %", "Final Score Sort"],
        ascending=[True, True, False],
    )
    closest_to_action_focus = focus_source[
        (focus_source["Trade Tier"] == "Tier 2 - High Quality, Wait Better Entry")
        & (focus_source["Professional Score Sort"] >= 80)
        & (focus_source["Entry Quality Sort"] >= 5)
        & (focus_source["RS Sort"] >= 7)
        & (focus_source["Signal State"] != "EXTENDED DO NOT CHASE")
    ].sort_values(
        ["Professional Score Sort", "Entry Quality Sort", "Institutional Quality Score", "RS Sort", "Risk %"],
        ascending=[False, False, False, False, True],
    )
    almost_buy_focus = focus_source[
        focus_source.get("Missing Condition", pd.Series("None", index=focus_source.index)).astype(str).ne("None")
    ].sort_values(
        ["Professional Score Sort", "Adjusted Final Score", "RS Sort", "Risk %"],
        ascending=[False, False, False, True],
    )

    st.subheader("Daily Focus Summary")
    if buy_now_focus.empty:
        st.info("No clean BUY NOW today. Best action: wait. Watchlist candidates below.")
    focus_cols = st.columns(4)
    with focus_cols[0]:
        show_focus_group("Top BUY NOW", buy_now_focus, "Decision Reason")
    with focus_cols[1]:
        show_focus_group("Top EARLY POSITION", early_position_focus, "Decision Reason")
    with focus_cols[2]:
        show_focus_group("Top BUY ON BREAKOUT", buy_breakout_focus, "Decision Reason")
    with focus_cols[3]:
        show_focus_group("Top Watchlist", watchlist_focus, "Decision Reason")
    extra_focus_cols = st.columns(3)
    with extra_focus_cols[0]:
        show_focus_group("Best Healthy Pullbacks", healthy_pullback_focus, "Decision Reason")
    with extra_focus_cols[1]:
        show_focus_group("High Quality But Extended", extended_focus, "Decision Reason")
    with extra_focus_cols[2]:
        show_focus_group("Reject / Avoid", rejected_focus, "Decision Reason")
    show_focus_group("Closest To Action", closest_to_action_focus, "Decision Reason")
    if not almost_buy_focus.empty:
        st.subheader("Top Almost Buy Setups")
        almost_buy_columns = [
            "ticker",
            "Sector / Industry",
            "Signal State",
            "Final Score",
            "Adjusted Final Score",
            "Professional Score",
            "RS Score",
            "Risk %",
            "Missing Condition",
            "Suggested Action",
        ]
        st.dataframe(round_display_values(almost_buy_focus.head(10)[almost_buy_columns]), width="stretch", hide_index=True)

    st.subheader("Action View")
    actionable_states = ["BUY NOW", "EARLY POSITION", "BUY ON BREAKOUT", "WATCH", "WAIT PULLBACK"]
    avoid_states = ["EXTENDED DO NOT CHASE", "REJECT"]
    action_view = visible[visible["Signal State"].isin(actionable_states)].copy()
    avoid_view = visible[visible["Signal State"].isin(avoid_states)].copy()

    if action_view.empty:
        st.info("No actionable setups match the current display filters.")
    else:
        for state, expanded in [
            ("BUY NOW", True),
            ("EARLY POSITION", True),
            ("BUY ON BREAKOUT", True),
            ("WATCH", True),
            ("WAIT PULLBACK", False),
        ]:
            group = action_view[action_view["Signal State"] == state]
            if group.empty:
                continue
            with st.expander(f"{state} ({len(group)})", expanded=expanded):
                table_display = round_display_values(group[display_columns])
                styled_table = table_display.style.apply(style_scan_table, axis=1)
                st.dataframe(styled_table, width="stretch", hide_index=True)

    if show_avoid_list and not avoid_view.empty:
        with st.expander(f"Avoid List - EXTENDED / REJECT ({len(avoid_view)})", expanded=False):
            table_display = round_display_values(avoid_view[display_columns])
            styled_table = table_display.style.apply(style_scan_table, axis=1)
            st.dataframe(styled_table, width="stretch", hide_index=True)
    elif not show_avoid_list and not avoid_view.empty:
        st.caption(f"{len(avoid_view)} EXTENDED / REJECT rows hidden. Enable Show Avoid List to review them.")

    export_source = visible
    export_frame = round_display_values(export_source[display_columns])
    if show_full_diagnostics:
        with st.expander("Full diagnostics", expanded=False):
            st.dataframe(round_display_values(export_source[diagnostic_columns]), width="stretch", hide_index=True)
        export_frame = round_display_values(export_source[export_columns])
    st.download_button(
        "Export scanner table CSV",
        data=export_frame.to_csv(index=False).encode("utf-8"),
        file_name=f"{key_prefix}_vcp_scan.csv",
        mime="text/csv",
        width="stretch",
    )
    st.download_button(
        "Export scanner table PDF",
        data=dataframe_to_simple_pdf(export_frame, f"{title} Export"),
        file_name=f"{key_prefix}_vcp_scan.pdf",
        mime="application/pdf",
        width="stretch",
    )

    selectable = visible if not visible.empty else results
    selected_ticker = st.selectbox("Review ticker", selectable["ticker"].tolist(), key=f"{key_prefix}_review")
    selected_row = results[results["ticker"] == selected_ticker].iloc[0]
    selected_data = indicator_data.get(selected_ticker)

    st.subheader("Live Quote & Data Sync")
    live_cols = st.columns(6)
    live_cols[0].metric("Current Price", f"${float(selected_row['Current Price']):.2f}" if pd.to_numeric(selected_row["Current Price"], errors="coerce") == pd.to_numeric(selected_row["Current Price"], errors="coerce") else "N/A", selected_row["% Change"])
    live_cols[1].metric("Premarket", selected_row["Premarket Price"])
    live_cols[2].metric("Afterhours", selected_row["Afterhours Price"])
    live_cols[3].metric("52W High", selected_row["52-week high"], f"{selected_row['Distance From High %']}%")
    live_cols[4].metric("Volume", selected_row["Today's Volume"], f"RelVol {selected_row['Relative Volume']}")
    live_cols[5].metric("Setup Status", selected_row["Current Setup Status"])
    breakout_cols = st.columns(5)
    breakout_cols[0].metric("Live Breakout", selected_row.get("Live Breakout Status", "N/A"))
    breakout_cols[1].metric("RVOL", selected_row.get("RVOL", "N/A"), selected_row.get("RVOL Label", ""))
    breakout_cols[2].metric("Intraday Volume Ratio", selected_row.get("Intraday Volume Ratio", "N/A"))
    breakout_cols[3].metric("Breakout Quality", f"{selected_row.get('Breakout Quality Score', 'N/A')}/10")
    breakout_cols[4].metric("Stage", selected_row.get("Stage Analysis", "N/A"))
    st.caption(
        f"Latest candle: {selected_row['Latest Candle Date']} | Dataframe last index: {selected_row['Dataframe Last Index']} | "
        f"Rows: {selected_row['Fetched Rows']} | Quote source: {selected_row['Quote Source']} | Quote time: {selected_row['Quote Time']} | "
        f"Quote applied to candle: {selected_row['Quote Applied To Candle']}"
    )
    if selected_row["Data Stale"] == "YES":
        st.warning("Data stale - refresh required")
    if selected_row["Chart Sync"] == "Chart sync error":
        st.error(f"Chart sync error: latest quote and chart close differ by {selected_row['Chart/Quote Mismatch %']}%.")

    chart_col, plan_col = st.columns([2, 1])
    with chart_col:
        if selected_data is not None and not selected_data.empty:
            st.plotly_chart(make_chart(selected_ticker, selected_data, selected_row), width="stretch")

    with plan_col:
        st.subheader("Trade Plan")
        st.metric("Signal State", selected_row["Signal State"])
        st.metric("Setup Type", selected_row["Setup Type"])
        st.metric("Breakout Quality", f"{selected_row.get('Breakout Quality Score', 'N/A')}/10", selected_row.get("Live Breakout Status", "N/A"))
        st.metric("Institutional Action", selected_row.get("Institutional Action", "N/A"))
        st.metric("Action", selected_row["Action Label"])
        st.metric("Trade", selected_row["Trade"], selected_row["Trade Reason"])
        st.metric("Entry Type", selected_row["Entry Type"])
        st.metric("Decision", selected_row["VCP Label"], selected_row["Decision Reason"])
        st.metric("Setup Quality", selected_row["Setup Quality Grade"], selected_row["Why Selected"])
        st.metric("Explosive Score", f"{selected_row['Explosive Score']}/10", selected_row["Explosive Label"])
        st.metric("Watchlist", selected_row["WATCHLIST FLAG"], selected_row["Watchlist Reason"])
        st.metric("Final Score", f"{selected_row['Final Score']:.1f}/100")
        st.metric("Entry Trigger", f"${selected_row['Entry Trigger']:.2f}")
        st.metric("Stop Loss", f"${selected_row['Stop Loss']:.2f}", f"Risk {selected_row['Risk %']:.2f}% - {selected_row['Risk Note']}")
        st.metric("Ideal TP", f"${selected_row['Ideal TP']:.2f}", selected_row["Ideal TP Reason"])
        st.metric("TP Quality", f"{selected_row['TP Quality Score']}/10", f"{selected_row['Ideal TP R']:.2f}R available")
        st.metric("Targets", f"1R ${selected_row['Target 1R']:.2f}", f"2R ${selected_row['Target 2R']:.2f} / 3R ${selected_row['Target 3R']:.2f}")
        st.metric("Trail Stop", f"${selected_row['Trail Stop Level']:.2f}", selected_row["Sell Strategy"])
        st.write(f"Sector / Industry: {selected_row['Sector / Industry']}")
        st.write(f"RS Score: {selected_row['RS Score']}/10")
        st.write(f"Sector: {selected_row['Sector Leadership']} vs {selected_row['Sector ETF']}")
        st.write(f"Volume confirmation: {selected_row['Volume Confirmation']}")
        st.write(f"Earnings: {selected_row['Earnings Risk']}")
        st.write(f"RR: {selected_row['RR Ratio']} ({selected_row['RR Score']})")
        st.write(f"Nearest resistance: ${selected_row['Nearest Resistance']:.2f}")
        if selected_row["Resistance Breakout Mode"] == "RESISTANCE BREAKOUT WATCH":
            st.write(
                f"Resistance breakout trigger: ${selected_row['Breakout Above Resistance Trigger']:.2f}; "
                f"new stop ${selected_row['Resistance Breakout Stop']:.2f}; "
                f"new 1R/2R/3R ${selected_row['Resistance Breakout 1R']:.2f}/"
                f"${selected_row['Resistance Breakout 2R']:.2f}/${selected_row['Resistance Breakout 3R']:.2f}"
            )
        st.write(f"Tightness: {selected_row['Tightness Score']}/5, {selected_row['Tightness Label']}")
        st.write(f"VCP: {selected_row['VCP Status']} ({selected_row['Contractions']})")
        st.write(f"Pivot: ${selected_row['Pivot']:.2f}, distance {selected_row['Distance to Pivot %']:.2f}%")
        st.write(f"MA distance: MA10 {selected_row['MA10 Distance %']:.2f}%, MA20 {selected_row['MA20 Distance %']:.2f}%")
        st.write(selected_row["Notes"])

    if show_position_management:
        render_position_management(selected_ticker, selected_row, selected_data, key_prefix)

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
            padding: 14px 16px;
            min-height: 128px;
            overflow: visible;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 8px;
        }
        [data-testid="stMetric"] [data-testid="stMetricLabel"] p {
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
            line-height: 1.2;
        }
        [data-testid="stMetric"] [data-testid="stMetricValue"] {
            font-size: clamp(1.25rem, 1.8vw, 2.35rem);
            line-height: 1.08;
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
            overflow-wrap: normal;
            word-break: normal;
            max-width: 100%;
        }
        [data-testid="stMetric"] [data-testid="stMetricValue"] > div,
        [data-testid="stMetric"] [data-testid="stMetricValue"] p {
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
            overflow-wrap: normal;
            word-break: normal;
            max-width: 100%;
        }
        [data-testid="stMetric"] [data-testid="stMetricDelta"] {
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
            max-width: 100%;
            align-items: flex-start;
            line-height: 1.2;
        }
        [data-testid="stMetric"] [data-testid="stMetricDelta"] p,
        [data-testid="stMetric"] [data-testid="stMetricDelta"] div {
            white-space: normal;
            overflow: visible;
            text-overflow: clip;
            overflow-wrap: anywhere;
            max-width: 100%;
        }
        [data-testid="column"] [data-testid="stMetric"] {
            height: 100%;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("IPO + Swing Pro Scanner")
    st.caption("Daily swing-trading scanner plus IPO grey-market scoring and trade planning.")

    us_tab, hk_tab, positions_tab, ipo_tab, top5_tab, alerts_tab, settings_tab = st.tabs(
        ["US Scanner", "HK Scanner", "My Positions", "IPO Scanner", "Top 5 Trades", "Alerts", "Settings"]
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
    with positions_tab:
        render_my_positions()
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
