# APISwitch

APISwitch is a local-first AI API gateway and model router.

Current milestone: `v0.2.0-core-gateway` stabilization, with the `v0.3.0-unified-auto-routing` foundation started.

## Product direction

APISwitch remains **Unified Model driven**. Clients call stable model names such as `code-best`; Provider accounts, OAuth connections, nodes, costs, quotas, routing strategies, and failover remain internal implementation details.

The expanded roadmap adds a compact OmniRoute-inspired architecture without trying to reproduce every OmniRoute subsystem:

- More high-value Providers.
- API Key, OAuth, anonymous/free-tier, and multi-account Provider Connections.
- Provider Nodes for region, proxy, endpoint, and weight management.
- Unified Model internal routing modes: `static`, `combo`, and `auto`.
- Explainable scoring using health, quota, cost, latency, task fit, context fit, stability, and manual priority.
- Pricing, Token accounting, usage history, quota snapshots, session affinity, and request budget controls.
- Planned protocol expansion for WebSocket, Files, Images, Audio, Moderations, Rerank, Search, Batches, Video, and Music.
- One-click Claude Code Profile writing.

See `docs/omniroute-inspired-roadmap.md` for the detailed design and phased implementation order.

## Handoff documents

For continuing development in a new conversation, read these first:

- `docs/confirmed-requirements.md` - confirmed product scope, priorities, constraints, and acceptance baseline.
- `docs/hand-off-context.md` - project context, requirements, architecture, current state, caveats, and next tasks.
- `docs/conversation-archive.md` - chronological archive of the available conversation and development history.
- `docs/development-plan.md` - milestone progress and remaining work.
- `docs/omniroute-inspired-roadmap.md` - new Provider, protocol, Auto-Combo, scoring, quota, and cost direction.
- `docs/api.md` - current gateway and admin API list.

Suggested prompt for a new conversation:

```text
请先阅读 BXXCAXCA/apiswitch 仓库中的 docs/confirmed-requirements.md、docs/hand-off-context.md、docs/conversation-archive.md、docs/development-plan.md、docs/omniroute-inspired-roadmap.md、docs/api.md 和 README.md，然后继续 APISwitch 开发。保持统一模型驱动，默认直接提交到 main，回答用中文，不要重复询问已确定需求。先跑通并修复 pytest、npm run test、npm run build，再实现 Provider Connection/Node、成本与配额、Auto-Combo 和扩展协议。
```

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router, Naive UI
- Current working providers: Mock, OpenAI, OpenAI-Compatible, Anthropic, and Gemini
- Planned providers: Azure OpenAI, Vertex AI, Bedrock, OpenRouter, xAI, Mistral, Cohere, DeepSeek, Groq, Together, Fireworks, SiliconFlow, Qwen, GLM, Kimi, Doubao, MiniMax, and selected others

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
npm run build
```

## Implemented scope

The current codebase provides:

- FastAPI app and OpenAPI groups
- SQLite, SQLAlchemy models, Alembic migrations, and development bootstrap seed
- OpenAI Chat Completions routed through Unified Models
- OpenAI Responses, including streaming, converted to Chat Completions and routed through Unified Models
- Streaming `text/event-stream` support for `/v1/chat/completions`
- Anthropic Messages routed through Unified Models
- Gateway API Token authentication for `/v1/*`
- Mock, OpenAI, OpenAI-Compatible, Anthropic, and Gemini adapters
- Provider model discovery and connection tests
- Unified Model candidate management
- Retry chains, Provider Health, and persistent Circuit Breakers
- Request logs, API Tokens, Budgets, Settings, WebDAV Profiles, and Agent configuration UI
- Claude Code Profile preview and write support
- Database foundations for Provider Connections, Provider Nodes, Model Pricing, Quota Snapshots, Usage History, and Session Affinity

The new database tables are foundations only. Provider Connection CRUD, OAuth flows, Auto-Combo integration, price ingestion, quota polling, usage accounting, and expanded protocols are not yet complete.

## Claude Code configuration

The Agent page can generate an isolated Claude Code Profile at:

```text
~/.claude/profiles/<profile>/settings.json
```

The generated profile contains the APISwitch Base URL and Unified Model, but does not store the API Token. Start Claude Code with a token injected at runtime:

```powershell
$env:CLAUDE_CONFIG_DIR="$HOME\.claude\profiles\apiswitch"
$env:ANTHROPIC_AUTH_TOKEN="<APISWITCH_TOKEN>"
claude
```

Admin API:

```text
POST /api/admin/agents/claude-code/write
```

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
curl -X POST http://127.0.0.1:8080/api/admin/agents/claude-code/write `
  -H "Content-Type: application/json" `
  -d '{"profile_name":"apiswitch","base_url":"http://127.0.0.1:8080","model":"code-best","dry_run":true}'
curl http://127.0.0.1:8080/api/admin/settings
curl http://127.0.0.1:8080/api/admin/budgets
curl http://127.0.0.1:8080/api/admin/webdav
curl http://127.0.0.1:8080/api/admin/agents
curl http://127.0.0.1:8080/api/admin/logs
curl http://127.0.0.1:8080/api/admin/tokens
curl http://127.0.0.1:8080/api/admin/router-health
```
