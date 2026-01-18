# Changelog

All notable changes for this repository are documented here. Entries are based on the v1 PRD and the current implementation.

## v3.23

### Changed
- Reduced merged follow-up questions to include only tool-specific prompts plus JSON context.

## v3.22

### Changed
- Generated tool-specific follow-up questions after step 1 with per-tool merging rules.

## v3.21

### Changed
- Used follow-up questions after step 1, merging them for graph/hybrid tools.

## v3.20

### Changed
- Updated partial-answer template to include evidence and request counts.

## v3.19

### Changed
- Allowed hybrid profiling to run full vector+graph question sets without trimming.

## v3.18

### Changed
- Profiled hybrid tools using vector L0 questions plus graph schema questions.

## v3.17

### Changed
- Unified profiling retry logic to avoid overlapping retry loops.

## v3.16

### Changed
- Applied profiling retry detection to all RAG types using shared retry criteria.

## v3.15

### Changed
- Removed profiling summary truncation to keep full answers.

## v3.14

### Changed
- Enforced --tool-id filtering during profiling and added retry progress output.

## v3.13

### Changed
- Retried graph schema profiling question when responses indicate schema is unavailable.

## v3.12

### Changed
- Added profiling progress output to `scripts/profile_tools.py`.

## v3.11

### Changed
- Fixed profiling rate limit semaphore scoping to avoid cross-event-loop errors.

## v3.10

### Changed
- Applied per-base_url concurrency limits to profiling requests and documented the setting.

## v3.9

### Changed
- Added per-base_url concurrency limits for tool requests (default 5).

## v3.8

### Changed
- Added structured follow-up context extraction to improve downstream questions.

## v3.7

### Changed
- Clarified plan skeleton prompt definitions for answer_blueprint and required_fields.

## v3.6

### Changed
- Split multi-queries only for vector and external tools; other tools use the original query.

## v3.5

### Changed
- Tightened multi-query prompt to enforce JSON-only output and gap-focused questions.

## v3.4

### Changed
- Removed step selection notes from `<think>` status output.

## v3.3

### Changed
- Switched vector profiling to L0 JSON prompts and L0-based relevance judging.

## v3.2

### Changed
- Added back the traversal query example to graph profiling questions.

## v3.1

### Changed
- Updated graph profiling to use a single schema summary question.

## v3.0

### Changed
- Major version reset to v3.0.

## v2.38

### Fixed
- Test stub updated for titled HybridRAG chat creation.

## v2.37

### Added
- Auto-load `.env.local` in `scripts/profile_tools.py`.

## v2.36

### Added
- HybridRAG chat reuse per tool with titled chats (`ReferenceAgent-yyMMDDhhmmss`).

## v2.35

### Changed
- Dropped `pipeline_prefix` from tool definitions; routing now derives prefixes from capabilities.

## v2.34

### Changed
- Removed the adapter field from tool definitions; dispatch now uses `type`.

## v2.33

### Changed
- Documented supported adapter values in `TOOLS.md` example docs.

## v2.32

### Changed
- Removed tool profiling notes from streamed `<think>` planning output.

## v2.31

### Changed
- Added capability value descriptions to `TOOLS.md` example docs.

## v2.30

### Changed
- Expanded `TOOLS.md` example docs with evidence field guidance and capabilities list.

## v2.29

### Added
- Traditional Chinese `TOOLS.md` example in `doc/tools_md_example_v1.zh_tw.md`.

## v2.28

### Added
- Annotated `TOOLS.md` example in `doc/tools_md_example_v1.en.md`.

## v2.26

### Changed
- `<think>` output now focuses on dynamic planning/tool relevance decisions.

## v2.24

### Added
- Configurable audit tracing via `audit.enabled`.

## v2.24

### Changed
- `<think>` planning output now includes per-tool selection reasons.

## v2.23

### Changed
- Trace IDs now use ULID for shorter, time-sortable filenames.

## v2.23

### Changed
- Streaming `<think>` status now includes planning rationale and step questions.

## v2.22

### Fixed
- Streaming requests no longer precompute synchronous answers before emitting SSE.

## v2.21

### Added
- Extra timing log for stream response readiness.

## v2.20

### Changed
- Stream timing diagnostics now log via Uvicorn error logger.

## v2.19

### Added
- Streaming diagnostics logs for first chunk timing.

## v2.18

### Changed
- Initialize status now emits earlier with timing metadata.

## v2.17

### Changed
- Streaming status updates now group `<think>` blocks by phase with an initialize event.

## v2.16

### Changed
- Streaming status updates now wrap in `<think>` tags.

## v2.15

### Changed
- Streaming status updates now render as markdown with a separator before the answer.

## v2.14

### Added
- Optional streaming status updates in OpenAI-compatible SSE responses.

## v2.13

### Added
- Streaming status updates via `POST /ask/stream` (SSE).

## v2.12

### Added
- README notes for configurable runtime port.

## v2.11

### Added
- Configurable runtime port via `runtime.port` and `REFERENCE_AGENT_PORT`.

## v2.10

### Changed
- References now render as a markdown section with list entries.

## v2.9

### Changed
- References now group pages per file into a single entry.

## v2.8

### Changed
- References are now sorted by filename then page number.

## v2.7

### Changed
- References now list file, page (parsed from content), and URL for each validation document.

## v2.6

### Changed
- References now include raw validation JSON for all evidences.

## v2.5

### Added
- Append References section with document names and download links resolved from validation data.

### Changed
- Use tool project_id as tenant header when resolving document links.

## v2.4

### Fixed
- Fix test fixture config formatting to avoid `.format` brace collisions.

## v2.3

### Added
- Append reference information to answers using evidence validation data when available.
- Fetch hybrid RAG validation data to resolve evidence sources.

## v2.2

### Changed
- OpenAI-compatible endpoint now accepts `prompt`/`input` when `messages` is missing.

## v2.1

### Changed
- Start script now prefers `.venv/bin/python` when available.

## v2.0

### Added
- Bounded planner with dynamic step execution and per-step plans in trace.
- Profiling system with tool summaries, runtime probing, and profiling artifacts in `tools/profiling/`.
- Cross-RAG synthesis pipeline (LLM normalization, alignment, conflict detection, mapping) with trace output.
- OpenAI-compatible `/v1/chat/completions` with optional SSE streaming.
- Optional TLS configuration and bearer token auth with active/next rotation.
 - Trace now records evaluation stop reasons and final status downgrade reasons.

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
