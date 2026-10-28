"""Immutable signal snapshots and daily-bar simulation, independent of scoring."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
from zoneinfo import ZoneInfo

import pandas as pd

OPEN_STATES = {"WAITING ENTRY", "ACTIVE", "TARGET REACHED"}
HORIZONS = (1, 3, 5, 10, 20)
POLICY = {
    "version": "daily-trigger-v1",
    "entry": "Next eligible session buy-stop: open if above trigger, otherwise trigger if high touches it.",
    "exit": "Fixed original stop intraday; close below MA20/saved low exits next open; 20 sessions after entry.",
    "targets": "2R/3R touches are informational; no automatic profit exit or partial sale.",
    "cost_bps_per_side": 10,
    "r_basis": "Original planned entry trigger minus original stop, including when fill gaps above trigger.",
    "entry_expiry_sessions": 20,
    "holding_sessions": 20,
    "ambiguity": "Entry-day low before entry is unknown; stop touches are ambiguous unless entry fills at open.",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if hasattr(value, "item"):
        return json_safe(value.item())
    return str(value)


def daily_bars(frame, market="US", asof=None):
    """Ignore current/incomplete sessions without changing scanner downloads."""
    if frame is None or frame.empty or not {"Open", "High", "Low", "Close"}.issubset(frame.columns):
        return pd.DataFrame()
    data = frame.copy()
    dates = pd.to_datetime(data.index, errors="coerce")
    zone = ZoneInfo("Asia/Hong_Kong" if market == "HK" else "America/New_York")
    if dates.tz is not None:
        dates = dates.tz_convert(zone).tz_localize(None)
    data.index = dates.normalize()
    data = data[~data.index.isna()].sort_index()
    data = data[~data.index.duplicated(keep="last")]
    from vcp_scanner.sessions import completed_bars
    return completed_bars(data,asof or now_iso(),market)


def strategy_version():
    try:
        root = Path(__file__).resolve().parents[2]
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, timeout=2, stderr=subprocess.DEVNULL).decode().strip()
        digest = hashlib.sha256((root / "app.py").read_bytes()).hexdigest()[:16]
        return f"{sha}:app-{digest}"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def storage_settings():
    configured = os.environ.get("VCP_TRACKING_DB")
    path = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / "data" / "signals.sqlite3"
    persistent = bool(configured and os.environ.get("VCP_TRACKING_PERSISTENT") == "1")
    message = "Persistent volume configured; back up this database regularly." if persistent else (
        "Local storage only: survives local app restarts, but cloud redeploys may erase it. "
        "Configure VCP_TRACKING_DB on a persistent disk and VCP_TRACKING_PERSISTENT=1."
    )
    return path, persistent, message


class SignalStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY, scanner TEXT NOT NULL, market TEXT NOT NULL,
                    ticker TEXT NOT NULL, source_date TEXT NOT NULL, setup_key TEXT NOT NULL,
                    created_at TEXT NOT NULL, snapshot TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'WAITING ENTRY', performance TEXT NOT NULL DEFAULT '{}'
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_episode
                ON signals(scanner, market, ticker)
                WHERE status IN ('WAITING ENTRY','ACTIVE','TARGET REACHED');
                CREATE TABLE IF NOT EXISTS observations (
                    signal_id TEXT NOT NULL REFERENCES signals(id), source_date TEXT NOT NULL,
                    observed_at TEXT NOT NULL, snapshot TEXT NOT NULL,
                    PRIMARY KEY(signal_id, source_date)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
                    outcome TEXT NOT NULL, detail TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS setup_states (
                    scanner TEXT NOT NULL, ticker TEXT NOT NULL, state TEXT NOT NULL,
                    source_date TEXT NOT NULL, PRIMARY KEY(scanner,ticker)
                );
                CREATE TABLE IF NOT EXISTS setup_events (
                    event_key TEXT PRIMARY KEY, scanner TEXT NOT NULL, ticker TEXT NOT NULL,
                    old_state TEXT, new_state TEXT NOT NULL, source_date TEXT NOT NULL,
                    observed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notifications (
                    key TEXT PRIMARY KEY, text TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'PENDING',
                    attempts INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL, error TEXT
                );
                CREATE TRIGGER IF NOT EXISTS immutable_signal_snapshot
                BEFORE UPDATE OF snapshot, created_at, source_date, setup_key ON signals
                BEGIN SELECT RAISE(ABORT, 'Original signal snapshots are immutable'); END;
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def records(self):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM signals ORDER BY created_at DESC").fetchall()
        return [dict(r) | {"snapshot": json.loads(r["snapshot"]), "performance": json.loads(r["performance"])} for r in rows]

    def save_buys(self, results, frames, scanner, created_at=None):
        created = created_at or now_iso()
        version = strategy_version()
        new_ids = []
        if results.empty or "Trade" not in results:
            return new_ids
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            for row in results.loc[results["Trade"] == "YES"].to_dict("records"):
                ticker = str(row.get("ticker", "")).strip().upper()
                market = "HK" if ticker.endswith(".HK") else "US"
                data = daily_bars(frames.get(ticker), market, created)
                if not ticker or data.empty:
                    continue
                source = str(data.index[-1].date())
                # Do not archive a scanner decision based on an incomplete daily candle.
                original_frame = frames[ticker]
                if pd.Timestamp(original_frame.index[-1]).date() != data.index[-1].date():
                    continue
                setup = json.dumps([row.get("Setup Category"), row.get("Action Label"), number(row.get("Entry Trigger"))])
                identity = "|".join([scanner, market, ticker, source, setup])
                signal_id = hashlib.sha256(identity.encode()).hexdigest()[:24]
                previous = db.execute("SELECT * FROM signals WHERE scanner=? AND market=? AND ticker=? ORDER BY source_date DESC LIMIT 1", (scanner, market, ticker)).fetchone()
                if previous:
                    if previous["status"] in OPEN_STATES:
                        signal_id = previous["id"]
                    else:
                        old = json.loads(previous["snapshot"])
                        previous_perf = json.loads(previous["performance"])
                        old_entry, entry = number(old.get("Entry Trigger")), number(row.get("Entry Trigger"))
                        changed = old.get("Setup Category") != row.get("Setup Category") or (
                            old_entry and entry and abs(entry / old_entry - 1) >= 0.01
                        )
                        # A closed old setup cannot be resurrected by a retry or stale Buy.
                        last_episode_date = previous_perf.get("exit_date", previous_perf.get("last_data_date", previous["source_date"]))
                        if source <= last_episode_date or not changed:
                            continue
                snapshot = json_safe(row)
                policy = dict(POLICY)
                if row.get("Maximum Acceptable Entry") is not None:
                    policy.update(version="daily-trigger-vnext", maximum_entry=number(row.get("Maximum Acceptable Entry")),
                                  entry="Next eligible session buy-stop, canceled if opening gap exceeds saved maximum entry.")
                    cost = number(row.get("Transaction Cost bps per Side"))
                    if cost is not None and cost >= 0:
                        policy['cost_bps_per_side'] = cost
                snapshot.update({
                    "strategy_version": version, "origin": "Recorded live scanner output",
                    "policy": policy, "source_close": number(data.iloc[-1]["Close"]),
                    "structure_low": number(data["Low"].tail(10).min()),
                    "adjustment_ratio": number(data.iloc[-1].get("Adj Close", data.iloc[-1]["Close"]) / data.iloc[-1]["Close"]),
                })
                inserted = db.execute("INSERT OR IGNORE INTO signals(id,scanner,market,ticker,source_date,setup_key,created_at,snapshot) VALUES(?,?,?,?,?,?,?,?)",
                                      (signal_id, scanner, market, ticker, source, setup, created, json.dumps(snapshot))).rowcount
                if inserted:
                    new_ids.append(signal_id)
                db.execute("INSERT OR IGNORE INTO observations VALUES(?,?,?,?)", (signal_id, source, created, json.dumps(json_safe(row))))
        return new_ids

    def record_states(self, results, scanner, regime=None, observed_at=None):
        """Persist only transitions; unchanged next-day states do not re-alert."""
        rows = results.to_dict('records') if not results.empty else []
        if regime:
            rows.append({'ticker':'MARKET REGIME','Setup Stage':regime,
                         'Data Trading Date':max((str(r.get('Data Trading Date','')) for r in rows),default='')})
        new = []
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for row in rows:
                state, ticker, source = row.get('Setup Stage'), row.get('ticker'), row.get('Data Trading Date')
                if not state or not ticker or not source: continue
                old = db.execute('SELECT state,source_date FROM setup_states WHERE scanner=? AND ticker=?',(scanner,ticker)).fetchone()
                if old and (source < old['source_date'] or state == old['state']): continue
                key = hashlib.sha256(f'{scanner}|{ticker}|{source}|{state}'.encode()).hexdigest()
                changed = db.execute('INSERT OR IGNORE INTO setup_events VALUES(?,?,?,?,?,?,?)',
                                    (key,scanner,ticker,old['state'] if old else None,state,source,observed_at or now_iso())).rowcount
                db.execute('INSERT INTO setup_states VALUES(?,?,?,?) ON CONFLICT(scanner,ticker) DO UPDATE SET state=excluded.state,source_date=excluded.source_date',
                           (scanner,ticker,state,source))
                if changed: new.append({'key':key,'ticker':ticker,'state':state,'source_date':source})
        return new

    def update(self, frames, asof=None):
        for record in self.records():
            try:
                data = daily_bars(frames.get(record["ticker"]), record["market"], asof)
                benchmark = daily_bars(frames.get("^HSI" if record["market"] == "HK" else "SPY"), record["market"], asof)
                if not data.empty and not benchmark.empty:
                    required_sessions = benchmark.loc[record["source_date"]:data.index[-1]].index
                    if not required_sessions.difference(data.index).empty:
                        continue  # An omitted session could conceal a stop/target event.
                performance = evaluate_signal(record, data)
            except (ValueError, TypeError, KeyError, OverflowError):
                continue  # A malformed date/bar must not block other signals.
            if performance is None:
                continue
            with self.connect() as db:
                # A stale worker must not overwrite an update made with newer market data.
                current = db.execute("SELECT performance FROM signals WHERE id=?", (record["id"],)).fetchone()
                previous = json.loads(current["performance"])
                if previous.get("last_data_date", "") > performance["last_data_date"]:
                    continue
                db.execute("UPDATE signals SET status=?, performance=? WHERE id=?", (performance["status"], json.dumps(performance), record["id"]))

    def record_run(self, run_id, started, outcome, detail):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO runs VALUES(?,?,?,?,?)", (run_id, started, now_iso(), outcome, json.dumps(json_safe(detail))))

    def enqueue(self, key, text):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO notifications(key,text,updated_at) VALUES(?,?,?)", (key, text[:4000], now_iso()))

    def claim_notification(self, excluded=(), operations_only=False):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            # Delivery may have succeeded before a crashed worker acknowledged it.
            db.execute("UPDATE notifications SET state='UNKNOWN',error='Delivery acknowledgement missing; manual reconciliation required' WHERE state='SENDING' AND updated_at < ?",
                       ((pd.Timestamp(now_iso()) - pd.Timedelta(minutes=10)).isoformat(),))
            candidates = db.execute("SELECT * FROM notifications WHERE state IN ('PENDING','FAILED') AND attempts < 3 ORDER BY updated_at").fetchall()
            row = None
            for candidate in candidates:
                if candidate["key"] in excluded or (operations_only and not candidate["key"].startswith("operation:")):
                    continue
                if candidate["key"].startswith("signal:"):
                    signal = db.execute("SELECT status,created_at FROM signals WHERE id=?", (candidate["key"][7:],)).fetchone()
                    if signal is None or signal["status"] not in OPEN_STATES or pd.Timestamp(now_iso()) - pd.Timestamp(signal["created_at"]) > pd.Timedelta(hours=48):
                        db.execute("UPDATE notifications SET state='SKIPPED',error='Closed or older than 48h; not sent as a new Buy' WHERE key=?", (candidate["key"],))
                        continue
                row = candidate
                break
            if row is None:
                return None
            db.execute("UPDATE notifications SET state='SENDING',attempts=attempts+1,updated_at=? WHERE key=?", (now_iso(), row["key"]))
            return dict(row)

    def finish_notification(self, key, state, error=None):
        with self.connect() as db:
            db.execute("UPDATE notifications SET state=?,error=?,updated_at=? WHERE key=?", (state, error, now_iso(), key))


def evaluate_signal(record, data):
    """Replay a fixed policy; never substitute a new scanner recommendation."""
    if data.empty:
        return None
    snapshot = record["snapshot"]
    source = pd.Timestamp(record["source_date"])
    if source not in data.index:
        return None  # Missing anchor/history cannot be treated as zero return or expiry.
    ohlc = data[["Open", "High", "Low", "Close"]].apply(pd.to_numeric, errors="coerce")
    if ohlc.loc[source:].isna().any().any() or (ohlc.loc[source:] <= 0).any().any():
        return None
    if ((ohlc["High"] < ohlc[["Open", "Close", "Low"]].max(axis=1)) | (ohlc["Low"] > ohlc[["Open", "Close", "High"]].min(axis=1))).loc[source:].any():
        return None
    future = data.loc[data.index > source]
    perf = {"status": "WAITING ENTRY", "triggered": False, "last_data_date": str(data.index[-1].date()),
            "latest_price": float(data.iloc[-1]["Close"]), "explanation": "Waiting for a future session to touch the saved entry trigger.",
            "cost_bps_per_side": snapshot["policy"]["cost_bps_per_side"], "target_events": []}
    reference = number(snapshot.get("source_close"))
    anchor = number(data.loc[source, "Close"])
    ratio = number(data.loc[source].get("Adj Close", anchor) / anchor)
    old_ratio = number(snapshot.get("adjustment_ratio"))
    if not reference or abs(anchor / reference - 1) > 0.20 or (ratio and old_ratio and abs(ratio / old_ratio - 1) > .20):
        return perf | {"status": "AMBIGUOUS", "explanation": "Price basis changed (possible split/corporate action). Manual reconciliation required."}
    for sessions in HORIZONS:
        perf[f"return_{sessions}d_pct"] = float((future.iloc[sessions-1]["Close"] / reference - 1) * 100) if len(future) >= sessions else None
    entry, stop = number(snapshot.get("Entry Trigger")), number(snapshot.get("Stop Loss"))
    if not entry or not stop or entry <= stop:
        return perf | {"status": "AMBIGUOUS", "explanation": "Saved entry/stop invalid; no simulated execution."}
    zone = "Asia/Hong_Kong" if record["market"] == "HK" else "America/New_York"
    creation = pd.Timestamp(record["created_at"]).tz_convert(zone)
    # Signals observed before today's open may use today's session. Signals created
    # during/after a session can only enter on a later date using EOD bars.
    day = creation.tz_localize(None).normalize()
    before_open = (creation.hour, creation.minute) < (9, 30)
    eligible = future.loc[future.index >= day] if before_open else future.loc[future.index > day]
    policy = snapshot["policy"]
    fill = None
    pending_invalidation = False
    highs, lows = [], []
    ma20 = data["Close"].rolling(20).mean()
    for waiting_index, (date, bar) in enumerate(eligible.iterrows()):
        opened, high, low, close = (float(bar[k]) for k in ("Open", "High", "Low", "Close"))
        if pending_invalidation:
            perf.update(status="STRUCTURE INVALIDATED", exit_date=str(date.date()), exit_price=opened,
                        explanation="Prior close broke MA20 or saved support; exited at next session open.")
            break
        if fill is None:
            maximum = number(policy.get("maximum_entry"))
            if maximum and opened > maximum:
                perf.update(status="EXPIRED", explanation="Gap above saved maximum acceptable entry; no simulated fill.")
                break
            if waiting_index >= policy["entry_expiry_sessions"]:
                perf.update(status="EXPIRED", explanation="Entry never triggered within 20 eligible sessions.")
                break
            if high < entry:
                if close < stop or (snapshot.get("structure_low") and close < snapshot["structure_low"]):
                    perf.update(status="STRUCTURE INVALIDATED", explanation="Saved support broke before entry; no trade.")
                    break
                continue
            fill = max(opened, entry)
            if fill <= stop:
                return perf | {"status": "AMBIGUOUS", "explanation": "Invalid fill relative to stop."}
            perf.update(triggered=True, entry_date=str(date.date()), entry_price=fill, status="ACTIVE", holding_sessions=0)
        perf["holding_sessions"] += 1
        entry_day = str(date.date()) == perf["entry_date"]
        targets = [(name, number(snapshot.get(name))) for name in ("Target 2R", "Target 3R")]
        touched = [name for name, target in targets if target and high >= target]
        if low <= stop:
            ambiguous = (entry_day and opened < entry) or bool(touched and opened > stop)
            if ambiguous:
                perf.update(status="AMBIGUOUS", exit_date=str(date.date()), explanation="Daily bar cannot resolve entry/stop/target order. No winning outcome assumed.")
                break
            exit_price = min(opened, stop)
            perf.update(status="STOPPED OUT", exit_date=str(date.date()), exit_price=exit_price, explanation="Original stop hit; gap-down fill uses session open.")
            break
        # Intraday entry: exclude the day's unknown pre-entry low from MAE.
        highs.append(high)
        lows.append(min(fill, close) if entry_day and opened < entry else low)
        for name in touched:
            if name not in [event["target"] for event in perf["target_events"]]:
                perf["target_events"].append({"target": name, "date": str(date.date())})
        perf["status"] = "TARGET REACHED" if perf["target_events"] else "ACTIVE"
        support = number(snapshot.get("structure_low"))
        if (pd.notna(ma20.loc[date]) and close < ma20.loc[date]) or (support and close < support):
            pending_invalidation = True
            perf["explanation"] = "Close broke MA20 or saved support; exit pending at next available session open."
        if perf["holding_sessions"] >= policy["holding_sessions"]:
            perf.update(status="EXPIRED", exit_date=str(date.date()), exit_price=close, explanation="20-session holding policy completed; simulated exit at close.")
            break
    if fill:
        risk = entry - stop
        terminal_price = perf.get("exit_price")
        if perf["status"] != "AMBIGUOUS":
            mark = terminal_price or perf["latest_price"]
            cost = policy["cost_bps_per_side"] / 10000
            net = mark * (1 - cost) - fill * (1 + cost)
            perf.update(simulated_return_pct=net / fill * 100, r_multiple=net / risk)
            if terminal_price:
                perf.update(final_return_pct=net / fill * 100, final_r=net / risk)
        perf.update(mfe_pct=(max(highs) / fill - 1) * 100 if highs else None,
                    mae_pct=(min(lows) / fill - 1) * 100 if lows else None,
                    excursion_note="Entry-day pre-trigger low and exit-day intrabar extremes excluded when order is unknown.")
        if perf["status"] in OPEN_STATES:
            if not pending_invalidation:
                perf["explanation"] = "Tracking saved plan; target touches do not force an exit."
    elif len(eligible) >= policy["entry_expiry_sessions"] and perf["status"] == "WAITING ENTRY":
        perf.update(status="EXPIRED", explanation="Entry never triggered within 20 eligible sessions.")
    return perf


def performance_table(records):
    return pd.DataFrame([{
        "Signal ID": r["id"], "Scanner": r["scanner"], "ticker": r["ticker"],
        "Signal Date": r["source_date"], "Recorded At": r["created_at"],
        "Entry Status": "TRIGGERED" if r["performance"].get("triggered") else "NOT TRIGGERED",
        "last_data_date": r["performance"].get("last_data_date", r["source_date"]),
        "explanation": "Awaiting valid price update.",
        "Status": r["status"], **r["performance"],
    } for r in records])


def performance_summary(records):
    triggered = [r for r in records if r["performance"].get("triggered")]
    closed = [r["performance"] for r in triggered if r["status"] not in OPEN_STATES and r["performance"].get("final_return_pct") is not None]
    wins = [p["final_return_pct"] for p in closed if p["final_return_pct"] > 0]
    losses = [p["final_return_pct"] for p in closed if p["final_return_pct"] < 0]
    return {"Signals": len(records), "Triggered Trades": len(triggered), "Resolved Closed Trades": len(closed),
            "Win Rate (resolved closed)": f"{len(wins) / len(closed):.1%}" if closed else "N/A",
            "Average Gain %": sum(wins)/len(wins) if wins else None,
            "Average Loss %": sum(losses)/len(losses) if losses else None,
            "Average Closed R": sum(p["final_r"] for p in closed)/len(closed) if closed else None,
            "Ambiguous": sum(r["status"] == "AMBIGUOUS" for r in records)}
