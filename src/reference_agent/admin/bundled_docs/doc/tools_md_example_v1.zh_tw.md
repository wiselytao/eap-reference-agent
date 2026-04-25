# Tools.md 範例 (v1, zh-TW)

本文件提供 `tools/TOOLS.md` 的附註範例。

## 結構
1) 保留單一 YAML 區塊，根節點為 `tools:`。
2) 每一個 list item 代表一個工具定義。
3) `summary` 需要簡潔清楚，供工具選擇與相關性判斷使用。

## 欄位說明
1) `tool_id`: 工具唯一識別碼 (string)。
2) `type`: 工具類型 (例如 `hybridrag_pipeline`、`external_mcp`)。
3) `project_id`: 專案或資料集識別。
4) `base_url`: 工具服務的 API endpoint。
5) `auth_ref`: 儲存 API 金鑰/Token 的環境變數名稱。
6) `summary`: 單行摘要，提供工具挑選依據。
7) `capabilities`: 能力標籤。
8) `constraints`: 執行時的限制或提示 (timeout、topK、max_hops 等)。
9) `evidence_contract`: `REQUIRED` 或 `OPTIONAL`。
10) `evidence_locator_policy`: 證據定位方式 (`chat_message_ref`、`external_ref`)。

## Evidence 欄位說明
1) `evidence_contract` 控制工具是否必須回傳證據才能視為成功。
2) `evidence_locator_policy` 決定回應中證據的引用方式。
3) `chat_message_ref` 用於 Hybrid RAG 類型，會回傳 `chat_id`/`message_id`。
4) `external_ref` 用於外部 MCP 工具，通常以文件參照為主。

## 路由前綴
路由前綴由 `capabilities` 推導：
1) `vector_rag` -> `VECTOR:`
2) `graph_rag` -> `GRAPH:`
3) `hybrid_rag` -> `HYBRID:`
4) `hybrid_cot` -> `HYBRIDCOT:`

## Capabilities 參考值
常見值：
1) `vector_rag`: 向量相似度檢索文件片段。
2) `graph_rag`: 圖譜關係查詢與遍歷。
3) `hybrid_rag`: 向量 + 圖譜混合檢索並綜合回答。
4) `hybrid_cot`: 針對推理步驟優化的混合檢索。
5) `answer_gen_builtin`: 工具會直接回傳最終答案，而非只有證據。
6) `external_rag`: 由外部 MCP 來源提供檢索。

## 附註範例
```yaml
tools:
  - tool_id: "demo.vector"              # 工具 ID
    type: "hybridrag_pipeline"          # 內部 Hybrid RAG pipeline
    project_id: "demo"                  # 專案或資料集識別
    base_url: "https://demo.example"    # API base URL
    auth_ref: "HYBRIDRAG_API_TOKEN"     # API token 的環境變數名稱
    summary: "Demo 向量資料集。"       # 工具摘要
    capabilities: ["vector_rag"]        # 能力標籤
    constraints:
      timeout_class: "standard"         # timeout 類型
      topK: 8                           # top-K 檢索筆數
    evidence_contract: "OPTIONAL"       # 證據可選
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.graph"
    type: "hybridrag_pipeline"
    project_id: "demo"
    base_url: "https://demo.example"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    summary: "Demo 圖譜資料集。"
    capabilities: ["graph_rag"]
    constraints:
      timeout_class: "standard"
      max_hops: 2
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.hybrid"
    type: "hybridrag_pipeline"
    project_id: "demo"
    base_url: "https://demo.example"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    summary: "混合資料集，內建 answer generation。"
    capabilities: ["hybrid_rag", "answer_gen_builtin"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "external.partner"
    type: "external_mcp"
    project_id: "partner"
    base_url: "https://partner.example.com"
    auth_ref: "EXTERNAL_MCP_TOKEN"
    summary: "外部 MCP 來源。"
    capabilities: ["external_rag"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "external_ref"
```
