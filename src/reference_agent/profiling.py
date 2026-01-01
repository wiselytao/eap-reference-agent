from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from reference_agent.adapters.hybridrag import HybridRagClient, HybridRagConfig
from reference_agent.models import ToolEntry
from reference_agent.secrets import resolve_secret


@dataclass
class ProfilingRecord:
    tool_id: str
    generated_at: str
    pipeline_prefix: Optional[str]
    questions: List[str]
    profile_summary: str
    tool_hash: Optional[str] = None


class ProfilingStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def load_latest(self, tool_id: str) -> Optional[ProfilingRecord]:
        pattern = f"{self._sanitize(tool_id)}-*.yaml"
        candidates = sorted(self.root.glob(pattern))
        if not candidates:
            return None
        path = candidates[-1]
        data = yaml.safe_load(path.read_text()) or {}
        try:
            return ProfilingRecord(
                tool_id=data.get("tool_id", tool_id),
                generated_at=data.get("generated_at", ""),
                pipeline_prefix=data.get("pipeline_prefix"),
                questions=data.get("questions", []),
                profile_summary=data.get("profile_summary", ""),
                tool_hash=data.get("tool_hash"),
            )
        except Exception:
            return None

    def save(self, record: ProfilingRecord) -> Path:
        timestamp = datetime.utcnow().strftime("%m%d%H%M")
        filename = f"{self._sanitize(record.tool_id)}-{timestamp}.yaml"
        path = self.root / filename
        payload = {
            "tool_id": record.tool_id,
            "generated_at": record.generated_at,
            "pipeline_prefix": record.pipeline_prefix,
            "questions": record.questions,
            "profile_summary": record.profile_summary,
            "tool_hash": record.tool_hash,
        }
        path.write_text(yaml.safe_dump(payload, sort_keys=False))
        return path

    @staticmethod
    def _sanitize(tool_id: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_.-]", "_", tool_id)


class RuntimeProber:
    def __init__(
        self,
        max_questions: int = 3,
        timeout_seconds: int = 60,
        max_retries: int = 2,
        retry_backoff_seconds: int = 2,
    ) -> None:
        self.max_questions = max_questions
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    async def probe(self, tool: ToolEntry, questions: List[str]) -> ProfilingRecord:
        prefix = tool.pipeline_prefix or ""
        trimmed = questions[: self.max_questions]
        responses = await self._ask_parallel(tool, [f"{prefix} {q}" for q in trimmed])
        summary = self._build_summary(trimmed, responses)
        return ProfilingRecord(
            tool_id=tool.tool_id,
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            pipeline_prefix=tool.pipeline_prefix,
            questions=trimmed,
            profile_summary=summary,
        )

    async def _ask_parallel(self, tool: ToolEntry, questions: List[str]) -> List[str]:
        tasks = [self._ask(tool, question) for question in questions]
        return await asyncio.gather(*tasks, return_exceptions=False)

    async def _ask(self, tool: ToolEntry, question: str) -> str:
        config = HybridRagConfig(
            base_url=tool.base_url or "",
            auth_token=resolve_secret(tool.auth_ref),
            timeout_seconds=self.timeout_seconds,
        )
        client = HybridRagClient(config)
        loop = asyncio.get_running_loop()
        for attempt in range(self.max_retries + 1):
            try:
                chat_id = await loop.run_in_executor(None, client.create_chat)
                answer, _ = await loop.run_in_executor(None, client.send_message, chat_id, question)
                return answer
            except Exception:
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(self.retry_backoff_seconds * (attempt + 1))
        return ""

    @staticmethod
    def _build_summary(questions: List[str], responses: List[str]) -> str:
        lines = []
        for question, response in zip(questions, responses):
            snippet = response.strip().replace("\n", " ")
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            lines.append(f"Q: {question}\nA: {snippet}")
        return "\n\n".join(lines)


def question_set_for_tool(tool: ToolEntry) -> List[str]:
    prefix = (tool.pipeline_prefix or "").upper()
    if prefix == "GRAPH:":
        return [
            "List the node labels in this graph and describe each briefly.",
            "List the relationship types and the allowed source/target labels for each.",
            "For each node label, list key properties and provide 2-3 sample values.",
            "For each relationship type, list key properties and provide 2-3 sample values.",
            "Provide one example traversal query this graph supports (include the labels and properties used).",
        ]
    if prefix == "SQL:":
        return [
            "What are the main tables or datasets available?",
            "Which time fields are available for filtering?",
            "Provide an example metric query supported by this dataset.",
        ]
    return [
        "What topics does this dataset cover?",
        "Provide 3 example questions this dataset can answer.",
        "List key entities or concepts (5-10) that appear frequently.",
        "What time range or scope is included?",
        "What common filters or fields are available (e.g., product, version, region)?",
    ]
