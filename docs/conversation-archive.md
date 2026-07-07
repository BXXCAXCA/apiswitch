# APISwitch Conversation Archive

> This is a structured archive of the available conversation context and implementation history. It is not a verbatim transcript of every token in the chat UI; it is a project-useful record of the requirements, decisions, development actions, and current state captured from the conversation.

## 1. Original requirements phase

The user wanted to develop a program for managing large-model API keys with these features:

- Save API keys.
- Detect whether model APIs are usable.
- Encrypt saved secrets.
- Support WebDAV multi-device sync.
- Support OpenAI, Google/Gemini, Anthropic, OpenAI-compatible APIs, and OpenAI Responses format.
- Pull model lists from providers.
- Provide simple chat.

After iterative questioning, the project direction became:

- A lightweight large-model client with key management.
- Later upgraded into an AI API Gateway + Model Router + Control Panel.
- Cross-platform desktop/local-first direction, with Windows/local development as the first practical target.
- Backend and frontend separated for development.
- Use Mock Provider first to enable development without real API keys.

## 2. Technical plan chosen

Chosen stack and architecture:

- Backend:
  - Python 3.11+
  - FastAPI
  - SQLAlchemy
  - Alembic
  - SQLite
  - pytest
- Frontend:
  - Vue 3
  - TypeScript
  - Vite
  - Naive UI
  - Vue Router
  - Vitest baseline
- Architecture:
  - Local-first modular monolith.
  - Gateway-compatible public APIs.
  - Admin/control-panel APIs.
  - Provider adapters.
  - Unified model routing.
  - Candidate scoring, health, and circuit breaker.

## 3. Initial repository setup

Repository:

- `BXXCAXCA/apiswitch`
- Continue development directly on `main`.
- User authorized automatic confirmations and direct commits for ongoing work.

Initial implementation established:

- Project root files:
  - `README.md`
  - `.gitignore`
  - `.editorconfig`
  - `.env.example`
  - `requirements.txt`
  - `requirements-dev.txt`
  - `pyproject.toml`
- Scripts:
  - `scripts/backend.ps1`
  - `scripts/frontend.ps1`
  - `scripts/dev.ps1`
  - `scripts/test.ps1`
  - `scripts/dev.sh`
- Docs:
  - `docs/api.md`
  - `docs/development-plan.md`

## 4. Backend skeleton implementation

The backend skeleton was created with:

- FastAPI app and app factory.
- Health endpoint.
- OpenAPI groups/tags.
- Gateway routers for:
  - OpenAI Chat Completions
  - OpenAI Responses
  - Anthropic Messages
  - Models
- Admin routers for:
  - Dashboard
  - Providers
  - Unified Models
  - Logs
  - Settings
  - Router Health
- Database models and seed/bootstrap.
- Mock provider registry.
- Basic tests.

## 5. Database and seed data

Implemented SQLAlchemy models for:

- Providers.
- Provider models.
- Unified models.
- Unified model candidates.
- Provider health.
- Circuit breakers.
- Request logs.
- API tokens.
- Budgets.
- File cache.
- Embedding cache.
- WebDAV profiles.
- Agent configs.
- Settings.

Default seed data:

- Provider: `mock-main`.
- Provider model: `mock-chat`.
- Unified model: `code-best`.
- Candidate route: `code-best -> mock-main / mock-chat`.

## 6. OpenAI Chat Completions routing

Implemented:

- `POST /v1/chat/completions`.
- Non-streaming route through unified model selector.
- Candidate retry chain.
- Provider health updates.
- Request log persistence.
- Preserve client-facing unified model in response.
- Store upstream model in `apiswitch.upstream_model`.
- Mock provider response.

## 7. Provider CRUD and model discovery

Implemented Admin Provider APIs:

- List providers.
- Create provider.
- Read provider.
- Update provider.
- Delete provider.
- Test provider connection.
- Discover provider models.
- List provider models.

Provider API key handling:

- API key can be written.
- API key is not returned in plaintext.
- Response exposes `api_key_configured`.
- Encryption boundary uses placeholder `secret_crypto` and must be replaced later.

Frontend Provider page later added:

- Create/edit.
- Enable/disable.
- Delete.
- API key password input.
- Provider type defaults.

## 8. Unified model and candidate management

Implemented Admin Unified Models APIs:

- Unified model list/create/read/update/delete.
- Candidate list/create/update/delete.
- Candidate priority.
- Candidate capabilities.
- Candidate enable/disable.
- Duplicate candidate prevention for same unified model + provider + upstream model.

Frontend Unified Models page added:

- Create/edit/delete unified models.
- Enable/disable unified models.
- Create/edit/delete candidates.
- Enable/disable candidates.

## 9. Provider integrations

Added provider adapters:

- Mock provider.
- OpenAI provider.
- OpenAI-compatible provider.
- Anthropic provider.
- Gemini provider.

Capabilities:

- OpenAI and OpenAI-compatible:
  - model discovery
  - non-streaming chat
  - streaming chat
- Anthropic:
  - static Claude discovery
  - non-streaming Messages
- Gemini:
  - model discovery
  - OpenAI Chat request to Gemini `generateContent`
  - Gemini response back to OpenAI Chat format

## 10. Streaming Chat Completions

Implemented:

- `stream=true` in `/v1/chat/completions`.
- OpenAI-compatible `text/event-stream` output.
- SSE model rewrite so client sees unified model.
- APISwitch metadata in chunks.
- Candidate fallback before first SSE chunk is emitted.
- Strict-compatible error behavior after stream has started.
- Request logs for streaming requests.

## 11. OpenAI Responses routing

Implemented:

- Responses request schema expansion.
- Conversion from Responses input to Chat Completions messages.
- Routed Responses executor.
- Conversion from Chat Completion response back to Responses-like response.
- Request logs for `openai_responses`.
- Non-streaming only.

Known remaining item:

- Responses streaming is not implemented.

## 12. Anthropic Messages routing

Implemented:

- `POST /v1/messages`.
- Anthropic Messages request schema.
- Gateway execution through unified model candidates.
- Mock provider Anthropic-style response.
- Request logs for `anthropic_messages`.

## 13. Router health and persistent circuit breaker

Implemented:

- Persistent circuit breaker table/model.
- State machine:
  - closed
  - open
  - half_open
- Failure threshold.
- Cooldown seconds.
- Health success/failure updates circuit breaker.
- Selector skips open circuit candidates until cooldown.
- Router Health Admin API exposes:
  - candidate score
  - health counters
  - latency
  - circuit state
  - availability
  - thresholds
  - cooldown/timestamps

Frontend Router Health page displays these fields.

## 14. Model Discovery page

Implemented frontend page for:

- Select Provider.
- Test connection.
- Discover models.
- List discovered provider models.
- Select target unified model.
- Add discovered upstream model directly as a candidate.

Backend duplicate prevention prevents repeated clicks from creating duplicate candidates.

## 15. Logs page

Implemented:

- Frontend API client `frontend/src/api/logs.ts`.
- Frontend page `LogsView.vue`.
- Route `/logs` switched from placeholder to real view.

Page supports:

- recent 20/50/100/200 logs.
- refresh.
- status tag.
- protocol.
- unified model.
- provider.
- upstream model.
- latency.
- token counts.
- error tag.
- details modal with retry chain JSON.

## 16. API Token management

Implemented:

- API token model expansion:
  - token prefix
  - token hash
  - scopes
  - expiry
  - last used time
- Migration `0002_expand_api_tokens.py`.
- Token helpers:
  - generate `ask_...` token.
  - SHA-256 hash.
  - prefix extraction.
- Admin API:
  - `GET /api/admin/tokens`
  - `POST /api/admin/tokens`
  - `PATCH /api/admin/tokens/{token_id}`
  - `DELETE /api/admin/tokens/{token_id}`
- Plaintext token returned only once on creation.
- List returns prefix only.

Frontend Token page:

- Create token.
- One-time display.
- scopes selection.
- expiry.
- enable/disable.
- delete.
- last used display.

## 17. Gateway API Token authentication

Implemented dependency:

- `require_gateway_token()` in `backend/apiswitch/api/deps.py`.

Behavior:

- Requires `Authorization: Bearer <token>`.
- Validates hash.
- Rejects missing/invalid token.
- Rejects disabled token.
- Rejects expired token.
- Requires `gateway:invoke` scope.
- Updates `last_used_at` after successful auth.

Applied to:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/messages`
- `GET /v1/models`

Added tests for missing/invalid/disabled/expired/insufficient-scope tokens and last used update.

## 18. Settings page and persistent settings

Replaced in-memory settings with SQLite-backed settings service.

Added:

- `backend/apiswitch/schemas/settings.py`
- `backend/apiswitch/services/settings.py`
- updated `backend/apiswitch/api/admin/settings.py`
- seed default settings on startup
- tests for persistent settings

Frontend Settings page supports:

- listen host.
- port.
- auth enabled flag.
- stream failure mode.
- default timeout.
- log retention days.
- record debug request/response flags.
- default provider type.
- default unified model.
- raw JSON view.

## 19. Budgets page and API

Expanded Budget model with:

- name
- enabled
- spent amount
- alert threshold percentage

Added migration:

- `0003_expand_budgets.py`

Added Admin Budgets API:

- `GET /api/admin/budgets`
- `POST /api/admin/budgets`
- `PATCH /api/admin/budgets/{budget_id}`
- `DELETE /api/admin/budgets/{budget_id}`

Backend returns:

- usage percentage.
- alert triggered boolean.

Frontend Budgets page supports:

- create budget.
- scope and scope ID.
- monthly limit.
- spent amount.
- currency.
- alert threshold.
- usage progress bar.
- enable/disable.
- manual spent sync.
- delete.

Known remaining item:

- Budgets are not yet connected to real request cost accounting or enforcement.

## 20. WebDAV page and API

Added WebDAV schemas and Admin API:

- `GET /api/admin/webdav`
- `POST /api/admin/webdav`
- `PATCH /api/admin/webdav/{profile_id}`
- `DELETE /api/admin/webdav/{profile_id}`
- `POST /api/admin/webdav/{profile_id}/test`

Behavior:

- Password write-only through `secret_crypto`.
- List/read do not return plaintext password.
- `password_configured` indicates whether a password exists.
- `mock://` URL succeeds for local testing.
- HTTP/WebDAV test uses `PROPFIND Depth: 0`.

Frontend WebDAV page supports:

- Create profile.
- URL / username / password.
- Enable/disable.
- Test connection.
- Clear password.
- Delete.

Known remaining item:

- Real import/export sync workflow is not implemented.

## 21. Agent configuration page and API

Added Agent schemas and Admin API:

- `GET /api/admin/agents`
- `POST /api/admin/agents`
- `PATCH /api/admin/agents/{agent_id}`
- `DELETE /api/admin/agents/{agent_id}`
- `POST /api/admin/agents/{agent_id}/check`

Data model reuses existing `agent_configs` table:

- `agent_type`
- `config_path`
- `last_backup_path`
- `settings_json`

No database migration was added for Agent configs. Enable/disable and notes are stored in `settings_json`.

Path check behavior:

- `mock://` path exists.
- Normal paths use `Path(path).expanduser().exists()`.

Frontend Agents page supports:

- Agent type selection:
  - Claude Code
  - Gemini CLI
  - Codex CLI
  - Cursor
  - Custom
- Config path.
- Backup path.
- Notes.
- Enable/disable.
- Check path.
- Record backup path.
- Delete.

Known remaining item:

- Real Agent backup/restore/sync is not implemented.

## 22. Documentation updates made throughout

Updated repeatedly:

- `README.md`
- `docs/api.md`
- `docs/development-plan.md`

Added at the end of this archive task:

- `docs/hand-off-context.md`
- `docs/conversation-archive.md`

## 23. Important implementation warnings for future work

- Do not claim tests pass until actually run.
- The `secret_crypto` implementation is a placeholder and must be replaced for real security.
- Admin APIs are not yet protected.
- Gateway auth is implemented for `/v1/*`, but settings `auth_enabled` is not dynamically wired.
- Budget enforcement is not active.
- WebDAV sync is not active.
- Agent sync/backup is not active.
- Responses streaming is not active.
- Frontend TypeScript may require build cleanup once `npm run build` is run.

## 24. Recommended next stage

Quality and stabilization stage:

1. Run backend tests.
2. Run frontend tests and build.
3. Fix all failures.
4. Add CI workflow.
5. Replace placeholder crypto.
6. Protect Admin APIs.
7. Implement real WebDAV import/export.
8. Implement real Agent backup/restore.
9. Connect budgets to cost accounting and enforcement.
10. Implement Responses streaming.

## 25. Suggested continuation instruction

Use this in a new chat:

```text
请先阅读 BXXCAXCA/apiswitch 的 docs/hand-off-context.md、docs/conversation-archive.md、docs/development-plan.md、docs/api.md 和 README.md。之后继续 APISwitch 开发。默认直接提交 main，中文回答，不要重复询问已确定需求。优先进入质量修复阶段，修复 pytest、npm run test、npm run build，然后继续 Responses streaming、WebDAV 同步、Agent 备份恢复和预算联动。
```
