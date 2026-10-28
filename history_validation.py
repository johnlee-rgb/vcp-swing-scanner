"""Explicit read-only provider research. Never sends alerts or executes orders."""
import argparse
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

import app
from vcp_scanner.vnext import meta_assessment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, help='Research data folder, not original signal archive')
    args = parser.parse_args()
    folder = Path(args.output)
    folder.mkdir(parents=True,exist_ok=True)
    symbols = ['DELL','WDC','GLW','NVDA']
    raw = yf.download(symbols,period='2y',auto_adjust=False,actions=True,group_by='ticker',progress=False,threads=False,timeout=10)
    report = {'provenance':'Yahoo/yfinance downloaded research, NOT independently verified or original signals',
              'retrieved_at':pd.Timestamp.now(tz='UTC').isoformat(), 'symbols':{}}
    for symbol in symbols:
        d = raw[symbol].dropna(subset=['Close']) if len(raw) else pd.DataFrame()
        if d.empty:
            report['symbols'][symbol] = {'status':'UNAVAILABLE'}
            continue
        d.to_csv(folder/(symbol+'.csv'))
        found=[]
        for i in range(25,len(d)+1):
            r=meta_assessment(d.iloc[:i],symbol)
            if r.get('Research Candidate') and r.get('Failed Breakdown Rejection'):
                found.append({k:r.get(k) for k in ['Signal Date','Reversal Date','Setup Stage','Prior Decline %','Bearish Body Midpoint','Closing Midpoint Reclaim','Entry Trigger','Stop Loss']})
        report['symbols'][symbol]={'rows':len(d),'first':str(d.index[0]),'last':str(d.index[-1]),
                                  'failed_breakdown_research_observations':found,
                                  'status':'PROVIDER DATA ONLY; independent verification pending'}
    (folder/'provenance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
