# Tools.md Example (v1, en)

This document provides an annotated example for `tools/TOOLS.md`.

## Structure
1) Keep a single YAML block under the `tools:` key.
2) Each list item defines one tool entry.
3) Use clear summaries so planning and relevance checks work well.

## Field Reference
1) `tool_id`: Unique ID used in profiles and traces (string).
2) `type`: Tool driver type (for example, `hybridrag_pipeline` or `external_mcp`).
3) `project_id`: Project or dataset identifier for the tool.
4) `adapter`: Adapter name used by the runtime.
5) `base_url`: Service endpoint for the tool.
6) `auth_ref`: Environment variable name that stores the API key or token.
7) `pipeline_prefix`: Routing prefix (ex: `VECTOR:`, `GRAPH:`, `HYBRID:`, `HYBRIDCOT:`).
8) `summary`: One-line description; used for tool selection relevance.
9) `capabilities`: Tags for what the tool can do.
10) `constraints`: Runtime hints (timeout class, topK, max_hops, etc).
11) `evidence_contract`: `REQUIRED` or `OPTIONAL`.
12) `evidence_locator_policy`: Evidence locator style (`chat_message_ref`, `external_ref`).

## Evidence Fields
1) `evidence_contract` controls whether evidence must be returned for the tool to be considered successful.
2) `evidence_locator_policy` sets how evidence is referenced in the response payload.
3) `chat_message_ref` is used for Hybrid RAG pipelines that return `chat_id`/`message_id`.
4) `external_ref` is used for external MCP tools that return document references.

## Capabilities Reference
Common values:
1) `vector_rag`: Vector similarity retrieval over document chunks.
2) `graph_rag`: Graph traversal queries over entity relationships.
3) `hybrid_rag`: Hybrid retrieval (vector + graph) with synthesized answers.
4) `hybrid_cot`: Hybrid retrieval optimized for chain-of-thought style reasoning.
5) `answer_gen_builtin`: Tool returns a final answer, not just raw evidence.
6) `external_rag`: Retrieval powered by an external MCP provider.

## Annotated Example
```yaml
tools:
  - tool_id: "demo.vector"              # Unique tool ID
    type: "hybridrag_pipeline"          # Internal hybrid RAG pipeline
    project_id: "demo"                  # Dataset or project identifier
    adapter: "hybridrag_chat_api_v1"    # Adapter used by Reference Agent
    base_url: "https://demo.example"    # API base URL
    auth_ref: "HYBRIDRAG_API_TOKEN"     # Env var that holds the API token
    pipeline_prefix: "VECTOR:"          # Router prefix
    summary: "Demo vector dataset."     # Short description for selection
    capabilities: ["vector_rag"]        # Capability tags
    constraints:
      timeout_class: "standard"         # Optional timeout profile
      topK: 8                           # Example: top-K retrieval size
    evidence_contract: "OPTIONAL"       # Whether evidence is required
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.graph"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "https://demo.example"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "GRAPH:"
    summary: "Demo graph dataset."
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
    base_url: "https://demo.example"
    auth_ref: "HYBRIDRAG_API_TOKEN"
    pipeline_prefix: "HYBRID:"
    summary: "Hybrid dataset with built-in answer generation."
    capabilities: ["hybrid_rag", "answer_gen_builtin"]
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
    summary: "External partner MCP source."
    capabilities: ["external_rag"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "external_ref"
```
