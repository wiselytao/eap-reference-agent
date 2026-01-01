from __future__ import annotations

import json
from typing import List, Optional

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.bindings import extract_bindings
from reference_agent.models import EvaluationRecord, Evidence, PlanSkeleton


class Evaluator:
    def __init__(self, llm: LLMClient | None, model: str | None) -> None:
        self._llm = llm
        self._model = model

    def evaluate(
        self,
        plan_skeleton: PlanSkeleton,
        answer: str,
        evidence: List[Evidence],
        evidence_min: int,
        step_id: str,
    ) -> EvaluationRecord:
        bindings_found = extract_bindings(answer)
        bindings_missing = [
            item for item in plan_skeleton.required_bindings if item not in bindings_found
        ]
        locator_ok = all(self._locator_ok(item) for item in evidence)
        evidence_count = len(evidence)
        coverage_complete, covered_items, missing_items, notes = self._coverage(
            plan_skeleton, answer
        )
        should_continue = (
            not coverage_complete
            or bool(bindings_missing)
            or evidence_count < evidence_min
            or not locator_ok
        )
        return EvaluationRecord(
            step_id=step_id,
            coverage_complete=coverage_complete,
            covered_items=covered_items,
            missing_items=missing_items,
            bindings_found=bindings_found,
            bindings_missing=bindings_missing,
            evidence_count=evidence_count,
            locator_ok=locator_ok,
            should_continue=should_continue,
            notes=notes,
        )

    def _coverage(
        self, plan_skeleton: PlanSkeleton, answer: str
    ) -> tuple[bool, List[str], List[str], Optional[str]]:
        if not plan_skeleton.answer_blueprint:
            return True, [], [], "No answer blueprint provided."
        if self._llm and self._model:
            prompt = self._coverage_prompt(plan_skeleton.answer_blueprint, answer)
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
                parsed = json.loads(response)
                covered = parsed.get("covered_items", [])
                missing = parsed.get("missing_items", [])
                coverage_complete = len(missing) == 0
                return coverage_complete, covered, missing, parsed.get("notes")
            except Exception:
                pass
        answer_lower = answer.lower()
        covered = [item for item in plan_skeleton.answer_blueprint if item.lower() in answer_lower]
        missing = [item for item in plan_skeleton.answer_blueprint if item.lower() not in answer_lower]
        return len(missing) == 0, covered, missing, "Heuristic coverage check"

    @staticmethod
    def _coverage_prompt(answer_blueprint: List[str], answer: str) -> str:
        return (
            "Evaluate whether the answer covers the required items. Return JSON with keys "
            "covered_items (list), missing_items (list), notes (string).\n\n"
            f"Required items: {answer_blueprint}\n\n"
            f"Answer: {answer}\n"
        )

    @staticmethod
    def _locator_ok(item: Evidence) -> bool:
        locator = item.locator
        return bool(locator.chat_id and locator.messageId) or bool(locator.external_ref)
