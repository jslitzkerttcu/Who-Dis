---
phase: 01-foundation
plan: 02
subsystem: infra
tags: [cache, background-thread, debt, admin-ui, htmx]

requires:
  - phase: 01-foundation
    provides: DI container, audit_service, SearchCache model, _cache_actions.html partial
provides:
  - Hourly background prune of expired SearchCache rows (CacheCleanupService)
  - Admin Run-now route (POST /admin/api/cache/cleanup/run)
  - Run-now button in cache management UI
affects: [phase-01-foundation]

tech-stack:
  added: []
  patterns:
    - "Background-thread service mirroring TokenRefreshService lifecycle (init_app, idempotent start, daemon thread, app_context-wrapped iteration body)"
    - "run_now() synchronous public wrapper for admin invocations that already hold a request context"
    - "HTMX HTML fragment response from admin route (green-50 success / red-50 error) with role='status' aria-live='polite'"

key-files:
  created:
    - app/services/cache_cleanup_service.py
  modified:
    - app/container.py
    - app/__init__.py
    - app/blueprints/admin/cache.py
    - app/blueprints/admin/__init__.py
    - app/templates/admin/_cache_actions.html

key-decisions:
  - "Hourly cadence (3600s) per D-13/DEBT-03 — matches existing IT-ops admin tone; finer cadence is unnecessary because rows are already expired"
  - "_cleanup() body wraps DELETE + commit in a single transaction; uses synchronize_session=False since we don't query the deleted rows in this session"
  - "run_now() does NOT wrap with app.app_context() because the Flask request handler already provides one; only the background _run() loop wraps each iteration"
  - "Exceptions inside the _run() loop are caught + logged but never propagate (T-01-02-03 mitigation — thread must not die)"
  - "Run-now button has NO confirmation modal because the operation is idempotent and only deletes already-expired rows (UI-SPEC §Component Contract)"
  - "Audit log entry written on every Run-now invocation regardless of success/failure (T-01-02-04 — repudiation mitigation)"
  - "Decorator stack matches existing cache routes: just @require_role('admin') (which internally calls auth_required) — does NOT stack @auth_required separately to avoid divergence from refresh_cache analog"

patterns-established:
  - "Background-thread service skeleton — third instance of the pattern (token_refresh, employee_profiles_refresh, cache_cleanup); future scheduled jobs can copy this verbatim"

requirements-completed: [DEBT-03]

metrics:
  duration: ~10 minutes
  completed: "2026-04-25"
  tasks: 3
  files-changed: 6
---

# Phase 1 Plan 02: Cache Cleanup Summary

Hourly background prune of expired `SearchCache` rows plus an admin "Run now" button that invokes the cleanup synchronously. Satisfies DEBT-03.

## What Was Built

Three thin layers wired together:

1. **`CacheCleanupService`** (`app/services/cache_cleanup_service.py`) — daemon thread mirroring `TokenRefreshService` lifecycle. `_cleanup()` runs `SearchCache.query.filter(expires_at < utcnow()).delete()` inside a single transaction and returns `(deleted_count, duration_ms)`. `run_now()` is the synchronous public entry point for the admin route.
2. **Admin route** `POST /admin/api/cache/cleanup/run` (`app/blueprints/admin/cache.py::cache_cleanup_run`) — pulls the service from `current_app.container`, calls `run_now()`, audits the action, returns an HTMX HTML fragment (green success / red error) with `role="status" aria-live="polite"`.
3. **UI row** in `_cache_actions.html` — fourth card row alongside Search Cache / Genesys Cache / Employee Profiles, using `fa-broom` icon, blue-500 button, posting to `admin.api_cache_cleanup_run` and swapping `#cleanup-result`.

Service is registered in `app/container.py` as `cache_cleanup` and started from `app/__init__.py` immediately after the existing `token_refresh.start()` block, inside the `WERKZEUG_RUN_MAIN` guard so the dev reloader does not double-start it.

## Tasks Completed

| Task | Name | Commit |
| ---- | ---- | ------ |
| 1 | CacheCleanupService background thread | d52be32 |
| 2 | Admin Run-now route returning HTMX fragments | 9da4955 |
| 3 | Run-now row in _cache_actions.html | 67d8ed9 |

## Verification

- `grep "class CacheCleanupService" app/services/cache_cleanup_service.py` matches
- `grep "check_interval = 3600" app/services/cache_cleanup_service.py` matches
- `grep 'container.register("cache_cleanup"' app/container.py` matches
- `grep "Cache cleanup background service started" app/__init__.py` matches
- `python -c "from app.services.cache_cleanup_service import CacheCleanupService; svc = CacheCleanupService(); assert hasattr(svc, 'run_now') and svc.check_interval == 3600"` exits 0
- `grep "def cache_cleanup_run" app/blueprints/admin/cache.py` matches
- `grep "api_cache_cleanup_run" app/blueprints/admin/__init__.py` matches
- `grep "/api/cache/cleanup/run" app/blueprints/admin/__init__.py` matches
- `grep "log_admin_action" app/blueprints/admin/cache.py` matches (audit wired)
- `grep -c "fa-broom" app/templates/admin/_cache_actions.html` returns 2 (icon circle + button)
- `grep 'id="cleanup-result"' app/templates/admin/_cache_actions.html` matches
- `grep "url_for('admin.api_cache_cleanup_run')" app/templates/admin/_cache_actions.html` matches
- `grep 'aria-live="polite"' app/templates/admin/_cache_actions.html` matches

`python -c "from app import create_app; create_app()"` raises the OPS-03 `ConfigurationError` because this dev environment has no encrypted LDAP/Graph/Genesys config — that gate fires from a previously completed plan and is unrelated to this work. Direct import of `app.blueprints.admin` and `app.services.cache_cleanup_service` succeeds.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocker] Plan referenced `app/models/search_cache.py`; actual model lives in `app/models/cache.py`**

- **Found during:** Task 1 read_first phase
- **Issue:** Plan task 1 said to read `app/models/search_cache.py` to confirm the `expires_at` column. That file does not exist; `class SearchCache` lives in `app/models/cache.py`.
- **Fix:** Imported `from app.models.cache import SearchCache` inside `_cleanup()`. Column name `expires_at` (provided by `CacheableModel` base) confirmed.
- **Files modified:** `app/services/cache_cleanup_service.py`
- **Commit:** d52be32

**2. [Rule 1 - Adjustment] Decorator stack: `@require_role("admin")` only, not `@auth_required` + `@require_role`**

- **Found during:** Task 2
- **Issue:** Plan suggested stacking `@auth_required` then `@require_role("admin")`. The canonical analog `refresh_cache` in `app/blueprints/admin/database.py:358` uses only `@require_role("admin")`, which itself invokes `auth_required` internally. Stacking both would diverge from existing cache routes for no security benefit.
- **Fix:** Used `@require_role("admin")` only, matching every other route in `app/blueprints/admin/cache.py`. Auth is still enforced — `require_role` calls `authenticate()` first.
- **Files modified:** `app/blueprints/admin/cache.py`
- **Commit:** 9da4955

**3. [Rule 2 - Critical] Added module-level `logger` to `app/blueprints/admin/cache.py`**

- **Found during:** Task 2
- **Issue:** New `cache_cleanup_run()` uses `logger.exception(...)` in its except branch (T-01-02-03 mitigation requires logging). The existing `cache.py` had no module logger.
- **Fix:** Added `import logging; logger = logging.getLogger(__name__)` at module top.
- **Files modified:** `app/blueprints/admin/cache.py`
- **Commit:** 9da4955

No `@handle_errors` decorator was applied to the new route per plan: doing so would replace the bespoke red-50 HTMX fragment with a generic JSON 500, breaking the UI-SPEC visual contract. The handler already manages its own try/except + audit log, which is the more specific pattern for HTMX endpoints.

## Threat Model Compliance

| Threat | Disposition | Mitigation in code |
|--------|-------------|---------------------|
| T-01-02-01 Elevation of privilege | mitigate | `@require_role("admin")` on the route; audit log includes `user_email`, `user_role`, IP |
| T-01-02-02 Tampering on DELETE | mitigate | DELETE filter is `expires_at < utcnow()` only — already-expired rows; verified via SearchCache model column path |
| T-01-02-03 DoS via thread crash | mitigate | `_run()` catches `Exception`, logs with `exc_info=True`, sleeps the full interval, never propagates |
| T-01-02-04 Repudiation | mitigate | `audit_service.log_admin_action(action="cache_cleanup_run", target="cache:search", success=…)` wired on both success and failure branches |

## Self-Check: PASSED

All claimed files exist:
- `app/services/cache_cleanup_service.py` — FOUND
- `app/blueprints/admin/cache.py` (modified) — FOUND with `cache_cleanup_run`
- `app/blueprints/admin/__init__.py` (modified) — FOUND with `api_cache_cleanup_run`
- `app/templates/admin/_cache_actions.html` (modified) — FOUND with `fa-broom`, `cleanup-result`
- `app/container.py` (modified) — FOUND with `cache_cleanup` registration
- `app/__init__.py` (modified) — FOUND with startup wiring

All claimed commits exist in `git log`:
- d52be32 — FOUND
- 9da4955 — FOUND
- 67d8ed9 — FOUND
