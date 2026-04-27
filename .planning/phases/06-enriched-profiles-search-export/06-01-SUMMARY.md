---
phase: 06-enriched-profiles-search-export
plan: 01
subsystem: services/graph
tags: [graph, msal, identity, enrichment, m365, permissions]
requires:
  - app/services/graph_service.py (existing get_sign_in_logs analog and BaseAPITokenService scaffolding)
  - app/services/base.py::_make_request (raises requests.HTTPError on 4xx via raise_for_status)
provides:
  - GraphService.get_authentication_methods(user_id) — MFA enumeration
  - GraphService.get_license_details(user_id) — per-user license enumeration
  - GraphService.get_subscribed_skus() — tenant SKU catalog
  - GraphService._permission_missing(perm) — D-06 sentinel + dedup ERROR helper
  - signInActivity + assignedLicenses passthrough on /users projection
affects:
  - Plan 06.02 (SkuCatalogCache will call get_subscribed_skus daily)
  - Plan 06.03/06.04 (HTMX endpoints will call the three new methods behind @require_role("viewer"))
  - EmployeeProfile.raw_data (new fields flow through 24h cache, no schema change)
tech-stack:
  added: []
  patterns:
    - "Permission-degradation sentinel: 403 → {error: permission_missing, permission: <scope>}"
    - "Module-level dedupe set so each missing permission logs ERROR exactly once per process"
    - "HTTPError catch (not pre-handle status check) — base _make_request raises on 4xx"
key-files:
  created: []
  modified:
    - app/services/graph_service.py
decisions:
  - "Detected 403 via except requests.HTTPError → e.response.status_code == 403 (deviation from plan wording — see Deviations)"
  - "Empty list ([]) returned when Graph response lacks 'value' key — matches get_sign_in_logs analog"
  - "_permission_missing returns dict, not raises — callers must type-check before iterating (mitigates T-06-04)"
metrics:
  duration: ~3 minutes
  completed: 2026-04-27T01:53:00Z
  tasks_completed: 2
  files_changed: 1
requirements: [PROF-01, PROF-02, PROF-06]
---

# Phase 06 Plan 01: Graph Enrichment Service Methods Summary

Added three Graph API service methods (MFA, license details, SKU catalog) plus signInActivity/assignedLicenses passthrough on the `/users` projection, with a per-permission dedup sentinel that lets downstream HTMX endpoints render inline degradation banners on 403 instead of crashing.

## What Was Built

### Methods Added (`app/services/graph_service.py`)

| Method | Permission Required | Returns on 200 | Returns on 403 |
|--------|---------------------|----------------|----------------|
| `get_authentication_methods(user_id: str) -> Optional[Any]` | `UserAuthenticationMethod.Read.All` | `value` array (or `[]`) | `{"error": "permission_missing", "permission": "UserAuthenticationMethod.Read.All"}` |
| `get_license_details(user_id: str) -> Optional[Any]` | `User.Read.All` (already granted per D-05) | `value` array (or `[]`) | `{"error": "permission_missing", "permission": "User.Read.All"}` |
| `get_subscribed_skus() -> Optional[Any]` | `Organization.Read.All` | `value` array (or `[]`) | `{"error": "permission_missing", "permission": "Organization.Read.All"}` |
| `_permission_missing(permission: str) -> Dict[str, Any]` | n/a (private helper) | n/a | sentinel dict + once-per-startup ERROR via module-level `_logged_missing_perms` set |

All three public methods return `None` on access-token failure or non-403 exceptions, matching the `get_sign_in_logs` analog (D-03).

### Projection Extensions

`_get_select_fields()` now requests `signInActivity` (D-01) and `assignedLicenses` (D-04). `_process_user_data()` carries both keys through the result dict using defensive `.get()` access (PROF-06). `assignedLicenses` defaults to `[]` when omitted; `signInActivity` is left as `None` when absent (then filtered out by the existing `None`-stripping pass at the end of `_process_user_data`, which is consistent with how every other optional field on the result dict already behaves — downstream consumers use `.get()`).

## Permissions Introduced

| Permission | Status on existing app registration | Scope |
|------------|--------------------------------------|-------|
| `AuditLog.Read.All` | Already required by `get_sign_in_logs` (assumed granted) | Premium P1 needed for `signInActivity` field on `/users` |
| `UserAuthenticationMethod.Read.All` | **Unknown — needs verification by admin** | Required for `get_authentication_methods` |
| `User.Read.All` | Already granted (per D-05 assumption in plan) | Required for `get_license_details` |
| `Organization.Read.All` | **Unknown — needs verification by admin** | Required for `get_subscribed_skus` |

The D-06 sentinel mechanism means missing grants produce a single ERROR log line per permission per process startup and an inline degradation banner in Plans 03/04 — they do not crash the request.

## How `_make_request` Handles 4xx (for Plans 03/04)

`app/services/base.py::_make_request` is decorated with `@handle_service_errors(raise_errors=True)` and explicitly calls `response.raise_for_status()`. **It raises `requests.HTTPError` on 4xx**, with the original `Response` available on `e.response`. Plans 03/04 do **not** need to repeat the 403 detection — the new methods absorb it and return either the sentinel dict or `None`. Plan 03/04 endpoints should:

1. Call the method.
2. If result is `None` → log/audit and render generic error banner.
3. If result is a `dict` with key `"error" == "permission_missing"` → render the inline amber banner using `result["permission"]` for the message.
4. Otherwise → iterate `result` as a list.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 403 detection pattern adjusted to match base behavior**
- **Found during:** Task 2
- **Issue:** The plan said "inspect the raw `response.status_code` (NOT `_handle_response`'s data) — if `response is not None and response.status_code == 403`, return `self._permission_missing(...)`". But `BaseAPIService._make_request` calls `response.raise_for_status()` internally, so a 403 response never returns to the caller — it raises `requests.HTTPError`. The plan acknowledges this in action step 5: "If `_make_request` already raises on 4xx in this codebase (verify by reading the file), wrap the call in try/except and check the raised exception's status_code."
- **Fix:** All three new methods use `except requests.HTTPError as e: if e.response is not None and e.response.status_code == 403: return self._permission_missing(...)`. Other status codes fall through to the generic error path. Added `import requests` at module top.
- **Files modified:** `app/services/graph_service.py`
- **Commit:** 283a2b2

### None — All other behavior matches the plan exactly.

## Tests Touched

No test files modified. Existing `tests/unit/services/test_graph_service.py` runs clean (21 passed). New methods are not yet covered by unit tests; testing is intentionally deferred to Plans 06.03/06.04 where the calling endpoints exercise them end-to-end (consistent with the existing pattern for `get_sign_in_logs`, which has no direct unit test either).

## Threat Flags

None. The plan's threat register (T-06-01 through T-06-05) covers all surface introduced. No new endpoints, no new schema, no new trust boundaries — this plan is pure service-layer infrastructure.

## Verification Results

- `python -c "from app.services.graph_service import GraphService"` → succeeds.
- `GraphService()` instance has callable `get_authentication_methods`, `get_license_details`, `get_subscribed_skus` → confirmed.
- `_get_select_fields` includes both `signInActivity` and `assignedLicenses` literals → confirmed.
- `_process_user_data` carries both new fields with `.get()` access → confirmed.
- `grep -c "permission_missing"` = 8 (≥ 4 required).
- `grep -c "signInActivity"` = 2 (one in select, one in process). `grep -c "assignedLicenses"` = 2.
- `grep -n "_logged_missing_perms"` shows 3 sites: declaration, membership check, `add()`.
- `pytest tests/unit/services/test_graph_service.py -x` → 21 passed (3 warnings, all pre-existing). Coverage failure (19% < 60%) is pre-existing project-wide threshold, not regressed by this plan.
- `ruff check app/services/graph_service.py` → All checks passed.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | `2ff556f` | feat(06-01): extend Graph user projection with signInActivity and assignedLicenses |
| 2 | `283a2b2` | feat(06-01): add Graph methods for MFA, license details, and SKU catalog |

## Self-Check: PASSED

- File `app/services/graph_service.py`: FOUND
- Commit `2ff556f`: FOUND in `git log`
- Commit `283a2b2`: FOUND in `git log`
- All success criteria from PLAN.md `<success_criteria>` verified above.
