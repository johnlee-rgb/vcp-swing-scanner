# Signal history and scheduled EOD scanning

## Deployment status

The repository contains a runnable job and systemd timer templates. No scheduler
has been installed or activated. No Telegram messages have been sent by development
tests. This app has no configured always-on server or persistent cloud volume.

The default database is `data/signals.sqlite3`, local to the checkout. It persists
across local app restarts. It is **not** durable across ephemeral hosting rebuilds.
For production, mount a persistent disk, set `VCP_TRACKING_DB` to an absolute path
on it, and set `VCP_TRACKING_PERSISTENT=1` only after verifying the mount. The flag
is an operator declaration, not automatic verification of hosting durability.
The UI and job must use the **same database**. Back it up with SQLite's backup API.
Use a single host/local disk; SQLite and file locks are not a distributed database.

## Immutable observations and episodes

Successful scans archive `Trade = YES` without changing results or decisions.
The source trading date comes from the downloaded ticker candle. Current/incomplete
sessions and partial/failed scans do not create new Buy snapshots. Each snapshot
contains original public row fields, app-file hash, Git SHA when available, UTC
creation time, entry/stop/targets, saved ten-session low, and simulation policy.
Private Python helper objects are excluded.

One active episode is allowed per scanner/market/ticker. Repeat signals add one
observation per source date. The original snapshot is protected by a database
trigger. A closed episode can recur only on a newer source date with a different
setup category or entry changing by at least 1%. This explicit heuristic errs on
the side of avoiding duplicate trades; it is not a new scanner decision rule.

No existing CSV is imported as original recommendations: unsaved prior decisions
are unknowable. Legacy `trade_signals_history.csv` is untouched.

## Performance assumptions

- Selection returns: close-to-close at 1/3/5/10/20 subsequent observed trading
  sessions. They are stock-selection diagnostics, not fills or portfolio returns.
- Buy-stop entry: only after source date and signal creation. A pre-open record
  can enter that session; a record made during/after trading waits until a later
  session. Gap above trigger fills at open, otherwise a high touching trigger
  fills at trigger. There is no fill from an already-completed signal-day candle.
- Stop: fixed original stop. Gap below stop fills at open. 10 basis points per
  side proxy transaction costs (not a broker-specific fee/slippage model).
  R multiples use the original planned trigger-minus-stop risk, also for gap fills.
- Targets: 2R/3R touches recorded, no automatic profit exit or partial sale.
- Close below MA20 or the saved structure low schedules exit at the next available
  session open (avoiding hindsight fills at the just-completed close). No automatic
  rejection merely for falling below an old pivot.
- Untriggered setups expire after 20 eligible sessions. Triggered trades have a
  20-session maximum holding policy.
- Entry-day stop touches with unknown order, and same-session stop plus target
  touches, are AMBIGUOUS and excluded from resolved trade win rate.
- Excursions exclude unknown pre-entry lows and exit-day intrabar extremes.
  For ambiguous outcomes, no realized return is fabricated.
- Missing anchors/invalid OHLC leave previous tracking intact. Corporate-action
  price-basis changes above 20% suspend evaluation as AMBIGUOUS; reconciliation is
  manual. No split adjustment is guessed. Ordinary cash dividends are not added
  to price-only simulated P/L.
- Daily data cannot establish intraday path, real liquidity, spreads or fills.
  No compounded portfolio return/drawdown is reported.
- Refresh uses the existing 18-month daily downloader. Records older than its
  available history require a future explicit archival-data import; no missing
  period is guessed. Missing ticker sessions relative to an available SPY/HSI
  benchmark suspend updates. Without that benchmark, horizons count received
  sessions; both provider series could omit the same date. This is not a full
  exchange-calendar validator.

## Run manually

Install project requirements into a virtual environment, then:

```sh
python scheduled_scan.py scan
python scheduled_scan.py deliver
```

The scan uses exactly the current interactive default `US Pro Market Scan`,
`US_PRO_UNIVERSE` capped at 500, minimum price 10, market cap 5B, average dollar
volume 20M, existing EOD downloader and scoring functions. There is no Quick Scan
preset in this checkout; no new universe or alternate scanner has been invented.
The two runs use the same EOD candle when no newer session is available.

Each run stores its ID, UTC times, requested/downloaded ticker counts, source
dates, result/Buy counts, and SUCCESS / PARTIAL DATA / SCAN FAILED status. Legitimate
prefilter rejection is not a download failure. Global data older than five calendar
days or any ticker behind the available benchmark is treated conservatively as
partial data. A process lock prevents overlapping scheduled jobs. Scan retries
are limited to two; the command bounds the entire worker to 900 seconds.

## Telegram setup

On the local app, open Signal Performance > Telegram Setup. Enter the BotFather
token in the password field, verify the bot username, select your private /start
chat, and explicitly save on this Mac. The token is saved atomically in
`data/telegram.json` with owner-only mode 0600; the directory is ignored by Git.
The UI never renders the saved token. The standalone job reads the same file.
Environment credentials take priority as a pair. `VCP_TELEGRAM_CONFIG` can select
a different private file location. This local file is not a cloud secret store;
use deployment environment secrets when moving to a server. Saving local settings
does not activate a schedule. Send Test Notification is a separate explicit action.

Secret environment names only:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Create/select a bot via Telegram BotFather. Store its token directly in the private
server secret store or protected environment file, not chat, source code, shell
history, GitHub, or logs. Open the bot in your own Telegram account and press Start.
Phone numbers are not chat IDs and are not used or stored.

With the token configured privately, run locally:

```sh
python scheduled_scan.py telegram-setup --confirm-read-updates
```

It reads pending updates without advancing the update offset and prints private
chat IDs that sent `/start`. Confirm your own chat before setting
`TELEGRAM_CHAT_ID`. An existing webhook or another bot consumer may prevent this;
do not delete a webhook without reviewing the other integration.

An explicit user-run test (sends a real message):

```sh
python scheduled_scan.py test-notification --confirm-send
```

Alerts use a persistent outbox and signal ID. Retried jobs, same-day scans, and
continuing active setups do not resend acknowledged messages. Explicit Telegram
rejections retry on later invocations up to three attempts. Timeout/connection
errors and crashed unacknowledged sends are UNKNOWN: delivery may have occurred,
so do not automatically resend. Reconcile in Telegram before an operator changes
UNKNOWN back to PENDING. Exactly-once delivery cannot be guaranteed by Telegram's
sendMessage API; this policy avoids blind duplicate sends.

Missing credentials preserve scan/persistence and leave messages pending.
Buy notifications older than 48 hours since recording, or whose episode has
closed, are skipped rather than delivered later as new signals. Failure
warnings are deduplicated per day/type. No markup parsing is enabled, and token-
bearing URLs or remote error bodies are never printed by the scheduled sender.
Material-update notifications are not enabled. No brokerage execution exists.

## Activate on an always-on Linux server

1. Deploy the checkout to `/opt/vcp-swing-scanner`; create its `.venv` and install
   requirements. Create a restricted `vcp` service user with write access to the
   persistent database directory.
2. Use `/etc/vcp-scanner.env`, mode 0600, with the four environment variables above.
   Mount the persistent disk and point both Streamlit and the job at the same DB.
3. Review and install `deploy/vcp-scan.service` and `deploy/vcp-scan.timer` into
   `/etc/systemd/system/`. Validate calendar expressions with `systemd-analyze
   calendar '*-*-* 12:00:00 Asia/Singapore'` and the 19:00 equivalent.
4. Run one manual job, inspect saved counts and signals, then run
   `systemctl daemon-reload` and `systemctl enable --now vcp-scan.timer`.
5. Confirm with `systemctl list-timers vcp-scan.timer` and inspect service logs.

Both times are explicitly Asia/Singapore (UTC+8): 04:00 and 11:00 UTC. Persistent
catch-up is disabled to avoid unexpected stale runs after downtime. Weekend and
holiday repeats are deduplicated by source date/episode. 19:00 is still EOD, not
a pre-market data feed. An ordinary Streamlit Cloud page or sleeping Mac is not
an unattended scheduler. Server setup/activation remains outstanding.
