# Checkpoint 2 Scoring Audit

Baseline commit: `97cebefa7725477fbdc38c65d737a184e611c9ab`

Purpose: document how the legacy blended scanner currently uses evidence before adding new dimensional scores. Checkpoint 2 keeps legacy `Trend Score`, `Technical Score`, `Final Score`, `Trade`, and exports for compatibility while adding separate research dimensions.

## Current Score Map

| Feature | Current Score(s) Using It | New Intended Dimension | Duplication Risk | Decision |
|---|---|---|---|---|
| Price above MA50/150/200 | Trend Score, Final Score via Trend | Leadership | Medium: trend and final both reward MA structure | Keep legacy, move interpretation to Leadership |
| MA50 > MA150/MA200 and MA150 > MA200 | Trend Score, Final Score via Trend | Leadership | Medium | Keep legacy, expose as Leadership component |
| MA200 rising | Trend Score, Final Score via Trend | Leadership | Low | Keep |
| Distance above 52-week low | Trend Score, Final Score via Trend | Leadership | Medium with 52-week high proximity | Keep legacy, treat as trend durability |
| Within 25% of 52-week high | Trend Score, Final Score via Trend | Leadership | Medium with RS and returns | Keep legacy, expose raw distance from high |
| RSSlope30 | Trend Score, Technical Score, Final Score via Trend/Technical | Leadership | High: RS slope is counted twice before Final Score | Keep legacy, move primary meaning to Leadership |
| Price above MA10/20/50 | Technical Score, Action Label, Trade eligibility indirectly | Setup Quality / Entry Quality split | High: structural health and entry timing are mixed | Keep legacy, split new dimensions |
| MA10 rising | Technical Score | Setup Quality | Low | Keep |
| Higher lows | Technical Score, Action Label forming base | Leadership / Setup Quality | Medium | Keep, expose as structure component |
| 10-day volume contraction | Technical Score, VCP Status, Tightness Score, Volume Confirmation, Watchlist | Setup Quality | High: volume dry-up is counted multiple times | Keep legacy, new dimensions count once in Setup Quality |
| Within 5% of pivot | Technical Score, Action Label, Volume Confirmation setup state, Watchlist | Entry Quality | High: pivot distance is setup and entry mixed | Keep legacy, primary new meaning is Entry Quality |
| Holding MA10 | Technical Score, Action Label pullback, Entry Quality | Entry Quality / Setup support | Medium | Keep, split support quality from current entry |
| Tight 5-day range | Technical Score, Tightness Score | Setup Quality | High: tightness double counted | Keep legacy, new Setup Quality tracks separately |
| VCP contractions | VCP Status, Tightness Score, Setup Category, Watchlist | Setup Quality | Medium | Keep legacy, Setup Quality component |
| Pivot tests | PivotInfo only; not in Final Score except through Action/Technical | Setup Quality | Low | Keep as setup component |
| Risk % | Trade YES/NO, Watchlist, Setup Category High Risk | Entry Quality | Medium | Keep legacy, primary new meaning is Entry Quality |
| RR Score | Trade YES/NO, Watchlist | Entry Quality | Medium | Keep legacy, uses structural target after Checkpoint 1 |
| Volume confirmation | Trade YES/NO, Breakout Alert, Rank Reason | Entry Quality | Medium | Keep legacy, state-aware after Checkpoint 1 |
| Extension from MA10/MA20/RSI | Action Label, Trade blocker, Setup Category | Entry Quality | High when it makes a leader look like a bad stock | Keep legacy, primary new meaning is Entry Quality |
| Market Score | Final Score, Watchlist | Market Regime | Medium: broad and sector context are blended | Keep legacy, add independent Market Regime |
| SMH in broad Market Score | Market Score for US scans | Sector Leadership, not broad market | High: semiconductor can bias all industries | Keep legacy for compatibility, exclude from new broad regime |
| Sector Score | Final Score, Watchlist | Sector Leadership | Medium | Keep legacy, add independent Sector Leadership |
| Stock-vs-sector spread | Sector Leadership display only | Sector Leadership | Low | Keep and expose |
| Earnings risk | Trade blocker, Watchlist reason | Catalyst / Data Completeness | Low | Keep legacy, mark data availability |
| Market cap / liquidity | Prefilter only | Data Completeness / Liquidity context | Low | Keep prefilter, expose completeness |

## Legacy Final Score

Legacy formula:

`Final Score = Trend 25% + Technical 25% + RS 20% + Sector 10% + Market 10% + Tightness 10%`

Known double-counting risks:

- RS evidence appears in `Trend Score`, `Technical Score`, `RS Score`, and then `Final Score`.
- Volume contraction appears in `Technical Score`, `VCP Status`, `Tightness Score`, and `Volume Confirmation`.
- Moving average structure mixes leadership, setup health, and entry timing.
- Pivot distance mixes setup readiness and entry attractiveness.
- Broad market and sector strength are blended into the same final ranking.

Checkpoint 2 keeps this legacy score unchanged and labels the new dimensions separately.

## New Dimensional Intent

Leadership Score asks: `How strong is the stock itself?`

Setup Quality Score asks: `How good is the current technical structure?`

Entry Quality Score asks: `How attractive is the entry right now?`

Market Regime asks: `Is the broad market supportive?`

Sector Leadership asks: `Is the relevant sector/ETF supportive and is the stock leading it?`

Data Completeness asks: `Which required inputs are known, partial, or missing?`

## Momentum Threshold Mapping

Checkpoint 1 made the Momentum Breakout route reachable but still intentionally strict:

- Trend Score must be at its documented maximum.
- Technical Score must be at its documented maximum.
- RS Score must be at least 8.

Checkpoint 2 maps this to:

- Leadership: strong RS and strong trend structure.
- Setup Quality: excellent technical/tightness/base evidence.
- Entry Quality: confirmed or actionable breakout state, controlled risk, valid volume state.

Threshold redesign belongs to Checkpoint 3, not Checkpoint 2.

## Compatibility Decision

- Keep `Trend Score`, `Technical Score`, `Tightness Score`, `RS Score`, `Market Score`, `Sector Score`, `Final Score`, `Trade`, and `WATCHLIST FLAG`.
- Add new columns beside them.
- Do not change existing exports or Trade YES/NO logic in Checkpoint 2.
- Use new dimensions for explainability and future migration only.
