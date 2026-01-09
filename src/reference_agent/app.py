from __future__ import annotations

import os
import json
import logging
from pathlib import Path
import time
import uuid
from typing import Any, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from reference_agent.models import AskRequest, AskResponse, ProfilingRunRequest, ValidateRequest
from reference_agent.service import ReferenceAgentService


def build_service() -> ReferenceAgentService:
    config_path = Path(os.getenv("REFERENCE_AGENT_CONFIG", "config.yaml"))
    tools_path = Path(os.getenv("REFERENCE_AGENT_TOOLS", "tools/TOOLS.md"))
    profiles_dir = Path(os.getenv("REFERENCE_AGENT_PROFILES", "profiles"))
    return ReferenceAgentService(config_path, tools_path, profiles_dir)


def create_app() -> FastAPI:
    app = FastAPI(title="Reference Agent", version="1.0")
    service = build_service()
    logger = logging.getLogger("uvicorn.error")

    @app.middleware("http")
    async def bearer_auth(request: Request, call_next):
        if not service.require_bearer_token:
            return await call_next(request)
        header = request.headers.get("authorization", "")
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
            if token and token in {service.bearer_token_active, service.bearer_token_next}:
                return await call_next(request)
        raise HTTPException(status_code=401, detail="Unauthorized")

    class OpenAIChatMessage(BaseModel):
        role: str
        content: Any

    def _extract_query(messages: List[Any]) -> str:
        for message in reversed(messages):
            role = message.get("role") if isinstance(message, dict) else message.role
            if role != "user":
                continue
            content = message.get("content") if isinstance(message, dict) else message.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("text"):
                        parts.append(str(item.get("text")))
                if parts:
                    return "\n".join(parts)
        return ""

    def _openai_response(answer: str, model: str | None) -> dict:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model or "reference-agent",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": answer},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _openai_stream(answer: str, model: str | None) -> Iterable[bytes]:
        stream_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        header = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "reference-agent",
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(header)}\n\n".encode("utf-8")
        body = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "reference-agent",
            "choices": [{"index": 0, "delta": {"content": answer}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(body)}\n\n".encode("utf-8")
        tail = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "reference-agent",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(tail)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"

    def _openai_stream_with_status(
        answer_stream: Iterable[dict],
        model: str | None,
        init_event: dict,
        request_start: float,
    ) -> Iterable[bytes]:
        stream_id = f"chatcmpl-{uuid.uuid4().hex}"
        created = int(time.time())
        current_phase: str | None = None
        initialize_sent = False
        first_chunk_sent = False
        header = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "reference-agent",
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(header)}\n\n".encode("utf-8")
        if init_event:
            init_content, current_phase = _format_status_event(init_event, current_phase)
            if init_content:
                initialize_sent = True
                if not first_chunk_sent:
                    first_chunk_sent = True
                    elapsed_ms = int((time.perf_counter() - request_start) * 1000)
                    logger.info("stream_first_chunk_ms=%s", elapsed_ms)
                body = {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model or "reference-agent",
                    "choices": [{"index": 0, "delta": {"content": init_content}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(body)}\n\n".encode("utf-8")
        for event in answer_stream:
            event_type = event.get("type")
            if event_type == "initialize" and initialize_sent:
                continue
            if event_type == "final":
                content = event.get("answer", "")
            elif event_type == "error":
                prefix = "</think>\n" if current_phase else ""
                current_phase = None
                content = f"{prefix}⏳ error: {event.get('error')}\n"
            else:
                content, current_phase = _format_status_event(event, current_phase)
            if not content:
                continue
            if not first_chunk_sent:
                first_chunk_sent = True
                elapsed_ms = int((time.perf_counter() - request_start) * 1000)
                logger.info("stream_first_chunk_ms=%s", elapsed_ms)
            body = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model or "reference-agent",
                "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(body)}\n\n".encode("utf-8")
        tail = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model or "reference-agent",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(tail)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"

    def _format_status_event(event: dict, current_phase: str | None) -> tuple[str, str | None]:
        event_type = event.get("type")
        prefix = ""
        next_phase = current_phase
        if event_type == "initialize":
            next_phase = "initialize"
            if current_phase != next_phase:
                if current_phase:
                    prefix += "</think>\n"
                prefix += "<think>\n"
            ts_ms = event.get("ts_ms")
            suffix = f" (t+{ts_ms}ms)" if isinstance(ts_ms, int) else ""
            return f"{prefix}- ⏳ initializing{suffix}\n", next_phase
        if event_type == "plan_started":
            next_phase = "plan"
            if current_phase != next_phase:
                if current_phase:
                    prefix += "</think>\n"
                prefix += "<think>\n"
            return f"{prefix}- ⏳ planning started\n", next_phase
        if event_type == "plan_completed":
            lines = ["- ✅ planning completed"]
            candidate_tools = event.get("candidate_tools") or []
            if candidate_tools:
                lines.append(f"  - candidate tools: {', '.join(candidate_tools)}")
            required_fields = event.get("required_fields") or []
            if required_fields:
                lines.append(f"  - required fields: {', '.join(required_fields)}")
            stop_conditions = event.get("stop_conditions") or []
            if stop_conditions:
                lines.append(f"  - stop conditions: {', '.join(stop_conditions)}")
            constraints = event.get("constraints") or {}
            if constraints:
                lines.append(f"  - constraints: {json.dumps(constraints)}")
            return "\n".join(lines) + "\n</think>\n", None
        if event_type == "step_started":
            step = event.get("step_index")
            tools = ", ".join(event.get("tool_ids") or [])
            next_phase = f"step:{step}"
            if current_phase != next_phase:
                if current_phase:
                    prefix += "</think>\n"
                prefix += "<think>\n"
            lines = [f"{prefix}- ⏳ step {step} started"]
            if tools:
                lines.append(f"  - tools: {tools}")
            selection_rationale = event.get("selection_rationale") or []
            if selection_rationale:
                lines.append(f"  - rationale: {', '.join(selection_rationale)}")
            selection_notes = event.get("selection_notes")
            if selection_notes:
                lines.append(f"  - notes: {selection_notes}")
            relevance_details = event.get("relevance_details") or []
            if relevance_details:
                for detail in relevance_details:
                    tool_id = detail.get("tool_id")
                    relevance = detail.get("relevance")
                    reason = detail.get("reason")
                    line = f"  - relevance: {tool_id} = {relevance}"
                    if reason:
                        line = f"{line} ({reason})"
                    lines.append(line)
            questions = event.get("questions") or []
            if questions:
                for idx, question in enumerate(questions, start=1):
                    lines.append(f"  - q{idx}: {question}")
            return "\n".join(lines) + "\n", next_phase
        if event_type == "tool_started":
            step = event.get("step_index")
            tool = event.get("tool_id")
            q_index = event.get("query_index")
            suffix = f" q{q_index}" if q_index else ""
            return f"- ⏳ step {step} tool started: {tool}{suffix}\n", next_phase
        if event_type == "tool_completed":
            step = event.get("step_index")
            tool = event.get("tool_id")
            duration = event.get("duration_ms")
            err = event.get("error_code")
            status = "error" if err else "ok"
            suffix = f" ({duration}ms)" if duration is not None else ""
            line = f"- ⏳ step {step} tool completed: {tool} {status}{suffix}"
            if err:
                line = f"{line} — error: {err}"
            return f"{line}\n", next_phase
        if event_type == "step_completed":
            step = event.get("step_index")
            return f"- ⏳ step {step} completed\n</think>\n", None
        if event_type == "composing_started":
            next_phase = "composing"
            if current_phase != next_phase:
                if current_phase:
                    prefix += "</think>\n"
                prefix += "<think>\n"
            return f"{prefix}- ⏳ composing answer\n", next_phase
        if event_type == "composing_completed":
            return "- ⏳ answer composed\n</think>\n\n---\n\n", None
        return "", current_phase

    def _sse_event(event_name: str, payload: dict) -> bytes:
        return f"event: {event_name}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")

    @app.post("/ask", response_model=AskResponse)
    def ask(request: AskRequest) -> AskResponse:
        try:
            return service.ask(request)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/ask/stream")
    def ask_stream(request: AskRequest):
        def event_stream() -> Iterable[bytes]:
            for event in service.ask_stream(request):
                event_type = event.get("type")
                if event_type == "final":
                    yield _sse_event("final", event)
                elif event_type == "error":
                    yield _sse_event("error", event)
                else:
                    yield _sse_event("status", event)
            yield b"data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/trace/{trace_id}")
    def trace(trace_id: str):
        trace_obj = service.get_trace(trace_id)
        if not trace_obj:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace_obj

    @app.post("/validate")
    def validate(request: ValidateRequest):
        return service.validate(request)

    @app.get("/capabilities")
    def capabilities(profile_id: str):
        return service.capabilities(profile_id)

    @app.post("/profiling/run")
    def run_profiling(request: ProfilingRunRequest):
        return service.run_profiling(
            request.profile_id, force=request.force, tool_ids=request.tool_ids
        )

    @app.post("/mcp/reference.ask")
    def mcp_ask(request: AskRequest):
        return ask(request)

    @app.post("/mcp/reference.trace")
    def mcp_trace(trace_id: str):
        return trace(trace_id)

    @app.post("/mcp/reference.validate")
    def mcp_validate(request: ValidateRequest):
        return validate(request)

    @app.post("/mcp/reference.capabilities")
    def mcp_capabilities(profile_id: str):
        return capabilities(profile_id)

    @app.post("/v1/chat/completions")
    async def openai_chat(request: Request):
        start_ts = time.perf_counter()
        logger.info("openai_chat_request_start")
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        messages = payload.get("messages")
        if not messages:
            prompt = payload.get("prompt") or payload.get("input")
            if isinstance(prompt, str) and prompt:
                messages = [{"role": "user", "content": prompt}]
        if not isinstance(messages, list) or not messages:
            raise HTTPException(status_code=400, detail="No messages provided.")
        query = _extract_query(messages)
        if not query:
            raise HTTPException(status_code=400, detail="No user message found.")
        stream = bool(payload.get("stream"))
        model = payload.get("model")
        if stream:
            if service.config.runtime.stream_status_updates:
                logger.info(
                    "openai_chat_stream_response_ready_ms=%s",
                    int((time.perf_counter() - start_ts) * 1000),
                )
                logger.info("openai_chat_stream_status_enabled")
                return StreamingResponse(
                    _openai_stream_with_status(
                        service.ask_stream(
                            AskRequest(
                                query=query,
                                profile_id=payload.get("profile_id", "default"),
                                context=payload.get("context"),
                                strategy_id=payload.get("strategy_id"),
                            )
                        ),
                        model,
                        {"type": "initialize", "ts_ms": int((time.perf_counter() - start_ts) * 1000)},
                        start_ts,
                    ),
                    media_type="text/event-stream",
                )
            try:
                response = service.ask(AskRequest(query=query, profile_id="default"))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return StreamingResponse(_openai_stream(response.answer, model), media_type="text/event-stream")
        try:
            response = service.ask(AskRequest(query=query, profile_id="default"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _openai_response(response.answer, model)

    return app
