# Changelog

All notable changes for this repository are documented here. Entries are based on the v1 PRD and the current implementation.

## v1.13

### Changed
- Enforce inclusion of the PARTIAL notice in composed responses.

## v1.12

### Changed
- PARTIAL responses now use AnswerComposer to format the response with the Hybrid RAG style prompt.

## v1.11

### Changed
- AnswerComposer prompt aligned with Hybrid RAG answerGen template.

## v1.10

### Changed
- Use evaluator results to downgrade incomplete answers to PARTIAL/EMPTY and prefer best step answer.

## v1.9

### Changed
- Added profiling retry policy and separate profiling timeout settings.

## v1.8

### Added
- Evaluator implementation with coverage/specificity/evidence checks and trace recording.

## v1.7

### Changed
- Profiling question sets expanded to 5 questions for Vector and Graph tools.

## v1.6

### Added
- Tool profiling invalidation based on `tools/TOOLS.md` changes and per-tool fingerprints.
- Manual profiling triggers via CLI (`scripts/profile_tools.py`) and API (`POST /profiling/run`).

### Changed
- Profiling records now store `tool_hash` to detect tool definition updates.

## v1.4

### Added
- v2 bounded planner and executor with templates T1/T2/T3 and plan execution trace.
- Binding extraction for dependency-aware second-step queries.

### Changed
- Increase Hybrid RAG timeout to 300s for v2 probing and execution.

## v1.3

### Added
- Profiling storage in `tools/profiling/` with `<tool_id>-MMDDHHmm` versioning.
- Runtime probing for missing summaries (up to 3 parallel questions).

### Changed
- Router tool selection prefers tools with summaries/profiling data.
- Tool entries support optional `summary` and `profile_summary`.

## v1.2

### Added
- Plan Skeleton builder and trace storage of plan skeleton for v2 planning.

### Changed
- Tool entries now accept optional `summary` for profiling use.

## v1.1

### Changed
- Move tool manifest to `tools/TOOLS.md` and add `tools/profiling/` directory for v2 profiling artifacts.
- Add per-component LLM overrides in `config.yaml` (plan builder/evaluator).

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
