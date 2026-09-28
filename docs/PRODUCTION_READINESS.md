# Production Readiness Roadmap

The current service is a functional local prototype. These items describe the main work to complete before relying on it for production traffic.

## Persistence and Deployment

- [ ] Configure PostgreSQL with a production-supported SQLAlchemy driver, managed credentials, connection-pool limits, and database migrations.
- [ ] Replace process-local in-memory caching with Redis or another shared cache. Define invalidation behavior for link changes and takedowns.
- [ ] Confirm random-code uniqueness enforcement, retry behavior, and code-generation policy across database restores, replicas, and any multi-region write topology.
- [ ] Define backup, restore, retention, and disaster-recovery objectives and test restore procedures.

## Analytics Durability and Privacy

- [ ] Replace best-effort FastAPI background tasks with a durable queue and define retry, deduplication, backpressure, and delivery semantics.
- [ ] Define analytics retention, aggregation, and deletion policies.
- [ ] Review collection of IP addresses, referrers, and user agents for privacy obligations; minimize, protect, and restrict access to stored data.
- [ ] Establish trusted-proxy configuration before relying on forwarded client IP headers.

## Abuse and Availability

- [ ] Add authentication and authorization before exposing the API to untrusted users; define service/user identities, credential rotation, secret storage, and audit requirements.
- [ ] Add rate limits and abuse monitoring for link creation, alias probing, and redirect traffic.
- [ ] Define malicious-destination reporting, detection, and takedown workflows.
- [ ] Set latency and availability SLOs, health checks, structured logs, metrics, tracing, and alert thresholds.
- [ ] Exercise database, cache, and analytics subsystem failures and document expected redirect behavior.
- [ ] Review the seven-character code space and threat model; short codes are identifiers, not authorization, and custom aliases are guessable.

## Release Readiness

- [ ] Add automated migration, dependency, vulnerability, and deployment checks to CI.
- [ ] Load-test redirect, creation, and analytics paths at expected peak traffic.
- [ ] Document deployment configuration, secrets management, rollback, and incident response procedures.