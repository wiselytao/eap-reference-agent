from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from typing import Callable, Dict, List

from reference_agent.executor import ExecutionResult, StrategyExecutor
from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.tool_routing import prefix_for_tool
from reference_agent.evaluator import Evaluator
from reference_agent.synthesis import CrossRagSynthesizer, SynthesisInput
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
        self._synthesizer = CrossRagSynthesizer(llm, model) if llm and model else None

    def execute(
        self,
        plan: PlanExecution,
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        event_handler: Callable[[dict], None] | None = None,
    ) -> ExecutionResult:
        if plan.template == "T3":
            return self._execute_t3(plan, plan_skeleton, query, profile, tools, event_handler)
        if plan.template == "DYNAMIC":
            return self._execute_dynamic(plan_skeleton, query, profile, tools, event_handler)
        return self._execute_sequential(plan.steps, plan_skeleton, query, profile, tools, event_handler)

    def _execute_t3(
        self,
        plan: PlanExecution,
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        event_handler: Callable[[dict], None] | None,
    ) -> ExecutionResult:
        external_tool = self._get_tool_by_prefix(plan.steps, tools, "EXTERNAL")
        local_tool = self._get_tool_by_prefix(plan.steps, tools, None)
        if not external_tool or not local_tool:
            return ExecutionResult("", [], [], "FAILED")

        self._emit(
            event_handler,
            {
                "type": "step_started",
                "step_index": 1,
                "tool_ids": [external_tool.tool_id, local_tool.tool_id],
                "questions": [query],
            },
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            self._emit(event_handler, {"type": "tool_started", "step_index": 1, "tool_id": external_tool.tool_id})
            self._emit(event_handler, {"type": "tool_started", "step_index": 1, "tool_id": local_tool.tool_id})
            external_future = pool.submit(self._executor.call_tool, external_tool, query)
            local_future = pool.submit(self._executor.call_tool, local_tool, query)
            external_answer, external_evidence, external_step = external_future.result()
            local_answer, local_evidence, local_step = local_future.result()
            self._emit(
                event_handler,
                {
                    "type": "tool_completed",
                    "step_index": 1,
                    "tool_id": external_tool.tool_id,
                    "duration_ms": external_step.duration_ms,
                    "error_code": external_step.error_code,
                },
            )
            self._emit(
                event_handler,
                {
                    "type": "tool_completed",
                    "step_index": 1,
                    "tool_id": local_tool.tool_id,
                    "duration_ms": local_step.duration_ms,
                    "error_code": local_step.error_code,
                },
            )

        evidence = external_evidence + local_evidence
        steps = [external_step, local_step]
        self._emit(event_handler, {"type": "composing_started"})
        answer = self._executor.compose_external(query, local_answer, external_answer, evidence)
        self._emit(event_handler, {"type": "composing_completed"})
        status = self._executor.evaluate_fork_join_status(profile, local_tool, external_tool, evidence)
        self._emit(event_handler, {"type": "step_completed", "step_index": 1})
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
        event_handler: Callable[[dict], None] | None,
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
                (
                    step_tool_ids,
                    selection_rationale,
                    selection_notes,
                    relevance_details,
                ) = self._filter_relevant_tools(
                    query,
                    tools,
                    candidate_tool_ids,
                )
            else:
                step_tool_ids, selection_rationale = self._select_gap_tools(
                    tools,
                    evaluations[-1],
                    candidate_tool_ids,
                    used_tool_ids,
                )
                selection_notes = None
                relevance_details = None
            if not step_tool_ids:
                if step_index == 1:
                    step_plans.append(
                        StepPlan(
                            step_index=step_index,
                            template="DYNAMIC",
                            tool_ids=[],
                            questions=[],
                            rationale_codes=selection_rationale,
                            notes=selection_notes,
                        )
                    )
                    return ExecutionResult(
                        "",
                        [],
                        [],
                        "EMPTY",
                        evaluations=[],
                        step_plans=step_plans,
                    )
                break

            step_answers: List[str] = []
            tool_questions: Dict[str, List[str]] = {}
            split_tool_ids = []
            for tool_id in step_tool_ids:
                tool = tools.get(tool_id)
                if not tool:
                    continue
                if step_index == 1:
                    if self._should_split_queries(tool):
                        split_tool_ids.append(tool_id)
                else:
                    split_tool_ids.append(tool_id)
            if split_tool_ids:
                questions, query_rationale = self._build_multi_queries(
                    query,
                    current_query,
                    evaluations[-1] if evaluations else None,
                )
            else:
                questions = []
                query_rationale = ["R_MULTI_QUERY_TOOL_BYPASS"]
            questions_for_emit: List[str] = []
            total_questions = 0
            for tool_id in step_tool_ids:
                tool = tools.get(tool_id)
                if not tool:
                    continue
                if tool_id in split_tool_ids:
                    if step_index == 1:
                        tool_questions[tool_id] = questions or [current_query]
                    else:
                        merged = "\n".join(questions) if questions else ""
                        if not self._should_split_queries(tool):
                            merged = "\n".join(
                                item for item in [merged, current_query] if item
                            ).strip()
                        if not merged:
                            merged = current_query
                        tool_questions[tool_id] = [merged]
                else:
                    tool_questions[tool_id] = [query]
                total_questions += len(tool_questions[tool_id])
                for question in tool_questions[tool_id]:
                    if question not in questions_for_emit:
                        questions_for_emit.append(question)
            self._emit(
                event_handler,
                {
                    "type": "step_started",
                    "step_index": step_index,
                    "tool_ids": step_tool_ids,
                    "question_count": total_questions,
                    "questions": questions_for_emit,
                    "selection_rationale": selection_rationale,
                    "selection_notes": selection_notes,
                    "relevance_details": relevance_details,
                },
            )
            max_workers = min(12, total_questions) or 1
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}
                for tool_id in step_tool_ids:
                    tool = tools.get(tool_id)
                    if not tool:
                        continue
                    for q_index, question in enumerate(tool_questions.get(tool_id, []), start=1):
                        self._emit(
                            event_handler,
                            {
                                "type": "tool_started",
                                "step_index": step_index,
                                "tool_id": tool_id,
                                "query_index": q_index,
                            },
                        )
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
                    self._emit(
                        event_handler,
                        {
                            "type": "tool_completed",
                            "step_index": step_index,
                            "tool_id": tool_id,
                            "query_index": q_index,
                            "duration_ms": step_record.duration_ms,
                            "error_code": step_record.error_code,
                        },
                    )

            step_plans.append(
                StepPlan(
                    step_index=step_index,
                    template="DYNAMIC",
                    tool_ids=step_tool_ids,
                    questions=questions,
                    rationale_codes=selection_rationale + query_rationale,
                    notes=selection_notes,
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
            self._emit(event_handler, {"type": "step_completed", "step_index": step_index})
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
        synthesis = None
        if self._synthesizer:
            synthesis = self._synthesizer.synthesize(
                SynthesisInput(
                    query=query,
                    tool_answers=tool_answers,
                    evidence=evidence,
                    plan_skeleton=plan_skeleton,
                )
            )
        if synthesis and synthesis.groups:
            self._emit(event_handler, {"type": "composing_started"})
            answer = self._executor.compose_synthesis(query, synthesis, evidence)
            self._emit(event_handler, {"type": "composing_completed"})
        else:
            self._emit(event_handler, {"type": "composing_started"})
            answer = self._executor.compose_multi(query, tool_answers, evidence)
            self._emit(event_handler, {"type": "composing_completed"})
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
            synthesis=synthesis,
        )

    def _execute_sequential(
        self,
        steps: List[PlanStep],
        plan_skeleton: PlanSkeleton,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        event_handler: Callable[[dict], None] | None,
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
            self._emit(
                event_handler,
                {
                    "type": "step_started",
                    "step_index": idx,
                    "tool_ids": [tool.tool_id],
                    "questions": [current_query],
                },
            )
            self._emit(event_handler, {"type": "tool_started", "step_index": idx, "tool_id": tool.tool_id})
            answer, step_evidence, step_record = self._executor.call_tool(tool, current_query)
            evidence.extend(step_evidence)
            step_records.append(step_record)
            last_tool = tool
            self._emit(
                event_handler,
                {
                    "type": "tool_completed",
                    "step_index": idx,
                    "tool_id": tool.tool_id,
                    "duration_ms": step_record.duration_ms,
                    "error_code": step_record.error_code,
                },
            )

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
            self._emit(event_handler, {"type": "step_completed", "step_index": idx})
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
        followup_context = self._extract_followup_context(answer)
        summary = followup_context.get("summary") or self._truncate(answer, 300)
        lines = [original_query]
        if summary:
            lines.append(f"Known summary: {summary}")
        if followup_context:
            context_json = json.dumps(followup_context, ensure_ascii=True, separators=(",", ":"))
            lines.append(f"Follow-up context (JSON): {context_json}")
        if missing_items:
            lines.append(f"Missing items: {', '.join(missing_items)}")
        if missing_fields:
            lines.append(f"Missing fields: {', '.join(missing_fields)}")
        if found_fields:
            lines.append(f"Identifiers: {', '.join(found_fields)}")
        draft = "\n".join(lines)
        return draft

    @staticmethod
    def _should_split_queries(tool: ToolEntry) -> bool:
        if tool.type == "external_mcp":
            return True
        return prefix_for_tool(tool) == "VECTOR:"

    def _extract_followup_context(self, answer: str) -> dict:
        base = {
            "summary": self._truncate(answer, 300),
            "key_entities": [],
            "key_fields": [],
            "prereq_facts": [],
        }
        if not self._llm or not self._model:
            return base
        prompt = (
            "Extract a compact follow-up context from the answer. "
            "Return JSON only with keys: summary (string), key_entities (list), "
            "key_fields (list), prereq_facts (list). "
            "Use only information present in the answer. Do not introduce new entities. "
            "Keep lists concise (0-5 items).\n\n"
            f"Answer: {answer}\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
            parsed = json.loads(response)
            if not isinstance(parsed, dict):
                return base
            summary = str(parsed.get("summary") or "").strip() or base["summary"]
            key_entities = [str(item).strip() for item in parsed.get("key_entities", []) if str(item).strip()]
            key_fields = [str(item).strip() for item in parsed.get("key_fields", []) if str(item).strip()]
            prereq_facts = [str(item).strip() for item in parsed.get("prereq_facts", []) if str(item).strip()]
            return {
                "summary": summary,
                "key_entities": key_entities[:5],
                "key_fields": key_fields[:5],
                "prereq_facts": prereq_facts[:5],
            }
        except Exception:
            return base

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
            "Generate up to 3 short, distinct follow-up questions that directly target the Missing items/fields. "
            "Each question must be standalone, in the same language as the Original question, and must include at "
            "least one Missing item/field term (verbatim when possible). Do not introduce new entities or "
            "constraints not implied by the Original question or Missing items/fields. "
            "Output JSON only: return a JSON array of strings with no extra text. "
            "If Missing items/fields is empty, return a JSON array containing the Current query context only.\n\n"
            f"Original question: {original_query}\n"
            f"Current query context (may include JSON follow-up context): {current_query}\n"
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

    def _filter_relevant_tools(
        self,
        query: str,
        tools: Dict[str, ToolEntry],
        candidate_tool_ids: List[str],
    ) -> tuple[List[str], List[str], str | None, list[dict[str, str]] | None]:
        if not self._llm or not self._model:
            return candidate_tool_ids, ["R_STEP1_RELEVANCE_FALLBACK"], None, None

        def assess(tool_id: str) -> tuple[str, str, str]:
            tool = tools.get(tool_id)
            if tool and prefix_for_tool(tool) == "VECTOR:" and tool.l0_profile:
                return self._assess_l0_relevance(tool, query)
            summary = ""
            if tool:
                summary = tool.profile_summary or tool.summary or ""
            if not summary:
                return tool_id, "uncertain", "no_summary"
            prompt = (
                "Decide whether the tool's profiling summary is relevant to answering the user question. "
                "Be recall-friendly: only mark not_relevant if it is clearly unrelated. "
                "Return JSON with keys: relevance (relevant/uncertain/not_relevant), reason (string).\n\n"
                f"Question: {query}\n\n"
                f"Tool summary: {summary}\n"
            )
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 128))
                parsed = json.loads(response)
                relevance = str(parsed.get("relevance") or "").strip().lower()
                reason = str(parsed.get("reason") or "").strip()
                if relevance not in {"relevant", "uncertain", "not_relevant"}:
                    relevance = "uncertain"
                return tool_id, relevance, reason
            except Exception:
                return tool_id, "uncertain", "llm_error"

        results = []
        with ThreadPoolExecutor(max_workers=min(8, len(candidate_tool_ids)) or 1) as pool:
            futures = {tool_id: pool.submit(assess, tool_id) for tool_id in candidate_tool_ids}
            for tool_id in candidate_tool_ids:
                results.append(futures[tool_id].result())

        relevant_tools = [
            tool_id for tool_id, relevance, _ in results if relevance in {"relevant", "uncertain"}
        ]
        relevance_details = [
            {"tool_id": tool_id, "relevance": relevance, "reason": reason}
            for tool_id, relevance, reason in results
        ]
        notes = "; ".join(
            f"{tool_id}: {relevance}"
            + (f" ({reason})" if reason else "")
            for tool_id, relevance, reason in results
        )
        if not relevant_tools:
            return [], ["R_STEP1_RELEVANCE_EMPTY_STOP"], notes, relevance_details
        return relevant_tools, ["R_STEP1_LLM_RELEVANCE_SOFT"], notes, relevance_details

    def _assess_l0_relevance(self, tool: ToolEntry, query: str) -> tuple[str, str, str]:
        if not self._llm or not self._model:
            return tool.tool_id, "uncertain", "llm_unavailable"
        l0_json = json.dumps(tool.l0_profile, ensure_ascii=True, separators=(",", ":"))
        prompt = (
            "You are a Layer-0 Relevance Judge for a Vector RAG system.\n\n"
            "Your task is to decide whether a USER_QUESTION should be considered relevant to a Vector RAG,\n"
            "based ONLY on the provided L0_PROFILE information.\n"
            "The L0_PROFILE represents a coarse \"world-domain fingerprint\" derived from probing questions.\n"
            "It is NOT a complete dataset description.\n\n"
            "IMPORTANT PRINCIPLES:\n"
            "1) Recall-first: Do NOT reject unless the mismatch is extremely obvious.\n"
            "2) Only reject when the USER_QUESTION is clearly from a completely different world/domain.\n"
            "3) Uncertainty must NOT cause rejection.\n"
            "4) Do NOT assume knowledge beyond what is explicitly present in the L0_PROFILE.\n"
            "5) You are judging world/domain overlap, NOT answerability or semantic similarity.\n\n"
            "Inputs:\n"
            "- L0_PROFILE:\n"
            f"{l0_json}\n\n"
            "- USER_QUESTION:\n"
            f"{query}\n\n"
            "Decision logic (strict):\n"
            "- If the USER_QUESTION clearly belongs to a completely different world\n"
            "  (e.g., entertainment awards vs enterprise operations, sports matches vs internal systems),\n"
            "  return CLEARLY_IRRELEVANT.\n"
            "- If there is any plausible overlap in world, task style, actions, or structures,\n"
            "  return RELEVANT.\n"
            "- If you cannot confidently decide, return UNCERTAIN (this still means \"allow\").\n\n"
            "Output ONLY the following JSON (no additional text):\n\n"
            "{\n"
            "  \"verdict\": \"RELEVANT | UNCERTAIN | CLEARLY_IRRELEVANT\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"reason\": \"One-sentence explanation referencing specific L0 signals or the lack thereof.\",\n"
            "  \"matched_signals\": {\n"
            "    \"actions\": [],\n"
            "    \"relations\": [],\n"
            "    \"task_types\": [],\n"
            "    \"artifacts\": [],\n"
            "    \"state_time\": []\n"
            "  },\n"
            "  \"decision_rule_applied\": \"only reject on world-level mismatch\"\n"
            "}\n\n"
            "Confidence guidance:\n"
            "- Use high confidence (>=0.8) ONLY when the mismatch is unmistakable.\n"
            "- Use medium confidence (0.4-0.7) when relevant.\n"
            "- Use low confidence (<0.4) when uncertain.\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
            parsed = json.loads(response)
            verdict = str(parsed.get("verdict") or "").strip().upper()
            reason = str(parsed.get("reason") or "").strip()
            if verdict == "CLEARLY_IRRELEVANT":
                return tool.tool_id, "not_relevant", reason
            if verdict == "RELEVANT":
                return tool.tool_id, "relevant", reason
            return tool.tool_id, "uncertain", reason
        except Exception:
            return tool.tool_id, "uncertain", "llm_error"

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
                tool_lines.append(f"- {tool_id} ({prefix_for_tool(tool) or 'UNKNOWN'}): {summary}")
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

    @staticmethod
    def _emit(handler: Callable[[dict], None] | None, payload: dict) -> None:
        if handler:
            handler(payload)
