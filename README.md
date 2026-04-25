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
python -m reference_agent.main
```

## Install & Configure
1) Create a virtual environment and install the package.
2) Copy `doc/config.example.yaml` to `config.yaml` and adjust values.
3) Copy `doc/env.example` to `.env.local` (or export variables manually).
4) Set required environment variables (e.g., `AOAI_KEY`, `TOOL_<id>_KEY`).
5) Start the service with `python -m reference_agent.main`.

## Start/Stop Scripts
- Start: `scripts/start.sh`
- Stop: `scripts/stop.sh`
`scripts/start.sh` prefers `.venv/bin/python` if present, otherwise falls back to `python3` or `python`.

## Admin Web UI
- Open `/admin` on the running Reference Agent service.
- Use `Service Control` for local daemon start/stop/restart and status checks.
- Use `Configuration` for structured runtime edits or validated raw file updates.
- Use `Logs` to inspect traces, service logs, and append-only admin action audits.
- Use `System Info` to review active paths, routes, and runtime metadata.
- Use `Docs` to browse allowlisted project documentation from the service itself.

## API & MCP Adapter
See `doc/API_MCP.md` for endpoint usage and examples.
Progress streaming is available via `POST /ask/stream` (SSE).

## Authentication
See `doc/AUTH.md` for bearer token setup and rotation.

Configuration files:
- `config.yaml`
- `tools/TOOLS.md`
- `profiles/default.yaml`
See `doc/tools_md_example_v1.en.md` for an annotated `TOOLS.md` example.
See `doc/tools_md_example_v1.zh_tw.md` for a Traditional Chinese example.

Override their paths with:
- `REFERENCE_AGENT_CONFIG`
- `REFERENCE_AGENT_TOOLS`
- `REFERENCE_AGENT_PROFILES`

Port configuration:
- `runtime.port` in `config.yaml` (default 8080)
- `REFERENCE_AGENT_PORT` env var overrides the config value
- Streaming status updates in `/v1/chat/completions`:
  - `runtime.stream_status_updates: true`
  - `REFERENCE_AGENT_STREAM_STATUS_UPDATES=true`
Rate limiting:
- `runtime.rate_limit_per_base_url` limits concurrent requests per tool `base_url` (default 5).
Trace configuration:
- `audit.enabled: true|false` to enable/disable trace file output

Execution plan prefixes (prepend to the user query):
- `DISTRIBUTED:` / `DISTRI:` to run a distributed plan (parallel tools, merged answer)
- `FAN-OUT:` / `FANOUT:` to run a fan-out plan (parallel tools, answers listed by tool)

Environment tools (optional):
- `TOOL_<id>_BASE_URL` + `TOOL_<id>_KEY` + `TOOL_<id>_RAG` (VECTOR/GRAPH/HYBRID/HYBRIDCOT) will be loaded automatically.
  If a profile uses `enabled_tools: ["*"]` and env tools exist, only env tools are enabled.

## Profiling (v2)
- Profiling files are stored in `tools/profiling/` with filenames `<tool_id>-MMDDHHmm.yaml`.
- If a tool has no `summary` in `tools/TOOLS.md`, runtime probing will ask up to 3 questions in parallel and save a profiling summary.
- `TOOLS.md` changes trigger re-profiling for affected tools on the next request.
- Manual profiling: `python scripts/profile_tools.py --profile default --force` (or `--tool-id <id>`).
- Profiling retries up to 5 times when responses indicate data is unavailable.

## Docker
```bash
docker build -t reference-agent .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=... \
  -e HYBRIDRAG_API_TOKEN=... \
  -e REFERENCE_AGENT_PORT=8080 \
  reference-agent
```

## Systemd Service
See `deploy/reference-agent.service` for a sample unit file. Update paths and environment variables before use.

## HTTPS (TLS)
Set `tls.enabled: true` and provide `tls.certfile` + `tls.keyfile` in `config.yaml`, then run:
```bash
python -m reference_agent.main
```
The API and MCP adapter will be served over HTTPS.

## Tests
```bash
pip install -e .[test]
pytest
```

Note: tests use `httpx.ASGITransport` (required for httpx 0.28+).
