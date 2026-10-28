"""Standalone daily scanner job. Credentials are read from the environment only."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from vcp_scanner.tracking import SignalStore, storage_settings
from vcp_scanner.workflow import deliver_alerts, run_scheduled_scan, send_telegram
from vcp_scanner.telegram_setup import credentials


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["scan", "deliver", "test-notification", "telegram-setup"])
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--confirm-send", action="store_true")
    parser.add_argument("--confirm-read-updates", action="store_true")
    args = parser.parse_args()
    if args.command == "scan" and not args.worker:
        # Bound the whole legacy downloader without modifying yfinance behavior.
        child = subprocess.Popen([sys.executable, __file__, "scan", "--worker"], start_new_session=True)
        try:
            return child.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
            store = SignalStore(storage_settings()[0])
            from vcp_scanner.tracking import now_iso
            from vcp_scanner.workflow import DEFAULT_MODE
            stamp = now_iso()
            with store.connect() as db:
                db.execute("UPDATE runs SET outcome='SCAN FAILED',finished_at=? WHERE outcome='RUNNING'", (stamp,))
            store.enqueue("operation:timeout:" + stamp[:10], f"VCP Scanner: SCAN FAILED. {DEFAULT_MODE} exceeded runtime limit; not a zero-Buy result.")
            deliver_alerts(store, operations_only=True)
            print("SCAN FAILED: runtime limit exceeded.")
            return 1
    token, chat_id = credentials()
    if args.command == "telegram-setup":
        if not token or not args.confirm_read_updates:
            print("Set TELEGRAM_BOT_TOKEN privately, open your bot and press Start. Run again with --confirm-read-updates. No phone lookup is used.")
            return 1
        import requests
        try:
            response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"timeout": 0}, timeout=(5, 10))
            response.raise_for_status()
            payload = response.json()
            ids = {u["message"]["chat"]["id"] for u in payload.get("result", []) if u.get("message", {}).get("chat", {}).get("type") == "private" and u["message"].get("text") == "/start"}
            print("Private /start chat IDs (confirm your own chat before configuring):", sorted(ids))
            print("No IDs: press Start/send /start; an existing webhook or another consumer may prevent getUpdates.") if not ids else None
            return 0
        except (requests.RequestException, ValueError, KeyError):
            print("Unable to read bot updates. Check bot credentials/webhook configuration. No secrets printed.")
            return 1
    if args.command == "test-notification":
        if not args.confirm_send or not token or not chat_id:
            print("Requires configured TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID and --confirm-send.")
            return 1
        state, _ = send_telegram(token, chat_id, "VCP Scanner test notification. No trade or order placed.")
        print(state)
        return 0 if state == "SENT" else 1
    store = SignalStore(storage_settings()[0])
    if args.command == "deliver":
        print(json.dumps(deliver_alerts(store)))
        return 0
    import app
    print(storage_settings()[2])
    report = run_scheduled_scan(app, store)
    print(json.dumps(report))
    return 0 if report["outcome"] == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
