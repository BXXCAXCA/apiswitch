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

Goal: stabilize the existing unified-model gateway and control panel before expanding the provider and protocol surface.

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
- Agent config admin API with config path checks, enable/disable, backup path tracking, notes, and delete
- Frontend Agent config management page
- Claude Code profile preview/write support with backup and safe profile path validation
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
- Tests for provider CRUD, API Key behavior, API tokens, budgets, WebDAV, agents, Claude Code profiles, gateway auth, persistent settings, provider discovery, duplicate candidates, routed chat completions, streaming chat completions, Responses, Anthropic Messages, Gemini conversion, circuit breaker transitions, and router health
- Isolated pytest SQLite database

Remaining stabilization work:

- Add Responses streaming conversion
- Replace placeholder secret encryption
- Add Admin API authentication or strict local-only protection
- Connect Agent configs to real import/export backup workflows
- Connect WebDAV to real import/export sync workflows
- Connect budgets to real request cost accounting and enforcement

Validation completed on 2026-07-11:

- Backend `pytest backend/tests -q`: 60 passed.
- Frontend `npm run test`: 2 passed.
- Frontend `npm run build`: passed.
- Frontend dependencies are now version-bounded and locked in `frontend/package-lock.json`; use Node 22 LTS or Node 24+ for CI and releases.

## v0.3.0-unified-auto-routing

Status: foundation started.

Goal: retain Unified Model as the stable client-facing abstraction while adding multi-account Provider Connections, Provider Nodes, Auto-Combo routing, pricing, quotas, usage history, and session affinity.

Foundation completed:

- `provider_connections` database model and migration
- `provider_nodes` database model and migration
- `model_pricing` database model and migration
- `quota_snapshots` database model and migration
- `usage_history` database model and migration
- `session_affinity` database model and migration
- OmniRoute-inspired architecture roadmap documented in `docs/omniroute-inspired-roadmap.md`
- Unified-model candidates can bind to a specific Provider Connection and Provider Node.
- Gateway execution resolves the selected account credential and node endpoint; request logs and usage history retain the connection identity.
- Unified Models expose `static`, `combo`, and `auto` mode configuration. `auto` materializes enabled provider-model/account/node tuples into durable candidates so their health and circuit-breaker history remains auditable.
- Combo dispatch supports priority, weighted rotation, round robin, least used, cost optimized, quota headroom, and last known good ordering.
- Budget scopes now accumulate actual estimated request costs and enforce `warn_only`, `reject`, `fallback_to_free`, or `fallback_to_cheapest` behavior before gateway execution.
- OpenAI-style, compatible, Gemini, and Anthropic adapters normalize common rate-limit headers into Connection-level Quota Snapshots after successful calls.

Planned Provider work:

- Provider Catalog with auth methods, protocols, free-tier metadata, and default endpoints
- Provider Connection CRUD for API Key, OAuth, and anonymous connections
- Provider Node CRUD for region, proxy, endpoint, and weight management
- Legacy Provider credential migration to a default Provider Connection
- Initial high-value Provider expansion: Azure OpenAI, Vertex AI, Bedrock, OpenRouter, xAI, Mistral, Cohere, DeepSeek, Groq, Together, Fireworks, SiliconFlow, Qwen, GLM, Kimi, Doubao, and MiniMax
- Selected OAuth flows rather than implementing OAuth for every Provider

Planned routing work:

- Unified Model routing modes: `static`, `combo`, and `auto`
- Compact strategy set: priority, weighted, round-robin, least-used, cost-optimized, quota-headroom, and last-known-good
- Dynamic Auto-Combo candidate pool generated from available Connections and Nodes
- Category and tier constraints inside Unified Models
- Session affinity / last-known-good routing
- Eight-factor explainable score: health, quota, cost, latency, task fit, context fit, stability, and manual priority
- Request controls: `X-APISwitch-Budget`, `X-APISwitch-Session`, and `X-APISwitch-Tier`

Planned accounting work:

- Pricing catalog and manual overrides
- Token accounting
- Usage history aggregation
- Provider quota polling and snapshots
- Automatic budget accumulation and enforcement
- Budget behaviors: reject, fallback-to-free, fallback-to-cheapest, or warn-only

## v0.4.0-protocol-expansion

Status: planned.

Protocol order:

1. Responses streaming
2. Embeddings
3. Gemini `v1beta`
4. WebSocket bridge
5. Files
6. Images generations and edits
7. Audio speech and transcriptions
8. Moderations
9. Rerank
10. Search
11. Batches
12. Video
13. Music

All protocol handlers must translate into a shared internal request/response model and route through a Unified Model.

## Later milestones

1. Docker and Windows desktop/tray packaging
2. Real WebDAV configuration sync and conflict resolution
3. Agent backup/restore and one-click CLI configuration
4. Files, multimodal processing, caches, and optional memory
5. Security hardening, CI, release automation, and documentation validation
