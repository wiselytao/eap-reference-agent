from __future__ import annotations

from typing import List, Optional

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.models import Evidence


class AnswerComposer:
    def __init__(self, llm: Optional[LLMClient], model: Optional[str]) -> None:
        self._llm = llm
        self._model = model

    def compose_external(self, query: str, local_answer: str, external_answer: str, evidence: List[Evidence]) -> str:
        if not self._llm or not self._model:
            return self._fallback_compose(local_answer, external_answer)
        prompt = self._build_prompt(query, local_answer, external_answer, evidence)
        return self._llm.generate(self._model, LLMRequest(prompt, 0.2, 512)).strip() or self._fallback_compose(
            local_answer, external_answer
        )

    def _fallback_compose(self, local_answer: str, external_answer: str) -> str:
        return (
            "Local evidence summary:\n"
            f"{local_answer}\n\n"
            "External evidence summary:\n"
            f"{external_answer}"
        )

    def _build_prompt(
        self, query: str, local_answer: str, external_answer: str, evidence: List[Evidence]
    ) -> str:
        citations = "\n".join(
            f"- {item.tool_id}: {item.locator.model_dump()}" for item in evidence
        )
        return (
            "You are composing a final answer from local and external evidence. "
            "Cite evidence by referencing tool_id and locator fields. "
            "If sources conflict, present both without resolving.\n\n"
            f"Question: {query}\n\n"
            f"Local answer: {local_answer}\n\n"
            f"External answer: {external_answer}\n\n"
            f"Evidence list:\n{citations}\n"
        )
