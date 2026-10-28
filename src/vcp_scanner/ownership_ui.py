"""On-demand bounded ownership research, independent from scanner decisions."""
from pathlib import Path
import json
import os

import pandas as pd
import streamlit as st

from vcp_scanner.ownership import SecClient,DEFAULT_MANAGERS,holding_changes,cluster_buying,concentration,map_cusips,normalize_disclosure_export


def local_rows(kind):
    path=Path(__file__).resolve().parents[2]/'data'/('research_'+kind+'.json')
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return []


def save_rows(kind,rows):
    old=local_rows(kind)
    merged={r['id']:r for r in [*old,*rows]}
    path=Path(__file__).resolve().parents[2]/'data'/('research_'+kind+'.json')
    path.parent.mkdir(exist_ok=True)
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile('w',dir=path.parent,delete=False) as f:
        os.chmod(f.name,0o600)
        json.dump(list(merged.values()),f)
    os.replace(f.name,path)
    return list(merged.values())


def render_ownership(kind,rows=None,readonly=False):
    institution=kind=='holdings'
    st.subheader('機構持倉研究（13F）' if institution else '內幕交易研究（Form 4）')
    st.warning('13F 係延遲季度持倉，唔代表今日買入；唔包括完整淡倉，期權、修訂、公司行動及 CUSIP 映射可能影響比較。' if institution else
               'P 代碼包括公開市場或私人買入。授予股份、行使期權、預先安排交易唔會加入 cluster buying 統計。研究分數未證明有盈利能力。')
    rows=rows if rows is not None else local_rows(kind)
    if not readonly:
        upload=st.file_uploader('匯入有來源及 available_at 嘅小型研究資料（CSV／Parquet，上限 10MB）',type=['csv','parquet'],key='ownership_import_'+kind)
        if upload is not None:
            try:
                if upload.size>10_000_000:raise ValueError('檔案超過 10MB')
                imported=pd.read_parquet(upload) if upload.name.lower().endswith('.parquet') else pd.read_csv(upload)
                if 'availableAt' in imported:
                    imported=pd.DataFrame(normalize_disclosure_export(imported.to_dict('records'),kind))
                required={'id','accession','available_at','manager_cik','period','cusip','shares','class','put_call','share_type','complete','amendment'} if institution else {'id','accession','available_at','ticker','code','transaction_date','owner_ciks','value'}
                if not required.issubset(imported):raise ValueError('缺少所需欄位：'+','.join(sorted(required-set(imported))))
                if len(imported)>20000:raise ValueError('最多匯入 20,000 行')
                st.dataframe(imported.head(10),hide_index=True)
                if st.button('確認匯入研究紀錄',key='ownership_confirm_'+kind):
                    records=imported.where(pd.notna(imported),None).to_dict('records')
                    rows=save_rows(kind,records)
            except (ValueError,TypeError,ImportError):st.warning('研究檔案格式或欄位不合要求，原有紀錄保留。')
        with st.expander('從 SEC 更新（按需、有上限）'):
            if institution:
                raw=st.text_area('機構清單：名稱=CIK，每行一間',value='\n'.join(f'{n}={c}' for n,c in DEFAULT_MANAGERS.items()),key='manager_watchlist')
            else:
                ticker=st.text_input('股票代號',value='DELL',key='sec_issuer_ticker').strip().upper()
            if st.button('更新 SEC 持倉' if institution else '更新 SEC 內幕交易',key='sec_update_'+kind):
                try:
                    client=SecClient();loaded=[]
                    if institution:
                        targets=[line.split('=',1)[1].strip() for line in raw.splitlines() if '=' in line][:5]
                    else:
                        companies=json.loads(client.fetch('https://www.sec.gov/files/company_tickers.json'))
                        targets=[str(r['cik_str']) for r in companies.values() if r['ticker'].upper()==ticker]
                        if not targets:st.warning('SEC ticker 映射未找到，冇產生推測資料。')
                    for cik in targets:
                        filings=client.recent(cik,('13F-HR','13F-HR/A') if institution else ('4','4/A'),limit=4)
                        for filing in filings:loaded.extend(client.load(filing))
                    rows=save_rows(kind,loaded)
                    st.success(f'已讀取 {len(loaded)} 行；按 accession 去除重複。')
                except Exception as exc:
                    st.warning(f'SEC 更新未完成：{type(exc).__name__}。檢查 SEC_USER_AGENT、網絡及官方存取限制；舊紀錄保留。')
        if institution:
            st.caption('Ticker 篩選必須有核實、帶日期嘅 CUSIP 映射；冇映射時保留 CUSIP，唔會估 ticker。')
    if not rows:
        st.info('未有已保存 SEC 資料。設定 SEC_USER_AGENT 或等待雲端研究工作完成。')
        return
    now=pd.Timestamp.now(tz='UTC')
    data=holding_changes(rows,now) if institution else rows
    frame=pd.DataFrame(data)
    query=st.text_input('篩選股票／CUSIP／機構／內幕人士',key='ownership_search_'+kind)
    if query and not frame.empty:
        frame=frame[frame.astype(str).apply(lambda c:c.str.contains(query,case=False,regex=False)).any(axis=1)]
    st.dataframe(frame,hide_index=True,width='stretch')
    st.download_button('下載持倉 CSV' if institution else '下載內幕交易 CSV',frame.to_csv(index=False).encode('utf-8-sig'),file_name=kind+'.csv',key='ownership_export_'+kind)
    if not institution:
        st.write('潛在群組買入（實驗）')
        st.dataframe(pd.DataFrame(cluster_buying(rows,now)),hide_index=True)
    else:
        st.write('所選申報機構集中度（唔係全市場機構持股百分比）')
        st.dataframe(pd.DataFrame(concentration(data)),hide_index=True)
    with st.expander('原始申報版本及資料來源'):
        st.dataframe(pd.DataFrame(rows),hide_index=True)
