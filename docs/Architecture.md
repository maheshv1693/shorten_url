 # Architecture Overview: Scalable URL Shortener Service

## 1. System Overview & Component Diagram

The prototype is implemented as a lightweight, modular service using FastAPI, SQLite for persistence, and an in-memory TTL cache for low-latency redirection. It is designed to transition to PostgreSQL and Redis in a distributed production deployment.

### Current Short-Code Implementation

The implementation uses Python's `secrets` module to generate random seven-character strings from the Base62 alphabet. The database unique constraint is authoritative; generated-code insertions retry up to three times on integrity conflicts. The `urls.id` primary key is not encoded into the short code. Random generation reduces straightforward sequential enumeration but remains probabilistic and is not an authorization mechanism.

### API Security Boundary

The current prototype does not authenticate API callers. Swagger UI is an API client, not an access-control boundary; URL creation and analytics can be called directly. Do not expose this prototype to untrusted networks before adding authentication and authorization. Health checks and reader redirects are also public. There is currently no delete endpoint.

```text
				  +-----------------------------------+
				  |           Client / App            |
				  +-----------------+-----------------+
									|
					HTTP Requests   |
									v
				  +-----------------+-----------------+
				  |       FastAPI Application         |
				  |  - Schema Validation (Pydantic)   |
				  |  - Base62 Encoding Engine         |
				  +--------+-----------------+--------+
						   |                 |
	  Write Path / Cache Miss                | BackgroundTasks
						   v                 v
			+--------------+----+     +------+--------------+
			|  SQLite (Assmt)   |     | In-Memory Cache (Assmt)
			| [Postgres in Prod]|     |   [Redis in Prod]   |
			| - urls            |     +---------------------+
			| - url_clicks      |
			+-------------------+
```

The API layer validates requests and orchestrates the URL, cache, and database operations. The local cache is process-local; Redis is a production replacement target. SQLite is used for local development, with PostgreSQL as the intended production database. Click telemetry currently uses FastAPI `BackgroundTasks` and is not durable across process failure.

## 2. Data Flow & Request Paths

### Create a short URL (`POST /api/v1/urls`)

1. Pydantic validates the destination as HTTP or HTTPS and validates optional alias and expiry fields.
2. A custom alias is used directly. If the alias is absent or blank, the repository generates a seven-character Base62 code with `secrets.choice`.
3. The URL row is committed. A short-code uniqueness conflict during generated-code insertion causes a rollback and retry, up to three total attempts. A custom-alias conflict returns HTTP 409.
4. The mapping is placed in the cache with a maximum 300-second TTL, bounded by the link's remaining lifetime when it expires.
5. The API returns HTTP 201 Created with the short URL.

### Redirect (`GET /{short_code}`)

1. The service checks the cache, then queries the database on a miss.
2. Unknown or inactive codes return HTTP 404. Expired links return HTTP 410.
3. A valid link returns HTTP 307 Temporary Redirect. Click metadata is recorded in a background task.

### Analytics (`GET /api/v1/urls/{short_code}/analytics`)

Returns the total recorded clicks and up to the 100 most recent click events, ordered newest first.

## 3. Data Model & Purpose

### Table: `urls` (Stores Link Mappings)
* `id`: Internal auto-incrementing primary key; not used to generate the public short code.
* `short_code`: The unique short identifier (e.g., `xyz123`). It is indexed so database searches are instant instead of scanning the whole table.
* `original_url`: The full long target URL (supports long links with tracking parameters).
* `created_at`: Timestamp recording when the link was created.
* `expires_at`: Optional expiration date. If the current time is past this date, the system stops redirecting and returns `HTTP 410 Gone`.
* `is_active`: Flag to disable or soft-delete links reported for spam or abuse without losing history.

### Table: `url_clicks` (Stores Click Analytics)
* `id`: Unique click record ID.
* `short_code`: Identifies which short link was clicked. Indexed to make analytics lookups fast.
* `clicked_at`: Timestamp of when the redirect occurred.
* `referrer`: The website or app where the user clicked the link (e.g., Google, X/Twitter).
* `user_agent`: Device and browser information (helps distinguish mobile vs. desktop and bots).
* `ip_address`: User's IP address (used for geographic tracking and abuse detection).

---

## 4. Key Decisions & Trade-Offs

| Decision Area | What We Chose | What We Rejected | Plain English Reason |
| :--- | :--- | :--- | :--- |
| **Generated Short Codes** | **Seven random Base62 characters via `secrets.choice`** | Sequential primary-key encoding | Codes are less predictable than sequential IDs. Random collisions remain possible; a unique database constraint and up to three insertion attempts handle them. |
| **Redirect Status** | **HTTP 307 (Temporary)** | HTTP 301 (Permanent) | Browsers permanently cache 301 redirects on the user's computer. Future clicks would bypass our server entirely, breaking click counts. 307 ensures every click hits our service. |
| **Click Tracking** | **FastAPI BackgroundTasks** | Writing to DB before redirecting | Saving to the database takes time and slows down the redirect for the user. Background tasks send the redirect response first, then log the click immediately after. |
| **Database & Cache** | **SQLite + Memory Cache (Local)**<br>*(Postgres + Redis in Prod)* | Forcing Docker setup locally | Lets anyone clone and run the project immediately with zero setup. The code uses repository patterns, so swapping to Postgres and Redis in production needs only a configuration change. |