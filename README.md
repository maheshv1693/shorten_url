# High-Performance URL Shortener

A self-contained URL shortener service built with FastAPI, SQLAlchemy 2.0, and Base62 encoding. It runs locally with SQLite and is structured to support PostgreSQL and Redis in a production deployment.

## Project Overview

The service provides:

- Cryptographically secure, random seven-character Base62 short codes with database-enforced uniqueness and bounded collision retries.
- Custom alias reservation enforced by a database uniqueness constraint.
- Optional link expiration, enforced on redirect and reflected in cache lifetime.
- A thread-safe, in-memory cache-aside layer for low-latency redirects.
- Click telemetry dispatched through FastAPI background tasks.

Generated codes are random rather than sequential. The database unique constraint handles collisions, and creation retries generation up to three times before failing. Custom aliases share the same unique short-code namespace and are user-chosen, so they are not secret. The current cache is local to each process, and FastAPI background tasks are best-effort rather than a durable analytics queue; see the [production readiness roadmap](docs/PRODUCTION_READINESS.md).

**Security note:** The API currently has no authentication. Do not expose URL creation or analytics to untrusted networks until an authentication and authorization mechanism is added. Swagger UI is only the API console; securing or hiding the page alone would not protect the endpoints.

## Architecture & Design Highlights

- **Opaque short codes:** Generated codes use Python's `secrets` module to choose seven characters from the Base62 alphabet. Random codes can collide, so the database unique constraint is authoritative and creation retries up to three times. Seven-character codes reduce easy enumeration but should not be treated as authorization.
- **Temporary redirects:** Redirects use HTTP `307 Temporary Redirect`, which tells clients to preserve the request method and body, and avoids permanent redirect caching that would bypass later telemetry requests.
- **Background analytics:** Click events are dispatched with FastAPI `BackgroundTasks`, keeping the analytics database write out of the redirect handler's critical path. The current in-process task is not durable across process failure.
- **Expiry-aware caching:** Cache entries have a maximum 300-second TTL, shortened to the remaining lifetime of expiring URLs. Redirects check expiry before caching a database result.
- **Storage:** The default local database is SQLite. Set `DATABASE_URL` to use a compatible SQLAlchemy database and driver; production scaling to PostgreSQL and Redis is described in the architecture and roadmap documents.

## Example Scenarios

The [AI-assisted engineering scenarios](docs/EXAMPLE_SCENARIOS.md) show the greenfield URL shortener requirement, a brownfield code-generation and alias-validation change, and an ambiguous news-agency use case. The news example documents WhatsApp delivery and branded-domain provisioning as out of scope for this prototype.

## Project Directory Structure

```text
shorten_url/
|-- app/
|   |-- api/
|   |   `-- v1/
|   |       |-- endpoints.py
|   |       `-- schemas.py
|   |-- core/
|   |   |-- base62.py
|   |   `-- cache.py
|   |-- db/
|   |   |-- models.py
|   |   |-- repository.py
|   |   `-- session.py
|   `-- main.py
|-- docs/
|   |-- AI_interaction_log.md
|   |-- Architecture.md
|   |-- EXAMPLE_SCENARIOS.md
|   `-- PRODUCTION_READINESS.md
|-- tests/
|   |-- test_api.py
|   |-- test_base62.py
|   |-- test_cache.py
|   `-- test_repository.py
|-- .gitignore
|-- requirements.txt
`-- README.md
```

## Local Setup & Quickstart

Python 3.10 or newer is recommended. Run commands from the project root.

### Windows PowerShell

```powershell
python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Optional: initialize the database explicitly. Startup also initializes it.
python -c "from app.db.session import init_db; init_db()"

uvicorn app.main:app --reload
```

If `python` is not available, use `py -m venv venv` to create the environment.

### Linux or macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt

# Optional: initialize the database explicitly. Startup also initializes it.
python -c 'from app.db.session import init_db; init_db()'

uvicorn app.main:app --reload
```

By default, SQLite creates `shortener.db` in the current working directory. To select another database, set `DATABASE_URL` before starting the application. For example:

```powershell
$env:DATABASE_URL = "sqlite:///./shortener.db"
```

```bash
export DATABASE_URL="sqlite:///./shortener.db"
```

The application lifespan calls `init_db()` automatically when Uvicorn starts. The explicit initialization command is useful when you want to create tables before launching the server.

## Executing Test Suites

Run all tests from the project root:

```bash
python -m pytest -v
```

Coverage includes Base62 known values and round trips, repository creation and duplicate-alias rollback behavior, cache hit/miss/deletion/TTL behavior, and FastAPI HTTP integration for public health and redirects, URL creation, conflicts, expiration, missing codes, and click analytics.

## OpenAPI & Interactive Documentation

When the server is running locally:

- Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- OpenAPI schema: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

## API Reference

### Create a short URL

`POST /api/v1/urls`

The `url` must use `http` or `https`. `custom_alias` is optional and must contain 4-16 letters, numbers, hyphens, or underscores. `expires_in_hours` is optional and accepts values from 1 through 720; omitted expiration means the link does not expire.
All endpoints are currently unauthenticated, including URL creation and analytics. Use this local prototype only in a trusted environment; add authentication before exposing it to untrusted clients. There is no URL deletion endpoint.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/urls" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/articles/fastapi",
    "custom_alias": "fast-api",
    "expires_in_hours": 24
  }'
```

Successful response (`201 Created`):

```json
{
  "short_code": "fast-api",
  "short_url": "http://127.0.0.1:8000/fast-api",
  "original_url": "https://example.com/articles/fastapi",
  "created_at": "2026-09-28T12:00:00Z",
  "expires_at": "2026-09-29T12:00:00Z"
}
```

A duplicate alias returns `409 Conflict` with `{"detail":"Alias already in use"}`. Invalid request fields return FastAPI's `422 Unprocessable Entity` validation response.

### Redirect to the destination

`GET /{short_code}`

```bash
curl -i "http://127.0.0.1:8000/fast-api"
```

A valid link returns `307 Temporary Redirect` with a `Location` header containing the destination. The response dispatches click telemetry in a background task. An unknown or inactive code returns `404 Not Found`; an expired code returns `410 Gone`.

### Read click analytics

`GET /api/v1/urls/{short_code}/analytics`

```bash
curl "http://127.0.0.1:8000/api/v1/urls/fast-api/analytics" \
  -H "Accept: application/json"
```

Example response:

```json
{
  "short_code": "fast-api",
  "total_clicks": 2,
  "recent_clicks": [
    {
      "clicked_at": "2026-09-28T12:10:00Z",
      "referrer": "https://news.example/",
      "user_agent": "Mozilla/5.0"
    },
    {
      "clicked_at": "2026-09-28T12:05:00Z",
      "referrer": null,
      "user_agent": "curl/8.0.0"
    }
  ]
}
```

Analytics include the total event count and up to the 100 most recent click records, ordered newest first. An unknown or inactive short code returns `404 Not Found`.

## Production Roadmap Reference

- [Production readiness roadmap](docs/PRODUCTION_READINESS.md): deployment, durability, security, and operations work to complete before production use.
- [Architecture overview](docs/Architecture.md): current component model, data flow, and design trade-offs.