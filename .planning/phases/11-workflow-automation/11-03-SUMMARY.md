---
phase: 11-workflow-automation
plan: 03
subsystem: workflow-automation
tags: [htmx, admin-ui, offboarding-items, crud, search-integration]
dependency_graph:
  requires:
    - phase: 11-01
      provides: StandardOffboardingItem model
    - phase: 11-02
      provides: workflow routes and create_workflow handler
  provides:
    - Standard offboarding items CRUD admin page
    - Start Onboarding button on search profile cards
    - Employee email pre-population on create workflow form
  affects: [app/blueprints/admin/__init__.py, app/blueprints/search/__init__.py]
tech_stack:
  added: []
  patterns: [inline-htmx-crud, query-param-prefill]
key_files:
  created:
    - app/templates/admin/workflow_offboarding_items.html
  modified:
    - app/blueprints/admin/workflows.py
    - app/blueprints/admin/__init__.py
    - app/blueprints/search/__init__.py
    - app/templates/admin/workflow_create.html
key_decisions:
  - "Adapted profile card button to inline Python HTML (search blueprint builds cards programmatically, not via template file)"
  - "Used soft delete (is_active=False) for offboarding items per RESEARCH guidance"
  - "Pre-population uses HTMX auto-trigger on search input when employee_email query param present"
patterns_established:
  - "Offboarding item CRUD: inline HTMX fragments returned from route handlers"
  - "Profile card admin-only actions: conditional on g.role == admin with url_for linking"
requirements_completed: [WKFL-01, WKFL-02, WKFL-04]
metrics:
  duration: 298s
  completed: 2026-05-18
  tasks_completed: 1
  tasks_total: 2
  checkpoint_pending: true
---

# Phase 11 Plan 03: Offboarding Items Admin and Search Integration Summary

**Standard offboarding items CRUD with HTMX inline management, Start Onboarding button on profile cards for admin users, and employee email pre-population on workflow create form.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-18T05:23:55Z
- **Completed:** 2026-05-18T05:28:53Z
- **Tasks:** 1 of 2 (Task 2 is checkpoint:human-verify, pending)
- **Files modified:** 5

## Accomplishments

- Standard offboarding items fully manageable via /admin/workflows/offboarding-items (add, edit, delete, reorder)
- Start Onboarding button appears on expanded profile cards for admin users, linking to pre-populated create form
- All offboarding item POST routes protected with @require_role("admin") and @csrf_double_submit.protect
- Audit logging on all state-changing offboarding item operations

## Task Commits

1. **Task 1: Standard Offboarding Items Admin and Search Integration** - `ee2f8b8` (feat)
2. **Task 2: Human Verification Checkpoint** - PENDING (checkpoint:human-verify)

## Files Created/Modified

- `app/templates/admin/workflow_offboarding_items.html` - Admin page for managing standard offboarding items with inline add/edit/delete/reorder
- `app/blueprints/admin/workflows.py` - 5 new route handlers for offboarding item CRUD + helper renderer
- `app/blueprints/admin/__init__.py` - 5 new route registrations for offboarding items
- `app/blueprints/search/__init__.py` - Start Onboarding button on profile cards (admin-only)
- `app/templates/admin/workflow_create.html` - Auto-trigger search when employee_email query param provided

## Decisions Made

- Profile card "Start Onboarding" button was added inline in the search blueprint Python code rather than in a Jinja2 template, because the profile card is built programmatically (not via a template file as the plan assumed)
- Soft delete for offboarding items (is_active=False) matches RESEARCH recommendation
- Reorder uses form-submitted item_ids[] array with positional sort_order assignment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Profile card template path does not exist**
- **Found during:** Task 1
- **Issue:** Plan specified `app/templates/search/partials/_profile_card.html` but profile cards are built inline in `app/blueprints/search/__init__.py` as Python f-strings
- **Fix:** Added Start Onboarding button to the inline HTML builder in the search blueprint, following the same pattern as the existing `ad_actions_html` section
- **Files modified:** app/blueprints/search/__init__.py
- **Verification:** `grep -c "Start Onboarding" app/blueprints/search/__init__.py` returns 2
- **Committed in:** ee2f8b8

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Path adaptation necessary; functionality delivered as specified. No scope creep.

## Checkpoint Pending

Task 2 is a `checkpoint:human-verify` gate requiring manual verification of the complete workflow automation feature across all 18 checklist items. This plan cannot be marked fully complete until the human verification is approved.

## Issues Encountered

None beyond the path deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All workflow automation code complete pending human verification
- Feature ready for end-to-end testing: dashboard, create, detail, offboarding items, profile card integration

---
*Phase: 11-workflow-automation*
*Completed: 2026-05-18 (Task 1 only; Task 2 checkpoint pending)*

## Self-Check: PASSED

- [x] app/templates/admin/workflow_offboarding_items.html -- FOUND
- [x] Commit ee2f8b8 -- FOUND
