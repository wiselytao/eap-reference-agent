# TOOLS.md

This file declares tools/pipelines available to the Reference Agent. The YAML block is the source of truth.

```yaml
tools:
  - tool_id: "demo.vector"
    type: "hybridrag_pipeline"
    project_id: "vulnerability-scannning"
    base_url: "https://demo.geminidata.com"
    auth_ref: "EAP_1_KEY"
    summary: "Security vulnerability scanning reports including SCA, DAST, and SAST. There are critiality inside the report."
    capabilities: ["vector_rag"]
    constraints:
      timeout_class: "standard"
      topK: 8
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.graph"
    type: "hybridrag_pipeline"
    project_id: "mitre-attack-enterprise"
    base_url: "https://demo.geminidata.com"
    auth_ref: "EAP_2_KEY"
    summary: "MITRE ATT&CK ENTERPRISE data for Cyber Security intelligence."
    capabilities: ["graph_rag"]
    constraints:
      timeout_class: "standard"
      max_hops: 2
    evidence_contract: "OPTIONAL"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.hybrid"
    type: "hybridrag_pipeline"
    project_id: "vulnerability-scanning"
    base_url: "https://demo.geminidata.com"
    auth_ref: "EAP_1_KEY"
    summary: "Security vulnerability scanning reports including SCA, DAST, and SAST. Application List is included."
    capabilities: ["hybrid_rag", "answer_gen_builtin"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"

  - tool_id: "demo.hybridcot"
    type: "hybridrag_pipeline"
    project_id: "vulnerability-scanning_2"
    base_url: "https://demo.geminidata.com"
    auth_ref: "EAP_3_KEY"
    summary: "Security vulnerability scanning reports including SCA, DAST, and SAST. CVE vulnerability database included."
    capabilities: ["hybrid_cot", "answer_gen_builtin"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
```
