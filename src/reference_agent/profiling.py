from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from reference_agent.adapters.hybridrag import HybridRagClient, HybridRagConfig
from reference_agent.models import ToolEntry
from reference_agent.secrets import resolve_secret
from reference_agent.tool_routing import prefix_for_tool


@dataclass
class ProfilingRecord:
    tool_id: str
    generated_at: str
    questions: List[str]
    profile_summary: str
    l0_profile: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    tool_hash: Optional[str] = None
    schema: Dict[str, List[str]] = field(default_factory=dict)


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
                questions=data.get("questions", []),
                profile_summary=data.get("profile_summary", ""),
                l0_profile=data.get("l0_profile", {}) or {},
                tool_hash=data.get("tool_hash"),
                schema=data.get("schema", {}) or {},
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
            "questions": record.questions,
            "profile_summary": record.profile_summary,
            "l0_profile": record.l0_profile,
            "tool_hash": record.tool_hash,
            "schema": record.schema,
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
        prefix = prefix_for_tool(tool) or ""
        trimmed = questions[: self.max_questions]
        responses = await self._ask_parallel(tool, [f"{prefix} {q}" for q in trimmed])
        summary = self._build_summary(trimmed, responses)
        l0_profile = self._build_l0_profile(responses)
        return ProfilingRecord(
            tool_id=tool.tool_id,
            generated_at=datetime.utcnow().isoformat(timespec="seconds"),
            questions=trimmed,
            profile_summary=summary,
            l0_profile=l0_profile,
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

    @staticmethod
    def _build_l0_profile(responses: List[str]) -> Dict[str, List[Dict[str, str]]]:
        merged: Dict[str, List[Dict[str, str]]] = {}
        for response in responses:
            payload = RuntimeProber._parse_json(response)
            if not payload:
                continue
            l0 = payload.get("l0_profile") or {}
            if not isinstance(l0, dict):
                continue
            for key, value in l0.items():
                if not isinstance(value, list):
                    continue
                merged.setdefault(key, [])
                for item in value:
                    if isinstance(item, dict):
                        merged[key].append({str(k): str(v) for k, v in item.items()})
        return merged

    @staticmethod
    def _parse_json(text: str) -> Dict[str, Any] | None:
        cleaned = text.strip()
        if not cleaned:
            return None
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def question_set_for_tool(tool: ToolEntry) -> List[str]:
    prefix = (prefix_for_tool(tool) or "").upper()
    if prefix == "GRAPH:":
        return [
            "show me the summary of schema in triple format, and then list all the properties "
            "of each node and relationship, and 3 sample values of each property. No translation.",
            "Provide one example traversal query this graph supports (include the labels and properties used).",
        ]
    if prefix == "VECTOR:":
        return [
            "Based only on the content you can actually retrieve, list the 8-12 most commonly described "
            'actions or behaviors (e.g., configure, check, analyze, report, adjust, remediate). '
            'For each action, provide one short sentence describing the typical context. '
            'If you cannot determine an action with confidence, explicitly mark it as "Unknown". '
            "Do NOT infer or guess.\n\n"
            "Output ONLY the following JSON:\n"
            "{\n"
            '  "raw_answer": "<your natural language answer here>",\n'
            '  "l0_profile": {\n'
            '    "actions": [\n'
            '      {"verb": "<action>", "context": "<typical context>"}\n'
            "    ]\n"
            "  }\n"
            "}",
            "Based only on the retrievable content, list 6-10 common and concrete relationship patterns "
            "using the format:\n"
            "A -[relation]-> B\n\n"
            'Avoid abstract placeholders (e.g., "item", "data"). Use only entities or roles you can '
            'actually observe. If you cannot determine a relationship with confidence, mark it as "Unknown".\n\n'
            "Output ONLY the following JSON:\n"
            "{\n"
            '  "raw_answer": "<your natural language answer here>",\n'
            '  "l0_profile": {\n'
            '    "relations": [\n'
            '      {"from": "A", "relation": "<relation>", "to": "B"}\n'
            "    ]\n"
            "  }\n"
            "}",
            "List 5 question types or example questions that you are MOST confident you can answer "
            "based on the available content. Each example must reflect common task language found in "
            "the data (e.g., operation, decision-making, troubleshooting, tracking, comparison). "
            'If unsure, explicitly mark as "Unknown".\n\n'
            "Output ONLY the following JSON:\n"
            "{\n"
            '  "raw_answer": "<your natural language answer here>",\n'
            '  "l0_profile": {\n'
            '    "task_types": [\n'
            '      {"example_question": "<example question>", "task_type": "<task type>"}\n'
            "    ]\n"
            "  }\n"
            "}",
            "List 5-10 systems, tools, document types, or artifacts that commonly appear in the "
            "retrievable content (e.g., SOPs, configuration guides, incident records, reports). "
            "Only include items you can directly observe or clearly identify. Do NOT infer.\n\n"
            "Output ONLY the following JSON:\n"
            "{\n"
            '  "raw_answer": "<your natural language answer here>",\n'
            '  "l0_profile": {\n'
            '    "artifacts": [\n'
            '      {"type": "<artifact type>", "description": "<brief purpose>"}\n'
            "    ]\n"
            "  }\n"
            "}",
            "Describe whether the retrievable content includes references to state changes, histories, "
            "versions, or time-based sequences. List 3-6 concrete examples of such signals or language "
            "patterns. If such signals are largely absent, explicitly state that.\n\n"
            "Output ONLY the following JSON:\n"
            "{\n"
            '  "raw_answer": "<your natural language answer here>",\n'
            '  "l0_profile": {\n'
            '    "state_time_signals": [\n'
            '      {"signal": "<state or time-related signal>", "usage": "<usage context>"}\n'
            "    ]\n"
            "  }\n"
            "}",
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
