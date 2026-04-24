from __future__ import annotations

from importlib.resources import files

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

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
