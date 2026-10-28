# vNext Configuration

> 2026-10-29：呢份係上一版設定基線。Cloud vNext 已改用 XNYS／XHKG 日曆，
> 並加入獨立資金組合研究及私人 D1 儲存。下文舊版關於 weekday／未有 portfolio
> 嘅限制唔代表最新狀態；請以 CLOUD_DEPLOYMENT_REPORT.md 及 BACKTEST_VALIDATION.md 為準。

No new paid service, account or API is required. Existing yfinance remains the
daily source. Risk inputs add symbols to the existing batch, not a new provider.
Normal startup performs no research downloads. A successful scan supplies the
research/risk views; backtests run only on explicit request.

## Shared rules

`VCP_RULES_JSON` is optional JSON read by both interactive and scheduled scans.
Unknown/invalid keys fail explicitly. Defaults are in `vcp_scanner.vnext.Rules`
and visible under Data Health. Example (not credentials):

```bash
export VCP_RULES_JSON='{"max_risk_pct":10,"max_extension_pct":5,"account_equity":100000,"risk_budget_pct":0.5,"max_allocation_pct":10}'
```

Default eligibility: developed legacy VCP/momentum setup, setup quality >=60,
defined pivot, trigger reached AND closing reclaim, close location >=0.75,
volume >=1.5x prior 20-session average, Stage 2 alignment and rising MA150/200,
RS >=5, positive stop below entry, risk <=10%, structural reward >=2R,
within 5% of entry / 12% of MA10 / 18% of MA20, current completed bar,
known earnings beyond seven weekdays, usable non-RED market regime.
Missing inputs appear as blockers; candidates remain visible on watchlist.
Legacy score thresholds are not sufficient to bypass this independent gate.

Wide-stop warning starts above 8%. No stop is tightened to pass a risk test.
The maximum next-session fill is capped by extension, stop-distance and saved
structural 2R limits. Original stop/targets remain saved. Costs default to 10bps
each side. Illustrative sizing assumes zero existing open/sector risk; the
Data Health calculator accepts actual aggregate/sector usage. It is not a
portfolio-aware trading authorization.

Risk sizing multipliers: GREEN 1, YELLOW .75, ORANGE .25, RED 0. Maximum aggregate
risk 3% and sector allocation 25%, maximum individual allocation 10% by default.
`VCP_REGIME_OVERRIDE=1` explicitly overrides the market gate with ORANGE sizing;
UI warnings and every result/snapshot record the override. It does NOT bypass
invalid stops, earnings, failed structures or absent breakout confirmation.
Do not enable casually. Off by default.

## Market data and limitations

SPY/QQQ are core market proxies; ^IXIC, ^SOX, WDC, ^TNX and ^TYX are contextual
inputs. 10Y/30Y warning defaults 4.75/5.30 are configurable
`yield_10y_warning` / `yield_30y_warning`. Inputs show daily observation date,
source and freshness. Five calendar days is the maximum conservative freshness
tolerance. Missing core data blocks routine eligibility; other missing inputs
keep regime selective, never count as positive. HK eligibility uses its HSI
MA50 context, not US indices. US Market Risk view remains US-focused.

Sample percentages above moving averages are not exchange breadth. Exchange
advance/decline series are unavailable, not fabricated. Earnings uses weekday
distance rather than an exchange calendar; holidays/early closes are not fully
modeled. Current session is conservatively excluded until normal 16:00 local
market time by the existing completed-bar helper.

## Research / replay

MET-A is research-only even when its stage is CONFIRMED. No setting in this
version enables its production Trade YES. Prior decline default 10%, meaningful
lower wick >=30% and CLV >=.75. A reversal is visible on its own close;
follow-through must be on a later completed bar. Body midpoint uses the prior
bearish candle BODY, not high/low midpoint. Dry volume alone is insufficient.

Replay recomputes indicators on prefixes. It never queries present-day
fundamentals/earnings as historical facts. Supply known historical earnings
dates to the Python API only when provenance is understood; otherwise coverage
is UNAVAILABLE. Current universe/mappings imply survivorship/classification bias.

Event studies compare VCP EARLY/CONFIRMED and MET-A WATCH/MIDPOINT/CONFIRMED.
These are explicitly UNGATED setup studies, not production eligible trades.
One ticker/variant at a time, next-session buy-stop, five-session entry expiry,
20-session hold, fixed original stop, no forced exit at target, opening-gap cap,
10bps each side. Stop/target ordering ambiguity is excluded from resolved win
rate. Missing OHLCV/zero volume is unresolved, not a loss. Benchmark dates expose
missing ticker bars when supplied. Raw Close is never mixed with Adj Close;
dividends are not credited. Known split windows are rejected; full point-in-time
corporate-action reconciliation remains unavailable.

Fixed chronological 70/30 development/test split, with crossing train outcomes
purged. No optimization or walk-forward calibration is implemented. No portfolio
return/drawdown claim; all statistics are per-event, with explicit denominators.
Short samples cannot establish profitability. Research exports are reconstructed,
never retroactive original recommendations.

Optional provider-only reproducibility command:

```bash
python history_validation.py --output /tmp/vcp-vnext-research
```

This downloads research CSVs with actions and records provenance. It neither
sends alerts nor writes the original signal archive. Independent verification
and strategy calibration are still required.

## Alerts and deployment

Existing Buy/operational Telegram outbox is preserved. Immutable new snapshots
save gap caps/costs; old snapshots/policies are not rewritten. Setup transitions
and regime changes are persisted after successful scans. `VCP_STATE_ALERTS=1`
opt-in queues ARMED/TRIGGERED/CONFIRMED/INVALIDATED and regime transitions, with
daily data date and UTC observation timestamp. Unchanged states do not re-alert.
No intraday monitoring or live orders. Nothing is auto-deployed or scheduled.
The earlier free GitHub Actions/durable shared storage design is not activated
by this upgrade; existing systemd templates are not a production service.
