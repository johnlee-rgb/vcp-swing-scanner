# VCP Swing Scanner

A practical Streamlit app for end-of-day US stock swing-trading preparation using VCP / J Law / Minervini-style checks.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What It Does

- Scans curated preset universes across semiconductors, power infrastructure, cloud/software, cybersecurity, data centers, automation, uranium, energy, defense, financials, healthcare growth, consumer growth, industrials, crypto stocks, and a combined Market Leaders 300 list.
- Supports custom ticker input.
- Downloads at least 18 months of daily OHLCV data with `yfinance`.
- Applies quality pre-filters for price, market cap, average volume, and average dollar volume.
- Calculates MA10, MA20, MA50, MA150, MA200, RSI 14, ATR 14, 20/50-day average volume, 52-week high/low, 20-day high, 10-day low, and relative strength versus SPY.
- Scores market condition, sector strength, Minervini-style trend, and VCP / entry timing separately.
- Scores relative strength versus SPY and QQQ, sector leadership versus the mapped ETF, earnings risk, volume confirmation, and a 0-100 final decision score.
- Auto-detects pivots, breakout triggers, VCP contractions, extension risk, and action labels.
- Produces trade-plan levels: entry trigger, stop loss, risk %, 2R target, 3R target, and invalidation notes.
- Highlights READY, PULLBACK ENTRY, WATCH, EXTENDED, and FAILED rows with different colors.
- Shows a selected ticker chart with candlesticks, MA10, MA20, MA50, volume, pivot, entry, stop, and target lines.

This is built for daily end-of-day swing-trading preparation, not real-time intraday trading.

## vNext Correctness and Research

US Scanner remains the default. Legacy scoring, VCP detection, ranking and
download helpers are retained. Final Trade eligibility is independently gated:
READY, dry-up and a high score are not a confirmed breakout. New fields expose
WATCH / ARMED / TRIGGERED / CONFIRMED / INVALIDATED, precise Final Action,
eligibility blockers and next-session execution assumptions. A confirmed daily
candidate is not an already-executed order.

Additional tabs: Market Risk, MET-A Research, Combined Watchlist,
Backtest / Replay and Data Health. MET-A is permanently research/watch-only
in this version; disable its display with Enable MET-A research. No trading
API is connected. Existing CSV/PDF/text buttons remain below ticker review.
Legacy CSV fields remain; new fields are appended to the displayed export
schema. Name-based consumers should ignore unfamiliar fields; positional CSV
consumers must adopt the documented vnext-1 schema before upgrading.

Run tests and compilation:

```bash
python -m pip install -r requirements.txt pytest
python -m py_compile app.py
python -m pytest -q
streamlit run app.py --server.port 8572
```

See [configuration](docs/VNEXT_CONFIGURATION.md),
[audit](docs/VNEXT_AUDIT.md), [implementation report](docs/VNEXT_IMPLEMENTATION_REPORT.md)
and [tracking/Telegram deployment](docs/SIGNAL_TRACKING.md).
No schedule or deployment is activated by running the UI. Keep credentials
out of GitHub. Local SQLite is not durable cloud storage.
