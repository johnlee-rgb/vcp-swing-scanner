"""Additional sourced regime diagnostics; missing input is never a positive vote."""
import os
import pandas as pd


def market_evidence(frames):
    leaders=[s.strip().upper() for s in os.environ.get('VCP_RISK_LEADERS','WDC,NVDA,AVGO').split(',') if s.strip()][:10]
    rows=[]
    spy=frames.get('SPY')
    for ticker in dict.fromkeys(['^SOX',*leaders]):
        d=frames.get(ticker)
        if d is None or len(d)<50 or not {'Low','Close','Volume'}.issubset(d):
            rows.append({'Input':ticker+' leadership','Value':'UNAVAILABLE','Source':'yfinance daily','Observation Date':None,'Freshness':'UNAVAILABLE','Risk Warning':'UNKNOWN'})
            continue
        lows=[d.Low.iloc[-15:-10].min(),d.Low.iloc[-10:-5].min(),d.Low.iloc[-5:].min()]
        lower_lows=lows[2]<lows[1]<lows[0]
        close=d.Close
        distribution=int(((close.pct_change()<-.002)&(d.Volume>d.Volume.shift())).tail(20).sum())
        rs='UNAVAILABLE'
        if spy is not None and len(spy)>30:
            line=close/spy.Close.reindex(d.index).ffill()
            rs=float((line.iloc[-1]/line.iloc[-21]-1)*100)
        rows.append({'Input':ticker+' leadership','Value':float(close.iloc[-1]),
                     'Source':'yfinance daily','Observation Date':str(pd.Timestamp(d.index[-1]).date()),
                     'Freshness':'DAILY OBSERVATION','Risk Warning':bool(lower_lows or distribution>=5),
                     'Successive Lower Lows':bool(lower_lows),'Distribution Days 20D':distribution,
                     'Relative Strength Change 20D %':rs,'Below MA20':bool(close.iloc[-1]<close.tail(20).mean()),
                     'Below MA50':bool(close.iloc[-1]<close.tail(50).mean())})
    return rows
