from __future__ import annotations

import json
from typing import Dict, List

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.models import PlanSkeleton, Profile, ToolEntry


class PlanSkeletonBuilder:
    def __init__(self, llm: LLMClient | None, model: str | None) -> None:
        self._llm = llm
        self._model = model

    def build(self, query: str, profile: Profile, tools: Dict[str, ToolEntry]) -> PlanSkeleton:
        candidates = [tool_id for tool_id in profile.enabled_tools if tool_id in tools]
        constraints = {
            "max_steps": profile.limits.max_steps,
            "evidence_min": profile.limits.evidence_min,
            "evidence_max": profile.limits.evidence_max,
        }
        if self._llm and self._model:
            prompt = self._prompt(query, candidates, tools, constraints)
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 512))
                parsed = self._parse(response)
                if parsed:
                    return parsed
            except Exception:
                pass
        return self._fallback(query, candidates, constraints)

    def _prompt(
        self, query: str, candidates: List[str], tools: Dict[str, ToolEntry], constraints: Dict[str, int]
    ) -> str:
        tool_lines = []
        for tool_id in candidates:
            tool = tools.get(tool_id)
            summary = ""
            if tool:
                summary = tool.profile_summary or tool.summary or ""
            tool_lines.append(f"- {tool_id} ({tool.pipeline_prefix or 'UNKNOWN'}): {summary}")
        return (
            "You are building a Plan Skeleton for a bounded RAG planner. "
            "Return strict JSON with keys: answer_blueprint (list of strings), "
            "required_bindings (list of strings), candidate_tools (list of strings), "
            "constraints (object), stop_conditions (list of strings).\n\n"
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
                required_bindings=data.get("required_bindings", []),
                candidate_tools=data.get("candidate_tools", []),
                constraints=data.get("constraints", {}),
                stop_conditions=data.get("stop_conditions", []),
                notes=data.get("notes"),
            )
        except Exception:
            return None

    def _fallback(self, query: str, candidates: List[str], constraints: Dict[str, int]) -> PlanSkeleton:
        return PlanSkeleton(
            answer_blueprint=["Answer the user query with verifiable evidence."],
            required_bindings=[],
            candidate_tools=candidates,
            constraints=constraints,
            stop_conditions=["evidence_min_met", "step_budget_exhausted"],
            notes="Fallback plan skeleton.",
        )
