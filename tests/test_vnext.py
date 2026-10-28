"""Synthetic deterministic correctness cases, not historical stock evidence."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest

import app
from vcp_scanner.vnext import Rules, configured_rules, features, market_risk, meta_assessment, price_plan, vcp_assessment
from vcp_scanner.research import outcome, replay, summarize


def bars(close=100., count=260):
    x = close*(1+.015*np.sin(np.arange(count)*.7))
    x[-1] = close
    d = pd.DataFrame({'Open':x*.998,'High':x*1.01,'Low':x*.99,'Close':x,
                      'Volume':np.full(count,1_000_000.)},index=pd.bdate_range('2025-01-01',periods=count))
    return app.add_indicators(d)


def row(entry=99,stop=94):
    return {'ticker':'TEST','Entry Trigger':entry,'Stop Loss':stop,'Pivot':entry-.1,
            'Setup Quality Score':80,
            'Structural Target':entry+3*(entry-stop),'RS Score':8,'VCP Status':'VALID VCP',
            'contraction count':3,'final contraction %':5,'Setup State':'READY_TO_TRIGGER',
            'Earnings Date':'2027-12-01','Earnings Risk':'LOW RISK'}


GREEN = {'regime':'GREEN','eligible':True}


def observe(d,r=None,regime=GREEN):
    return vcp_assessment(d,r or row(),regime,asof=pd.Timestamp(d.index[-1],tz='UTC')+pd.Timedelta(hours=23))


def test_eog_mandatory_untriggered_regression():
    d = bars(161.10)
    d.loc[d.index[-1],'High'] = 162
    r = row(165.28,149.71)
    r.update({'Final Score':82.7,'VCP Status':'EARLY VCP','Breakout Alert':'NEAR BREAKOUT',
              'Action Label':'READY','Trade':'YES','Accumulation Score':8,'Volume Confirmation':'YES'})
    result = observe(d,r)
    assert result['Trade'] == 'NO'
    assert result['Trigger Status'] == 'ARMED'
    assert result['Risk %'] == pytest.approx(9.4204,abs=.001)
    assert 'Wide stop' in result['Risk Warning']
    assert 'trigger not reached' in result['All Eligibility Blockers']
    assert result['Target 2R'] == pytest.approx(196.42)
    assert result['Target 3R'] == pytest.approx(211.99)


def test_base_dry_up_does_not_confirm_breakout():
    d = bars()
    d.loc[d.index[-1],'Volume'] = 300_000
    r = observe(d)
    assert r['Trade'] == 'NO'
    assert r['Volume Status'] == 'DRY-UP'


def confirmed():
    d = bars()
    d[['Open','High','Low','Close']] = d[['Open','High','Low','Close']].mul(np.linspace(.6,1,len(d)),axis=0)
    d.loc[d.index[-1],['Open','High','Low','Close','Volume']] = [99,100.1,98.9,100,2_000_000]
    return app.add_indicators(d)


def test_confirmed_buy_is_next_session_only():
    r = observe(confirmed())
    assert r['Trade'] == 'YES'
    assert r['Final Action'] == 'CONFIRMED BUY CANDIDATE'
    assert r['Execution Timing'] == 'NEXT SESSION ONLY'


@pytest.mark.parametrize('mutation', ['earnings','red','failed','extended','risk','weak','resistance'])
def test_independent_buy_blockers(mutation):
    d,r,regime = confirmed(),row(),GREEN
    if mutation == 'earnings': r['Earnings Date'] = str(d.index[-1].date())
    if mutation == 'red': regime = {'regime':'RED','eligible':False}
    if mutation == 'failed': r['Setup State'] = 'BREAKOUT_FAILED'
    if mutation == 'extended': r['Entry Trigger'] = 80
    if mutation == 'risk': r['Stop Loss'] = 70
    if mutation == 'weak': r['RS Score'] = 3
    if mutation == 'resistance': r['Structural Target'] = 100
    assert observe(d,r,regime)['Trade'] == 'NO'


def test_invalid_stops_and_risk_budget_caps():
    assert price_plan(100,101)['Suggested Shares'] == 0
    assert price_plan(100,95,open_risk=3000)['Suggested Shares'] == 0
    assert price_plan(100,95,sector_capital=25000)['Suggested Shares'] == 0
    assert price_plan(100,95,regime='RED')['Suggested Shares'] == 0
    assert price_plan(100,95,regime='GREEN')['Suggested Shares'] == 100


def test_missing_regime_cannot_be_green():
    r = market_risk({})
    assert r['regime'] == 'YELLOW'
    assert not r['eligible']
    assert all(r['Freshness'] == 'UNAVAILABLE' for r in r['inputs'])


def test_missing_earnings_blocks_buy():
    r = row()
    r['Earnings Date'] = 'N/A'
    assert observe(confirmed(),r)['Trade'] == 'NO'


def test_zero_range_and_volume_safe():
    d = bars()
    d.loc[d.index[-1],['Open','High','Low','Close','Volume']] = [100,100,100,100,0]
    f = features(d)
    assert f['clv'] == .5
    assert observe(d)['Trade'] == 'NO'
    assert meta_assessment(d)['Trade'] == 'NO'


def test_meta_failed_breakdown_midpoint_and_followthrough():
    d = bars(count=100)
    for i in range(-22,-2):
        c = 110-(i+22)*.6
        d.iloc[i,d.columns.get_indexer(['Open','High','Low','Close','Volume'])] = [c+.8,c+1,c-1,c,2_000_000]
    d.iloc[-3,d.columns.get_indexer(['Open','High','Low','Close','Volume'])] = [100,101,97,98,2_000_000]
    d.iloc[-2,d.columns.get_indexer(['Open','High','Low','Close','Volume'])] = [98,101,95,100.8,800_000]
    d.iloc[-1,d.columns.get_indexer(['Open','High','Low','Close','Volume'])] = [101.2,103,100.8,102.9,4_000_000]
    r = meta_assessment(d,'SYNTHETIC')
    assert r['Failed Breakdown Rejection']
    assert r['Bearish Body Midpoint'] == 99
    assert r['Closing Midpoint Reclaim']
    assert r['Setup Stage'] == 'CONFIRMED'
    assert r['Trade'] == 'NO'
    initial = meta_assessment(d.iloc[:-1],'SYNTHETIC')
    assert initial['Setup Stage'] == 'ARMED'
    assert initial['Trigger Status'] != 'CONFIRMED'
    assert initial['Stop Loss'] < d.Low.iloc[-2]


def test_replay_unchanged_by_future_candles():
    d = bars()
    date = d.index[230]
    a = replay(app,{'TEST':d,'SPY':d,'QQQ':d},'TEST',date)
    changed = d.copy()
    changed.loc[changed.index > date,['Open','High','Low','Close']] *= 5
    b = replay(app,{'TEST':changed,'SPY':d,'QQQ':d},'TEST',date)
    for key in ('Setup Stage','Entry Trigger','Stop Loss','Final Score','Trade'):
        assert a[key] == b[key]
    assert a['Trade'] == 'NO'  # Historical earnings unknown, not borrowed from today.


def test_simulation_cannot_fill_on_signal_day_and_no_fake_win():
    d = bars(count=30)
    r = outcome(d,25,row(150,140))
    assert r['Entry Status'] == 'UNTRIGGERED'
    assert pd.isna(r['Simulated Return %'])
    r = outcome(d,29,row())
    assert r['Entry Status'] == 'UNTRIGGERED'


def test_stop_target_same_bar_ambiguous():
    d = bars(count=30)
    d.iloc[26,d.columns.get_indexer(['Open','High','Low','Close'])] = [100,120,90,105]
    r = outcome(d,25,row(100,95))
    assert r['Ambiguous']
    assert pd.isna(r['Simulated Return %'])


def test_gap_chase_never_fills():
    d = bars(count=30)
    d.iloc[26,d.columns.get_indexer(['Open','High','Low','Close'])] = [110,112,109,111]
    assert outcome(d,25,row(100,95))['Exit Reason'] == 'GAP ABOVE MAXIMUM ENTRY'


def test_gap_stop_conservative():
    d = bars(count=30)
    d.iloc[26,d.columns.get_indexer(['Open','High','Low','Close'])] = [100,102,99,101]
    d.iloc[27,d.columns.get_indexer(['Open','High','Low','Close'])] = [90,93,89,92]
    r = outcome(d,25,row(100,95))
    assert r['Exit Reason'] == 'STOP'
    assert r['Simulated Return %'] < -10


def test_missing_bar_not_false_loss():
    d = bars(count=30)
    d.iloc[26,d.columns.get_loc('Close')] = np.nan
    assert outcome(d,25,row())['Exit Reason'] == 'DATA GAP / INVALID BAR'


def test_win_rate_denominator_and_no_portfolio_claim():
    events = pd.DataFrame([{'Entry Status':'UNTRIGGERED','Simulated Return %':np.nan,'Ambiguous':False,
                            'Holding Sessions':0,'R Multiple':np.nan},
                           {'Entry Status':'CLOSED','Simulated Return %':5,'Ambiguous':False,
                            'Holding Sessions':5,'R Multiple':1}])
    r = summarize(events)
    assert r['Win Rate % (closed only)'] == 100
    assert r['Closed Trades'] == 1
    assert 'NOT CALCULATED' in r['Portfolio Drawdown']


def test_configuration_validation(monkeypatch):
    monkeypatch.setenv('VCP_RULES_JSON','{"max_risk_pct": 8}')
    assert configured_rules().max_risk_pct == 8
    monkeypatch.setenv('VCP_RULES_JSON','{"close_location": 3}')
    with pytest.raises(ValueError): configured_rules()


def test_explicit_regime_override_recorded_and_reduced_size():
    d=confirmed()
    r=vcp_assessment(d,row(),{'regime':'RED','eligible':False},override=True,
                     asof=pd.Timestamp(d.index[-1],tz='UTC')+pd.Timedelta(hours=23))
    assert r['Regime Override']
    assert r['Market Regime Eligibility']=='OVERRIDE'
    assert r['Trade']=='YES'
    assert 'OVERRIDE' in r['Top Supporting Reasons']
    assert r['Suggested Shares'] < observe(d)['Suggested Shares']


def test_split_replay_not_silently_adjusted():
    d=bars()
    d['Stock Splits']=0.
    d.loc[d.index[-10],'Stock Splits']=2.
    assert replay(app,{'TEST':d},'TEST',d.index[-1]) is None


def test_large_upper_wick_cannot_confirm_buy():
    d=confirmed()
    d.loc[d.index[-1],'High']=110
    assert observe(d)['Trade']=='NO'


def test_stale_data_blocks_buy():
    d = confirmed()
    r = vcp_assessment(d,row(),GREEN,asof='2030-01-01T23:00:00Z')
    assert r['Trade'] == 'NO'
    assert r['Data Freshness'] == 'STALE'


def test_state_transitions_persist_and_deduplicate(tmp_path):
    from vcp_scanner.tracking import SignalStore
    path = tmp_path/'states.sqlite3'
    rows = pd.DataFrame([{'ticker':'EOG','Setup Stage':'ARMED','Data Trading Date':'2026-10-27'}])
    assert len(SignalStore(path).record_states(rows,'US')) == 1
    assert not SignalStore(path).record_states(rows,'US')
    rows['Data Trading Date'] = '2026-10-28'
    assert not SignalStore(path).record_states(rows,'US')
    rows['Setup Stage'] = 'CONFIRMED'
    assert len(SignalStore(path).record_states(rows,'US')) == 1


def test_scanner_preserves_score_and_exports_new_states(monkeypatch):
    d = confirmed()
    d.index = pd.bdate_range(end='2026-10-27',periods=len(d))
    raw = {t:d for t in ['TEST','SPY','QQQ','IWM','^VIX']}
    monkeypatch.setattr(app,'download_daily_data',lambda *a,**kw:raw)
    monkeypatch.setattr(app,'download_market_caps',lambda *a:{'TEST':10_000_000_000})
    monkeypatch.setattr(app,'download_earnings_data',lambda *a:{'TEST':{'next_date':'2027-12-01','days_to_earnings':400}})
    results,frames,summary = app.scan_universe(['TEST'],'US Pro Market Scan',10,0,0)
    assert len(results) == 1
    assert 'risk_dashboard' in summary
    r = results.iloc[0]
    legacy = app.build_scan_row('TEST',frames['TEST'],10_000_000_000,
                               {'next_date':'2027-12-01','days_to_earnings':400},
                               summary['market_score'],summary['sector_score'],{},frames,
                               app.SECTOR_ETFS_BY_MODE.get('US Pro Market Scan',['SPY'])[0])
    assert legacy['Final Score'] == r['Final Score']
    assert legacy['Trade'] == r['Legacy Trade']
    assert {'Final Action','Trade Eligibility','Trade','Entry Trigger','Target 2R','Final Score'}.issubset(results)
    exported = app.round_display_values(results.drop(columns=['_pivot','_vcp'])).to_csv(index=False)
    assert 'Trigger Status' in exported


def test_full_streamlit_smoke_without_network(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('VCP_TRACKING_DB',str(tmp_path/'ui.sqlite3'))
    monkeypatch.setenv('VCP_TELEGRAM_CONFIG',str(tmp_path/'none.json'))
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False)
    monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    monkeypatch.setattr(app,'render_ipo_scanner',lambda:None)
    def render():
        import app
        app.main()
    test = AppTest.from_function(render).run(timeout=20)
    assert not test.exception
    names = [tab.label for tab in test.tabs]
    assert 'US Scanner' in names and 'MET-A Research' in names and 'Backtest / Replay' in names


def test_streamlit_scan_and_export_render(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    d=confirmed()
    d.index=pd.bdate_range(end='2026-10-27',periods=len(d))
    raw={t:d for t in ['TEST','SPY','QQQ','IWM','^VIX']}
    monkeypatch.setenv('VCP_TRACKING_DB',str(tmp_path/'scan.sqlite3'))
    monkeypatch.setenv('VCP_TELEGRAM_CONFIG',str(tmp_path/'none.json'))
    monkeypatch.delenv('TELEGRAM_BOT_TOKEN',raising=False)
    monkeypatch.delenv('TELEGRAM_CHAT_ID',raising=False)
    monkeypatch.setattr(app,'US_PRO_UNIVERSE',['TEST'])
    monkeypatch.setitem(app.PRESET_UNIVERSES,'US Pro Market Scan',['TEST'])
    monkeypatch.setattr(app,'download_daily_data',lambda *a,**kw:raw)
    monkeypatch.setattr(app,'download_market_caps',lambda *a:{'TEST':10_000_000_000})
    monkeypatch.setattr(app,'download_earnings_data',lambda *a:{'TEST':{'next_date':'2027-12-01','days_to_earnings':400}})
    monkeypatch.setattr(app,'render_ipo_scanner',lambda:None)
    def render():
        import app
        app.main()
    test=AppTest.from_function(render).run(timeout=20)
    test.button(key='us_run').click().run(timeout=30)
    assert not test.exception
    assert len(test.session_state['us_results']) == 1
    assert len(test.get('download_button')) >= 3


def test_saved_vnext_gap_cap_does_not_change_legacy_policy(tmp_path):
    from vcp_scanner.tracking import SignalStore
    d=bars(count=260)
    d.index=pd.bdate_range(end='2026-10-27',periods=len(d))
    r={**row(100,95),'Trade':'YES','Maximum Acceptable Entry':105,'Setup Category':'VCP Breakout'}
    store=SignalStore(tmp_path/'tracking.sqlite3')
    store.save_buys(pd.DataFrame([r]),{'TEST':d},'US',created_at='2026-10-27T22:00:00Z')
    future=pd.DataFrame({'Open':[110],'High':[112],'Low':[109],'Close':[111], 'Volume':[1_000_000]},index=[pd.Timestamp('2026-10-28')])
    store.update({'TEST':pd.concat([d,future])},'2026-10-28T22:00:00Z')
    record=store.records()[0]
    assert record['status']=='EXPIRED'
    assert not record['performance']['triggered']
