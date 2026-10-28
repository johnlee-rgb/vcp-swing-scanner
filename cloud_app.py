"""Private read-only Streamlit cloud dashboard. Never exposes local setup tabs."""
import hmac
import os
import pandas as pd
import streamlit as st

from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'src'))
from vcp_scanner.cloud_store import CloudStore
from vcp_scanner.ownership_ui import render_ownership


def main():
    st.set_page_config(page_title='VCP 私人雲端研究',layout='wide')
    def setting(k):
        value=os.environ.get(k)
        if value:return value
        try:return st.secrets.get(k,'')
        except Exception:return ''
    password=setting('VCP_DASHBOARD_PASSWORD')
    if not password or len(password)<20:
        st.error('私人存取尚未設定；資料不會公開。')
        return
    if not st.session_state.get('cloud_authenticated'):
        st.title('VCP 私人雲端研究')
        with st.form('cloud_login',clear_on_submit=True):
            entered=st.text_input('私人存取密碼',type='password')
            go=st.form_submit_button('登入')
        if go:
            if hmac.compare_digest(entered,password):
                st.session_state['cloud_authenticated']=True
                st.rerun()
            else:st.warning('密碼不正確。')
        return
    st.title('VCP 私人雲端研究')
    if st.button('登出'):
        st.session_state.clear();st.rerun()
    try:cloud=CloudStore(setting('VCP_CLOUD_URL'),setting('VCP_CLOUD_READ_TOKEN'))
    except ValueError:
        st.error('雲端讀取設定未完成，唔會使用臨時磁碟冒充永久儲存。');return
    @st.cache_data(ttl=300,show_spinner=False)
    def read(namespace):return cloud.get(namespace) or {}
    if st.button('重新讀取已保存結果'):
        read.clear()
    names=['市場與 VCP','MET-A 研究','機構持倉','內幕交易','回測與勝率','訊號歷史','資料健康']
    tabs=st.tabs(names)
    for tab,kind in zip(tabs,['scans','meta','holdings','insiders','research','signals','failures']):
        with tab:
            try:data=read(kind)
            except RuntimeError:
                st.warning('雲端資料暫時無法讀取。舊紀錄不會被當成新掃描。');continue
            st.caption('更新：'+str(data.get('saved_at','未有資料')))
            st.write(data.get('status','未有已保存資料'))
            rows=data.get('rows',[])
            if kind in ('insiders','holdings'):
                # holdings object already contains compared rows; raw source retained separately.
                if kind=='insiders':render_ownership(kind,rows,readonly=True)
                else:st.dataframe(pd.DataFrame(rows),hide_index=True)
            else:st.dataframe(pd.DataFrame(rows),hide_index=True)
            if rows:st.download_button('下載 CSV',pd.DataFrame(rows).to_csv(index=False).encode('utf-8-sig'),kind+'.csv',key='cloud_export_'+kind)
            with st.expander('來源、限制及完整診斷'):st.json(data)
    st.warning('WATCH 唔係 BUY。MET-A、內幕及機構模型屬研究用途。無經紀交易連線；Telegram 尚未啟用。')


if __name__=='__main__':main()
