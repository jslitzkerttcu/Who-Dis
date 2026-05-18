---
phase: 09-write-operations
plan: 03
subsystem: license-management
tags: [graph-api, license, htmx, write-operations, m365]
dependency_graph:
  requires: [09-01, 09-02]
  provides: [license-endpoints, license-ui, sku-dropdown]
  affects: [_m365_section.html, write_routes.py, write-actions.js]
tech_stack:
  added: []
  patterns: [htmx-fragment-loading, dual-dropdown-modal, showBanner-event-bridge]
key_files:
  created:
    - app/templates/search/_license_actions.html
    - app/templates/search/_license_select.html
    - tests/unit/test_license_endpoints.py
  modified:
    - app/blueprints/search/write_routes.py
    - app/blueprints/search/__init__.py
    - app/templates/search/_m365_section.html
    - app/templates/search/_write_confirm_modal.html
    - app/static/js/write-actions.js
decisions:
  - "License actions use same confirmation modal as AD actions with modalType extension"
  - "showBanner event bridge handles D-09 double failure with duration=0 (no auto-dismiss)"
  - "Per-chip remove icon uses group-hover pattern for admin-only visibility"
  - "Added display_name and user_email to M365 section data dict for license action context"
metrics:
  duration: "6 minutes"
  completed: "2026-05-18"
---

# Phase 9 Plan 03: License Management UI Summary

License write endpoints and action UI wired end-to-end with assign/remove/swap modals, SKU dropdown fragments, and persistent error banner for swap double-failure.

## Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | License write endpoints + SKU fragment + tests | 1506133 | write_routes.py, _license_select.html, test_license_endpoints.py |
| 2 | License action UI + M365 section integration | 221dbfe | _license_actions.html, _m365_section.html, write-actions.js, _write_confirm_modal.html |

## Implementation Details

### Task 1: License Write Endpoints

Added 4 new endpoints to write_routes.py:
- `GET /search/api/write/available-skus` - Returns HTML fragment with SKU options (availability counts, disabled state for 0-available)
- `POST /search/api/write/assign-license` - Assign license with HX-Trigger toast
- `POST /search/api/write/remove-license` - Remove license (high-risk per D-14)
- `POST /search/api/write/swap-license` - Swap with 4 result state handling:
  - success -> toast
  - rollback_success -> warning toast
  - double_failure -> showBanner (persistent, D-09)
  - standard failure -> error response

All POST endpoints use `@require_role("admin")` + `@csrf_double_submit.protect`.
Total `require_role("admin")` count: 8 (4 AD + 4 license).

### Task 2: License Action UI

- `_license_actions.html`: Admin-only button group (Assign + Swap) with empty state message
- Per-chip remove icon: `fa-times` button with `opacity-0 group-hover:opacity-100` on each license chip
- `write-actions.js` extended with `modalType` parameter handling:
  - `assign-license`: SKU dropdown loaded via fetch on modal open
  - `swap-license`: Dual dropdowns (remove from current + assign from available, filtered), max-w-lg modal
  - `remove-license`: Pre-populated from chip data attributes
- `showBanner` event listener for D-09 double failure (duration=0, no auto-dismiss)
- Confirm button validation requires both dropdown selection(s) AND reason >= 3 chars

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added display_name and user_email to M365 data dict**
- **Found during:** Task 2
- **Issue:** `_m365_section.html` template only receives `data` dict which lacked user display name and email needed for license action modal context
- **Fix:** Added `display_name` and `user_email` fields to the return dict in `_build_m365_section_data()` (from `user_profile.get("displayName")` and `user_profile.get("userPrincipalName")`)
- **Files modified:** app/blueprints/search/__init__.py
- **Commit:** 221dbfe

## Verification

- All Python files pass `ruff check` (no errors)
- All Jinja2 templates compile without errors
- Unit tests syntax-valid (cannot run in this environment due to Docker requirement for testcontainers)
- `require_role("admin")` count verified at 8 (4 AD + 4 license)
- `_m365_section.html` includes `_license_actions.html` confirmed
- `write-actions.js` contains `showBanner` event handling confirmed

## Self-Check: PASSED

- [x] app/templates/search/_license_actions.html EXISTS
- [x] app/templates/search/_license_select.html EXISTS
- [x] tests/unit/test_license_endpoints.py EXISTS
- [x] Commit 1506133 EXISTS
- [x] Commit 221dbfe EXISTS
