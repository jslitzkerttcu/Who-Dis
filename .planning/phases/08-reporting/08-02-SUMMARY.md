---
phase: "08-reporting"
plan: "02"
subsystem: "reporting-frontend"
tags: [report-tabs, kpi-cards, csv-export, htmx-tabs, stale-cache]
dependency_graph:
  requires: [ReportCache-model, ReportSyncService]
  provides: [reports-blueprint, report-templates, license-tab, security-tab, csv-exports]
  affects: [08-03-PLAN]
tech_stack:
  added: []
  patterns: [htmx-tab-navigation, kpi-card-grid, server-side-list-pagination, csv-injection-prevention]
key_files:
  created:
    - app/blueprints/admin/reports.py
    - app/templates/admin/reports.html
    - app/templates/admin/partials/_report_licenses.html
    - app/templates/admin/partials/_report_security.html
    - app/templates/admin/partials/_report_stale_badge.html
  modified:
    - app/blueprints/admin/__init__.py
    - app/templates/admin/index.html
decisions:
  - "Server-side list pagination for sign-ins (not SQLAlchemy paginate) since data comes from ReportCache JSON, not DB query"
  - "Stale badge refresh POSTs directly to SandCastle job trigger API at /api/v2/admin/jobs/{name}/trigger"
  - "Date filter uses inline hx-vals with onclick for custom date range HTMX submission"
metrics:
  duration: "297s"
  completed: "2026-05-17T19:20:18Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 5
  files_modified: 2
---

# Phase 08 Plan 02: Reports Blueprint and Tab Views Summary

Reports blueprint with HTMX tabbed navigation, license utilization and security posture views featuring KPI cards, data tables, stale-cache indicators, date range filtering, and CSV export.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Reports blueprint with license/security tab routes and CSV exports | cde0b92 | app/blueprints/admin/reports.py |
| 2 | Reports page shell, tab partials, stale badge, and route registration | 791d669 | app/templates/admin/reports.html, app/templates/admin/partials/_report_*.html, app/blueprints/admin/__init__.py |

## What Was Built

1. **Reports Blueprint** (`app/blueprints/admin/reports.py`) - All routes decorated with `@require_role("admin")`. Main `reports()` function detects HX-Request for HTMX partial returns vs full page renders. Tab dispatcher routes to license and security handlers. `api_licenses_tab()` and `api_security_tab()` serve as named HTMX endpoints.

2. **License Tab** - Reads `ReportCache("license_summary", "totals")` for KPI cards (Total SKUs, Assigned, Unused 30d, Utilization %) and `ReportCache("license_summary", "per_sku")` for the sortable SKU data table. Rows with utilization < 80% highlighted with `bg-yellow-50`.

3. **Security Tab** - Reads MFA data from `ReportCache("mfa_summary", "totals")` and `("mfa_summary", "users_without")`. Failed sign-ins fetched from `report_sync_service.get_failed_signins()` with server-side list pagination (25 per page). Date range filter bar with preset buttons (24h/7d/30d) and custom date inputs.

4. **CSV Exports** - Two export endpoints returning `text/csv` with `Content-Disposition: attachment`. License CSV includes metadata header rows + per-SKU data. Security CSV includes MFA users-without section + failed sign-ins section. All values sanitized via `_csv_safe()` (T-08-05 mitigation).

5. **Stale Badge** - Reusable `_report_stale_badge.html` partial showing green/yellow clock icon based on `is_stale` property, age display text, and "Refresh Data" button that POSTs to the SandCastle job trigger API.

6. **Route Registration & Navigation** - Five routes registered in admin `__init__.py`. Reports card with `fa-chart-bar` icon added to admin index page.

## Deviations from Plan

None - plan executed exactly as written.

## Threat Mitigations Applied

- **T-08-05**: `_csv_safe()` prefixes `=`, `+`, `-`, `@` with apostrophe in all CSV output values.
- **T-08-06**: `_validate_date()` rejects non-ISO-8601 date input before passing to sign-in query.
- **T-08-07**: `@require_role("admin")` on every route function; no public report endpoints.

## Self-Check: PASSED
