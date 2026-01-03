from __future__ import annotations

import os
import json
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

    class OpenAIChatRequest(BaseModel):
        model: Optional[str] = None
        messages: List[OpenAIChatMessage]
        stream: bool = False
        temperature: Optional[float] = None
        max_tokens: Optional[int] = None
        user: Optional[str] = None

    def _extract_query(messages: List[OpenAIChatMessage]) -> str:
        for message in reversed(messages):
            if message.role != "user":
                continue
            content = message.content
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

    @app.post("/ask", response_model=AskResponse)
    def ask(request: AskRequest) -> AskResponse:
        try:
            return service.ask(request)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    def openai_chat(request: OpenAIChatRequest):
        query = _extract_query(request.messages)
        if not query:
            raise HTTPException(status_code=400, detail="No user message found.")
        try:
            response = service.ask(AskRequest(query=query, profile_id="default"))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if request.stream:
            return StreamingResponse(
                _openai_stream(response.answer, request.model), media_type="text/event-stream"
            )
        return _openai_response(response.answer, request.model)

    return app
