from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from reference_agent.models import PlanExecution, PlanStep, Profile, ToolEntry
from reference_agent.router import Router


@dataclass
class TemplateChoice:
    template: str
    steps: List[PlanStep]
    notes: str


class BoundedPlanner:
    def __init__(self, router: Router) -> None:
        self._router = router

    def build(
        self, query: str, profile: Profile, tools: Dict[str, ToolEntry], context: Dict | None = None
    ) -> PlanExecution:
        intent = self._router.detect_intent(query)
        if context and context.get("need_external"):
            intent = "external"
        vector_tools = self._tools_by_prefix(profile, tools, "VECTOR:")
        graph_tools = self._tools_by_prefix(profile, tools, "GRAPH:")
        hybrid_tools = self._tools_by_prefix(profile, tools, "HYBRID:")
        hybridcot_tools = self._tools_by_prefix(profile, tools, "HYBRIDCOT:")
        sql_tools = self._tools_by_prefix(profile, tools, "SQL:")
        external_tools = [
            tool_id for tool_id in profile.enabled_tools if tools.get(tool_id, None) and tools[tool_id].type == "external_mcp"
        ]

        if external_tools and intent == "external":
            return self._template_t3(external_tools, hybrid_tools or vector_tools or graph_tools or sql_tools, tools)

        if len(vector_tools) >= 2 and graph_tools and self._should_use_t2(query):
            return self._template_t2(vector_tools, graph_tools)

        if vector_tools and graph_tools:
            return self._template_t1(intent, vector_tools, graph_tools)

        if hybrid_tools:
            return self._single("T1", hybrid_tools[0], "HYBRID:", "Single hybrid step")
        if hybridcot_tools:
            return self._single("T1", hybridcot_tools[0], "HYBRIDCOT:", "Single hybridcot step")
        if vector_tools:
            return self._single("T1", vector_tools[0], "VECTOR:", "Single vector step")
        if graph_tools:
            return self._single("T1", graph_tools[0], "GRAPH:", "Single graph step")
        if sql_tools:
            return self._single("T1", sql_tools[0], "SQL:", "Single SQL step")

        return PlanExecution(template="T0", steps=[], notes="No eligible tools")

    def _template_t1(self, intent: str, vector_tools: List[str], graph_tools: List[str]) -> PlanExecution:
        if intent == "relation":
            first = PlanStep(step_id="1", template="T1", tool_id=graph_tools[0], pipeline_prefix="GRAPH:")
            second = PlanStep(step_id="2", template="T1", tool_id=vector_tools[0], pipeline_prefix="VECTOR:")
            return PlanExecution(template="T1", steps=[first, second], notes="G->V dependency")
        first = PlanStep(step_id="1", template="T1", tool_id=vector_tools[0], pipeline_prefix="VECTOR:")
        second = PlanStep(step_id="2", template="T1", tool_id=graph_tools[0], pipeline_prefix="GRAPH:")
        return PlanExecution(template="T1", steps=[first, second], notes="V->G dependency")

    def _template_t2(self, vector_tools: List[str], graph_tools: List[str]) -> PlanExecution:
        steps = [
            PlanStep(step_id="1", template="T2", tool_id=vector_tools[0], pipeline_prefix="VECTOR:"),
            PlanStep(step_id="2", template="T2", tool_id=vector_tools[1], pipeline_prefix="VECTOR:"),
            PlanStep(step_id="3", template="T2", tool_id=graph_tools[0], pipeline_prefix="GRAPH:"),
        ]
        return PlanExecution(template="T2", steps=steps, notes="V->V->G narrowing then graph")

    @staticmethod
    def _should_use_t2(query: str) -> bool:
        lowered = query.lower()
        return any(keyword in lowered for keyword in ["compare", "intersection", "overlap", "difference"])

    def _template_t3(
        self, external_tools: List[str], local_tools: List[str], tools: Dict[str, ToolEntry]
    ) -> PlanExecution:
        steps: List[PlanStep] = []
        if external_tools:
            steps.append(PlanStep(step_id="1", template="T3", tool_id=external_tools[0], pipeline_prefix="EXTERNAL"))
        if local_tools:
            local_tool = tools.get(local_tools[0])
            steps.append(
                PlanStep(
                    step_id="2",
                    template="T3",
                    tool_id=local_tools[0],
                    pipeline_prefix=local_tool.pipeline_prefix if local_tool else "",
                )
            )
        return PlanExecution(template="T3", steps=steps, notes="External join")

    def _single(self, template: str, tool_id: str, prefix: str, notes: str) -> PlanExecution:
        return PlanExecution(
            template=template,
            steps=[PlanStep(step_id="1", template=template, tool_id=tool_id, pipeline_prefix=prefix)],
            notes=notes,
        )

    def _tools_by_prefix(self, profile: Profile, tools: Dict[str, ToolEntry], prefix: str) -> List[str]:
        candidates = [
            tool_id
            for tool_id in profile.enabled_tools
            if tool_id in tools and tools[tool_id].pipeline_prefix == prefix
        ]
        return candidates
