# Lead Generator

First production-style vertical slice for lead intake automation:

`POST /leads` → Pydantic validation → PostgreSQL persistence → n8n webhook → lead status update → retry/failure handling.

## What is implemented

- FastAPI API with strict Pydantic request validation.
- PostgreSQL persistence through SQLAlchemy 2.x and Alembic migrations.
- Lead lifecycle: `pending` → `dispatched` or `failed`.
- n8n webhook delivery with configurable timeout, bounded exponential backoff for transient failures, and fail-fast handling for non-retryable 4xx responses.
- Failed leads remain persisted and can be retried with `POST /leads/{lead_id}/retry`.
- `GET /leads/{lead_id}` for status inspection.
- Docker Compose stack for the API, PostgreSQL, and n8n.
- Importable n8n starter workflow at `n8n/workflows/lead_intake.json`.
- API and dispatcher tests that run without Docker by using SQLite and `httpx.MockTransport`.

## Project layout

```text
app/
  api/routes/       FastAPI route layer
  models/           SQLAlchemy persistence models
  schemas/          Pydantic request/response models
  services/         lead orchestration and n8n delivery
migrations/         Alembic migrations
n8n/workflows/      n8n workflow export
postgres/init/      local PostgreSQL bootstrap for the n8n database
tests/              API and delivery tests
```

## Local setup with Docker Compose

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Set a real `N8N_ENCRYPTION_KEY` in `.env`.

3. Start the stack:

   ```bash
   docker compose up --build -d
   ```

   The API runs Alembic migrations before starting Uvicorn.

4. Open n8n at `http://localhost:5678`, complete the local owner setup if prompted, import `n8n/workflows/lead_intake.json`, and activate the workflow. The production webhook URL used by the API is:

   ```text
   http://n8n:5678/webhook/lead-intake
   ```

5. Create a lead:

   ```bash
   curl -sS http://localhost:8000/leads \
     -H 'Content-Type: application/json' \
     -d '{
       "first_name": "Jane",
       "last_name": "Doe",
       "email": "jane@example.com",
       "company": "Acme",
       "source": "website"
     }'
   ```

A successful n8n response produces `status: "dispatched"`. If n8n is unavailable or returns a non-2xx response for all configured attempts, the lead still exists in PostgreSQL with `status: "failed"` and error metadata.

Retry a failed lead:

```bash
curl -sS -X POST http://localhost:8000/leads/<lead-id>/retry
```

Read the current state:

```bash
curl -sS http://localhost:8000/leads/<lead-id>
```

Health check:

```bash
curl -sS http://localhost:8000/healthz
```

## Run locally without Docker

Python 3.12+ is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

For a host-run API, change `DATABASE_URL` to point at `localhost` and change `N8N_WEBHOOK_URL` to `http://localhost:5678/webhook/lead-intake`.

## Tests

```bash
pytest
```

The tests cover validation, persistence-facing API behavior, successful dispatch, exhausted failure, transient exponential retry behavior, non-retryable 4xx handling, manual retry, and retry conflict handling.

## Failure semantics

The database commit happens before the outbound n8n call. This is intentional: a temporary automation outage must not discard a valid lead. The HTTP resource is therefore created even when automation dispatch ultimately fails, and the response exposes that state as `failed` so the same lead can be retried safely.

For a later production hardening slice, the synchronous webhook delivery can be replaced by a transactional outbox plus worker/queue without changing the external lead model or status API.
