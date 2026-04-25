from importlib.resources import files
from html.parser import HTMLParser
import json

import httpx
import pytest
from starlette.requests import Request

from reference_agent.app import create_app


class _StructuredFormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_structured_form = False
        self._current_select_name: str | None = None
        self._current_option_value: str | None = None
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        if tag == "form" and attributes.get("action") == "/admin/configuration":
            self._in_structured_form = "admin-form-grid" in attributes.get("class", "")
            return
        if not self._in_structured_form:
            return
        if tag == "input":
            name = attributes.get("name")
            value = attributes.get("value", "")
            if name is not None:
                self.fields[name] = value
            return
        if tag == "select":
            self._current_select_name = attributes.get("name")
            return
        if tag == "option" and self._current_select_name is not None:
            self._current_option_value = attributes.get("value", "")
            if "selected" in attributes:
                self.fields[self._current_select_name] = self._current_option_value

    def handle_endtag(self, tag: str) -> None:
        if tag == "form" and self._in_structured_form:
            self._in_structured_form = False
            self._current_select_name = None
            self._current_option_value = None
            return
        if tag == "select":
            self._current_select_name = None
        if tag == "option":
            self._current_option_value = None


def _extract_structured_form_fields(html_text: str) -> dict[str, str]:
    parser = _StructuredFormParser()
    parser.feed(html_text)
    return parser.fields


@pytest.mark.asyncio
async def test_admin_overview_page_renders_with_navigation(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin")

    assert response.status_code == 200
    assert "Reference Agent Admin" in response.text
    assert "Overview" in response.text
    assert "Runtime Summary" in response.text
    assert "Port" in response.text
    assert "8080" in response.text
    assert str(temp_config / "config.yaml") in response.text
    assert str(temp_config / "TOOLS.md") in response.text
    assert str(temp_config / "profiles") in response.text

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
async def test_admin_system_info_page_renders_routes_and_paths(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/system-info")

    assert response.status_code == 200
    assert "System Info" in response.text
    assert "/v1/chat/completions" in response.text
    assert "/mcp/reference.ask" in response.text
    assert str(temp_config / "config.yaml") in response.text
    assert str(temp_config / "TOOLS.md") in response.text
    assert str(temp_config / "profiles") in response.text


@pytest.mark.asyncio
async def test_admin_service_control_page_renders_status_and_actions(temp_config, monkeypatch):
    from reference_agent.admin import routes

    status_model = {
        "pid": 4321,
        "running": True,
        "healthy": True,
        "pid_file": str(temp_config / "ra.pid"),
        "log_file": str(temp_config / "ra.log"),
        "status_summary": "Running and healthy",
        "available_actions": ["start", "stop", "restart"],
    }

    monkeypatch.setattr(routes, "build_service_control_read_model", lambda: status_model)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/service-control")

    assert response.status_code == 200
    assert "Service Control" in response.text
    assert "Running and healthy" in response.text
    assert "4321" in response.text
    assert "true" in response.text.lower()
    assert 'data-admin-service-control="true"' in response.text
    assert 'data-admin-action="start"' in response.text
    assert 'data-admin-action="stop"' in response.text
    assert 'data-admin-action="restart"' in response.text


@pytest.mark.asyncio
async def test_admin_service_control_status_endpoint_returns_json(temp_config, monkeypatch):
    from reference_agent.admin import routes

    status_model = {
        "pid": 9876,
        "running": True,
        "healthy": True,
        "pid_file": str(temp_config / "ra.pid"),
        "log_file": str(temp_config / "ra.log"),
        "status_summary": "Running and healthy",
        "available_actions": ["start", "stop", "restart"],
    }

    monkeypatch.setattr(routes, "build_service_control_read_model", lambda: status_model)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/service-control/status")

    assert response.status_code == 200
    assert response.json() == status_model


@pytest.mark.asyncio
async def test_admin_service_control_actions_write_audit_records(temp_config, monkeypatch):
    from reference_agent.admin import process_control
    from reference_agent.admin import routes

    calls: list[str] = []

    monkeypatch.setattr(
        routes,
        "build_service_control_read_model",
        lambda: {
            "pid": 2468,
            "running": True,
            "healthy": True,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Running and healthy",
            "available_actions": ["start", "stop", "restart"],
        },
    )

    def fake_run_script(script_path):
        calls.append(script_path.name)
        return {"message": f"{script_path.name} finished", "script": str(script_path)}

    monkeypatch.setattr(process_control, "_run_script", fake_run_script)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_response = await client.post("/admin/service-control/actions/start")
        stop_response = await client.post("/admin/service-control/actions/stop")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert start_response.json()["result"]["message"] == "start.sh finished"
    assert stop_response.json()["result"]["message"] == "stop.sh finished"
    assert calls == ["start.sh", "stop.sh"]

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]

    assert [record["action"] for record in records] == ["start", "stop"]
    assert all(record["scope"] == "admin" for record in records)
    assert all(record["target"] == "service-control" for record in records)


@pytest.mark.asyncio
async def test_admin_service_control_restart_queues_background_task(temp_config, monkeypatch):
    from reference_agent.admin import routes

    scheduled_calls: list[str] = []

    class FakeBackgroundTasks:
        def __init__(self):
            self.tasks: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

        def add_task(self, func, *args, **kwargs):
            self.tasks.append((func, args, kwargs))

    monkeypatch.setattr(
        routes,
        "build_service_control_read_model",
        lambda: {
            "pid": None,
            "running": False,
            "healthy": False,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Stopped",
            "available_actions": ["start", "stop", "restart"],
        },
    )

    def fake_schedule_restart():
        scheduled_calls.append("scheduled")
        return {"message": "restart scheduled", "poll_url": "/admin/service-control/status"}

    monkeypatch.setattr(routes, "schedule_restart", fake_schedule_restart)

    background_tasks = FakeBackgroundTasks()
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/admin/service-control/actions/restart",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )

    response = await routes.service_control_action(
        request, "restart", background_tasks=background_tasks
    )

    assert response.status_code == 202
    body = json.loads(response.body)
    assert body["result"]["message"] == "restart scheduled"
    assert body["poll_url"] == "/admin/service-control/status"
    assert body["detached"] is True
    assert scheduled_calls == []
    assert len(background_tasks.tasks) == 1

    task_func, task_args, task_kwargs = background_tasks.tasks[0]
    assert task_args == ("127.0.0.1",)
    assert task_kwargs == {}

    task_func(*task_args, **task_kwargs)
    assert scheduled_calls == ["scheduled"]

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert records[-1]["action"] == "restart"


@pytest.mark.asyncio
async def test_admin_service_control_restart_response_triggers_background_spawn(temp_config, monkeypatch):
    from reference_agent.admin import process_control
    from reference_agent.admin import routes

    popen_calls: list[tuple[object, dict[str, object]]] = []

    monkeypatch.setattr(
        routes,
        "build_service_control_read_model",
        lambda: {
            "pid": None,
            "running": False,
            "healthy": False,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Stopped",
            "available_actions": ["start", "stop", "restart"],
        },
    )
    monkeypatch.setattr(process_control, "repo_root", lambda: process_control.Path("/repo"))
    monkeypatch.setattr(process_control, "start_script_path", lambda: process_control.Path("/repo/scripts/start.sh"))
    monkeypatch.setattr(process_control, "stop_script_path", lambda: process_control.Path("/repo/scripts/stop.sh"))

    def fake_popen(args, **kwargs):
        popen_calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(process_control.subprocess, "Popen", fake_popen)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/service-control/actions/restart")

    assert response.status_code == 202
    body = response.json()
    assert body["result"]["message"] == "restart scheduled"
    assert body["poll_url"] == "/admin/service-control/status"
    assert body["detached"] is True
    assert len(popen_calls) == 1
    command = popen_calls[0][0][2]
    assert command.index("/repo/scripts/stop.sh") < command.index("/repo/scripts/start.sh")
    assert command.index("/repo/scripts/stop.sh") < command.index("sleep")
    assert command.index("sleep") < command.index("/repo/scripts/start.sh")

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert records[-1]["action"] == "restart"


@pytest.mark.asyncio
async def test_admin_service_control_action_audits_unexpected_failures(temp_config, monkeypatch):
    from reference_agent.admin import process_control
    from reference_agent.admin import routes

    monkeypatch.setattr(
        routes,
        "build_service_control_read_model",
        lambda: {
            "pid": None,
            "running": False,
            "healthy": False,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Stopped",
            "available_actions": ["start", "stop", "restart"],
        },
    )

    def fake_run_script(script_path):
        raise FileNotFoundError(f"missing script: {script_path}")

    monkeypatch.setattr(process_control, "_run_script", fake_run_script)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/service-control/actions/start")

    assert response.status_code == 500
    assert "Service control action failed." in response.text

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert records[-1]["action"] == "start"
    assert records[-1]["outcome"] == "error"
    assert records[-1]["details"]["error_type"] == "FileNotFoundError"
    assert "missing script" in records[-1]["details"]["message"]


@pytest.mark.asyncio
async def test_admin_configuration_page_renders_targets_and_forms(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/configuration")

    assert response.status_code == 200
    assert "Configuration" in response.text
    assert str(temp_config / "config.yaml") in response.text
    assert str(temp_config / "TOOLS.md") in response.text
    assert str(temp_config / "profiles" / "default.yaml") in response.text
    assert 'name="structured_runtime_port"' in response.text
    assert 'name="structured_runtime_timeout_seconds"' in response.text
    assert 'name="structured_runtime_streaming_default"' in response.text
    assert 'name="raw_content"' in response.text


@pytest.mark.asyncio
async def test_admin_configuration_structured_preview_marks_restart_required(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    form_data = {
        "mode": "structured",
        "action": "preview",
        "structured_runtime_port": "9090",
        "structured_runtime_timeout_seconds": "75",
        "structured_runtime_concurrency": "6",
        "structured_runtime_rate_limit_per_base_url": "8",
        "structured_runtime_streaming_default": "true",
        "structured_runtime_stream_status_updates": "false",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/configuration", data=form_data)

    assert response.status_code == 200
    assert "Structured Runtime Preview" in response.text
    assert "restart required" in response.text.lower()
    assert "9090" in response.text
    assert "75" in response.text
    assert "stream_status_updates" in response.text
    assert 'name="structured_runtime_port"' in response.text
    assert 'value="9090"' in response.text
    assert '<option value="false" selected>false</option>' in response.text


@pytest.mark.asyncio
async def test_admin_configuration_structured_preview_then_apply_round_trip_writes_previewed_values(
    temp_config,
):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    config_path = temp_config / "config.yaml"
    form_data = {
        "mode": "structured",
        "structured_runtime_port": "9191",
        "structured_runtime_timeout_seconds": "88",
        "structured_runtime_concurrency": "10",
        "structured_runtime_rate_limit_per_base_url": "11",
        "structured_runtime_streaming_default": "true",
        "structured_runtime_stream_status_updates": "false",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        preview_response = await client.post(
            "/admin/configuration", data={**form_data, "action": "preview"}
        )
        preview_fields = _extract_structured_form_fields(preview_response.text)
        apply_response = await client.post(
            "/admin/configuration",
            data={**preview_fields, "action": "apply"},
        )

    assert preview_response.status_code == 200
    assert 'value="9191"' in preview_response.text
    assert 'value="88"' in preview_response.text
    assert '<option value="false" selected>false</option>' in preview_response.text
    assert preview_fields["mode"] == "structured"
    assert preview_fields["structured_runtime_port"] == "9191"
    assert preview_fields["structured_runtime_timeout_seconds"] == "88"
    assert preview_fields["structured_runtime_stream_status_updates"] == "false"

    assert apply_response.status_code == 200
    assert "Configuration updated" in apply_response.text
    assert 'value="9191"' in apply_response.text
    assert config_path.read_text().count("port: 9191") == 1
    updated_text = config_path.read_text()
    assert "timeout_seconds: 88" in updated_text
    assert "concurrency: 10" in updated_text
    assert "rate_limit_per_base_url: 11" in updated_text
    assert "stream_status_updates: false" in updated_text


@pytest.mark.asyncio
async def test_admin_configuration_invalid_structured_submission_does_not_persist_changes(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    config_path = temp_config / "config.yaml"
    before_text = config_path.read_text()
    form_data = {
        "mode": "structured",
        "action": "apply",
        "structured_runtime_port": "bad-port",
        "structured_runtime_timeout_seconds": "90",
        "structured_runtime_concurrency": "7",
        "structured_runtime_rate_limit_per_base_url": "9",
        "structured_runtime_streaming_default": "true",
        "structured_runtime_stream_status_updates": "true",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/configuration", data=form_data)

    assert response.status_code == 200
    assert "Validation failed" in response.text
    assert "Port must be an integer." in response.text
    assert "Restart required:" in response.text
    assert "<strong>no</strong>" in response.text
    assert 'name="structured_runtime_port"' in response.text
    assert 'value="bad-port"' in response.text
    assert 'type="text"' in response.text
    assert 'inputmode="numeric"' in response.text
    assert 'pattern="[0-9]*"' not in response.text
    assert config_path.read_text() == before_text


@pytest.mark.asyncio
async def test_admin_configuration_raw_preview_rejects_invalid_yaml(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    form_data = {
        "mode": "raw",
        "action": "preview",
        "raw_target": "config",
        "raw_content": "runtime:\n  port: [",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/configuration", data=form_data)

    assert response.status_code == 200
    assert "Validation failed" in response.text
    assert "while parsing" in response.text.lower()
    assert "config.yaml" in response.text


@pytest.mark.asyncio
async def test_admin_configuration_raw_preview_rejects_invalid_tools_markdown(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    form_data = {
        "mode": "raw",
        "action": "preview",
        "raw_target": "tools",
        "raw_content": "# TOOLS\n\nNo fenced yaml block here.\n",
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/configuration", data=form_data)

    assert response.status_code == 200
    assert "Validation failed" in response.text
    assert "yaml" in response.text.lower()
    assert "TOOLS.md" in response.text


@pytest.mark.asyncio
async def test_admin_configuration_apply_writes_only_validated_content(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    config_path = temp_config / "config.yaml"

    invalid_form = {
        "mode": "raw",
        "action": "apply",
        "raw_target": "config",
        "raw_content": "runtime:\n  port: [",
    }
    valid_form = {
        "mode": "structured",
        "action": "apply",
        "structured_runtime_port": "9091",
        "structured_runtime_timeout_seconds": "90",
        "structured_runtime_concurrency": "7",
        "structured_runtime_rate_limit_per_base_url": "9",
        "structured_runtime_streaming_default": "true",
        "structured_runtime_stream_status_updates": "true",
    }

    before_invalid = config_path.read_text()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        invalid_response = await client.post("/admin/configuration", data=invalid_form)

    assert invalid_response.status_code == 200
    assert "Validation failed" in invalid_response.text
    assert config_path.read_text() == before_invalid

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        valid_response = await client.post("/admin/configuration", data=valid_form)

    assert valid_response.status_code == 200
    assert "Configuration updated" in valid_response.text
    updated_text = config_path.read_text()
    assert "port: 9091" in updated_text
    assert "timeout_seconds: 90" in updated_text
    assert "concurrency: 7" in updated_text
    assert "rate_limit_per_base_url: 9" in updated_text
    assert "streaming_default: true" in updated_text
    assert "stream_status_updates: true" in updated_text


@pytest.mark.asyncio
async def test_admin_configuration_raw_apply_writes_validated_tools_content(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    tools_path = temp_config / "TOOLS.md"
    raw_content = """
# TOOLS

```yaml
tools:
  - tool_id: "demo.hybrid"
    type: "hybridrag_pipeline"
    project_id: "demo"
    base_url: "http://example.com"
    auth_ref: "TEST_TOKEN"
    summary: "Updated tool summary."
    capabilities: ["hybrid_rag"]
    constraints:
      timeout_class: "standard"
    evidence_contract: "REQUIRED"
    evidence_locator_policy: "chat_message_ref"
```
"""

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration",
            data={
                "mode": "raw",
                "action": "apply",
                "raw_target": "tools",
                "raw_content": raw_content,
            },
        )

    assert response.status_code == 200
    assert "Configuration updated" in response.text
    assert "Updated tool summary." in tools_path.read_text()


@pytest.mark.asyncio
async def test_admin_configuration_invalid_raw_apply_does_not_write_tools_content(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    tools_path = temp_config / "TOOLS.md"
    before_text = tools_path.read_text()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration",
            data={
                "mode": "raw",
                "action": "apply",
                "raw_target": "tools",
                "raw_content": "# TOOLS\n\nNo fenced yaml block here.\n",
            },
        )

    assert response.status_code == 200
    assert "Validation failed" in response.text
    assert "<strong>no</strong>" in response.text
    assert tools_path.read_text() == before_text


@pytest.mark.asyncio
async def test_admin_configuration_raw_apply_writes_validated_profile_content(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    profile_path = temp_config / "profiles" / "default.yaml"
    raw_content = """
profile_id: "default"
version: "v2"
enabled_tools:
  - "demo.hybrid"
allowed_strategies:
  - "STR_H"
limits:
  max_steps: 4
  evidence_min: 1
  evidence_max: 6
fallback_order:
  - "STR_FALLBACK_V"
answer_policy:
  must_cite: true
  conflict_show: true
  no_evidence_template: "TPL_NO_EVIDENCE_V1"
"""

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration",
            data={
                "mode": "raw",
                "action": "apply",
                "raw_target": "profile:default",
                "raw_content": raw_content,
            },
        )

    assert response.status_code == 200
    assert "Configuration updated" in response.text
    updated_text = profile_path.read_text()
    assert 'version: "v2"' in updated_text
    assert "max_steps: 4" in updated_text


@pytest.mark.asyncio
async def test_admin_configuration_invalid_raw_apply_does_not_write_profile_content(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    profile_path = temp_config / "profiles" / "default.yaml"
    before_text = profile_path.read_text()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration",
            data={
                "mode": "raw",
                "action": "apply",
                "raw_target": "profile:default",
                "raw_content": 'profile_id: "default"\nversion: "v2"\n',
            },
        )

    assert response.status_code == 200
    assert "Validation failed" in response.text
    assert "<strong>no</strong>" in response.text
    assert profile_path.read_text() == before_text


@pytest.mark.asyncio
async def test_admin_static_assets_are_served(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/static/admin.css")

    assert response.status_code == 200
    assert ".admin-shell" in response.text


@pytest.mark.asyncio
async def test_admin_logs_page_renders_trace_and_service_sections(temp_config, monkeypatch):
    from reference_agent.admin import routes

    monkeypatch.setattr(
        routes,
        "build_logs_page_model",
        lambda: {
            "trace_explorer": {
                "trace_count": 1,
                "traces": [
                    {
                        "trace_id": "trace-001",
                        "profile_id": "default",
                        "final_status": "SUCCESS",
                        "step_count": 2,
                        "evidence_count": 1,
                        "href": "/admin/logs/trace/trace-001",
                    }
                ],
            },
            "service_log": {
                "path": str(temp_config / "service.log"),
                "exists": True,
                "lines": ["service booted", "service ready"],
            },
            "admin_actions": {
                "path": str(temp_config / "traces" / "admin_actions.jsonl"),
                "records": [
                    {
                        "ts": "2026-04-25T10:00:00Z",
                        "action": "restart",
                        "target": "service-control",
                        "outcome": "success",
                        "remote_addr": "127.0.0.1",
                    }
                ],
            },
        },
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/logs")

    assert response.status_code == 200
    assert "Logs" in response.text
    assert "Trace Explorer" in response.text
    assert "Service Log" in response.text
    assert "trace-001" in response.text
    assert 'href="/admin/logs/trace/trace-001"' in response.text
    assert "service booted" in response.text
    assert "Admin Actions" in response.text
    assert "restart" in response.text


@pytest.mark.asyncio
async def test_admin_trace_detail_page_renders_readable_timeline(temp_config):
    trace_dir = temp_config / "traces"
    trace_dir.mkdir(exist_ok=True)
    trace_id = "trace-readable"
    (trace_dir / f"{trace_id}.json").write_text(
        json.dumps(
            {
                "trace_id": trace_id,
                "profile_id": "default",
                "profile_version": "v1",
                "router": {
                    "strategy_id": "STR_H",
                    "params": {"intent": "status"},
                    "rationale_codes": ["MATCH_CAPABILITY"],
                    "binding_readiness": {
                        "required_bindings": ["customer_id"],
                        "provided_bindings": ["customer_id"],
                        "missing_bindings": [],
                        "dependency_required": False,
                        "resolution_policy": "strict",
                    },
                    "intent_detected": "status_check",
                    "candidate_strategies": ["STR_H", "STR_FALLBACK_V"],
                    "tool_health_snapshot": {"demo.hybrid": "healthy"},
                    "selected_tools": [{"tool_id": "demo.hybrid", "reason": "best match"}],
                },
                "steps": [
                    {
                        "step_id": "step-1",
                        "tool_id": "demo.hybrid",
                        "input_summary": {"query": "Find customer status"},
                        "output_summary": {"message": "Found active status"},
                        "duration_ms": 120,
                        "error_code": None,
                        "degraded": False,
                    },
                    {
                        "step_id": "step-2",
                        "tool_id": "demo.hybrid",
                        "input_summary": {"query": "Confirm SLA"},
                        "output_summary": {"message": "SLA platinum"},
                        "duration_ms": 85,
                        "error_code": None,
                        "degraded": False,
                    },
                ],
                "final_status": "SUCCESS",
                "evidence": [
                    {
                        "source_type": "hybrid_answer",
                        "tool_id": "demo.hybrid",
                        "source_id": "doc-1",
                        "locator": {"chat_id": "chat-1", "messageId": "msg-1"},
                        "snippet": "Customer is active.",
                        "retrieval_meta": {"score": 0.98},
                        "confidence": 0.98,
                    }
                ],
                "user_visible_notes": ["Returned active customer status."],
                "plan_skeleton": {
                    "answer_blueprint": ["status", "sla"],
                    "required_fields": ["customer_id"],
                    "candidate_tools": ["demo.hybrid"],
                    "constraints": {"max_steps": 2},
                    "stop_conditions": ["enough_evidence"],
                    "notes": "Query customer state first.",
                    "tool_selection_notes": ["Prefer hybrid search."],
                },
                "plan_execution": {
                    "template": "bounded",
                    "steps": [
                        {
                            "step_id": "step-1",
                            "template": "lookup",
                            "tool_id": "demo.hybrid",
                            "input_hint": "status",
                            "bindings_used": ["customer_id"],
                        }
                    ],
                    "notes": "Short plan.",
                },
                "evaluations": [
                    {
                        "step_id": "step-1",
                        "coverage_complete": True,
                        "covered_items": ["status"],
                        "missing_items": [],
                        "bindings_found": ["customer_id"],
                        "bindings_missing": [],
                        "evidence_count": 1,
                        "locator_ok": True,
                        "should_continue": False,
                        "notes": "Enough evidence.",
                        "stop_reasons": ["resolved"],
                    }
                ],
                "queried_tools_by_step": [["demo.hybrid"], ["demo.hybrid"]],
                "step_plans": [
                    {
                        "step_index": 1,
                        "template": "lookup",
                        "tool_ids": ["demo.hybrid"],
                        "questions": ["Find customer status"],
                        "rationale_codes": ["MATCH_CAPABILITY"],
                        "notes": "Direct lookup.",
                    }
                ],
                "synthesis": {
                    "claims": [],
                    "groups": [],
                    "intersection_ids": [],
                    "conflict_ids": [],
                    "mappings": {},
                    "notes": "No conflicts.",
                },
                "final_status_reasons": ["SUFFICIENT_EVIDENCE"],
            }
        ),
        encoding="utf-8",
    )

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(f"/admin/logs/trace/{trace_id}")

    assert response.status_code == 200
    assert "Trace Timeline" in response.text
    assert trace_id in response.text
    assert "step-1" in response.text
    assert "Find customer status" in response.text
    assert "Found active status" in response.text
    assert "Routing Summary" in response.text
    assert "Evidence" in response.text
    assert "Returned active customer status." in response.text


@pytest.mark.asyncio
async def test_admin_docs_page_renders_allowlisted_project_doc(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/docs?doc=README.md")

    assert response.status_code == 200
    assert "Docs" in response.text
    assert "README.md" in response.text
    assert "Reference Agent" in response.text
    assert "Reference Agent is a constrained-strategy RAG broker" in response.text
    assert 'href="/admin/docs?doc=README.md"' in response.text


def test_admin_resources_are_package_contained():
    admin_package = files("reference_agent.admin")

    assert admin_package.joinpath("templates/admin/base.html").is_file()
    assert admin_package.joinpath("templates/admin/configuration.html").is_file()
    assert admin_package.joinpath("templates/admin/docs.html").is_file()
    assert admin_package.joinpath("templates/admin/logs.html").is_file()
    assert admin_package.joinpath("templates/admin/overview.html").is_file()
    assert admin_package.joinpath("templates/admin/service_control.html").is_file()
    assert admin_package.joinpath("templates/admin/system_info.html").is_file()
    assert admin_package.joinpath("static/admin.css").is_file()
    assert admin_package.joinpath("static/admin.js").is_file()
