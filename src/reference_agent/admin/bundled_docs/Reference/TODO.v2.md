# TODO.md（Post-v2 Roadmap）

> 本文件為 **v2 之後**的候選演進項目清單。  
> 原先 v1.1 / v1.2 / 舊 v2 規劃全部作廢，以下以本輪討論重新整理。

---

## A. v3（高價值、可預期、仍不越界）

1. **Query Plan Skeleton 可視化（Read-only）**
   - 顯示 Answer Blueprint、bindings、候選工具、停止條件
   - step-by-step replay（回放）

2. **Plan Diff**
   - 展示 Step #1 與 Step #2 的規劃差異（缺口如何被填補）

3. **更完整的 Cross-RAG 對照輸出格式**
   - 交集/對齊/映射的表格化輸出（保留 evidence locator）

4. **Profiling 管理強化**
   - profiling 結果版本管理、審核流程（human-in-the-loop）
   - profiling question sets 可配置（仍維持有限集合）

---

## B. Experimental（可試，但要嚴格護欄）

1. **Demo Mode：Probe-lite**
   - 明確模式開關（僅 demo）
   - 每次 query 探測工具數量上限（例如 N≤2）
   - 探測結果必落 trace，並可沉澱回 profiling

2. **Answer Blueprint 半結構化 Schema**
   - 仍以「回答覆蓋」為核心，不做任務分解
   - 提升 coverage check 的穩定度與可測試性

3. **Binding Extraction 強化（仍受限）**
   - 強化 CVE/ATT&CK/ID/time_range 抽取與正規化
   - 不引入自動 re-plan loop

---

## C. Deferred（暫緩）

1. **JWT/OIDC 整合**
2. **mTLS**
3. **平台級多租戶治理（RBAC/Quota/Billing）**

---

## D. Explicitly Rejected（明確不做）

- Web Search / Crawling
- 自由 ReAct / 無限自我反思
- 無上限 probing / 無上限 query loop
- 動態 tool discovery / 工具推薦 / marketplace
- Workflow Designer / 任意策略無限延伸
- 多 Agent 協作平台
