from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from typing import Dict, List

from reference_agent.executor import ExecutionResult, StrategyExecutor
from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.evaluator import Evaluator
from reference_agent.models import (
    Evidence,
    EvaluationRecord,
    PlanExecution,
    PlanSkeleton,
    PlanStep,
    Profile,
    StepPlan,
    ToolEntry,
)


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
        if plan.template == "DYNAMIC":
            return self._execute_dynamic(plan_skeleton, query, profile, tools)
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

    def _execute_dynamic(
        self,
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
    ) -> ExecutionResult:
        evidence: List[Evidence] = []
        step_records = []
        evaluations: List[EvaluationRecord] = []
        step_plans: List[StepPlan] = []
        tool_answer_map: dict[str, List[str]] = {}
        current_query = query
        candidate_tool_ids = [
            tool_id for tool_id in (plan_skeleton.candidate_tools or profile.enabled_tools) if tool_id in tools
        ]
        used_tool_ids: set[str] = set()

        for step_index in range(1, profile.limits.max_steps + 1):
            if step_index == 1:
                step_tool_ids = candidate_tool_ids
                selection_rationale = ["R_STEP1_ALL_CANDIDATES"]
            else:
                step_tool_ids, selection_rationale = self._select_gap_tools(
                    tools,
                    evaluations[-1],
                    candidate_tool_ids,
                    used_tool_ids,
                )
            if not step_tool_ids:
                break

            step_answers: List[str] = []
            questions, query_rationale = self._build_multi_queries(
                query,
                current_query,
                evaluations[-1] if evaluations else None,
            )
            max_workers = min(12, len(step_tool_ids) * len(questions)) or 1
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for tool_id in step_tool_ids:
                    tool = tools.get(tool_id)
                    if not tool:
                        continue
                    for q_index, question in enumerate(questions, start=1):
                        futures[(tool_id, q_index)] = pool.submit(
                            self._executor.call_tool, tool, question
                        )
                for (tool_id, q_index), future in futures.items():
                    answer, step_evidence, step_record = future.result()
                    step_record.input_summary["step_index"] = step_index
                    step_record.input_summary["query_index"] = q_index
                    step_record.step_id = f"{step_index}:{tool_id}:{q_index}"
                    step_records.append(step_record)
                    evidence.extend(step_evidence)
                    step_answers.append(f"[{tool_id}#{q_index}] {answer}".strip())
                    tool_answer_map.setdefault(tool_id, []).append(answer)

            step_plans.append(
                StepPlan(
                    step_index=step_index,
                    template="DYNAMIC",
                    tool_ids=step_tool_ids,
                    questions=questions,
                    rationale_codes=selection_rationale + query_rationale,
                )
            )
            used_tool_ids.update(step_tool_ids)
            step_answer = "\n".join(step_answers)
            evaluation = self._evaluator.evaluate(
                plan_skeleton,
                step_answer,
                evidence,
                profile.limits.evidence_min,
                step_id=f"STEP_{step_index}",
                step_index=step_index,
                max_steps=profile.limits.max_steps,
            )
            evaluations.append(evaluation)
            if step_index > 1:
                prev = evaluations[-2]
                coverage_progress = len(evaluation.missing_items) < len(prev.missing_items)
                field_progress = len(evaluation.missing_fields) < len(prev.missing_fields)
                if not coverage_progress and not field_progress:
                    if (
                        evaluation.evidence_count >= profile.limits.evidence_min
                        and evaluation.locator_ok
                    ):
                        evaluation.should_continue = False
            if not evaluation.should_continue:
                break
            if step_index < profile.limits.max_steps:
                current_query = self._build_followup_query(
                    query,
                    step_answer,
                    evaluation.missing_items,
                    evaluation.missing_fields,
                    evaluation.found_fields,
                )

        tool_answers = [
            (tool_id, "\n".join(answers))
            for tool_id, answers in tool_answer_map.items()
            if answers
        ]
        answer = self._executor.compose_multi(query, tool_answers, evidence)
        if not evidence:
            status = "EMPTY"
        elif len(evidence) >= profile.limits.evidence_min:
            status = "SUCCESS"
        else:
            status = "PARTIAL"
        return ExecutionResult(
            answer,
            evidence,
            step_records,
            status,
            evaluations=evaluations,
            step_plans=step_plans,
        )

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

    def _build_multi_queries(
        self,
        original_query: str,
        current_query: str,
        evaluation: EvaluationRecord | None,
    ) -> tuple[List[str], List[str]]:
        gaps = []
        if evaluation:
            gaps = [item.strip() for item in evaluation.missing_items + evaluation.missing_fields if item.strip()]
        if not self._llm or not self._model:
            return [current_query], ["R_MULTI_QUERY_FALLBACK"]
        prompt = (
            "Generate up to 3 short, distinct follow-up questions to retrieve missing information. "
            "Each question must be standalone. Return a JSON array of strings only.\n\n"
            f"Original question: {original_query}\n"
            f"Current query context: {current_query}\n"
            f"Missing items/fields: {', '.join(gaps)}\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
            parsed = json.loads(response)
            if isinstance(parsed, list):
                questions = [str(item).strip() for item in parsed if str(item).strip()]
                if questions:
                    return questions[:3], ["R_MULTI_QUERY_LLM"]
        except Exception:
            pass
        return [current_query], ["R_MULTI_QUERY_FALLBACK"]

    def _select_gap_tools(
        self,
        tools: Dict[str, ToolEntry],
        evaluation: EvaluationRecord,
        candidate_tool_ids: List[str],
        used_tool_ids: set[str],
    ) -> tuple[List[str], List[str]]:
        gaps = [item.strip() for item in evaluation.missing_items + evaluation.missing_fields if item.strip()]
        if not gaps:
            return [], ["R_GAP_NONE"]
        if self._llm and self._model:
            tool_lines = []
            for tool_id in candidate_tool_ids:
                tool = tools.get(tool_id)
                if not tool:
                    continue
                summary = tool.profile_summary or tool.summary or ""
                tool_lines.append(f"- {tool_id} ({tool.pipeline_prefix or 'UNKNOWN'}): {summary}")
            prompt = (
                "Select the tools most likely to fill the missing fields/items. "
                "Return a JSON array of tool_id strings. If none, return [] only.\n\n"
                f"Missing items/fields: {', '.join(gaps)}\n\n"
                f"Candidate tools:\n{chr(10).join(tool_lines)}\n"
            )
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
                parsed = json.loads(response)
                if isinstance(parsed, list):
                    filtered = [tool_id for tool_id in parsed if tool_id in candidate_tool_ids]
                    if filtered:
                        return filtered, ["R_GAP_LLM_SELECTION"]
            except Exception:
                pass

        lowered_gaps = [gap.lower() for gap in gaps]
        matching = []
        for tool_id in candidate_tool_ids:
            tool = tools.get(tool_id)
            if not tool:
                continue
            summary = (tool.profile_summary or tool.summary or "").lower()
            if any(gap in summary for gap in lowered_gaps):
                matching.append(tool_id)
        if matching:
            return matching, ["R_GAP_SUMMARY_MATCH"]
        if used_tool_ids:
            return (
                [tool_id for tool_id in candidate_tool_ids if tool_id not in used_tool_ids]
                or candidate_tool_ids,
                ["R_GAP_UNUSED_FALLBACK"],
            )
        return candidate_tool_ids, ["R_GAP_ALL_CANDIDATES"]

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
