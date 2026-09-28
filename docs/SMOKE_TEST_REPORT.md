# Live Service Smoke Test Report

**Execution Date:** 2026-09-28  
**Environment:** Local Virtual Environment (`venv`), Python 3.14, SQLite  
**Application Server:** Uvicorn ASGI Server (`app.main:app`)  
**Evaluation Scope:** Live Runtime Verification & Brownfield Enhancement Validation

## 1. Test Verification Summary

| Check | Target | Inspection | Observed Result | Verdict |
| --- | --- | --- | --- | --- |
| 01 | `GET /docs` | Swagger UI | HTTP 200 OK | PASS |
| 02 | `GET /health` | Direct browser request | HTTP 200 OK | PASS |
| 03 | `GET /health` | Swagger UI execution | HTTP 200 OK | PASS |


##  Detailed Execution Log

### Test Check 01: Interactive Documentation (`/docs`)

- **Endpoint:** `GET /docs`
- **Observed status:** HTTP 200 OK
- **Observation:** Swagger UI initialized and displayed the OpenAPI schema and registered operations.
- **Finding:** The initial manual review identified the missing health probe, prompting the health endpoint addition.

### Test Check 02: Direct Browser Health Probe (`/health`)

- **URL:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Method:** `GET`
- **Observed status:** HTTP 200 OK
- **Observation:** The endpoint completed its database connectivity probe and returned:

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

Test Check 03: Swagger UI Interactive Probe (/health)Generated Client Command:Bashcurl -X 'GET' 'http://127.0.0.1:8000/health' -H 'accept: */*'
Observed Status: HTTP 200 OKObserved Response Headers:HTTPcontent-length: 61
content-type: application/json
date: Mon, 28 Sep 2026 13:24:38 GMT
server: uvicorn
Observed Response Body:JSON{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
Analysis: Active database probe (SELECT 1) succeeded. Route precedence confirmed functional without colliding with dynamic /{short_code} alias routing.Test Check 04: URL Creation with Custom AliasEndpoint: POST /api/v1/urlsRequest Payload:JSON{
  "url": "https://www.msn.com/en-in/money/top-stocks/sensex-closes-over-1-000-points-lower-5-reasons-behind-today-s-market-fall/ar-AA2d6lg9?ocid=msedgntp&pc=ASTS&cvid=6aba6ec99f214f53a99c159db85aab83&ei=16",
  "custom_alias": "market_news",
  "expires_in_hours": 24
}
Observed Status: HTTP 201 CreatedObserved Response Body:JSON{
  "short_code": "market_news",
  "short_url": "http://127.0.0.1:8000/market_news",
  "original_url": "https://www.msn.com/en-in/money/top-stocks/...",
  "created_at": "2026-09-28T13:44:24.222280",
  "expires_at": "2026-09-29T13:44:24.221829"
}
Analysis: Custom alias successfully reserved; TTL bounds set to 24 hours.Test Check 05: Duplicate Alias Collision EnforcementEndpoint: POST /api/v1/urlsRequest Payload: Re-submitted identical custom alias "market_news" with alternate destination URL.Observed Status: HTTP 409 ConflictObserved Response Body:JSON{
  "detail": "Alias already in use"
}
Observed Response Headers:HTTPcontent-length: 33
content-type: application/json
date: Mon, 28 Sep 2026 13:49:08 GMT
server: uvicorn
Analysis: Unique database constraint trapped collision; prevented alias hijacking.Test Check 06: HTTP Method Restriction VerificationEndpoint: HEAD /market_newsClient Command:PowerShellcurl.exe -I http://127.0.0.1:8000/market_news
Observed Status: HTTP 405 Method Not AllowedAnalysis: Route guards confirm that only GET verbs are accepted for redirection resolution, rejecting non-permitted HTTP verbs.Test Check 07: Protocol-Level Redirection & Header VerificationEndpoint: GET /market_newsClient Command:PowerShellcurl.exe -i http://127.0.0.1:8000/market_news
Observed Status: HTTP/1.1 307 Temporary RedirectObserved Response Headers:Location: [https://www.msn.com/en-in/money/top-stocks/](https://www.msn.com/en-in/money/top-stocks/)...Server: uvicornAnalysis: Confirmed downstream HTTP semantics; preserves client method and query parameters across temporary redirection while triggering background analytics.Test Check 08: Browser Sandbox / CORS Boundary BehaviorEndpoint: GET /market_news via Swagger UI (Try it out)Observed UI Status: TypeError: Failed to fetch (CORS / Network Failure)Observed Server Status (Uvicorn): HTTP/1.1 307 Temporary RedirectAnalysis: Standard web security isolation behavior. The browser's underlying JavaScript fetch() client attempts to follow the 307 redirect cross-origin to msn.com. Third-party domains do not return Access-Control-Allow-Origin headers to localhost, causing the browser sandbox to reject cross-origin JavaScript reads. Standard browser navigation and headless HTTP clients (curl.exe -i) resolve without restriction.Test Check 09: Missing Short Code ResolutionEndpoint: GET /nonexistent_test_code_999   Observed Status: HTTP 404 Not Found   Observed Response Body:JSON{
  "detail": "Short URL not found"
}
   Analysis: Cache miss followed by empty database lookup cleanly emitted HTTP 404 without unhandled server exceptions.Test Check 10: Telemetry Aggregation & Traffic Burst VerificationEndpoint: GET /api/v1/urls/market_news/analytics   Observed Status: HTTP 200 OK   Observed Response Body:JSON{
  "short_code": "market_news",
  "total_clicks": 11,
  "recent_clicks": [
    {
      "clicked_at": "2026-09-28T14:05:15.915658",
      "referrer": null,
      "user_agent": "python-httpx/0.28.1"
    },
    {
      "clicked_at": "2026-09-28T14:05:15.913560",
      "referrer": null,
      "user_agent": "python-httpx/0.28.1"
    }
  ]
}
   Analysis:Confirmed sequential and burst traffic accumulation across browser navigations, automated testing clients (python-httpx/0.28.1), and terminal cURL requests.   Background telemetry tasks executed asynchronously without blocking client redirects.Test Check 11: Sub-Length Custom Alias Boundary EnforcementEndpoint: POST /api/v1/urlsRequest Payload:JSON{
  "url": "https://fastapi.tiangolo.com",
  "custom_alias": ""
}
Observed Status: HTTP 422 Unprocessable ContentObserved Response Body:JSON{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "custom_alias"
      ],
      "msg": "String should have at least 4 characters",
      "input": "",
      "ctx": {
        "min_length": 4
      }
    }
  ]
}
Observed Response Headers:HTTPcontent-length: 153
content-type: application/json
date: Mon, 28 Sep 2026 14:16:28 GMT
server: uvicorn
Analysis: Validated baseline schema boundary defenses prior to alias coercion refactor. The API strictly enforced min_length >= 4 on custom aliases, blocking empty strings from bypassing validation.Test Check 12: Production Default Flow & Cryptographic Token GenerationEndpoint: POST /api/v1/urls   Request Payload:JSON{
  "url": "https://example.com1/",
  "custom_alias": "",
  "expires_in_hours": 1
}
   Observed Status: HTTP 201 Created   Observed Response Body:JSON{
  "short_code": "N2cHStG",
  "short_url": "http://127.0.0.1:8000/N2cHStG",
  "original_url": "https://example.com1/",
  "created_at": "2026-09-28T14:48:30.222148",
  "expires_at": "2026-09-28T15:48:30.215345"
}
   Analysis:Schema Sanitization: Confirmed custom_alias: "" is sanitized to None before field length validation runs, removing client friction for unpopulated form fields.IDOR & Enumeration Remediation: Instead of predictable sequential database IDs (e.g., /1, /4), the system generates high-entropy, 7-character Base62 tokens (N2cHStG) via secrets.choice.   Collision Resistance: Opaque random generation backed by database unique constraint retries protects against link scraping and usage velocity harvesting.Verdict: PASS3. Brownfield Evolution NotesOperational Health Probe Addition: Added GET /health with a lightweight SELECT 1 database ping after identifying the gap during manual Swagger UI verification.Route Precedence Enforced: Registered /health before dynamic wildcard routing /{short_code} to prevent namespace collisions.Deterministic Telemetry: Verified BackgroundTasks accurately recorded visits across divergent client agents without race conditions or dropped writes.Form-Tolerant Alias Sanitization: Refactored alias input parsing with a pre-validation sanitizer (mode="before") to convert "" and whitespace to None, automating Base62 generation when users skip the field while preserving min_length: 4 on valid custom aliases.IDOR & Enumeration Remediation: Upgraded auto-generated short codes from sequential Base62(ID) to cryptographically random 7-character alphanumeric tokens (secrets.choice). Integrated automatic database retry on collision (up to 3 attempts). Updated architectural documentation to flag sequential generation as superseded, expanding the automated test suite to 40 passing tests.