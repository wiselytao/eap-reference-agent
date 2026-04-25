from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from reference_agent.admin.process_control import log_file_path
from reference_agent.config import configured_config_path, load_config
from reference_agent.models import Trace


TRACE_LIST_LIMIT = 25
SERVICE_LOG_LINE_LIMIT = 80
ADMIN_ACTION_LIMIT = 25


def build_logs_page_model() -> dict[str, Any]:
    trace_dir = audit_trace_dir()
    return {
        "trace_explorer": {
            "trace_count": len(list(trace_dir.glob("*.json"))) if trace_dir.exists() else 0,
            "traces": list_recent_traces(trace_dir),
        },
        "service_log": read_service_log(log_file_path()),
        "admin_actions": read_admin_actions(trace_dir / "admin_actions.jsonl"),
    }


def build_trace_detail_model(trace_id: str) -> dict[str, Any] | None:
    trace_path = audit_trace_dir() / f"{trace_id}.json"
    if not trace_path.exists():
        return None

    trace = Trace(**json.loads(trace_path.read_text(encoding="utf-8")))
    return {
        "trace_id": trace.trace_id,
        "profile_id": trace.profile_id,
        "profile_version": trace.profile_version,
        "final_status": trace.final_status,
        "final_status_reasons": trace.final_status_reasons,
        "step_count": len(trace.steps),
        "evidence_count": len(trace.evidence),
        "notes": trace.user_visible_notes,
        "routing_summary": {
            "strategy_id": trace.router.strategy_id,
            "intent_detected": trace.router.intent_detected,
            "candidate_strategies": trace.router.candidate_strategies,
            "rationale_codes": trace.router.rationale_codes,
            "selected_tools": trace.router.selected_tools,
            "params_json": pretty_json(trace.router.params),
            "tool_health_json": pretty_json(trace.router.tool_health_snapshot),
            "binding_readiness": {
                "required": trace.router.binding_readiness.required_fields,
                "provided": trace.router.binding_readiness.provided_fields,
                "missing": trace.router.binding_readiness.missing_fields,
                "resolution_policy": trace.router.binding_readiness.resolution_policy,
                "dependency_required": trace.router.binding_readiness.dependency_required,
            },
        },
        "timeline": build_timeline(trace),
        "evidence": [
            {
                "tool_id": item.tool_id,
                "source_type": item.source_type,
                "source_id": item.source_id,
                "confidence": item.confidence,
                "snippet": item.snippet,
                "locator_json": pretty_json(item.locator.model_dump(exclude_none=True)),
                "meta_json": pretty_json(item.retrieval_meta),
            }
            for item in trace.evidence
        ],
        "plan": {
            "skeleton": pretty_json(trace.plan_skeleton.model_dump()) if trace.plan_skeleton else None,
            "execution": pretty_json(trace.plan_execution.model_dump()) if trace.plan_execution else None,
            "step_plans": pretty_json([item.model_dump() for item in trace.step_plans]),
        },
        "synthesis_json": pretty_json(trace.synthesis.model_dump()) if trace.synthesis else None,
    }


def audit_trace_dir() -> Path:
    config = load_config(configured_config_path())
    return Path(config.audit.trace_dir)


def list_recent_traces(trace_dir: Path) -> list[dict[str, Any]]:
    if not trace_dir.exists():
        return []

    traces: list[dict[str, Any]] = []
    for path in sorted(trace_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            trace = Trace(**json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
        traces.append(
            {
                "trace_id": trace.trace_id,
                "profile_id": trace.profile_id,
                "final_status": trace.final_status,
                "step_count": len(trace.steps),
                "evidence_count": len(trace.evidence),
                "href": f"/admin/logs/trace/{trace.trace_id}",
            }
        )
        if len(traces) >= TRACE_LIST_LIMIT:
            break
    return traces


def read_service_log(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "lines": []}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "path": str(path),
        "exists": True,
        "lines": lines[-SERVICE_LOG_LINE_LIMIT:],
    }


def read_admin_actions(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "records": []}

    records: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        details = payload.get("details") or {}
        records.append(
            {
                "ts": payload.get("ts"),
                "action": payload.get("action"),
                "target": payload.get("target"),
                "outcome": payload.get("outcome"),
                "remote_addr": payload.get("remote_addr"),
                "details_json": pretty_json(details),
            }
        )
    records.reverse()
    return {"path": str(path), "records": records[:ADMIN_ACTION_LIMIT]}


def build_timeline(trace: Trace) -> list[dict[str, Any]]:
    plan_by_index = {item.step_index: item for item in trace.step_plans}
    evaluations_by_step = {item.step_id: item for item in trace.evaluations}
    queried_by_index = {
        index + 1: queried_tools for index, queried_tools in enumerate(trace.queried_tools_by_step)
    }

    items: list[dict[str, Any]] = []
    for index, step in enumerate(trace.steps, start=1):
        evaluation = evaluations_by_step.get(step.step_id)
        step_plan = plan_by_index.get(index)
        items.append(
            {
                "index": index,
                "step_id": step.step_id,
                "tool_id": step.tool_id,
                "duration_ms": step.duration_ms,
                "degraded": step.degraded,
                "error_code": step.error_code,
                "input_summary_json": pretty_json(step.input_summary),
                "output_summary_json": pretty_json(step.output_summary),
                "headline": step.input_summary.get("query")
                or step.output_summary.get("message")
                or step.step_id,
                "evaluation": None
                if evaluation is None
                else {
                    "coverage_complete": evaluation.coverage_complete,
                    "covered_items": evaluation.covered_items,
                    "missing_items": evaluation.missing_items,
                    "should_continue": evaluation.should_continue,
                    "evidence_count": evaluation.evidence_count,
                    "notes": evaluation.notes,
                    "stop_reasons": evaluation.stop_reasons,
                },
                "step_plan": None
                if step_plan is None
                else {
                    "template": step_plan.template,
                    "tool_ids": step_plan.tool_ids,
                    "questions": step_plan.questions,
                    "notes": step_plan.notes,
                },
                "queried_tools": queried_by_index.get(index, []),
            }
        )
    return items


def pretty_json(value: Any) -> str:
    if value in (None, "", [], {}):
        return "None"
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
