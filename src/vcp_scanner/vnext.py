"""Point-in-time setup analysis and independent EOD eligibility, no IO/orders."""
from dataclasses import dataclass
import math
import json
import os

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Rules:
    max_risk_pct: float = 10.0
    wide_risk_pct: float = 8.0
    max_extension_pct: float = 5.0
    breakout_volume: float = 1.5
    close_location: float = 0.75
    earnings_sessions: int = 7
    max_age_days: int = 5
    decline_pct: float = 10.0
    ma10_extension_pct: float = 12.0
    ma20_extension_pct: float = 18.0
    min_contractions: int = 2
    max_final_contraction_pct: float = 12.0
    min_setup_quality: float = 60.0
    account_equity: float = 100000.0
    risk_budget_pct: float = 0.5
    max_allocation_pct: float = 10.0
    max_aggregate_risk_pct: float = 3.0
    max_sector_allocation_pct: float = 25.0
    cost_bps_per_side: float = 10.0
    yield_10y_warning: float = 4.75
    yield_30y_warning: float = 5.30


def configured_rules():
    """Optional validated JSON environment settings shared by UI and jobs."""
    text = os.environ.get('VCP_RULES_JSON')
    if not text:
        return Rules()
    values = json.loads(text)
    if not isinstance(values, dict) or set(values)-set(Rules.__dataclass_fields__):
        raise ValueError('Invalid VCP_RULES_JSON keys')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v < 0 for v in values.values()):
        raise ValueError('VCP_RULES_JSON must contain finite nonnegative numbers')
    for k in ('earnings_sessions','max_age_days','min_contractions'):
        if k in values and not float(values[k]).is_integer():
            raise ValueError('Session counts must be integers')
    if 'close_location' in values and values['close_location'] > 1:
        raise ValueError('close_location must be at most 1')
    if any(v > 100 for k,v in values.items() if k.endswith('_pct') or k == 'min_setup_quality'):
        raise ValueError('Percentage/score configuration cannot exceed 100')
    return Rules(**values)


def regime_override_enabled():
    return os.environ.get('VCP_REGIME_OVERRIDE') == '1'


def number(value, default=np.nan):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (ValueError, TypeError):
        return default


def price_plan(entry, stop, rules=Rules(), open_risk=0.0, sector_capital=0.0,
               regime='YELLOW'):
    entry, stop = number(entry), number(stop)
    valid = bool(entry > stop > 0)
    if not valid:
        return {'Risk Eligibility': 'INVALID', 'Risk per Share': np.nan,
                'Risk %': np.nan, 'Target 2R': np.nan, 'Target 3R': np.nan,
                'Suggested Shares': 0, 'Risk Warning': 'Invalid entry/stop relationship'}
    risk = entry - stop
    pct = risk / entry * 100
    equity = max(0, rules.account_equity)
    multiplier = {'GREEN': 1, 'YELLOW': .75, 'ORANGE': .25, 'RED': 0}.get(regime, 0)
    budget = min(equity * rules.risk_budget_pct / 100 * multiplier,
                 max(0, equity * rules.max_aggregate_risk_pct / 100 - open_risk))
    capital = min(equity * rules.max_allocation_pct / 100,
                  max(0, equity * rules.max_sector_allocation_pct / 100 - sector_capital))
    shares = max(0, min(math.floor(budget / risk), math.floor(capital / entry)))
    eligible = pct <= rules.max_risk_pct
    return {'Risk Eligibility': 'ELIGIBLE' if eligible else 'TOO WIDE',
            'Risk per Share': round(risk, 6), 'Risk %': round(pct, 4),
            'Target 2R': round(entry + 2 * risk, 4),
            'Target 3R': round(entry + 3 * risk, 4),
            'Suggested Shares': shares if eligible else 0,
            'Position Risk Budget': round(budget, 2),
            'Transaction Cost bps per Side': rules.cost_bps_per_side,
            'Risk Warning': 'Wide stop for short-term setup' if pct > rules.wide_risk_pct else 'None'}


def features(data):
    """All windows end at supplied observation, never a future swing point."""
    if data is None or len(data) < 25:
        return {}
    d = data.copy()
    if not {'Open', 'High', 'Low', 'Close', 'Volume'}.issubset(d):
        return {}
    for c in ('Open', 'High', 'Low', 'Close', 'Volume'):
        d[c] = pd.to_numeric(d[c], errors='coerce')
    if d[['Open', 'High', 'Low', 'Close', 'Volume']].tail(25).isna().any().any():
        return {}
    if ((d.High < d[['Open', 'Close', 'Low']].max(axis=1)) |
        (d.Low > d[['Open', 'Close', 'High']].min(axis=1)) |
        (d.Low <= 0) | (d.Volume < 0)).tail(25).any():
        return {}
    r = d.iloc[-1]
    width = r.High - r.Low
    avgvol = d.Volume.iloc[-21:-1].mean()
    ranges = d.High - d.Low
    tr = pd.concat([ranges, (d.High-d.Close.shift()).abs(),
                    (d.Low-d.Close.shift()).abs()], axis=1).max(axis=1)
    ma = {n: number(d.Close.tail(n).mean()) if len(d) >= n else np.nan for n in (10,20,50,150,200)}
    close = float(r.Close)
    lower_wick = (min(r.Open, r.Close) - r.Low) / width if width > 0 else 0
    upper_wick = (r.High - max(r.Open, r.Close)) / width if width > 0 else 0
    recent = d.tail(10)
    distribution = int(((recent.Close.diff() < 0) & (recent.Volume > avgvol * 1.25)).sum())
    ranges_contract = ranges.tail(5).mean() < ranges.iloc[-20:-5].mean()
    atr_contract = tr.tail(5).mean() < tr.iloc[-20:-5].mean()
    dry = avgvol > 0 and d.Volume.tail(3).mean() < avgvol * .85
    tight = d.Close.tail(5).max() / d.Close.tail(5).min() - 1 <= .03
    return dict(close=close, high=float(r.High), low=float(r.Low), ma=ma,
                clv=(close-r.Low)/width if width > 0 else .5,
                lower_wick=lower_wick, upper_wick=upper_wick,
                volume_ratio=float(r.Volume/avgvol) if avgvol > 0 else np.nan,
                dry=dry, tight=tight, range_contract=ranges_contract,
                atr_contract=atr_contract, distribution=distribution,
                tightness=int(2*sum([ranges_contract, atr_contract, dry, tight, distribution <= 1])),
                ma10_distance=(close/ma[10]-1)*100,
                ma20_distance=(close/ma[20]-1)*100,
                atr_pct=float(tr.tail(14).mean()/close*100))


def market_risk(frames, asof=None, rules=Rules()):
    """Available daily inputs only; missing/freshness explicitly visible."""
    now = pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    now = now.tz_localize('UTC') if now.tzinfo is None else now.tz_convert('UTC')
    rows, flags = [], []
    for symbol in ('SPY', 'QQQ', '^IXIC', '^SOX', 'WDC', '^TNX', '^TYX'):
        d = frames.get(symbol)
        value, stamp, state, warning = np.nan, None, 'UNAVAILABLE', None
        if d is not None and len(d) and 'Close' in d:
            value = number(d.Close.iloc[-1])
            dt = pd.Timestamp(d.index[-1])
            dt = dt.tz_localize(None) if dt.tzinfo else dt
            stamp = str(dt.date())
            age = (now.tz_localize(None).normalize()-dt.normalize()).days
            state = 'FRESH' if 0 <= age <= rules.max_age_days else 'STALE'
            if not np.isfinite(value):
                state = 'UNAVAILABLE'
            if state == 'FRESH':
                if symbol in ('^TNX', '^TYX'):
                    warning = value > (rules.yield_10y_warning if symbol == '^TNX' else rules.yield_30y_warning)
                elif len(d) >= 50:
                    warning = value < d.Close.tail(20).mean() and value < d.Close.tail(50).mean()
        if warning is not None:
            flags.append((symbol, bool(warning)))
        rows.append({'Input': symbol, 'Value': value, 'Source': 'yfinance daily',
                     'Observation Date': stamp, 'Freshness': state,
                     'Risk Warning': warning if warning is not None else 'UNKNOWN'})
    # Breadth is the scan sample, not exchange advance/decline breadth.
    sample = [d for t,d in frames.items() if t not in {r['Input'] for r in rows}
              and d is not None and len(d) >= 200 and 'Close' in d]
    for n in (20,50,200):
        eligible = [d for d in sample if 0 <= (now.tz_localize(None).normalize() -
                    pd.Timestamp(d.index[-1]).tz_localize(None).normalize()).days <= rules.max_age_days]
        pct = 100*sum(d.Close.iloc[-1] > d.Close.tail(n).mean() for d in eligible)/len(eligible) if eligible else np.nan
        rows.append({'Input': f'Scan sample above MA{n} ({len(eligible)} stocks)',
                     'Value': pct, 'Source': 'Current scan sample, survivorship-biased',
                     'Observation Date': 'Per-stock dates',
                     'Freshness': 'SAMPLE ONLY' if eligible else 'UNAVAILABLE', 'Risk Warning': 'REFERENCE ONLY'})
    core = [v for t,v in flags if t in ('SPY','QQQ')]
    warnings = [t for t,v in flags if v]
    regime = ('YELLOW' if len(core) < 2 else 'RED' if all(core) and len(warnings) >= 3
              else 'ORANGE' if all(core) else 'YELLOW' if warnings or len(flags) < 5 else 'GREEN')
    return {'regime': regime, 'inputs': rows,
            'reasons': ([t+' risk warning' for t in warnings] +
                        [r['Input']+' '+r['Freshness'].lower() for r in rows[:7] if r['Freshness'] != 'FRESH'])[:5],
            'eligible': bool(len(core) == 2 and regime != 'RED'),
            'core_data_date': max((r['Observation Date'] for r in rows if r['Input'] in ('SPY','QQQ') and r['Freshness']=='FRESH'),default=None),
            'coverage': f'{len(flags)}/7 usable regime inputs'}


def vcp_assessment(data, row, regime, rules=Rules(), asof=None, override=False):
    f = features(data)
    if not f:
        return {'Strategy': 'VCP', 'Setup Stage': 'INVALIDATED', 'Trigger Status': 'INVALIDATED',
                'Final Action': 'NO TRADE', 'Trade': 'NO', 'Trade Eligibility': 'NO',
                'Trade Reason': 'NO TRADE: missing or invalid OHLCV',
                'Reasons NOT to Buy': 'Missing or invalid OHLCV'}
    entry, stop = number(row.get('Entry Trigger')), number(row.get('Stop Loss'))
    pivot = number(row.get('Pivot'))
    plan = price_plan(entry, stop, rules, regime='ORANGE' if override and not regime['eligible'] else regime['regime'])
    valid = row.get('VCP Status') in ('VALID VCP','EARLY VCP') or row.get('Setup Category') == 'Momentum Breakout'
    contractions = int(number(row.get('contraction count'), 0))
    final_contraction = number(row.get('final contraction %'))
    textbook = (row.get('VCP Status') == 'VALID VCP' and contractions >= rules.min_contractions
                and final_contraction <= rules.max_final_contraction_pct and f['tightness'] >= 6)
    below50 = f['close'] < f['ma'][50]
    failed = (row.get('Setup State') in ('FAILED','BREAKOUT_FAILED') or
              row.get('Character Change Flag') == 'CHARACTER CHANGE' or row.get('Stage Label') == 'FAILED STAGE')
    reached = bool(entry > 0 and f['high'] >= entry)
    close_reclaim = bool(entry > 0 and f['close'] >= entry)
    expansion = f['volume_ratio'] >= rules.breakout_volume
    confirmed = reached and close_reclaim and expansion and f['clv'] >= rules.close_location
    distance = (f['close']/entry-1)*100 if entry > 0 else np.nan
    extended = (distance > rules.max_extension_pct or f['ma10_distance'] > rules.ma10_extension_pct
                or f['ma20_distance'] > rules.ma20_extension_pct)
    blockers, supporting = [], []
    if not valid: blockers.append('Setup not sufficiently developed')
    else: supporting.append('Valid legacy setup')
    if number(row.get('Setup Quality Score'),0) < rules.min_setup_quality:
        blockers.append('Setup quality below configured minimum or unavailable')
    if not pivot > 0: blockers.append('Pivot unavailable')
    if not reached: blockers.append('Entry trigger not reached')
    elif not close_reclaim: blockers.append('Intraday touch only; no closing reclaim')
    if not expansion: blockers.append('Breakout volume expansion missing (base dry-up is not confirmation)')
    if f['clv'] < rules.close_location: blockers.append('Close not strong enough')
    if extended: blockers.append('Extended from entry/MA10/MA20; wait reset')
    if plan['Risk Eligibility'] != 'ELIGIBLE': blockers.append('Invalid or excessive stop distance')
    if plan['Suggested Shares'] <= 0: blockers.append('No available position risk/capital budget')
    structural = number(row.get('Structural Target'))
    if not structural > entry or not (entry > stop > 0) or (structural-entry)/(entry-stop) < 2:
        blockers.append('Structural resistance / reward does not support 2R')
    if failed or below50: blockers.append('Failed structure / below MA50')
    ma = f['ma']
    alignment = all(np.isfinite(ma[n]) for n in (50,150,200)) and f['close'] > ma[50] > ma[150] > ma[200]
    rising = len(data) >= 220 and all(data.Close.rolling(n).mean().iloc[-1] > data.Close.rolling(n).mean().iloc[-21] for n in (150,200))
    if not alignment or not rising:
        blockers.append('Stage 2 trend template not confirmed')
    if not regime['eligible'] and not override: blockers.append('Market regime blocks entry or core inputs unavailable')
    if override: supporting.append('EXPLICIT MARKET OVERRIDE RECORDED')
    earnings_date = pd.to_datetime(row.get('Earnings Date'), errors='coerce')
    source = pd.Timestamp(data.index[-1]).tz_localize(None).normalize()
    blackout = row.get('Earnings Risk') == 'HIGH RISK'
    if pd.notna(earnings_date):
        earnings_date = earnings_date.tz_localize(None).normalize()
        # Conservative weekdays estimate, explicitly not an exchange calendar.
        days = np.busday_count(source.date(), earnings_date.date())
        blackout = 0 <= days <= rules.earnings_sessions
    if blackout: blockers.append('Earnings within blackout window')
    elif pd.isna(earnings_date) or earnings_date < source:
        blockers.append('Earnings date unavailable or expired; verify before entry')
    now = pd.Timestamp(asof or pd.Timestamp.now(tz='UTC')).tz_localize(None)
    age = (now.normalize()-source).days
    if age < 0 or age > rules.max_age_days: blockers.append('Stale or future market-data date')
    if regime.get('core_data_date') and str(source.date()) < regime['core_data_date']:
        blockers.append('Stock price lags latest benchmark session')
    rs = number(row.get('RS Score'))
    if not rs >= 5: blockers.append('RS too weak or unavailable')
    stage = 'INVALIDATED' if failed or below50 else 'CONFIRMED' if confirmed else 'TRIGGERED' if reached else 'ARMED' if valid and -3 <= distance <= 0 else 'WATCH'
    eligible = not blockers and confirmed
    final = ('CONFIRMED BUY CANDIDATE' if eligible else 'NO TRADE' if stage == 'INVALIDATED'
             else 'BREAKOUT TRIGGERED' if stage in ('TRIGGERED','CONFIRMED') and not extended
             else 'READY TO TRIGGER' if stage == 'ARMED' else 'READY TO WATCH')
    setup = ('FAILED BREAKOUT' if stage == 'INVALIDATED' else 'EXTENDED' if extended
             else 'VCP BREAKOUT' if textbook and reached else 'VCP ARMED' if textbook
             else 'VCP DEVELOPING' if valid else 'TREND LEADER' if rs >= 7 else 'EARLY BASE')
    supporting += [name for name,ok in [('Sequential contraction structure',textbook),
                   ('Tight closes',f['tight']),('Volume dry-up',f['dry']),
                   ('Closing reclaim with expansion',confirmed)] if ok]
    base = data.iloc[-61:-1]
    depth = (base.High.max()-base.Low.min())/base.High.max()*100
    # Confirmed local peaks only: each peak has two completed bars on either side.
    highs = data.High.tail(252)
    peaks = highs[highs.eq(highs.rolling(5,center=True).max()) & highs.gt(entry)]
    resistance = float(peaks.min()) if len(peaks) else np.nan
    resistance_warning = ('Nearby historical swing resistance before 2R; measured targets are not guaranteed'
                          if resistance < plan['Target 2R'] else 'No identified swing resistance before 2R; not proof of clear supply')
    max_entry = entry*(1+rules.max_extension_pct/100)
    if 0 < rules.max_risk_pct < 100 and stop > 0:
        max_entry = min(max_entry,stop/(1-rules.max_risk_pct/100))
    if structural > entry and stop > 0:
        max_entry = min(max_entry,(structural+2*stop)/3)
    checks = {'Stage 2 alignment':alignment,'MA150/200 rising':rising,
              'Multiple contractions':contractions >= rules.min_contractions,
              'Final contraction controlled':final_contraction <= rules.max_final_contraction_pct,
              'ATR compression':f['atr_contract'],'Range compression':f['range_contract'],
              'Volume dry-up':f['dry'],'Tight closes':f['tight']}
    return {'Strategy': 'VCP', 'Setup Stage': stage, 'VCP Development': setup,
            'Trigger Status': stage, 'Trade Eligibility': 'YES' if eligible else 'NO',
            'Final Action': final, 'Trade': 'YES' if eligible else 'NO',
            'WATCHLIST FLAG': 'NO' if eligible or stage == 'INVALIDATED' else 'YES',
            'Trade Reason': final+': '+('Confirmed at daily close; next-session candidate, recheck gap/stop/earnings' if eligible else '; '.join(blockers)),
            'Market Risk Regime': regime['regime'], 'Market Regime Eligibility': 'OVERRIDE' if override else 'YES' if regime['eligible'] else 'NO',
            'Regime Override': bool(override), 'VCP Tightness Score': f['tightness'],
            'Top Supporting Reasons': '; '.join(supporting[:3]) or 'None',
            'Reasons NOT to Buy': '; '.join(blockers[:3]) or 'Revalidate next-session gap and risk',
            'All Eligibility Blockers': '; '.join(blockers) or 'None',
            'Next Required Confirmation': 'Next-session fill within maximum entry; no same-close execution' if eligible else '; '.join(blockers[:2]),
            'Maximum Acceptable Entry': max_entry,
            'Schema Version':'vnext-1',
            'Data Trading Date': str(source.date()), 'Data Freshness': 'FRESH' if 0 <= age <= rules.max_age_days else 'STALE',
            'Session Status': 'COMPLETED DAILY BAR', 'Volume Status': 'EXPANSION' if expansion else 'DRY-UP' if f['dry'] else 'UNCONFIRMED',
            'VCP Condition Audit': '; '.join(f'{k}: {"PASS" if v else "FAIL"}' for k,v in checks.items()),
            'Base Depth %': round(float(depth),2), 'Base Lookback Sessions':len(base),
            'Nearby Resistance':resistance, 'Resistance Warning':resistance_warning,
            'Execution Timing': 'NEXT SESSION ONLY', **plan}


def meta_assessment(data, ticker='', rules=Rules()):
    """Research-only failed-breakdown/reclaim, requires separate follow-through."""
    f = features(data)
    if not f:
        return {'ticker': ticker, 'Strategy': 'MET-A', 'Setup Stage': 'INVALIDATED', 'Trade': 'NO', 'Trade Eligibility': 'NO'}
    d = data
    prior = d.iloc[-1]
    # Candidate reversal must precede today's possible follow-through.
    prior_features = features(d.iloc[:-1])
    reversal = d.iloc[-2]
    support = float(d.Low.iloc[-12:-2].min())
    peak = float(d.High.iloc[-22:-2].max())
    decline = (1-float(reversal.Low)/peak)*100
    recent_drop = (1-float(reversal.Close)/float(d.Close.iloc[-7]))*100
    bearish = d.iloc[-12:-2].loc[lambda x: x.Close < x.Open]
    current_reversal = bool(prior.Low < d.Low.iloc[-11:-1].min() and
                            prior.Close > d.Low.iloc[-11:-1].min() and
                            f['lower_wick'] >= .3 and f['clv'] >= rules.close_location)
    if current_reversal:
        reversal, prior_features = prior, f
        support = float(d.Low.iloc[-11:-1].min())
        peak = float(d.High.iloc[-21:-1].max())
        decline = (1-float(reversal.Low)/peak)*100
        recent_drop = (1-float(reversal.Close)/float(d.Close.iloc[-6]))*100
        bearish = d.iloc[-11:-1].loc[lambda x:x.Close < x.Open]
    midpoint = float((bearish.Open.iloc[-1]+bearish.Close.iloc[-1])/2) if len(bearish) else np.nan
    rejection = bool(reversal.Low < support and reversal.Close > support and prior_features
                     and prior_features['lower_wick'] >= .3 and prior_features['clv'] >= rules.close_location)
    contraction = bool(d.Volume.iloc[-4:-1].mean() < d.Volume.iloc[-11:-4].mean()
                       and (d.High-d.Low).iloc[-4:-1].mean() < (d.High-d.Low).iloc[-11:-4].mean())
    weak = decline >= rules.decline_pct or recent_drop >= rules.decline_pct
    reclaim = bool(reversal.Close > midpoint and reversal.Close > reversal.Open)
    trigger = float(reversal.High)*1.001
    stop = min(float(reversal.Low),float(d.Low.iloc[-12:-1].min()))*.998
    chase = (f['close']/trigger-1)*100 > rules.max_extension_pct
    invalid = bool(prior.Close < stop)
    reached = bool(not current_reversal and prior.High >= trigger)
    confirmed = reached and prior.Close >= trigger and f['volume_ratio'] >= rules.breakout_volume and f['clv'] >= rules.close_location
    armed = weak and rejection and reclaim
    stage = ('INVALIDATED' if invalid else 'CONFIRMED' if armed and confirmed
             else 'TRIGGERED' if armed and reached else 'ARMED' if armed
             else 'WATCH')
    return {'ticker': ticker, 'Strategy': 'MET-A', 'Setup Stage': stage,
            'Trigger Status': stage, 'Trade': 'NO', 'Trade Eligibility': 'NO (RESEARCH ONLY)',
            'Research Candidate': bool(weak and (rejection or contraction or reclaim)),
            'Signal Date': str(pd.Timestamp(d.index[-1]).date()),
            'Reversal Date': str(pd.Timestamp(d.index[-1] if current_reversal else d.index[-2]).date()),
            'Prior Decline %': round(decline,2), 'Selling Pressure Contraction': contraction,
            'Failed Breakdown Rejection': rejection, 'Bearish Body Midpoint': midpoint,
            'Closing Midpoint Reclaim': reclaim, 'Setup Low': stop/.998,
            'Entry Trigger': trigger, 'Stop Loss': stop,
            'Maximum Acceptable Entry': trigger*(1+rules.max_extension_pct/100),
            'Gap/Chase Warning': 'Do not chase' if chase else 'Recheck next-session open',
            'Nearby Resistance': float(d.High.iloc[-21:-1].max()),
            'Expected Duration': '5-20 trading sessions',
            'Invalidation Rule': 'Close below saved setup low / gap beyond maximum entry',
            'Next Required Confirmation': 'Follow-through closing above reversal high with expansion; research-only',
            'Trade Reason': 'MET-A '+stage+': research-only; historical/execution validation pending',
            **price_plan(trigger,stop,rules)}
