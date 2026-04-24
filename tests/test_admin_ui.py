from importlib.resources import files
import json

import httpx
import pytest

from reference_agent.app import create_app


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
        "healthy": False,
        "pid_file": str(temp_config / "ra.pid"),
        "log_file": str(temp_config / "ra.log"),
        "status_summary": "Running but unhealthy",
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
    from reference_agent.admin import routes

    calls: list[str] = []

    def fake_status():
        return {
            "pid": 2468,
            "running": True,
            "healthy": True,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Running and healthy",
            "available_actions": ["start", "stop", "restart"],
        }

    def fake_start():
        calls.append("start")
        return {"message": "started"}

    def fake_stop():
        calls.append("stop")
        return {"message": "stopped"}

    monkeypatch.setattr(routes, "build_service_control_read_model", fake_status)
    monkeypatch.setattr(routes, "start_service", fake_start)
    monkeypatch.setattr(routes, "stop_service", fake_stop)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        start_response = await client.post("/admin/service-control/actions/start")
        stop_response = await client.post("/admin/service-control/actions/stop")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert start_response.json()["result"]["message"] == "started"
    assert stop_response.json()["result"]["message"] == "stopped"
    assert calls == ["start", "stop"]

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]

    assert [record["action"] for record in records] == ["start", "stop"]
    assert all(record["scope"] == "admin" for record in records)
    assert all(record["target"] == "service-control" for record in records)


@pytest.mark.asyncio
async def test_admin_service_control_restart_is_detached_and_audited(temp_config, monkeypatch):
    from reference_agent.admin import routes

    calls: list[str] = []

    def fake_status():
        return {
            "pid": None,
            "running": False,
            "healthy": False,
            "pid_file": str(temp_config / "ra.pid"),
            "log_file": str(temp_config / "ra.log"),
            "status_summary": "Stopped",
            "available_actions": ["start", "stop", "restart"],
        }

    def fake_schedule_restart():
        calls.append("restart")
        return {"message": "restart scheduled", "poll_url": "/admin/service-control/status"}

    monkeypatch.setattr(routes, "build_service_control_read_model", fake_status)
    monkeypatch.setattr(routes, "schedule_restart", fake_schedule_restart)

    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/service-control/actions/restart")

    assert response.status_code == 202
    body = response.json()
    assert body["result"]["message"] == "restart scheduled"
    assert body["poll_url"] == "/admin/service-control/status"
    assert body["detached"] is True
    assert calls == ["restart"]

    audit_log = temp_config / "traces" / "admin_actions.jsonl"
    records = [json.loads(line) for line in audit_log.read_text().splitlines()]
    assert records[-1]["action"] == "restart"


@pytest.mark.asyncio
async def test_admin_static_assets_are_served(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/static/admin.css")

    assert response.status_code == 200
    assert ".admin-shell" in response.text


def test_admin_resources_are_package_contained():
    admin_package = files("reference_agent.admin")

    assert admin_package.joinpath("templates/admin/base.html").is_file()
    assert admin_package.joinpath("templates/admin/overview.html").is_file()
    assert admin_package.joinpath("templates/admin/service_control.html").is_file()
    assert admin_package.joinpath("templates/admin/system_info.html").is_file()
    assert admin_package.joinpath("static/admin.css").is_file()
    assert admin_package.joinpath("static/admin.js").is_file()
