"""Prefix-only historical replay and event studies, not a portfolio simulator."""
import numpy as np
import pandas as pd

from vcp_scanner.vnext import Rules, features, market_risk, meta_assessment, number, vcp_assessment


def replay(app, frames, ticker, date, strategy='VCP', rules=Rules(), earnings_dates=()):
    cutoff = pd.to_datetime(date, errors='coerce')
    if pd.isna(cutoff): return None
    cutoff = cutoff.tz_localize(None).normalize()
    sliced = {}
    for t,d in frames.items():
        if d is None or d.empty or not {'Open','High','Low','Close','Volume'}.issubset(d):
            continue
        index = pd.to_datetime(d.index, errors='coerce', utc=True).tz_localize(None).normalize()
        part = d.loc[index <= cutoff].copy()
        if not part.empty:
            # Recalculate every indicator on the historical prefix.
            sliced[t] = part
    data = sliced.get(ticker)
    if data is None or len(data) < (25 if strategy == 'MET-A' else 210):
        return None
    if 'Stock Splits' in data and data['Stock Splits'].fillna(0).tail(252).ne(0).any():
        return None  # Corporate-action basis requires explicit reconciliation.
    benchmark = sliced.get('^HSI' if ticker.endswith('.HK') else 'SPY')
    indicated = {t: app.add_indicators(d, benchmark) for t,d in sliced.items()}
    regime = market_risk(indicated, cutoff.tz_localize('UTC')+pd.Timedelta(hours=23), rules)
    if strategy == 'MET-A':
        row = meta_assessment(indicated[ticker],ticker,rules)
        row.update(app.display_sector_metadata(ticker,app.SECTOR_ETF_BY_TICKER.get(ticker,'SPY')))
    else:
        context = indicated.copy()
        score,_,_ = app.calculate_market_score(context)
        sector_score,_ = app.calculate_sector_score('US Pro Market Scan',context)
        # No present-day market cap/earnings/fundamentals in historical decisions.
        future_earnings = sorted(pd.Timestamp(e).tz_localize(None) for e in earnings_dates
                                 if pd.Timestamp(e).tz_localize(None) >= cutoff)
        earnings = {'next_date': str(future_earnings[0].date()),
                    'days_to_earnings': (future_earnings[0]-cutoff).days} if future_earnings else {}
        row = app.build_scan_row(ticker, indicated[ticker],None,earnings,score,sector_score,
                                 {},context,app.SECTOR_ETF_BY_TICKER.get(ticker,'SPY'))
        row.update(vcp_assessment(indicated[ticker],row,regime,rules,
                                 asof=cutoff.tz_localize('UTC')+pd.Timedelta(hours=23)))
    row.update({'Record Provenance': 'RECONSTRUCTED RESEARCH (not original recommendation)',
                'Market Risk Regime': regime['regime'], 'Replay Date': str(cutoff.date()),
                'Historical Earnings Coverage': 'SUPPLIED EVENT DATES (not verified point-in-time)' if earnings_dates else 'UNAVAILABLE',
                'Research Caveat': 'Current universe; survivorship bias; dividends not included; price basis must be verified'})
    return {k:v for k,v in row.items() if not k.startswith('_')}


def outcome(data, index, row, rules=Rules(), hold=20, entry_window=5):
    """Next-session buy-stop, gap cap, stop-first ambiguity, fixed saved stop."""
    ref = number(data.Close.iloc[index])
    entry, stop = number(row.get('Entry Trigger')), number(row.get('Stop Loss'))
    result = {'Entry Status': 'UNTRIGGERED', 'Simulated Return %': np.nan,
              'R Multiple': np.nan, 'Exit Reason': 'NO FILL', 'Ambiguous': False,
              'Holding Sessions': 0, 'MFE %': np.nan, 'MAE %': np.nan,
              '2R Before Stop': None, '3R Before Stop': None, 'Subsequent Lower Low': None}
    for n in (5,10,20):
        result[f'{n}D Forward Return %'] = (number(data.Close.iloc[index+n])/ref-1)*100 if index+n < len(data) and ref > 0 else np.nan
    if not entry > stop > 0:
        result['Exit Reason'] = 'INVALID PLAN'
        return result
    maximum = number(row.get('Maximum Acceptable Entry'),entry*1.05)
    original_risk = entry-stop
    filled, price, best, worst = None, None, None, None
    for i in range(index+1, min(len(data),index+entry_window+hold+1)):
        b = data.iloc[i]
        vals = [number(b.get(c)) for c in ('Open','High','Low','Close','Volume')]
        o,h,l,c,v = vals
        if not all(np.isfinite(vals)) or not 0 < l <= min(o,c) <= max(o,c) <= h or v <= 0:
            result['Exit Reason'] = 'DATA GAP / INVALID BAR'
            result['Entry Status'] = 'UNRESOLVED' if filled else 'UNTRIGGERED'
            return result
        if 'Stock Splits' in data and number(b.get('Stock Splits'),0) != 0:
            result.update({'Entry Status': 'UNRESOLVED', 'Exit Reason': 'SPLIT REQUIRES RECONCILIATION'})
            return result
        if filled is None:
            if i > index+entry_window:
                break
            if o > maximum:
                result['Exit Reason'] = 'GAP ABOVE MAXIMUM ENTRY'
                break
            if h < entry:
                continue
            price = max(entry,o)*(1+rules.cost_bps_per_side/10000)
            if o <= stop or (o < entry and l <= stop):
                result.update({'Entry Status':'AMBIGUOUS','Ambiguous':True,'Exit Reason':'ENTRY/STOP ORDER UNKNOWN'})
                return result
            filled = i
            result.update({'Entry Status':'TRIGGERED','Simulated Entry Date':str(data.index[i]),
                           'Simulated Entry':price})
            best, worst = price, price  # Do not assign pre-fill intraday extremes.
        count = i-filled+1
        target = entry+2*original_risk
        stop_touch, target_touch = l <= stop, h >= target
        if stop_touch and target_touch and o > stop:
            result.update({'Entry Status':'AMBIGUOUS','Ambiguous':True,
                           'Exit Reason':'STOP/TARGET ORDER UNKNOWN','Holding Sessions':count})
            return result
        if target_touch and result['2R Before Stop'] is None:
            result['2R Before Stop'] = True
        if h >= entry+3*original_risk:
            result['3R Before Stop'] = True
        if l < number(row.get('Setup Low'),stop):
            result['Subsequent Lower Low'] = True
        exit_price = min(o,stop) if stop_touch else c if count >= hold else None
        if i > filled:
            # On stop session use gap/open or stop, not unknowable favorable high.
            best = max(best, o if stop_touch else h)
            worst = min(worst, min(o,stop) if stop_touch else l)
        if exit_price is not None:
            exit_price *= 1-rules.cost_bps_per_side/10000
            result.update({'Entry Status':'CLOSED','Simulated Return %':(exit_price/price-1)*100,
                           'R Multiple':(exit_price-price)/original_risk,
                           'Exit Reason':'STOP' if stop_touch else 'TIME EXIT',
                           'Exit Date':str(data.index[i]), 'Holding Sessions':count,
                           'MFE %':(best/price-1)*100,'MAE %':(worst/price-1)*100})
            if result['2R Before Stop'] is None: result['2R Before Stop'] = False
            if result['3R Before Stop'] is None: result['3R Before Stop'] = False
            if result['Subsequent Lower Low'] is None: result['Subsequent Lower Low'] = False
            return result
    if filled is not None:
        result.update({'Entry Status':'OPEN / RIGHT CENSORED', 'Exit Reason':'INSUFFICIENT FUTURE SESSIONS'})
    return result


def backtest(app, frames, ticker, start, end, strategy='VCP', variant='CONFIRMED', rules=Rules(), earnings_dates=(), candidate_filter=None):
    data = frames.get(ticker)
    if data is None or data.empty or not {'Open','High','Low','Close','Volume'}.issubset(data):
        return pd.DataFrame()
    benchmark = frames.get('^HSI' if ticker.endswith('.HK') else 'SPY')
    if benchmark is not None and not benchmark.empty:
        data = data.reindex(data.index.union(benchmark.index)).sort_index()
    rows = []
    active_until = -1
    for i,dt in enumerate(data.index):
        stamp = pd.Timestamp(dt).tz_localize(None)
        if stamp < pd.Timestamp(start) or stamp > pd.Timestamp(end) or i <= active_until:
            continue
        row = replay(app,frames,ticker,stamp,strategy,rules,earnings_dates)
        if not row: continue
        if strategy == 'VCP':
            condition = row['Setup Stage'] == 'CONFIRMED' if variant == 'CONFIRMED' else row['Setup Stage'] in ('ARMED','TRIGGERED')
        else:
            condition = (row.get('Research Candidate',False) if variant == 'WATCH' else
                         row.get('Closing Midpoint Reclaim',False) and row.get('Research Candidate',False) if variant == 'MIDPOINT' else
                         row['Setup Stage'] == 'CONFIRMED')
        if not condition: continue
        if candidate_filter is not None and not candidate_filter(row,stamp):continue
        result = outcome(data,i,row,rules)
        split = pd.Timestamp(start)+(pd.Timestamp(end)-pd.Timestamp(start))*.7
        label = 'OUT OF SAMPLE' if stamp >= split else 'TRAIN / DEVELOPMENT'
        if label == 'TRAIN / DEVELOPMENT' and (not result.get('Exit Date') or pd.Timestamp(result['Exit Date']) >= split):
            label = 'BOUNDARY / PURGED FROM TRAIN'
        rows.append({**row,**result,'Variant':variant,'Signal Date':str(stamp.date()),
                     'Study Eligibility': 'UNGATED SETUP EVENT STUDY; not production trade recommendations',
                     'Evaluation':label})
        # Nonoverlap per ticker/variant; no fabricated independent daily trades.
        if result['Entry Status'] == 'CLOSED':
            active_until = data.index.get_loc(pd.Timestamp(result['Exit Date']))
        elif result['Entry Status'] in ('AMBIGUOUS','OPEN / RIGHT CENSORED'):
            active_until = i+25
    return pd.DataFrame(rows)


def summarize(events):
    if events.empty: return {'Signal Count':0,'Closed Trades':0}
    closed = events[events['Entry Status'] == 'CLOSED']
    returns = pd.to_numeric(closed['Simulated Return %'],errors='coerce').dropna()
    wins, losses = returns[returns>0],returns[returns<0]
    summary = {'Signal Count':len(events),'Closed Trades':len(returns),
            'Ambiguous Trades':int(events.Ambiguous.sum()),
            'Win Rate % (closed only)':100*len(wins)/len(returns) if len(returns) else np.nan,
            'Average Win %':wins.mean(),'Average Loss %':losses.mean(),
            'Expectancy After Costs %':returns.mean(),'Median Return %':returns.median(),
            'Profit Factor':wins.sum()/-losses.sum() if len(losses) else np.nan,
            'Average R':pd.to_numeric(closed.get('R Multiple'),errors='coerce').mean(),
            'Average Holding Sessions':closed['Holding Sessions'].mean(),
            'Portfolio Drawdown': 'NOT CALCULATED: no capital/overlap portfolio model',
            'Exposure': 'Per-trade holding sessions only; no portfolio exposure estimate'}
    for n in (5,10,20):
        if f'{n}D Forward Return %' in events:
            values=pd.to_numeric(events[f'{n}D Forward Return %'],errors='coerce').dropna()
            summary[f'{n}D Forward Mean %']=values.mean()
            summary[f'{n}D Forward Denominator']=len(values)
    for column in ('MFE %','MAE %'):
        if column in closed:
            summary['Average '+column]=pd.to_numeric(closed[column],errors='coerce').mean()
    for column in ('2R Before Stop','Subsequent Lower Low'):
        if column in closed:
            known=closed[column].dropna()
            summary[column+' Frequency %']=100*known.astype(bool).sum()/len(known) if len(known) else np.nan
            summary[column+' Denominator']=len(known)
    return summary
