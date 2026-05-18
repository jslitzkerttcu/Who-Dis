---
phase: 11-workflow-automation
plan: 02
subsystem: workflow-automation
tags: [blueprints, templates, htmx, admin-ui, routes]
dependency_graph:
  requires: [WorkflowService, Workflow, WorkflowItem, StandardOffboardingItem]
  provides: [workflow-dashboard, workflow-create, workflow-detail, workflow-routes]
  affects: [app/blueprints/admin/__init__.py, app/templates/admin/index.html]
tech_stack:
  added: []
  patterns: [tab-dispatch, htmx-fragment, csrf-double-submit, audit-logging]
key_files:
  created:
    - app/blueprints/admin/workflows.py
    - app/templates/admin/workflows.html
    - app/templates/admin/workflow_create.html
    - app/templates/admin/workflow_detail.html
    - app/templates/admin/partials/_workflow_kpi.html
    - app/templates/admin/partials/_workflow_active_table.html
    - app/templates/admin/partials/_workflow_completed_table.html
    - app/templates/admin/partials/_workflow_item.html
  modified:
    - app/blueprints/admin/__init__.py
    - app/templates/admin/index.html
decisions:
  - Used vanilla JS for skip menu and employee search interactions (no Alpine.js) to match project tech stack
  - Skip form renders as sibling div below item row rather than inline swap, to avoid complex HTMX nesting
  - Cancel workflow uses traditional form POST with confirm dialog, matching existing compliance dashboard pattern
metrics:
  duration: 586s
  completed: 2026-05-18T05:20:11Z
  tasks_completed: 2
  tasks_total: 2
  files_created: 8
  files_modified: 2
---

# Phase 11 Plan 02: Workflow Admin UI and Routes Summary

Admin blueprint routes for workflow dashboard, create, detail, and item actions with 4 page templates and 4 HTMX partials following established reports/compliance patterns.

## Task Completion

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Admin Blueprint Routes and Route Wiring | d68ecd3 | app/blueprints/admin/workflows.py, app/blueprints/admin/__init__.py |
| 2 | Dashboard, Create, and Detail Templates with HTMX Partials | d6d1bff | app/templates/admin/workflows.html, workflow_create.html, workflow_detail.html, partials/_workflow_kpi.html, _workflow_active_table.html, _workflow_completed_table.html, _workflow_item.html, admin/index.html |

## What Was Built

### Routes (app/blueprints/admin/workflows.py)

- **workflows_dashboard**: GET /admin/workflows -- KPI stats, tab dispatch (active/completed), HTMX fragment support
- **create_workflow**: GET/POST /admin/workflows/create -- form rendering, validation, workflow generation via WorkflowService
- **preview_checklist**: GET /admin/workflows/preview -- HTMX endpoint returning preview of items for selected job code/type
- **workflow_detail**: GET /admin/workflows/<id> -- detail view with checklist items
- **complete_item**: POST /admin/workflows/items/<id>/complete -- CSRF-protected, audit-logged item completion
- **skip_item**: POST /admin/workflows/items/<id>/skip -- CSRF-protected, audit-logged skip with required reason
- **cancel_workflow**: POST /admin/workflows/<id>/cancel -- CSRF-protected workflow cancellation
- **export_workflow_csv**: GET /admin/workflows/<id>/export -- CSV export of checklist
- **employee_search**: GET /admin/workflows/employee-search -- HTMX typeahead for employee lookup

### Route Wiring (app/blueprints/admin/__init__.py)

- Added `workflows` to import block
- 9 route registrations wired after api_tokens block

### Templates

- **workflows.html**: Dashboard with KPI include, Active/Completed tabs with HTMX tab switching and push-url
- **workflow_create.html**: Two-column form (left: employee search + manual entry toggle, job code dropdown, type radios; right: preview panel). Employee search uses HTMX typeahead with 300ms debounce. Preview updates on job code/type change.
- **workflow_detail.html**: Header with employee info, type badge, status badge, progress bar. Action buttons (Export CSV, Delete). Checklist grouped by item_source with section headers. Items rendered via _workflow_item partial.
- **partials/_workflow_kpi.html**: 4 KPI cards (Active/Overdue/Completed/Avg Time) with icons matching UI-SPEC
- **partials/_workflow_active_table.html**: Table with Employee, Type, Job Code, Progress (bar), Overdue (badge), Created, Actions. Empty state with CTA.
- **partials/_workflow_completed_table.html**: Table with pagination links using hx-get and hx-push-url
- **partials/_workflow_item.html**: Three states (pending/completed/skipped) with checkbox completion, skip menu, and inline skip form

### Admin Index Card

- Workflows card added before Database card with fa-list-check icon, "New" badge, and link to workflows_dashboard

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

- All 9 route handler functions importable from workflows module -- PASS
- All route handlers have @require_role("admin") decorator -- PASS
- State-changing handlers have @csrf_double_submit.protect -- PASS
- Audit logging on create, complete, skip, cancel actions -- PASS
- All 7 templates parse without Jinja2 syntax errors -- PASS
- Ruff lint passes on workflows.py and __init__.py -- PASS
- Admin index.html contains Workflows card with fa-list-check and workflows_dashboard link -- PASS

## Self-Check: PASSED

- [x] app/blueprints/admin/workflows.py -- FOUND
- [x] app/templates/admin/workflows.html -- FOUND
- [x] app/templates/admin/workflow_create.html -- FOUND
- [x] app/templates/admin/workflow_detail.html -- FOUND
- [x] app/templates/admin/partials/_workflow_kpi.html -- FOUND
- [x] app/templates/admin/partials/_workflow_active_table.html -- FOUND
- [x] app/templates/admin/partials/_workflow_completed_table.html -- FOUND
- [x] app/templates/admin/partials/_workflow_item.html -- FOUND
- [x] Commit d68ecd3 -- FOUND
- [x] Commit d6d1bff -- FOUND
