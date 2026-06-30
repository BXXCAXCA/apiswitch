# APISwitch Development Plan

## v0.1.0-skeleton

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

## Later milestones

1. Core OpenAI Chat Completions route
2. Real OpenAI/Anthropic/Gemini providers
3. Health scoring, retry, circuit breaker
4. Responses and Anthropic Messages conversion
5. Streaming
6. Full Web UI management
7. Files, multimodal, embeddings, cache
8. WebDAV and Agent configuration
9. Security, packaging, Docker, Windows release
