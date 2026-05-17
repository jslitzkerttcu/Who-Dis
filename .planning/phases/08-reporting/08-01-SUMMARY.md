---
phase: "08-reporting"
plan: "01"
subsystem: "reporting-backend"
tags: [graph-api, genesys-api, report-cache, sync-service, sandcastle-jobs]
dependency_graph:
  requires: []
  provides: [ReportCache-model, ReportSyncService, bulk-graph-methods, bulk-genesys-methods, report-jobs]
  affects: [08-02-PLAN, 08-03-PLAN]
tech_stack:
  added: []
  patterns: [tiered-ttl-cache, hybrid-cache-live-query, paginated-bulk-api, odata-pagination]
key_files:
  created:
    - app/models/report_cache.py
    - app/services/report_sync_service.py
  modified:
    - app/services/graph_service.py
    - app/services/genesys_service.py
    - app/blueprints/admin/jobs.py
    - app/container.py
decisions:
  - "MFA endpoint uses v1.0 (not beta) per RESEARCH.md Pattern 2 for stable bulk data"
  - "ISO 8601 regex validation on date inputs before OData embedding (T-08-04 mitigation)"
  - "Genesys presence is live-only (not cached) per D-09 real-time requirement"
metrics:
  duration: "210s"
  completed: "2026-05-17T19:12:02Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 2
  files_modified: 4
---

# Phase 08 Plan 01: Reporting Backend Data Layer Summary

ReportCache model with tiered TTL upsert pattern, ReportSyncService aggregating license/MFA/sign-in data from Graph API bulk endpoints, Genesys bulk presence method, and two SandCastle job manifest entries.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | ReportCache model | e3eb51e | app/models/report_cache.py |
| 2 | Graph bulk methods and Genesys bulk presence | 383fb17 | app/services/graph_service.py, app/services/genesys_service.py |
| 3 | ReportSyncService, job registration, DI wiring | 36a4540 | app/services/report_sync_service.py, app/blueprints/admin/jobs.py, app/container.py |

## What Was Built

1. **ReportCache Model** - PostgreSQL-backed cache with `report_type`/`cache_key` unique constraint, `is_stale` property comparing `generated_at + ttl_hours` against UTC now, `age_display` for template rendering, `store()` upsert classmethod, `get_cached()` retrieval.

2. **Graph Bulk Methods** - Three new paginated methods on GraphService:
   - `get_all_users_with_licenses()` - /beta/users with ConsistencyLevel:eventual, $top=500
   - `get_mfa_registration_details()` - v1.0 userRegistrationDetails (stable endpoint)
   - `get_failed_signins_bulk(from_date, to_date)` - /beta/auditLogs/signIns with ISO 8601 validation

3. **Genesys Bulk Presence** - `get_all_agents_presence()` via POST /api/v2/users/search with presence+routingStatus expand, paginated by pageNumber.

4. **ReportSyncService** - Orchestrates Graph API calls into ReportCache:
   - `sync_license_data()`: per-SKU utilization + 30-day unused detection (ttl=4h)
   - `sync_security_data()`: MFA registration + failed sign-ins (ttl=1h)
   - `get_failed_signins()`: hybrid cache/live pattern per D-07

5. **SandCastle Jobs** - `report_license_sync` (daily 4am) and `report_security_sync` (hourly) registered with runners in JOB_REGISTRY.

6. **DI Registration** - `report_sync_service` registered in container.py.

## Deviations from Plan

None - plan executed exactly as written.

## Threat Mitigations Applied

- **T-08-04**: ISO 8601 regex validation on `from_date`/`to_date` parameters in `get_failed_signins_bulk()` before embedding in OData $filter string.
- **T-08-01**: Response structure validated (dict check for "error" key) before storing in ReportCache; raw HTML never stored.
- **T-08-02**: Job endpoints inherit `@admin_or_portal_required` from existing jobs.py pattern.

## Self-Check: PASSED
