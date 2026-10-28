"""Independent SEPA-inspired diagnostics, never replace legacy ranking/BUY gates."""
import numpy as np
import pandas as pd
from vcp_scanner.vnext import features,number


def enhanced_vcp(data,row):
    f=features(data)
    legacy=number(row.get('Final Score'),0)
    if not f: return {'Legacy VCP Score':legacy,'Enhanced VCP Score':None}
    close=data.Close
    ma=f['ma']
    trend=all(np.isfinite(ma[n]) for n in (50,150,200)) and f['close']>ma[50]>ma[150]>ma[200]
    slopes=all(len(data)>=220 and close.rolling(n).mean().iloc[-1]>close.rolling(n).mean().iloc[-21] for n in (150,200))
    near_high=f['close']>=data.High.tail(252).max()*.85
    rs=number(row.get('RS Score'),0)
    contraction=f['tightness']/10
    score=100*(.25*trend+.10*slopes+.10*near_high+.25*contraction+.15*rs/10+.10*f['dry']+.05*(f['distribution']<=1))
    acceleration=(close.pct_change(5).iloc[-1]-close.pct_change(20).iloc[-1]/4)*100
    depth=(1-data.Low.tail(60).min()/data.High.tail(60).max())*100
    exhaustion=f['ma20_distance']>20 and f['upper_wick']>.35
    return {'Legacy VCP Score':legacy,'Enhanced VCP Score':round(float(np.clip(score,0,100)),1),
            'Experimental Momentum Acceleration':round(float(acceleration),2),
            'Experimental Exhaustion':bool(exhaustion),
            'Experimental DBTC':bool(depth>=20 and f['tightness']>=8),
            'Enhanced Distribution Days':f['distribution'],
            'Enhanced Model Status':'RESEARCH ONLY — does not change legacy score/rank/Trade'}


def meta_context(data,benchmark=None,sector=None):
    def relative(other):
        if other is None or len(other)<25 or len(data)<25: return 'UNAVAILABLE'
        b=other.Close.reindex(data.index).ffill()
        ratio=data.Close/b
        return bool(ratio.iloc[-1]>ratio.iloc[-6]) if pd.notna(ratio.iloc[-6]) else 'UNAVAILABLE'
    return {'MET-A RS Improvement':relative(benchmark),'MET-A Sector Confirmation':relative(sector),
            'MET-A Capitulation':bool(len(data)>20 and data.Volume.tail(10).max()>data.Volume.iloc[-30:-10].mean()*2 and data.Close.pct_change().tail(10).min()<-.05)}
