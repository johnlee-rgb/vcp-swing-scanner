# VCP Scanner Upgrade Audit

Checkpoint: 1 - characterization tests and correctness bugs.

## Repository Safety

- Working tree: Git repository confirmed.
- Branch: `main`.
- Remote: `git@github.com:johnlee-rgb/vcp-swing-scanner.git`.
- Local HEAD at audit start: `93df010f29d22793b5d019fe4a8162aca25a9bfb`.
- `origin/main` after fetch: `93df010f29d22793b5d019fe4a8162aca25a9bfb`.
- Ahead / behind: `0 / 0`.

## Current File Structure

```text
.devcontainer/devcontainer.json
README.md
app.py
requirements.txt
trade_signals_history.csv
```

## app.py Size / Responsibility

- `app.py`: 4,167 lines at audit start.
- Responsibilities currently combined in one file:
  - Streamlit UI.
  - Universe definitions.
  - yfinance data download.
  - indicator calculation.
  - market / sector scoring.
  - VCP and pivot detection.
  - trade-plan construction.
  - trade/watchlist decisions.
  - IPO scoring and live IPO scraping.
  - charting and exports.
  - Telegram/email alerts.

## Existing Functions

Major groups identified:

- Data: `download_daily_data`, `download_market_caps`, `download_earnings_data`.
- Indicators: `add_indicators`, `period_return`, `calculate_rs_score`.
- Market/Sector: `calculate_market_score`, `calculate_hk_market_score`, `calculate_sector_score`, `calculate_sector_leadership`.
- Setup detection: `detect_pivot`, `detect_vcp`, `detect_extension`, `choose_action_label`, `detect_breakout_alert`.
- Scoring: `score_trend`, `score_technical`, `calculate_tightness`, `calculate_final_score`.
- Decision: `decide_trade`, `decide_watchlist_flag`, `classify_setup_category`, momentum breakout helpers.
- Trade plan: `build_trade_plan`, `calculate_rr_score`.
- Display/export: `make_chart`, `round_display_values`, `dataframe_to_simple_pdf`, `trade_plan_text`.
- IPO: manual scoring, live fetch/parsing, score normalization.
- Alerts: `send_telegram_message`, `send_email_message`, `get_secret`.

## Existing Score Ranges

- `score_trend`: documented max 7.
- `score_technical`: documented max 8.
- `calculate_tightness`: max 5.
- `calculate_rs_score`: max 10.
- `calculate_market_score`: max 4.
- `calculate_hk_market_score`: max 4.
- `calculate_sector_score`: max 3.
- `calculate_final_score`: blended 0-100.

## Current Setup Logic

- Main action labels: `READY`, `PULLBACK ENTRY`, `WATCH`, `EXTENDED`, `FAILED`.
- VCP statuses: `VALID VCP`, `EARLY VCP`, `NOT VCP`.
- Setup categories added before this checkpoint: `VCP Breakout`, `Momentum Breakout`, `Pullback Setup`, `Early Base`, `High Risk`.
- Momentum breakout route currently references `trend_score >= 8`, which is impossible with the current 7-point trend score.

## Current Data Sources

- yfinance daily OHLCV for stocks, benchmarks, sector ETFs, market cap, and earnings metadata.
- Nasdaq public IPO calendar endpoint.
- HK IPO table scraping from AAStocks, ETNet, Investing.com, and Yahoo RSS fallback.
- Static fallback universes and sector mappings.

## Current Historical-Data Behavior

- `trade_signals_history.csv` exists in repository root.
- No durable point-in-time signal ledger currently exists.
- Historical scan rows are not currently modeled as immutable signal snapshots with versioned rules.

## Current Notification Behavior

- Telegram alerts via Telegram bot API.
- Email alerts through Gmail SMTP.
- Credentials are read from Streamlit secrets or typed into the UI.
- Alerts do not currently persist state transitions to suppress repeated unchanged alerts.

## Known Bugs Verified Against Source

### Bug A - Impossible Momentum Threshold

Verified. `score_trend()` max is 7, while `classify_setup_category()`, `is_momentum_breakout_confirmed()`, and `is_momentum_breakout_watch()` require `trend_score >= 8`.

### Bug B - Circular RR Score

Verified. `build_trade_plan()` creates `Target 2R = entry + 2 * risk`, and `calculate_rr_score()` uses that self-generated target, mechanically producing about 2R when entry/stop are valid.

### Bug C - Pre-Breakout vs Breakout Volume

Verified. `calculate_volume_confirmation()` treats `action == READY` as near breakout and asks for breakout volume. For pre-breakout VCP, this mixes ready-to-trigger dry-up logic with confirmed breakout expansion logic.

### Bug D - Old Pivot After Breakout

Partially mitigated by display-only `entry_logic_audit`, but verified that decision logic can still use old pivot-derived entry without a hard stale-pivot guard.

## Security / Secrets Risks

- `.streamlit/credentials.toml` should never be committed if real credentials are present.
- Alert-related secret names in app:
  - `telegram_bot_token`
  - `telegram_chat_id`
  - `smtp_email`
  - `smtp_password`
  - `recipient_email`
- `trade_signals_history.csv` may contain private research/history and should be reviewed before public commits.

## Backward-Compatibility Risks

- Existing UI/export code depends on legacy column names including `Final Score`, `Trade`, `WATCHLIST FLAG`, `RR Score`, `Target 2R`, `Target 3R`, `AI Trading Notes`.
- IPO tabs are in the same monolithic app and can regress if imports or global dependencies change.
- Tests must avoid live yfinance calls to remain deterministic.

