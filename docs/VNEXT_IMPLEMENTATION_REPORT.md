# vNext Implementation Report — 2026-10-28

## Status

Working correctness/research upgrade on `codex/vnext-correctness`. Not a claim
that every Master Upgrade research/deployment requirement is complete.
No commit, push, PR, merge, production deployment, Telegram message or broker
order was performed. Existing dirty Checkpoint 2/tracking/Telegram work remains
uncommitted and intact. A reviewable PR requires separating/accepting that
uncommitted prerequisite work first; no unrelated files were staged.

## Files changed in this upgrade

- app.py: final eligibility integration inside scan_universe; completed EOD
  bars only; US risk symbols in existing daily batch; empty dashboard protection;
  required new cache fields; appended action/audit columns; extra tabs.
- src/vcp_scanner/vnext.py (new): Rules/configuration, features, price_plan,
  market_risk, vcp_assessment, meta_assessment. Pure analysis, no network/orders.
- src/vcp_scanner/research.py (new): replay, outcome, backtest, summarize.
- src/vcp_scanner/vnext_ui.py (new): render_vnext, risk/MET-A/watchlist/research/
  settings/data-health views using already downloaded data.
- src/vcp_scanner/tracking.py: snapshot-specific next-session gap cap/costs,
  backward-compatible old policies; persistent setup transition ledger.
- src/vcp_scanner/workflow.py: successful-scan transition recording; optional
  deduplicated state alerts; Buy messages include timestamp/session/state.
- history_validation.py (new): explicit provider-only historical research tool.
- tests/test_vnext.py (new): deterministic synthetic/regression/integration/UI tests.
- README.md, docs/VNEXT_AUDIT.md, docs/VNEXT_CONFIGURATION.md and this report.

Other pre-existing untracked/modified files were not newly created by this task.
No requirements change or secret file read/upload was needed.

## Correctness delivered

- Legacy score/detection/ranking/download helper implementations retained.
  Legacy Trade and Legacy Trade Reason remain visible for comparison.
- Separate setup quality, development stage, trigger, risk, regime, eligibility
  and precise final action. Daily confirmation means NEXT SESSION candidate.
- A base dry-up YES is not expansion. Actual trigger, closing reclaim, strong
  closing location, prior-volume baseline, stage/trend, risk/reward, freshness
  and earnings checks independently control final Trade YES.
- Original stops are not tightened to manufacture eligibility. Sizing uses
  risk/capital/aggregate/sector caps; unknown live holdings are not inferred.
- Maximum acceptable next-session entry respects extension, original stop risk
  and original structural reward. Gap above cap cancels the simulated entry.
- Missing earnings/core market inputs explicitly block routine entry; missing
  contextual risk inputs are shown, not favorable votes. Weekday earnings
  blackout is conservative and documented, not a full exchange calendar.
- VCP development diagnostics add compression, base depth, contraction conditions,
  moving-average alignment/slope and historical swing-resistance warnings.
- MET-A separates decline, contraction, rejection, prior bearish-body closing
  reclaim, defined trigger and later follow-through. Same-day reversal cannot
  confirm its own follow-through. Always Trade NO, research-only.
- Regime inputs have source/date/freshness/availability. Missing exchange breadth
  is explicitly not replaced by invented advance/decline numbers.
- Existing public CSV names remain; new columns are additive. Positional CSV
  consumers need schema migration; this caveat is in README/configuration.

## Tests and actual checks

- Baseline: 43 existing tests passed before new tests.
- Final complete suite: **75 passed** (pytest, 2.44 seconds).
- py_compile: app.py, scheduled_scan.py, history_validation.py and all affected
  modules passed. git diff --check passed.
- Streamlit AppTest: complete app/tab smoke, actual mocked Run Scan and
  CSV/PDF/Trade Plan button rendering passed. Existing characterization,
  tracking/restart/immutability/deduplication/Telegram tests passed unchanged.
- EOG deterministic regression: close 161.10 / trigger 165.28 / stop 149.71
  produces ARMED, Trade NO; risk 9.4204%; 2R196.42/3R211.99; wide-stop warning;
  trigger and volume confirmation blockers visible.
- Actual yfinance scan, EOG/DELL/GLW: 3 rows, zero scoring errors. EOG legacy
  Trade YES becomes ARMED / READY TO TRIGGER / Trade NO, entry165.28 and risk
  9.4204 retained. No archive or alerts invoked for this diagnostic command.
- Provider-only historical retrieval: DELL/WDC/GLW/NVDA each 501 sessions,
  2024-10-28 through 2026-10-27. Initial sandbox DNS failed; approved network
  retry succeeded. Data/provenance stored only in /private/tmp/vcp-vnext-research.
- A DELL event-study smoke run exercised VCP early/confirmed and MET-A
  watch/midpoint/confirmed variants. Tiny, ungated, unverified sample results
  are NOT treated as profitability evidence or calibration.
- Local Streamlit started at http://127.0.0.1:8572 for user testing.

## Research coverage and incomplete items

These limitations are material, not hidden completed features:

1. DELL/GLW/WDC named historical cases are provider research observations, not
   independently verified fixtures. Synthetic reversal tests are labeled synthetic.
   SKHY mapping/comparable data has not been validated. MET-A Buy remains disabled.
2. Replay recomputes current deterministic rules on prefixes. It is reconstructed
   research, not reconstruction of unsaved original recommendations.
3. Event studies are ungated setup comparisons, not production-eligibility
   backtests. Current universe has survivorship bias. Fixed 70/30 chronological
   split with boundary purging exists, but no optimization/walk-forward calibrated
   historical validation or point-in-time universe/earnings database.
4. Price-return studies exclude dividend cash flows. Known split windows are
   blocked; full adjusted/unadjusted and corporate-action reconciliation remains
   incomplete. Missing benchmark sessions are detected when benchmark supplied.
5. No capital-weighted multi-asset portfolio simulation, portfolio drawdown or
   portfolio exposure statistic. Per-trade MFE/MAE/returns and denominators only.
6. No true exchange advance/decline breadth, consecutive SOX lower-low model,
   complete leadership basket or verified macro history. The available-input
   regime is a documented conservative first implementation, not full Phase 4.
7. Intraday optional monitoring is not implemented; daily bars only. New alert
   transitions are opt-in/off by default; no production schedule is activated.
8. Durable shared cloud storage and free GitHub Actions deployment remain
   unconfigured. Existing local SQLite is still not cloud durable. No paid
   service was provisioned. Public deployment still needs private settings access
   controls; do not expose local Telegram setup controls to anonymous users.
9. MET-A confirmation does not yet include independently calibrated sector/RS
   improvement requirements. VCP defaults are documented engineering thresholds,
   not historically optimized/validated investment rules.

## Run / inspect

```bash
python -m pip install -r requirements.txt pytest
python -m py_compile app.py
python -m pytest -q
streamlit run app.py --server.port 8572
```

Run US Scanner first; review Final Action, Trade Eligibility, All Eligibility
Blockers and Legacy Trade under diagnostics. For EOG compare Legacy Trade with
final Trade, not just READY or Final Score. Review MET-A under MET-A Research;
uncheck Enable MET-A research to hide it. No option enables its production Buy.
Replay/backtest use already downloaded scan data only; longer independent
datasets can be supplied to the Python research APIs. Configuration and exact
assumptions are documented in VNEXT_CONFIGURATION.md.

## Reference checks

- NYSE regular session timing: https://www.nyse.com/markets/hours-calendars
- Yahoo historical data: https://finance.yahoo.com/quote/DELL/history/
- Weekdays are not exchange sessions:
  https://pandas.pydata.org/docs/reference/api/pandas.bdate_range.html

No external performance advertisement or historical example was used as proof
of strategy profitability.
