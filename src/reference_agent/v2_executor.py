from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from reference_agent.bindings import extract_bindings
from reference_agent.executor import ExecutionResult, StrategyExecutor
from reference_agent.models import Evidence, PlanExecution, PlanStep, Profile, ToolEntry


class BoundedExecutor:
    def __init__(self, executor: StrategyExecutor) -> None:
        self._executor = executor

    def execute(self, plan: PlanExecution, query: str, profile: Profile, tools: Dict[str, ToolEntry]) -> ExecutionResult:
        if plan.template == "T3":
            return self._execute_t3(plan, query, profile, tools)
        return self._execute_sequential(plan.steps, query, profile, tools)

    def _execute_t3(
        self, plan: PlanExecution, query: str, profile: Profile, tools: Dict[str, ToolEntry]
    ) -> ExecutionResult:
        external_tool = self._get_tool_by_prefix(plan.steps, tools, "EXTERNAL")
        local_tool = self._get_tool_by_prefix(plan.steps, tools, None)
        if not external_tool or not local_tool:
            return ExecutionResult("", [], [], "FAILED")

        with ThreadPoolExecutor(max_workers=2) as pool:
            external_future = pool.submit(self._executor.call_tool, external_tool, query)
            local_future = pool.submit(self._executor.call_tool, local_tool, query)
            external_answer, external_evidence, external_step = external_future.result()
            local_answer, local_evidence, local_step = local_future.result()

        evidence = external_evidence + local_evidence
        steps = [external_step, local_step]
        answer = self._executor.compose_external(query, local_answer, external_answer, evidence)
        status = self._executor.evaluate_fork_join_status(profile, local_tool, external_tool, evidence)
        return ExecutionResult(answer, evidence, steps, status)

    def _execute_sequential(
        self, steps: List[PlanStep], query: str, profile: Profile, tools: Dict[str, ToolEntry]
    ) -> ExecutionResult:
        evidence: List[Evidence] = []
        step_records = []
        current_query = query
        last_tool = None
        for idx, step in enumerate(steps, start=1):
            tool = tools.get(step.tool_id or "")
            if not tool:
                return ExecutionResult("", evidence, step_records, "FAILED")
            answer, step_evidence, step_record = self._executor.call_tool(tool, current_query)
            evidence.extend(step_evidence)
            step_records.append(step_record)
            last_tool = tool

            bindings = extract_bindings(answer)
            if bindings:
                step.bindings_used = bindings
            if idx < len(steps) and bindings:
                current_query = f"{query}\nIdentifiers: {', '.join(bindings)}"

        if not last_tool:
            return ExecutionResult("", evidence, step_records, "EMPTY")
        status = self._executor.evaluate_status(profile, last_tool, evidence, required=True)
        return ExecutionResult(answer, evidence, step_records, status)

    @staticmethod
    def _get_tool_by_prefix(steps: List[PlanStep], tools: Dict[str, ToolEntry], prefix: str | None) -> ToolEntry | None:
        for step in steps:
            tool = tools.get(step.tool_id or "")
            if not tool:
                continue
            if prefix == "EXTERNAL" and tool.type == "external_mcp":
                return tool
            if prefix is None and tool.type != "external_mcp":
                return tool
        return None
