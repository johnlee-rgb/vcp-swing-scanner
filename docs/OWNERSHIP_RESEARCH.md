# 機構持倉及內幕交易研究

## 已實作

- Institutional Ownership／Insider Transactions 獨立頁面；SEC 更新按需、有上限。
- 13F XML 及 Form4 XML 解析，保留 accession、CIK、原始 SEC URL、報告期、
  filing date、available_at、amendment。
- available_at 優先用 acceptance datetime；只有日期時保守採用紐約當晚
  23:59:59，唔用 transaction date／quarter end 當可知時間。
- 13F 只有完整、非 amendment、相鄰季度先作 NEW／INCREASED／REDUCED／
  CLOSED／UNCHANGED 比較。缺前期係 BASELINE，唔當新增。
- 完整性要核對 cover-page tableEntryTotal 同實際表格數。大於有界上限嘅
  filing 不會用部分資料推斷 exit。修訂保留另外版本並顯示警告。
- 選定機構 HHI／同時增加持倉機構數，唔冒充整個市場機構持股比例。
- Form4 P／S／A／M／F／G 等代碼分開；derivative、grant、exercise、已知
  arrangement、amendment 唔會增加 cluster buying 指標。
- 多人共同申報唔當多個獨立買家；accession+leg 去重，聯名交易金額唔重複。
- cluster 及 Insider Conviction Score 屬實驗，唔影響現有 VCP Trade YES。
- CSV／小型 Parquet 有界匯入；sec-ownership-disclosures compatible adapter。

## 真實資料驗證

已從 SEC 取得有界樣本：404 行 13F raw records、13 行 Form4，保存至私人 D1。
機構比較頁顯示可驗證嘅 30 行當期比較。呢個唔代表全市場或所有機構都覆蓋。
部分 Vanguard／BlackRock 請求超過有界解析限制，已保存失敗標記；唔會
下載多 GB 檔案，亦唔會因此顯示佢哋冇持倉。

## 重要限制

13F 係延遲季度披露，唔係今日買賣。唔包括完整淡倉，期權、類別、
voting/discretion、公司行動會令比較複雜。reported_value 保留申報單位，
未驗證申報年代嘅 dollars／thousands 前唔亂轉金額。

Ticker/CUSIP 唔會按公司名估。map_cusips 要明確來源同 valid_from／valid_to，
有歧義就保持 unmapped。全面歷史 CUSIP、delisting、ticker changes 尚未具備；
所以 institutional ticker filters 喺缺映射時唔會當成通過。
P 包括公開市場或私人 purchase，唔可宣稱每筆 P 都係公開市場買入。
10b5-1 關鍵字只作保守 disclosure flag，唔估安排嘅完整法律性質。
內幕買入前跌幅可同價格重播分析，但現有 conviction score 未用跌幅加權。

## 設定

SEC_USER_AGENT 需要真實名稱及聯絡 email；只放私人 secret store。
程式每程序約最多 2 requests/second，低於 SEC 公布嘅 10 requests/second，
最多三次請求嘗試。預設機構清單可編輯；雲端 VCP_SEC_MANAGERS／
VCP_SEC_ISSUERS 接受小型 JSON 清單，唔係保證名人現時持倉。

資料來源：https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
