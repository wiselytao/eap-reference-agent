# Changelog

All notable changes for this repository are documented here. Entries are based on the v1 PRD and the current implementation.

## v1.0

### Added
- Core HTTP API (`/ask`, `/trace/{id}`, `/validate`, `/capabilities`) with MCP adapter endpoints.
- YAML configuration (`config.yaml`), static tool manifest (`TOOLS.md`), and profile support (`profiles/*.yaml`).
- Hybrid RAG adapter for Chat API v1 (create chat → send message, evidence locator).
- External MCP client stub with pluggable base URL and tool path.
- Router with deterministic strategy selection and guardrails.
- Strategy executor for v1 strategies (V/G/H/HCOT, E_FJ_H, fallback).
- Evidence and trace models with file-based trace storage.
- Language-aware templates for EMPTY/PARTIAL/NO_EVIDENCE responses.
- Dockerfile and systemd service unit for deployment.
- pytest + httpx tests for API surface.

### Changed
- Tool loading supports `TOOL_<id>_*` environment variables and prefers env tools when profiles use `enabled_tools: ["*"]`.
- Trace router output expanded with intent, candidates, tool health snapshot, and selected tools.

