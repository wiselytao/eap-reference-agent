from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, Optional

from reference_agent.adapters.llm import LLMClient
from reference_agent.composer import AnswerComposer
from reference_agent.config import load_config, load_profiles, load_tools_md
from reference_agent.evidence import dedupe_evidence, sort_evidence
from reference_agent.executor import StrategyExecutor
from reference_agent.models import (
    AskRequest,
    AskResponse,
    CapabilitiesResponse,
    Evidence,
    Profile,
    ToolHealth,
    Trace,
    ValidateRequest,
)
from reference_agent.router import Router
from reference_agent.secrets import resolve_secret
from reference_agent.storage import FileTraceStore
from reference_agent.templates import get_template


class ReferenceAgentService:
    def __init__(self, config_path: Path, tools_path: Path, profiles_dir: Path) -> None:
        self.config = load_config(config_path)
        self.tools = {tool.tool_id: tool for tool in load_tools_md(tools_path)}
        self.profiles = load_profiles(profiles_dir)
        env_tool_ids = [
            tool_id
            for tool_id, tool in self.tools.items()
            if tool.auth_ref and tool.auth_ref.startswith("TOOL_")
        ]
        for profile in self.profiles.values():
            if "*" in profile.enabled_tools:
                profile.enabled_tools = env_tool_ids or list(self.tools.keys())
        self.tool_health: Dict[str, ToolHealth] = {
            tool_id: ToolHealth(tool_id=tool_id) for tool_id in self.tools
        }
        llm = LLMClient(
            provider=self.config.llm.provider,
            base_url=self.config.llm.base_url,
            api_key=resolve_secret(self.config.llm.api_key_ref),
            extra=self.config.llm.extra,
        )
        self.router = Router(llm, self.config.llm.model)
        self.composer = AnswerComposer(llm, self.config.llm.model)
        self.executor = StrategyExecutor(
            self.tools, self.tool_health, self.composer, self.config.runtime.timeout_seconds
        )
        self.trace_store = FileTraceStore(Path(self.config.audit.trace_dir))

    def ask(self, request: AskRequest) -> AskResponse:
        profile = self._get_profile(request.profile_id)
        router_output = (
            self.router.select_strategy(
                request.query, profile, self.tools, self.tool_health, request.context
            )
            if not request.strategy_id
            else self._manual_strategy(request.strategy_id, profile)
        )
        result = self.executor.execute(router_output.strategy_id, request.query, profile)
        evidence = sort_evidence(dedupe_evidence(result.evidence))
        evidence = evidence[: profile.limits.evidence_max]

        final_status = result.status
        answer = result.answer
        if not self._evidence_contract_ok(profile, evidence, result.steps):
            if final_status == "SUCCESS":
                final_status = "EMPTY"
        if profile.answer_policy.must_cite and not evidence:
            final_status = "EMPTY"
            answer = get_template(profile.answer_policy.no_evidence_template, request.query)
        elif final_status == "EMPTY":
            answer = get_template(profile.answer_policy.no_evidence_template, request.query)
        elif final_status == "PARTIAL":
            answer = get_template("TPL_PARTIAL_V1", request.query) + "\n\n" + answer

        trace = Trace(
            trace_id=str(uuid.uuid4()),
            profile_id=profile.profile_id,
            profile_version=profile.version,
            router=router_output,
            steps=result.steps,
            final_status=final_status,
            evidence=evidence,
            user_visible_notes=[],
        )
        self.trace_store.save(trace)
        self._update_health(result.steps)
        return AskResponse(
            answer=answer,
            evidence=evidence,
            trace_id=trace.trace_id,
            status=final_status,
        )

    def get_trace(self, trace_id: str) -> Optional[Trace]:
        return self.trace_store.load(trace_id)

    def validate(self, request: ValidateRequest) -> Dict:
        if request.trace_id:
            trace = self.get_trace(request.trace_id)
            if not trace:
                return {"status": "not_found"}
            return {"status": "ok", "evidence": [e.model_dump() for e in trace.evidence]}
        if request.evidence_ref:
            return {"status": "ok", "locator": request.evidence_ref.model_dump()}
        return {"status": "invalid_request"}

    def capabilities(self, profile_id: str) -> CapabilitiesResponse:
        profile = self._get_profile(profile_id)
        return CapabilitiesResponse(
            profile_id=profile.profile_id,
            allowed_strategies=profile.allowed_strategies,
            limits=profile.limits,
            enabled_tools=profile.enabled_tools,
        )

    def _get_profile(self, profile_id: str) -> Profile:
        if self.config.security.allowed_profiles and profile_id not in self.config.security.allowed_profiles:
            raise ValueError("Profile not allowed")
        profile = self.profiles.get(profile_id)
        if not profile:
            raise ValueError("Profile not found")
        return profile

    def _manual_strategy(self, strategy_id: str, profile: Profile):
        if strategy_id not in profile.allowed_strategies:
            raise ValueError("Strategy not allowed by profile")
        router_output = self.router.select_strategy("", profile, self.tools, self.tool_health)
        router_output.strategy_id = strategy_id
        router_output.rationale_codes.append("R_PROFILE_RESTRICTED")
        router_output.selected_tools = self.router._selected_tools(strategy_id, profile, self.tools)
        return router_output

    def _update_health(self, steps):
        for step in steps:
            if not step.tool_id:
                continue
            health = self.tool_health.get(step.tool_id)
            if not health:
                continue
            if step.error_code:
                health.failure_count += 1
                if health.failure_count >= 3:
                    health.healthy = False
            else:
                health.failure_count = 0
                health.healthy = True

    def _evidence_contract_ok(
        self, profile: Profile, evidence: list[Evidence], steps
    ) -> bool:
        used_tool_ids = {step.tool_id for step in steps if step.tool_id}
        required_tools = {
            tool_id: tool
            for tool_id, tool in self.tools.items()
            if tool.evidence_contract == "REQUIRED"
            and tool_id in profile.enabled_tools
            and tool_id in used_tool_ids
        }
        if not required_tools:
            return True
        evidence_min = profile.limits.evidence_min
        for tool_id in required_tools:
            items = [item for item in evidence if item.tool_id == tool_id]
            if len(items) < evidence_min:
                return False
            if not all(self._locator_ok(item) for item in items):
                return False
        return True

    @staticmethod
    def _locator_ok(item: Evidence) -> bool:
        locator = item.locator
        return bool(locator.chat_id and locator.messageId) or bool(locator.external_ref)
