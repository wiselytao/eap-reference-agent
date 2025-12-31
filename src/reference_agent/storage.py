from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from reference_agent.models import Trace


class FileTraceStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _trace_path(self, trace_id: str) -> Path:
        return self.root / f"{trace_id}.json"

    def save(self, trace: Trace) -> None:
        path = self._trace_path(trace.trace_id)
        path.write_text(trace.model_dump_json(indent=2))

    def load(self, trace_id: str) -> Optional[Trace]:
        path = self._trace_path(trace_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Trace(**data)
