# APISwitch API

## Gateway authentication

All Gateway endpoints require:

```http
Authorization: Bearer <api_token>
```

Create an API token from the Web UI or `POST /api/admin/tokens`. The plaintext token is returned only once.

## Unified routing controls

The current text and embedding endpoints support optional per-request controls:

- `X-APISwitch-Tier`
  - `balanced`
  - `fast`
  - `cheap`
  - `free`
  - `quality`
  - `reliable`
- `X-APISwitch-Budget`
  - Positive maximum estimated request cost in USD.
  - Candidates without pricing are excluded when a hard request budget is supplied.
- `X-APISwitch-Session`
  - Session affinity key.
  - APISwitch remembers the last successful candidate for that Unified Model and session.

These controls refine routing inside a Unified Model. They do not bypass the Unified Model abstraction.

## Gateway endpoints

### OpenAI Chat Completions

- `POST /v1/chat/completions`
  - Non-streaming JSON.
  - `stream=true` OpenAI-compatible SSE.
  - Unified Model routing, retry chain, Circuit Breaker, Tier, request budget, and session affinity.

### OpenAI Responses

- `POST /v1/responses`
  - Non-streaming Responses-compatible JSON and Responses SSE when `stream=true`.
  - Converts Responses input to the shared Chat execution path.
  - Streaming emits lifecycle and `response.output_text.delta` events.

### Anthropic Messages

- `POST /v1/messages`
  - Non-streaming Anthropic Messages-compatible JSON.
  - Unified Model routing and request controls.

### Embeddings

- `POST /v1/embeddings`
  - OpenAI-compatible Embeddings request/response.
  - Supports `float` and `base64` encoding formats when the selected Provider supports them.
  - Implemented by Mock, OpenAI, and OpenAI-Compatible adapters.
  - Default development Unified Model: `embedding-best`.

### Gemini v1beta

- `POST /v1beta/models/{unified_model}:generateContent`
  - Converts Gemini `contents`, `systemInstruction`, and `generationConfig` to the shared Chat execution path.
  - Returns a Gemini-compatible `candidates` and `usageMetadata` response.

### Models

- `GET /v1/models`

## Planned protocol expansion

- WebSocket bridge
- Files
- Images generations / edits
- Audio speech / transcriptions
- Moderations
- Rerank
- Search
- Batches
- Video
- Music

See `docs/omniroute-inspired-roadmap.md` for the phased implementation order.

## Admin endpoints

### Dashboard

- `GET /api/admin/dashboard/summary`

### Provider Catalog

- `GET /api/admin/provider-catalog`
- `GET /api/admin/provider-catalog/{provider_type}`

The Catalog distinguishes native adapters, generic OpenAI-Compatible adapters, and planned dedicated adapters.

### Providers

- `GET /api/admin/providers`
- `POST /api/admin/providers`
- `GET /api/admin/providers/{provider_id}`
- `PATCH /api/admin/providers/{provider_id}`
- `DELETE /api/admin/providers/{provider_id}`
- `POST /api/admin/providers/{provider_id}/test`
- `POST /api/admin/providers/{provider_id}/discover-models`
- `GET /api/admin/providers/{provider_id}/models`

### Provider Connections

- `GET /api/admin/providers/{provider_id}/connections`
- `POST /api/admin/providers/{provider_id}/connections`
- `PATCH /api/admin/providers/{provider_id}/connections/{connection_id}`
- `DELETE /api/admin/providers/{provider_id}/connections/{connection_id}`

Credentials and Refresh Tokens are write-only and never returned by the API.

### Provider Nodes

- `GET /api/admin/providers/{provider_id}/nodes`
- `POST /api/admin/providers/{provider_id}/nodes`
- `PATCH /api/admin/providers/{provider_id}/nodes/{node_id}`
- `DELETE /api/admin/providers/{provider_id}/nodes/{node_id}`

### Pricing, quota, and usage

- `GET /api/admin/accounting/pricing`
- `POST /api/admin/accounting/pricing`
- `PATCH /api/admin/accounting/pricing/{pricing_id}`
- `DELETE /api/admin/accounting/pricing/{pricing_id}`
- `GET /api/admin/accounting/quota-snapshots`
- `POST /api/admin/accounting/quota-snapshots`
- `GET /api/admin/accounting/usage`
- `GET /api/admin/accounting/usage/summary`

Successful non-streaming Chat, Responses, Messages, and Embeddings requests write Usage History. Streaming usage accounting is still pending because SSE usage aggregation is not implemented yet.

### Unified Models

- `GET /api/admin/unified-models`
- `POST /api/admin/unified-models`
- `GET /api/admin/unified-models/{model_id}`
- `PATCH /api/admin/unified-models/{model_id}`
- `DELETE /api/admin/unified-models/{model_id}`
- `GET /api/admin/unified-models/{model_id}/candidates`
- `POST /api/admin/unified-models/{model_id}/candidates`
- `PATCH /api/admin/unified-models/{model_id}/candidates/{candidate_id}`
- `DELETE /api/admin/unified-models/{model_id}/candidates/{candidate_id}`

### Router Health

- `GET /api/admin/router-health`
  - Includes the explainable score breakdown.

### Logs

- `GET /api/admin/logs`

### API Tokens

- `GET /api/admin/tokens`
- `POST /api/admin/tokens`
- `PATCH /api/admin/tokens/{token_id}`
- `DELETE /api/admin/tokens/{token_id}`

### Budgets

- `GET /api/admin/budgets`
- `POST /api/admin/budgets`
- `PATCH /api/admin/budgets/{budget_id}`
- `DELETE /api/admin/budgets/{budget_id}`

Budget CRUD exists. Automatic monthly budget accumulation and enforcement are still pending; per-request hard budget filtering is implemented through `X-APISwitch-Budget`.

### WebDAV

- `GET /api/admin/webdav`
- `POST /api/admin/webdav`
- `PATCH /api/admin/webdav/{profile_id}`
- `DELETE /api/admin/webdav/{profile_id}`
- `POST /api/admin/webdav/{profile_id}/test`

### Agents

- `GET /api/admin/agents`
- `POST /api/admin/agents`
- `PATCH /api/admin/agents/{agent_id}`
- `DELETE /api/admin/agents/{agent_id}`
- `POST /api/admin/agents/{agent_id}/check`
- `POST /api/admin/agents/claude-code/write`
  - Preview or write an isolated Claude Code Profile.
  - Back up an existing `settings.json`.
  - Never write `ANTHROPIC_AUTH_TOKEN` to disk.

### Settings

- `GET /api/admin/settings`
- `PATCH /api/admin/settings`
