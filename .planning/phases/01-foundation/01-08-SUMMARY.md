---
phase: 01-foundation
plan: 08
subsystem: security
tags: [rate-limiting, flask-limiter, security, sec-03]
requires:
  - SEC-03 acceptance criterion: per-user rate limit on search endpoints
provides:
  - 30 req/min per-user (or per-IP pre-auth) limit on search fan-out endpoints
  - app.limiter module-level instance, also registered as `limiter` in container
  - 429 response with Retry-After / RateLimit-* headers (RATELIMIT_HEADERS_ENABLED)
affects:
  - app/blueprints/search/__init__.py (decorator on POST /search and POST /user)
tech-stack:
  added:
    - "Flask-Limiter>=3.5,<4 (installed: 3.12)"
  patterns:
    - "Module-level limiter created in app/__init__.py, init_app(app) inside create_app, route modules import via `from app import limiter`"
    - "Custom key function `_search_rate_key` falls back to remote address when g.user is unset (limiter runs before @require_role)"
key-files:
  created: []
  modified:
    - requirements.txt
    - app/__init__.py
    - app/container.py
    - app/blueprints/search/__init__.py
decisions:
  - "Storage: in-memory (Flask-Limiter default). PostgreSQL backend dropped in Flask-Limiter v3.x; user (Joe) chose to ship in-memory now and swap to Redis during SandCastle integration phase per WD-NET-01."
  - "Rate-limit applied to POST /search and POST /user (the fan-out endpoints). GET /search/ (form render) and admin/health endpoints intentionally unlimited per D-10."
  - "Limiter decorator placed ABOVE @require_role so the limit check runs first; key function tolerates pre-auth requests (g.user None) by falling back to remote_addr."
metrics:
  completed: "2026-04-25"
  tasks_completed: 2
  files_modified: 4
---

# Phase 01 Plan 08: Rate Limiting Summary

Per-user rate limiting (30 req/min) on the search fan-out endpoints using Flask-Limiter with in-memory storage; PostgreSQL-backend deviation forced by upstream library limitation, Redis follow-up scheduled for SandCastle integration.

## What Was Built

- **`Flask-Limiter>=3.5,<4`** pinned in `requirements.txt` (resolved to 3.12).
- **Module-level `limiter`** in `app/__init__.py` constructed with `Limiter(key_func=get_remote_address)` (default in-memory storage). Initialized against the Flask app inside `create_app()` after the DI container is wired. `app.config["RATELIMIT_HEADERS_ENABLED"] = True` is set so 429 responses carry `Retry-After` plus the `RateLimit-*` informational headers.
- **Container registration** in `app/container.py:register_services()` exposes the limiter as `container.get("limiter")`.
- **Search-endpoint decoration:**
  - `_search_rate_key()` helper returns `g.user` when set, else `get_remote_address()`.
  - `@limiter.limit("30/minute", key_func=_search_rate_key)` applied above `@require_role("viewer")` on:
    - `POST /search/search` (HTMX search action — line 794)
    - `POST /search/user` (JSON API — line 296)
  - These are the two endpoints that fan out to LDAP + Graph + Genesys per request.
- **Unlimited (intentional):** GET `/search/` (form render, no fan-out), all admin endpoints, all health endpoints, all session endpoints.

## Verification

| Check | Result |
| ----- | ------ |
| `grep "Flask-Limiter" requirements.txt` | matches: `Flask-Limiter>=3.5,<4` |
| `grep "from flask_limiter import Limiter" app/__init__.py` | matches |
| `grep "limiter.init_app(app)" app/__init__.py` | matches |
| `grep '"limiter"' app/container.py` | matches: `container.register("limiter", lambda c: limiter)` |
| `grep -c "@limiter.limit" app/blueprints/search/__init__.py` | 2 |
| `grep "limiter.limit" app/blueprints/admin/__init__.py` | 0 matches (admin unlimited) |
| `python -c "from app import limiter; ..."` | imports cleanly |
| `python -c "from app.blueprints.search import _search_rate_key, search_bp"` | imports cleanly |

`create_app()` smoke test fails locally with a pre-existing OPS-03 ConfigurationError (missing LDAP/Graph/Genesys creds in this dev environment) — unrelated to this plan; module-level `limiter` import path was verified independently.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-08 PostgreSQL storage backend dropped in Flask-Limiter v3.x**
- **Found during:** Task 1 (during initial executor session, prior to checkpoint)
- **Issue:** D-08 mandated a PostgreSQL `storage_uri` so per-user counters aggregate across gunicorn workers. Flask-Limiter v3.x removed PostgreSQL support entirely — the only first-class options in the installed (3.12) version are `memory://`, `redis://`, `memcached://`, and `mongodb://`.
- **Fix:** Per user decision, ship in-memory storage now. `Limiter(key_func=get_remote_address)` uses `memory://` by default — no `storage_uri` is passed. Set `RATELIMIT_HEADERS_ENABLED = True` to preserve the Retry-After contract from D-08.
- **Files modified:** `app/__init__.py`, `requirements.txt`, `app/container.py`
- **Commits:** `56bb5ce`

**Rationale for in-memory now:** WhoDis currently runs in a single/low-worker deployment. Per-worker in-memory counters provide partial protection against runaway scripts, which satisfies SEC-03's intent (bound LDAP/Graph/Genesys API budgets). Cross-worker aggregation is only critical at multi-worker scale.

**Redis follow-up (deferred to SandCastle integration phase):**
The SandCastle integration requirements document the long-term plan:
- **WD-CONT-02** (multi-worker target): production deployment will run multiple gunicorn workers, at which point per-worker counters become inadequate.
- **WD-NET-01** (Redis available): SandCastle's internal network exposes a managed Redis instance, which Flask-Limiter natively supports as a `redis://` storage backend.
- During the SandCastle integration phase, swap `Limiter(key_func=...)` for `Limiter(key_func=..., storage_uri=os.environ["RATELIMIT_REDIS_URI"])`. No application-code changes are needed beyond the constructor.

### Other Deviations

**2. [Rule 1 - Bug] Plan referenced `/api/search` route that does not exist**
- **Found during:** Task 2
- **Issue:** Plan acceptance criteria mention applying limiter to `/search` and `/api/search`. The search blueprint has no `/api/search` route. The two real fan-out endpoints are POST `/search/search` (HTMX) and POST `/search/user` (JSON API).
- **Fix:** Applied `@limiter.limit("30/minute", key_func=_search_rate_key)` to BOTH POST `/search/search` and POST `/search/user` — these are the two endpoints that fan out to LDAP/Graph/Genesys, which is the threat the plan was protecting against. The plan's intent is preserved.
- **Files modified:** `app/blueprints/search/__init__.py`
- **Commit:** `69b5467`

## Deployment Notes

**CRITICAL: in-memory limits are per-worker.** In the current single/low-worker deployment this is acceptable — partial protection still bounds LDAP/Graph/Genesys API consumption against a runaway script.

**Migration plan (must execute during SandCastle integration phase):**
1. Provision the WhoDis app with `RATELIMIT_REDIS_URI` (or equivalent) pointing to the SandCastle Redis instance per WD-NET-01.
2. In `app/__init__.py`, change the limiter constructor to:
   ```python
   limiter = Limiter(
       key_func=get_remote_address,
       storage_uri=os.environ["RATELIMIT_REDIS_URI"],
   )
   ```
3. Verify cross-worker aggregation: hit the `/search/user` endpoint 31 times across multiple workers (e.g., via a load-balancer-pinned client) and confirm request 31 returns 429.
4. Update this SUMMARY's Deployment Notes to reflect the swap.

If WhoDis moves to multi-worker BEFORE the SandCastle migration, the Redis swap becomes required at that earlier date — track via WD-CONT-02.

## Commits

| Hash      | Subject |
| --------- | ------- |
| `56bb5ce` | feat(01-08): initialize Flask-Limiter with in-memory storage |
| `69b5467` | feat(01-08): apply 30/minute rate limit to search endpoints |

## Self-Check: PASSED

- FOUND: `requirements.txt` includes `Flask-Limiter>=3.5,<4`
- FOUND: `app/__init__.py` imports `Limiter` and calls `limiter.init_app(app)`
- FOUND: `app/container.py` registers `"limiter"`
- FOUND: `app/blueprints/search/__init__.py` has 2x `@limiter.limit("30/minute", ...)`
- FOUND: commit `56bb5ce`
- FOUND: commit `69b5467`
- VERIFIED: admin blueprint has 0 limiter decorators
