from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from reference_agent.adapters.llm import LLMClient, LLMRequest, build_intent_prompt, parse_intent_response
from reference_agent.models import Profile, RouterBindingReadiness, RouterOutput, ToolEntry, ToolHealth
from reference_agent import strategies


class Router:
    def __init__(self, llm: Optional[LLMClient], model: Optional[str]) -> None:
        self._llm = llm
        self._model = model

    def select_strategy(
        self,
        query: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        tool_health: Dict[str, ToolHealth],
        context: Optional[Dict] = None,
    ) -> RouterOutput:
        context = context or {}
        rationale: List[str] = []
        intent = self._detect_intent(query)
        candidate_strategies = self._candidate_strategies(intent, profile)

        if context.get("need_external") or intent == "external":
            strategy_id = strategies.STR_E_FJ_H
            rationale.append(strategies.R_NEED_EXTERNAL)
        elif intent == "relation":
            strategy_id = strategies.STR_G
            rationale.append(strategies.R_INTENT_RELATION)
        elif intent == "citation":
            strategy_id = strategies.STR_V
            rationale.append(strategies.R_INTENT_CITATION)
        elif intent == "hybridcot" and profile.hybrid_preference.prefer_hybridcot:
            strategy_id = strategies.STR_HCOT
            rationale.append(strategies.R_USE_HYBRIDCOT_PIPELINE)
        else:
            strategy_id = strategies.STR_H
            rationale.append(strategies.R_USE_HYBRID_PIPELINE)

        strategy_id, fallback_rationale = self._apply_profile_and_health(
            strategy_id, profile, tools, tool_health
        )
        rationale.extend(fallback_rationale)
        selected_tools = self._selected_tools(strategy_id, profile, tools)
        health_snapshot = {
            tool_id: {"healthy": health.healthy, "failure_count": health.failure_count}
            for tool_id, health in tool_health.items()
        }

        return RouterOutput(
            strategy_id=strategy_id,
            params={},
            rationale_codes=rationale,
            binding_readiness=RouterBindingReadiness(),
            intent_detected=intent,
            candidate_strategies=candidate_strategies,
            tool_health_snapshot=health_snapshot,
            selected_tools=selected_tools,
        )

    def _detect_intent(self, query: str) -> str:
        if self._llm and self._model:
            try:
                prompt = build_intent_prompt(query)
                text = self._llm.generate(self._model, LLMRequest(prompt, 0.0, 64))
                intent = parse_intent_response(text)
                if intent != "unknown":
                    return intent
            except Exception:
                pass
        lowered = query.lower()
        if any(word in lowered for word in ["external", "outside", "third-party"]):
            return "external"
        if any(word in lowered for word in ["relationship", "graph", "connected", "relation"]):
            return "relation"
        if any(word in lowered for word in ["source", "citation", "document", "reference"]):
            return "citation"
        return "unknown"

    def _apply_profile_and_health(
        self,
        strategy_id: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        tool_health: Dict[str, ToolHealth],
    ) -> Tuple[str, List[str]]:
        rationale: List[str] = []
        allowed = set(profile.allowed_strategies)
        if strategy_id not in allowed:
            rationale.append(strategies.R_PROFILE_RESTRICTED)
            strategy_id = self._fallback_strategy(profile, allowed)

        if not self._strategy_tools_healthy(strategy_id, profile, tools, tool_health):
            rationale.append(strategies.R_TOOL_UNHEALTHY_FALLBACK)
            strategy_id = self._fallback_strategy(profile, allowed)

        return strategy_id, rationale

    def _candidate_strategies(self, intent: str, profile: Profile) -> List[str]:
        candidates: List[str] = []
        if intent == "external":
            candidates.append(strategies.STR_E_FJ_H)
        elif intent == "relation":
            candidates.append(strategies.STR_G)
        elif intent == "citation":
            candidates.append(strategies.STR_V)
        elif intent == "hybridcot":
            candidates.append(strategies.STR_HCOT)
        candidates.append(strategies.STR_H)
        candidates.append(strategies.STR_FALLBACK_V)
        allowed = set(profile.allowed_strategies)
        return [item for item in candidates if item in allowed]

    def _fallback_strategy(self, profile: Profile, allowed: set) -> str:
        for fallback in profile.fallback_order:
            if fallback in allowed:
                return fallback
        if strategies.STR_FALLBACK_V in allowed:
            return strategies.STR_FALLBACK_V
        return next(iter(allowed))

    def _strategy_tools_healthy(
        self,
        strategy_id: str,
        profile: Profile,
        tools: Dict[str, ToolEntry],
        tool_health: Dict[str, ToolHealth],
    ) -> bool:
        required_tool_ids = []
        if strategy_id in {strategies.STR_V, strategies.STR_FALLBACK_V}:
            required_tool_ids = self._tool_ids_by_prefix(profile, tools, "VECTOR:")
        elif strategy_id == strategies.STR_G:
            required_tool_ids = self._tool_ids_by_prefix(profile, tools, "GRAPH:")
        elif strategy_id == strategies.STR_H:
            required_tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRID:")
        elif strategy_id == strategies.STR_HCOT:
            required_tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRIDCOT:")
        elif strategy_id == strategies.STR_E_FJ_H:
            required_tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRID:")
            required_tool_ids += self._external_tool_ids(profile, tools)

        if not required_tool_ids:
            return False
        for tool_id in required_tool_ids:
            health = tool_health.get(tool_id)
            if health and not health.healthy:
                return False
        return True

    def _tool_ids_by_prefix(
        self, profile: Profile, tools: Dict[str, ToolEntry], prefix: str
    ) -> List[str]:
        return [
            tool_id
            for tool_id in profile.enabled_tools
            if tool_id in tools and tools[tool_id].pipeline_prefix == prefix
        ]

    def _selected_tools(
        self, strategy_id: str, profile: Profile, tools: Dict[str, ToolEntry]
    ) -> List[Dict[str, str]]:
        tool_ids: List[str] = []
        if strategy_id in {strategies.STR_V, strategies.STR_FALLBACK_V}:
            tool_ids = self._tool_ids_by_prefix(profile, tools, "VECTOR:")
        elif strategy_id == strategies.STR_G:
            tool_ids = self._tool_ids_by_prefix(profile, tools, "GRAPH:")
        elif strategy_id == strategies.STR_H:
            tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRID:")
        elif strategy_id == strategies.STR_HCOT:
            tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRIDCOT:")
        elif strategy_id == strategies.STR_E_FJ_H:
            tool_ids = self._tool_ids_by_prefix(profile, tools, "HYBRID:")
            tool_ids += self._external_tool_ids(profile, tools)
        selected = []
        for tool_id in tool_ids:
            tool = tools.get(tool_id)
            if not tool:
                continue
            selected.append(
                {
                    "tool_id": tool.tool_id,
                    "type": tool.type,
                    "pipeline_prefix": tool.pipeline_prefix,
                }
            )
        return selected

    def _external_tool_ids(self, profile: Profile, tools: Dict[str, ToolEntry]) -> List[str]:
        return [
            tool_id
            for tool_id in profile.enabled_tools
            if tool_id in tools and tools[tool_id].type == "external_mcp"
        ]
