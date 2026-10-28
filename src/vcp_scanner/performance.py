"""Explicit research comparisons, confidence bounds, and funded daily simulation."""
import math
import numpy as np
import pandas as pd

from vcp_scanner.enhanced import enhanced_vcp
from vcp_scanner.ownership import cluster_buying,holding_changes
from vcp_scanner.research import backtest,summarize
from vcp_scanner.vnext import Rules,number


def win_interval(wins,count):
    if not count: return (None,None)
    z=1.96;p=wins/count;den=1+z*z/count
    center=(p+z*z/(2*count))/den
    half=z*math.sqrt(p*(1-p)/count+z*z/(4*count*count))/den
    return (100*(center-half),100*(center+half))


def metrics(events):
    stats=summarize(events)
    if events.empty:return stats
    closed=events[events['Entry Status'].eq('CLOSED')]
    values=pd.to_numeric(closed['Simulated Return %'],errors='coerce').dropna()
    lo,hi=win_interval(int((values>0).sum()),len(values))
    stats.update({'Win Rate 95% CI Lower':lo,'Win Rate 95% CI Upper':hi,
                  'Sample Warning':'SMALL SAMPLE — not evidence of edge' if len(values)<30 else 'Out-of-sample verification still required',
                  'Executed Trades':int(events.get('Simulated Entry',pd.Series(np.nan,index=events.index)).notna().sum())})
    if '3R Before Stop' in closed:
        known=closed['3R Before Stop'].dropna()
        stats['3R Before Stop %']=100*known.astype(bool).mean() if len(known) else None
        stats['3R Denominator']=len(known)
    return stats


def compare(app,frames,tickers,start,end,rules=Rules(),insiders=(),holdings=(),filters=()):
    all_events=[];summaries=[]
    for ticker in tickers:
        for name,strategy,variant in [('Legacy VCP','VCP','CONFIRMED'),('Enhanced VCP','VCP','CONFIRMED'),
                                       ('MET-A WATCH','MET-A','WATCH'),('MET-A MIDPOINT','MET-A','MIDPOINT'),
                                       ('MET-A CONFIRMED','MET-A','CONFIRMED')]:
            def eligible(event,date):
                enhanced=enhanced_vcp(frames[ticker].loc[:date],event)
                event.update(enhanced)
                if name=='Enhanced VCP' and number(enhanced.get('Enhanced VCP Score'),0)<70:return False
                cutoff=date.tz_localize('America/New_York')+pd.Timedelta(hours=16)
                if 'regime' in filters and event.get('Market Risk Regime') in ('RED','ORANGE'):return False
                if 'insider' in filters and not any(c['ticker']==ticker and c['cluster'] for c in cluster_buying(insiders,cutoff)):return False
                if 'institution' in filters and not any(c.get('ticker')==ticker and c['status'] in ('NEW','INCREASED') for c in holding_changes(holdings,cutoff)):return False
                return True
            e=backtest(app,frames,ticker,start,end,strategy,variant,rules,candidate_filter=eligible)
            selected=[]
            for event in e.to_dict('records'):
                event.update({'Strategy Comparison':name,'ticker':ticker,'Filters':','.join(filters) or 'None',
                              'Filing Coverage':'SUPPLIED FILINGS ONLY' if insiders or holdings else 'UNAVAILABLE'})
                selected.append(event)
            part=pd.DataFrame(selected)
            all_events.extend(selected)
            summaries.append({'ticker':ticker,'Strategy':name,'Filters':','.join(filters),**metrics(part)})
    return pd.DataFrame(all_events),pd.DataFrame(summaries)


def portfolio(signals,frames,rules=Rules(),benchmark=None):
    """Daily funded long-only simulation, next-session entries, stop-first bounds.

    This is distinct from resolved-trade win rates. Every supplied signal is
    considered chronologically, including later losers/open positions.
    """
    if signals.empty:return pd.DataFrame(),[]
    sessions=sorted(set().union(*(set(d.index) for d in frames.values() if d is not None)))
    pending=[];positions={};cash=rules.account_equity;curve=[];trades=[]
    for i,row in signals.iterrows():
        r=row.to_dict();r['_id']=str(i);pending.append(r)
    costs=rules.cost_bps_per_side/10000
    for date in sessions:
        date=pd.Timestamp(date).tz_localize(None)
        mark_equity=cash+sum(p['shares']*p['mark'] for p in positions.values())
        risk_used=sum(p['shares']*max(0,p['fill']-p['stop']) for p in positions.values())
        for r in list(pending):
            signal_date=pd.Timestamp(r['Signal Date']).tz_localize(None)
            if date<=signal_date:continue
            d=frames.get(r['ticker'])
            if d is None or date not in d.index:continue
            bar=d.loc[date]
            vals=[number(bar.get(k)) for k in ('Open','High','Low','Close','Volume')]
            if not all(np.isfinite(vals)) or vals[4]<=0:continue
            o,h,l,c,_=vals
            r['_wait']=r.get('_wait',0)+1
            entry,stop=number(r.get('Entry Trigger')),number(r.get('Stop Loss'))
            maximum=number(r.get('Maximum Acceptable Entry'),entry*1.05)
            if r['_wait']>5 or o>maximum:
                pending.remove(r);continue
            if h<entry:
                if c<stop:pending.remove(r)
                continue
            if r['ticker'] in positions:
                pending.remove(r);continue
            if not entry>stop>0:
                pending.remove(r);continue
            fill=max(entry,o)*(1+costs)
            if (fill-stop)/fill*100>rules.max_risk_pct:
                pending.remove(r);continue
            sector=r.get('Sector / Industry','UNKNOWN')
            sector_used=sum(p['shares']*p['mark'] for p in positions.values() if p['sector']==sector)
            budget=max(0,min(mark_equity*rules.risk_budget_pct/100,
                             mark_equity*rules.max_aggregate_risk_pct/100-risk_used))
            capital=max(0,min(cash,mark_equity*rules.max_allocation_pct/100,
                              mark_equity*rules.max_sector_allocation_pct/100-sector_used))
            shares=max(0,min(math.floor(budget/(fill-stop)),math.floor(capital/fill)))
            if shares:
                cash-=shares*fill
                positions[r['ticker']]={'shares':shares,'fill':fill,'stop':stop,'mark':fill,
                    'entry_date':str(date.date()),'held':0,'sector':sector,'signal':r,
                    'ambiguity':o<entry and l<=stop}
                risk_used+=shares*(fill-stop)
            pending.remove(r)
        unresolved=False
        for ticker,p in list(positions.items()):
            d=frames[ticker]
            if date not in d.index:
                unresolved=True;continue
            b=d.loc[date]
            if not all(np.isfinite(number(b.get(c))) for c in ('Open','High','Low','Close')):
                unresolved=True;continue
            if number(b.get('Volume'),0)<=0:
                unresolved=True;continue
            if number(b.get('Stock Splits'),0)!=0:
                unresolved=True;continue
            p['held']+=1
            p['mark']=float(b.Close)
            stop_hit=b.Low<=p['stop']
            exit_price=(min(float(b.Open),p['stop']) if stop_hit else float(b.Close) if p['held']>=20 else None)
            if exit_price is not None:
                proceeds=exit_price*(1-costs)*p['shares'];cash+=proceeds
                trades.append({'ticker':ticker,'entry_date':p['entry_date'],'exit_date':str(date.date()),
                               'shares':p['shares'],'entry':p['fill'],'exit':exit_price*(1-costs),
                               'pnl':proceeds-p['fill']*p['shares'],'reason':'STOP' if stop_hit else 'TIME',
                               'ambiguity_policy':'STOP FIRST CONSERVATIVE BOUND' if p['ambiguity'] else 'Daily OHLC model'})
                del positions[ticker]
        equity=cash+sum(p['shares']*p['mark'] for p in positions.values())
        if any(date>=pd.Timestamp(r['Signal Date']).tz_localize(None) for r in signals.to_dict('records')):
            curve.append({'date':date,'equity':equity,'cash':cash,'positions':len(positions),
                          'unresolved_data':unresolved,
                          'exposure_pct':100*(equity-cash)/equity if equity else 0})
    result=pd.DataFrame(curve)
    if not result.empty:
        result['drawdown_pct']=(result.equity/result.equity.cummax()-1)*100
    return result,trades


def portfolio_metrics(curve,initial):
    if curve.empty:return {'Portfolio Status':'NO SIMULATION'}
    if initial<=0:return {'Portfolio Status':'NO CAPITAL — performance not calculated'}
    if curve.get('unresolved_data',pd.Series(False,index=curve.index)).any():
        return {'Portfolio Status':'UNRESOLVED — missing held prices or corporate action; performance withheld'}
    returns=curve.equity.pct_change().dropna()
    return {'Portfolio Return %':(curve.equity.iloc[-1]/initial-1)*100,
            'Maximum Drawdown %':float(curve.drawdown_pct.min()),
            'Average Exposure %':float(curve.exposure_pct.mean()),
            'Sharpe (daily, annualized)':float(returns.mean()/returns.std()*np.sqrt(252)) if len(returns)>=60 and returns.std()>0 else None,
            'Portfolio Status':'Explicit funded simulation; daily stop-first conservative bounds, not live results'}


def vectorbt_benchmark(close,capital=100000):
    """Optional private-use reference engine, never substitutes daily stop model."""
    import os,tempfile
    from pathlib import Path
    os.environ.setdefault('NUMBA_CACHE_DIR',str(Path(tempfile.gettempdir())/'vcp-numba-cache'))
    import vectorbt as vbt
    if len(close)<2:return {}
    p=vbt.Portfolio.from_holding(close.astype(float),init_cash=capital,fees=.001,freq='1D')
    return {'Engine':'VectorBT '+vbt.__version__,'Benchmark Return %':float(p.total_return()*100),
            'Benchmark Maximum Drawdown %':float(p.max_drawdown()*100),
            'License':'Apache-2.0 with Commons Clause; personal research only'}


def walk_forward(events,folds=3):
    if events.empty:return pd.DataFrame()
    e=events.copy();e['_date']=pd.to_datetime(e['Signal Date'])
    dates=sorted(e['_date'].unique())
    if len(dates)<folds+1:return pd.DataFrame([{'Status':'Insufficient dates for walk-forward'}])
    windows=np.array_split(dates,folds+1);out=[]
    for i in range(1,len(windows)):
        test_start,test_end=pd.Timestamp(windows[i][0]),pd.Timestamp(windows[i][-1])
        train=e[e['_date']<test_start]
        # Outcomes extending into test are not used for development statistics.
        if 'Exit Date' in train:
            train=train[pd.to_datetime(train['Exit Date'],errors='coerce')<test_start]
        test=e[(e['_date']>=test_start)&(e['_date']<=test_end)]
        out.append({'Fold':i,'Train Signals':len(train),'Test Start':str(test_start.date()),
                    'Test End':str(test_end.date()),**metrics(test)})
    return pd.DataFrame(out)
