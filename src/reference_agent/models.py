from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

ToolType = Literal["hybridrag_pipeline", "external_mcp"]
AdapterType = Literal["hybridrag_chat_api_v1", "mcp"]
EvidenceContract = Literal["REQUIRED", "OPTIONAL", "NONE"]
EvidenceSourceType = Literal[
    "vector_chunk",
    "graph_node",
    "graph_edge",
    "sql_row",
    "sql_metric",
    "external_chunk",
    "hybrid_answer",
]
FinalStatus = Literal["SUCCESS", "PARTIAL", "EMPTY", "FAILED"]


class ToolConstraints(BaseModel):
    timeout_class: Optional[str] = None
    topK: Optional[int] = None
    max_hops: Optional[int] = None
    max_rows: Optional[int] = None


class ToolEntry(BaseModel):
    tool_id: str
    type: ToolType
    project_id: str
    adapter: AdapterType
    base_url: Optional[str] = None
    auth_ref: Optional[str] = None
    pipeline_prefix: Optional[str] = None
    summary: Optional[str] = None
    profile_summary: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    constraints: ToolConstraints = Field(default_factory=ToolConstraints)
    evidence_contract: EvidenceContract = "OPTIONAL"
    evidence_locator_policy: Optional[str] = None


class ProfileLimits(BaseModel):
    max_steps: int = 3
    evidence_min: int = 1
    evidence_max: int = 12
    token_max: Optional[int] = None
    per_tool: Dict[str, ToolConstraints] = Field(default_factory=dict)


class AnswerPolicy(BaseModel):
    must_cite: bool = True
    conflict_show: bool = True
    no_evidence_template: str = "TPL_NO_EVIDENCE_V1"


class HybridPreference(BaseModel):
    prefer_hybrid_pipeline: bool = True
    prefer_hybridcot: bool = False
    hybridcot_allowlist_intents: List[str] = Field(default_factory=list)


class QualityGate(BaseModel):
    require_evidence_contract: bool = True
    enable_quality_rescue: bool = False


class Profile(BaseModel):
    profile_id: str
    version: str
    description: Optional[str] = None
    enabled_tools: List[str]
    allowed_strategies: List[str]
    limits: ProfileLimits = Field(default_factory=ProfileLimits)
    fallback_order: List[str] = Field(default_factory=list)
    answer_policy: AnswerPolicy = Field(default_factory=AnswerPolicy)
    hybrid_preference: HybridPreference = Field(default_factory=HybridPreference)
    quality_gate: QualityGate = Field(default_factory=QualityGate)


class EvidenceLocator(BaseModel):
    chat_id: Optional[str] = None
    messageId: Optional[str] = None
    external_ref: Optional[str] = None


class Evidence(BaseModel):
    source_type: EvidenceSourceType
    tool_id: str
    source_id: str
    locator: EvidenceLocator
    snippet: Optional[str] = None
    retrieval_meta: Dict[str, Any] = Field(default_factory=dict)
    confidence: Optional[float] = None


class RouterBindingReadiness(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    required_fields: List[str] = Field(default_factory=list, alias="required_bindings")
    provided_fields: List[str] = Field(default_factory=list, alias="provided_bindings")
    missing_fields: List[str] = Field(default_factory=list, alias="missing_bindings")
    dependency_required: bool = False
    resolution_policy: Optional[str] = None


class RouterOutput(BaseModel):
    strategy_id: str
    params: Dict[str, Any] = Field(default_factory=dict)
    rationale_codes: List[str] = Field(default_factory=list)
    binding_readiness: RouterBindingReadiness = Field(default_factory=RouterBindingReadiness)
    intent_detected: Optional[str] = None
    candidate_strategies: List[str] = Field(default_factory=list)
    tool_health_snapshot: Dict[str, Any] = Field(default_factory=dict)
    selected_tools: List[Dict[str, Any]] = Field(default_factory=list)


class StepRecord(BaseModel):
    step_id: str
    tool_id: Optional[str] = None
    input_summary: Dict[str, Any] = Field(default_factory=dict)
    output_summary: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: Optional[int] = None
    error_code: Optional[str] = None
    degraded: bool = False


class EvaluationRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    step_id: str
    coverage_complete: bool
    covered_items: List[str] = Field(default_factory=list)
    missing_items: List[str] = Field(default_factory=list)
    found_fields: List[str] = Field(default_factory=list, alias="bindings_found")
    missing_fields: List[str] = Field(default_factory=list, alias="bindings_missing")
    evidence_count: int = 0
    locator_ok: bool = False
    should_continue: bool = False
    notes: Optional[str] = None
    stop_reasons: List[str] = Field(default_factory=list)


class StepPlan(BaseModel):
    step_index: int
    template: str
    tool_ids: List[str] = Field(default_factory=list)
    questions: List[str] = Field(default_factory=list)
    rationale_codes: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    tool_id: str
    subject: str
    predicate: str
    object: str
    qualifiers: Dict[str, Any] = Field(default_factory=dict)


class ClaimGroup(BaseModel):
    canonical_id: str
    label: str
    claim_ids: List[str] = Field(default_factory=list)
    tool_ids: List[str] = Field(default_factory=list)
    intersection: bool = False
    conflict: bool = False
    conflict_notes: Optional[str] = None


class SynthesisResult(BaseModel):
    claims: List[Claim] = Field(default_factory=list)
    groups: List[ClaimGroup] = Field(default_factory=list)
    intersection_ids: List[str] = Field(default_factory=list)
    conflict_ids: List[str] = Field(default_factory=list)
    mappings: Dict[str, List[str]] = Field(default_factory=dict)
    notes: Optional[str] = None


class Trace(BaseModel):
    trace_id: str
    profile_id: str
    profile_version: str
    router: RouterOutput
    steps: List[StepRecord] = Field(default_factory=list)
    final_status: FinalStatus
    evidence: List[Evidence] = Field(default_factory=list)
    user_visible_notes: List[str] = Field(default_factory=list)
    plan_skeleton: Optional["PlanSkeleton"] = None
    plan_execution: Optional["PlanExecution"] = None
    evaluations: List[EvaluationRecord] = Field(default_factory=list)
    queried_tools_by_step: List[List[str]] = Field(default_factory=list)
    step_plans: List[StepPlan] = Field(default_factory=list)
    synthesis: Optional[SynthesisResult] = None
    final_status_reasons: List[str] = Field(default_factory=list)


class PlanSkeleton(BaseModel):
    answer_blueprint: List[str]
    required_fields: List[str]
    candidate_tools: List[str]
    constraints: Dict[str, Any] = Field(default_factory=dict)
    stop_conditions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    tool_selection_notes: List[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    step_id: str
    template: str
    tool_id: Optional[str] = None
    pipeline_prefix: Optional[str] = None
    input_hint: Optional[str] = None
    bindings_used: List[str] = Field(default_factory=list)


class PlanExecution(BaseModel):
    template: str
    steps: List[PlanStep]
    notes: Optional[str] = None


class AskRequest(BaseModel):
    query: str
    profile_id: str
    context: Optional[Dict[str, Any]] = None
    strategy_id: Optional[str] = None


class AskResponse(BaseModel):
    answer: str
    evidence: List[Evidence]
    trace_id: str
    status: FinalStatus


class ValidateRequest(BaseModel):
    trace_id: Optional[str] = None
    evidence_ref: Optional[EvidenceLocator] = None


class ProfilingRunRequest(BaseModel):
    profile_id: str
    force: bool = False
    tool_ids: Optional[List[str]] = None


class CapabilitiesResponse(BaseModel):
    profile_id: str
    allowed_strategies: List[str]
    limits: ProfileLimits
    enabled_tools: List[str]


class ToolHealth(BaseModel):
    tool_id: str
    healthy: bool = True
    failure_count: int = 0
