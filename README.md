# POC-BASE

Multi-tenant authentication and workspace management API (FastAPI, SQLAlchemy, PostgreSQL, Redis).

## UV

This project uses [uv](https://docs.astral.sh/uv/) for Python and dependencies (see `pyproject.toml`, lockfile `uv.lock`). Requires **Python 3.14+** (`.python-version`).

| Command | Purpose |
|---------|---------|
| `uv sync` | Install runtime dependencies |
| `uv sync --group dev` | Include dev tools (pytest, httpx, …) |
| `uv run <cmd>` | Run a command in the project environment |

Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (or see the [install docs](https://docs.astral.sh/uv/getting-started/installation/)).

## Quick start

```bash
uv sync --group dev
cp env.example .env
docker compose up -d
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run python scripts/seed.py   # optional demo data; --show to list users/workspaces
```

- API: http://127.0.0.1:8000 — docs at `/docs`
- Tests: `uv run pytest` (in-memory SQLite + fakeredis)

## Auth & tokens

- **JWT** signed with **HS256** (`python-jose`), secret from `SECRET_KEY` in `.env`
- **Access token** — default **30 minutes** (`ACCESS_TOKEN_EXPIRE_MINUTES`). Send as `Authorization: Bearer <token>` on protected routes
- **Refresh token** — default **7 days** (`REFRESH_TOKEN_EXPIRE_DAYS`). Used for `POST /api/v1/auth/refresh` and `POST /api/v1/auth/logout`
- **Claims:** `sub` (user id), `type` (`access` | `refresh`), `jti` (unique id), optional `workspace_id` when a workspace is active
- **Workspace scope:** set active workspace via `POST /api/v1/workspaces/{id}/activate` or `PUT /api/v1/users/me/active-workspace`; new tokens then include `workspace_id`. Login without an active workspace works; workspace-scoped checks require activation first
- **Logout** revokes the refresh token in **Redis** by `jti`; access tokens stay valid until they expire
- **Passwords:** bcrypt hashes at registration