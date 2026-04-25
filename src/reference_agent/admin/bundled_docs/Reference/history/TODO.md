# TODO.md — Reference Agent（Broker）後續版本待辦清單

> 本檔案列出 **v1 之後**（v1.1 / v1.2 / v2）可考慮的擴充項目，避免污染 v1 PRD。
> 每一項都應以「仍維持 Reference Agent 邊界」為前提：有限策略、無動態 re-plan、無 ReAct、無 web search。

---

## v1 已定稿補充（已納入 v1 PRD 的條款，不屬 TODO）
- Router **不得**基於結果品質進行策略重選/重排（禁止 dynamic re-plan）。
- HYBRID / HYBRIDCOT 必須符合 **Evidence Contract** 才能判定 SUCCESS。
- 若不符合 Evidence Contract：v1 預設 **不自動補救**（不升級 Fork-Join），以固定模板回覆 EMPTY/PARTIAL。

---

## v1.1（可選，偏穩定性與可用性提升）

### A. Quality Gate 的「單次 deterministic rescue」（Profile 控制）
- `enable_quality_rescue=true` 時才啟用
- 固定救援路徑（僅允許 1 次）：例如 `STR_H` 失敗 → `STR_V_FALLBACK`（或 `STR_G`）
- 記錄於 trace：rescue_trigger、rescue_strategy_id、前後 evidence 差異

### B. 更強的 Evidence Contract（工具層）
- TOOLS.md tool entry 增加：
  - `evidence_contract: REQUIRED|OPTIONAL|NONE`
  - `citation_format: ...`（若 Hybrid RAG 能輸出 citations）
- 增加「evidence parser」：從 Hybrid RAG 的 Markdown 回覆抽取 citations（若存在）
- 增加「最小可查證定位」的 UI/輸出模板（chat_id/messageId 連結規則）

### C. Trace 與可觀測性（Ops）
- 指標：
  - strategy 命中率、EMPTY/PARTIAL 比例、rescue 觸發率
  - tool error rate、circuit breaker 次數
  - evidence count 分布、平均延遲（p50/p95）
- 可輸出 daily/weekly 報表（僅統計，不做自主優化）

---

## v1.2（可選，偏擴充與企業治理）

### A. Profiles / RBAC / 多租戶治理
- 多租戶（tenant_id）隔離：profile、trace、audit retention policy
- RBAC 細分：
  - Admin（管理 profiles、發布 TOOLS.md）
  - Auditor（讀 trace/validate）
  - User（ask）
- Profile 版本 pinning 與回滾

### B. TOOLS.md 的安全發佈流程（仍維持「不可熱更新」或「受控熱更新」）
- （選配）受控熱更新：
  - 簽章/校驗（checksum、signature）
  - 版本鎖與回滾
  - 生效窗口（maintenance window）
- CI/CD 產物：TOOLS.md + profiles 打包發佈

### C. MCP Adapter 強化
- MCP tool schema 明確化（input/output JSON schema）
- 針對 host 的錯誤格式兼容（標準錯誤碼、可讀訊息）

---

## v2（功能擴充，但仍守 Reference Agent 邊界）

### A. SQL RAG 納入策略集（仍有限策略）
- 新增策略 instance（示例）：
  - `STR_S`、`STR_SV`（SQL→Vector cite）
  - `STR_S_VG`（SQL→(V||G)）
- SQL 查詢必須 template/allowlist（避免自由 SQL 生成）
- SQL evidence locator：query_hash + dataset/version + row locators（可查證）

### B. 3-step 策略（仍有限、白名單、深度≤3）
- 只新增高價值場景（每新增需走 PRD/版本）
- 示例：
  - `V→G→V`、`G→S→V`、`S→V→G`
- 仍禁止 dynamic chaining

### C. External（E）擴充（謹慎）
- v2 才考慮：`E→V→S`、`E→G→V`（成本與可用性要求更高）
- 必須搭配更強 guardrails（timeout class、fallback、breaker）與可觀測性

---

## 長期（不一定做，先列備忘）

### A. 更完整的 Validation（跨系統）
- Graph：node/edge locator 可點回查（需要平台支援）
- Vector：doc_id + chunk locator + text span（需要平台支援）
- External：若能提供外部來源 locator，則納入 evidence（但仍需本地落地引用策略）

### B. Streaming（可選）
- ask 支援 streaming=true（SSE/Chunk）
- 需確保 trace/evidence 仍可完整落盤（不可因 streaming 破壞稽核）

### C. Policy Pack（合規策略包）
- 不同企業的固定 policy 模板（must_cite、conflict_show、敏感遮罩、保留天數）
- 仍由 profile 選用，不提供任意自訂 workflow

---

## 明確不做（維持 Reference Agent 定位）
- ReAct / 自由規劃 / 自我反思 / 多 Agent 協作
- Web Search / Crawling
- 工作流編輯器 / 任意策略串接
- 工具市場、動態 discovery（除非受控且仍維持有限策略與強審核）
