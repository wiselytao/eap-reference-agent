from __future__ import annotations

import hashlib
import json
from typing import Dict

from reference_agent.models import ToolEntry


def tool_fingerprint(tool: ToolEntry) -> str:
    payload: Dict[str, object] = {
        "tool_id": tool.tool_id,
        "type": tool.type,
        "project_id": tool.project_id,
        "base_url": tool.base_url,
        "summary": tool.summary,
        "capabilities": tool.capabilities,
        "constraints": tool.constraints.model_dump(),
        "evidence_contract": tool.evidence_contract,
        "evidence_locator_policy": tool.evidence_locator_policy,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def tools_md_hash(contents: str) -> str:
    return hashlib.sha256(contents.encode("utf-8")).hexdigest()
