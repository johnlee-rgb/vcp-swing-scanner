"""Scanner orchestration and persistent notification outbox; no trading decisions."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
import time
import uuid

import pandas as pd
import requests

from vcp_scanner.tracking import SignalStore, daily_bars, now_iso, storage_settings
from vcp_scanner.telegram_setup import credentials

SCHEDULE_TIMEZONE = "Asia/Singapore"
SCHEDULE_HOURS = (12, 19)
DEFAULT_MODE = "US Pro Market Scan"
DEFAULT_FILTERS = {"min_price": 10.0, "min_market_cap": 5_000_000_000, "min_dollar_volume": 20_000_000}


def scan_outcome(tickers, frames, summary, asof=None):
    """Missing downloads/scoring errors are not a legitimate zero-Buy result."""
    downloaded, dates, incomplete = [], {}, []
    for ticker in tickers[:500]:
        frame = frames.get(ticker)
        market = "HK" if ticker.endswith(".HK") else "US"
        data = daily_bars(frame, market, asof)
        if not data.empty:
            downloaded.append(ticker)
            dates[ticker] = str(data.index[-1].date())
            if pd.Timestamp(frame.index[-1]).date() != data.index[-1].date():
                incomplete.append(ticker)
    scoring_errors = [r for r in summary.get("rejected", []) if "scoring failed" in r]
    stale = []
    for market in ("US", "HK"):
        group = [t for t in dates if ("HK" if t.endswith(".HK") else "US") == market]
        benchmark = daily_bars(frames.get("^HSI" if market == "HK" else "SPY"), market, asof)
        latest = str(benchmark.index[-1].date()) if not benchmark.empty else max((dates[t] for t in group), default="")
        stale.extend(t for t in group if dates[t] < latest)
        # Reject globally stale responses; allow weekends and multi-day holidays.
        if latest and (pd.Timestamp(asof or now_iso()).tz_localize(None).normalize() - pd.Timestamp(latest)).days > 5:
            stale.extend(group)
    outcome = "SCAN FAILED" if not downloaded else (
        "PARTIAL DATA" if len(downloaded) != len(tickers[:500]) or scoring_errors or incomplete or stale else "SUCCESS"
    )
    return outcome, {"requested": len(tickers[:500]), "downloaded": len(downloaded), "market_data_dates": sorted(set(dates.values())),
                     "missing": sorted(set(tickers[:500]) - set(downloaded)), "scoring_errors": len(scoring_errors),
                     "incomplete_candles": incomplete, "stale_tickers": sorted(set(stale))}


def archive_scan(results, frames, summary, tickers, scanner, store=None, started=None, run_id=None):
    store = store or SignalStore(storage_settings()[0])
    started = started or now_iso()
    run_id = run_id or uuid.uuid4().hex
    outcome, detail = scan_outcome(tickers, frames, summary, started)
    new_ids = []
    if outcome == "SUCCESS":
        store.update(frames, started)
        new_ids = store.save_buys(results, frames, scanner, created_at=now_iso())
        store.update(frames)
        transitions = store.record_states(results, scanner, summary.get('risk_dashboard',{}).get('regime'))
        if os.environ.get('VCP_STATE_ALERTS') == '1':
            for event in transitions:
                if event['state'] in {'ARMED','TRIGGERED','CONFIRMED','INVALIDATED','GREEN','YELLOW','ORANGE','RED'}:
                    store.enqueue('state:'+event['key'],
                                  f"{scanner} | {event['ticker']} | {event['state']}\nData: {event['source_date']} | COMPLETED EOD\nObserved UTC: {now_iso()}\nResearch/setup transition, not a broker order.")
    # Preserve outcomes and known historical tracking even when downloads are partial.
    elif frames:
        good_frames = {t: f for t, f in frames.items() if t not in detail["stale_tickers"] and t not in detail["incomplete_candles"]}
        store.update(good_frames)
    detail.update(result_rows=len(results), buy_rows=int((results.get("Trade", pd.Series(dtype=str)) == "YES").sum()), new_signals=new_ids)
    store.record_run(run_id, started, outcome, detail)
    return {"run_id": run_id, "outcome": outcome, **detail}


def signal_message(record):
    s = record["snapshot"]
    return (
        f"VCP Scanner | {record['scanner']} / {record['market']}\n"
        f"{record['ticker']} | {s.get('Setup Category', 'N/A')}\n"
        f"Data trading date: {record['source_date']} | Trade = YES\n"
        f"Reference close: {s.get('close', 'N/A')}\n"
        f"Entry trigger: {s.get('Entry Trigger', 'N/A')}\n"
        f"Stop: {s.get('Stop Loss', 'N/A')} | Risk: {s.get('Risk %', 'N/A')}%\n"
        f"2R: {s.get('Target 2R', 'N/A')} | 3R: {s.get('Target 3R', 'N/A')}\n"
        f"Reason: {s.get('Trade Reason', 'N/A')}\n"
        f"State: {s.get('Setup Stage', 'LEGACY')} | Session: {s.get('Session Status', 'EOD')}\n"
        f"Created (UTC): {record.get('created_at', 'N/A')}\n"
        f"Signal ID: {record['id']}\n"
        "Scanner signal only. Simulated entry may not have triggered; no broker order placed."
    )[:4000]


def queue_signal_alerts(store):
    # Reconcile from immutable signals after restart, including a crash before enqueue.
    for record in store.records():
        if record["status"] in {"WAITING ENTRY", "ACTIVE", "TARGET REACHED"}:
            store.enqueue("signal:" + record["id"], signal_message(record))


def send_telegram(token, chat_id, text, post=requests.post):
    """Plain text needs no markup escaping. Never expose credential-bearing URLs."""
    try:
        response = post(f"https://api.telegram.org/bot{token}/sendMessage",
                        json={"chat_id": chat_id, "text": text[:4000]}, timeout=(5, 10))
        payload = response.json()
        if response.ok and payload.get("ok") is True:
            return "SENT", None
        return "FAILED", f"Telegram rejected delivery (HTTP {response.status_code})."
    except (requests.RequestException, ValueError):
        return "UNKNOWN", "Delivery outcome unknown; reconcile in Telegram before retrying."


def deliver_alerts(store, token=None, chat_id=None, sender=send_telegram, operations_only=False):
    configured_token, configured_chat = credentials()
    token = token or configured_token
    chat_id = chat_id or configured_chat
    if not token or not chat_id:
        return {"status": "NOT CONFIGURED", "sent": 0}
    counts = {"status": "COMPLETE", "sent": 0, "failed": 0, "unknown": 0}
    # One attempt per message per invocation. Explicit failures retry on later runs.
    attempted = set()
    while True:
        item = store.claim_notification(attempted, operations_only)
        if item is None:
            break
        attempted.add(item["key"])
        state, error = sender(token, chat_id, item["text"])
        store.finish_notification(item["key"], state, error)
        counts[state.lower()] += 1
    return counts


@contextmanager
def job_lock(store):
    """Single-host process lock; released by the OS on crash."""
    with open(str(store.path) + ".job.lock", "a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another scheduled scan is running.") from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_scheduled_scan(scanner_app, store, retries=2):
    """Use exactly the interactive default universe and filters."""
    tickers = list(scanner_app.US_PRO_UNIVERSE)
    started, run_id = now_iso(), uuid.uuid4().hex
    with job_lock(store):
        store.record_run(run_id, started, "RUNNING", {"requested": len(tickers[:500])})
        report = None
        for attempt in range(retries):
            try:
                results, frames, summary = scanner_app.scan_universe(tickers=tickers, mode=DEFAULT_MODE, **DEFAULT_FILTERS)
                report = archive_scan(results, frames, summary, tickers, DEFAULT_MODE, store, started, run_id)
                if report["outcome"] == "SUCCESS":
                    # Refresh saved custom/HK signals outside today's US universe too.
                    records = store.records()
                    tracked = {r["ticker"] for r in records}
                    benchmarks = {"^HSI" if r["market"] == "HK" else "SPY" for r in records}
                    missing = (tracked | benchmarks) - set(frames)
                    if missing:
                        try:
                            extra = scanner_app.download_daily_data(tuple(sorted(missing)), period="18mo")
                            store.update({**frames, **extra})
                            report["tracking_unavailable"] = sorted(missing - set(extra))
                        except Exception:
                            report["tracking_unavailable"] = sorted(missing)
                    store.record_run(run_id, started, report["outcome"], report)
            except Exception:
                # Do not log exception strings: upstream URLs may contain credentials.
                report = {"run_id": run_id, "outcome": "SCAN FAILED", "error": "Scan or persistence failed; inspect local environment."}
                store.record_run(run_id, started, report["outcome"], report)
            if report["outcome"] == "SUCCESS":
                break
            if attempt + 1 < retries:
                scanner_app.download_daily_data.clear() if hasattr(scanner_app.download_daily_data, "clear") else None
                time.sleep(1)
        if report["outcome"] == "SUCCESS":
            queue_signal_alerts(store)
        else:
            day = pd.Timestamp(started).tz_convert(SCHEDULE_TIMEZONE).date()
            store.enqueue(f"operation:{DEFAULT_MODE}:{day}:{report['outcome']}",
                          f"VCP Scanner: {report['outcome']}. Market data or persistence failed. This is not a 'No Buy today' result. No new Buy alerts sent.")
        # Existing archive reconciliation occurs only after a successful scan.
        report["telegram"] = deliver_alerts(store, operations_only=report["outcome"] != "SUCCESS")
        return report
