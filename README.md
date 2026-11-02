# AgileSim

Web platform for Agile simulations (Startup Flow, LegoScrum) - diploma project.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI service and the simulation rule engine (Python 3.13, [uv](https://docs.astral.sh/uv/)) |
| `frontend/` | React + TypeScript single-page app (Vite, pnpm) |
| `docker-compose.yml` | The whole stack: PostgreSQL, backend, frontend |
| `.github/workflows/` | CI: one workflow per component plus a Compose smoke test |

Branching model, commit rules and quality gates: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start (Docker)

```bash
cp .env.example .env      # then set POSTGRES_PASSWORD
docker compose up --build
```

| Service | URL |
| --- | --- |
| App | http://localhost:8080 |
| API (direct) | http://localhost:8000/health, docs at http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` |

The app proxies `/api/*` to the backend, so `http://localhost:8080/api/health` reaches the same endpoint.

## Local development without Docker

```bash
# backend
cd backend
uv sync
uv run uvicorn agilesim.main:app --reload      # http://localhost:8000
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run ty check

# frontend (in another terminal)
cd frontend
pnpm install
pnpm dev                                        # http://localhost:5173, /api is proxied to :8000
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test
```
