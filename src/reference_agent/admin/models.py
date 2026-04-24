from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdminSummaryItem:
    label: str
    value: str


@dataclass(frozen=True)
class AdminPathItem:
    label: str
    value: str


@dataclass(frozen=True)
class AdminRouteItem:
    path: str
    methods: tuple[str, ...]
    name: str


@dataclass(frozen=True)
class OverviewReadModel:
    summary_items: tuple[AdminSummaryItem, ...]


@dataclass(frozen=True)
class SystemInfoReadModel:
    path_items: tuple[AdminPathItem, ...]
    route_items: tuple[AdminRouteItem, ...]
