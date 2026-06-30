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

Goal: make OpenAI Chat Completions pass through the real APISwitch routing pipeline while still using Mock Provider.

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
- Unified model CRUD endpoints
- Unified model candidate CRUD endpoints
- Admin logs API backed by SQLite
- Dashboard summary backed by request logs
- Admin router health API
- Frontend router health page connected to backend data
- Frontend provider creation form
- Frontend unified model and candidate creation forms
- Tests for provider CRUD, candidate CRUD, routed chat completions, and router health
- Isolated pytest SQLite database

Remaining:

- Expand tests around selector ranking and provider health updates
- Add provider health to circuit breaker transition logic
- Add richer edit/delete actions to frontend tables
- Add model discovery workflow before real providers

## Later milestones

1. Real OpenAI/Anthropic/Gemini providers
2. Health scoring, retry, circuit breaker
3. Responses and Anthropic Messages conversion
4. Streaming
5. Full Web UI management
6. Files, multimodal, embeddings, cache
7. WebDAV and Agent configuration
8. Security, packaging, Docker, Windows release
