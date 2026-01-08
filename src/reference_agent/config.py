from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from reference_agent.models import ToolEntry, Profile


class LLMComponentConfig(BaseModel):
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    api_key_ref: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 512
    extra: Dict[str, Any] = Field(default_factory=dict)


class LLMConfig(BaseModel):
    provider: str
    base_url: Optional[str] = None
    model: str
    api_key_ref: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 512
    extra: Dict[str, Any] = Field(default_factory=dict)
    plan_builder: LLMComponentConfig = Field(default_factory=LLMComponentConfig)
    evaluator: LLMComponentConfig = Field(default_factory=LLMComponentConfig)


class RuntimeConfig(BaseModel):
    streaming_default: bool = False
    timeout_seconds: int = 60
    concurrency: int = 4
    port: int = 8080
    stream_status_updates: bool = True


class AuditConfig(BaseModel):
    trace_dir: str = "data/traces"
    retention_days: Optional[int] = None
    enabled: bool = True


class SecurityConfig(BaseModel):
    allowed_profiles: List[str] = Field(default_factory=list)
    require_bearer_token: bool = False
    bearer_token_active: Optional[str] = None
    bearer_token_next: Optional[str] = None


class ObservabilityConfig(BaseModel):
    log_level: str = "INFO"


class TlsConfig(BaseModel):
    enabled: bool = False
    certfile: Optional[str] = None
    keyfile: Optional[str] = None


class AppConfig(BaseModel):
    llm: LLMConfig
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    tls: TlsConfig = Field(default_factory=TlsConfig)
    profiling_dir: str = "tools/profiling"
    profiling_timeout_seconds: int = 300
    profiling_max_retries: int = 2
    profiling_retry_backoff_seconds: int = 2


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    return yaml.safe_load(path.read_text()) or {}


def load_config(path: Path) -> AppConfig:
    data = load_yaml(path)
    runtime = data.get("runtime", {})
    env_port = os.getenv("REFERENCE_AGENT_PORT")
    if env_port:
        try:
            runtime["port"] = int(env_port)
        except ValueError as exc:
            raise ValueError("Invalid REFERENCE_AGENT_PORT; must be an integer.") from exc
    env_stream = os.getenv("REFERENCE_AGENT_STREAM_STATUS_UPDATES")
    if env_stream is not None:
        runtime["stream_status_updates"] = env_stream.strip().lower() in {"1", "true", "yes", "on"}
    data["runtime"] = runtime
    security = data.get("security", {})
    if "bearer_token_active" not in security:
        env_active = os.getenv("REFERENCE_AGENT_BEARER_TOKEN")
        if env_active:
            security["bearer_token_active"] = env_active
    if "bearer_token_next" not in security:
        env_next = os.getenv("REFERENCE_AGENT_BEARER_TOKEN_NEXT")
        if env_next:
            security["bearer_token_next"] = env_next
    data["security"] = security
    return AppConfig(**data)


def _extract_tools_yaml(text: str) -> Dict[str, Any]:
    match = re.search(r"```yaml\n(.*?)\n```", text, re.DOTALL)
    if not match:
        raise ValueError("TOOLS.md must include a ```yaml``` block.")
    return yaml.safe_load(match.group(1)) or {}


def load_tools_md(path: Path) -> List[ToolEntry]:
    if not path.exists():
        raise FileNotFoundError(f"Missing TOOLS.md: {path}")
    data = _extract_tools_yaml(path.read_text())
    tools = data.get("tools", [])
    tool_entries = [ToolEntry(**tool) for tool in tools]
    tool_entries.extend(load_tools_from_env())
    return tool_entries


def load_tools_from_env() -> List[ToolEntry]:
    tools: List[ToolEntry] = []
    indices = _collect_tool_indices()
    for idx in indices:
        base_url = os.getenv(f"TOOL_{idx}_BASE_URL")
        rag_type = os.getenv(f"TOOL_{idx}_RAG")
        if not base_url or not rag_type:
            continue
        rag_type = rag_type.strip().upper()
        prefix = _rag_to_prefix(rag_type)
        if not prefix:
            continue
        tool_id = f"rag{idx}.{rag_type.lower()}"
        tools.append(
            ToolEntry(
                tool_id=tool_id,
                type="hybridrag_pipeline",
                project_id=f"rag{idx}",
                adapter="hybridrag_chat_api_v1",
                base_url=base_url,
                auth_ref=f"TOOL_{idx}_KEY",
                pipeline_prefix=prefix,
                capabilities=[rag_type.lower()],
                evidence_contract="REQUIRED" if rag_type in {"HYBRID", "HYBRIDCOT"} else "OPTIONAL",
                evidence_locator_policy="chat_message_ref",
            )
        )
    return tools


def _collect_tool_indices() -> List[int]:
    indices = set()
    for key in os.environ:
        match = re.match(r"TOOL_(\d+)_BASE_URL", key)
        if match:
            indices.add(int(match.group(1)))
    return sorted(indices)


def _rag_to_prefix(rag_type: str) -> Optional[str]:
    mapping = {
        "VECTOR": "VECTOR:",
        "GRAPH": "GRAPH:",
        "HYBRID": "HYBRID:",
        "HYBRIDCOT": "HYBRIDCOT:",
        "SQL": "SQL:",
    }
    return mapping.get(rag_type)


def load_profile(path: Path) -> Profile:
    data = load_yaml(path)
    return Profile(**data)


def load_profiles(directory: Path) -> Dict[str, Profile]:
    profiles: Dict[str, Profile] = {}
    for profile_path in directory.glob("*.yaml"):
        profile = load_profile(profile_path)
        profiles[profile.profile_id] = profile
    return profiles
