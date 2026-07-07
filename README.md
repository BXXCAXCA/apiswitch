# APISwitch

APISwitch is a local-first AI API gateway and model router.

Current milestone: `v0.2.0-core-gateway` in progress.

## Handoff documents

For continuing development in a new conversation, read these first:

- `docs/hand-off-context.md` - project context, requirements, architecture, current state, caveats, and next tasks.
- `docs/conversation-archive.md` - chronological archive of the available conversation and development history.
- `docs/development-plan.md` - milestone progress and remaining work.
- `docs/api.md` - current gateway and admin API list.

Suggested prompt for a new conversation:

```text
请先阅读 BXXCAXCA/apiswitch 仓库中的 docs/hand-off-context.md、docs/conversation-archive.md、docs/development-plan.md、docs/api.md 和 README.md，然后继续 APISwitch 开发。默认直接提交到 main；回答用中文；不要重复询问已确定需求。优先进入质量修复阶段：跑通/修复 pytest、npm run test、npm run build，然后继续做 Responses streaming、WebDAV 同步和 Agent 备份恢复。
```

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
- Gateway API Token authentication for `/v1/*` endpoints with scope, expiry, enabled-state, and last-used checks
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
- Request logs UI with status, protocol, provider, upstream model, latency, token counts, errors, and retry-chain details
- API Token admin API and UI with one-time token display, prefix-only listing, enable/disable, scopes, expiry, and delete
- Budget admin API and UI with monthly limits, spent amount, usage percentage, alert threshold, enable/disable, and delete
- WebDAV profile admin API and UI with password write-only storage, enable/disable, delete, and connection testing
- Agent config admin API and UI with config path checks, enable/disable, backup path tracking, notes, and delete
- Persistent system settings API and UI backed by SQLite
- Admin APIs backed by SQLite for providers, unified models, provider models, logs, dashboard summary, router health, API tokens, budgets, WebDAV profiles, agents, settings, and system configuration
- Vue 3 + Naive UI admin shell connected to the backend APIs
- Web UI management for providers, unified models, candidates, router health, logs, API tokens, budgets, WebDAV, agents, settings, and model discovery
- Provider, unified model, and candidate create/edit/enable/disable/delete actions
- Model discovery can add discovered upstream models directly as unified-model candidates
- Duplicate unified-model candidates are rejected by the Admin API
- Backend pytest and frontend Vitest baseline

The default setup still uses a Mock Provider. Add an OpenAI, OpenAI-Compatible, Anthropic, or Gemini provider in the Web UI, discover models, attach an upstream model as a candidate, and create an API Token for gateway calls.

## Smoke test

```powershell
curl http://127.0.0.1:8080/health
$tokenResponse = curl -X POST http://127.0.0.1:8080/api/admin/tokens `
  -H "Content-Type: application/json" `
  -d '{"name":"local-dev","scopes":["gateway:invoke"]}' | ConvertFrom-Json
$token = $tokenResponse.token
curl http://127.0.0.1:8080/v1/models -H "Authorization: Bearer $token"
curl -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{"model":"code-best","messages":[{"role":"user","content":"hello"}]}'
curl -N -X POST http://127.0.0.1:8080/v1/chat/completions `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{"model":"code-best","stream":true,"messages":[{"role":"user","content":"hello"}]}'
curl -X POST http://127.0.0.1:8080/v1/responses `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{"model":"code-best","input":"hello"}'
curl -X POST http://127.0.0.1:8080/v1/messages `
  -H "Content-Type: application/json" `
  -H "Authorization: Bearer $token" `
  -d '{"model":"code-best","max_tokens":128,"messages":[{"role":"user","content":"hello"}]}'
curl http://127.0.0.1:8080/api/admin/settings
curl http://127.0.0.1:8080/api/admin/budgets
curl http://127.0.0.1:8080/api/admin/webdav
curl http://127.0.0.1:8080/api/admin/agents
curl http://127.0.0.1:8080/api/admin/logs
curl http://127.0.0.1:8080/api/admin/tokens
curl http://127.0.0.1:8080/api/admin/router-health
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/test
curl -X POST http://127.0.0.1:8080/api/admin/providers/1/discover-models
curl http://127.0.0.1:8080/api/admin/providers/1/models
```
