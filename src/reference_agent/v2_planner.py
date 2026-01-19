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
        if context and context.get("execution_plan") in {"DISTRIBUTED", "FAN_OUT"}:
            plan = context["execution_plan"]
            return PlanExecution(
                template=plan,
                steps=[PlanStep(step_id="1", template=plan)],
                notes=f"Execution plan override: {plan}",
            )
        return PlanExecution(
            template="DYNAMIC",
            steps=[PlanStep(step_id="1", template="DYNAMIC")],
            notes="Parallel candidate tools then gap-driven follow-ups",
        )
