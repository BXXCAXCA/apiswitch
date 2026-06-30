# APISwitch

APISwitch is a local-first AI API gateway and model router.

Current milestone: `v0.2.0-core-gateway` in progress.

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router, Naive UI
- Current providers: Mock, OpenAI, OpenAI-Compatible, Anthropic Messages, and Gemini Chat conversion

## Development startup

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r ..\requirements.txt -r ..\requirements-dev.txt
alembic upgrade head
python -m apiswitch
```

Backend URLs:

- Health: http://127.0.0.1:8080/health
- OpenAPI: http://127.0.0.1:8080/docs

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend URL:

- http://127.0.0.1:5173

### Tests

```powershell
cd backend
pytest

cd ../frontend
npm run test
```

## Implemented scope

The current codebase provides:

- FastAPI app and OpenAPI groups
- SQLite, SQLAlchemy models, Alembic migration, and development bootstrap seed
- OpenAI Chat Completions endpoint routed through the unified-model selector
- OpenAI Responses endpoint converted to Chat Completions and routed through the unified-model selector
- Streaming `text/event-stream` support for `/v1/chat/completions`
- SSE model-name rewrite so clients see the unified model while APISwitch records the upstream model
- Anthropic Messages endpoint routed through the unified-model selector
- Mock Provider adapter with Chat Completions and Anthropic Messages support
- OpenAI Provider adapter for model discovery, non-streaming Chat Completions, and streaming Chat Completions
- OpenAI-Compatible adapter for model discovery, non-streaming Chat Completions, and streaming Chat Completions
- Anthropic Provider adapter for static Claude model discovery and non-streaming Messages
- Gemini Provider adapter for model discovery and OpenAI Chat to Gemini `generateContent` conversion
- Gemini response conversion back to OpenAI Chat Completions format
- Provider API Key write path with non-plaintext read responses
- Provider connection test and model discovery APIs
- Router scoring, candidate selector, retry chain, provider health, and persistent circuit breaker state machine
- Circuit breaker states exposed in Router Health and used to skip unavailable candidates
- Request log persistence for chat completions, responses, and messages
- Admin APIs backed by SQLite for providers, unified models, provider models, logs, dashboard summary, router health, and settings
- Vue 3 + Naive UI admin shell connected to the backend APIs
- Web UI management for providers, unified models, candidates, router health, and model discovery
- Provider, unified model, and candidate create/edit/enable/disable/delete actions
- Backend pytest and frontend Vitest baseline

The default setup still uses a Mock Provider. Add an OpenAI, OpenAI-Compatible, Anthropic, or Gemini provider in the Web UI, discover models, and attach an upstream model as a candidate to route real traffic.

## Smoke test

```powershell
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
curl -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"code-best","messages":[{"role":"user","content":"hello"}]}'
curl -N -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"code-best","stream":true,"messages":[{"role":"user","content":"hello"}]}'
curl -X POST http://127.0.0.1:8080/v1/responses `
  -H "Content-Type: application/json" `
  -d '{"model":"code-best","input":"hello"}'
curl -X POST http://127.0.0.1:8080/v1/messages `
  -H "Content-Type: application/json" `
  -d '{"model":"code-best","max_tokens":128,"messages":[{"role":"user","content":"hello"}]}'
curl http://127.0.0.1:8080/api/admin/router-health
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/test
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/discover-models
curl http://127.0.0.1:8080/api/admin/providers/1/models
```
