# APISwitch

APISwitch is a local-first AI API gateway and model router.

Current milestone: `v0.2.0-core-gateway` in progress.

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router, Naive UI
- Current providers: Mock, OpenAI, and OpenAI-Compatible non-streaming Chat Completions

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
- OpenAI Responses and Anthropic Messages endpoint skeletons
- Mock Provider adapter
- OpenAI Provider adapter for model discovery and non-streaming Chat Completions
- OpenAI-Compatible adapter for model discovery and non-streaming Chat Completions
- Provider API Key write path with non-plaintext read responses
- Provider connection test and model discovery APIs
- Router scoring, candidate selector, and circuit-breaker skeleton
- Request log persistence for chat completions
- Admin APIs backed by SQLite for providers, unified models, provider models, logs, dashboard summary, router health, and settings
- Vue 3 + Naive UI admin shell connected to the backend APIs
- Web UI forms for providers, unified models, candidates, router health, and model discovery
- Backend pytest and frontend Vitest baseline

The default setup still uses a Mock Provider. Add an OpenAI or OpenAI-Compatible provider in the Web UI, discover models, and attach an upstream model as a candidate to route real traffic.

## Smoke test

```powershell
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/v1/models
curl -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"code-best","messages":[{"role":"user","content":"hello"}]}'
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/test
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/discover-models
curl http://127.0.0.1:8080/api/admin/providers/1/models
```
