# VCP Swing Scanner

## 私人雲端版本（2026-10-29）

雲端結果入口：https://vcp-cloud-research.john-lee-5f2.workers.dev/

呢個係同一套 Python scanner 嘅已保存結果前台，唔需要 Mac 長開。
密碼同讀寫 key 唔會放 Git。完整 Streamlit 私人前台入口係 `cloud_app.py`，
平台帳戶部署尚需授權；唔好將舊本機 Telegram 設定頁公開部署。

- 每日 US EOD／每週有界研究 workflow：`.github/workflows/daily-cloud.yml`。
- 資料永久來源係 D1，唔係 runner／Streamlit 嘅 SQLite 或 artifacts。
- Form4／13F、Enhanced VCP、MET-A 及回測均屬研究，唔會單靠分數產生 BUY。
- 原有 75 個測試保留；新增 SEC、日曆、永久保存、資金組合及 OIDC 測試。
- Python 3.12；一般使用 `requirements.txt`，批次研究用 `requirements-research.txt`。
- 唔會自動 merge main、開付費服務、發 Telegram 或落真實盤。

交付說明：[雲端部署](docs/CLOUD_DEPLOYMENT_REPORT.md)、
[開源整合](docs/OPEN_SOURCE_INTEGRATION_REPORT.md)、
[持倉研究](docs/OWNERSHIP_RESEARCH.md)、[回測解讀](docs/BACKTEST_VALIDATION.md)、
[完成狀態](docs/VNEXT_FINAL_STATUS.md)。

以下係原有本機及上一版說明；交易日曆、資金組合及雲端狀態以以上最新報告為準。

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
