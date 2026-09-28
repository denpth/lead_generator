# Lead Generator

First production-style vertical slice for lead intake automation:

`POST /leads` → Pydantic validation → PostgreSQL persistence → n8n webhook → lead status update → retry/failure handling.

## What is implemented

- Node.js frontend at `http://localhost:3000` for lead intake, search, delivery status, and manual retries.
- FastAPI API with strict Pydantic request validation.
- PostgreSQL persistence through SQLAlchemy 2.x and Alembic migrations.
- Lead lifecycle: `pending` → `dispatched` or `failed`.
- n8n webhook delivery with configurable timeout, bounded exponential backoff for transient failures, and fail-fast handling for non-retryable 4xx responses.
- Failed leads remain persisted and can be retried with `POST /leads/{lead_id}/retry`.
- `GET /leads/{lead_id}` for status inspection.
- `GET /leads` with bounded pagination, literal text search, status filters, and overall status counts.
- Docker Compose stack for the frontend, API, PostgreSQL, and n8n.
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
frontend/           Node.js server, browser UI, and proxy tests
```

## Local setup with Docker Compose

1. Copy the environment template:

   ```bash
   test -f .env || (umask 077; cp .env.example .env)
   ```

2. Set a real `N8N_ENCRYPTION_KEY` in `.env`.

3. Start the stack:

   ```bash
   docker compose up --build -d
   ```

   The API runs Alembic migrations before starting Uvicorn. All four services have health checks; the API waits for n8n readiness and the frontend waits for the API. Run `docker compose ps` to confirm they are healthy.

4. Open n8n at `http://localhost:5678`, complete the local owner setup if prompted, import `n8n/workflows/lead_intake.json`, and publish the workflow. Alternatively, initialize the included workflow from the CLI:

   ```bash
   docker compose exec -T n8n n8n import:workflow --input=/workflows/lead_intake.json
   docker compose exec -T n8n n8n publish:workflow --id=a75ee401-5862-4d32-94c7-31d9c65d1953
   docker compose restart n8n
   docker compose up -d --wait
   ```

   The CLI changes the database, so the restart is required to register the production webhook. Import once during initial setup: reimporting the same workflow ID replaces that workflow, including any local edits. The pinned n8n version is `2.40.7`. The production webhook URL used by the API is:

   ```text
   http://n8n:5678/webhook/lead-intake
   ```

5. Open `http://localhost:3000` and click **New lead**. The inbox shows existing database records, supports search and status filters, and opens delivery details when you select a contact. Failed deliveries have a **Retry delivery** action. You can also create a lead directly:

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
test -f .env || (umask 077; cp .env.example .env)
alembic upgrade head
uvicorn app.main:app --reload
```

For a host-run API, change `DATABASE_URL` to point at `localhost` and change `N8N_WEBHOOK_URL` to `http://localhost:5678/webhook/lead-intake`.

## Tests

```bash
pytest
```

The tests cover validation, persistence-facing API behavior, successful dispatch, exhausted failure, transient exponential retry behavior, non-retryable 4xx handling, manual retry, and retry conflict handling.

## Frontend development

The frontend uses Node.js 22+ (Docker uses Node 24) and browser-native HTML, CSS, and JavaScript. It has no npm dependencies or bundle step. From the repository root:

```bash
cd frontend
npm run dev
```

By default, the Node server listens on port 3000 and proxies `/api/...` to `http://127.0.0.1:8000`. Set `PORT` and `API_ORIGIN` to override those values. Stop the Compose frontend first (`docker compose stop frontend`) if it already occupies port 3000. Reload the browser after editing browser assets.

The same-origin proxy keeps the browser API URL consistent between Docker and host development. It only forwards the supported lead and health endpoints, limits request size, and preserves API errors. Credentials and database settings stay out of browser assets. The Compose frontend port binds to localhost; this is a local workspace without user authentication.

```bash
npm run check
npm test
```

List endpoint example: `GET /leads?limit=20&offset=0&status=failed&q=Acme`. The response has `items`, the filtered `total`, and overall `counts` for pending, dispatched, and failed leads. Search matches name fields, email, phone, or company. Limit is 1–100; offset must be non-negative.

The UI disables submission while delivery is in flight. If a network interruption makes the result uncertain, it asks the user to refresh before submitting again. It never automatically repeats a lead-creation request. `Dispatched` confirms webhook acceptance, not downstream workflow completion.

Partial contacts are supported: name, company, and notes are optional. Provide an email or a phone number containing at least seven digits. A supplied invalid phone is rejected even when an email is also present; clear the phone field to use email only. Both the page and API explain this rule. Unexpected or incomplete server responses are rejected before rendering contact details, so they cannot appear as saved leads with invalid dates.

## Failure semantics

The database commit happens before the outbound n8n call. This is intentional: a temporary automation outage must not discard a valid lead. The HTTP resource is therefore created even when automation dispatch ultimately fails, and the response exposes that state as `failed` so the same lead can be retried safely.

For a later production hardening slice, the synchronous webhook delivery can be replaced by a transactional outbox plus worker/queue without changing the external lead model or status API.
