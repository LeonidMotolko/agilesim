# AgileSim

Web platform for Agile simulations (Startup Flow, LegoScrum) - diploma project.

## Repository layout

| Path | Contents |
| --- | --- |
| `backend/` | FastAPI service and the simulation rule engine (Python 3.13, [uv](https://docs.astral.sh/uv/)) |
| `frontend/` | React + TypeScript single-page app (Vite, pnpm) |
| `docker-compose.yml` | The whole stack: PostgreSQL, backend, frontend |
| `db/init/` | PostgreSQL first-start script: creates the limited login role of the API |
| `docs/` | [Database documentation](docs/database.md): ER diagram, data dictionary, roles, indexes |
| `.github/workflows/` | CI: one workflow per component plus a Compose smoke test |

Branching model, commit rules and quality gates: see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quick start (Docker)

```bash
cp .env.example .env      # then set POSTGRES_PASSWORD and POSTGRES_APP_PASSWORD
docker compose up --build
```

The backend container applies the database migrations (as the schema owner) and then starts the
API as the limited role `agilesim_app`, which is not a superuser. The `db/init/` script runs only
when the data volume is created; after changing `POSTGRES_APP_PASSWORD` run
`docker compose down --volumes` first.

| Service | URL |
| --- | --- |
| App | http://localhost:8080 |
| API (direct) | http://localhost:8000/health, `/health/db` (database readiness), docs at http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` |

The app proxies `/api/*` to the backend, so `http://localhost:8080/api/health` reaches the same endpoint.

## Local development without Docker

```bash
# backend (PostgreSQL 17 must be running)
cd backend
uv sync
export AGILESIM_MIGRATION_DATABASE_URL=postgresql://owner:password@localhost:5432/agilesim
export AGILESIM_DATABASE_URL=postgresql://agilesim_app:password@localhost:5432/agilesim
uv run python -m agilesim.db.migrate            # create / update the schema
uv run uvicorn agilesim.main:app --reload      # http://localhost:8000
export AGILESIM_TEST_DATABASE_URL=postgresql://owner:password@localhost:5432/agilesim_test
uv run pytest                                   # database tests are skipped without the test URL
uv run ruff check . && uv run ruff format --check . && uv run ty check

# frontend (in another terminal)
cd frontend
pnpm install
pnpm dev                                        # http://localhost:5173, /api is proxied to :8000
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test
```
