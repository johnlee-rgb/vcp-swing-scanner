"""Small read-only performance view with an explicit daily refresh."""
import streamlit as st

from vcp_scanner.tracking import OPEN_STATES, POLICY, SignalStore, performance_summary, performance_table, storage_settings
from vcp_scanner.telegram_setup import render_telegram_setup


def render_tracking(download):
    st.subheader("Signal Performance")
    path, persistent, message = storage_settings()
    (st.caption if persistent else st.warning)(message)
    st.caption("Automatic schedule: not managed by this page. Deployment setup is documented in docs/SIGNAL_TRACKING.md.")
    render_telegram_setup()
    try:
        store = SignalStore(path)
        records = store.records()
        if st.button("Refresh Tracking", key="signal_tracking_refresh") and records:
            try:
                # The existing 18mo EOD batch downloader is reused unchanged.
                tickers = {r["ticker"] for r in records}
                benchmarks = {"^HSI" if r["market"] == "HK" else "SPY" for r in records}
                frames = download(tuple(sorted(tickers | benchmarks)), period="18mo")
                store.update(frames)
                records = store.records()
                missing = sorted({r["ticker"] for r in records} - set(frames))
                if missing:
                    st.warning("No price update for: " + ", ".join(missing) + ". Previous tracking preserved.")
            except Exception:
                st.warning("Market data update unavailable. Saved signals and previous tracking are preserved.")
        if not records:
            st.info("No Buy signals recorded yet. Run a scan first. Historical unsaved recommendations are not reconstructed.")
            return
        metrics = performance_summary(records)
        columns = st.columns(4)
        for i, (name, value) in enumerate(metrics.items()):
            columns[i % 4].metric(name, "N/A" if value is None else round(value, 2) if isinstance(value, float) else value)
        st.caption("Win rate and average R use resolved closed simulated trades only; untriggered and ambiguous signals are excluded.")
        for label, subset in (("Active Signals", [r for r in records if r["status"] in OPEN_STATES]),
                              ("Closed / Review History", [r for r in records if r["status"] not in OPEN_STATES])):
            st.markdown(f"### {label}")
            if subset:
                table = performance_table(subset)
                columns = [c for c in ["ticker", "Scanner", "Signal Date", "Entry Status", "Status", "entry_date", "entry_price",
                           "return_1d_pct", "return_3d_pct", "return_5d_pct", "return_10d_pct", "return_20d_pct",
                           "simulated_return_pct", "r_multiple", "mfe_pct", "mae_pct", "holding_sessions", "target_events",
                           "last_data_date", "explanation"] if c in table]
                st.dataframe(table[columns], hide_index=True, width="stretch")
            else:
                st.caption("No records.")
        with st.expander("Saved Plans and Simulation Assumptions"):
            for key, value in POLICY.items():
                st.write(f"{key}: {value}")
            st.caption("Selection returns measure reference-close performance; simulated returns include 10 bps per side. No portfolio return is inferred.")
            choice = st.selectbox("Saved Signal", [r["id"] for r in records], format_func=lambda sid: next(f"{r['ticker']} | {r['source_date']} | {sid}" for r in records if r["id"] == sid))
            selected = next(r for r in records if r["id"] == choice)
            st.json(selected["snapshot"])
            st.json(selected["performance"])
        with st.expander("Scan and Notification Status"):
            with store.connect() as db:
                st.dataframe([dict(r) for r in db.execute("SELECT id,started_at,finished_at,outcome,detail FROM runs ORDER BY started_at DESC LIMIT 20")], width="stretch")
                st.dataframe([dict(r) for r in db.execute("SELECT key,state,attempts,updated_at,error FROM notifications ORDER BY updated_at DESC LIMIT 20")], width="stretch")
    except Exception:
        st.warning("Signal storage is unavailable. Check the configured database path and disk permissions. Scanner decisions are unaffected.")
