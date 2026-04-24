# Reference Agent Admin Web UI Design

> Status: approved design draft for implementation planning
> Date: 2026-04-24
> Scope: v1 admin interface for managing the local Reference Agent service

## 1. Goal

Add an Admin Web UI for Reference Agent that lets an operator:

1. control the local daemon lifecycle,
2. inspect and edit all project configuration,
3. review logs and traces in a high-readability format,
4. inspect product, runtime, and connection information,
5. read project documentation from the same interface.

The first implementation is built into the existing FastAPI application, while
keeping the admin layer isolated enough to be extracted into a standalone admin
service later.

## 2. Scope

### In scope

1. Built-in admin routes under `/admin`
2. Service control for the existing script-driven local daemon model
3. Structured configuration editing for common settings
4. Raw file editing for `config.yaml`, `profiles/*.yaml`, and `tools/TOOLS.md`
5. Trace and service log exploration with readable summaries
6. System information and connection detail views
7. Embedded documentation pages rendered from repository markdown files
8. Admin action audit records for every mutating operation

### Out of scope for v1

1. Separate admin login system
2. RBAC or multi-user permission models
3. `systemd`, Docker, Kubernetes, or container-native control backends
4. Editing shell-session-only environment variables from the UI
5. Real-time websocket dashboards
6. Multi-node or remote fleet management

## 3. Deployment and Security Model

### Deployment model

The v1 Admin UI is served by the same FastAPI application as the Reference
Agent API. It is mounted under `/admin` and shares the same process and port.

The implementation must still separate:

1. admin route handlers,
2. admin service/domain logic,
3. file/process adapters,
4. HTML template rendering.

That boundary is required so the admin layer can later move into a separate
service with minimal code movement.

### Security model

The first version assumes the admin surface is protected externally by one of:

1. internal-network-only deployment,
2. reverse proxy access control,
3. the existing bearer-token model when enabled.

The admin UI does not introduce its own username/password or session system in
v1.

## 4. Information Architecture

The admin UI uses a left-side primary navigation with a right-side main content
area. This layout is preferred because the application contains dense operational
information and multiple work modes.

Primary sections:

1. `Overview`
2. `Service Control`
3. `Configuration`
4. `Logs & Audit`
5. `System Info`
6. `Docs`

## 5. Page Design

### 5.1 Overview

Purpose: present the current operational summary without requiring the operator
to inspect multiple pages.

Content:

1. current service status,
2. PID and uptime when available,
3. product version,
4. active port and local base URL,
5. key file paths:
   `config.yaml`, `tools/TOOLS.md`, `profiles/`, `data/traces/`, `data/ra.log`,
6. quick links to service control, config editing, and recent traces.

### 5.2 Service Control

Purpose: manage the local daemon using the existing shell scripts.

Supported actions:

1. `Start`
2. `Stop`
3. `Restart`
4. `Refresh Status`

Displayed state:

1. running or stopped,
2. PID file status,
3. process liveness check,
4. health probe result,
5. last control action result,
6. recent stdout/stderr excerpt on failure.

Important operational rule:

The UI must not attempt a synchronous in-request self-restart of the same
process that is currently serving the admin page. Restart must be modeled as a
detached external control action followed by client-side reconnect polling.

Recommended restart sequence:

1. user clicks restart,
2. admin endpoint records an action request,
3. endpoint launches a detached control command,
4. control command runs `scripts/stop.sh` and then `scripts/start.sh`,
5. browser switches to a reconnecting state and polls until the service is
   available again.

### 5.3 Configuration

Purpose: allow complete configuration management from the browser while reducing
breakage risk for common edits.

The page has two editing modes.

#### Structured form mode

Used for known fields with direct validation and operator-friendly labels.

Targets:

1. `config.yaml`
2. `profiles/*.yaml`
3. common metadata in `tools/TOOLS.md`

Structured form groups:

1. General and product paths
2. Runtime
3. Audit
4. Security
5. TLS
6. Profiling
7. Profiles
8. Tools

Required behavior:

1. load current file content,
2. map content into typed form fields,
3. validate before save,
4. show a diff preview,
5. indicate whether restart is required,
6. write back only after successful validation.

#### Raw editor mode

Used for full-fidelity editing of:

1. `config.yaml`
2. any file in `profiles/*.yaml`
3. `tools/TOOLS.md`

Required behavior:

1. syntax-aware save path,
2. parse validation before write,
3. clear error messages with line/context when validation fails,
4. no hidden normalization beyond the selected file format,
5. explicit warning when raw edits may affect runtime behavior broadly.

### 5.4 Logs & Audit

Purpose: make trace and operational review readable enough for day-to-day use.

Subsections:

1. `Trace Explorer`
2. `Service Log`
3. `Admin Actions`

#### Trace Explorer

Primary readability model:

1. list traces with filters,
2. show summary cards for trace id, time, profile, status,
3. render a step timeline instead of raw JSON first,
4. show tool selection, durations, outcomes, and final status,
5. show evidence and final answer in dedicated panels,
6. allow raw JSON expansion for advanced debugging.

Filters:

1. trace id,
2. profile id,
3. final status,
4. tool id,
5. date range,
6. free-text search against trace content.

#### Service Log

Read from `data/ra.log` and present:

1. reverse chronological entries,
2. severity hints when possible,
3. text search,
4. tail view for recent lines.

#### Admin Actions

A dedicated admin audit record is required for every mutating action, including:

1. service control commands,
2. configuration saves,
3. profiling triggers,
4. future admin-side maintenance operations.

Each record must capture at least:

1. timestamp,
2. action type,
3. target resource,
4. operator context available from request metadata,
5. result status,
6. short message.

## 6. System Info

Purpose: give operators a single page for runtime and product facts.

Display:

1. product name and package version,
2. current runtime port,
3. HTTP vs HTTPS mode,
4. computed base URLs,
5. OpenAI-compatible route,
6. MCP routes,
7. bearer token requirement status,
8. trace and profiling directories,
9. config, tools, and profiles paths,
10. enabled profiles and tool counts.

This page is read-only in v1.

## 7. Docs

Purpose: make project operating guidance available without leaving the admin UI.

The v1 docs page renders repository markdown sources directly rather than
introducing a separate document system.

Initial sources:

1. `README.md`
2. `doc/API_MCP.md`
3. `doc/AUTH.md`
4. `doc/RATIONALE_CODES.md`
5. `doc/tools_md_example_v1.en.md`
6. `doc/tools_md_example_v1.zh_tw.md`

Required behavior:

1. nav tree of supported docs,
2. rendered markdown view,
3. link to raw source path,
4. graceful handling when a doc file is missing.

## 8. Internal Architecture

The implementation should introduce an admin subsystem with explicit boundaries.

Recommended code units:

1. `admin routes`
   handle HTTP endpoints for page rendering and admin actions,
2. `admin services`
   implement configuration, trace/log reading, system info, and process control,
3. `file adapters`
   read and write YAML, markdown, TOOLS markdown blocks, and audit records,
4. `process controller`
   run `start.sh`, `stop.sh`, status checks, and detached restart orchestration,
5. `templates/static assets`
   server-rendered HTML with minimal client-side JavaScript.

UI delivery model:

1. server-rendered HTML,
2. minimal vanilla JavaScript for polling, filter forms, expand/collapse, and
   reconnect states,
3. no JS build pipeline in v1.

## 9. Data Sources and Persistence

The Admin UI reads from the existing project files and runtime state.

Primary sources:

1. `config.yaml`
2. `profiles/*.yaml`
3. `tools/TOOLS.md`
4. `data/traces/*.json`
5. `data/ra.log`
6. PID file from the existing shell scripts
7. runtime service config loaded by the process

New persistence introduced by the admin layer:

1. an admin action audit log, preferably append-only JSONL under `data/`

## 10. Validation and Error Handling

### Configuration saves

Before writing any configuration file:

1. parse candidate content,
2. validate against the relevant pydantic model or structured parser,
3. reject invalid content with readable errors,
4. only persist validated content.

### Service control

When start, stop, or restart fails:

1. show the action as failed,
2. persist the failure in admin action audit,
3. surface a readable stdout/stderr excerpt,
4. keep the current UI state refreshable.

### Read operations

When trace, log, or docs sources are missing:

1. do not crash the page,
2. render an empty-state or missing-file message,
3. preserve navigation and other working sections.

## 11. User Experience Requirements

The UI should optimize for high readability over visual novelty.

Required UX characteristics:

1. dense but well-grouped information,
2. prominent status states,
3. readable trace timeline with clear step boundaries,
4. explicit action results,
5. visible restart-needed indicators after config edits,
6. consistent path and route labeling for operators.

## 12. Testing Expectations for Implementation

The implementation plan should cover at least:

1. route tests for admin pages and action endpoints,
2. config parsing and validation tests,
3. trace listing and rendering tests,
4. process controller tests with mocked subprocess execution,
5. docs rendering tests,
6. failure-path tests for invalid config and failed service actions.

## 13. Deferred Follow-ups

Candidate next steps after v1:

1. extract admin API into a separate service,
2. add authenticated admin sessions or RBAC,
3. support additional control backends such as `systemd`,
4. add richer search and retention tools for traces and logs,
5. add live streaming status widgets.
