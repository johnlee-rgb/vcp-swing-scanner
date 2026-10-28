"""Actual exchange sessions, holidays, early closes and DST."""
import pandas as pd
import exchange_calendars as xcals
from functools import lru_cache


@lru_cache(maxsize=2)
def calendar(market='US'):
    return xcals.get_calendar('XHKG' if market=='HK' else 'XNYS',start='1990-01-01',end='2035-12-31')


def completed_session(asof=None,market='US'):
    now=pd.Timestamp(asof or pd.Timestamp.now(tz='UTC'))
    now=now.tz_localize('UTC') if now.tzinfo is None else now.tz_convert('UTC')
    cal=calendar(market)
    sessions=cal.sessions_in_range((now-pd.Timedelta(days=14)).date(),now.date())
    finished=[s for s in sessions if cal.session_close(s) <= now]
    return finished[-1] if finished else None


def completed_bars(data,asof=None,market='US'):
    if data is None or data.empty: return pd.DataFrame()
    session=completed_session(asof,market)
    if session is None: return data.iloc[:0]
    dates=pd.to_datetime(data.index,errors='coerce')
    if dates.tz is not None: dates=dates.tz_convert('Asia/Hong_Kong' if market=='HK' else 'America/New_York').tz_localize(None)
    return data.loc[(~dates.isna())&(dates.normalize()<=pd.Timestamp(session).tz_localize(None).normalize())]


def sessions_until(start,end,market='US'):
    if pd.Timestamp(end)<pd.Timestamp(start): return -1
    cal=calendar(market)
    return max(0,len(cal.sessions_in_range(pd.Timestamp(start).date(),pd.Timestamp(end).date()))-1)
