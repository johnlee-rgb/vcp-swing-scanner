"""Offline fixtures: SEC publication timing, cloud durability and funded research."""
import json
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import requests

import app
from vcp_scanner.ownership import (availability,parse_form4,parse_13f,visible_at,holding_changes,
                                   cluster_buying,concentration,map_cusips,SecClient,edgar_filings,normalize_disclosure_export)
from vcp_scanner.cloud_store import CloudStore
from vcp_scanner.enhanced import enhanced_vcp,meta_context
from vcp_scanner.sessions import completed_session,sessions_until
from vcp_scanner.performance import metrics,portfolio,portfolio_metrics,win_interval,walk_forward,vectorbt_benchmark
from vcp_scanner.tracking import SignalStore


def form4(code='P',owner='123',extra='',doctype='4'):
    return f'''<ownershipDocument><documentType>{doctype}</documentType><issuer><issuerCik>1</issuerCik><issuerName>Fixture</issuerName><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer>
    <reportingOwner><reportingOwnerId><rptOwnerCik>{owner}</rptOwnerCik><rptOwnerName>Test insider</rptOwnerName></reportingOwnerId><reportingOwnerRelationship><isDirector>1</isDirector></reportingOwnerRelationship></reportingOwner>
    <nonDerivativeTable><nonDerivativeTransaction><transactionDate><value>2026-10-01</value></transactionDate><transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>
    <transactionAmounts><transactionShares><value>1000</value></transactionShares><transactionPricePerShare><value>100</value></transactionPricePerShare></transactionAmounts>
    <postTransactionAmounts><sharesOwnedFollowingTransaction><value>5000</value></sharesOwnedFollowingTransaction></postTransactionAmounts><ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature></nonDerivativeTransaction></nonDerivativeTable>{extra}</ownershipDocument>'''


def parse(code='P',owner='123',accession='1',extra='',doctype='4'):
    return parse_form4(form4(code,owner,extra,doctype),accession,'2026-10-02','https://www.sec.gov/example')


def holding(period,shares,cusip='123456789',accession=None,**extra):
    return {'id':period+cusip,'accession':accession or period,'manager_cik':'1','manager':'Fixture manager',
            'period':period,'available_at':availability('2026-10-01'),'amendment':False,'complete':True,
            'cusip':cusip,'class':'COM','shares':shares,'put_call':'','share_type':'SH',**extra}


def prices():
    d=pd.DataFrame({'Open':[100.]*30,'High':[102.]*30,'Low':[99.]*30,'Close':[101.]*30,'Volume':[1e6]*30},index=pd.bdate_range('2026-01-01',periods=30))
    return d


def test_form4_fields_and_value():
    r=parse()[0]
    assert r['value']==100000 and r['code']=='P'
    assert r['role']=='Director' and r['ownership_after']==5000
    assert r['direct_indirect']=='D' and not r['derivative']


def test_point_in_time_never_uses_transaction_date():
    rows=parse()
    assert not visible_at(rows,'2026-10-02T16:00:00Z')
    assert visible_at(rows,'2026-10-03T04:00:00Z')
    assert availability('2026-10-02','2026-10-02T10:00:00')=='2026-10-02T14:00:00+00:00'


@pytest.mark.parametrize('code',['A','M','S','F','G'])
def test_grants_exercises_sales_do_not_inflate_cluster(code):
    assert not cluster_buying(parse(code),'2026-10-05T00:00:00Z')


def test_cluster_unique_people_and_duplicate_filings():
    a=parse(owner='123',accession='a');b=parse(owner='456',accession='b')
    r=cluster_buying(a+a+b,'2026-10-05T00:00:00Z')[0]
    assert r['cluster'] and r['distinct_insiders']==2
    assert r['reported_purchase_value']==200000


def test_arrangements_and_amendments_excluded():
    assert not cluster_buying(parse(extra='<aff10b5One>1</aff10b5One>'),'2026-10-05')
    assert not cluster_buying(parse(doctype='4/A'),'2026-10-05')


def test_xml_entity_expansion_rejected():
    with pytest.raises(Exception):
        parse_form4('<!DOCTYPE x [<!ENTITY x SYSTEM "file:///etc/passwd">]><ownershipDocument>&x;</ownershipDocument>','1','2026-01-01','SEC')


def test_namespaced_13f():
    text='<informationTable xmlns="urn:test"><infoTable><nameOfIssuer>Fixture</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>123456789</cusip><value>500</value><shrsOrPrnAmt><sshPrnamt>100</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable></informationTable>'
    r=parse_13f(text,{'accession':'abc'})[0]
    assert r['shares']==100 and r['reported_value']==500
    assert 'CUSIP ONLY' in r['identifier_status']


def test_holding_changes_baseline_not_new_and_true_exits():
    old=holding('2026-03-31',100)
    new=holding('2026-06-30',150)
    prior_only=holding('2026-03-31',50,cusip='999999999')
    assert holding_changes([old],'2026-10-03')[0]['status']=='BASELINE / PRIOR UNAVAILABLE'
    out={r['cusip']:r for r in holding_changes([old,new,prior_only],'2026-10-03')}
    assert out['123456789']['status']=='INCREASED' and out['123456789']['change_pct']==50
    assert out['999999999']['status']=='CLOSED'


def test_incomplete_and_amended_snapshot_no_false_exits():
    a=holding('2026-03-31',100)
    b=holding('2026-06-30',50,cusip='other',complete=False)
    assert all(r['status']!='CLOSED' for r in holding_changes([a,b],'2026-10-03'))
    b.update(complete=True,amendment=True)
    assert all(r['status']!='CLOSED' for r in holding_changes([a,b],'2026-10-03'))


def test_nonadjacent_quarters_not_qoq():
    out=holding_changes([holding('2025-12-31',10),holding('2026-06-30',100)],'2026-10-03')
    assert out[0]['status']=='BASELINE / PRIOR UNAVAILABLE'


def test_mapping_requires_sourced_valid_dates_and_no_ambiguity():
    rows=[holding('2026-06-30',100)]
    m={'cusip':'123456789','ticker':'TEST','valid_from':'2026-01-01','source_url':'https://www.sec.gov/mapping'}
    assert map_cusips(rows,[m],'2026-07-01')[0]['ticker']=='TEST'
    assert map_cusips(rows,[m],'2025-01-01')[0]['ticker'] is None
    assert map_cusips(rows,[m,{**m,'ticker':'OTHER'}],'2026-07-01')[0]['ticker'] is None


def test_disclosure_export_preserves_availability_and_versions():
    rows=[{'accession':'a','availableAt':'2026-10-03T03:59:59Z','resolvedTicker':'TEST','transactionCode':'P',
           'transactionDate':'2026-10-01','reportingOwnerCik':'1','transactionShares':10,'transactionPricePerShare':20}]
    result=normalize_disclosure_export(rows,'insiders')
    assert result[0]['value']==200 and result[0]['available_at'].startswith('2026-10-03')
    assert not cluster_buying(result,'2026-10-04')  # Unknown arrangement/instrument classification is not positive.
    with pytest.raises(ValueError):normalize_disclosure_export([{**rows[0],'availableAt':None}],'insiders')


def test_negative_or_missing_holdings_never_proves_exit():
    rows=[holding('2026-03-31',100),holding('2026-06-30',None)]
    assert all(r['status']!='CLOSED' for r in holding_changes(rows,'2026-10-03'))


def test_sec_client_policy_cache_and_domain(monkeypatch):
    calls=[]
    monkeypatch.setattr('vcp_scanner.ownership.time.sleep',lambda _:None)
    def get(url,**kw):
        calls.append(kw);return SimpleNamespace(status_code=200,ok=True,text='{}',content=b'{}')
    client=SecClient('Test Research test@example.invalid',get=get)
    assert client.fetch('https://data.sec.gov/a')=='{}'
    client.fetch('https://data.sec.gov/a')
    assert len(calls)==1 and calls[0]['timeout']==(5,20)
    with pytest.raises(ValueError):client.fetch('https://evil.example/a')
    with pytest.raises(ValueError):SecClient('',get=get).fetch('https://data.sec.gov/a')


def test_edgar_adapter_lazy_integration(monkeypatch,tmp_path):
    monkeypatch.setenv('EDGAR_LOCAL_DATA_DIR',str(tmp_path/'edgar'))
    import edgar
    monkeypatch.setenv('SEC_USER_AGENT','Fixture test@example.invalid')
    identity=[]
    monkeypatch.setattr(edgar,'set_identity',lambda s:identity.append(bool(s)))
    class Filings:
        def head(self,n):return self
        data=SimpleNamespace(to_pandas=lambda:pd.DataFrame({'form':['4']}))
    monkeypatch.setattr(edgar,'Company',lambda cik:SimpleNamespace(get_filings=lambda **kw:Filings()))
    assert edgar_filings('1').iloc[0]['form']=='4' and identity


@pytest.mark.parametrize('asof,expected',[
    ('2026-11-26T23:00:00Z','2026-11-25'), # Thanksgiving closed
    ('2026-11-27T17:59:00Z','2026-11-25'), # Before 13:00 ET early close
    ('2026-11-27T18:01:00Z','2026-11-27'),
    ('2026-03-09T20:01:00Z','2026-03-09'), # DST
    ('2026-01-06T20:59:00Z','2026-01-05'), # Standard time
])
def test_exchange_holiday_early_close_dst(asof,expected):
    assert str(pd.Timestamp(completed_session(asof)).date())==expected


def test_earnings_exchange_sessions_skip_holiday():
    assert sessions_until('2026-11-25','2026-11-27')==1


class MemoryCloud(CloudStore):
    def __init__(self):self.values={};self.lease_id='test'
    def put(self,namespace,value,key='latest'):self.values[(namespace,key)]=value
    def get(self,namespace,key='latest'):return self.values.get((namespace,key))
    def heartbeat(self):pass


def test_cloud_tracking_roundtrip_restart_immutable(tmp_path):
    a=SignalStore(tmp_path/'a.sqlite3')
    a.record_run('run','2026-10-01T00:00:00Z','SUCCESS',{'x':1})
    a.record_states(pd.DataFrame([{'ticker':'EOG','Setup Stage':'ARMED','Data Trading Date':'2026-10-01'}]),'US')
    cloud=MemoryCloud();cloud.save_tracking(a)
    b=SignalStore(tmp_path/'b.sqlite3');cloud.restore_tracking(b)
    with b.connect() as db:
        assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM setup_events').fetchone()[0]==1
    cloud.restore_tracking(b)
    with b.connect() as db:assert db.execute('SELECT COUNT(*) FROM runs').fetchone()[0]==1


def test_cloud_incomplete_generation_fails_closed(tmp_path):
    cloud=MemoryCloud();cloud.values[('tracking','current')]={'generation':'bad','tables':{'signals':1}}
    with pytest.raises(RuntimeError):cloud.restore_tracking(SignalStore(tmp_path/'db.sqlite3'))


def test_storage_error_never_leaks_credentials():
    class Failed:
        def request(self,*a,**kw):raise requests.ConnectionError('secret token should never be shown')
    cloud=CloudStore('https://example.invalid','private-token',Failed())
    with pytest.raises(RuntimeError) as e:cloud.get('scans')
    assert 'private-token' not in str(e.value) and 'secret token' not in str(e.value)


def test_enhanced_reference_does_not_mutate_legacy():
    d=app.add_indicators(pd.concat([prices()]*9,ignore_index=True))
    row={'Final Score':82.7,'RS Score':8}
    before=row.copy();r=enhanced_vcp(d,row)
    assert row==before and r['Legacy VCP Score']==82.7
    assert 0<=r['Enhanced VCP Score']<=100


def test_confidence_and_small_sample():
    lo,hi=win_interval(1,1)
    assert lo<100 and hi<=100.00001
    assert win_interval(0,0)==(None,None)


def test_funded_portfolio_no_signal_close_fill_and_stop_loss_preserved():
    d=prices();date=d.index[0]
    d.loc[d.index[1],['Open','High','Low','Close']]=[100,102,90,92]
    signals=pd.DataFrame([{'ticker':'TEST','Signal Date':str(date.date()),'Entry Trigger':100,'Stop Loss':95,'Maximum Acceptable Entry':105}])
    curve,trades=portfolio(signals,{'TEST':d})
    assert len(trades)==1 and trades[0]['pnl']<0
    assert trades[0]['entry_date']!=str(date.date())
    assert portfolio_metrics(curve,100000)['Maximum Drawdown %']<0


def test_untriggered_not_executed_portfolio():
    d=prices()
    signals=pd.DataFrame([{'ticker':'TEST','Signal Date':str(d.index[0].date()),'Entry Trigger':110,'Stop Loss':105,'Maximum Acceptable Entry':115}])
    curve,trades=portfolio(signals,{'TEST':d})
    assert not trades and curve.equity.eq(100000).all()


def test_cloud_streamlit_fails_closed_no_secret(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    import cloud_app
    monkeypatch.delenv('VCP_DASHBOARD_PASSWORD',raising=False)
    # Avoid relying on an absent local Streamlit secrets file.
    monkeypatch.setattr(cloud_app.st,'secrets',{})
    def render():
        import cloud_app
        cloud_app.main()
    at=AppTest.from_function(render).run(timeout=20)
    assert not at.exception
    assert len(at.error)==1 and not at.dataframe


def test_vectorbt_actual_reference_engine():
    d=pd.Series([100.,101.,99.,105.],index=pd.bdate_range('2025-01-01',periods=4))
    r=vectorbt_benchmark(d)
    assert r['Benchmark Return %']==pytest.approx(4.8951048951)
    assert '1.2.0' in r['Engine']
