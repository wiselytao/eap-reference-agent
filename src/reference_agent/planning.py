from __future__ import annotations

import json
from typing import Dict, List

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.models import PlanSkeleton, Profile, ToolEntry
from reference_agent.tool_routing import prefix_for_tool
from reference_agent.profiling import ProfilingStore


class PlanSkeletonBuilder:
    def __init__(
        self, llm: LLMClient | None, model: str | None, profiling_store: ProfilingStore | None = None
    ) -> None:
        self._llm = llm
        self._model = model
        self._profiling_store = profiling_store

    def build(self, query: str, profile: Profile, tools: Dict[str, ToolEntry]) -> PlanSkeleton:
        candidates = [tool_id for tool_id in profile.enabled_tools if tool_id in tools]
        constraints = {
            "max_steps": profile.limits.max_steps,
            "evidence_min": profile.limits.evidence_min,
            "evidence_max": profile.limits.evidence_max,
        }
        allowed_fields = self._allowed_fields(candidates, tools)
        tool_selection_notes = self._tool_selection_notes(candidates, tools)
        if self._llm and self._model:
            prompt = self._prompt(query, candidates, tools, constraints, allowed_fields)
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 512))
                parsed = self._parse(response)
                if parsed:
                    if allowed_fields:
                        parsed.required_fields = [
                            item for item in parsed.required_fields if item in allowed_fields
                        ]
                    if tool_selection_notes:
                        parsed.tool_selection_notes = tool_selection_notes
                    return parsed
            except Exception:
                pass
        return self._fallback(query, candidates, constraints, tool_selection_notes)

    def _prompt(
        self,
        query: str,
        candidates: List[str],
        tools: Dict[str, ToolEntry],
        constraints: Dict[str, int],
        allowed_fields: List[str],
    ) -> str:
        tool_lines = []
        for tool_id in candidates:
            tool = tools.get(tool_id)
            summary = ""
            if tool:
                summary = tool.profile_summary or tool.summary or ""
            prefix = prefix_for_tool(tool) if tool else "UNKNOWN"
            tool_lines.append(f"- {tool_id} ({prefix}): {summary}")
        allowed_note = (
            f"required_fields must be chosen from this list only: {allowed_fields}\n\n"
            if allowed_fields
            else "required_fields may be any concise field names that the answer must include.\n\n"
        )
        return (
            "You are building a Plan Skeleton for a bounded RAG planner. "
            "Return strict JSON with keys: answer_blueprint (list of strings), "
            "required_fields (list of strings), candidate_tools (list of strings), "
            "constraints (object), stop_conditions (list of strings), tool_selection_notes (list of strings).\n\n"
            f"{allowed_note}"
            f"Query: {query}\n\n"
            f"Candidate tools:\n{chr(10).join(tool_lines)}\n\n"
            f"Constraints: {json.dumps(constraints)}\n"
        )

    def _parse(self, text: str) -> PlanSkeleton | None:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        try:
                return PlanSkeleton(
                    answer_blueprint=data.get("answer_blueprint", []),
                    required_fields=data.get("required_fields", data.get("required_bindings", [])),
                    candidate_tools=data.get("candidate_tools", []),
                    constraints=data.get("constraints", {}),
                    stop_conditions=data.get("stop_conditions", []),
                    notes=data.get("notes"),
                    tool_selection_notes=data.get("tool_selection_notes", []),
                )
        except Exception:
            return None

    def _fallback(
        self, query: str, candidates: List[str], constraints: Dict[str, int], tool_notes: List[str]
    ) -> PlanSkeleton:
        return PlanSkeleton(
            answer_blueprint=["Answer the user query with verifiable evidence."],
            required_fields=[],
            candidate_tools=candidates,
            constraints=constraints,
            stop_conditions=["evidence_min_met", "step_budget_exhausted"],
            notes="Fallback plan skeleton.",
            tool_selection_notes=tool_notes,
        )

    def _allowed_fields(self, candidates: List[str], tools: Dict[str, ToolEntry]) -> List[str]:
        schema_fields = []
        for tool_id in candidates:
            tool = tools.get(tool_id)
            if not tool:
                continue
            prefix = prefix_for_tool(tool)
            if prefix in {"GRAPH:", "SQL:"}:
                if self._profiling_store:
                    record = self._profiling_store.load_latest(tool_id)
                    if record and record.schema:
                        schema_fields.extend(record.schema.get("fields", []))
        if len(schema_fields) >= 3:
            return sorted(set(schema_fields))
        return []

    @staticmethod
    def _tool_selection_notes(candidates: List[str], tools: Dict[str, ToolEntry]) -> List[str]:
        notes = []
        for tool_id in candidates:
            tool = tools.get(tool_id)
            if not tool:
                continue
            summary = tool.profile_summary or tool.summary or ""
            prefix = prefix_for_tool(tool) or "UNKNOWN"
            if summary:
                notes.append(f"{tool_id} ({prefix}): {summary}")
            else:
                notes.append(f"{tool_id} ({prefix}): no summary available")
        return notes
