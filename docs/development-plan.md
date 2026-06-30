# APISwitch Development Plan

## v0.1.0-skeleton

Status: completed.

Goal: establish a runnable, testable skeleton before real provider integrations.

Deliverables:

- FastAPI backend
- Vue 3 + Naive UI frontend
- SQLite + SQLAlchemy + Alembic
- Gateway-compatible Mock APIs
- Admin Mock APIs
- Provider registry and Mock Provider
- Router scoring and circuit-breaker skeleton
- Baseline tests

## v0.2.0-core-gateway

Status: in progress.

Goal: make OpenAI Chat Completions and Anthropic Messages pass through the real APISwitch routing pipeline while supporting Mock, OpenAI, OpenAI-Compatible, Anthropic, and Gemini providers.

Completed:

- Database bootstrap and seed data for `mock-main`, `mock-chat`, and `code-best`
- Unified-model candidate selector and ranked candidate list
- Gateway error types
- Request log persistence for `/v1/chat/completions`
- Provider health updates after candidate success/failure
- Retry chain across enabled ranked candidates
- Admin providers API backed by SQLite
- Admin unified models API backed by SQLite
- Provider CRUD endpoints
- Provider API Key write path with non-plaintext read responses
- Unified model CRUD endpoints
- Unified model candidate CRUD endpoints
- Provider connection test API
- Provider model discovery and ProviderModel sync
- OpenAI Provider adapter for `/models`, non-streaming `/chat/completions`, and streaming `/chat/completions`
- OpenAI-Compatible adapter for `/models`, non-streaming `/chat/completions`, and streaming `/chat/completions`
- Anthropic Provider adapter for static Claude model discovery and non-streaming `/messages`
- Gemini Provider adapter for model discovery and OpenAI Chat to Gemini `generateContent` conversion
- Gemini response conversion back to OpenAI Chat Completions format
- Mock Provider streaming Chat Completions and Anthropic Messages
- Gateway streaming execution for `stream=true`
- Gateway execution for Anthropic Messages
- SSE model-name rewrite while tracking actual upstream model in APISwitch metadata
- Gateway execution from database Provider config and candidate upstream model
- Client response model preservation while tracking actual upstream model in `apiswitch.upstream_model`
- Admin logs API backed by SQLite
- Dashboard summary backed by request logs
- Admin router health API
- Frontend router health page connected to backend data
- Frontend model discovery page connected to backend data
- Frontend provider creation form with API Key input and provider defaults
- Frontend unified model and candidate creation forms
- Tests for provider CRUD, API Key behavior, provider discovery, routed chat completions, streaming chat completions, Anthropic Messages, Gemini conversion, and router health
- Isolated pytest SQLite database

Remaining:

- Expand tests around selector ranking and provider health updates
- Add provider health to circuit breaker transition logic
- Add richer edit/delete actions to frontend tables
- Add Responses protocol conversion

## Later milestones

1. Health scoring, retry, circuit breaker
2. Responses protocol conversion
3. Full Web UI management
4. Files, multimodal, embeddings, cache
5. WebDAV and Agent configuration
6. Security, packaging, Docker, Windows release
