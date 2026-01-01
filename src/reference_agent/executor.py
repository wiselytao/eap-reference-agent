from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from reference_agent.adapters.external_mcp import ExternalMcpClient, ExternalMcpConfig
from reference_agent.adapters.hybridrag import HybridRagClient, HybridRagConfig, build_hybrid_evidence
from reference_agent.composer import AnswerComposer
from reference_agent.models import Evidence, EvaluationRecord, Profile, StepRecord, ToolEntry, ToolHealth
from reference_agent.secrets import resolve_secret
from reference_agent import strategies


@dataclass
class ExecutionResult:
    answer: str
    evidence: List[Evidence]
    steps: List[StepRecord]
    status: str
    evaluations: List[EvaluationRecord] = field(default_factory=list)


class StrategyExecutor:
    def __init__(
        self,
        tools: Dict[str, ToolEntry],
        tool_health: Dict[str, ToolHealth],
        composer: AnswerComposer,
        timeout_seconds: int,
    ) -> None:
        self._tools = tools
        self._tool_health = tool_health
        self._composer = composer
        self._timeout_seconds = timeout_seconds

    def execute(self, strategy_id: str, query: str, profile: Profile) -> ExecutionResult:
        if strategy_id in {strategies.STR_V, strategies.STR_FALLBACK_V}:
            return self._run_single_prefix("VECTOR:", query, profile, strategy_id)
        if strategy_id == strategies.STR_G:
            return self._run_single_prefix("GRAPH:", query, profile, strategy_id)
        if strategy_id == strategies.STR_H:
            return self._run_single_prefix("HYBRID:", query, profile, strategy_id)
        if strategy_id == strategies.STR_HCOT:
            return self._run_single_prefix("HYBRIDCOT:", query, profile, strategy_id)
        if strategy_id == strategies.STR_E_FJ_H:
            return self._run_external_fork_join(query, profile)
        raise ValueError(f"Unsupported strategy: {strategy_id}")

    def call_tool(self, tool: ToolEntry, query: str) -> Tuple[str, List[Evidence], StepRecord]:
        if tool.type == "external_mcp":
            return self._call_external(tool, query)
        prefix = tool.pipeline_prefix or ""
        return self._call_hybrid(tool, prefix, query)

    def compose_external(
        self, query: str, local_answer: str, external_answer: str, evidence: List[Evidence]
    ) -> str:
        return self._composer.compose_external(query, local_answer, external_answer, evidence)

    def evaluate_status(
        self, profile: Profile, tool: ToolEntry, evidence: List[Evidence], required: bool
    ) -> str:
        return self._evaluate_status(profile, tool, evidence, required)

    def evaluate_fork_join_status(
        self, profile: Profile, local_tool: ToolEntry, external_tool: ToolEntry, evidence: List[Evidence]
    ) -> str:
        return self._evaluate_fork_join_status(profile, local_tool, external_tool, evidence)

    def call_fork_join(
        self, profile: Profile, local_tool: ToolEntry, external_tool: ToolEntry, query: str
    ) -> ExecutionResult:
        steps: List[StepRecord] = []
        evidence: List[Evidence] = []
        local_answer = ""
        external_answer = ""
        local_answer, local_evidence, local_step = self._call_hybrid(
            local_tool, local_tool.pipeline_prefix or "", query
        )
        external_answer, external_evidence, external_step = self._call_external(external_tool, query)
        evidence.extend(local_evidence)
        evidence.extend(external_evidence)
        steps.extend([local_step, external_step])
        answer = self.compose_external(query, local_answer, external_answer, evidence)
        status = self.evaluate_fork_join_status(profile, local_tool, external_tool, evidence)
        return ExecutionResult(answer, evidence, steps, status)

    def _run_single_prefix(
        self, prefix: str, query: str, profile: Profile, strategy_id: str
    ) -> ExecutionResult:
        tool = self._select_tool_by_prefix(prefix, profile)
        if not tool:
            return ExecutionResult("", [], [], "FAILED")
        answer, evidence, step = self._call_hybrid(tool, prefix, query)
        status = self._evaluate_status(profile, tool, evidence, required=True)
        return ExecutionResult(answer, evidence, [step], status)

    def _run_external_fork_join(self, query: str, profile: Profile) -> ExecutionResult:
        steps: List[StepRecord] = []
        evidence: List[Evidence] = []
        local_tool = self._select_tool_by_prefix("HYBRID:", profile)
        external_tool = self._select_external_tool(profile)
        local_answer = ""
        external_answer = ""
        local_step: Optional[StepRecord] = None
        external_step: Optional[StepRecord] = None

        if local_tool:
            local_answer, local_evidence, local_step = self._call_hybrid(
                local_tool, "HYBRID:", query
            )
            evidence.extend(local_evidence)

        if external_tool:
            external_answer, external_evidence, external_step = self._call_external(
                external_tool, query
            )
            evidence.extend(external_evidence)

        if local_step:
            steps.append(local_step)
        if external_step:
            steps.append(external_step)

        answer = self._composer.compose_external(query, local_answer, external_answer, evidence)
        status = self._evaluate_fork_join_status(profile, local_tool, external_tool, evidence)
        return ExecutionResult(answer, evidence, steps, status)

    def _select_tool_by_prefix(self, prefix: str, profile: Profile) -> Optional[ToolEntry]:
        for tool_id in profile.enabled_tools:
            tool = self._tools.get(tool_id)
            if tool and tool.pipeline_prefix == prefix:
                return tool
        return None

    def _select_external_tool(self, profile: Profile) -> Optional[ToolEntry]:
        for tool_id in profile.enabled_tools:
            tool = self._tools.get(tool_id)
            if tool and tool.type == "external_mcp":
                return tool
        return None

    def _call_hybrid(self, tool: ToolEntry, prefix: str, query: str) -> Tuple[str, List[Evidence], StepRecord]:
        start = time.perf_counter()
        chat_id = ""
        message_id = ""
        answer = ""
        error_code = None
        try:
            client = HybridRagClient(
                HybridRagConfig(
                    base_url=tool.base_url or "",
                    auth_token=resolve_secret(tool.auth_ref),
                    timeout_seconds=self._timeout_seconds,
                )
            )
            chat_id = client.create_chat()
            answer, message_id = client.send_message(chat_id, f"{prefix} {query}")
            evidence = [build_hybrid_evidence(tool.tool_id, chat_id, message_id, answer)]
        except Exception as exc:
            evidence = []
            error_code = str(exc)
        duration_ms = int((time.perf_counter() - start) * 1000)
        step = StepRecord(
            step_id=f"{tool.tool_id}:{prefix}",
            tool_id=tool.tool_id,
            input_summary={"query": query, "prefix": prefix},
            output_summary={"message_id": message_id, "chat_id": chat_id},
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return answer, evidence, step

    def _call_external(self, tool: ToolEntry, query: str) -> Tuple[str, List[Evidence], StepRecord]:
        start = time.perf_counter()
        error_code = None
        answer = ""
        evidence: List[Evidence] = []
        try:
            client = ExternalMcpClient(
                ExternalMcpConfig(base_url=tool.base_url or "", auth_token=resolve_secret(tool.auth_ref))
            )
            answer, evidence = client.query(tool.tool_id, query)
        except Exception as exc:
            error_code = str(exc)
        duration_ms = int((time.perf_counter() - start) * 1000)
        step = StepRecord(
            step_id=f"{tool.tool_id}:external",
            tool_id=tool.tool_id,
            input_summary={"query": query},
            output_summary={"evidence_count": len(evidence)},
            duration_ms=duration_ms,
            error_code=error_code,
        )
        return answer, evidence, step

    def _evaluate_status(self, profile: Profile, tool: ToolEntry, evidence: List[Evidence], required: bool) -> str:
        evidence_min = profile.limits.evidence_min
        if tool.evidence_contract == "REQUIRED" and len(evidence) < evidence_min:
            return "EMPTY" if required else "PARTIAL"
        if len(evidence) >= evidence_min:
            return "SUCCESS"
        return "EMPTY"

    def _evaluate_fork_join_status(
        self,
        profile: Profile,
        local_tool: Optional[ToolEntry],
        external_tool: Optional[ToolEntry],
        evidence: List[Evidence],
    ) -> str:
        if not evidence:
            return "EMPTY"
        evidence_min = profile.limits.evidence_min
        if len(evidence) >= evidence_min:
            return "SUCCESS" if local_tool and external_tool else "PARTIAL"
        return "PARTIAL"
