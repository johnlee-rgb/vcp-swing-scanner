"""Record upstream refs/licenses without installing or running upstream scripts."""
import base64
import json
from pathlib import Path
import requests

REPOS=['alau1158/sepa','polakowo/vectorbt','dgunning/edgartools','austin-starks/sec-ownership-disclosures']


def main():
    folder=Path('third_party');folder.mkdir(exist_ok=True)
    session=requests.Session();out=[]
    for repo in REPOS:
        r=session.get('https://api.github.com/repos/'+repo,timeout=20);r.raise_for_status();meta=r.json()
        commit=session.get('https://api.github.com/repos/'+repo+'/commits/'+meta['default_branch'],timeout=20)
        commit.raise_for_status();sha=commit.json()['sha']
        license=session.get('https://api.github.com/repos/'+repo+'/license',params={'ref':sha},timeout=20)
        license.raise_for_status();lic=license.json()
        text=base64.b64decode(lic['content']).decode()
        filename=repo.replace('/','_')+'_LICENSE.txt'
        (folder/filename).write_text(text)
        out.append({'repository':repo,'commit':sha,'pushed_at':meta['pushed_at'],'archived':meta['archived'],
                    'license':lic['license']['spdx_id'],'license_file':filename,
                    'source_url':'https://github.com/'+repo,'execution':'Upstream code not executed or vendored'})
    (folder/'sources.json').write_text(json.dumps(out,indent=2))
    print(json.dumps(out,indent=2))


if __name__=='__main__':main()
