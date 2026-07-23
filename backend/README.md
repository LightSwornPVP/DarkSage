# DarkSage Backend — Local Development

Phase 1 foundation slice. Paper-trading-only project; nothing here requires
real API keys, a broker connection, or any paid service (SECURITY_RULES.md,
TRADING_RULES.md).

## Requirements

- Python 3.14.x — the only version this slice's lock files are generated
  against and tested on. Do not assume broader 3.x compatibility; if you
  need to support another minor version, regenerate and verify the lock
  files under that interpreter first (see "Updating dependencies" below).
- No external accounts, API keys, or network access required for this slice.

## Setup

Two dependency files exist for every environment:

- `requirements.txt` / `requirements-dev.txt` — human-maintained, loose version
  ranges. Edit these when you want to add/remove/upgrade a dependency.
- `requirements.lock.txt` / `requirements-dev.lock.txt` — fully pinned, hash-locked
  files generated from the above with [pip-tools](https://github.com/jazzband/pip-tools).
  These are what you actually install from, so every environment (yours, CI, a
  teammate's machine) resolves to the exact same dependency versions.

Install from the lock file for a reproducible environment:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install --require-hashes -r requirements-dev.lock.txt
```

### Updating dependencies

After editing `requirements.txt` or `requirements-dev.txt`, regenerate the lock
files (requires `pip-tools`, already included in `requirements-dev.txt`):

```bash
cd backend
pip-compile --generate-hashes --allow-unsafe --output-file=requirements.lock.txt requirements.txt
pip-compile --generate-hashes --allow-unsafe --output-file=requirements-dev.lock.txt requirements-dev.txt
```

Commit the regenerated lock files alongside the source change.

No `.env` file is required to start — `backend/app/config.py` ships with
safe local defaults (SQLite file in the current directory, debug mode on).
To override any setting, copy the pattern below into a `.env` file in the
repository root (never commit this file — it is already gitignored):

```bash
DARKSAGE_ENVIRONMENT=development
DARKSAGE_DEBUG=true
DARKSAGE_HOST=127.0.0.1
DARKSAGE_PORT=8000
DARKSAGE_DATABASE_URL=sqlite+aiosqlite:///./darksage.db
```

Invalid values (e.g. an unsupported `DARKSAGE_DATABASE_URL` scheme, or a
`DARKSAGE_PORT` outside 1-65535) cause the app to fail immediately at
startup with a clear validation error — never silently.

## Run the app

From the **repository root** (so the `backend`, `shared`, and `ai` packages
resolve correctly):

```bash
uvicorn backend.app.main:app --reload
```

Then check:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

## Database migrations

Schema is managed with Alembic. From the repository root:

```bash
alembic -c backend/alembic.ini revision --autogenerate -m "describe the change"
alembic -c backend/alembic.ini upgrade head
```

No migrations exist yet in this slice — `backend/alembic/versions/` is
intentionally empty. Domain models in `shared/models/` never import from
the database layer, so SQLite can be replaced later (ARCHITECTURE.md
Section 20) without touching business logic.

## Tests

From the repository root:

```bash
pip install --require-hashes -r backend/requirements-dev.lock.txt
pytest
```

Tests never touch a real database file — every test uses an isolated
in-memory SQLite database via fixtures in `tests/conftest.py`.

Optional static type check (strict mode, see `pyproject.toml`):

```bash
mypy backend shared ai
```

## What this slice does not include

- No live trading, no broker integration, no order execution.
- No real market-data provider or AI provider implementation — only the
  `MarketDataProvider` and `AIProvider` interfaces (`backend/app/market_data/`,
  `ai/providers/`).
- No desktop/mobile client code.
- No API keys or paid services of any kind.
