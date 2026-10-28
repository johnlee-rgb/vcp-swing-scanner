"""Additional research views; only uses completed scan data, no startup IO."""
from dataclasses import asdict, replace

import pandas as pd
import streamlit as st

from vcp_scanner.vnext import configured_rules, regime_override_enabled, market_risk, meta_assessment, price_plan
from vcp_scanner.research import backtest, replay, summarize


def render_vnext(app, view):
    frames = {}
    for prefix in ('us','hk'):
        frames.update(st.session_state.get(prefix+'_indicator_data',{}))
    results = [st.session_state.get(p+'_results',pd.DataFrame()) for p in ('us','hk')]
    results = pd.concat([r for r in results if not r.empty],ignore_index=True) if any(not r.empty for r in results) else pd.DataFrame()
    try:
        rules = configured_rules()
    except (ValueError,TypeError):
        st.error('Invalid VCP_RULES_JSON configuration. Correct configuration before scanning.')
        return
    if view == 'health':
        st.subheader('Settings and Data Health')
        st.json(asdict(rules))
        if regime_override_enabled():
            st.warning('EXPLICIT MARKET REGIME OVERRIDE ACTIVE. VCP_REGIME_OVERRIDE=1; this is recorded on every result.')
        st.caption('Scanner and scheduled job share VCP_RULES_JSON. Capital sizing assumes zero existing open/sector risk unless supplied to the risk calculator; not a portfolio allocation approval.')
        st.warning('Daily data is not real-time. Earnings weekdays are a conservative estimate, not an exchange holiday calendar. Missing earnings blocks new confirmed eligibility.')
        if not results.empty:
            cols = [c for c in ['ticker','Data Trading Date','Data Freshness','Data Completeness','Earnings Date','Trade Eligibility','All Eligibility Blockers'] if c in results]
            st.dataframe(results[cols],hide_index=True)
        with st.form('vnext_sizing'):
            equity = st.number_input('Account equity',min_value=0.0,value=rules.account_equity)
            budget = st.number_input('Risk per trade %',min_value=0.0,max_value=100.0,value=rules.risk_budget_pct)
            entry = st.number_input('Sizing entry',min_value=0.0,value=100.0)
            stop = st.number_input('Sizing stop',min_value=0.0,value=95.0)
            open_risk = st.number_input('Existing aggregate open risk (cash)',min_value=0.0,value=0.0)
            sector = st.number_input('Existing sector capital',min_value=0.0,value=0.0)
            if st.form_submit_button('Calculate research size'):
                st.write(price_plan(entry,stop,replace(rules,account_equity=equity,risk_budget_pct=budget),open_risk,sector))
        return
    if not frames:
        st.info('Run scan first. No historical signals are invented.')
        return
    if view == 'risk':
        risk = market_risk(frames,rules=rules)
        st.subheader('Market Risk: '+risk['regime'])
        st.write(risk['coverage'])
        st.write('; '.join(risk['reasons']) or 'Available inputs constructive')
        st.dataframe(pd.DataFrame(risk['inputs']),hide_index=True)
        st.caption('Unavailable indices/yields are not positive votes. Sample breadth is not exchange advance/decline breadth. Yield warning defaults: 10Y 4.75%, 30Y 5.30%. No automatic liquidation.')
    elif view == 'meta':
        st.subheader('MET-A Early Reversal — Research Only')
        enabled = st.checkbox('Enable MET-A research',value=True,key='meta_enabled')
        if enabled and not results.empty:
            rows = [meta_assessment(frames[t],t,rules) for t in results.ticker if t in frames]
            output = pd.DataFrame(rows)
            if not output.empty:
                output = output[output.get('Research Candidate',pd.Series(False,index=output.index)).fillna(False)]
                st.dataframe(output,hide_index=True)
                st.download_button('Download MET-A Research CSV',output.to_csv(index=False).encode(),file_name='meta_research.csv',mime='text/csv')
            st.warning('WATCH is not BUY. MET-A eligibility remains disabled; real historical case verification and calibration are not complete.')
    elif view == 'combined':
        st.subheader('Combined Watchlist')
        if not results.empty:
            cols = [c for c in ['ticker','Sector / Industry','Strategy','Final Action','Setup Stage','Trigger Status','Trade Eligibility','Trade','Setup Quality Score','Market Risk Regime','Entry Trigger','Stop Loss','Risk %','Target 2R','Target 3R','Top Supporting Reasons','Reasons NOT to Buy','Next Required Confirmation'] if c in results]
            st.dataframe(results[cols],hide_index=True)
        if st.session_state.get('meta_enabled',True) and not results.empty:
            meta = pd.DataFrame([meta_assessment(frames[t],t,rules) for t in results.ticker if t in frames])
            if 'Research Candidate' in meta:
                st.dataframe(meta[meta['Research Candidate'].fillna(False)],hide_index=True)
    elif view == 'research':
        st.subheader('Historical Replay and Event Study')
        st.warning('Reconstructed research, not saved recommendations. Current universe has survivorship bias. No profitability claim, portfolio return or drawdown. Missing historical earnings prevents production eligibility.')
        tickers = sorted(set(results.ticker)) if not results.empty else sorted(frames)
        ticker = st.selectbox('Research ticker',tickers,key='vnext_replay_ticker')
        strategy = st.selectbox('Research strategy',['VCP','MET-A'])
        dates = pd.to_datetime(frames[ticker].index)
        date = st.date_input('Replay date',value=dates[-1].date(),min_value=dates[0].date(),max_value=dates[-1].date())
        if st.button('Replay selected date'):
            row = replay(app,frames,ticker,date,strategy,rules)
            if row: st.json(row)
            else: st.warning('Insufficient validated historical prefix or unresolved corporate action.')
        with st.form('vnext_backtest'):
            start = st.date_input('Research start',value=dates[max(0,len(dates)-126)].date())
            end = st.date_input('Research end',value=dates[-1].date())
            variant = st.selectbox('Signal variant',['CONFIRMED','WATCH','MIDPOINT'] if strategy == 'MET-A' else ['CONFIRMED','EARLY'])
            run = st.form_submit_button('Run historical event study')
        if run:
            if start >= end:
                st.warning('Start must be before end.')
            else:
                with st.spinner('Replaying historical prefixes...'):
                    events = backtest(app,frames,ticker,start,end,strategy,variant,rules)
                st.write(summarize(events))
                st.dataframe(events,hide_index=True)
                if not events.empty:
                    st.download_button('Download research events',events.to_csv(index=False).encode(),file_name='research_events.csv')
                    for group in ('Evaluation','Market Risk Regime','Sector / Industry','Historical Earnings Coverage'):
                        if group in events:
                            st.write(group)
                            st.dataframe(pd.DataFrame([{group:k,**summarize(v)} for k,v in events.groupby(group)]),hide_index=True)
