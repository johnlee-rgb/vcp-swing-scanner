# 開源整合報告（2026-10-29）

四個 repository 都已確認可讀、未 archived；精確 commit、maintenance
日期及完整 license 保存在 third_party/sources.json／*_LICENSE.txt。
唔會執行上游 email、AI、broker 或全量下載腳本。

| 項目 | 授權／版本 | 處理方式 |
|---|---|---|
| alau1158/sepa | MIT，2026-08-24 更新 | 對照趨勢、縮量、distribution、momentum／exhaustion 概念；獨立實作 enhanced.py，唔整個匯入上游 app |
| polakowo/vectorbt | 1.2.0；Apache-2.0 **加 Commons Clause** | 私人批次 benchmark；唔用佢取代有止蝕順序假設嘅既有模擬引擎；唔可當成無限制商業 MIT 套件 |
| dgunning/edgartools | 5.62.1；MIT，2026-10-25 更新 | Lazy SDK adapter 已測試；輕量 SEC/XML pipeline 不需要 dashboard 啟動時載入整個 SDK |
| austin-starks/sec-ownership-disclosures | MIT，2026-09-27 更新 | 接受 availableAt／accession／CIK／CUSIP 有界 exports；保留 amendment 版本，唔喺 web process 跑 Node 全量 lake |

Legacy VCP Score 直接保留舊 Final Score；Enhanced VCP Score 係獨立、實驗性
診斷，唔修改舊 scanner 分數、排名或單靠高分產生 BUY。
DBTC、momentum acceleration、exhaustion 另外標示，尚未校準。
目前 enhanced 權重係本項目工程預設，唔冒稱完全重現 SEPA 上游所有算法。

VectorBT 1.2.0 需要 pandas >=3.0.3、numpy >=2.4.6；已喺 Python3.12、
pandas3.1.0、numpy2.5.4 測試。Dashboard 不載入 numba／SDK；只有研究批次
或明確測試會載入。requirements-research.txt 鎖住測試版本。
Numba／Edgar cache 放可寫臨時路徑，唔寫入套件目錄或依賴 home 可寫。

安全措施：只用官方 SEC HTTPS endpoint；XML 用 defusedxml，禁止外部 entity；
HTTP 有 timeout／重試／8MB 上限／低速率／快取；唔執行遠端 code 或 pickle。
上游 Node pipeline 及巨大 HuggingFace 全量 archive 暫不執行。
呢個係避免無界儲存／未知 identifier 品質，唔係假裝已整合全世界歷史資料。

依賴同版本已鎖定；未執行完整 SBOM/CVE 供應鏈審核，仍需定期更新。
原始來源及 notices 已保留，唔會將 Commons Clause 說成可自由轉售。
