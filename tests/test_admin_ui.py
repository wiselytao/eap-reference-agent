from importlib.resources import files

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
    assert admin_package.joinpath("templates/admin/system_info.html").is_file()
    assert admin_package.joinpath("static/admin.css").is_file()
    assert admin_package.joinpath("static/admin.js").is_file()
