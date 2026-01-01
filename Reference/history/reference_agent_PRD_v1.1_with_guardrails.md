# PRD v1.1：Reference Agent（Broker）— Stability & Usability Enhancements

> **版本**：v1.1（設計草案）  
> **定位**：Reference Agent（受限策略查詢 Broker），維持 v1 邊界  
> **核心目標**：在不擴張為 Agent 平台的前提下，提升穩定性、可用性、可觀測性

---

## 0. 版本範圍與原則（沿用 v1）
- 不做 Web Search / Crawling
- 不做 ReAct / 動態 re-plan / 多 Agent 協作
- 不允許任意 workflow/策略串接
- Strategy 仍為有限白名單、深度 ≤ 3（v1.1 仍以 1–2 step 為主）

---

## 1. Quality Gate：單次 deterministic rescue（Profile 控制）

### 1.1 需求
- `quality_gate.enable_quality_rescue=true` 才啟用
- 救援路徑固定、最多一次（不做多輪）
- 救援僅在 **Evidence Contract 失敗** 或 **必要步驟失敗** 時觸發

### 1.2 救援路徑（示例）
- `STR_H` 失敗 → `STR_FALLBACK_V`（或 `STR_G`）
- `STR_E_FJ_H` 失敗 → `STR_FALLBACK_V`（僅保守回退）

### 1.3 Trace 要求
trace 必須記錄：
- `rescue_trigger`（原因：evidence_contract_failed / step_failed）
- `rescue_strategy_id`
- `evidence_before[]` / `evidence_after[]`（或差異摘要）

### 1.4 Guardrails
- 不允許根據內容品質反覆重跑（只允許一次 rescue）
- rescue 不能形成新策略鏈或動態規劃

---

## 2. Evidence Contract 強化（工具層）

### 2.1 TOOLS.md 擴充欄位
每個 tool entry 支援：
- `evidence_contract: REQUIRED | OPTIONAL | NONE`
- `citation_format: <string>`（若 Hybrid RAG 輸出 citations）

### 2.2 Evidence Parser（Hybrid RAG）
- 解析 Hybrid RAG Markdown 回覆中的 citations（若存在）
- 生成 evidence locator（最小可回查定位）
- 若 citations 不可解析，視為 evidence_contract 未滿足

### 2.3 最小可查證定位（UI/輸出模板）
- 固定 locator 格式：`{chat_id, messageId}` 或外部 locator
- validate/trace 輸出可直接用於回查（host 端可組 URL）

---

## 3. Trace 與可觀測性（Ops）

### 3.1 指標（metrics）
- strategy 命中率、EMPTY/PARTIAL 比例、rescue 觸發率
- tool error rate、circuit breaker 次數
- evidence count 分布、平均延遲（p50/p95）

### 3.2 報表輸出
- 支援 daily/weekly 報表輸出（僅統計）
- 不做自動優化或策略調整

---

## 4. API 與行為變更（v1.1）

### 4.1 ask 行為
- 若啟用 rescue：可在 v1 規則下自動降級一次
- 回應需揭露 rescue 發生（user_visible_notes）

### 4.2 trace/validate
- trace 增加 rescue 與 evidence parser 資訊
- validate 可回傳 citations 解析結果（若有）

---

## 5. MVP 驗收標準（v1.1）
1) 啟用 rescue 時，最多只會觸發一次，且 trace 可回放  
2) evidence_contract=REQUIRED 時，無 citations 或不可解析 → 不得判定 SUCCESS  
3) trace 可輸出 router/rescue/evidence parser 資訊  
4) metrics 與報表輸出存在（僅統計）  

---

## 6. Design Guardrails（沿用 v1）
- Router 不得 dynamic re-plan
- Strategy 不可串接（rescue 不是 chaining）
- Evidence 不得觸發新查詢（rescue 是固定路徑）
- TOOLS.md 不可視為動態 registry

