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

Goal: make OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages pass through the real APISwitch routing pipeline while supporting Mock, OpenAI, OpenAI-Compatible, Anthropic, and Gemini providers.

Completed:

- Database bootstrap and seed data for `mock-main`, `mock-chat`, and `code-best`
- Unified-model candidate selector and ranked candidate list
- Gateway error types
- Request log persistence for `/v1/chat/completions`
- Provider health updates after candidate success/failure
- Retry chain across enabled ranked candidates
- Persistent circuit breaker state machine with `closed`, `open`, and `half_open`
- Circuit breaker updates from Provider Health success/failure events
- Candidate selector skips open circuit candidates until cooldown allows half-open probing
- Router Health API exposes circuit state, availability, thresholds, and cooldown timestamps
- Frontend Router Health page displays circuit state and availability
- Admin providers API backed by SQLite
- Admin unified models API backed by SQLite
- Provider CRUD endpoints
- Provider API Key write path with non-plaintext read responses
- API Token admin API with one-time plaintext token return, prefix-only listing, scopes, expiry, enable/disable, and delete
- Gateway API Token authentication on public `/v1/*` endpoints
- Gateway token enabled-state, expiry, and `gateway:invoke` scope checks
- Gateway token `last_used_at` update after successful authentication
- Budget admin API with monthly limit, spent amount, usage percentage, alert threshold, enable/disable, and delete
- Frontend budget management page
- WebDAV profile admin API with password write-only storage and connection testing
- Frontend WebDAV profile management page
- Persistent system settings API backed by SQLite
- Frontend system settings page
- Frontend API Token management page
- Unified model CRUD endpoints
- Unified model candidate CRUD endpoints
- Duplicate unified-model candidate prevention
- Frontend Provider create, edit, enable/disable, and delete actions
- Frontend unified model create, edit, enable/disable, and delete actions
- Frontend candidate create, edit, enable/disable, and delete actions
- Frontend model discovery page can add discovered upstream models directly as candidates
- Frontend request logs page with status, protocol, provider, latency, tokens, errors, and retry-chain details
- Provider connection test API
- Provider model discovery and ProviderModel sync
- OpenAI Provider adapter for `/models`, non-streaming `/chat/completions`, and streaming `/chat/completions`
- OpenAI-Compatible adapter for `/models`, non-streaming `/chat/completions`, and streaming `/chat/completions`
- Anthropic Provider adapter for static Claude model discovery and non-streaming `/messages`
- Gemini Provider adapter for model discovery and OpenAI Chat to Gemini `generateContent` conversion
- Gemini response conversion back to OpenAI Chat Completions format
- Mock Provider streaming Chat Completions and Anthropic Messages
- Gateway streaming execution for `stream=true`
- Streaming candidate fallback before the first SSE chunk is sent
- Strict-compatible streaming failure handling once SSE output has started
- Gateway execution for Anthropic Messages
- OpenAI Responses input conversion to Chat Completions
- OpenAI Responses non-streaming gateway execution and response conversion
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
- Tests for provider CRUD, API Key behavior, API tokens, budgets, WebDAV, gateway auth, persistent settings, provider discovery, duplicate candidates, routed chat completions, streaming chat completions, Responses, Anthropic Messages, Gemini conversion, circuit breaker transitions, and router health
- Isolated pytest SQLite database

Remaining:

- Expand tests around selector ranking edge cases
- Add Responses streaming conversion
- Add UI page for agents
- Connect WebDAV to real import/export sync workflows
- Connect budgets to real request cost accounting and enforcement

## Later milestones

1. Full Web UI management
2. Files, multimodal, embeddings, cache
3. WebDAV and Agent configuration
4. Security, packaging, Docker, Windows release
