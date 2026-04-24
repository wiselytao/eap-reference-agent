import os
from pathlib import Path

import httpx
import pytest

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
    base_url: "http://example.com"
    auth_ref: "TEST_TOKEN"
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
limits:
  max_steps: 3
  evidence_min: 1
  evidence_max: 5
fallback_order:
  - "STR_H"
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
async def test_admin_overview_page_renders_with_navigation(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin")

    assert response.status_code == 200
    assert "Reference Agent Admin" in response.text
    assert "Overview" in response.text

    for path in (
        "/admin/service-control",
        "/admin/configuration",
        "/admin/logs",
        "/admin/system-info",
        "/admin/docs",
    ):
        assert f'href="{path}"' in response.text

    assert 'href="/admin/static/admin.css"' in response.text
    assert 'src="/admin/static/admin.js"' in response.text


@pytest.mark.asyncio
async def test_admin_static_assets_are_served(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/static/admin.css")

    assert response.status_code == 200
    assert ".admin-shell" in response.text
