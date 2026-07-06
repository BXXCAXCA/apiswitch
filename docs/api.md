# API Skeleton

## Gateway

All `/v1/*` gateway endpoints require `Authorization: Bearer <api_token>`.

Create an API token from the Web UI or `POST /api/admin/tokens`. The plaintext token is returned only once.

- `POST /v1/chat/completions`
  - Supports non-streaming JSON responses.
  - Supports `stream=true` with `text/event-stream` OpenAI-compatible SSE output.
  - Routes unified model names to candidate upstream models through APISwitch.
- `POST /v1/responses`
  - Supports non-streaming OpenAI Responses-compatible JSON responses.
  - Converts Responses input to Chat Completions internally, then routes through APISwitch.
  - `stream=true` is currently rejected with `responses_streaming_not_implemented`.
- `POST /v1/messages`
  - Supports non-streaming Anthropic Messages-compatible JSON responses.
  - Routes unified model names to candidate upstream models through APISwitch.
- `GET /v1/models`

## Admin

### Dashboard

- `GET /api/admin/dashboard/summary`

### Providers

- `GET /api/admin/providers`
- `POST /api/admin/providers`
- `GET /api/admin/providers/{provider_id}`
- `PATCH /api/admin/providers/{provider_id}`
- `DELETE /api/admin/providers/{provider_id}`
- `POST /api/admin/providers/{provider_id}/test`
- `POST /api/admin/providers/{provider_id}/discover-models`
- `GET /api/admin/providers/{provider_id}/models`

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

### Logs

- `GET /api/admin/logs`

### API Tokens

- `GET /api/admin/tokens`
- `POST /api/admin/tokens`
  - Returns the plaintext token only once at creation time.
- `PATCH /api/admin/tokens/{token_id}`
- `DELETE /api/admin/tokens/{token_id}`

### Budgets

- `GET /api/admin/budgets`
- `POST /api/admin/budgets`
- `PATCH /api/admin/budgets/{budget_id}`
- `DELETE /api/admin/budgets/{budget_id}`

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

### Settings

- `GET /api/admin/settings`
- `PATCH /api/admin/settings`
