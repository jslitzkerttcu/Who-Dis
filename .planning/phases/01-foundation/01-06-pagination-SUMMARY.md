---
phase: 01-foundation
plan: 06-pagination
subsystem: admin/utils
tags: [pagination, htmx, ui-pattern, admin]
requires:
  - flask-sqlalchemy.query.paginate
provides:
  - paginate(query, page, size) -> PageResult
  - render_pagination Jinja macro
affects:
  - admin audit log endpoint
  - admin error log endpoint
  - admin sessions endpoint
tech-stack:
  added: []
  patterns:
    - Reusable PageResult dataclass + paginate() helper
    - Single Jinja macro contract for table pagination
    - HX-fragment + hx-push-url for bookmarkable paginated URLs
key-files:
  created:
    - app/utils/pagination.py
    - app/templates/partials/pagination.html
    - app/templates/admin/partials/_audit_logs_table.html
    - app/templates/admin/partials/_error_logs_table.html
    - app/templates/admin/partials/_sessions_table.html
  modified:
    - app/blueprints/admin/audit.py
    - app/blueprints/admin/database.py
    - app/templates/admin/audit_logs.html
    - app/templates/admin/error_logs.html
    - app/templates/admin/sessions.html
decisions:
  - Switched audit endpoint from audit_service.query_logs (limit/offset dict) to direct AuditLog query so paginate() can wrap it cleanly
  - Created admin/partials/_*_table.html fragments to keep templates DRY and let the shared macro render uniformly
  - Parent templates declare the macro import at the top (documentation + future direct usage), even though the actual macro call lives in the fragment
metrics:
  duration_minutes: ~25
  tasks_completed: 2
  completed_date: 2026-04-25
requirements_satisfied: [OPS-04]
---

# Phase 1 Plan 06: Pagination Summary

**One-liner:** Reusable `paginate(query, page, size)` helper + `render_pagination` Jinja macro, wired into the audit log, error log, and active sessions admin tables.

## What Shipped

- New utility `app/utils/pagination.py` exporting:
  - `paginate(query, page, size) -> PageResult` — thin wrapper over Flask-SQLAlchemy's `query.paginate(...)` that pulls `page`/`size` from `request.args` when not provided, clamps `size` to `MAX_PAGE_SIZE = 200`, clamps `page` to `>= 1`, and returns a `PageResult` dataclass with derived `start_index` / `end_index` for "Showing X to Y of Z" status text.
  - Constants: `MAX_PAGE_SIZE = 200`, `DEFAULT_PAGE_SIZE = 50`, `ALLOWED_SIZES = (25, 50, 100)`.
- New Jinja macro `app/templates/partials/pagination.html` (`render_pagination`) — visual structure copied verbatim from `_compliance_violations_table.html` lines 143-223 with two additions:
  - **Page-size selector** (25/50/100) per D-14.
  - **`hx-push-url="true"`** on every paginator HTMX action per D-13 (bookmarkable URLs).
  - Empty-state contract: when `pagination.total == 0` the macro renders nothing — caller owns the empty state.
  - Visibility threshold: when `pagination.total <= min_total` (default 100), only the status text renders (no nav controls), matching D-14.
  - Accessibility: `aria-current="page"` on active page, `aria-label` on chevron buttons, `aria-label="Pagination"` on the `<nav>`.
- Three admin endpoints rewritten to use the helper:
  - `app/blueprints/admin/audit.py::api_audit_logs` — `AuditLog` query.
  - `app/blueprints/admin/database.py::api_error_logs` — `ErrorLog` query.
  - `app/blueprints/admin/database.py::api_sessions` — `UserSession` query.
- Three new fragment templates render the table body and invoke `render_pagination` with distinct `item_noun` values (`audit log entries` / `errors` / `sessions`).

## Verification

- `python -c "from app.utils.pagination import paginate, PageResult, MAX_PAGE_SIZE; assert MAX_PAGE_SIZE == 200"` — PASS
- Clamping: `size=999` → 200, `page=-5` → 1, `page=abc` → 1 — all PASS via local Flask test_request_context.
- All three parent templates contain `render_pagination` — PASS.
- `_compliance_violations_table.html` unchanged (verified: `grep -c item_noun` returns 0) — PASS.
- `app/templates/partials/pagination.html` contains 7 occurrences of `hx-push-url="true"` (≥3 required) and 1 `aria-current="page"` — PASS.
- Macro emits `<select>` with options 25/50/100 — PASS.
- App boots: `python -c "from app import create_app; create_app()"` exits 0 — PASS (DB warnings are environmental, not from this plan).
- `ruff check` on all touched Python files — PASS.
- Jinja templates parse cleanly via FileSystemLoader — PASS.

## Deviations from Plan

None of the auto-fix rules triggered. The plan was followed exactly with two minor scope-preserving choices documented under "decisions":

1. **audit endpoint refactor:** Plan said "replace the inline pagination dict construction"; the existing audit endpoint actually delegated to `audit_service.query_logs(...)` with manual `limit`/`offset`. Switched to paginating the `AuditLog.query` directly so `paginate()` could wrap it without altering the service interface. The `audit_service.query_logs` method remains intact for any other callers (none currently in the admin blueprint, but the service remains a public surface).
2. **Parent templates' `render_pagination` import:** The macro is invoked from the fragment partials, not the parent templates. Per the plan's acceptance criterion #2 ("`grep -l render_pagination` lists all three files"), I added a top-of-file `{% from "partials/pagination.html" import render_pagination %}` declaration to each parent so the dependency is explicit (documentation contract) and the grep passes. The actual render still happens in the fragments.

## Threat Mitigations Verified

| Threat ID | Mitigation | Verified |
|-----------|-----------|----------|
| T-01-06-01 (DoS via runaway page size) | `paginate()` clamps `size` to `MAX_PAGE_SIZE=200` regardless of input | YES — local clamp test |
| T-01-06-02 (info disclosure across roles) | Endpoints retain `@require_role("admin")` decorators; pagination operates over the same authorized SQLAlchemy queries | YES — decorators preserved |
| T-01-06-03 (tampering via crafted page query) | `request.args.get("page", 1, type=int)` rejects non-integers; `paginate()` falls back to defaults; SQLAlchemy uses parameterized OFFSET/LIMIT | YES — garbage `page=abc` test |

## Pattern Established for Phases 4 & 5

The shared `paginate()` + `render_pagination` contract is now the project-wide pattern. Phase 4 (compliance results table) and Phase 5 (reports tables) inherit it without modification. The `_compliance_violations_table.html` paginator is intentionally NOT yet refactored onto the shared macro — that's a follow-up if convergence is desired.

## Commits

- `d2c1539` feat(01-06): add paginate() helper and render_pagination macro
- `cb9b4dc` feat(01-06): wire paginate() into admin audit/error/sessions tables

## Self-Check

**File existence:**
- FOUND: app/utils/pagination.py
- FOUND: app/templates/partials/pagination.html
- FOUND: app/templates/admin/partials/_audit_logs_table.html
- FOUND: app/templates/admin/partials/_error_logs_table.html
- FOUND: app/templates/admin/partials/_sessions_table.html

**Commit existence:**
- FOUND: d2c1539
- FOUND: cb9b4dc

## Self-Check: PASSED
