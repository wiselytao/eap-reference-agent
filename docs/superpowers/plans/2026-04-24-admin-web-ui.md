# Admin Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a built-in `/admin` web interface for Reference Agent that can manage the local daemon, edit configuration, inspect traces and logs, show system details, and render project documentation.

**Architecture:** Keep the admin interface inside the existing FastAPI app for v1, but isolate it behind a dedicated `reference_agent.admin` package. Use server-rendered Jinja templates, minimal vanilla JavaScript, and small service modules for process control, config editing, trace/log reading, docs rendering, and admin action auditing.

**Tech Stack:** FastAPI, Starlette templates/static files, Jinja2, Python Markdown, PyYAML, httpx, pytest, pytest-asyncio

---

### Task 1: Admin Foundation and Routing

**Files:**
- Create: `src/reference_agent/admin/__init__.py`
- Create: `src/reference_agent/admin/routes.py`
- Create: `templates/admin/base.html`
- Create: `templates/admin/overview.html`
- Create: `static/admin.css`
- Create: `static/admin.js`
- Modify: `src/reference_agent/app.py`
- Modify: `pyproject.toml`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Write the failing admin routing tests**

```python
import os
from pathlib import Path

import httpx
import pytest

from reference_agent.app import create_app


@pytest.mark.asyncio
async def test_admin_overview_page_renders(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin")
    assert response.status_code == 200
    assert "Reference Agent Admin" in response.text
    assert "Overview" in response.text


@pytest.mark.asyncio
async def test_admin_navigation_links_present(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin")
    body = response.text
    assert "/admin/service-control" in body
    assert "/admin/configuration" in body
    assert "/admin/logs" in body
    assert "/admin/system-info" in body
    assert "/admin/docs" in body
```

- [ ] **Step 2: Run the new test and verify it fails**

Run: `pytest tests/test_admin_ui.py::test_admin_overview_page_renders -v`

Expected: FAIL with `404 != 200` because `/admin` does not exist yet.

- [ ] **Step 3: Add the admin router, templates, and static assets**

```toml
[project]
dependencies = [
  "fastapi>=0.110",
  "uvicorn>=0.23",
  "pydantic>=2.6",
  "httpx>=0.25",
  "PyYAML>=6.0",
  "python-dotenv>=1.0",
  "Jinja2>=3.1",
  "Markdown>=3.6",
]
```

```python
# src/reference_agent/admin/routes.py
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


def create_admin_router(service) -> APIRouter:
    router = APIRouter(prefix="/admin", include_in_schema=False)
    templates = Jinja2Templates(directory=str(Path("templates")))

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    def admin_overview(request: Request):
        return templates.TemplateResponse(
            request,
            "admin/overview.html",
            {
                "page_title": "Overview",
                "nav_items": [
                    ("Overview", "/admin"),
                    ("Service Control", "/admin/service-control"),
                    ("Configuration", "/admin/configuration"),
                    ("Logs & Audit", "/admin/logs"),
                    ("System Info", "/admin/system-info"),
                    ("Docs", "/admin/docs"),
                ],
                "summary_cards": [
                    ("Status", "Unknown"),
                    ("Version", "Loading"),
                    ("Config Path", str(Path("config.yaml").resolve())),
                ],
            },
        )

    return router
```

```python
# src/reference_agent/app.py
from fastapi.staticfiles import StaticFiles

from reference_agent.admin.routes import create_admin_router


def create_app() -> FastAPI:
    app = FastAPI(title="Reference Agent", version="1.0")
    service = build_service()
    app.mount("/admin/static", StaticFiles(directory="static"), name="admin-static")
    app.include_router(create_admin_router(service))
```

```html
<!-- templates/admin/base.html -->
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>{{ page_title }} | Reference Agent Admin</title>
    <link rel="stylesheet" href="/admin/static/admin.css">
    <script defer src="/admin/static/admin.js"></script>
  </head>
  <body>
    <aside class="sidebar">
      <h1>Reference Agent Admin</h1>
      <nav>
        {% for label, href in nav_items %}
        <a href="{{ href }}">{{ label }}</a>
        {% endfor %}
      </nav>
    </aside>
    <main class="content">
      {% block content %}{% endblock %}
    </main>
  </body>
</html>
```

```html
<!-- templates/admin/overview.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>Overview</h2>
<section class="card-grid">
  {% for label, value in summary_cards %}
  <article class="card">
    <h3>{{ label }}</h3>
    <p>{{ value }}</p>
  </article>
  {% endfor %}
</section>
{% endblock %}
```

```css
/* static/admin.css */
body { margin: 0; font-family: Arial, sans-serif; background: #f6f8fb; color: #132238; display: flex; }
.sidebar { width: 240px; min-height: 100vh; background: #132238; color: #fff; padding: 24px; box-sizing: border-box; }
.sidebar nav a { display: block; color: #cdd8e5; text-decoration: none; padding: 10px 0; }
.content { flex: 1; padding: 32px; }
.card-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.card { background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 8px 24px rgba(19, 34, 56, 0.08); }
```

```javascript
// static/admin.js
document.addEventListener("DOMContentLoaded", () => {
  document.body.dataset.adminReady = "true";
});
```

- [ ] **Step 4: Run the admin routing tests and verify they pass**

Run: `pytest tests/test_admin_ui.py::test_admin_overview_page_renders tests/test_admin_ui.py::test_admin_navigation_links_present -v`

Expected: both tests PASS.

- [ ] **Step 5: Commit the foundation changes**

```bash
git add pyproject.toml src/reference_agent/app.py src/reference_agent/admin/__init__.py src/reference_agent/admin/routes.py templates/admin/base.html templates/admin/overview.html static/admin.css static/admin.js tests/test_admin_ui.py
git commit -m "feat: add admin routing foundation"
```

### Task 2: Overview and System Info Read Models

**Files:**
- Create: `src/reference_agent/admin/models.py`
- Create: `src/reference_agent/admin/system_info.py`
- Create: `templates/admin/system_info.html`
- Modify: `src/reference_agent/admin/routes.py`
- Modify: `templates/admin/overview.html`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Add failing tests for overview summary and system info**

```python
@pytest.mark.asyncio
async def test_admin_overview_shows_runtime_summary(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin")
    assert "8080" in response.text or "8081" in response.text
    assert "TOOLS.md" in response.text
    assert "profiles" in response.text


@pytest.mark.asyncio
async def test_system_info_page_shows_routes_and_paths(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/system-info")
    assert response.status_code == 200
    assert "/v1/chat/completions" in response.text
    assert "/mcp/reference.ask" in response.text
    assert "config.yaml" in response.text
```

- [ ] **Step 2: Run the summary test and verify it fails**

Run: `pytest tests/test_admin_ui.py::test_system_info_page_shows_routes_and_paths -v`

Expected: FAIL with `404 != 200` for `/admin/system-info`.

- [ ] **Step 3: Implement admin view models and system info pages**

```python
# src/reference_agent/admin/models.py
from pydantic import BaseModel


class SummaryCard(BaseModel):
    label: str
    value: str
    tone: str = "default"


class SystemInfoView(BaseModel):
    version: str
    http_mode: str
    base_url: str
    openai_route: str
    mcp_routes: list[str]
    config_path: str
    tools_path: str
    profiles_path: str
    trace_dir: str
    profiling_dir: str
    allowed_profiles: list[str]
    enabled_tool_count: int
```

```python
# src/reference_agent/admin/system_info.py
from pathlib import Path

from reference_agent.admin.models import SummaryCard, SystemInfoView


def build_system_info(service) -> SystemInfoView:
    scheme = "https" if service.config.tls.enabled else "http"
    base_url = f"{scheme}://localhost:{service.config.runtime.port}"
    return SystemInfoView(
        version="v4.2",
        http_mode="HTTPS" if service.config.tls.enabled else "HTTP",
        base_url=base_url,
        openai_route=f"{base_url}/v1/chat/completions",
        mcp_routes=[
            f"{base_url}/mcp/reference.ask",
            f"{base_url}/mcp/reference.trace",
            f"{base_url}/mcp/reference.validate",
            f"{base_url}/mcp/reference.capabilities",
        ],
        config_path=str(Path.cwd() / "config.yaml"),
        tools_path=str(Path.cwd() / "tools" / "TOOLS.md"),
        profiles_path=str(Path.cwd() / "profiles"),
        trace_dir=service.config.audit.trace_dir,
        profiling_dir=service.config.profiling_dir,
        allowed_profiles=service.config.security.allowed_profiles,
        enabled_tool_count=len(service.tools),
    )


def build_overview_cards(service) -> list[SummaryCard]:
    system_info = build_system_info(service)
    return [
        SummaryCard(label="Status", value="Unknown"),
        SummaryCard(label="Version", value=system_info.version),
        SummaryCard(label="Base URL", value=system_info.base_url),
        SummaryCard(label="Config", value=system_info.config_path),
        SummaryCard(label="Tools", value=system_info.tools_path),
        SummaryCard(label="Profiles", value=system_info.profiles_path),
    ]
```

```python
# src/reference_agent/admin/routes.py
from reference_agent.admin.system_info import build_overview_cards, build_system_info

    @router.get("/system-info", response_class=HTMLResponse)
    def system_info(request: Request):
        info = build_system_info(service)
        return templates.TemplateResponse(
            request,
            "admin/system_info.html",
            {"page_title": "System Info", "nav_items": nav_items, "info": info},
        )

    @router.get("", response_class=HTMLResponse)
    @router.get("/", response_class=HTMLResponse)
    def admin_overview(request: Request):
        cards = [(card.label, card.value) for card in build_overview_cards(service)]
        return templates.TemplateResponse(
            request,
            "admin/overview.html",
            {"page_title": "Overview", "nav_items": nav_items, "summary_cards": cards},
        )
```

```html
<!-- templates/admin/system_info.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>System Info</h2>
<dl class="detail-grid">
  <dt>Mode</dt><dd>{{ info.http_mode }}</dd>
  <dt>Base URL</dt><dd>{{ info.base_url }}</dd>
  <dt>OpenAI Route</dt><dd>{{ info.openai_route }}</dd>
  <dt>Config Path</dt><dd>{{ info.config_path }}</dd>
  <dt>Tools Path</dt><dd>{{ info.tools_path }}</dd>
  <dt>Profiles Path</dt><dd>{{ info.profiles_path }}</dd>
  <dt>Trace Dir</dt><dd>{{ info.trace_dir }}</dd>
  <dt>Profiling Dir</dt><dd>{{ info.profiling_dir }}</dd>
</dl>
<ul>
  {% for route in info.mcp_routes %}
  <li>{{ route }}</li>
  {% endfor %}
</ul>
{% endblock %}
```

- [ ] **Step 4: Run the overview and system info tests**

Run: `pytest tests/test_admin_ui.py::test_admin_overview_shows_runtime_summary tests/test_admin_ui.py::test_system_info_page_shows_routes_and_paths -v`

Expected: both tests PASS.

- [ ] **Step 5: Commit the overview/system info work**

```bash
git add src/reference_agent/admin/models.py src/reference_agent/admin/system_info.py src/reference_agent/admin/routes.py templates/admin/overview.html templates/admin/system_info.html tests/test_admin_ui.py
git commit -m "feat: add admin overview and system info pages"
```

### Task 3: Service Control and Admin Action Audit

**Files:**
- Create: `src/reference_agent/admin/audit.py`
- Create: `src/reference_agent/admin/process_control.py`
- Create: `templates/admin/service_control.html`
- Modify: `src/reference_agent/admin/routes.py`
- Modify: `static/admin.js`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Add failing service-control tests**

```python
@pytest.mark.asyncio
async def test_service_control_page_shows_status(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/service-control")
    assert response.status_code == 200
    assert "Refresh Status" in response.text


@pytest.mark.asyncio
async def test_service_control_start_action_records_audit(monkeypatch, temp_config, tmp_path):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    calls = []

    def fake_run_action(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "ok", "message": "started", "stdout": "started", "stderr": ""}

    monkeypatch.setattr("reference_agent.admin.process_control.run_control_action", fake_run_action)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/admin/service-control/start")
    assert response.status_code == 303
    assert calls
```

- [ ] **Step 2: Run the failing service-control page test**

Run: `pytest tests/test_admin_ui.py::test_service_control_page_shows_status -v`

Expected: FAIL with `404 != 200`.

- [ ] **Step 3: Implement process control, action auditing, and the service-control page**

```python
# src/reference_agent/admin/audit.py
import json
from datetime import datetime, timezone
from pathlib import Path


class AdminAuditStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, action: str, target: str, status: str, message: str, actor: str) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "target": target,
            "status": status,
            "message": message,
            "actor": actor,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
```

```python
# src/reference_agent/admin/process_control.py
import os
import signal
import subprocess
from pathlib import Path

import httpx


def read_pid(pidfile: Path) -> int | None:
    if not pidfile.exists():
        return None
    try:
        return int(pidfile.read_text().strip())
    except ValueError:
        return None


def is_process_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def probe_health(port: int, token: str | None) -> bool:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = httpx.get(
        f"http://127.0.0.1:{port}/capabilities",
        params={"profile_id": "default"},
        headers=headers,
        timeout=2.0,
    )
    return response.status_code == 200


def run_control_action(script_path: Path) -> dict[str, str]:
    result = subprocess.run(
        ["/bin/bash", str(script_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "status": "ok" if result.returncode == 0 else "error",
        "message": result.stdout.strip() or result.stderr.strip() or "completed",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_restart_detached(stop_script: Path, start_script: Path) -> None:
    subprocess.Popen(
        ["/bin/bash", "-lc", f"'{stop_script}' && '{start_script}'"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
```

```python
# src/reference_agent/admin/routes.py
from fastapi.responses import RedirectResponse

from reference_agent.admin.audit import AdminAuditStore
from reference_agent.admin.process_control import (
    is_process_alive,
    probe_health,
    read_pid,
    run_control_action,
    run_restart_detached,
)

    audit_store = AdminAuditStore(Path("data/admin_actions.jsonl"))
    pidfile = Path("data/ra.pid")
    start_script = Path("scripts/start.sh")
    stop_script = Path("scripts/stop.sh")

    @router.get("/service-control", response_class=HTMLResponse)
    def service_control(request: Request):
        pid = read_pid(pidfile)
        is_running = is_process_alive(pid)
        health_ok = probe_health(service.config.runtime.port, service.bearer_token_active) if is_running else False
        status = {"pid": pid or "-", "running": is_running, "healthy": health_ok}
        return templates.TemplateResponse(
            request,
            "admin/service_control.html",
            {"page_title": "Service Control", "nav_items": nav_items, "status": status},
        )

    @router.post("/service-control/start")
    def service_control_start(request: Request):
        result = run_control_action(start_script)
        audit_store.append("start", "reference-agent", result["status"], result["message"], request.client.host if request.client else "unknown")
        return RedirectResponse("/admin/service-control", status_code=303)

    @router.post("/service-control/stop")
    def service_control_stop(request: Request):
        result = run_control_action(stop_script)
        audit_store.append("stop", "reference-agent", result["status"], result["message"], request.client.host if request.client else "unknown")
        return RedirectResponse("/admin/service-control", status_code=303)

    @router.post("/service-control/restart")
    def service_control_restart(request: Request):
        run_restart_detached(stop_script, start_script)
        audit_store.append("restart", "reference-agent", "pending", "restart requested", request.client.host if request.client else "unknown")
        return RedirectResponse("/admin/service-control?reconnecting=1", status_code=303)
```

```html
<!-- templates/admin/service_control.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>Service Control</h2>
<section class="card-grid">
  <article class="card"><h3>PID</h3><p>{{ status.pid }}</p></article>
  <article class="card"><h3>Running</h3><p>{{ status.running }}</p></article>
  <article class="card"><h3>Healthy</h3><p>{{ status.healthy }}</p></article>
</section>
<form method="post" action="/admin/service-control/start"><button>Start</button></form>
<form method="post" action="/admin/service-control/stop"><button>Stop</button></form>
<form method="post" action="/admin/service-control/restart"><button>Restart</button></form>
<a href="/admin/service-control">Refresh Status</a>
{% endblock %}
```

```javascript
// static/admin.js
document.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  if (params.get("reconnecting") === "1") {
    const poll = window.setInterval(async () => {
      try {
        const response = await fetch("/admin/service-control", { headers: { "X-Requested-With": "fetch" } });
        if (response.ok) {
          window.clearInterval(poll);
          window.location.href = "/admin/service-control";
        }
      } catch (error) {
        console.debug("service still restarting", error);
      }
    }, 1500);
  }
});
```

- [ ] **Step 4: Run the service-control tests**

Run: `pytest tests/test_admin_ui.py::test_service_control_page_shows_status tests/test_admin_ui.py::test_service_control_start_action_records_audit -v`

Expected: both tests PASS.

- [ ] **Step 5: Commit the service-control and audit work**

```bash
git add src/reference_agent/admin/audit.py src/reference_agent/admin/process_control.py src/reference_agent/admin/routes.py templates/admin/service_control.html static/admin.js tests/test_admin_ui.py
git commit -m "feat: add admin service control and action audit"
```

### Task 4: Configuration Management with Structured and Raw Editing

**Files:**
- Create: `src/reference_agent/admin/config_editor.py`
- Create: `templates/admin/configuration.html`
- Modify: `src/reference_agent/admin/routes.py`
- Modify: `src/reference_agent/config.py`
- Modify: `static/admin.css`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Add failing configuration page tests**

```python
@pytest.mark.asyncio
async def test_configuration_page_lists_edit_targets(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/configuration")
    assert response.status_code == 200
    assert "config.yaml" in response.text
    assert "TOOLS.md" in response.text


@pytest.mark.asyncio
async def test_configuration_structured_preview_shows_restart_required(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration/form/preview",
            data={"port": "9090", "timeout_seconds": "120", "stream_status_updates": "on"},
        )
    assert response.status_code == 200
    assert "Restart required" in response.text
    assert "9090" in response.text


@pytest.mark.asyncio
async def test_configuration_raw_save_rejects_invalid_yaml(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/admin/configuration/raw/preview",
            data={"target": "config.yaml", "content": "llm: [broken"},
        )
    assert response.status_code == 400
    assert "Invalid YAML" in response.text
```

- [ ] **Step 2: Run the raw-save validation test and verify it fails**

Run: `pytest tests/test_admin_ui.py::test_configuration_raw_save_rejects_invalid_yaml -v`

Expected: FAIL with `404 != 400`.

- [ ] **Step 3: Implement config readers, diff preview, and save flows**

```python
# src/reference_agent/admin/config_editor.py
import difflib
from pathlib import Path

import yaml

from reference_agent.config import _extract_tools_yaml, dump_yaml, load_yaml


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def preview_diff(original: str, updated: str, filename: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            original.splitlines(),
            updated.splitlines(),
            fromfile=f"{filename}:current",
            tofile=f"{filename}:updated",
            lineterm="",
        )
    )


def validate_yaml_text(content: str) -> dict:
    try:
        return yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML: {exc}") from exc


def validate_tools_md(content: str) -> dict:
    try:
        return _extract_tools_yaml(content)
    except Exception as exc:
        raise ValueError(f"Invalid TOOLS.md YAML block: {exc}") from exc


def save_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def build_runtime_form_preview(config_path: Path, port: int, timeout_seconds: int, stream_status_updates: bool) -> tuple[str, str]:
    current = load_yaml(config_path)
    updated = dict(current)
    runtime = dict(updated.get("runtime", {}))
    runtime["port"] = port
    runtime["timeout_seconds"] = timeout_seconds
    runtime["stream_status_updates"] = stream_status_updates
    updated["runtime"] = runtime
    original_text = read_text(config_path)
    updated_text = dump_yaml(updated)
    return updated_text, preview_diff(original_text, updated_text, str(config_path))
```

```python
# src/reference_agent/admin/routes.py
from fastapi import Form

from reference_agent.admin.config_editor import (
    build_runtime_form_preview,
    preview_diff,
    read_text,
    save_text,
    validate_tools_md,
    validate_yaml_text,
)

    @router.get("/configuration", response_class=HTMLResponse)
    def configuration(request: Request):
        files = ["config.yaml", "tools/TOOLS.md"] + [str(path) for path in Path("profiles").glob("*.yaml")]
        return templates.TemplateResponse(
            request,
            "admin/configuration.html",
            {
                "page_title": "Configuration",
                "nav_items": nav_items,
                "files": files,
                "diff_text": "",
                "error": "",
                "restart_required": False,
            },
        )

    @router.post("/configuration/form/preview", response_class=HTMLResponse)
    def configuration_form_preview(
        request: Request,
        port: int = Form(...),
        timeout_seconds: int = Form(...),
        stream_status_updates: bool = Form(False),
    ):
        updated_text, diff_text = build_runtime_form_preview(
            Path("config.yaml"),
            port,
            timeout_seconds,
            stream_status_updates,
        )
        return templates.TemplateResponse(
            request,
            "admin/configuration.html",
            {
                "page_title": "Configuration",
                "nav_items": nav_items,
                "files": ["config.yaml", "tools/TOOLS.md"] + [str(path) for path in Path("profiles").glob("*.yaml")],
                "structured_values": {
                    "port": port,
                    "timeout_seconds": timeout_seconds,
                    "stream_status_updates": stream_status_updates,
                },
                "selected_target": "config.yaml",
                "editor_content": updated_text,
                "diff_text": diff_text,
                "error": "",
                "restart_required": True,
            },
        )

    @router.post("/configuration/raw/preview", response_class=HTMLResponse)
    def configuration_preview(request: Request, target: str = Form(...), content: str = Form(...)):
        path = Path(target)
        original = read_text(path)
        if path.name.endswith(".yaml"):
            validate_yaml_text(content)
        elif path.name == "TOOLS.md":
            validate_tools_md(content)
        diff_text = preview_diff(original, content, target)
        return templates.TemplateResponse(
            request,
            "admin/configuration.html",
            {"page_title": "Configuration", "nav_items": nav_items, "files": [target], "selected_target": target, "editor_content": content, "diff_text": diff_text, "error": "", "restart_required": True},
        )

    @router.post("/configuration/raw/apply")
    def configuration_apply(request: Request, target: str = Form(...), content: str = Form(...)):
        path = Path(target)
        if path.name.endswith(".yaml"):
            validate_yaml_text(content)
        elif path.name == "TOOLS.md":
            validate_tools_md(content)
        save_text(path, content)
        audit_store.append("config_apply", target, "ok", "configuration updated", request.client.host if request.client else "unknown")
        return RedirectResponse(f"/admin/configuration?target={target}&saved=1", status_code=303)
```

```html
<!-- templates/admin/configuration.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>Configuration</h2>
<section class="card">
  <h3>Structured Runtime Form</h3>
  <form method="post" action="/admin/configuration/form/preview">
    <label for="port">Port</label>
    <input id="port" name="port" value="{{ structured_values.port if structured_values else '8081' }}">
    <label for="timeout_seconds">Timeout Seconds</label>
    <input id="timeout_seconds" name="timeout_seconds" value="{{ structured_values.timeout_seconds if structured_values else '300' }}">
    <label><input type="checkbox" name="stream_status_updates" {% if structured_values and structured_values.stream_status_updates %}checked{% endif %}> Stream Status Updates</label>
    <button type="submit">Preview Runtime Changes</button>
  </form>
</section>
<section class="card">
  <h3>Raw Editor</h3>
<ul>
  {% for file_path in files %}
  <li>{{ file_path }}</li>
  {% endfor %}
</ul>
<form method="post" action="/admin/configuration/raw/preview">
  <label for="target">Target</label>
  <input id="target" name="target" value="{{ selected_target or 'config.yaml' }}">
  <textarea name="content" rows="20">{{ editor_content or '' }}</textarea>
  <button type="submit">Preview Diff</button>
</form>
{% if diff_text %}
<h3>Diff Preview</h3>
<pre>{{ diff_text }}</pre>
{% endif %}
{% if restart_required %}
<p class="callout">Restart required after apply.</p>
<form method="post" action="/admin/configuration/raw/apply">
  <input type="hidden" name="target" value="{{ selected_target }}">
  <textarea name="content" hidden>{{ editor_content }}</textarea>
  <button type="submit">Apply Changes</button>
</form>
{% endif %}
{% if error %}<p class="error">{{ error }}</p>{% endif %}
</section>
{% endblock %}
```

```python
# src/reference_agent/config.py
def dump_yaml(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False)
```

- [ ] **Step 4: Run the configuration tests**

Run: `pytest tests/test_admin_ui.py::test_configuration_page_lists_edit_targets tests/test_admin_ui.py::test_configuration_structured_preview_shows_restart_required tests/test_admin_ui.py::test_configuration_raw_save_rejects_invalid_yaml -v`

Expected: all listed tests PASS.

- [ ] **Step 5: Commit the configuration management work**

```bash
git add src/reference_agent/admin/config_editor.py src/reference_agent/admin/routes.py src/reference_agent/config.py templates/admin/configuration.html static/admin.css tests/test_admin_ui.py
git commit -m "feat: add admin configuration editor"
```

### Task 5: Logs, Trace Explorer, Docs, and Final Admin Integration

**Files:**
- Create: `src/reference_agent/admin/log_reader.py`
- Create: `src/reference_agent/admin/docs_reader.py`
- Create: `templates/admin/logs.html`
- Create: `templates/admin/docs.html`
- Modify: `src/reference_agent/admin/routes.py`
- Modify: `static/admin.css`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Add failing tests for traces, logs, and docs**

```python
@pytest.mark.asyncio
async def test_logs_page_renders_trace_and_log_sections(monkeypatch, temp_config):
    trace_dir = temp_config / "traces"
    trace_dir.mkdir(exist_ok=True)
    (trace_dir / "trace1.json").write_text(
        '{"trace_id":"trace1","profile_id":"default","profile_version":"v1","router":{"strategy_id":"STR_H","params":{},"rationale_codes":[],"binding_readiness":{"required_bindings":[],"provided_bindings":[],"missing_bindings":[],"dependency_required":false,"resolution_policy":null},"intent_detected":null,"candidate_strategies":[],"tool_health_snapshot":{},"selected_tools":[]},"steps":[],"final_status":"SUCCESS","evidence":[],"user_visible_notes":[],"evaluations":[],"queried_tools_by_step":[],"step_plans":[],"final_status_reasons":[]}'
    )
    (temp_config / "ra.log").write_text("INFO started\n")

    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/logs")
    assert response.status_code == 200
    assert "Trace Explorer" in response.text
    assert "Service Log" in response.text


@pytest.mark.asyncio
async def test_trace_detail_page_renders_timeline(monkeypatch, temp_config):
    trace_dir = temp_config / "traces"
    trace_dir.mkdir(exist_ok=True)
    (trace_dir / "trace2.json").write_text(
        '{"trace_id":"trace2","profile_id":"default","profile_version":"v1","router":{"strategy_id":"STR_H","params":{},"rationale_codes":[],"binding_readiness":{"required_bindings":[],"provided_bindings":[],"missing_bindings":[],"dependency_required":false,"resolution_policy":null},"intent_detected":null,"candidate_strategies":[],"tool_health_snapshot":{},"selected_tools":[]},"steps":[{"step_id":"step-1","tool_id":"demo.hybrid","input_summary":{"q":"What is X?"},"output_summary":{"status":"ok"},"duration_ms":18,"error_code":null,"degraded":false}],"final_status":"SUCCESS","evidence":[],"user_visible_notes":[],"evaluations":[],"queried_tools_by_step":[["demo.hybrid"]],"step_plans":[{"step_index":1,"template":"T1","tool_ids":["demo.hybrid"],"questions":["What is X?"],"rationale_codes":["R1"],"notes":"first step"}],"final_status_reasons":[]}'
    )

    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/logs/trace/trace2")
    assert response.status_code == 200
    assert "step-1" in response.text
    assert "demo.hybrid" in response.text
    assert "18" in response.text


@pytest.mark.asyncio
async def test_docs_page_renders_readme(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/admin/docs?doc=README.md")
    assert response.status_code == 200
    assert "Reference Agent" in response.text
```

- [ ] **Step 2: Run the logs/docs tests and verify they fail**

Run: `pytest tests/test_admin_ui.py::test_logs_page_renders_trace_and_log_sections tests/test_admin_ui.py::test_trace_detail_page_renders_timeline tests/test_admin_ui.py::test_docs_page_renders_readme -v`

Expected: all selected tests FAIL with missing routes.

- [ ] **Step 3: Implement the trace/log readers, docs renderer, and final routes**

```python
# src/reference_agent/admin/log_reader.py
import json
from pathlib import Path

from reference_agent.models import Trace


def list_trace_summaries(trace_dir: Path) -> list[dict]:
    traces = []
    for path in sorted(trace_dir.glob("*.json"), reverse=True):
        data = json.loads(path.read_text(encoding="utf-8"))
        traces.append(
            {
                "trace_id": data["trace_id"],
                "profile_id": data["profile_id"],
                "final_status": data["final_status"],
                "step_count": len(data.get("steps", [])),
                "evidence_count": len(data.get("evidence", [])),
            }
        )
    return traces


def read_service_log(log_path: Path, limit: int = 200) -> list[str]:
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return lines[-limit:]


def read_admin_actions(path: Path, limit: int = 200) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()[-limit:] if line.strip()]


def load_trace_detail(trace_dir: Path, trace_id: str) -> Trace:
    path = trace_dir / f"{trace_id}.json"
    return Trace.model_validate_json(path.read_text(encoding="utf-8"))
```

```python
# src/reference_agent/admin/docs_reader.py
from pathlib import Path

import markdown


DOC_SOURCES = {
    "README.md": Path("README.md"),
    "doc/API_MCP.md": Path("doc/API_MCP.md"),
    "doc/AUTH.md": Path("doc/AUTH.md"),
    "doc/RATIONALE_CODES.md": Path("doc/RATIONALE_CODES.md"),
    "doc/tools_md_example_v1.en.md": Path("doc/tools_md_example_v1.en.md"),
    "doc/tools_md_example_v1.zh_tw.md": Path("doc/tools_md_example_v1.zh_tw.md"),
}


def available_docs() -> list[str]:
    return [name for name, path in DOC_SOURCES.items() if path.exists()]


def render_doc(name: str) -> tuple[str, str]:
    path = DOC_SOURCES[name]
    text = path.read_text(encoding="utf-8")
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    return str(path), html
```

```python
# src/reference_agent/admin/routes.py
from reference_agent.admin.docs_reader import available_docs, render_doc
from reference_agent.admin.log_reader import load_trace_detail, list_trace_summaries, read_admin_actions, read_service_log

    @router.get("/logs", response_class=HTMLResponse)
    def logs(request: Request):
        traces = list_trace_summaries(Path(service.config.audit.trace_dir))
        service_log = read_service_log(Path("data/ra.log"))
        actions = read_admin_actions(Path("data/admin_actions.jsonl"))
        return templates.TemplateResponse(
            request,
            "admin/logs.html",
            {
                "page_title": "Logs & Audit",
                "nav_items": nav_items,
                "traces": traces,
                "service_log": service_log,
                "actions": actions,
            },
        )

    @router.get("/logs/trace/{trace_id}", response_class=HTMLResponse)
    def trace_detail(request: Request, trace_id: str):
        trace = load_trace_detail(Path(service.config.audit.trace_dir), trace_id)
        return templates.TemplateResponse(
            request,
            "admin/logs.html",
            {
                "page_title": "Logs & Audit",
                "nav_items": nav_items,
                "traces": [],
                "service_log": [],
                "actions": [],
                "selected_trace": trace,
            },
        )

    @router.get("/docs", response_class=HTMLResponse)
    def docs(request: Request, doc: str = "README.md"):
        docs_list = available_docs()
        source_path, rendered_html = render_doc(doc)
        return templates.TemplateResponse(
            request,
            "admin/docs.html",
            {
                "page_title": "Docs",
                "nav_items": nav_items,
                "docs_list": docs_list,
                "current_doc": doc,
                "source_path": source_path,
                "rendered_html": rendered_html,
            },
        )
```

```html
<!-- templates/admin/logs.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>Logs & Audit</h2>
<section>
  <h3>Trace Explorer</h3>
  {% for trace in traces %}
  <article class="card">
    <strong><a href="/admin/logs/trace/{{ trace.trace_id }}">{{ trace.trace_id }}</a></strong>
    <p>{{ trace.profile_id }} | {{ trace.final_status }} | steps={{ trace.step_count }} | evidence={{ trace.evidence_count }}</p>
  </article>
  {% endfor %}
</section>
{% if selected_trace %}
<section>
  <h3>Trace Timeline</h3>
  {% for step in selected_trace.steps %}
  <article class="card">
    <strong>{{ step.step_id }}</strong>
    <p>tool={{ step.tool_id }} | duration={{ step.duration_ms }}ms | error={{ step.error_code or 'none' }}</p>
    <pre>{{ step.input_summary | tojson(indent=2) }}</pre>
    <pre>{{ step.output_summary | tojson(indent=2) }}</pre>
  </article>
  {% endfor %}
</section>
{% endif %}
<section>
  <h3>Service Log</h3>
  <pre>{% for line in service_log %}{{ line }}
{% endfor %}</pre>
</section>
<section>
  <h3>Admin Actions</h3>
  <pre>{{ actions | tojson(indent=2) }}</pre>
</section>
{% endblock %}
```

```html
<!-- templates/admin/docs.html -->
{% extends "admin/base.html" %}
{% block content %}
<h2>Docs</h2>
<aside class="doc-nav">
  <ul>
    {% for doc_name in docs_list %}
    <li><a href="/admin/docs?doc={{ doc_name }}">{{ doc_name }}</a></li>
    {% endfor %}
  </ul>
</aside>
<p>Source: {{ source_path }}</p>
<article class="doc-body">{{ rendered_html | safe }}</article>
{% endblock %}
```

- [ ] **Step 4: Run the admin UI test suite**

Run: `pytest tests/test_admin_ui.py -v`

Expected: all admin tests PASS.

- [ ] **Step 5: Commit the logs/docs/admin integration**

```bash
git add src/reference_agent/admin/log_reader.py src/reference_agent/admin/docs_reader.py src/reference_agent/admin/routes.py templates/admin/logs.html templates/admin/docs.html static/admin.css tests/test_admin_ui.py
git commit -m "feat: add admin logs and docs pages"
```

### Task 6: Changelog, Version, and Operational Documentation

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `VERSION.md`
- Test: `tests/test_admin_ui.py`

- [ ] **Step 1: Write a failing smoke test for the completed admin surface**

```python
@pytest.mark.asyncio
async def test_admin_sections_all_resolve(monkeypatch, temp_config):
    monkeypatch.setenv("REFERENCE_AGENT_CONFIG", str(temp_config / "config.yaml"))
    monkeypatch.setenv("REFERENCE_AGENT_TOOLS", str(temp_config / "TOOLS.md"))
    monkeypatch.setenv("REFERENCE_AGENT_PROFILES", str(temp_config / "profiles"))

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for route in [
            "/admin",
            "/admin/service-control",
            "/admin/configuration",
            "/admin/logs",
            "/admin/system-info",
            "/admin/docs",
        ]:
            response = await client.get(route)
            assert response.status_code == 200, route
```

- [ ] **Step 2: Run the smoke test**

Run: `pytest tests/test_admin_ui.py::test_admin_sections_all_resolve -v`

Expected: PASS after Tasks 1-5 are complete.

- [ ] **Step 3: Document the admin UI and update release metadata**

```markdown
<!-- README.md -->
## Admin Web UI
- Open `/admin` on the running Reference Agent service.
- Use `Service Control` for local daemon start/stop/restart.
- Use `Configuration` for structured edits and raw file editing.
- Use `Logs & Audit` to inspect traces, service logs, and admin actions.
```

```markdown
<!-- VERSION.md -->
# Version

v4.3
```

```markdown
<!-- CHANGELOG.md -->
## v4.3

### Added
- Added the built-in Admin Web UI for service control, configuration management, trace/log review, system information, and embedded docs.
```

- [ ] **Step 4: Run the full API and admin test suite**

Run: `pytest -v`

Expected: all existing API tests plus new admin tests PASS.

- [ ] **Step 5: Commit the final admin UI release**

```bash
git add README.md CHANGELOG.md VERSION.md tests/test_admin_ui.py
git commit -m "feat: ship admin web ui"
```
