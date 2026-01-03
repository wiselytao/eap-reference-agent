from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.models import Claim, ClaimGroup, PlanSkeleton, SynthesisResult


@dataclass
class SynthesisInput:
    query: str
    tool_answers: List[Tuple[str, str]]
    evidence: List[Evidence]
    plan_skeleton: PlanSkeleton


class CrossRagSynthesizer:
    def __init__(self, llm: Optional[LLMClient], model: Optional[str]) -> None:
        self._llm = llm
        self._model = model

    def synthesize(self, data: SynthesisInput) -> Optional[SynthesisResult]:
        if not self._llm or not self._model:
            return SynthesisResult(notes="LLM not configured for synthesis.")
        claims = self._normalize_claims(data.tool_answers)
        if not claims:
            return SynthesisResult(notes="No claims extracted from tool answers.")
        groups = self._align_claims(claims)
        if not groups:
            return SynthesisResult(claims=claims, notes="No aligned claim groups returned by LLM.")
        groups = self._add_group_metadata(groups, claims)
        groups = self._detect_conflicts(groups, claims)
        mappings = self._map_to_blueprint(data.plan_skeleton, groups, claims)
        intersection_ids = [group.canonical_id for group in groups if group.intersection]
        conflict_ids = [group.canonical_id for group in groups if group.conflict]
        return SynthesisResult(
            claims=claims,
            groups=groups,
            intersection_ids=intersection_ids,
            conflict_ids=conflict_ids,
            mappings=mappings,
        )

    def _normalize_claims(self, tool_answers: List[Tuple[str, str]]) -> List[Claim]:
        claims: List[Claim] = []
        for tool_id, answer in tool_answers:
            prompt = (
                "Extract atomic claims from the answer. Each claim should be a concise triple "
                "(subject, predicate, object) with optional qualifiers. "
                "Return JSON array of objects with keys: subject, predicate, object, qualifiers.\n\n"
                f"Answer:\n{answer}\n"
            )
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 512))
                parsed = json.loads(response)
                if not isinstance(parsed, list):
                    continue
                for idx, item in enumerate(parsed):
                    subject = str(item.get("subject") or "").strip()
                    predicate = str(item.get("predicate") or "").strip()
                    obj = str(item.get("object") or "").strip()
                    qualifiers = item.get("qualifiers") or {}
                    if not subject or not predicate or not obj:
                        continue
                    claims.append(
                        Claim(
                            claim_id=f"{tool_id}:{idx}",
                            tool_id=tool_id,
                            subject=subject,
                            predicate=predicate,
                            object=obj,
                            qualifiers=qualifiers if isinstance(qualifiers, dict) else {},
                        )
                    )
            except Exception:
                continue
        return claims

    def _align_claims(self, claims: List[Claim]) -> List[ClaimGroup]:
        payload = [
            {
                "claim_id": claim.claim_id,
                "subject": claim.subject,
                "predicate": claim.predicate,
                "object": claim.object,
            }
            for claim in claims
        ]
        prompt = (
            "Group claims that refer to the same underlying fact. "
            "Return JSON array of objects with keys: canonical_id, label, claim_ids.\n\n"
            f"Claims:\n{payload}\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 512))
            parsed = json.loads(response)
            groups: List[ClaimGroup] = []
            if isinstance(parsed, list):
                for item in parsed:
                    canonical_id = str(item.get("canonical_id") or "").strip()
                    label = str(item.get("label") or "").strip()
                    claim_ids = item.get("claim_ids") or []
                    if not canonical_id or not label or not claim_ids:
                        continue
                    groups.append(
                        ClaimGroup(
                            canonical_id=canonical_id,
                            label=label,
                            claim_ids=[str(cid) for cid in claim_ids],
                        )
                    )
            return groups
        except Exception:
            return []

    @staticmethod
    def _add_group_metadata(groups: List[ClaimGroup], claims: List[Claim]) -> List[ClaimGroup]:
        claim_map = {claim.claim_id: claim for claim in claims}
        for group in groups:
            tool_ids = []
            for claim_id in group.claim_ids:
                claim = claim_map.get(claim_id)
                if claim:
                    tool_ids.append(claim.tool_id)
            unique_tools = sorted(set(tool_ids))
            group.tool_ids = unique_tools
            group.intersection = len(unique_tools) >= 2
        return groups

    def _detect_conflicts(self, groups: List[ClaimGroup], claims: List[Claim]) -> List[ClaimGroup]:
        claim_map = {claim.claim_id: claim for claim in claims}
        for group in groups:
            items = [claim_map.get(cid) for cid in group.claim_ids]
            objects = [item.object for item in items if item]
            if len(set(objects)) <= 1:
                continue
            prompt = (
                "Determine whether the following claims are in conflict. "
                "Return JSON with keys: conflict (true/false), reason (string).\n\n"
                f"Claims: {objects}\n"
            )
            try:
                response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 128))
                parsed = json.loads(response)
                conflict = bool(parsed.get("conflict"))
                reason = str(parsed.get("reason") or "").strip()
                group.conflict = conflict
                group.conflict_notes = reason
            except Exception:
                continue
        return groups

    def _map_to_blueprint(
        self, plan_skeleton: PlanSkeleton, groups: List[ClaimGroup], claims: List[Claim]
    ) -> Dict[str, List[str]]:
        items = plan_skeleton.answer_blueprint + plan_skeleton.required_fields
        if not items:
            return {}
        payload = [
            {"canonical_id": group.canonical_id, "label": group.label}
            for group in groups
        ]
        prompt = (
            "Map each required item to the most relevant canonical_ids. "
            "Return JSON object where keys are items and values are lists of canonical_ids.\n\n"
            f"Required items: {items}\n\n"
            f"Canonical groups: {payload}\n"
        )
        try:
            response = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 256))
            parsed = json.loads(response)
            if isinstance(parsed, dict):
                return {
                    str(key): [str(cid) for cid in value] for key, value in parsed.items() if value
                }
        except Exception:
            return {}
        return {}
