"""Private HTTPS storage; D1 is authoritative, temporary SQLite is a job cache."""
from contextlib import contextmanager
import json
import os
import uuid

import requests

from vcp_scanner.tracking import json_safe


class CloudStore:
    def __init__(self,url=None,token=None,session=None):
        self.url=(url or os.environ.get('VCP_CLOUD_URL','')).rstrip('/')
        self.token=token or os.environ.get('VCP_CLOUD_TOKEN','')
        self.session=session or requests.Session()
        self.lease_id=None
        if not self.url.startswith('https://') or not self.token:
            raise ValueError('Configure VCP_CLOUD_URL and VCP_CLOUD_TOKEN securely')

    def request(self,path,body=None):
        import time
        headers={'Authorization':'Bearer '+self.token}
        failure='RequestException'
        for attempt in range(3):
            try:
                r=self.session.request('POST' if body is not None else 'GET',self.url+path,
                                       json=body,headers=headers,timeout=(5,30))
                if r.status_code in (429,502,503,504) and attempt<2:
                    time.sleep(2**attempt)
                    continue
                if not r.ok: raise RuntimeError(f'Cloud storage HTTP {r.status_code}; state not committed')
                return r.json()
            except requests.RequestException as exc:
                failure=type(exc).__name__
                if attempt<2:time.sleep(2**attempt)
        raise RuntimeError(f'Cloud storage unavailable ({failure}); no successful run claimed') from None

    def get(self,namespace,key='latest'):
        from urllib.parse import urlencode
        return self.request('/api/object?'+urlencode({'namespace':namespace,'key':key})).get('value')

    def put(self,namespace,value,key='latest'):
        value=json_safe(value)
        if len(json.dumps(value).encode())>900000 and isinstance(value,dict) and isinstance(value.get('rows'),list):
            root=uuid.uuid4().hex;chunks=[value['rows'][i:i+20] for i in range(0,len(value['rows']),20)]
            for i,chunk in enumerate(chunks):self.put('chunks',chunk,root+'-'+str(i))
            value={**value,'rows':[],'__chunks':{'root':root,'count':len(chunks)}}
        body={'namespace':namespace,'key':key,'value':value,'lease_id':self.lease_id}
        self.request('/api/object',body)

    @contextmanager
    def lease(self):
        self.lease_id=uuid.uuid4().hex
        acquired=self.request('/api/lease',{'id':self.lease_id}).get('acquired')
        if not acquired: raise RuntimeError('Another cloud job is running')
        try: yield self
        finally:
            self.request('/api/lease',{'id':self.lease_id,'release':True})
            self.lease_id=None

    def heartbeat(self):
        if not self.request('/api/lease',{'id':self.lease_id}).get('acquired'):
            raise RuntimeError('Cloud lease lost')

    def save_tracking(self,store):
        """Generation manifest changes last; a crash cannot publish half a DB."""
        generation=uuid.uuid4().hex
        tables=['signals','observations','runs','notifications','setup_states','setup_events']
        manifest={'generation':generation,'tables':{}}
        with store.connect() as db:
            available={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in tables:
                if table not in available: continue
                rows=[dict(r) for r in db.execute(f'SELECT * FROM {table}')]
                chunks=[rows[i:i+10] for i in range(0,len(rows),10)]
                manifest['tables'][table]=len(chunks)
                for i,chunk in enumerate(chunks):
                    self.put('tracking-'+generation,chunk,f'{table}-{i}')
                self.heartbeat()
        self.put('tracking',manifest,'current')
        return manifest

    def restore_tracking(self,store):
        manifest=self.get('tracking','current')
        if not manifest: return
        allowed={'signals','observations','runs','notifications','setup_states','setup_events'}
        with store.connect() as db:
            for table,count in manifest['tables'].items():
                if table not in allowed: raise ValueError('Unexpected saved tracking table')
                for i in range(count):
                    rows=self.get('tracking-'+manifest['generation'],f'{table}-{i}')
                    if rows is None: raise RuntimeError('Incomplete durable tracking generation')
                    for row in rows:
                        columns=list(row)
                        if not all(c.replace('_','').isalnum() for c in columns): raise ValueError('Invalid stored columns')
                        # Temporary cache is empty; never overwrite original snapshots.
                        db.execute(f'INSERT OR IGNORE INTO {table} ({",".join(columns)}) VALUES ({",".join("?" for _ in columns)})',list(row.values()))


def settings_file():
    from pathlib import Path
    return Path(__file__).resolve().parents[2]/'data'/'cloud_access.json'


def local_cloud_settings():
    path=settings_file()
    if not path.exists() or path.is_symlink() or path.stat().st_mode & 0o077: return {}
    return json.loads(path.read_text())
