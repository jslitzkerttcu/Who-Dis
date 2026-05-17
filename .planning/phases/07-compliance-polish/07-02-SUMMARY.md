---
phase: "07"
plan: "02"
subsystem: "jobs-api"
tags: [sandcastle, jobs, portal-auth, compliance, warehouse]
dependency_graph:
  requires: [07-01]
  provides: [jobs-blueprint, portal-auth, warehouse-error-categorization, compliance-progress]
  affects: [admin-blueprint, warehouse-service, compliance-service]
tech_stack:
  added: [PyJWT/JWKS validation]
  patterns: [M2M token auth, error categorization, progress callback]
key_files:
  created:
    - app/auth/portal_auth.py
    - app/blueprints/admin/jobs.py
  modified:
    - app/blueprints/admin/__init__.py
    - app/services/job_role_warehouse_service.py
    - app/services/compliance_checking_service.py
decisions:
  - "Used PyJWKClient for RS256 token validation against Keycloak JWKS endpoint"
  - "Applied admin_or_portal_required at function level (not via add_url_rule wrapper) for clarity"
metrics:
  duration_seconds: 157
  completed: "2026-05-17T02:27:56Z"
  tasks_completed: 2
  tasks_total: 2
---

# Phase 07 Plan 02: SandCastle Job API & Service Adaptations Summary

**One-liner:** Portal auth decorator with Keycloak JWKS validation, jobs blueprint with manifest/trigger/status endpoints, warehouse error categorization with SyncMetadata tracking, and compliance progress callback.

## What Was Built

1. **Portal Auth Decorator** (`app/auth/portal_auth.py`): `admin_or_portal_required` allows access for admin session users OR M2M Bearer tokens from the `sandcastle-scheduler` service account, validated via RS256 against Keycloak JWKS.

2. **Jobs Blueprint** (`app/blueprints/admin/jobs.py`): Three endpoints consumed by SandCastle scheduler:
   - `GET /api/admin/jobs/manifest` - returns job registry
   - `POST /api/admin/jobs/<name>` - triggers job via JobManagerService
   - `GET /api/admin/jobs/<name>/status/<run_id>` - returns run status

3. **Warehouse Error Categorization**: `WAREHOUSE_ERROR_CATEGORIES` dict maps pyodbc SQLSTATE codes (08001, 08S01, 28000, HYT00, HYT01) to categories. `_update_sync_metadata` persists success/failure state to SyncMetadata model.

4. **Compliance Progress Callback**: `run_compliance_check` now accepts `progress_callback: Optional[Callable[[int, int], None]]` and updates `checked_count` on `ComplianceCheckRun` after each batch.

## Commits

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Portal auth decorator and jobs blueprint | d66edc4 | portal_auth.py, jobs.py, admin/__init__.py |
| 2 | Warehouse error categorization and compliance progress | 50af94b | job_role_warehouse_service.py, compliance_checking_service.py |

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

- `from app.auth.portal_auth import admin_or_portal_required` - PASS
- `JOB_REGISTRY` has 2 entries with correct names - PASS
- `WAREHOUSE_ERROR_CATEGORIES` contains '08001' - PASS
- `progress_callback` in `run_compliance_check` signature - PASS

## Self-Check: PASSED
