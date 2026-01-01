from __future__ import annotations

import uuid
from pathlib import Path
import asyncio
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
    ToolEntry,
    ToolHealth,
    Trace,
    ValidateRequest,
)
from reference_agent.evaluator import Evaluator
from reference_agent.planning import PlanSkeletonBuilder
from reference_agent.profiling import ProfilingStore, RuntimeProber, question_set_for_tool
from reference_agent.tools_fingerprint import tool_fingerprint, tools_md_hash
from reference_agent.v2_executor import BoundedExecutor
from reference_agent.v2_planner import BoundedPlanner
from reference_agent.router import Router
from reference_agent.secrets import resolve_secret
from reference_agent.storage import FileTraceStore
from reference_agent.templates import get_template


class ReferenceAgentService:
    def __init__(self, config_path: Path, tools_path: Path, profiles_dir: Path) -> None:
        self.config = load_config(config_path)
        self.tools_path = tools_path
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
        llm = self._build_llm_client(self.config.llm, self.config.llm.model)
        plan_model = self.config.llm.plan_builder.model or self.config.llm.model
        plan_llm = self._build_llm_client(self.config.llm.plan_builder, plan_model) or llm
        eval_model = self.config.llm.evaluator.model or self.config.llm.model
        eval_llm = self._build_llm_client(self.config.llm.evaluator, eval_model) or llm
        self.plan_builder = PlanSkeletonBuilder(plan_llm, plan_model)
        self.router = Router(plan_llm, plan_model)
        self.bounded_planner = BoundedPlanner(self.router)
        self.evaluator = Evaluator(eval_llm, eval_model)
        self.composer = AnswerComposer(llm, self.config.llm.model)
        self.executor = StrategyExecutor(
            self.tools, self.tool_health, self.composer, self.config.runtime.timeout_seconds
        )
        self.bounded_executor = BoundedExecutor(self.executor, self.evaluator)
        self.trace_store = FileTraceStore(Path(self.config.audit.trace_dir))
        self.eval_llm = eval_llm or llm
        self.profiling_store = ProfilingStore(Path(self.config.profiling_dir))
        self.prober = RuntimeProber(
            max_questions=3,
            timeout_seconds=self.config.profiling_timeout_seconds,
            max_retries=self.config.profiling_max_retries,
            retry_backoff_seconds=self.config.profiling_retry_backoff_seconds,
        )
        self._tools_hash_path = Path(self.config.profiling_dir) / ".tools_md.hash"

    def ask(self, request: AskRequest) -> AskResponse:
        profile = self._get_profile(request.profile_id)
        self._ensure_profiling(profile)
        plan_skeleton = self.plan_builder.build(request.query, profile, self.tools)
        plan_execution = self.bounded_planner.build(request.query, profile, self.tools, request.context)
        router_output = (
            self.router.select_strategy(
                request.query, profile, self.tools, self.tool_health, request.context
            )
            if not request.strategy_id
            else self._manual_strategy(request.strategy_id, profile)
        )
        result = self.bounded_executor.execute(
            plan_execution, plan_skeleton, request.query, profile, self.tools
        )
        evidence = sort_evidence(dedupe_evidence(result.evidence))
        evidence = evidence[: profile.limits.evidence_max]

        final_status = result.status
        answer = result.answer
        if result.evaluations:
            needs_more = any(record.should_continue for record in result.evaluations)
            if needs_more:
                final_status = "PARTIAL" if evidence else "EMPTY"
        if not self._evidence_contract_ok(profile, evidence, result.steps):
            if final_status == "SUCCESS":
                final_status = "EMPTY"
        if profile.answer_policy.must_cite and not evidence:
            final_status = "EMPTY"
            answer = get_template(profile.answer_policy.no_evidence_template, request.query)
        elif final_status == "EMPTY":
            answer = get_template(profile.answer_policy.no_evidence_template, request.query)
        elif final_status == "PARTIAL":
            template = get_template("TPL_PARTIAL_V1", request.query)
            answer = self.composer.compose_partial(request.query, answer, evidence, template)
            if template not in answer:
                answer = f"{template}\n\n{answer}"

        trace = Trace(
            trace_id=str(uuid.uuid4()),
            profile_id=profile.profile_id,
            profile_version=profile.version,
            router=router_output,
            plan_skeleton=plan_skeleton,
            plan_execution=plan_execution,
            steps=result.steps,
            final_status=final_status,
            evidence=evidence,
            evaluations=result.evaluations,
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

    def _ensure_profiling(self, profile: Profile, force: bool = False, tool_ids: list[str] | None = None) -> None:
        changed_tool_ids = self._detect_changed_tools()
        if force:
            changed_tool_ids = set(tool_ids or profile.enabled_tools)
        elif tool_ids:
            changed_tool_ids = set(tool_ids) & set(profile.enabled_tools)
        for tool_id in profile.enabled_tools:
            if changed_tool_ids is not None and tool_id not in changed_tool_ids and not force:
                continue
            tool = self.tools.get(tool_id)
            if not tool:
                continue
            if tool.type == "external_mcp":
                continue
            if not force and changed_tool_ids is None and (tool.summary or tool.profile_summary):
                continue
            record = self.profiling_store.load_latest(tool.tool_id)
            if record and record.profile_summary and not force:
                tool.profile_summary = record.profile_summary
                continue
            questions = question_set_for_tool(tool)
            record = self._run_probe(tool, questions)
            tool.profile_summary = record.profile_summary
            record.tool_hash = tool_fingerprint(tool)
            self.profiling_store.save(record)
        self._write_tools_hash()

    def _run_probe(self, tool: ToolEntry, questions: list[str]):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.prober.probe(tool, questions))
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self.prober.probe(tool, questions), loop)
            return future.result()
        return loop.run_until_complete(self.prober.probe(tool, questions))

    def _detect_changed_tools(self) -> set[str] | None:
        current_hash = self._compute_tools_hash()
        stored_hash = self._read_tools_hash()
        if stored_hash and stored_hash == current_hash:
            return None
        changed = set()
        for tool_id, tool in self.tools.items():
            record = self.profiling_store.load_latest(tool_id)
            fingerprint = tool_fingerprint(tool)
            if not record or record.tool_hash != fingerprint:
                changed.add(tool_id)
        return changed

    def _compute_tools_hash(self) -> str:
        contents = self.tools_path.read_text() if self.tools_path.exists() else ""
        return tools_md_hash(contents)

    def _read_tools_hash(self) -> str | None:
        if not self._tools_hash_path.exists():
            return None
        return self._tools_hash_path.read_text().strip() or None

    def _write_tools_hash(self) -> None:
        current_hash = self._compute_tools_hash()
        self._tools_hash_path.write_text(current_hash)

    def run_profiling(self, profile_id: str, force: bool = False, tool_ids: list[str] | None = None) -> dict:
        profile = self._get_profile(profile_id)
        self._ensure_profiling(profile, force=force, tool_ids=tool_ids)
        return {"status": "ok"}

    @staticmethod
    def _build_llm_client(config, model_name):
        if not config or not model_name:
            return None
        if isinstance(config, dict):
            provider = config.get("provider")
            base_url = config.get("base_url")
            api_key_ref = config.get("api_key_ref")
            extra = config.get("extra", {})
        else:
            provider = config.provider
            base_url = config.base_url
            api_key_ref = config.api_key_ref
            extra = config.extra
        if not provider or not model_name:
            return None
        return LLMClient(
            provider=provider,
            base_url=base_url,
            api_key=resolve_secret(api_key_ref),
            extra=extra,
        )

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
