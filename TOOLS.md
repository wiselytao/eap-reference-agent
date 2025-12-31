# TOOLS.md

This file declares tools/pipelines available to the Reference Agent. The YAML block is the source of truth.

```yaml
tools:
  - tool_id: "demo.vector"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "https://demo.geminidata.com"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "VECTOR:"
    capabilities: ["vector_rag"]
    constraints:
      timeout_class: "standard"
      topK: 8
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.graph"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "https://demo.geminidata.com"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "GRAPH:"
    capabilities: ["graph_rag"]
    constraints:
      timeout_class: "standard"
      max_hops: 2
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.hybrid"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "https://demo.geminidata.com"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "HYBRID:"
    capabilities: ["hybrid_rag", "answer_gen_builtin"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.hybridcot"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "https://demo.geminidata.com"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "HYBRIDCOT:"
    capabilities: ["hybrid_cot", "answer_gen_builtin"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "external.partner"
    type: "external_mcp"
    project_id: "partner"
    adapter: "mcp"
    base_url: "https://partner.example.com"
    auth_ref: "EXTERNAL_MCP_TOKEN"
    capabilities: ["external_rag"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "external_ref"
```
