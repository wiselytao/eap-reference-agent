from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException

from reference_agent.models import AskRequest, AskResponse, ValidateRequest
from reference_agent.service import ReferenceAgentService


def build_service() -> ReferenceAgentService:
    config_path = Path(os.getenv("REFERENCE_AGENT_CONFIG", "config.yaml"))
    tools_path = Path(os.getenv("REFERENCE_AGENT_TOOLS", "TOOLS.md"))
    profiles_dir = Path(os.getenv("REFERENCE_AGENT_PROFILES", "profiles"))
    return ReferenceAgentService(config_path, tools_path, profiles_dir)


def create_app() -> FastAPI:
    app = FastAPI(title="Reference Agent", version="1.0")
    service = build_service()

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

    return app
