# Phase 1: Foundation - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Tech debt cleanup + operational primitives + security hardening that establish the production baseline before feature phases. Delivers DEBT-01..04, OPS-01..04, SEC-01..04. Out of scope: feature work, write operations, new endpoints beyond `/health`.

</domain>

<decisions>
## Implementation Decisions

### Salt File & Encryption Key (SEC-01, SEC-02)
- **D-01:** Remediate `.whodis_salt` leak by **rotating + gitignoring**, not rewriting git history. Generate new salt, gitignore it, rotate `WHODIS_ENCRYPTION_KEY`, re-encrypt all config rows. The leaked salt becomes useless once the key rotates. Avoids force-push coordination.
- **D-02:** Key rotation tool lives at `scripts/rotate_encryption_key.py` — matches existing `scripts/` pattern (`export_config.py`, `verify_encrypted_config.py`). No `flask` CLI command.
- **D-03:** Rotation flow is **in-place dual-key re-encrypt**: script reads `OLD_WHODIS_ENCRYPTION_KEY` and `NEW_WHODIS_ENCRYPTION_KEY` env vars, decrypts each `Configuration` row with old key and writes with new key inside a single transaction. Required: `--dry-run` flag, post-rotation verify step that decrypts every row with the new key.
- **D-04:** Document the salt-rotation runbook (steps + ordering) as part of phase deliverables. Operators must export config (`scripts/export_config.py`) before rotation as backup.

### Request ID & Logging (OPS-02)
- **D-05:** Request ID via **custom Flask middleware + `flask.g` + `logging.Filter`**. No new library. `before_request` handler generates UUID4 (or honors inbound `X-Request-ID` header), stores on `g.request_id`. A logging Filter injects the value into every `LogRecord`. For background threads using `copy_current_request_context`, the request ID propagates through Flask's context.
- **D-06:** Log format is **structured JSON via `python-json-logger`**. Every log line emits `{timestamp, level, request_id, user, logger, message, ...extras}`. Configure once in `app/__init__.py`. Replaces current plain-text formatter.
- **D-07:** Honor inbound `X-Request-ID` header (e.g., from reverse proxy) when present and well-formed; otherwise generate UUID4. Echo the request ID back as `X-Request-ID` response header so clients can correlate.

### Rate Limiting (SEC-03)
- **D-08:** Use **Flask-Limiter with PostgreSQL storage backend** so limits aggregate across gunicorn workers. New dependency added to `requirements.txt`. Storage URI uses existing PostgreSQL connection.
- **D-09:** Search endpoint limit: **30 requests/minute per authenticated user**. Apply via `@limiter.limit("30/minute", key_func=lambda: g.user)` decorator. Exceeded limit returns HTTP 429 with `Retry-After` header.
- **D-10:** Limit applies to `/search` and `/api/search` endpoints (Phase 1 scope). Other endpoints get sensible defaults during planning; admin endpoints remain unlimited.

### Health Check (OPS-01)
- **D-11:** **Two endpoints, both unauthenticated:**
  - `GET /health` — deep check: returns `{status, database: {connected, latency_ms}, version, request_id}`. Returns 503 if DB unreachable.
  - `GET /health/live` — shallow liveness: returns `{status: "ok"}` 200 OK. No DB hit.
- **D-12:** External API probes (LDAP/Graph/Genesys) are **NOT** part of `/health` — they live behind `/admin/api/tokens/status` (auth required). Rationale: transient API outages must not flip monitoring red when the app itself is healthy.

### Pagination (OPS-04)
- **D-13:** **Page numbers with offset/limit**, not Load More or infinite scroll. Bookmarkable URLs (`?page=3&size=50`). HTMX swaps the table body fragment on Prev/Next/page-number click. Establishes the pattern for Phase 4 compliance results and Phase 5 reports tables.
- **D-14:** Default page size **50 rows**. Show paginator UI only when total > 100 rows (small tables render fully). Page-size selector offers 25/50/100. Server-side limit max 200 to prevent runaway queries.
- **D-15:** Build a reusable `pagination.html` Jinja partial + `paginate(query, page, size)` helper in `app/utils/` so Phases 4 and 5 inherit the pattern.

### Claude's Discretion
The following items are concrete enough to decide during planning without further discussion. Planner should pick the obvious answer:

- **DEBT-01 init consolidation** — Keep `app/__init__.py` as the canonical factory. Delete `app/app_factory.py` after merging any unique logic. Verify no callers reference `app_factory` (already known: container + scripts use `__init__.py:create_app`).
- **DEBT-02 DataWarehouseService removal** — Delete `app/services/data_warehouse_service.py`, remove its container registration, ensure `EmployeeProfilesRefreshService` covers all callers.
- **DEBT-03 Cache cleanup job** — Background thread on app startup, same pattern as existing token refresh thread. Run hourly, delete `SearchCache` rows where `expires_at < NOW()`. Admin UI gets a "Run now" button (matches existing infrastructure tone).
- **DEBT-04 Asyncio modernization** — Replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()` / `asyncio.run()`. Targeted refactor of any `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)` patterns.
- **OPS-03 Config validation** — Define a startup validator that checks for required keys (LDAP server, Graph tenant/client, Genesys client_id, etc.) and raises a clear `ConfigurationError` with the missing-keys list. Failure aborts app boot.
- **OPS-04 Pagination wiring** — Apply the new helper to admin audit log, error log, and access attempts tables (the three known >100-row tables today).
- **SEC-04 Auth header config** — Allow override of the `X-MS-CLIENT-PRINCIPAL-NAME` header name via configuration (default unchanged). Add a dev-mode bypass behind an explicit, loud config flag (`DANGEROUS_DEV_AUTH_BYPASS_USER`) — never enabled in production.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 items)
- `.planning/REQUIREMENTS.md` — DEBT-01..04, OPS-01..04, SEC-01..04 acceptance criteria
- `.planning/STATE.md` — Current focus and accumulated decisions

### Existing Code (must read before changing)
- `app/__init__.py` — Canonical app factory (keep)
- `app/app_factory.py` — Duplicate to delete (DEBT-01)
- `app/container.py` — Service registration; new services (rate limiter, request-id middleware) registered here
- `app/services/data_warehouse_service.py` — To delete (DEBT-02)
- `app/services/refresh_employee_profiles.py` — Authoritative replacement
- `app/services/encryption_service.py` — Salt/key handling reference for SEC-01/02
- `app/services/configuration_service.py` — Config read path; OPS-03 validator integrates here
- `app/middleware/auth.py` — Auth orchestration; SEC-04 header config plugs in here
- `app/middleware/audit_logger.py` — Pattern reference for new request-ID middleware
- `scripts/export_config.py`, `scripts/verify_encrypted_config.py` — Pattern for new `rotate_encryption_key.py`
- `.gitignore` — Add `.whodis_salt` (SEC-01)

### Project Conventions
- `CLAUDE.md` — Architecture patterns, DI container usage, error handling decorators, encryption notes ("Memory Objects" section)
- `docs/architecture.md` — DI container details and search architecture
- `docs/database.md` — DB management, including ANALYZE requirement after schema changes

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **Background thread pattern** — Token refresh service already runs as background thread on app startup. DEBT-03 cleanup job follows the same pattern.
- **DI container** (`app/container.py`) — Register new RateLimiter and RequestIdMiddleware here.
- **Service base classes** (`app/services/base.py`) — `BaseAPIService`, `BaseTokenService`, `BaseSearchService` already established. No new bases needed in this phase.
- **Logging filter pattern** — Module-level `logger = logging.getLogger(__name__)` is universal. The new request-ID Filter attaches at handler level so every existing logger picks it up automatically.
- **HTMX fragment pattern** — Existing admin pages already swap table fragments. Pagination partial extends this.

### Established Patterns
- **Config access** — `config_get("category.key", default)`. OPS-03 validator iterates a hardcoded required-keys list and calls `config_get` for each.
- **Decorator stack** — `@auth_required` → `@require_role("admin")` → route. Rate-limit decorator inserts above `@auth_required` on `/search`.
- **Script invocation** — `python scripts/<name>.py [args]`. Scripts use `dotenv` + `create_app()` for context.
- **Encryption key handling** — `WHODIS_ENCRYPTION_KEY` env var, `.whodis_salt` per-install. CLAUDE.md notes the bootstrap problem: DB credentials stay in `.env` because the config service needs the DB to function.

### Integration Points
- `app/__init__.py:create_app()` — Add: request-ID middleware registration, JSON log formatter config, OPS-03 validator call, rate-limiter init, `/health` + `/health/live` blueprint registration.
- `app/middleware/__init__.py` — New `request_id.py` module with the middleware + LogFilter.
- `requirements.txt` — Add `Flask-Limiter`, `python-json-logger`. No other new deps.
- `database/create_tables.sql` — Flask-Limiter PostgreSQL storage may need a table; check library docs during planning.

</code_context>

<specifics>
## Specific Ideas

- Salt rotation runbook is a deliverable — operators need exact steps in order. Treat it as documentation, not just a script.
- JSON logging output should be readable at the CLI in dev — fine to add a pretty-print toggle if it's cheap, but don't gate on it.
- The pagination helper must be reusable enough that Phase 4 (compliance results table) and Phase 5 (reports tables) drop it in without rework. Generic enough to take any SQLAlchemy query.

</specifics>

<deferred>
## Deferred Ideas

- **Redis-backed rate limiting** — Future scaling. Flask-Limiter supports Redis storage; swap is a one-line config change if usage outgrows PostgreSQL counter.
- **Liveness/readiness split with k8s-style probes** — Not deploying to k8s today. `/health/live` is the seed; readiness can be added when the platform demands it.
- **Distributed tracing (OpenTelemetry)** — Request ID is the precursor. OTEL adoption is a future-milestone concern, not Phase 1.
- **API rate limiting** (separate from search) — Phase 7 REST API will need its own per-token limits. Flask-Limiter chosen here makes that drop-in.
- **CI gate on tests** (CI-01) — Already in v2 backlog. Phase 2 sets up the suite; CI wiring waits.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-04-24*
