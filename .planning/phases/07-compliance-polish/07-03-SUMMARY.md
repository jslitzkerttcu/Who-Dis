---
phase: 7
plan: 3
subsystem: compliance-ui
tags: [htmx, polling, csv-export, client-sort, tailwind]
dependency_graph:
  requires: [07-01, 07-02]
  provides: [compliance-progress-ui, sync-status-card, csv-export, sortable-table]
  affects: [compliance_dashboard.html, jobs.py, job_role_compliance.py]
tech_stack:
  added: []
  patterns: [htmx-polling, client-side-sort, csv-injection-prevention]
key_files:
  created:
    - app/templates/admin/partials/_compliance_progress.html
    - app/templates/admin/partials/_warehouse_sync_status.html
    - app/static/js/compliance-sort.js
  modified:
    - app/templates/admin/compliance_dashboard.html
    - app/templates/admin/partials/_compliance_violations_table.html
    - app/blueprints/admin/jobs.py
    - app/blueprints/admin/job_role_compliance.py
    - app/blueprints/admin/__init__.py
decisions:
  - Used outerHTML swap for progress-to-results transition to stop HTMX polling naturally
  - CSV export uses full run data ignoring client sort state per UI spec D-12
  - Status column excluded from sortable headers since it has no rank order
metrics:
  duration: 232s
  completed: 2026-05-17
  tasks: 2
  files_changed: 8
---

# Phase 7 Plan 3: UI Layer — Progress, Sync Status, Sortable Table, CSV Export Summary

HTMX progress polling with 2s interval, warehouse sync status card with categorized error messages, client-side sortable violations table with severity-rank comparator, and CSV export with injection prevention.

## What Was Built

### Task 1: Progress Partial, Sync Status Card, Dashboard Wiring
- **_compliance_progress.html**: HTMX polling partial with three states (running/completed/failed). Running state auto-polls status endpoint every 2s; completed state swaps in the full violations table (stops polling). Failed state shows error message.
- **_warehouse_sync_status.html**: Status card showing sync state (success/error/syncing/never) with categorized error messages from UI-SPEC copywriting contract.
- **compliance_dashboard.html**: Wired Run Compliance Check button with hx-post, included sync status card, added progress container.
- **jobs.py**: Enhanced get_job_status to detect HX-Request and return appropriate partials for compliance_check (running/completed/failed) and warehouse_sync jobs.
- **job_role_compliance.py**: Updated compliance_dashboard route to pass SyncMetadata context; updated api_run_compliance_check to return progress partial for HTMX requests.

### Task 2: Client-Side Sorting and CSV Export
- **compliance-sort.js**: ComplianceSortManager class with severity-rank map, date, and text comparators. Initializes on DOMContentLoaded and htmx:afterSettle for dynamic content.
- **_compliance_violations_table.html**: Enhanced with data-sort-column/data-sort-type attributes, sort icons, toolbar with result count and Download CSV button.
- **api_compliance_export**: CSV export endpoint with metadata header rows, CSV injection prevention (apostrophe prefix for =, +, -, @), Content-Disposition attachment header.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | d5b67ee | Progress polling, sync status card, and dashboard wiring |
| 2 | 277c7b9 | Client-side sorting and CSV export for violations table |

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED
