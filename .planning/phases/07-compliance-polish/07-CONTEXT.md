# Phase 7: Compliance Polish - Context

**Gathered:** 2026-05-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins running bulk compliance checks get real-time progress feedback, can export results as CSV, and can see when warehouse data was last synced — all with graceful error handling instead of raw stack traces. This phase polishes the existing compliance checking infrastructure (models, services, routes already exist) into a production-quality admin experience.

Delivers COMP-01, COMP-02, COMP-03, COMP-04, COMP-05.

</domain>

<decisions>
## Implementation Decisions

### Progress Feedback (COMP-01)
- **D-01:** Compliance check runs as a **SandCastle job** — follows the same manifest/trigger/status pattern used by ProjectCrystalBall and Queue-Tip. WhoDis exposes `GET /api/admin/jobs/manifest`, `POST /api/admin/jobs/{name}`, `GET /api/admin/jobs/{name}/status/{run_id}`. Portal authenticates via Keycloak M2M token (`azp=sandcastle-scheduler`).
- **D-02:** **Both entry paths** — admin UI "Run Compliance Check" button triggers the same job endpoint (POST) and polls status via HTMX. Portal can also trigger on a schedule. Same backend, two entry points.
- **D-03:** Progress UI is a **progress bar + counter** showing "42/150 employees checked" with percentage. HTMX polls the status endpoint every 2s (`hx-trigger="every 2s"`). Shows error count inline if any. Bar disappears when check completes and results table loads.
- **D-04:** Job manager pattern: thread-pool executor (single worker for compliance), mutex to prevent concurrent runs, `ComplianceCheckRun` model already tracks `total_employees`, `total_checks`, `error_count`, `status`. Add `checked_count` field for incremental progress.

### Severity Sorting (COMP-02)
- **D-05:** **Client-side JavaScript sort** on the violations results table. No server round-trip for sort changes. Severity uses a rank map: critical=4, high=3, medium=2, low=1.
- **D-06:** **All columns sortable** — employee, job code, system, violation type, severity, detected date all get clickable sort headers with ascending/descending toggle.

### Warehouse Sync Visibility (COMP-04, COMP-05)
- **D-07:** Warehouse sync is **also a SandCastle job** registered in the manifest alongside compliance_check. Manual re-sync button in admin UI triggers the same job endpoint.
- **D-08:** **Both SandCastle job status + local sync_metadata record**. A `sync_metadata` table/row stores `last_success_at`, `last_error_at`, `last_error_message`, `last_error_category`. UI reads local record for display; portal tracks scheduling history.
- **D-09:** **Categorized error messages** — map pyodbc error codes to human-readable categories: "Connection timeout — warehouse unreachable", "Authentication failed — check service principal credentials", "Query timeout — warehouse may be under load". Show category + timestamp, hide raw stack trace.
- **D-10:** Re-sync button **disabled during sync** — grays out + shows "Syncing..." while active. Re-enables when done. Standard mutex pattern from the job manager.

### CSV Export (COMP-03)
- **D-11:** Export button appears **on the results table** after a compliance check completes. "Download CSV" button above the violations table. Hidden when no run has completed.
- **D-12:** CSV always exports the **full run** regardless of active filters/sort. Compliance reports need the complete picture.
- **D-13:** **Metadata header rows** — first 3-4 rows contain run context: Run ID, Date/Time (UTC), Scope, Triggered By. Blank row separator, then column headers + data rows.
- **D-14:** Required columns: Employee (UPN), Job Code, System, Expected Role, Actual Assignment (true/false), Violation Type, Severity, Remediation Action.

### Claude's Discretion
- Severity sorting approach chosen: client-side JS (small team, <1000 rows typical)
- Export button placement: on results table (matches Phase 6 per-profile export pattern)
- Export scope: full run always (compliance reports need complete picture)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### SandCastle Job Pattern (reference implementations)
- `/Users/jslitzker/Repos/ProjectCrystalBall/src/api/v2/routers/jobs.py` — Job manifest schema, JOB_REGISTRY pattern, status polling endpoints, pipeline step structure
- `/Users/jslitzker/Repos/ProjectCrystalBall/src/api/v2/job_manager.py` — Thread-pool executor job manager with SQLite state, mutex lock, progress_callback pattern
- `/Users/jslitzker/Repos/Queue-Tip/src/auth/keycloak_deps.py` — Portal M2M token validation (`azp=sandcastle-scheduler`)

### Existing WhoDis Compliance Code
- `app/services/compliance_checking_service.py` — Current synchronous check logic, batch processing, ComplianceCheckRun lifecycle
- `app/services/job_role_warehouse_service.py` — Warehouse sync via pyodbc, Azure SQL connection string, sync methods
- `app/blueprints/admin/job_role_compliance.py` — Current routes (api_run_compliance_check, api_sync_job_codes, compliance_dashboard)
- `app/models/job_role_compliance.py` — ComplianceCheck, ComplianceCheckRun, JobCode, SystemRole models

### Requirements
- `.planning/REQUIREMENTS.md` §COMP-01..05 — Compliance hardening requirements

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ComplianceCheckRun` model: already has `run_id`, `status`, `total_employees`, `total_checks`, `error_count`, `started_by`, `mark_completed()`, `mark_failed()` — needs only `checked_count` added for progress
- `ComplianceCheckingService.run_compliance_check()`: batch-of-50 loop already exists, just needs progress updates per batch
- `api_compliance_violations()`: pagination and severity filtering already in place — add sort headers to the template
- `JobCode.synced_at` / `SystemRole.synced_at`: per-record sync timestamps exist, need a global summary
- Token refresh background threading pattern in `app/container.py` — similar executor pattern

### Established Patterns
- HTMX partial fragments: all compliance routes already return HTML for `HX-Request` headers
- Keycloak authentication: Phase 4 established the auth stack; portal M2M token validation follows same Keycloak JWKS pattern
- `@require_role("admin")` on all compliance routes — new job endpoints use same decorator + portal service account bypass

### Integration Points
- New `/api/admin/jobs/` blueprint for manifest and job endpoints (portal integration)
- Existing admin blueprint routes refactored to use job manager internally
- Docker-compose: no new container needed (job runs in-process via thread pool, single gunicorn worker for job state consistency)

</code_context>

<specifics>
## Specific Ideas

- Follow CrystalBall's `JobManifestEntry` schema exactly for portal compatibility (name, description, endpoint, default_cron, timeout_seconds, display_name, method, dependencies)
- Job manager should be Flask-adapted version of CrystalBall's pattern (use PostgreSQL instead of SQLite for state since WhoDis already has it)
- Progress bar should auto-dismiss and swap to results table when run completes (HTMX `hx-swap="outerHTML"` on final poll)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 7-Compliance Polish*
*Context gathered: 2026-05-16*
