# Datus Agent API Server

This package contains the FastAPI HTTP service used by web frontends, services, and automation.

The current server entry point is the `datus-api` console script, backed by `datus.api.main`.

## Quick Start

Install dependencies once:

```bash
uv sync
```

Start the API server in the foreground:

```bash
uv run datus-api --host 127.0.0.1 --port 8000
```

Start with a specific datasource and streaming thinking deltas enabled:

```bash
uv run datus-api \
  --host 127.0.0.1 \
  --port 8000 \
  --datasource <your_datasource> \
  --stream
```

Enable auto-reload for backend development:

```bash
uv run datus-api --host 127.0.0.1 --port 8000 --reload
```

## Frontend Integration

The frontend-facing API contract is exposed by FastAPI:

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI schema: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

`GET /health` is a liveness endpoint. It deliberately does not open database
connections or call an LLM; use the explicit datasource/model connectivity
endpoints for dependency diagnostics.

Long-running chat work is bounded per API worker, project, and authenticated
user. Defaults can be overridden in `agent.api.chat`:

```yaml
agent:
  api:
    chat:
      max_active_global: 32
      max_active_per_project: 16
      max_active_per_user: 4
      max_buffer_events: 5000
      max_buffer_bytes: 16777216
      stream_delta_batch_interval_ms: 50
      stream_delta_batch_chars: 1024
      completed_task_ttl_seconds: 300
      cleanup_interval_seconds: 60
```

Capacity rejections are emitted as an SSE `error` event with
`error_type=CHAT_CAPACITY_EXCEEDED`. If a resume cursor is older than the
bounded in-memory event window, the stream emits
`error_type=CHAT_EVENT_BUFFER_EXPIRED` and the client should load persisted
history instead.

Most JSON endpoints live under `/api/v1` and return the `Result[T]` envelope:

```json
{
  "success": true,
  "data": {},
  "errorCode": null,
  "errorMessage": null
}
```

Streaming endpoints such as `POST /api/v1/chat/stream` and `POST /api/v1/kb/bootstrap` return
`text/event-stream` instead of the JSON envelope. See `docs/API/chat.md` and
`docs/API/knowledge_base.md` for the event grammar.

For local Vue/Vite development, either use a Vite proxy or restrict CORS explicitly:

```bash
DATUS_CORS_ORIGINS=http://127.0.0.1:5173 \
  uv run datus-api --host 127.0.0.1 --port 8000
```

## Common Endpoints

- `GET /health`
- `GET /docs`
- `GET /openapi.json`
- `POST /api/v1/chat/stream`
- `POST /api/v1/chat/resume`
- `POST /api/v1/chat/stop`
- `GET /api/v1/chat/sessions`
- `GET /api/v1/chat/history?session_id=...`
- `GET /api/v1/catalog/list`
- `GET /api/v1/models`
- `GET /api/v1/agent/list`
- `GET /api/v1/config/agent`

## More Documentation

Use the maintained API docs as the canonical reference:

- `docs/API/introduction.md`
- `docs/API/deployment.md`
- `docs/API/chat.md`
- `docs/API/knowledge_base.md`
