# Windows Development Runbook

## Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r ..\requirements.txt -r ..\requirements-dev.txt
alembic upgrade head
python -m apiswitch
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

## One-click development

```powershell
.\scripts\dev.ps1
```
