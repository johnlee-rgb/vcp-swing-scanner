"""Bounded cloud jobs. No Telegram delivery, no orders, no browser required."""
import argparse
import json
import os
import tempfile
from pathlib import Path

import pandas as pd

import app
from vcp_scanner.cloud_store import CloudStore,local_cloud_settings
from vcp_scanner.enhanced import meta_context
from vcp_scanner.ownership import SecClient,DEFAULT_MANAGERS,holding_changes
from vcp_scanner.performance import compare,portfolio,portfolio_metrics,walk_forward,vectorbt_benchmark
from vcp_scanner.sessions import completed_session
from vcp_scanner.tracking import SignalStore,strategy_version,now_iso,performance_table
from vcp_scanner.vnext import meta_assessment
from vcp_scanner.workflow import archive_scan,DEFAULT_FILTERS,DEFAULT_MODE


def scan_job(cloud,tickers=None,force=False):
    tickers=list(tickers or app.US_PRO_UNIVERSE)[:500]
    source=str(pd.Timestamp(completed_session()).date())
    version=strategy_version()
    old=cloud.get('scans') or {}
    if not force and old.get('source_session')==source and old.get('strategy_version')==version and old.get('universe')==tickers:
        return {'status':'UNCHANGED COMPLETED SESSION','source_session':source}
    with tempfile.TemporaryDirectory(prefix='vcp-cloud-job-') as folder:
        store=SignalStore(Path(folder)/'tracking.sqlite3')
        cloud.restore_tracking(store)
        results,frames,summary=app.scan_universe(tickers,DEFAULT_MODE,**DEFAULT_FILTERS)
        outcome=archive_scan(results,frames,summary,tickers,DEFAULT_MODE,store=store)
        payload={'status':outcome['outcome'],'saved_at':now_iso(),'source_session':source,
                 'runner_source':'GITHUB ACTIONS' if os.environ.get('GITHUB_ACTIONS')=='true' else 'LOCAL VERIFICATION',
                 'github_run_id':os.environ.get('GITHUB_RUN_ID'),
                 'strategy_version':version,'universe':tickers,'summary':summary,
                 'rows':[{k:v for k,v in r.items() if not k.startswith('_')} for r in results.to_dict('records')]}
        cloud.save_tracking(store)
        # Failed/partial scan is saved separately, never overwrites last successful results.
        if outcome['outcome']!='SUCCESS':
            cloud.put('failures',payload)
            return {'status':outcome['outcome'],'source_session':source}
        meta=[{**meta_assessment(frames[t],t),**meta_context(frames[t],frames.get('SPY'),frames.get(app.SECTOR_ETF_BY_TICKER.get(t,'')))}
              for t in results.ticker if t in frames]
        cloud.put('meta',{'status':'RESEARCH ONLY — Trade NO','saved_at':now_iso(),
                          'rows':[r for r in meta if r.get('Research Candidate')]})
        cloud.put('signals',{'saved_at':now_iso(),'status':'Immutable saved signals; simulated results only',
                             'rows':performance_table(store.records()).to_dict('records')})
        # Bounded historical cache for resumed research jobs, not huge repository data.
        for t,d in frames.items():
            if t in tickers or t in ('SPY','QQQ','^SOX','WDC','^TNX','^TYX'):
                cloud.put('prices',{'ticker':t,'rows':d.reset_index().rename(columns={d.index.name or 'index':'date'}).to_dict('records')},t)
        cloud.put('scans',payload,source)
        cloud.put('scans',payload)
        return {'status':'SUCCESS','source_session':source,'rows':len(results),'buys':int(results.Trade.eq('YES').sum())}


def sec_job(cloud):
    client=SecClient()
    insider=(cloud.get('insiders') or {}).get('rows',[])
    holdings=(cloud.get('holdings_raw') or {}).get('rows',[])
    managers=json.loads(os.environ.get('VCP_SEC_MANAGERS',json.dumps(DEFAULT_MANAGERS)))
    issuers=json.loads(os.environ.get('VCP_SEC_ISSUERS','{"DELL":"1571996","NVDA":"1045810"}'))
    failures=[]
    for kind,targets,forms in [('holdings',managers,('13F-HR','13F-HR/A')),('insiders',issuers,('4','4/A'))]:
        for _,cik in list(targets.items())[:5]:
            try:
                for filing in client.recent(cik,forms,4):
                    rows=client.load(filing)
                    if kind=='holdings':holdings.extend(rows)
                    else:insider.extend(rows)
            except Exception as exc:
                failures.append({'cik':str(cik),'error_type':type(exc).__name__})
            cloud.heartbeat()
    holdings=list({r['id']:r for r in holdings}.values())
    insider=list({r['id']:r for r in insider}.values())
    stamp=now_iso()
    cloud.put('holdings_raw',{'rows':holdings,'saved_at':stamp,'failures':failures})
    cloud.put('holdings',{'rows':holding_changes(holdings,stamp),'saved_at':stamp,
                          'status':'SEC delayed disclosures; CUSIP mapping required','failures':failures})
    cloud.put('insiders',{'rows':insider,'saved_at':stamp,'status':'SEC Form 4 research only','failures':failures})
    return {'holdings':len(holdings),'insiders':len(insider),'failures':failures}


def research_job(cloud,ticker='DELL',filters=()):
    frames={}
    for t in (ticker,'SPY','QQQ'):
        obj=cloud.get('prices',t)
        if obj and obj.get('rows'):
            d=pd.DataFrame(obj['rows'])
            d.index=pd.to_datetime(d.pop('date'),utc=True).dt.tz_localize(None)
            frames[t]=d
    if ticker not in frames:raise ValueError('Run successful cloud scan before research; prices unavailable')
    d=frames[ticker]
    start,end=d.index[max(210,len(d)-126)],d.index[-1]
    insider=(cloud.get('insiders') or {}).get('rows',[])
    holdings=(cloud.get('holdings_raw') or {}).get('rows',[])
    events,summaries=compare(app,frames,[ticker],start,end,insiders=insider,holdings=holdings,filters=filters)
    portfolios=[]
    if not events.empty:
        for name,part in events.groupby('Strategy Comparison'):
            curve,trades=portfolio(part,frames)
            portfolios.append({'strategy':name,**portfolio_metrics(curve,100000),'closed_trades':len(trades)})
    reference={}
    for t in ('SPY','QQQ'):
        if t in frames:
            close=frames[t].Close.loc[start:end]
            try:reference[t]=vectorbt_benchmark(close)
            except ImportError:reference[t]={'status':'Install requirements-research.txt for optional VectorBT benchmark'}
    payload={'saved_at':now_iso(),'status':'RESEARCH ONLY — limited data, no profitability claim',
             'rows':summaries.to_dict('records'),'events':events.to_dict('records'),
             'portfolios':portfolios,'benchmarks':reference,'walk_forward':walk_forward(events).to_dict('records'),
             'limitations':['Current-universe survivorship bias','Historical earnings incomplete',
                            'Dividends excluded; unresolved splits withhold portfolio metrics','Filing coverage limited to saved SEC observations']}
    cloud.put('research',payload,ticker)
    cloud.put('research',payload)
    return {'status':'SAVED','ticker':ticker,'events':len(events)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('job',choices=['scan','sec','research'])
    p.add_argument('--tickers',default='')
    p.add_argument('--research-ticker',default='DELL')
    p.add_argument('--filters',default='')
    p.add_argument('--force',action='store_true')
    p.add_argument('--local-config',action='store_true',help='Explicit one-time development verification only')
    args=p.parse_args()
    if args.local_config:
        v=local_cloud_settings()
        os.environ['VCP_CLOUD_URL']=v.get('url','')
        os.environ['VCP_CLOUD_TOKEN']=v.get('WRITE_TOKEN','')
        os.environ.setdefault('SEC_USER_AGENT',v.get('SEC_USER_AGENT',''))
    elif not os.environ.get('VCP_CLOUD_TOKEN') and os.environ.get('ACTIONS_ID_TOKEN_REQUEST_URL'):
        import requests
        from urllib.parse import quote
        url=os.environ.get('VCP_CLOUD_URL','').rstrip('/')
        identity=requests.get(os.environ['ACTIONS_ID_TOKEN_REQUEST_URL']+'&audience='+quote(url,safe=''),
                              headers={'Authorization':'Bearer '+os.environ['ACTIONS_ID_TOKEN_REQUEST_TOKEN']},timeout=(5,20))
        identity.raise_for_status()
        exchange=requests.post(url+'/api/oidc',json={'token':identity.json()['value']},timeout=(5,20))
        if not exchange.ok:raise RuntimeError('Cloud denied this workflow identity')
        credentials=exchange.json()
        os.environ['VCP_CLOUD_TOKEN']=credentials['token']
        if credentials.get('sec_user_agent'):os.environ['SEC_USER_AGENT']=credentials['sec_user_agent']
    cloud=CloudStore()
    with cloud.lease():
        if args.job=='scan':result=scan_job(cloud,args.tickers.split(',') if args.tickers else None,args.force)
        elif args.job=='sec':result=sec_job(cloud)
        else:result=research_job(cloud,args.research_ticker,tuple(filter(None,args.filters.split(','))))
    print(json.dumps(result,default=str))
    if result.get('status') in ('SCAN FAILED','PARTIAL DATA'):raise SystemExit(2)


if __name__=='__main__':main()
