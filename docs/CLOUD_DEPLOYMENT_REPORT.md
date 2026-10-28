# 雲端部署報告（2026-10-29）

## 已可使用嘅 HTTPS 入口

https://vcp-cloud-research.john-lee-5f2.workers.dev/

呢個係同一個項目嘅私人、唯讀結果入口，唔係另一套 JS scanner。
交易判斷繼續由現有 Python app.py／vNext 模組產生。
Cloudflare Worker 只處理登入、權限、D1 儲存及已保存資料展示。
唔需要 Mac 長開。完整 Streamlit 雲端前台係另一個可選部署，未聲稱已開通。

驗證紀錄：HTTPS 登入頁 200；未登入資料 API 401；登入後頁面及資料 API
200；唯讀 token 寫入 403；冇有效 lease 嘅寫入 409。
已喺瀏覽器實際開啟 HTTPS 登入頁，另以私人 session 驗證登入及讀取。
測試過程冇輸出密碼／token。

## 儲存與隔離

- 專用 D1：vcp-cloud-research，冇使用或修改另一個項目嘅資料表。
- D1 係正式資料來源；GitHub runner／Streamlit 本地 SQLite 只可做臨時快取。
- tracking 分 generation 保存全部訊號、觀察、run、狀態及通知紀錄；manifest
  最後先更新。工作中斷唔會將半份資料庫當成完成。
- 每次寫入都原子檢查單一工作 lease；失去 lease 嘅舊工作無權提交。
- 過大掃描結果分塊；讀取缺塊會明確失敗，唔會當成空掃描。
- 失敗／partial scan 另存，唔覆蓋上一份成功結果。
- 原始訊號 snapshot 唔會因今次更新而被改寫。
- D1 有供應商復原能力，但仍建議另外做加密備份；目前未配置第二供應商備份。

## 私人設定

登入參考保存在本機私人檔 `data/CLOUD_LOGIN.txt`；只包含網址及登入密碼。
`data/cloud_access.json` 另有 API 憑證，權限 0600，全個 data/ 已排除 Git。
呢啲檔案唔可以 upload GitHub、發到普通對話或加進 artifacts。
Worker API token 只放 Cloudflare secret bindings，唔會送入 browser JS。
session cookie 設有 HttpOnly、Secure、SameSite=Strict，並有到期時間。
登入嘗試有十分鐘窗口上限。

## GitHub 工作認證

建議 OIDC，唔需要 GitHub 存長期寫入 key。
後端驗證 GitHub 官方 RS256 簽署、issuer、audience、不可變 repo／owner ID、
ref、workflow_ref、event、hosted runner、期限。只接受本項目 main 或
codex/cloud-vnext 嘅 daily-cloud.yml；唔接受 pull_request 或 fork 身份。
換取嘅工作 token 20 分鐘失效，只供有 lease 嘅工作保存資料。

可選舊式 secret 名稱：VCP_CLOUD_WRITE_TOKEN、SEC_USER_AGENT。
唔會配置或使用 Telegram 發送憑證。

## 排程

daily-cloud.yml：新加坡時間星期二至六 12:20 跑 US EOD。
程式使用 XNYS session close，處理美國 DST、假期及提早收市；資料一樣就跳過。
星期六 13:45 執行 DELL／WDC／GLW／NVDA 有界研究。
每日掃描後可執行 SEC 有界更新；大型表格超過 8MB 會保留失敗原因，唔無限下載。

GitHub 只會由 default branch 啟用 schedule。未經用戶批准唔會 merge main，
所以 feature branch 上面嘅定時排程唔等於已生效。
新分支首次 push 只做三隻股票嘅雲端端到端驗證，唔改正式預設股票池。
雲端工作 40746649316 已成功：OIDC 認證、實際下載、三股掃描及 D1 保存
全部完成；資料內 runner_source 為 GITHUB ACTIONS，github_run_id 同工作一致。
EOG／DELL／GLW 共 3 rows、0 Buy；呢個唔等於完整 500 股驗證。
暫時連線失敗有三次有界重試，重試沿用相同 lease／寫入內容，唔製造重複訊號。
正式每日工作仍用現有 US_PRO_UNIVERSE／DEFAULT_FILTERS。
完整股票池嘅雲端時間／供應商限制仍需實測；工作有 18 分鐘硬上限。
GitHub 排程可能延遲，唔係精確時間服務。

## 可選 Streamlit Community Cloud

cloud_app.py 係專用私人唯讀入口，唔會顯示本機 Telegram／Email 設定頁。
需要登入 Streamlit Community Cloud，建立新 app，選擇 feature branch、
entry point cloud_app.py，並設為 Only specific people can view。
必須係新 app，唔好直接替換現有 production app。
私人唯讀設定已準備喺 `data/streamlit_cloud_secrets.toml`，只放到該平台
secret store，唔放 Git。冇平台帳戶部署授權，所以呢個 Streamlit HTTPS
前台仍未部署；唔會捏造 streamlit.app URL。

## 費用與限制

冇開新付費訂閱、付費主機或 broker 服務。
標準 public-repo GitHub Actions 可免費；額外 storage、較大 runner 唔會啟用。
D1 免費額度目前包括每日 5M rows read、100k rows write、共 5GB storage；
額度可能改變，亦可能同帳戶其他項目共用，唔保證無限免費。
唔用 artifacts 當唯一資料庫，唔將資料庫加入 Git history。
Worker/D1 只存有界結果；長期 retention／備份成本要另行監察。

參考：
- https://developers.cloudflare.com/d1/platform/pricing/
- https://docs.github.com/en/actions/concepts/security/openid-connect
- https://docs.github.com/en/actions/concepts/billing-and-usage
- https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app
