@echo off
cd /d "%~dp0..\backend"
set LPG_ENVIRONMENT=local
set LPG_DATABASE_URL=postgresql+asyncpg://lpg_app:dev123@localhost:5433/lpg_dev
set LPG_REDIS_URL=redis://localhost:56379/0
set LPG_CORS_ORIGINS=http://localhost:4200
rem Sign-in keys are never stored here (this repository is public). They come
rem from backend\.env; without any, a local run makes a throwaway pair.
uv run uvicorn lpg.api.app:app --host 0.0.0.0 --port 8000 --reload
