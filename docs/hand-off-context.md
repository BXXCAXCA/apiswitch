# APISwitch Handoff Context

> Purpose: this document preserves the project context, decisions, requirements, current implementation state, and next tasks so a new ChatGPT conversation can continue development without losing continuity.
>
> How to use in a new conversation: ask ChatGPT to read `docs/hand-off-context.md`, `docs/conversation-archive.md`, `docs/development-plan.md`, and `docs/api.md` before making changes.

## Repository and workflow

- Repository: `BXXCAXCA/apiswitch`
- Default branch: `main`
- Development mode requested by the user: continue developing directly in the existing repository, commit directly to `main`, and do not ask for repeated confirmation for routine implementation steps.
- Conversation language: Chinese is preferred.
- Current product direction: APISwitch is now an AI API Gateway + Model Router + Control Panel, not only a simple API key manager.
- Current milestone: `v0.2.0-core-gateway` in progress.
- Tests and builds: many tests have been added, but the remote ChatGPT/GitHub tool environment has not actually executed `pytest`, `npm run test`, or `npm run build`. Do not claim tests pass until they are run in a real environment.

## Original product goal

The original requirement was to build a cross-platform lightweight client/program for saving and managing large-model API keys, with:

- API key management.
- API key detection / provider connectivity checks.
- Encrypted key storage.
- WebDAV multi-device sync.
- Support for OpenAI, Google/Gemini, Anthropic, OpenAI-compatible formats, and OpenAI Responses-style API.
- Pulling provider model lists.
- Simple chat.

The goal later evolved into:

- Local-first AI API gateway.
- Unified model routing.
- Provider failover and health tracking.
- Admin control panel.
- API token protected gateway endpoints.
- Web UI for providers, unified models, candidates, logs, settings, budgets, WebDAV, and Agents.

## Important user decisions captured during requirements gathering

- Build on an existing repository rather than starting a standalone prototype.
- Use a practical stack suitable for fast iteration:
  - Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite.
  - Frontend: Vue 3, TypeScript, Vite, Naive UI.
- Start Windows/local-first but keep structure portable.
- Start as separate backend/frontend dev servers; backend can serve frontend dist later.
- First provider is Mock Provider so tests and UI can work before real API keys are added.
- Support provider types:
  - `mock`
  - `openai`
  - `compatible`
  - `anthropic`
  - `gemini`
- Support gateway protocols:
  - OpenAI Chat Completions: `/v1/chat/completions`
  - OpenAI Responses: `/v1/responses`
  - Anthropic Messages: `/v1/messages`
  - Model list: `/v1/models`
- Admin/API UI should manage providers, unified models, candidates, model discovery, logs, dashboard, router health, API tokens, settings, budgets, WebDAV profiles, and Agent configs.
- Continue implementing incrementally when the user says “继续”.

## Current architecture

### Backend

- `backend/apiswitch/app.py`: FastAPI application factory, router registration, CORS, health endpoint.
- `backend/apiswitch/config.py`: runtime settings.
- `backend/apiswitch/db/`: SQLAlchemy base/session/models/bootstrap/seed.
- `backend/apiswitch/api/gateway/`: public gateway protocol routes.
- `backend/apiswitch/api/admin/`: admin/control-panel APIs.
- `backend/apiswitch/providers/`: provider adapters and factory.
- `backend/apiswitch/gateway/`: execution, routing integration, streaming, protocol conversions.
- `backend/apiswitch/router/`: scoring, selector, health, persistent circuit breaker.
- `backend/apiswitch/schemas/`: Pydantic request/response schemas.
- `backend/apiswitch/security/`: token helpers and placeholder secret crypto.
- `backend/tests/`: backend pytest coverage.

### Frontend

- `frontend/src/router/index.ts`: Vue routes.
- `frontend/src/layouts/AdminLayout.vue`: admin shell.
- `frontend/src/api/`: typed API clients.
- `frontend/src/views/`: functional admin pages.

### Database tables currently modeled

- `providers`
- `provider_models`
- `unified_models`
- `unified_model_candidates`
- `provider_health`
- `circuit_breakers`
- `request_logs`
- `api_tokens`
- `budgets`
- `file_cache`
- `embedding_cache`
- `webdav_profiles`
- `agent_configs`
- `settings`

## Implemented backend functionality

### Core app and database

- FastAPI app with OpenAPI tags.
- SQLite + SQLAlchemy models.
- Alembic migration baseline and later migrations.
- Development bootstrap creates tables and seeds default data.
- Seed data:
  - Provider: `mock-main`, type `mock`, base URL `mock://local`.
  - Provider model: `mock-chat`.
  - Unified model: `code-best`.
  - Candidate from `code-best` to `mock-main` / `mock-chat`.
  - Default persistent settings.

### Gateway endpoints

All `/v1/*` endpoints now require `Authorization: Bearer <api_token>` with `gateway:invoke` scope.

- `POST /v1/chat/completions`
  - Routed through unified-model selector.
  - Supports non-streaming JSON responses.
  - Supports OpenAI-compatible SSE when `stream=true`.
  - Preserves client-facing unified model in response.
  - Tracks actual upstream model in `apiswitch.upstream_model` metadata.
  - Writes request logs.
  - Updates provider health and circuit breaker state.
  - Retries ranked candidates before final failure.
- `POST /v1/responses`
  - Accepts OpenAI Responses-like request schema.
  - Converts Responses input to Chat Completions internally.
  - Routes through gateway selector.
  - Converts chat response back to Responses-like object.
  - Non-streaming implemented.
  - `stream=true` currently returns `responses_streaming_not_implemented`.
- `POST /v1/messages`
  - Accepts Anthropic Messages-like request schema.
  - Routed through unified-model selector.
  - Mock provider supports Anthropic-style response.
- `GET /v1/models`
  - Requires gateway API token.
  - Currently backed by Mock provider registry model list; future improvement should expose DB unified/provider models more fully.

### Providers

- Mock provider:
  - Chat Completions.
  - Streaming Chat Completions SSE.
  - Anthropic Messages.
  - Model list.
- OpenAI provider:
  - `/models` discovery.
  - Non-streaming `/chat/completions`.
  - Streaming `/chat/completions`.
  - Requires API key.
- OpenAI-Compatible provider:
  - `/models` discovery.
  - Non-streaming `/chat/completions`.
  - Streaming `/chat/completions`.
- Anthropic provider:
  - Static Claude model discovery.
  - Non-streaming Messages path.
- Gemini provider:
  - Model discovery.
  - OpenAI Chat to Gemini `generateContent` conversion.
  - Gemini response converted back to OpenAI Chat format.

### Routing, health, and circuit breaker

- Candidate scoring and ranking.
- Provider health updates after success/failure.
- Retry chain metadata.
- Persistent circuit breaker model with states:
  - `closed`
  - `open`
  - `half_open`
- Selector skips open circuit candidates until cooldown allows half-open probe.
- Router Health API exposes:
  - score
  - provider/upstream model
  - success/failure counters
  - latency stats
  - circuit state
  - availability
  - thresholds/cooldown/timestamps

### Admin APIs

Implemented under `/api/admin/*`:

- Dashboard:
  - `GET /api/admin/dashboard/summary`
- Providers:
  - CRUD.
  - API key write path.
  - API key is not returned in plaintext; response exposes `api_key_configured`.
  - Test connection.
  - Discover models.
  - List provider models.
- Unified models:
  - CRUD.
  - Candidate CRUD.
  - Duplicate candidate prevention for same unified model + provider + upstream model.
- Router health:
  - Scoring and circuit state view.
- Logs:
  - Recent request logs.
- API tokens:
  - CRUD.
  - One-time plaintext token return at creation.
  - Prefix-only listing.
  - SHA-256 token hash storage.
  - Scopes.
  - Expiry.
  - Enable/disable.
  - `last_used_at` update after successful gateway authentication.
- Settings:
  - Persistent SQLite-backed settings API.
  - Defaults seeded on startup.
- Budgets:
  - CRUD.
  - Monthly limit.
  - Spent amount.
  - Usage percentage.
  - Alert threshold.
  - Enable/disable.
- WebDAV:
  - Profile CRUD.
  - Password write-only storage through existing `secret_crypto` boundary.
  - Password not returned in list/read responses.
  - Connection test via `PROPFIND`; `mock://` succeeds for local tests.
- Agents:
  - Config CRUD.
  - Agent type, config path, backup path, notes, enable/disable.
  - Config path check; `mock://` succeeds for local tests.

## Implemented frontend pages

All major sidebar pages are now functional rather than placeholders:

- Dashboard.
- Providers.
- Unified Models.
- Model Discovery.
- Router Health.
- Logs.
- API Tokens.
- Settings.
- Budgets.
- WebDAV.
- Agents.

### Provider page

- Create provider.
- Edit provider.
- Enable/disable.
- Delete.
- API key password input.
- API key configured status tag.
- Provider type options and default base URL behavior.

### Unified Models page

- Create unified model.
- Edit unified model.
- Enable/disable.
- Delete.
- Create candidate.
- Edit candidate.
- Enable/disable candidate.
- Delete candidate.
- Set manual priority and capabilities.

### Model Discovery page

- Select provider.
- Test provider connection.
- Discover provider models.
- List discovered models.
- Select target unified model.
- Add discovered upstream model directly as a candidate.

### Router Health page

- Shows candidate score.
- Provider/upstream model.
- Success/failure counts.
- Circuit breaker state.
- Availability tag.
- Failure threshold/cooldown info.

### Logs page

- Select recent 20/50/100/200 logs.
- Refresh.
- Status tag.
- Protocol.
- Unified model.
- Provider/upstream model.
- Latency.
- Token counts.
- Error type.
- Details modal with retry chain JSON.

### API Tokens page

- Create token.
- Display plaintext token once after creation.
- Hide saved token.
- List token prefixes only.
- Scopes selection.
- Expiry selection.
- Enable/disable.
- Delete.
- Last used time.

### Settings page

- Persistent settings backed by SQLite.
- Editable:
  - listen host
  - port
  - auth enabled
  - stream failure mode
  - default timeout seconds
  - request log retention days
  - record debug request/response body flags
  - default provider type
  - default unified model
- Displays raw settings JSON.

### Budgets page

- Create budget.
- Scope options:
  - global
  - provider
  - api_token
  - unified_model
- Scope ID.
- Monthly limit.
- Spent amount.
- Currency.
- Alert threshold.
- Enable/disable.
- Usage progress bar.
- Manual spent amount sync.
- Delete.

### WebDAV page

- Create profile.
- URL / username / password input.
- Password write-only; no frontend readback.
- List profiles.
- Password configured tag.
- Enable/disable.
- Test connection.
- Clear password.
- Delete.

### Agents page

- Create Agent config.
- Agent types:
  - Claude Code
  - Gemini CLI
  - Codex CLI
  - Cursor
  - custom
- Config path.
- Backup path.
- Notes.
- Enable/disable.
- Check path.
- Record backup path.
- Delete.

## Current known caveats

- Tests and frontend build have not been run in this ChatGPT/GitHub tool environment.
- `secret_crypto` is still a placeholder encryption boundary:
  - It stores as `stage1-placeholder:<plaintext>`.
  - It should later be replaced by Windows DPAPI, OS keychain, Credential Manager, or `APISWITCH_MASTER_KEY` based encryption.
- Gateway token hashing is SHA-256 without per-token salt. For a local-first tool this may be acceptable temporarily, but production-grade storage should use stronger keyed hashing or token-only-once + high entropy + strict storage model.
- Admin APIs are currently unauthenticated. Gateway `/v1/*` is token protected, but `/api/admin/*` remains open to local network users unless deployment is restricted.
- Settings `auth_enabled` is persisted but does not currently disable or enable gateway token enforcement dynamically. The gateway auth dependency enforces tokens unconditionally.
- Budgets are CRUD-only and do not yet enforce request cost limits.
- Request cost accounting is not connected to budgets.
- WebDAV profiles are CRUD/test-only; real import/export sync is not implemented.
- Agent configs are CRUD/check-only; real backup/import/export/sync is not implemented.
- Responses streaming is not implemented.
- `/v1/models` should eventually expose unified models and/or provider models from DB instead of the simple mock registry path.
- Provider duplicate name errors may still surface as generic DB errors instead of clean 409 responses.
- Frontend pages may need TypeScript/build cleanup after `npm run build` is actually run.

## Most important next tasks

1. Run backend tests locally:

   ```powershell
   cd backend
   pytest
   ```

2. Run frontend tests/build locally:

   ```powershell
   cd frontend
   npm run test
   npm run build
   ```

3. Fix any backend failures introduced by migrations, bootstrap, or API changes.
4. Fix any frontend TypeScript/Naive UI render type issues.
5. Replace placeholder `secret_crypto` with real local encryption.
6. Implement admin authentication or local-only binding protections.
7. Connect budgets to request logs and cost accounting.
8. Implement WebDAV export/import sync for configuration and encrypted secrets.
9. Implement Agent backup/restore and WebDAV sync integration.
10. Implement Responses streaming conversion.

## Files that are especially important for the next conversation

- `README.md`
- `docs/api.md`
- `docs/development-plan.md`
- `docs/hand-off-context.md`
- `docs/conversation-archive.md`
- `backend/apiswitch/app.py`
- `backend/apiswitch/db/models.py`
- `backend/apiswitch/db/seed.py`
- `backend/apiswitch/api/deps.py`
- `backend/apiswitch/api/gateway/chat_completions.py`
- `backend/apiswitch/api/gateway/responses.py`
- `backend/apiswitch/api/gateway/messages.py`
- `backend/apiswitch/api/gateway/models.py`
- `backend/apiswitch/api/admin/`
- `backend/apiswitch/providers/`
- `backend/apiswitch/gateway/`
- `backend/apiswitch/router/`
- `frontend/src/router/index.ts`
- `frontend/src/views/`
- `frontend/src/api/`

## Suggested prompt for a new conversation

```text
请先阅读 BXXCAXCA/apiswitch 仓库中的 docs/hand-off-context.md、docs/conversation-archive.md、docs/development-plan.md、docs/api.md 和 README.md，然后继续 APISwitch 开发。默认直接提交到 main；回答用中文；不要重复询问已确定需求。优先进入质量修复阶段：跑通/修复 pytest、npm run test、npm run build，然后继续做 Responses streaming、WebDAV 同步和 Agent 备份恢复。
```
