# PRD v1.0：Reference Agent（Broker）— Hybrid RAG+（全新產品）

> **版本**：v1.0（定稿）  
> **定位**：Reference Agent（受限策略查詢 Broker），不是通用 Agent 平台  
> **核心目標**：可控、可預期、可稽核的多來源 RAG 查詢編排（僅限有限策略），並可透過 MCP 介面整合到任何 MCP Host。  
> **重要原則**：不做 Web Search / Crawling，不做 ReAct / 自由 planning / 多 Agent 協作，不允許任意 workflow/策略串接。

---

## 0. 決策定稿（v1.0）

1. **TOOLS.md 不支援熱更新**：啟動載入；更新需重啟（A）
2. **Fork-Join 允許 PARTIAL 交付**：必須揭露失敗分支（A）
3. **External（E）v1 僅允許到 Fork-Join**：不做 E→V→S / E→G→V 等 3-step（A）
4. **最小 Evidence 門檻**：SUCCESS 至少 **1–3 條 evidence** 且 **locator 必填**（同意）
5. **v1 策略數量**：有限策略集（本 PRD 定義 **6–8 個**，可由 Profile 白名單控制）（同意）
6. **HYBRIDCOT 預設關閉**：僅能在特定 profile 顯式開啟（A）
7. **涉及 E 的合併答案由 Reference Agent 生成**：以 Reference Agent 自有 LLM 生成最終 answer（A）
8. **Router 不允許 dynamic re-plan**：不得基於結果品質重新選策略/重排步驟（已同意）
9. **HYBRID/HYBRIDCOT Evidence Contract**：不符合可解析 evidence → **不得判定 SUCCESS**；v1 預設不做自動補救（已同意）

---

## 1. 產品定位與邊界

### 1.1 一句話定位
Reference Agent 是「**受限策略（finite strategies）**」的查詢 Broker：允許企業自由宣告可連結的 RAG/工具來源，但只允許執行有限、可測試、可稽核的查詢策略，確保可控與可交付。

### 1.2 產品目標（Goals）
- 以「Profile + TOOLS.md」實現**可配置**的來源與策略白名單
- 在不進入 Agentic 紅海前提下，提供**可控查詢編排**（固定策略、最多三層原則）
- 每次回答必須附帶可驗證的 evidence 與 trace（可稽核、可回放）
- 可選提供 MCP Server Adapter，讓 Reference Agent 以「工具」形式接入 MCP Host
- 成本與延遲可控：V+G 優先用 Hybrid RAG 的 **HYBRID/HYBRIDCOT pipeline** 以節省呼叫次數

### 1.3 不做（Non-goals）
- Web Search / Crawling
- ReAct / 自由 planning / 自我反思 / 多 Agent 協作
- 任意工具 discovery、工具市場、任意 tool call（僅限 TOOLS.md 宣告）
- 任意 workflow 編輯、任意策略串接（No dynamic chaining）
- 知識管理平台功能（ingest/index/schema），此責任歸屬 Hybrid RAG / KM 平台

---

## 2. 兩層產品架構 + MCP Adapter

### 2.1 Layer A：Reference Agent Core Service
- Query Router（受限策略選擇）
- Strategy Executor（固定策略執行）
- Answer Composer（引用、衝突呈現、不足揭露；E 情境必用）
- Audit & Trace（每步稽核、回放）
- Validation（最小可查證定位；未來擴充跨系統證據）

### 2.2 Layer B：Profiles（配置層）
- 啟用哪些工具來源（從 TOOLS.md 中挑）
- 允許哪些策略（strategy allowlist）
- 限制與降級（limits / fallback order / evidence policy）
- HYBRIDCOT 開關與意圖白名單

### 2.3 MCP Server Adapter（薄封裝）
- 將 Core 的功能暴露為 MCP tools：`reference.ask / reference.trace / reference.validate / reference.capabilities`
- Adapter 不包含 Router/Executor 邏輯（只轉送）

---

## 3. 設定檔與宣告檔（v1 必備）

### 3.1 設定檔分層（YAML 或 TOML）
建議三層檔案（可交付、可客製）：

1) **系統設定**：`config.yaml`（或 `config.toml`）  
2) **工具宣告清單**：`TOOLS.md`（含 YAML 區塊）  
3) **Profiles**：`profiles/<profile_id>.yaml`（或 `.toml`）

**優先序**：Profile 覆蓋 config 的偏好/限制；TOOLS.md 提供工具能力與預設限制（硬限制以 Profile 為準）。

### 3.2 config.yaml（最小內容）
- `llm`：供 Router（分類/受限抽取）與 E 合併答案生成使用  
  - provider / base_url / model / api_key_ref / temperature / max_tokens
- `runtime`：streaming_default=false、timeout 預設、並行度
- `audit`：trace 儲存（db/file）、retention
- `security`：secret backend（env/vault）、允許的 profile 列表
- `observability`：metrics/logging 基本設定

---

## 4. TOOLS.md v1（Manifest：以「Pipeline = Tool」為單位）

### 4.1 核心原則
- **每個 tool entry = 一個可直接呼叫的 query pipeline**
- 同一個 Hybrid RAG 專案可宣告多個 pipeline tool：
  - `VECTOR:` / `GRAPH:` / `HYBRID:` / `HYBRIDCOT:`
- TOOLS.md：只讀、啟動載入、不可熱更新；版本變更需寫入 trace

### 4.2 tool entry（最小欄位）
- `tool_id`：唯一（建議 `<project>.<pipeline>`）
- `type`：
  - `hybridrag_pipeline`（Hybrid RAG Chat API 的 pipeline）
  - `external_mcp`（外部 MCP RAG）
- `project_id`：邏輯名稱
- `adapter`：
  - `hybridrag_chat_api_v1`（呼叫 Hybrid RAG Chat API）
  - `mcp`（呼叫 external MCP server）
- `base_url`（hybridrag_pipeline 必填）
- `auth_ref`（secret reference）
- `pipeline_prefix`：`VECTOR:` / `GRAPH:` / `HYBRID:` / `HYBRIDCOT:`
- `capabilities`：例如 `vector_rag/graph_rag/hybrid_rag/hybrid_cot/answer_gen_builtin`
- `constraints`：timeout_class/topK/max_hops/max_rows（預設值）
- `evidence_contract`：`REQUIRED | OPTIONAL | NONE`  
  - v1 對 HYBRID/HYBRIDCOT 建議設為 `REQUIRED`（若 Profile 要 must_cite）
- `evidence_locator_policy`：`chat_message_ref`（最小可回查定位）

---

## 5. Profile v1（策略白名單 + 限制 + 偏好）

### 5.1 最小欄位
- `profile_id`, `version`, `description`
- `enabled_tools[]`（必須存在於 TOOLS.md）
- `allowed_strategies[]`（下節策略 instance IDs）
- `limits`
  - `max_steps=3`（寫死）
  - `evidence_min=1`（可設為 1 或 3）
  - `evidence_max`（例如 12）
  - `token_max`
  - 每工具覆寫：topK/max_hops/max_rows/timeout_class
- `fallback_order`（策略降級順序）
- `answer_policy`
  - `must_cite=true`
  - `conflict_show=true`
  - `no_evidence_template=TPL_NO_EVIDENCE_V1`
- `hybrid_preference`
  - `prefer_hybrid_pipeline=true`
  - `prefer_hybridcot=false`（v1 預設）
  - `hybridcot_allowlist_intents=[]`（若需）
- `quality_gate`
  - `require_evidence_contract=true`
  - `enable_quality_rescue=false`（v1 預設；不做自動補救）

---

## 6. Evidence / Trace（v1 稽核核心輸出）

### 6.1 Evidence（統一格式）
- `source_type`：`vector_chunk | graph_node | graph_edge | sql_row | sql_metric | external_chunk | hybrid_answer`
- `tool_id`
- `source_id`
- `locator`（**必填**；v1 最小為 `{chat_id, messageId}` 或外部 locator）
- `snippet`（可引用片段）
- `retrieval_meta`（filters/topK/hops/rows…）
- `confidence`（可選）

### 6.2 Trace（每次 ask 產生）
- `trace_id`
- `profile_id@version`
- `router`
  - `strategy_id`
  - `rationale_codes[]`
  - `binding_readiness`（required/provided/missing + dependency_required）
- `steps[]`：每步輸入摘要、輸出摘要、耗時、錯誤碼、是否降級
- `final_status`：`SUCCESS | PARTIAL | EMPTY | FAILED`
- `evidence[]`
- `user_visible_notes`（固定模板）

---

## 7. Strategy Catalog v1（有限策略集）

> v1 策略核心：  
> - **只用 V+G 時**：優先使用 Hybrid RAG 的內建 **HYBRID/HYBRIDCOT pipeline**（省成本、內建答案合併）  
> - **涉及 E 時**：必須用 Fork-Join，由 Reference Agent 合併輸出並生成最終 answer

### 7.1 v1 Strategy Instances（建議 6–8 個）
**單步（1-step）**
1. `STR_V`：使用 `<proj>.vector`（prefix=`VECTOR:`）
2. `STR_G`：使用 `<proj>.graph`（prefix=`GRAPH:`）
3. `STR_H`：使用 `<proj>.hybrid`（prefix=`HYBRID:`，內建 answer generation）
4. `STR_HCOT`：使用 `<proj>.hybridcot`（prefix=`HYBRIDCOT:`，預設關閉）

**涉及 E 的 Fork-Join（2-step, parallel）**
5. `STR_E_FJ_H`：`E || HYBRID` → Join/Compose by Reference Agent  
   - External 來源：`type=external_mcp` tool  
   - 本地來源：`STR_H`（省成本、聚合答案）

**Fallback**
6. `STR_FALLBACK_V`：強制回到 `STR_V`

> v1 如需更細分（可選）：`STR_E_FJ_V`、`STR_E_FJ_G`（先不啟用，放 TODO.md）。

---

## 8. Query Router v1（策略選擇規則）

### 8.1 Router 輸入/輸出
**輸入**：user_query、profile、TOOLS.md（工具可用性與能力）、tool health、（可選）對話 context  
**輸出**：`strategy_id + params + rationale_codes[]`（不得輸出任意 steps）

### 8.2 Binding Readiness（依賴判斷）
Router 產出：
- `required_bindings[]`（由意圖映射）
- `provided_bindings[]`（受限抽取）
- `missing_bindings[]`
- `dependency_required`（missing 非空即 true）
- `resolution_policy`：`AUTO_FILL_LIMITED` 或 `ASK_USER`

### 8.3 v1 選擇邏輯（Deterministic）
1) 依 Profile 過濾：只在 `allowed_strategies` 中選  
2) 工具可用性：tool 必須在 `enabled_tools` 且健康  
3) 若判定需要 External（E）：
   - 選 `STR_E_FJ_H`  
4) 否則（僅 V+G）：
   - 若 user_query 明確只要文件 → `STR_V`
   - 若明確只要關聯 → `STR_G`
   - 其他或不確定 → `STR_H`（預設）
   - 若 profile 允許且命中 allowlist intent → `STR_HCOT`

### 8.4 理由碼（rationale_codes）枚舉（v1）
- `R_INTENT_CITATION`
- `R_INTENT_RELATION`
- `R_INTENT_METRIC`（v1 先保留；SQL 版本後續擴充）
- `R_NEED_EXTERNAL`
- `R_PROFILE_RESTRICTED`
- `R_TOOL_UNHEALTHY_FALLBACK`
- `R_USE_HYBRID_PIPELINE`
- `R_USE_HYBRIDCOT_PIPELINE`

---

## 9. Quality Gate & Evidence Contract（v1 定稿條款）

### 9.1 不允許 dynamic re-plan
- Router/Executor **不得**根據回傳品質自動換策略或重排步驟（避免變成 Agent 平台）
- v1 只允許「固定模板回覆」或「降級到 fallback（依 profile）」的單一路徑（但 v1 預設不啟用救援）

### 9.2 Evidence Contract（工具層）
- 若工具 `evidence_contract=REQUIRED`：
  - 工具回覆必須能產生 ≥ `evidence_min` 條 evidence（1–3），且 locator 必填
  - 若不滿足：**不得判定 SUCCESS**，至少為 `EMPTY` 或 `PARTIAL`

### 9.3 v1 不做自動補救
- `enable_quality_rescue=false`（預設）
- 不滿足 evidence → 套用 no_evidence_template 或 partial template（並建議使用者補資訊）

---

## 10. Strategy Executor v1（交易語意與異常處理）

### 10.1 Final Status
- **SUCCESS**：evidence ≥ evidence_min 且 locator 完整、無必要步驟 fail-fast
- **PARTIAL**：Fork-Join 任一分支成功且 evidence 足夠；必須揭露失敗分支
- **EMPTY**：合法執行但 evidence 不足（或查無資料）；套模板
- **FAILED**：必要步驟失敗且無可降級

### 10.2 Fork-Join Join 規則（固定）
- 去重（同 source_id 取最佳 snippet）
- 排序（source_type priority + confidence）
- 衝突呈現（必須並列，不強行消解）
- evidence 上限（evidence_max）

### 10.3 E 合併答案生成（v1）
- 由 Reference Agent 的 LLM 生成最終 answer
- 必須引用兩側 evidence（external + 本地 HYBRID 的 locator）
- 必須揭露：外部分支/本地分支各自的資訊來源與可能差異

---

## 11. Ops Guardrails v1（最小必備）
- Hard limits：max_steps=3、timeout_class、evidence_max/token_max、並行度上限
- Circuit breaker：連續 N 次失敗標記 unhealthy，Router 剔除
- Fallback：依 `fallback_order`（最終 STR_FALLBACK_V）
- 必須引用：must_cite=true 時，無 evidence 不得給肯定答案

---

## 12. API 與 MCP 介面（v1 可交付）

### 12.1 Core Service HTTP API
- `POST /ask`
  - input：`query`, `profile_id`, `context?`, `strategy_id?`
  - output：`answer`, `evidence[]`, `trace_id`, `status`
- `GET /trace/{trace_id}`
  - output：router/steps/evidence/fallback
- `POST /validate`
  - input：`trace_id` 或 `evidence_ref`
  - output：locator 展開、可回查定位（至少 chat_id/messageId）
- `GET /capabilities?profile_id=...`
  - output：允許策略、limits 摘要、enabled_tools 摘要

### 12.2 MCP Adapter tools
- `reference.ask`
- `reference.trace`
- `reference.validate`
- `reference.capabilities`

---

## 13. 混合存取 Hybrid RAG 的 Adapter（hybridrag_chat_api_v1）

### 13.1 呼叫方式（非 streaming，v1 預設）
- create chat → send message（q = `<PREFIX> <question>`）→ 取得 result + messageId
- 產生 evidence locator：`{tool_id, chat_id, messageId}`
- 如需回查：`GET /messages`（由 validate/trace 提供）

### 13.2 HYBRID/HYBRIDCOT 的定位
- 被視為「單一工具」：內建 V+G 合併與答案生成
- Reference Agent 不依賴其內部「V/G 分支細節」做 router re-plan
- 品質以 Evidence Contract 與 evidence_min 判斷（工具不可知）

---

## 14. MVP 驗收標準（v1）
1) 每次 ask 都回 `trace_id`，且 trace 可完整回放（策略、理由碼、步驟）
2) SUCCESS 必須 evidence ≥ 1–3 且 locator 必填；否則只能 EMPTY/PARTIAL + 模板
3) Fork-Join：任一分支失敗仍可 PARTIAL 交付，且 answer + trace 揭露失敗分支
4) TOOLS.md 更新需重啟才生效；啟動載入校驗失敗則拒啟
5) HYBRIDCOT 預設不可用，除非 profile 明確開啟
6) Router 不得因結果品質動態換策略（禁止 dynamic re-plan）

---

## 15. 預設交付物（v1 建議）
- `config.yaml`（或 toml）
- `TOOLS.md`（含示例 project：vector/graph/hybrid/hybridcot）
- `profiles/default.yaml`（內含策略白名單、limits、hybridcot 開關）
- OpenAPI（Core Service）與 MCP tool schema（Adapter）

---

## 16. 後續版本（不寫在本 PRD）
請參考 `TODO.md`（另檔管理）。
