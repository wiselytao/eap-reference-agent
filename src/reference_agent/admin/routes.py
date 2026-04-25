from __future__ import annotations

from importlib.resources import files
from urllib.parse import parse_qs

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from reference_agent.admin.audit import append_admin_action_audit
from reference_agent.admin.config_editor import (
    build_configuration_page_model,
    handle_configuration_submission,
)
from reference_agent.admin.docs_reader import build_docs_page_model
from reference_agent.admin.log_reader import build_logs_page_model, build_trace_detail_model
from reference_agent.admin.process_control import (
    ProcessControlError,
    build_service_control_read_model,
    schedule_restart,
    start_service,
    stop_service,
)
from reference_agent.admin.system_info import (
    build_overview_read_model,
    build_system_info_read_model,
)

admin_package = files("reference_agent.admin")
templates = Jinja2Templates(directory=str(admin_package.joinpath("templates")))
admin_static_dir = admin_package.joinpath("static")

admin_router = APIRouter(prefix="/admin", tags=["admin"])
nav_links = [
    {"label": "Overview", "href": "/admin"},
    {"label": "Service Control", "href": "/admin/service-control"},
    {"label": "Configuration", "href": "/admin/configuration"},
    {"label": "Logs", "href": "/admin/logs"},
    {"label": "System Info", "href": "/admin/system-info"},
    {"label": "Docs", "href": "/admin/docs"},
]


@admin_router.get("", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/overview.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Overview",
            "nav_links": nav_links,
            "overview": build_overview_read_model(),
        },
    )


@admin_router.get("/system-info", response_class=HTMLResponse)
async def system_info(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/system_info.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "System Info",
            "nav_links": nav_links,
            "system_info": build_system_info_read_model(request.app.routes),
        },
    )


@admin_router.get("/service-control", response_class=HTMLResponse)
async def service_control(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/service_control.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Service Control",
            "nav_links": nav_links,
            "service_status": build_service_control_read_model(),
        },
    )


@admin_router.get("/configuration", response_class=HTMLResponse)
async def configuration(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/configuration.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Configuration",
            "nav_links": nav_links,
            "configuration": build_configuration_page_model(),
        },
    )


@admin_router.post("/configuration", response_class=HTMLResponse)
async def configuration_submit(request: Request) -> HTMLResponse:
    form_data = await _read_form_data(request)
    return templates.TemplateResponse(
        request,
        "admin/configuration.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Configuration",
            "nav_links": nav_links,
            "configuration": handle_configuration_submission(form_data),
        },
    )


@admin_router.get("/logs", response_class=HTMLResponse)
async def logs(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/logs.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Logs",
            "nav_links": nav_links,
            "logs_model": build_logs_page_model(),
            "trace_detail": None,
        },
    )


@admin_router.get("/logs/trace/{trace_id}", response_class=HTMLResponse)
async def trace_detail(request: Request, trace_id: str) -> HTMLResponse:
    model = build_trace_detail_model(trace_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return templates.TemplateResponse(
        request,
        "admin/logs.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Logs",
            "nav_links": nav_links,
            "logs_model": build_logs_page_model(),
            "trace_detail": model,
        },
    )


@admin_router.get("/docs", response_class=HTMLResponse)
async def docs(request: Request, doc: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/docs.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Docs",
            "nav_links": nav_links,
            "docs_model": build_docs_page_model(doc),
        },
    )


@admin_router.get("/service-control/status")
async def service_control_status() -> dict[str, object]:
    return build_service_control_read_model()


@admin_router.post("/service-control/actions/{action_name}")
async def service_control_action(
    request: Request, action_name: str, background_tasks: BackgroundTasks
) -> JSONResponse:
    action_handlers = {
        "start": (start_service, 200, False),
        "stop": (stop_service, 200, False),
    }
    if action_name == "restart":
        background_tasks.add_task(_spawn_restart_with_audit, _request_remote_addr(request))
        payload = {
            "action": action_name,
            "result": {
                "message": "restart scheduled",
                "poll_url": "/admin/service-control/status",
            },
            "status": build_service_control_read_model(),
            "detached": True,
            "poll_url": "/admin/service-control/status",
        }
        return JSONResponse(payload, status_code=202)

    handler_meta = action_handlers.get(action_name)
    if handler_meta is None:
        raise HTTPException(status_code=404, detail="Unknown admin action")
    handler, status_code, detached = handler_meta
    try:
        result = handler()
    except Exception as exc:
        append_admin_action_audit(
            request,
            action=action_name,
            target="service-control",
            outcome="error",
            details={"error_type": type(exc).__name__, "message": str(exc)},
        )
        if isinstance(exc, ProcessControlError):
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="Service control action failed.") from exc

    append_admin_action_audit(
        request,
        action=action_name,
        target="service-control",
        outcome="success",
        details=result,
    )
    payload = {
        "action": action_name,
        "result": result,
        "status": build_service_control_read_model(),
    }
    if detached:
        payload["detached"] = True
        payload["poll_url"] = str(result.get("poll_url", "/admin/service-control/status"))
    return JSONResponse(payload, status_code=status_code)


def _spawn_restart_with_audit(remote_addr: str | None) -> None:
    try:
        result = schedule_restart()
    except Exception as exc:
        append_admin_action_audit(
            None,
            action="restart",
            target="service-control",
            outcome="error",
            details={"error_type": type(exc).__name__, "message": str(exc)},
            remote_addr_override=remote_addr,
        )
        return

    append_admin_action_audit(
        None,
        action="restart",
        target="service-control",
        outcome="success",
        details=result,
        remote_addr_override=remote_addr,
    )


def _request_remote_addr(request: Request) -> str | None:
    if request.client is None:
        return None
    return request.client.host


async def _read_form_data(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8")
    parsed = parse_qs(body, keep_blank_values=True)
    return {key: values[-1] for key, values in parsed.items()}
