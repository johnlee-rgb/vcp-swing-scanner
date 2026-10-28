# vNext Audit (2026-10-28)

## Repository and baseline

Confirmed SSH origin: johnlee-rgb/vcp-swing-scanner. Feature branch:
`codex/vnext-correctness`. Existing dirty app.py, src/, tracking, Telegram,
deployment and Checkpoint 2 work are preserved, not attributed to this upgrade.
No repository-specific AGENTS.md was found. No backup directory was used.

## Existing application

app.py is the Streamlit entry point. US/HK/IPO, Top 5, alerts, settings and
Signal Performance are existing tabs. Cached yfinance daily OHLCV, market caps
and earnings supply the scanner. Universe is capped at 500. Indicators include
MA10/20/50/150/200, RSI, ATR, RS versus benchmark. VCP uses retrospective swing
points, shrinking contractions, volume contraction and support occupancy.
Legacy weighted final score, separate dimensional scores, sector scoring,
trade/watch routes, 2R/3R plans, CSV/PDF/text exports already exist.
Tracking uses immutable SQLite snapshots and explicit next-session simulation.

## Correctness defects / risks

- READY and dry-up confirmation are not execution triggers. A legacy YES can
  occur below trigger; breakout confirmation previously accepts dry-up YES.
- Setup state labels a close above pivot confirmed without checking trigger,
  closing quality or expansion. Failed-breakout low comparison includes itself.
- scan_universe scores latest supplied bar without excluding incomplete EOD.
- Empty results can reach dashboard column indexing before empty guard.
- Current earnings classifier uses calendar days, not exchange sessions.
- Existing momentum/legacy helpers overlap; preserve them for compatibility,
  but independently gate their final YES output.
- Fundamentals/current earnings cannot be replayed as historical truth.
- Weekdays are not exchange holidays. Prior partial-data checks are conservative
  but do not establish point-in-time corporate-action or earnings provenance.
- Existing default local SQLite is not durable cloud storage; no production
  scheduler is enabled by adding a tab or systemd templates.

## Architecture / compatibility

Keep existing VCP detector, scores, exports, ranking and downloads as baseline.
Add pure vNext analysis with configurable thresholds; independent eligibility
gate overrides premature YES while preserving legacy decision in extra fields.
Add MET-A research-only, risk sizing, timestamped regime inputs, historical
prefix replay and conservative next-session research backtest. Keep legacy
columns; append new diagnostics. No orders, automatic deploy or merge.

## Validation policy

Synthetic tests are logic tests, not evidence for DELL/GLW/WDC profitability.
Real historical examples require independently verified data and are explicitly
incomplete if provider verification is unavailable. No missing input is a green
vote. No portfolio drawdown from averaging overlapping signals. Research mode
does not authorize MET-A live Buy eligibility. Historical replay is reconstructed
research, never a saved original recommendation.
