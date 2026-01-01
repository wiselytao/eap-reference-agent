from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple

from reference_agent.bindings import extract_bindings
from reference_agent.executor import ExecutionResult, StrategyExecutor
from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.evaluator import Evaluator
from reference_agent.models import Evidence, PlanExecution, PlanSkeleton, PlanStep, Profile, ToolEntry


class BoundedExecutor:
    def __init__(
        self,
        executor: StrategyExecutor,
        evaluator: Evaluator,
        llm: LLMClient | None = None,
        model: str | None = None,
    ) -> None:
        self._executor = executor
        self._evaluator = evaluator
        self._llm = llm
        self._model = model

    def execute(
        self,
        plan: PlanExecution,
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
    ) -> ExecutionResult:
        if plan.template == "T3":
            return self._execute_t3(plan, plan_skeleton, query, profile, tools)
        return self._execute_sequential(plan.steps, plan_skeleton, query, profile, tools)

    def _execute_t3(
        self,
        plan: PlanExecution,
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
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
        evaluation = self._evaluator.evaluate(
            plan_skeleton,
            answer,
            evidence,
            profile.limits.evidence_min,
            step_id="T3",
            step_index=1,
            max_steps=profile.limits.max_steps,
        )
        return ExecutionResult(answer, evidence, steps, status, evaluations=[evaluation])

    def _execute_sequential(
        self,
        steps: List[PlanStep],
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
    ) -> ExecutionResult:
        evidence: List[Evidence] = []
        step_records = []
        evaluations = []
        current_query = query
        last_tool = None
        best_answer = ""
        for idx, step in enumerate(steps, start=1):
            tool = tools.get(step.tool_id or "")
            if not tool:
                return ExecutionResult("", evidence, step_records, "FAILED")
            answer, step_evidence, step_record = self._executor.call_tool(tool, current_query)
            evidence.extend(step_evidence)
            step_records.append(step_record)
            last_tool = tool

            evaluation = self._evaluator.evaluate(
                    plan_skeleton,
                    answer,
                    evidence,
                    profile.limits.evidence_min,
                    step_id=step.step_id,
                    step_index=idx,
                    max_steps=profile.limits.max_steps,
                )
            evaluations.append(evaluation)
            if evaluation.coverage_complete and evaluation.evidence_count >= profile.limits.evidence_min:
                best_answer = answer
            if idx > 1:
                prev = evaluations[-2]
                coverage_progress = len(evaluation.missing_items) < len(prev.missing_items)
                binding_progress = len(evaluation.missing_fields) < len(prev.missing_fields)
                if not coverage_progress and not binding_progress:
                    if (
                        evaluation.evidence_count >= profile.limits.evidence_min
                        and evaluation.locator_ok
                    ):
                        evaluation.should_continue = False
            if idx < len(steps):
                current_query = self._build_followup_query(
                    query,
                    answer,
                    evaluation.missing_items,
                    evaluation.missing_fields,
                    evaluation.found_fields,
                )
            if not evaluation.should_continue:
                break

            bindings = extract_bindings(answer)
            if bindings:
                step.bindings_used = bindings
            if idx < len(steps) and bindings:
                current_query = f"{query}\nIdentifiers: {', '.join(bindings)}"

        if not last_tool:
            return ExecutionResult("", evidence, step_records, "EMPTY")
        status = self._executor.evaluate_status(profile, last_tool, evidence, required=True)
        if best_answer:
            answer = best_answer
        return ExecutionResult(answer, evidence, step_records, status, evaluations=evaluations)

    def _build_followup_query(
        self,
        original_query: str,
        answer: str,
        missing_items: List[str],
        missing_fields: List[str],
        found_fields: List[str],
    ) -> str:
        summary = self._truncate(answer, 300)
        lines = [original_query]
        if summary:
            lines.append(f"Known summary: {summary}")
        if missing_items:
            lines.append(f"Missing items: {', '.join(missing_items)}")
        if missing_fields:
            lines.append(f"Missing fields: {', '.join(missing_fields)}")
        if found_fields:
            lines.append(f"Identifiers: {', '.join(found_fields)}")
        draft = "\n".join(lines)
        if not self._llm or not self._model:
            return draft
        prompt = (
            "Rewrite the following follow-up context into a single concise question. "
            "Keep it focused on retrieving the missing items/fields. Do not include labels like "
            "'Missing items' or 'Missing fields' in the final question.\n\n"
            f"{draft}\n"
        )
        try:
            rewritten = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 128)).strip()
            return rewritten or draft
        except Exception:
            return draft

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        snippet = (text or "").strip().replace("\n", " ")
        if len(snippet) <= max_len:
            return snippet
        return snippet[:max_len] + "..."

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
