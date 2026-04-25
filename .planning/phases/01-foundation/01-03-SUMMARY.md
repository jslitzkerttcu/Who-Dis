---
phase: 01-foundation
plan: 03
subsystem: infra
tags: [health, monitoring, ops, blueprint, unauthenticated]

requires:
  - phase: 01-foundation
    provides: request-id middleware (g.request_id), database connection pool
provides:
  - Unauthenticated /health/live shallow liveness probe
  - Unauthenticated /health deep DB probe (SELECT 1 + latency_ms)
  - health_bp blueprint registered at root in app/__init__.py
affects: [phase-01-foundation, phase-08-deploy]

tech-stack:
  added: []
  patterns:
    - "Unauthenticated public probe blueprint: registered at root, no @auth_required, returns JSON via @handle_errors(json_response=True)"
    - "Deep health probe: SELECT 1 via SQLAlchemy text() + time.perf_counter() for latency_ms; 200/503 split on DB reachability"

key-files:
  created:
    - app/blueprints/health/__init__.py
  modified:
    - app/__init__.py

key-decisions:
  - "Both /health and /health/live remain unauthenticated (D-11) so external monitors (Azure App Service, uptime checks) can probe without Azure AD SSO"
  - "/health performs ONLY a database probe (D-12) — no LDAP/Graph/Genesys calls; deep external-service health is out of scope and would create false negatives during upstream outages"
  - "Response body intentionally omits DSN, credentials, and row counts; error strings truncated to 200 chars (T-01-03-01)"
  - "Liveness is intentionally trivial — only proves the Python process is up; /health is the deep check (T-01-03-03)"
  - "No rate limiting on health endpoints — SELECT 1 is the cheapest possible query and uptime monitors need free access (T-01-03-02 accept)"
  - "request_id pulled defensively via getattr(g, 'request_id', None) so the route works even if the request-id middleware is bypassed"

patterns-established:
  - "Public probe blueprint: register with no url_prefix at root; pure-JSON via @handle_errors(json_response=True); no decorators that depend on g.user/g.role"

requirements-completed: [OPS-01]

duration: ~10min
completed: 2026-04-25
---

# Phase 01 Plan 03: Health Endpoints Summary

**Two unauthenticated health endpoints — `/health/live` (shallow process-up probe) and `/health` (deep DB probe with SELECT 1 + latency_ms, 503 on DB failure) — wired into the app at root for external monitors.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-04-25T00:08:00Z (approx)
- **Completed:** 2026-04-25T00:12:00Z
- **Tasks:** 1
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments

- New `app/blueprints/health/__init__.py` with `health_bp` blueprint exposing two GET routes
- `/health/live` returns 200 with `{"status": "ok"}` — no DB call, no external service call
- `/health` executes `SELECT 1` via `db.session.execute(text("SELECT 1"))`, measures latency with `time.perf_counter()`, returns:
  - 200 with `{status, database: {connected: true, latency_ms}, version, request_id}` when DB up
  - 503 with `{status: "degraded", database: {connected: false, error}, version, request_id}` when DB unreachable
- Error text truncated to 200 chars to prevent leaking DSN/credentials in failure mode
- Registered at root (no `url_prefix`) in `app/__init__.py` after the existing blueprint registration block
- Confirmed unauthenticated: zero `@auth_required` / `@require_role` decorators on the routes; auth middleware uses route-level decorators (no global before_request gate to bypass)

## Verification

Tested via Flask test client with both a healthy SQLite in-memory DB and a deliberately unreachable Postgres DSN:

| Probe | DB State | Status | Body keys |
|-------|----------|--------|-----------|
| `/health/live` | n/a | 200 | `status` |
| `/health` | up | 200 | `status, database.connected, database.latency_ms, version, request_id` |
| `/health` | down | 503 | `status, database.connected, database.error, version, request_id` |
| Content-Type | both | — | `application/json` |

URL-map inspection confirmed routes registered as `/health/live` and `/health`.

Could not boot the full `create_app()` in this environment (missing encrypted-config keys triggers the OPS-03 validator from plan 01-05 — working as intended), so verification used a minimal Flask app + the blueprint in isolation. The integration path exercises the same `db.session.execute` + `@handle_errors` chain that the production wiring uses.

## Deviations from Plan

None — plan executed exactly as written. The plan's verification command attempted to use `python -c 'from app import create_app; ...'` which can't run without configured encrypted-config; substituted an isolated-blueprint test that exercises the same code paths.

## Threat Model Compliance

| Threat ID | Mitigation Applied |
|-----------|-------------------|
| T-01-03-01 (Info Disclosure) | Response body limited to `connected: bool`, `latency_ms`, static version, request_id; error strings truncated to 200 chars; no DSN/credentials/row counts |
| T-01-03-02 (DoS) | Accepted — `SELECT 1` is cheapest possible query; rate limiting deferred so monitors get free access (SEC-03 limits search endpoints separately) |
| T-01-03-03 (Spoofing — liveness without DB) | Accepted — liveness intentionally proves process-up only; `/health` is the deep DB check |

No new threat surface introduced beyond the registered routes.

## Commits

- `101b4e8` — feat(01-03): add unauthenticated /health and /health/live endpoints

## Self-Check: PASSED

- FOUND: app/blueprints/health/__init__.py
- FOUND: register_blueprint(health_bp) in app/__init__.py
- FOUND: commit 101b4e8
- VERIFIED: zero @auth_required matches in app/blueprints/health/__init__.py
- VERIFIED: /health/live returns 200 {"status":"ok"}
- VERIFIED: /health returns 200 with database.connected=true when DB up
- VERIFIED: /health returns 503 with database.connected=false when DB down
- VERIFIED: both responses Content-Type application/json
