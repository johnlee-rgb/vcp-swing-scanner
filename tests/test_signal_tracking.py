"""Persistent lifecycle tests with fixed OHLCV; never call Telegram/yfinance."""
from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import requests

import app
from vcp_scanner.tracking import SignalStore, daily_bars, evaluate_signal, performance_summary
from vcp_scanner.workflow import (
    DEFAULT_FILTERS, DEFAULT_MODE, SCHEDULE_HOURS, SCHEDULE_TIMEZONE,
    archive_scan, deliver_alerts, job_lock, queue_signal_alerts, run_scheduled_scan,
    scan_outcome, send_telegram,
)

CREATED = "2026-10-01T21:00:00+00:00"
ASOF = "2026-12-01T21:00:00+00:00"


@pytest.fixture(autouse=True)
def fixed_tracking_clock(monkeypatch, tmp_path):
    from vcp_scanner import tracking, workflow
    monkeypatch.setattr(tracking, "now_iso", lambda: CREATED)
    monkeypatch.setattr(workflow, "now_iso", lambda: CREATED)
    monkeypatch.setenv("VCP_TELEGRAM_CONFIG", str(tmp_path / "telegram.json"))


def bars(future=None):
    index = pd.bdate_range(end="2026-10-01", periods=30)
    data = pd.DataFrame({"Open": 100., "High": 101., "Low": 98., "Close": 100., "Adj Close": 100., "Volume": 2e6}, index=index)
    if future:
        dates = pd.bdate_range("2026-10-02", periods=len(future))
        extra = pd.DataFrame(future, columns=["Open", "High", "Low", "Close"], index=dates)
        extra["Adj Close"] = extra["Close"]
        extra["Volume"] = 2e6
        data = pd.concat([data, extra])
    return data


def result(**changes):
    row = {"ticker": "DELL", "Trade": "YES", "Action Label": "READY", "Setup Category": "VCP Breakout",
           "Entry Trigger": 101., "Stop Loss": 95., "Target 2R": 113., "Target 3R": 119., "close": 100.,
           "Final Score": 90., "Trade Reason": "Valid setup", "Risk %": 5.94}
    row.update(changes)
    return pd.DataFrame([row])


def saved(tmp_path):
    store = SignalStore(tmp_path / "signals.sqlite3")
    store.save_buys(result(), {"DELL": bars()}, DEFAULT_MODE, CREATED)
    return store


def test_repeat_concurrent_scans_preserve_original_snapshot(tmp_path):
    store = saved(tmp_path)
    original = store.records()[0]["snapshot"]
    changed = result(**{"Entry Trigger": 103., "Final Score": 99.})
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: SignalStore(store.path).save_buys(changed, {"DELL": bars()}, DEFAULT_MODE, CREATED), range(6)))
    assert len(store.records()) == 1
    assert store.records()[0]["snapshot"] == original
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            db.execute("UPDATE signals SET snapshot='{}'")


def test_next_session_buy_is_an_observation_not_a_second_trade(tmp_path):
    store = saved(tmp_path)
    store.save_buys(result(**{"Entry Trigger": 102}), {"DELL": bars([(101, 104, 100, 103)])}, DEFAULT_MODE, "2026-10-02T21:00:00Z")
    assert len(store.records()) == 1
    assert store.records()[0]["snapshot"]["Entry Trigger"] == 101
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 2


def test_no_signal_day_or_pre_creation_execution(tmp_path):
    store = saved(tmp_path)
    record = store.records()[0]
    assert not evaluate_signal(record, bars())["triggered"]
    data = bars([(105, 107, 104, 106), (106, 108, 105, 107)])
    record["created_at"] = "2026-10-02T21:00:00+00:00"
    perf = evaluate_signal(record, data)
    assert perf["entry_date"] == "2026-10-05"
    assert perf["entry_price"] == 106


def test_gap_fill_returns_and_targets_do_not_force_exit(tmp_path):
    record = saved(tmp_path).records()[0]
    data = bars([(105, 115, 104, 114), (114, 121, 113, 120)])
    perf = evaluate_signal(record, data)
    assert perf["entry_price"] == 105
    assert perf["status"] == "TARGET REACHED"
    assert "final_return_pct" not in perf
    assert perf["return_1d_pct"] == pytest.approx(14)
    assert len(perf["target_events"]) == 2
    assert perf["r_multiple"] == pytest.approx((120*.999 - 105*1.001)/6)


def test_stop_target_ambiguity_is_not_a_winner(tmp_path):
    record = saved(tmp_path).records()[0]
    perf = evaluate_signal(record, bars([(102, 120, 94, 105)]))
    assert perf["status"] == "AMBIGUOUS"
    assert "final_return_pct" not in perf
    record.update(status=perf["status"], performance=perf)
    assert performance_summary([record])["Resolved Closed Trades"] == 0


def test_intraday_trigger_stop_order_is_ambiguous(tmp_path):
    record = saved(tmp_path).records()[0]
    perf = evaluate_signal(record, bars([(100, 105, 94, 103)]))
    assert perf["status"] == "AMBIGUOUS"


def test_stopped_trade_and_closed_record_survive_restart(tmp_path):
    store = saved(tmp_path)
    store.update({"DELL": bars([(102, 105, 101, 104), (93, 96, 92, 94)])}, ASOF)
    records = SignalStore(store.path).records()
    perf = records[0]["performance"]
    assert records[0]["status"] == "STOPPED OUT"
    assert perf["exit_price"] == 93
    assert perf["final_return_pct"] < 0
    assert performance_summary(records)["Win Rate (resolved closed)"] == "0.0%"
    # Same old setup cannot be resurrected by a later repeat.
    store.save_buys(result(), {"DELL": bars([(102, 105, 101, 104)])}, DEFAULT_MODE, ASOF)
    assert len(store.records()) == 1


def test_untriggered_and_missing_data_not_counted_as_losses(tmp_path):
    store = saved(tmp_path)
    store.update({"DELL": bars([(100, 100.5, 99, 100)])}, ASOF)
    before = store.records()
    assert not before[0]["performance"]["triggered"]
    store.update({}, ASOF)
    assert store.records() == before
    assert performance_summary(before)["Resolved Closed Trades"] == 0
    missing_anchor = bars().iloc[:10]
    assert evaluate_signal(before[0], missing_anchor) is None


def test_invalid_ohlc_and_split_do_not_fabricate_results(tmp_path):
    record = saved(tmp_path).records()[0]
    bad = bars([(105, 104, 103, 106)])
    assert evaluate_signal(record, bad) is None
    split = bars()
    split[["Open", "High", "Low", "Close", "Adj Close"]] /= 2
    assert evaluate_signal(record, split)["status"] == "AMBIGUOUS"


def test_structure_invalidation_exits_next_open(tmp_path):
    record = saved(tmp_path).records()[0]
    perf = evaluate_signal(record, bars([(102, 104, 99, 100), (100, 101, 96, 97)]))
    assert perf["status"] == "ACTIVE"
    assert "pending" in perf["explanation"]
    perf = evaluate_signal(record, bars([(102, 104, 99, 100), (100, 101, 96, 97), (96, 99, 94, 98)]))
    assert perf["status"] == "STRUCTURE INVALIDATED"
    assert perf["exit_price"] == 96


def test_twenty_session_expiry_and_selection_horizons(tmp_path):
    record = saved(tmp_path).records()[0]
    perf = evaluate_signal(record, bars([(100, 100.5, 99, 100)]*20))
    assert perf["status"] == "EXPIRED"
    assert not perf["triggered"]
    assert perf["return_20d_pct"] == 0
    active = evaluate_signal(record, bars([(102, 104, 101, 103)]*20))
    assert active["status"] == "EXPIRED"
    assert active["final_return_pct"] is not None


def test_partial_failure_and_zero_buy_are_distinct(tmp_path):
    store = saved(tmp_path)
    good = {"DELL": bars(), "SPY": bars()}
    assert scan_outcome(["DELL"], good, {}, CREATED)[0] == "SUCCESS"
    assert scan_outcome(["DELL", "AAPL"], good, {}, CREATED)[0] == "PARTIAL DATA"
    assert scan_outcome(["DELL"], {}, {}, CREATED)[0] == "SCAN FAILED"
    assert scan_outcome(["DELL"], good, {"rejected": ["DELL: scoring failed (x)"]}, CREATED)[0] == "PARTIAL DATA"
    empty = archive_scan(pd.DataFrame(), good, {}, ["DELL"], DEFAULT_MODE, store, CREATED)
    assert empty["outcome"] == "SUCCESS" and empty["buy_rows"] == 0


def test_incomplete_and_stale_daily_data_are_not_archived(tmp_path):
    data = bars([(101, 103, 100, 102)])
    assert len(daily_bars(data, "US", "2026-10-02T15:00:00Z")) == 30
    assert scan_outcome(["DELL"], {"DELL": data}, {}, "2026-10-02T15:00:00Z")[0] == "PARTIAL DATA"
    assert scan_outcome(["DELL"], {"DELL": bars(), "SPY": data}, {}, "2026-10-02T21:00:00Z")[0] == "PARTIAL DATA"


def test_outbox_deduplicates_on_restart_and_repeated_scans(tmp_path):
    store = saved(tmp_path)
    queue_signal_alerts(store)
    queue_signal_alerts(store)
    calls = []
    def sender(token, chat, text):
        assert len(store.records()) == 1  # persistence preceded notification
        calls.append(text)
        return "SENT", None
    assert deliver_alerts(store, "test-token", "test-chat", sender)["sent"] == 1
    store = SignalStore(store.path)
    queue_signal_alerts(store)
    assert deliver_alerts(store, "test-token", "test-chat", sender)["sent"] == 0
    assert len(calls) == 1


def test_missing_credentials_and_delivery_failure_are_separate(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    store = saved(tmp_path)
    queue_signal_alerts(store)
    assert deliver_alerts(store)["status"] == "NOT CONFIGURED"
    calls = []
    def sender(*args):
        calls.append(1)
        return "FAILED", "HTTP 429"
    for _ in range(5):
        deliver_alerts(store, "test", "chat", sender)
    assert len(calls) == 3
    assert len(store.records()) == 1


def test_unknown_delivery_never_blindly_retries_or_leaks_token(tmp_path):
    store = saved(tmp_path)
    queue_signal_alerts(store)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise requests.Timeout("secret URL must not appear")
    sender = lambda token, chat, text: send_telegram(token, chat, text, post=fail)
    report = deliver_alerts(store, "test-token", "chat", sender)
    assert report["unknown"] == 1
    deliver_alerts(store, "test-token", "chat", sender)
    assert len(calls) == 1
    with store.connect() as db:
        assert "secret" not in db.execute("SELECT error FROM notifications").fetchone()[0]


def test_crashed_sender_and_old_notifications_are_not_replayed(tmp_path, monkeypatch):
    from vcp_scanner import tracking
    store = saved(tmp_path)
    queue_signal_alerts(store)
    item = store.claim_notification()
    assert item is not None
    monkeypatch.setattr(tracking, "now_iso", lambda: "2026-10-01T22:00:00+00:00")
    assert store.claim_notification() is None
    with store.connect() as db:
        assert db.execute("SELECT state FROM notifications").fetchone()[0] == "UNKNOWN"
    another = SignalStore(tmp_path / "old.sqlite3")
    another.save_buys(result(), {"DELL": bars()}, DEFAULT_MODE, CREATED)
    queue_signal_alerts(another)
    monkeypatch.setattr(tracking, "now_iso", lambda: "2026-10-05T21:00:00+00:00")
    assert another.claim_notification() is None
    with another.connect() as db:
        assert db.execute("SELECT state FROM notifications").fetchone()[0] == "SKIPPED"


def test_missing_benchmark_session_preserves_previous_tracking(tmp_path):
    store = saved(tmp_path)
    full = bars([(102, 105, 101, 104), (104, 107, 103, 106)])
    missing = full.drop(pd.Timestamp("2026-10-02"))
    store.update({"DELL": missing, "SPY": full}, ASOF)
    assert store.records()[0]["performance"] == {}


def test_failure_does_not_send_pending_buy_alert(tmp_path):
    store = saved(tmp_path)
    queue_signal_alerts(store)
    store.enqueue("operation:failed", "SCAN FAILED")
    messages = []
    deliver_alerts(store, "test", "chat", lambda *args: (messages.append(args[-1]) or "SENT", None), operations_only=True)
    assert messages == ["SCAN FAILED"]


def test_schedule_and_shared_scan_settings(tmp_path, monkeypatch):
    from vcp_scanner import workflow
    monkeypatch.setattr(workflow, "now_iso", lambda: CREATED)
    import vcp_scanner.tracking as tracking
    monkeypatch.setattr(tracking, "now_iso", lambda: CREATED)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    store = SignalStore(tmp_path / "job.sqlite3")
    calls = []
    rows = result()
    before = rows.copy(deep=True)
    def scan(**kwargs):
        calls.append(kwargs)
        return rows, {"DELL": bars(), "SPY": bars()}, {"scanned": 1}
    fake_app = SimpleNamespace(US_PRO_UNIVERSE=["DELL"], scan_universe=scan)
    first = run_scheduled_scan(fake_app, store)
    second = run_scheduled_scan(fake_app, store)
    assert first["outcome"] == second["outcome"] == "SUCCESS"
    assert len(store.records()) == 1
    assert calls == [{"tickers": ["DELL"], "mode": DEFAULT_MODE, **DEFAULT_FILTERS}]*2
    pd.testing.assert_frame_equal(rows, before)
    assert SCHEDULE_HOURS == (12, 19) and SCHEDULE_TIMEZONE == "Asia/Singapore"
    timer = (app.Path(__file__).resolve().parents[1] / "deploy/vcp-scan.timer").read_text()
    assert "12:00:00 Asia/Singapore" in timer and "19:00:00 Asia/Singapore" in timer


def test_job_lock_prevents_overlapping_workers(tmp_path):
    store = saved(tmp_path)
    with job_lock(store):
        with pytest.raises(RuntimeError, match="running"):
            with job_lock(store):
                pass


def test_failed_run_retries_without_creating_false_zero_buy(tmp_path, monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    from vcp_scanner import workflow
    monkeypatch.setattr(workflow.time, "sleep", lambda *_: None)
    store = SignalStore(tmp_path / "fail.sqlite3")
    calls = []
    def scan(**kwargs):
        calls.append(1)
        return pd.DataFrame(), {}, {"scanned": 1}
    fake = SimpleNamespace(US_PRO_UNIVERSE=["DELL"], scan_universe=scan, download_daily_data=lambda *_: {})
    report = run_scheduled_scan(fake, store)
    assert report["outcome"] == "SCAN FAILED"
    assert len(calls) == 2 and not store.records()
    with store.connect() as db:
        assert db.execute("SELECT outcome FROM runs").fetchone()[0] == "SCAN FAILED"
        assert db.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 1


def test_streamlit_performance_tab_smoke(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv("VCP_TRACKING_DB", str(tmp_path / "ui.sqlite3"))
    monkeypatch.setattr(app, "render_ipo_scanner", lambda: None)
    monkeypatch.setattr(app, "download_daily_data", lambda *a, **k: {})
    def render():
        import app
        app.main()
    test = AppTest.from_function(render).run(timeout=20)
    assert not test.exception
    assert "Signal Performance" in [t.label for t in test.tabs]
    store = SignalStore(tmp_path / "ui.sqlite3")
    store.save_buys(result(), {"DELL": bars()}, DEFAULT_MODE, CREATED)
    test.run(timeout=20)
    assert not test.exception
    test.button(key="signal_tracking_refresh").click().run(timeout=20)
    assert not test.exception
