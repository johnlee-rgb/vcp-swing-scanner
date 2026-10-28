"""Bounded SEC research, accession provenance and publication-time joins."""
from datetime import datetime, timezone
import hashlib
import os
import re
import time
import threading
import json

import pandas as pd
import requests
from defusedxml import ElementTree as ET

_lock = threading.Lock()
_last_request = 0.
TRANSACTIONS = {'P':'Purchase (market/private; verify filing)', 'S':'Sale', 'A':'Grant / award',
                'M':'Option exercise / conversion', 'F':'Tax withholding', 'G':'Gift'}
DEFAULT_MANAGERS = {'Berkshire Hathaway':'1067983','Vanguard':'102909','BlackRock':'1364742'}


def utc(value):
    stamp = pd.to_datetime(value,errors='coerce',utc=True)
    return None if pd.isna(stamp) else stamp.isoformat()


def availability(filing_date, accepted=None):
    if accepted:
        stamp = pd.Timestamp(accepted)
        if stamp.tzinfo is None: stamp = stamp.tz_localize('America/New_York')
        return stamp.tz_convert('UTC').isoformat()
    # A date-only filing becomes known at END of that date in New York, not midnight.
    stamp = pd.Timestamp(filing_date).tz_localize('America/New_York')+pd.Timedelta(hours=23,minutes=59,seconds=59)
    return stamp.tz_convert('UTC').isoformat()


def xml_root(text):
    if len(text.encode()) > 8_000_000: raise ValueError('SEC document exceeds bounded size')
    root = ET.fromstring(text)
    for node in root.iter(): node.tag=node.tag.split('}')[-1]
    return root


def txt(node,path,default=''):
    item=node.find(path)
    return item.text.strip() if item is not None and item.text else default


def num(value):
    try:
        result=float(str(value).replace(',',''))
        return result if pd.notna(result) and abs(result) != float('inf') else None
    except (TypeError,ValueError): return None


def parse_form4(text, accession, filing_date, source_url, accepted=None):
    root=xml_root(text)
    owners=root.findall('reportingOwner')
    names=[txt(o,'reportingOwnerId/rptOwnerName') for o in owners]
    ciks=[txt(o,'reportingOwnerId/rptOwnerCik') for o in owners]
    roles=[txt(o,'reportingOwnerRelationship/officerTitle') or
           ('Director' if txt(o,'reportingOwnerRelationship/isDirector')=='1' else 'Reporting owner') for o in owners]
    footnotes=' '.join(n.text or '' for n in root.findall('.//footnote'))
    arranged=txt(root,'aff10b5One') in ('1','true') or bool(re.search(r'10b5[\s-]*1',footnotes,re.I))
    rows=[]
    for derivative, path in [(False,'.//nonDerivativeTransaction'),(True,'.//derivativeTransaction')]:
        for i,t in enumerate(root.findall(path)):
            code=txt(t,'transactionCoding/transactionCode')
            shares=num(txt(t,'transactionAmounts/transactionShares/value'))
            price=num(txt(t,'transactionAmounts/transactionPricePerShare/value'))
            rows.append({'id':f'{accession}:{"D" if derivative else "N"}:{i}', 'accession':accession,
                'issuer_cik':txt(root,'issuer/issuerCik'),'ticker':txt(root,'issuer/issuerTradingSymbol').upper(),
                'company':txt(root,'issuer/issuerName'), 'insider':' / '.join(names), 'owner_ciks':ciks,
                'role':' / '.join(roles),'transaction_date':txt(t,'transactionDate/value'),
                'filing_date':filing_date,'available_at':availability(filing_date,accepted),
                'code':code,'transaction_type':TRANSACTIONS.get(code,'Other: '+code),
                'shares':shares,'price':price,'value':shares*price if shares is not None and price is not None else None,
                'direct_indirect':txt(t,'ownershipNature/directOrIndirectOwnership/value'),
                'ownership_after':num(txt(t,'postTransactionAmounts/sharesOwnedFollowingTransaction/value')),
                'derivative':derivative,'arrangement_disclosed':arranged,
                'amendment':txt(root,'documentType').endswith('/A'),
                'source_url':source_url,'provenance':'SEC ownership XML'})
    return rows


def parse_13f(text, metadata):
    root=xml_root(text)
    rows=[]
    for i,t in enumerate(root.findall('.//infoTable')):
        cusip=txt(t,'cusip').upper()
        rows.append({**metadata,'id':f'{metadata["accession"]}:{i}', 'cusip':cusip,
                     'issuer':txt(t,'nameOfIssuer'),'class':txt(t,'titleOfClass'),
                     'shares':num(txt(t,'shrsOrPrnAmt/sshPrnamt')),
                     'share_type':txt(t,'shrsOrPrnAmt/sshPrnamtType'),
                     'reported_value':num(txt(t,'value')), 'put_call':txt(t,'putCall'),
                     'discretion':txt(t,'investmentDiscretion'),
                     'identifier_status':'CUSIP ONLY — verified dated ticker map required'})
    return rows


def visible_at(rows, asof):
    cutoff=pd.Timestamp(asof)
    cutoff=cutoff.tz_localize('UTC') if cutoff.tzinfo is None else cutoff.tz_convert('UTC')
    return [r for r in rows if utc(r.get('available_at')) and pd.Timestamp(r['available_at']) <= cutoff]


def holding_changes(rows, asof):
    """Only compare COMPLETE, non-amended quarterly snapshots. No false exits."""
    rows=visible_at(rows,asof)
    if not rows: return []
    df=pd.DataFrame(rows)
    bad=set(df.loc[pd.to_numeric(df.shares,errors='coerce').isna() | (pd.to_numeric(df.shares,errors='coerce')<0),'accession'])
    df.loc[df.accession.isin(bad),'complete']=False
    out=[]
    for manager,part in df.groupby('manager_cik'):
        filings=part[['period','accession','available_at','amendment','complete']].drop_duplicates()
        filings=filings[(filings['complete']==True) & (filings['amendment']==False)]
        periods=sorted(filings.period.unique())
        if not periods: continue
        current=periods[-1]
        previous=periods[-2] if len(periods)>1 else None
        if previous and pd.Period(current,freq='Q').ordinal-pd.Period(previous,freq='Q').ordinal!=1:
            previous=None
        latest=filings[filings.period==current].sort_values('available_at').iloc[-1]
        prior=filings[filings.period==previous].sort_values('available_at').iloc[-1] if previous else None
        new=part[(part.accession==latest.accession) & part.put_call.eq('') & part.share_type.eq('SH')]
        old=part[(part.accession==prior.accession) & part.put_call.eq('') & part.share_type.eq('SH')] if prior is not None else part.iloc[:0]
        # Different security classes / option legs are not aggregated into common equity.
        keys=set(zip(new.cusip,new['class']))|set(zip(old.cusip,old['class']))
        for cusip,cls in keys:
            n=new[(new.cusip==cusip)&(new['class']==cls)]
            p=old[(old.cusip==cusip)&(old['class']==cls)]
            shares=float(n.shares.sum()) if len(n) else 0.
            before=float(p.shares.sum()) if len(p) else 0.
            sample=(n if len(n) else p).iloc[0].to_dict()
            status=('BASELINE / PRIOR UNAVAILABLE' if previous is None else 'NEW' if before==0 and shares>0 else
                    'CLOSED' if shares==0 and before>0 else 'INCREASED' if shares>before else 'REDUCED' if shares<before else 'UNCHANGED')
            amended=bool(((part.period==current)&(part.amendment==True)).any())
            if amended:status='AMENDMENT REVIEW REQUIRED'
            out.append({**sample,'period':current,'available_at':latest.available_at,
                        'accession':latest.accession,'shares':shares,'prior_shares':before if previous else None,
                        'change':shares-before if previous and not amended else None,
                        'change_pct':(shares/before-1)*100 if before>0 and not amended else None,'status':status,
                        'amendments_available':amended,
                        'source_url':f'https://www.sec.gov/Archives/edgar/data/{int(manager)}/{latest.accession.replace("-","")}/'})
    return out


def normalize_disclosure_export(rows,kind,filings=()):
    """Interoperable bounded exports; availability and amendment versions retained."""
    aliases={'accessionNumber':'accession','availableAt':'available_at','resolvedTicker':'ticker',
             'issuerName':'issuer','issuerCik':'issuer_cik','managerCik':'manager_cik',
             'managerName':'manager','reportPeriod':'period','periodOfReport':'period',
             'sharesAmount':'shares','transactionShares':'shares','transactionPricePerShare':'price',
             'transactionCode':'code','transactionDate':'transaction_date','filingDate':'filing_date',
             'reportingOwnerCik':'owner_cik','reportingOwnerName':'insider','titleOfClass':'class',
             'putCall':'put_call','sharesType':'share_type','isAmendment':'amendment'}
    meta={r.get('accession') or r.get('accessionNumber'):r for r in filings}
    out=[]
    for i,original in enumerate(rows):
        r={aliases.get(k,k):v for k,v in original.items()}
        r={**{aliases.get(k,k):v for k,v in meta.get(r.get('accession'),{}).items()},**r}
        if not r.get('accession') or not utc(r.get('available_at')):
            raise ValueError('Accession and actual availableAt are mandatory; no transaction-date substitution')
        r['available_at']=utc(r['available_at'])
        r['id']=r.get('id') or f'{r["accession"]}:import:{i}'
        r['provenance']='Imported sec-ownership-disclosures compatible export; source verification required'
        r['amendment']=str(r.get('amendment','')).lower() in ('true','1')
        if kind=='insiders':
            if not r.get('code') or not r.get('ticker'):raise ValueError('Transaction code and resolvedTicker required')
            r['owner_ciks']=r.get('owner_ciks') or ([str(r['owner_cik'])] if r.get('owner_cik') else [])
            r['shares'],r['price']=num(r.get('shares')),num(r.get('price'))
            r['value']=r['shares']*r['price'] if r['shares'] is not None and r['price'] is not None else None
            # Unknown instrument/arrangement classification cannot inflate conviction.
            r['derivative']=r.get('derivative',True)
            r['arrangement_disclosed']=r.get('arrangement_disclosed',True)
        else:
            if not r.get('manager_cik') or not r.get('period') or not r.get('cusip'):
                raise ValueError('Join institutional_filings for manager CIK and report period')
            r['complete']=r.get('complete',False)  # A subset export never proves a manager exited.
            r.setdefault('class','UNKNOWN');r.setdefault('put_call','UNKNOWN');r.setdefault('share_type','UNKNOWN')
        out.append(r)
    return out


def concentration(changes):
    out=[]
    for cusip in sorted({r['cusip'] for r in changes}):
        rows=[r for r in changes if r['cusip']==cusip and (num(r.get('shares')) or 0)>0]
        total=sum(r['shares'] for r in rows)
        out.append({'cusip':cusip,'reporting_managers':len({r['manager_cik'] for r in rows}),
                    'new_or_increased_managers':len({r['manager_cik'] for r in rows if r['status'] in ('NEW','INCREASED')}),
                    'selected_manager_HHI':sum((r['shares']/total)**2 for r in rows) if total else None,
                    'scope':'Selected manager disclosures only; not total institutional ownership %'})
    return out


def map_cusips(rows,mapping,asof):
    """Only explicit, sourced, valid-time mappings; ambiguous symbols stay unmapped."""
    day=pd.Timestamp(asof).date()
    out=[]
    for r in rows:
        matches=[m for m in mapping if m.get('cusip')==r.get('cusip') and m.get('source_url')
                 and pd.to_datetime(m.get('valid_from'),errors='coerce') is not pd.NaT
                 and pd.Timestamp(m['valid_from']).date()<=day
                 and (not m.get('valid_to') or pd.Timestamp(m['valid_to']).date()>=day)]
        symbols={m['ticker'] for m in matches if m.get('ticker')}
        out.append({**r,'ticker':next(iter(symbols)) if len(symbols)==1 else None,
                    'mapping_status':'SOURCED DATED MAP' if len(symbols)==1 else 'UNMAPPED / AMBIGUOUS'})
    return out


def cluster_buying(rows,asof,days=30):
    end=pd.Timestamp(asof)
    end=end.tz_localize('UTC') if end.tzinfo is None else end.tz_convert('UTC')
    rows=visible_at(rows,end)
    amendments={(r.get('ticker'),str(owner),r.get('transaction_date')) for r in rows if r.get('amendment') for owner in r.get('owner_ciks',[])}
    unique={r['id']:r for r in rows if r.get('code')=='P' and not r.get('derivative')
            and not r.get('amendment') and not r.get('arrangement_disclosed')
            and not any((r.get('ticker'),str(owner),r.get('transaction_date')) in amendments for owner in r.get('owner_ciks',[]))
            and (num(r.get('value')) or 0)>0 and utc(r.get('transaction_date'))
            and end-pd.Timedelta(days=days) <= pd.Timestamp(r['transaction_date'],tz='UTC') <= end}
    out=[]
    for ticker in sorted({r['ticker'] for r in unique.values()}):
        items=[r for r in unique.values() if r['ticker']==ticker]
        # Multi-owner joint reports do not count as independent cluster participants.
        owners={r['owner_ciks'][0] for r in items if len(r.get('owner_ciks',[]))==1}
        amount=sum(r['value'] for r in items)
        out.append({'ticker':ticker,'distinct_insiders':len(owners),'purchase_transactions':len(items),
                    'reported_purchase_value':amount,'cluster':len(owners)>=2,
                    'Insider Conviction Score (experimental)':min(10,2*len(owners)+(2 if amount>=1e6 else 1 if amount>=100000 else 0)),
                    'limitation':'P may include private purchases; not a proven trading edge'})
    return out


class SecClient:
    def __init__(self,user_agent=None,get=None,cache=None):
        self.user_agent=user_agent or os.environ.get('SEC_USER_AGENT','')
        self.get=get or requests.get
        self.cache=cache if cache is not None else {}

    def fetch(self,url):
        global _last_request
        if not re.match(r'^https://(www\.sec\.gov|data\.sec\.gov)/',url):
            raise ValueError('Only official SEC HTTPS endpoints are permitted')
        if '@' not in self.user_agent: raise ValueError('SEC_USER_AGENT requires declared name and contact email')
        key=hashlib.sha256(url.encode()).hexdigest()
        if key in self.cache: return self.cache[key]
        for attempt in range(3):
            with _lock:
                time.sleep(max(0,.55-(time.monotonic()-_last_request)))
                _last_request=time.monotonic()
            response=self.get(url,headers={'User-Agent':self.user_agent,'Accept-Encoding':'gzip, deflate'},timeout=(5,20))
            if response.status_code in (429,503) and attempt<2:
                time.sleep(2**attempt)
                continue
            if not response.ok: raise RuntimeError(f'SEC request failed HTTP {response.status_code}; no data fabricated')
            if len(response.content)>8_000_000: raise ValueError('SEC response exceeds 8MB bounded request')
            self.cache[key]=response.text
            return response.text
        raise RuntimeError('SEC retry limit reached')

    def recent(self,cik,forms,limit=4):
        cik=str(int(cik))
        body=json.loads(self.fetch(f'https://data.sec.gov/submissions/CIK{int(cik):010d}.json'))
        r=body.get('filings',{}).get('recent',{})
        out=[]
        for i,form in enumerate(r.get('form',[])):
            if form not in forms: continue
            item={k:(v[i] if i<len(v) else None) for k,v in r.items() if isinstance(v,list)}
            item.update(cik=cik,manager=body.get('name',''),
                        available_at=availability(item['filingDate'],item.get('acceptanceDateTime')))
            out.append(item)
            if len(out)>=min(limit,8): break
        return out

    def load(self,filing):
        cik=str(int(filing['cik']))
        accession=filing['accessionNumber']
        base=f'https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace("-","")}/'
        # EDGAR lists stylesheet-prefixed primary paths; directory has actual XML.
        index=json.loads(self.fetch(base+'index.json'))
        names=[x['name'] for x in index.get('directory',{}).get('item',[])
               if x['name'].lower().endswith('.xml') and re.fullmatch(r'[\w.-]+',x['name'])]
        out=[];expected=None;period=filing.get('reportDate')
        for name in names[:6]:
            text=self.fetch(base+name)
            root=xml_root(text)
            if root.tag=='ownershipDocument' and filing['form'] in ('4','4/A'):
                return parse_form4(text,accession,filing['filingDate'],base+name,filing.get('acceptanceDateTime'))
            if root.tag.lower()=='informationtable' and filing['form'].startswith('13F'):
                meta={'accession':accession,'manager_cik':cik,'manager':filing['manager'],
                      'period':filing.get('reportDate'),'filing_date':filing['filingDate'],
                      'available_at':filing['available_at'],'amendment':filing['form'].endswith('/A'),
                      'complete':False,'source_url':base+name,'value_units':'AS REPORTED — check filing era',
                      'provenance':'SEC information table XML'}
                out.extend(parse_13f(text,meta))
            elif filing['form'].startswith('13F'):
                try:
                    total=root.find('.//tableEntryTotal')
                    if total is not None:expected=num(total.text)
                    node=root.find('.//periodOfReport')
                    if node is not None and node.text:period=str(pd.Timestamp(node.text).date())
                except (ValueError,ET.ParseError):pass
        for row in out:
            row['period']=period
            row['complete']=bool(period and expected is not None and expected==len(out) and len(names)<=6)
        return out


def edgar_filings(cik,form='4',limit=4):
    """Optional tested SDK adapter; never imported on dashboard startup."""
    import tempfile
    from pathlib import Path
    os.environ.setdefault('EDGAR_LOCAL_DATA_DIR',str(Path(tempfile.gettempdir())/'vcp-edgar-cache'))
    from edgar import Company,set_identity
    identity=os.environ.get('SEC_USER_AGENT','')
    if '@' not in identity: raise ValueError('Configure SEC_USER_AGENT first')
    set_identity(identity)
    filings=Company(str(cik)).get_filings(form=form)
    return filings.head(min(limit,8)).data.to_pandas()
