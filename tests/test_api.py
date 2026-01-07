import os
from pathlib import Path

import pytest
import httpx

from reference_agent.app import create_app


@pytest.fixture()
def temp_config(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    tools_path = tmp_path / "TOOLS.md"
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    config_path.write_text(
        f"""
llm:
  provider: openai_compatible
  base_url: "http://example.com"
  model: "test-model"
  api_key_ref: "TEST_API_KEY"
  temperature: 0.0
  max_tokens: 32
  extra:
    endpoint: "/v1/chat/completions"
  plan_builder:
    provider: ""
    base_url: ""
    model: ""
    api_key_ref: ""
    temperature: 0.0
    max_tokens: 32
    extra: {{}}
  evaluator:
    provider: ""
    base_url: ""
    model: ""
    api_key_ref: ""
    temperature: 0.0
    max_tokens: 32
    extra: {{}}

audit:
  trace_dir: "{tmp_path / "traces"}"
security:
  allowed_profiles:
    - "default"
"""
    )

    tools_path.write_text(
        """
# TOOLS

```yaml
tools:
  - tool_id: "demo.hybrid"
    type: "hybridrag_pipeline"
    project_id: "demo"
    adapter: "hybridrag_chat_api_v1"
    base_url: "http://example.com"
    auth_ref: "TEST_TOKEN"
    pipeline_prefix: "HYBRID:"
    summary: "Test dataset for hybrid queries."
    capabilities: ["hybrid_rag"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"
```
"""
    )

    (profiles_dir / "default.yaml").write_text(
        """
profile_id: "default"
version: "v1"
enabled_tools:
  - "demo.hybrid"
allowed_strategies:
  - "STR_H"
  - "STR_FALLBACK_V"
limits:
  max_steps: 3
  evidence_min: 1
  evidence_max: 5
fallback_order:
  - "STR_FALLBACK_V"
answer_policy:
  must_cite: true
  conflict_show: true
  no_evidence_template: "TPL_NO_EVIDENCE_V1"
"""
    )

    os.environ["REFERENCE_AGENT_CONFIG"] = str(config_path)
    os.environ["REFERENCE_AGENT_TOOLS"] = str(tools_path)
    os.environ["REFERENCE_AGENT_PROFILES"] = str(profiles_dir)
    os.environ["TEST_API_KEY"] = "dummy"
    os.environ["TEST_TOKEN"] = "dummy"

    return tmp_path


@pytest.mark.asyncio
async def test_ask_endpoint(monkeypatch, temp_config):
    from reference_agent.adapters import hybridrag
    from reference_agent.adapters.llm import LLMClient

    def fake_create_chat(self):
        return "chat123"

    def fake_send_message(self, chat_id, question, streaming=False):
        return "Answer", "msg123"

    def fake_llm(self, model, request):
        return (
            '{'
            '"answer_blueprint": ["Test"], '
            '"required_bindings": [], '
            '"candidate_tools": [], '
            '"constraints": {}, '
            '"stop_conditions": []'
            '}'
        )

    monkeypatch.setattr(hybridrag.HybridRagClient, "create_chat", fake_create_chat)
    monkeypatch.setattr(hybridrag.HybridRagClient, "send_message", fake_send_message)
    monkeypatch.setattr(LLMClient, "generate", fake_llm)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/ask", json={"query": "What is X?", "profile_id": "default"}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "SUCCESS"
        assert payload["evidence"]


@pytest.mark.asyncio
async def test_capabilities(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/capabilities", params={"profile_id": "default"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile_id"] == "default"
