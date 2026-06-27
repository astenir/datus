# Frontend API Contract

This document records the API contract expected by web frontends.

## Source Of Truth

Use the running FastAPI service as the machine-readable contract:

- Swagger UI: `GET /docs`
- OpenAPI schema: `GET /openapi.json`
- Health check: `GET /health`

Generate frontend TypeScript types from `/openapi.json` for ordinary JSON endpoints.

Example:

```bash
curl http://127.0.0.1:8000/openapi.json -o openapi.json
npx openapi-typescript openapi.json -o src/types/openapi.d.ts
```

## JSON Response Envelope

Most JSON endpoints under `/api/v1` return:

```json
{
  "success": true,
  "data": {},
  "errorCode": null,
  "errorMessage": null
}
```

Frontend clients should unwrap `data` only when `success=true`. When `success=false`, use `errorCode`
for control flow and `errorMessage` for display.

Some authentication, authorization, validation, and legacy errors may still be emitted by FastAPI as:

```json
{
  "detail": "AUTH_REQUIRED"
}
```

Frontend error handling should support both shapes.

## Request Context Headers

Open-source development can identify a caller with:

```text
X-Datus-User-Id: alice
```

SQL policy principal fields are separate from user identity:

```text
X-Datus-Principal: {"market_code":"MKT300"}
```

Do not place `user_id` inside `X-Datus-Principal`; that field is reserved for `X-Datus-User-Id`.

Enterprise deployments may replace this with a Bearer-token or signed-header auth provider. In those modes,
the browser should not spoof trusted gateway headers directly.

## Streaming Endpoints

Streaming endpoints return `text/event-stream` and are not represented as a normal `Result[T]` envelope.

Frontend code should use a `fetch()` + `ReadableStream` SSE parser for POST streams. Native `EventSource`
is not enough for `POST /api/v1/chat/stream`.

### Chat Stream

Endpoints:

- `POST /api/v1/chat/stream`
- `POST /api/v1/chat/resume`
- `POST /api/v1/chat/feedback`

Reference: `docs/API/chat.md`.

Expected frame shape:

```text
id: <sequential int>
event: <session|message|error|ping|end>
data: <JSON payload>
```

Clients must handle at least:

- `session`: save `session_id`
- `message`: apply `createMessage`, `appendMessage`, or `updateMessage`
- `error`: show a terminal stream error
- `ping`: keepalive, usually ignored
- `end`: mark the run complete

### Knowledge Base Streams

Endpoints:

- `POST /api/v1/kb/bootstrap`
- `POST /api/v1/kb/bootstrap-docs`

Reference: `docs/API/knowledge_base.md`.

The `event` field is the bootstrap stage, and `data` contains the stage payload.

## Frontend Type Strategy

Recommended split:

- Generate ordinary JSON types from `/openapi.json`.
- Handwrite TypeScript types for chat and KB SSE event payloads.
- Keep all request helpers under a single API layer, for example `src/lib/api/**`.
- Do not call `fetch()` directly from Vue components.

Suggested frontend scripts:

```json
{
  "scripts": {
    "api:schema": "curl http://127.0.0.1:8000/openapi.json -o openapi.json",
    "api:types": "openapi-typescript openapi.json -o src/types/openapi.d.ts",
    "api:sync": "npm run api:schema && npm run api:types"
  }
}
```

## High-Use Frontend Endpoints

- `GET /api/v1/models`
- `GET /api/v1/config/agent`
- `GET /api/v1/agent/list`
- `GET /api/v1/agent`
- `GET /api/v1/agent/use_tools`
- `GET /api/v1/catalog/list`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/history?session_id=...`
- `POST /api/v1/chat/stream`
- `POST /api/v1/chat/stop`
- `POST /api/v1/chat/insert`
- `POST /api/v1/chat/user_interaction`
