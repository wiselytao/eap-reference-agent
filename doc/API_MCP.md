# API & MCP Adapter Guide

This document describes the Core HTTP API and the MCP adapter endpoints exposed by Reference Agent.

## Base URL
- Default: `http://localhost:8080`
- If TLS enabled: `https://localhost:8080`

## OpenAPI
See `doc/openapi.json` (OAS 3.1).

## Authentication
Reference Agent can optionally require a bearer token. See `doc/AUTH.md`.

## Core HTTP API

### POST /ask
Ask a question and receive an answer with evidence and a trace ID.

Request:
```json
{
  "query": "Tell me the most critical vulnerability in Java systems.",
  "profile_id": "default",
  "context": { "need_external": false },
  "strategy_id": "STR_H"
}
```

Response:
```json
{
  "answer": "string",
  "evidence": [
    {
      "source_type": "hybrid_answer",
      "tool_id": "rag1.vector",
      "source_id": "chat_id",
      "locator": { "chat_id": "chat123", "messageId": "msg123", "external_ref": null },
      "snippet": "string",
      "retrieval_meta": {},
      "confidence": 0.8
    }
  ],
  "trace_id": "uuid",
  "status": "SUCCESS"
}
```

### GET /trace/{trace_id}
Fetch the full trace for audit and debugging.

Response includes:
- `plan_skeleton`, `plan_execution`
- `evaluations`, `step_plans`, `queried_tools_by_step`
- `synthesis` (if available)

### POST /validate
Validate a trace or a locator.

Request (trace):
```json
{ "trace_id": "uuid" }
```

Request (locator):
```json
{ "evidence_ref": { "chat_id": "chat123", "messageId": "msg123", "external_ref": null } }
```

Response:
```json
{ "status": "ok", "evidence": [ ... ] }
```

### GET /capabilities?profile_id=default
Fetch profile capabilities.

Response:
```json
{
  "profile_id": "default",
  "allowed_strategies": ["STR_H", "STR_G"],
  "limits": { "max_steps": 3, "evidence_min": 1, "evidence_max": 12, "token_max": 2048, "per_tool": {} },
  "enabled_tools": ["rag1.vector", "rag4.hybridcot"]
}
```

### POST /profiling/run
Trigger profiling for a profile.

Request:
```json
{ "profile_id": "default", "force": true, "tool_ids": ["rag1.vector"] }
```

Response:
```json
{ "status": "ok" }
```

### POST /v1/chat/completions
OpenAI-compatible chat completion endpoint. This routes to `/ask` internally.

Request:
```json
{
  "model": "reference-agent",
  "messages": [
    { "role": "user", "content": "What is X?" }
  ],
  "stream": false
}
```

Response:
```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "created": 1730000000,
  "model": "reference-agent",
  "choices": [
    { "index": 0, "message": { "role": "assistant", "content": "..." }, "finish_reason": "stop" }
  ],
  "usage": { "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0 }
}
```

Streaming (SSE) is supported by setting `"stream": true`.

## MCP Adapter Endpoints
MCP endpoints mirror the Core API (same payloads), prefixed with `/mcp`.

### POST /mcp/reference.ask
Same request/response as `/ask`.

### POST /mcp/reference.trace?trace_id=<id>
Same response as `/trace/{trace_id}`.

### POST /mcp/reference.validate
Same as `/validate`.

### POST /mcp/reference.capabilities?profile_id=default
Same as `/capabilities`.

## Curl Examples

Ask:
```bash
curl -s -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What is X?","profile_id":"default"}'
```

Trace:
```bash
curl -s http://localhost:8080/trace/<trace_id>
```

MCP ask:
```bash
curl -s -X POST http://localhost:8080/mcp/reference.ask \
  -H "Content-Type: application/json" \
  -d '{"query":"What is X?","profile_id":"default"}'
```
