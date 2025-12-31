# Reference Agent

Reference Agent is a constrained-strategy RAG broker implementing the v1 PRD. It exposes a Core HTTP API and an MCP adapter layer.

## Requirements
- Python 3.9+
- Optional: Docker (for container deployment)

## Quick Start (Daemon/Local)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
export OPENAI_API_KEY=your_key
export HYBRIDRAG_API_TOKEN=your_token
uvicorn reference_agent.main:app --host 0.0.0.0 --port 8080
```

Configuration files:
- `config.yaml`
- `TOOLS.md`
- `profiles/default.yaml`

Override their paths with:
- `REFERENCE_AGENT_CONFIG`
- `REFERENCE_AGENT_TOOLS`
- `REFERENCE_AGENT_PROFILES`

Environment tools (optional):
- `TOOL_<id>_BASE_URL` + `TOOL_<id>_KEY` + `TOOL_<id>_RAG` (VECTOR/GRAPH/HYBRID/HYBRIDCOT) will be loaded automatically.
  If a profile uses `enabled_tools: ["*"]` and env tools exist, only env tools are enabled.

## Docker
```bash
docker build -t reference-agent .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=... \
  -e HYBRIDRAG_API_TOKEN=... \
  reference-agent
```

## Systemd Service
See `deploy/reference-agent.service` for a sample unit file. Update paths and environment variables before use.

## Tests
```bash
pip install -e .[test]
pytest
```

Note: tests use `httpx.ASGITransport` (required for httpx 0.28+).
