# APISwitch

APISwitch is a local-first AI API gateway and model router.

Current milestone: `v0.1.0-skeleton`.

## Tech stack

- Backend: Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite
- Frontend: Vue 3, TypeScript, Vite, Pinia, Vue Router, Naive UI
- First-stage provider: Mock Provider

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
```

## First-stage scope

The skeleton provides:

- FastAPI app and OpenAPI groups
- SQLite, SQLAlchemy models, Alembic migration
- OpenAI/Responses/Anthropic-compatible endpoint skeletons
- Mock Provider and provider registry
- Router scoring and circuit-breaker skeleton
- Admin Mock APIs for Web UI
- Vue 3 + Naive UI admin shell
- Backend pytest and frontend Vitest baseline

The first implementation intentionally uses a Mock Provider so routing, UI, persistence, and tests can be validated before real upstream API integrations are added.
