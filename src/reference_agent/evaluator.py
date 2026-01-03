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
        step_index: int,
        max_steps: int,
    ) -> EvaluationRecord:
        bindings_found = extract_bindings(answer)
        required_fields = plan_skeleton.required_fields
        if self._llm and self._model and required_fields:
            fields_found = set(self._semantic_field_mapping(required_fields, answer))
        else:
            fields_found = set(
                item for item in required_fields if item.lower() in (answer or "").lower()
            )
        missing_fields = [item for item in required_fields if item not in fields_found]
        locator_ok = all(self._locator_ok(item) for item in evidence)
        evidence_count = len(evidence)
        coverage_complete, covered_items, missing_items, notes = self._coverage(
            plan_skeleton, answer
        )
        should_continue, stop_reasons = self._should_continue(
            plan_skeleton.stop_conditions,
            coverage_complete,
            missing_fields,
            evidence_count,
            evidence_min,
            locator_ok,
            step_index,
            max_steps,
        )
        return EvaluationRecord(
            step_id=step_id,
            coverage_complete=coverage_complete,
            covered_items=covered_items,
            missing_items=missing_items,
            found_fields=sorted(fields_found),
            missing_fields=missing_fields,
            evidence_count=evidence_count,
            locator_ok=locator_ok,
            should_continue=should_continue,
            notes=notes,
            stop_reasons=stop_reasons,
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

    def _semantic_field_mapping(self, required_fields: List[str], answer: str) -> List[str]:
        prompt = (
            "Given the required field types, determine which are supported by the answer. "
            "Return JSON with key 'found_fields' as a list chosen only from the required_fields.\n\n"
            f"required_fields: {required_fields}\n\n"
            f"answer: {answer}\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 128))
            data = json.loads(response)
            found = data.get("found_fields", [])
            return [item for item in found if item in required_fields]
        except Exception:
            return []

    @staticmethod
    def _should_continue(
        stop_conditions: List[str],
        coverage_complete: bool,
        bindings_missing: List[str],
        evidence_count: int,
        evidence_min: int,
        locator_ok: bool,
        step_index: int,
        max_steps: int,
    ) -> tuple[bool, List[str]]:
        reasons: List[str] = []
        if step_index >= max_steps:
            reasons.append("STOP_MAX_STEPS")
            return False, reasons
        normalized = " ".join(stop_conditions).lower()
        if "coverage" in normalized and coverage_complete:
            reasons.append("STOP_COVERAGE_COMPLETE")
            return False, reasons
        if ("binding" in normalized or "identifier" in normalized) and not bindings_missing:
            reasons.append("STOP_BINDINGS_MET")
            return False, reasons
        if "evidence" in normalized and evidence_count >= evidence_min and locator_ok:
            if coverage_complete and not bindings_missing:
                reasons.append("STOP_EVIDENCE_MIN_MET")
                return False, reasons
        if "step_budget" in normalized or "step budget" in normalized:
            if step_index >= max_steps:
                reasons.append("STOP_STEP_BUDGET")
                return False, reasons
        # default: continue if any core requirement is missing
        should_continue = (
            not coverage_complete
            or bool(bindings_missing)
            or evidence_count < evidence_min
            or not locator_ok
        )
        if not should_continue:
            reasons.append("STOP_NO_PROGRESS")
        return should_continue, reasons

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
