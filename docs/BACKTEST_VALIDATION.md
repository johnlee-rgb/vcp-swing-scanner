# 回測驗證與解讀

## 三種資料唔可以混淆

1. 原始研究訊號：各日期用歷史 prefix 重新計算，唔係過去已保存嘅建議。
2. 模擬交易：下一 session 才可觸發，未觸發唔計勝率；缺資料／順序不明分開。
3. 資金組合：獨立 portfolio()，有現金、share size、風險／allocation／sector
   caps、真實持倉 mark-to-market，同時保留虧損及未平倉。

比較頁包括 Legacy／Enhanced VCP、MET-A WATCH／MIDPOINT／CONFIRMED，
可加 regime／insider／institution 篩選。篩選先於模擬交易及 episode 排除，
唔會先用已知未來盈利揀樣本。所有 filing join 用 available_at。

metrics() 顯示樣本數、已觸發／已平倉／ambiguous、平均盈虧、淨 expectancy、
profit factor、5/10/20 session returns、2R/3R、MFE/MAE、Wilson 95% 勝率區間。
少於 30 個平倉樣本會警告。Walk-forward 用時間窗口，跨 test boundary 嘅
訓練交易剔除；冇使用 test 結果調參，亦未完成策略參數嘅校準研究。

獨立資金組合使用預設 100,000 資本、每筆 0.5% 風險、單股 10% allocation、
總 open risk 3%、sector 25%、每邊 10bps。原始止蝕不會為過濾規則而收窄。
每日 OHLC stop-first 係保守界限，唔係已知 intraday 順序。會計入虧損、
opening gaps、未平倉；冇當日 signal close 入場。缺持倉報價或 split 未處理時，
拒絕顯示組合績效；唔用最後價硬充可靠結果。
只有足夠日收益樣本才顯示簡單 Sharpe；唔將 event return 平均當 portfolio。

VectorBT 只計 SPY／QQQ reference holding 比較；核心 stop/ambiguity engine
保留現有可解釋實作。已實際載入 1.2.0，同測試價格驗證結果，唔只做假 import。

## 實際覆蓋

已用私人 D1 保存嘅 DELL 價格完成有界比較，保存 5 個策略 summary 同
23 個研究事件，並保存 portfolio／benchmark／walk-forward 結果。
呢個係有限資料 smoke test，唔係證明 DELL、VCP 或 MET-A 有優勢。
WDC／GLW／NVDA 可由同一個可重跑工作逐隻擴展；唔會捏造缺少價量。

## 仍然有限制

- 現有 universe 有 survivorship bias；未有完整 delisted／point-in-time universe。
- Dividends cash flows 未計；raw Close 同 Adj Close 不混用；已知 split 視窗會阻止
  重播。完整 corporate-action reconciliation 尚未完成。
- 全量歷史 earnings、13F、Form4、CUSIP 映射未覆蓋；冇覆蓋唔等於安全。
- 日期順序及基本交易規則有測試，但未有大樣本獨立 out-of-sample 校準。
- 比較策略係 research events，唔可以將 ungated watch study 當 production BUY。
- Portfolio 係明確假設嘅研究模擬，未連接真實持倉／broker，唔係實際回報。

原有 EOG 測試保留：161.10 未到 165.28，stop149.71、risk9.4204%，必須
Trade NO／ARMED，唔能夠單靠 82.7 分／READY／縮量就變 confirmed BUY。
