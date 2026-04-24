from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from starlette.routing import BaseRoute

from reference_agent.config import load_config

from reference_agent.admin.models import (
    AdminPathItem,
    AdminRouteItem,
    AdminSummaryItem,
    OverviewReadModel,
    SystemInfoReadModel,
)


def build_overview_read_model() -> OverviewReadModel:
    path_items = build_path_items()
    return OverviewReadModel(
        summary_items=(
            AdminSummaryItem(label="Port", value=str(read_runtime_port())),
            AdminSummaryItem(label="Config", value=path_items[0].value),
            AdminSummaryItem(label="Tools", value=path_items[1].value),
            AdminSummaryItem(label="Profiles", value=path_items[2].value),
        )
    )


def build_system_info_read_model(routes: Iterable[BaseRoute]) -> SystemInfoReadModel:
    return SystemInfoReadModel(
        path_items=build_path_items(),
        route_items=tuple(sorted(_iter_route_items(routes), key=lambda item: (item.path, item.name))),
    )


def build_path_items() -> tuple[AdminPathItem, ...]:
    return (
        AdminPathItem(label="Config file", value=str(_configured_path("REFERENCE_AGENT_CONFIG", "config.yaml"))),
        AdminPathItem(label="Tools file", value=str(_configured_path("REFERENCE_AGENT_TOOLS", "tools/TOOLS.md"))),
        AdminPathItem(label="Profiles directory", value=str(_configured_path("REFERENCE_AGENT_PROFILES", "profiles"))),
    )


def read_runtime_port() -> int:
    config_path = _configured_path("REFERENCE_AGENT_CONFIG", "config.yaml")
    try:
        return load_config(config_path).runtime.port
    except (FileNotFoundError, ValueError):
        env_port = os.getenv("REFERENCE_AGENT_PORT")
        if env_port:
            try:
                return int(env_port)
            except ValueError:
                pass
        return 8080


def _configured_path(env_var: str, default: str) -> Path:
    return Path(os.getenv(env_var, default)).resolve()


def _iter_route_items(routes: Iterable[BaseRoute]) -> Iterable[AdminRouteItem]:
    for route in routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        methods = tuple(sorted(method for method in getattr(route, "methods", set()) if method != "HEAD"))
        if not methods:
            methods = ("MOUNT",)
        yield AdminRouteItem(
            path=path,
            methods=methods,
            name=getattr(route, "name", route.__class__.__name__),
        )
