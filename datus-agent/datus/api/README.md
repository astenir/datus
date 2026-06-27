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
