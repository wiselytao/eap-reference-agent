# Changelog

All notable changes for this repository are documented here. Entries are based on the v1 PRD and the current implementation.

## v1.47

### Added
- Standard start/stop scripts in `scripts/`.

## v1.46

### Added
- Bearer token can be provided via environment variables.

## v1.45

### Added
- Optional Bearer token auth with active/next rotation and documentation.

## v1.44

### Added
- OpenAI-compatible `/v1/chat/completions` with optional SSE streaming.

## v1.43

### Added
- API guide now links to OAS 3.1 spec.

## v1.42

### Added
- OAS 3.1 specification for Core API and MCP adapter in `doc/openapi.json`.

## v1.41

### Added
- README link to API/MCP usage guide.

## v1.40

### Added
- API & MCP adapter usage guide in `doc/API_MCP.md`.

## v1.39

### Added
- Environment variable example under `doc/env.example`.

## v1.38

### Added
- Config example file under `doc/` and README install/config steps.

## v1.37

### Added
- TLS configuration support for HTTPS serving via `config.yaml`.

## v1.36

### Changed
- Trace now records synthesis notes when LLM extraction/alignment fails.

## v1.35

### Added
- Cross-RAG synthesis pipeline (LLM normalization, alignment, conflict detection, mapping) with trace output.

## v1.34

### Changed
- Step 1 relevance filter is now recall-friendly with an `uncertain` bucket.

## v1.33

### Changed
- Step 1 relevance filter now stops early and returns no-evidence when no tools are relevant.

## v1.32

### Added
- Step 1 relevance filter using LLM on profiling summaries (with traceable rationale codes).

## v1.31

### Added
- Rationale code reference in `doc/RATIONALE_CODES.md`.

## v1.30

### Added
- Trace now records per-step plans (tools, questions, rationale codes).

## v1.29

### Added
- Multi-question per step: each tool can receive up to 3 parallel questions in a single step.

### Changed
- Follow-up tool selection can use LLM-based gap/tool matching with profile summaries as context.
- Trace tool grouping uses step index to reflect parallel queries per step.

## v1.27

### Changed
- Removed strict validation of rewritten follow-up queries.

## v1.26

### Changed
- Validate LLM-rewritten follow-up queries to ensure all missing items are preserved.

## v1.25

### Changed
- Follow-up queries now include missing items/fields and are rewritten by LLM into a single question.

## v1.24

### Fixed
- Align no-progress evaluation check with renamed `missing_fields`.

## v1.23

### Added
- Trace now includes `queried_tools_by_step` for each round.

## v1.22

### Changed
- Rename evaluation fields to `found_fields`/`missing_fields` (aliases keep old names).

## v1.21

### Changed
- Adjusted stop_conditions: evidence stop requires coverage complete & no missing fields; no-progress step can stop when evidence is sufficient.

## v1.20

### Fixed
- Initialize profiling store before Plan Skeleton builder to avoid startup error.

## v1.19

### Changed
- Remove domain-specific required_fields defaults; use profiling schema when available or free-form fields otherwise.
- Evaluator relies on semantic field mapping without hardcoded domain patterns.

## v1.18

### Added
- required_fields now constrained by profiling schema (strict for Graph/SQL, weak fallback for others).
- Evaluator uses LLM semantic mapping for required_fields when available.

## v1.17

### Changed
- Rename Plan Skeleton field `required_bindings` to `required_fields` (backward-compatible parsing).
- Rename router binding fields to `required_fields`/`provided_fields`/`missing_fields` (with aliases).

## v1.15

### Changed
- Use bindings_missing to guide follow-up queries when bindings are not found.

## v1.14

### Changed
- Evaluator now enforces stop_conditions and max_steps to decide whether to proceed to next steps.

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
