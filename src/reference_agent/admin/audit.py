from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Request

from reference_agent.config import load_config


def append_admin_action_audit(
    request: Request | None,
    *,
    action: str,
    target: str,
    outcome: str,
    details: dict[str, Any] | None = None,
) -> Path:
    record = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "scope": "admin",
        "target": target,
        "action": action,
        "outcome": outcome,
        "remote_addr": _remote_addr(request),
        "details": details or {},
    }
    audit_path = _admin_audit_log_path()
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")
    return audit_path


def _admin_audit_log_path() -> Path:
    config_path = Path(os.getenv("REFERENCE_AGENT_CONFIG", "config.yaml"))
    trace_dir = Path(load_config(config_path).audit.trace_dir)
    return trace_dir / "admin_actions.jsonl"


def _remote_addr(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host
