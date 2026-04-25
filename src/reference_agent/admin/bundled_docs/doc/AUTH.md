# API Authentication

Reference Agent can optionally require a Bearer token on all endpoints (Core API, MCP adapter, and OpenAI-compatible routes).

## Enable Bearer Token
In `config.yaml`:
```yaml
security:
  require_bearer_token: true
  bearer_token_active: "your_active_token"
  bearer_token_next: "your_next_token"
```

Or via environment variables:
```
REFERENCE_AGENT_BEARER_TOKEN=your_active_token
REFERENCE_AGENT_BEARER_TOKEN_NEXT=your_next_token
```

## Generate a Token
Example (32 hex chars):
```bash
openssl rand -hex 16
```

## Use the Token
Send the token in the Authorization header:
```
Authorization: Bearer <token>
```

## Rotation (Active/Next)
1) Set `bearer_token_next` and reload the service.
2) Update clients to use the next token.
3) Promote next → active and clear next.

If `require_bearer_token` is `false`, the API accepts requests without a token.
