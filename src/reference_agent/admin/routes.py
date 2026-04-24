from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

repo_root = Path(__file__).resolve().parents[3]
templates = Jinja2Templates(directory=str(repo_root / "templates"))
admin_static_dir = repo_root / "static"

admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin/overview.html",
        {
            "page_title": "Reference Agent Admin",
            "page_heading": "Overview",
            "nav_links": [
                {"label": "Overview", "href": "/admin"},
                {"label": "Service Control", "href": "/admin/service-control"},
                {"label": "Configuration", "href": "/admin/configuration"},
                {"label": "Logs", "href": "/admin/logs"},
                {"label": "System Info", "href": "/admin/system-info"},
                {"label": "Docs", "href": "/admin/docs"},
            ],
        },
    )
