# Phase 7: Compliance Polish - Research

**Researched:** 2026-05-16
**Domain:** Flask background jobs, HTMX progress polling, CSV export, SandCastle job pattern adaptation
**Confidence:** HIGH

## Summary

Phase 7 polishes the existing compliance checking infrastructure into a production-quality admin experience. The core work involves: (1) implementing a SandCastle-compatible job manager adapted from ProjectCrystalBall's pattern but using PostgreSQL instead of SQLite for state, (2) wiring HTMX polling for real-time progress feedback during bulk compliance checks, (3) adding client-side JavaScript sorting to the violations table, (4) building CSV export with metadata headers, and (5) adding warehouse sync status visibility with categorized error messages.

The existing codebase is remarkably well-prepared. `ComplianceCheckRun` already tracks `total_employees`, `total_checks`, `error_count`, and `status`. The `run_compliance_check()` method already processes in batches of 50. The violations table template already exists with severity filtering. The main additions are: a `checked_count` column for incremental progress, a job manager service, new API endpoints for the SandCastle manifest pattern, and a `sync_metadata` table for warehouse sync tracking.

**Primary recommendation:** Adapt CrystalBall's job_manager.py into a Flask-native `JobManagerService` that stores state in PostgreSQL (not SQLite), registers `compliance_check` and `warehouse_sync` as SandCastle jobs, and uses the existing `ThreadPoolExecutor` + mutex pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Compliance check runs as a SandCastle job with manifest/trigger/status endpoints at `/api/admin/jobs/`
- **D-02:** Both admin UI button and portal scheduler can trigger via same POST endpoint
- **D-03:** Progress UI is progress bar + counter showing "42/150 employees checked" with HTMX polling every 2s
- **D-04:** Job manager uses thread-pool executor (single worker for compliance), mutex to prevent concurrent runs, `ComplianceCheckRun` model tracks progress with new `checked_count` field
- **D-05:** Client-side JavaScript sort for violations table (no server round-trip)
- **D-06:** All columns sortable with ascending/descending toggle
- **D-07:** Warehouse sync is also a SandCastle job in the manifest
- **D-08:** Both SandCastle job status + local `sync_metadata` record for UI display
- **D-09:** Categorized error messages mapping pyodbc error codes to human-readable text
- **D-10:** Re-sync button disabled during sync with "Syncing..." text
- **D-11:** Export button appears on results table after compliance check completes
- **D-12:** CSV exports full run regardless of active filters/sort
- **D-13:** CSV has metadata header rows (Run ID, Date/Time UTC, Scope, Triggered By)
- **D-14:** CSV columns: Employee (UPN), Job Code, System, Expected Role, Actual Assignment (true/false), Violation Type, Severity, Remediation Action

### Claude's Discretion
- Severity sorting approach chosen: client-side JS (small team, <1000 rows typical)
- Export button placement: on results table (matches Phase 6 per-profile export pattern)
- Export scope: full run always (compliance reports need complete picture)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMP-01 | Admin can see real-time progress during bulk compliance checks via HTMX polling | Job manager service + HTMX partial `_compliance_progress.html` polling every 2s; `checked_count` field on `ComplianceCheckRun` |
| COMP-02 | Admin can sort violations by severity (critical > high > medium > low) | Client-side JS sort with rank map {critical:4, high:3, medium:2, low:1}; all columns sortable |
| COMP-03 | Admin can export compliance results as CSV | `GET /admin/api/compliance-export/{run_id}` returning `Content-Disposition: attachment`; metadata headers + data rows |
| COMP-04 | Warehouse sync failures display clear user-facing error messages | Categorized pyodbc error mapping in `JobRoleWarehouseService`; `sync_metadata` table stores `last_error_category` |
| COMP-05 | Admin UI shows when warehouse data was last synced with manual sync trigger | `sync_metadata` table with `last_success_at`; Sync Status Card partial with "Sync Now" button |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Job execution (compliance check, warehouse sync) | API / Backend | -- | CPU-bound batch processing, DB writes, external warehouse queries |
| Progress polling | API / Backend | Browser / Client | Server stores state; HTMX polls and swaps HTML fragments |
| Client-side table sorting | Browser / Client | -- | Pure JS on rendered table (D-05, no server round-trip) |
| CSV generation | API / Backend | -- | Server queries DB, builds CSV response with headers |
| Sync status display | API / Backend | Browser / Client | Server renders partial; HTMX refreshes on state change |
| SandCastle portal integration | API / Backend | -- | Manifest + job endpoints for external scheduler |
| Keycloak M2M auth for portal | API / Backend | -- | Token validation middleware for `azp=sandcastle-scheduler` |

## Standard Stack

### Core (already in project -- no new packages)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | Web framework | Project standard [VERIFIED: requirements.txt] |
| SQLAlchemy | 2.0.45 | ORM | Project standard [VERIFIED: requirements.txt] |
| HTMX | 1.9.10 | Client-side polling + partial swaps | Project standard [VERIFIED: base.html CDN link] |
| Jinja2 | (Flask bundled) | Template rendering | Project standard |
| pyodbc | 5.3.0 | Azure SQL warehouse connectivity | Project standard [VERIFIED: requirements.txt] |
| authlib | (installed Phase 4) | Keycloak OIDC + JWT validation | Project standard [VERIFIED: app/auth/oidc.py] |

### Supporting (no new installs needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `concurrent.futures` | stdlib | ThreadPoolExecutor for background jobs | Job manager service |
| `threading` | stdlib | Lock/mutex for job concurrency control | Prevent duplicate runs |
| `csv` | stdlib | CSV generation | Export endpoint |
| `io.StringIO` | stdlib | In-memory CSV buffer | Stream response without temp file |
| `uuid` | stdlib | Job run IDs | Unique identifiers for job runs |
| `PyJWT` / `authlib` | installed | Portal M2M token validation | SandCastle scheduler auth |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ThreadPoolExecutor (in-process) | Celery | Overkill for 4-5 user team; adds Redis/RabbitMQ dependency |
| PostgreSQL job state | SQLite (like CrystalBall) | WhoDis already uses PostgreSQL; no need for second DB engine |
| Client-side JS sort | Server-side sort (HTMX) | D-05 locks client-side; avoids round-trip for <1000 rows |
| HTMX polling | WebSocket/SSE | Polling every 2s is simpler and sufficient for this use case |

**Installation:** No new packages required. All dependencies already in `requirements.txt`.

## Package Legitimacy Audit

> No new packages installed in this phase. All libraries are existing project dependencies or Python stdlib modules.

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Admin UI (Browser)                          SandCastle Portal
    |                                             |
    | POST /api/admin/jobs/compliance_check       | POST /api/admin/jobs/compliance_check
    | (HTMX form submit)                          | (M2M token: azp=sandcastle-scheduler)
    v                                             v
+-----------------------------------------------------------+
| Flask: /api/admin/jobs/ Blueprint                          |
| - GET  /manifest          (job discovery)                  |
| - POST /{name}            (trigger job)                    |
| - GET  /{name}/status/{run_id}  (poll progress)           |
+-----------------------------------------------------------+
    |                            |
    | Auth: @require_role("admin") OR portal M2M token
    v
+-----------------------------------------------------------+
| JobManagerService (singleton in DI container)              |
| - ThreadPoolExecutor(max_workers=1)                       |
| - threading.Lock (mutex)                                  |
| - start_job() -> run_id                                   |
| - get_status(run_id) -> {status, checked_count, total}    |
+-----------------------------------------------------------+
    |                                    |
    | compliance_check job               | warehouse_sync job
    v                                    v
+---------------------------+    +---------------------------+
| ComplianceCheckingService |    | JobRoleWarehouseService   |
| .run_compliance_check()   |    | .sync_all_compliance_data()|
| - batch of 50             |    | - pyodbc to Azure SQL     |
| - progress_callback()     |    | - categorized errors      |
| - updates ComplianceCheckRun | | - updates sync_metadata   |
+---------------------------+    +---------------------------+
    |                                    |
    v                                    v
+-----------------------------------------------------------+
| PostgreSQL                                                 |
| - compliance_check_runs (+ checked_count column)          |
| - compliance_checks                                        |
| - sync_metadata (new table)                               |
| - job_runs (new table for job manager state)              |
+-----------------------------------------------------------+
```

### Recommended Project Structure

```
app/
├── blueprints/
│   └── admin/
│       ├── jobs.py                    # NEW: SandCastle job endpoints
│       └── job_role_compliance.py     # MODIFIED: wire job manager, add CSV export
├── services/
│   ├── job_manager_service.py         # NEW: Flask-adapted job manager
│   ├── compliance_checking_service.py # MODIFIED: add progress_callback
│   └── job_role_warehouse_service.py  # MODIFIED: categorized errors, sync_metadata
├── models/
│   ├── job_role_compliance.py         # MODIFIED: add checked_count to ComplianceCheckRun
│   └── sync_metadata.py              # NEW: SyncMetadata model
├── templates/admin/
│   ├── partials/
│   │   ├── _compliance_progress.html  # NEW: progress bar partial
│   │   ├── _warehouse_sync_status.html # NEW: sync status card
│   │   └── _compliance_violations_table.html  # MODIFIED: sortable headers, CSV button
│   └── compliance_dashboard.html      # MODIFIED: wire progress + sync card
├── static/js/
│   └── compliance-sort.js             # NEW: client-side table sorting
└── auth/
    └── oidc.py                        # EXISTING: handles M2M token validation
```

### Pattern 1: SandCastle Job Manager (adapted from CrystalBall)

**What:** A Flask-adapted job manager storing state in PostgreSQL instead of SQLite.
**When to use:** Any background task that needs: trigger API, progress tracking, mutex prevention of concurrent runs, portal scheduling integration.

**Key differences from CrystalBall reference:**
- Uses PostgreSQL via SQLAlchemy instead of SQLite (WhoDis already has PostgreSQL)
- Flask app context management (requires `app.app_context()` in worker thread)
- Simpler than CrystalBall (no composite pipeline runs needed -- just individual jobs)
- Single worker thread pool (compliance check + warehouse sync are mutually exclusive enough)

```python
# Source: Adapted from ProjectCrystalBall/src/api/v2/job_manager.py
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

from flask import current_app

class JobManagerService:
    """Flask-native job manager with PostgreSQL state."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()

    def start_job(self, job_name: str, runner_fn: Callable, app=None) -> str:
        """Start a background job. Returns run_id. Raises ConflictError if already running."""
        with self._lock:
            # Check for active run of same type in DB
            active = JobRun.query.filter_by(
                job_name=job_name, status="running"
            ).first()
            if active:
                raise ConflictError(f"{job_name} already running", active.run_id)

            run_id = str(uuid.uuid4())
            job_run = JobRun(
                run_id=run_id,
                job_name=job_name,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            db.session.add(job_run)
            db.session.commit()

        # Submit to thread pool with Flask app context
        app = app or current_app._get_current_object()
        self._executor.submit(self._run_with_context, app, run_id, runner_fn)
        return run_id

    def _run_with_context(self, app, run_id: str, fn: Callable):
        """Execute job within Flask app context."""
        with app.app_context():
            try:
                fn(run_id=run_id)
                # Mark completed
                job_run = JobRun.query.filter_by(run_id=run_id).first()
                job_run.status = "completed"
                job_run.completed_at = datetime.now(timezone.utc)
                db.session.commit()
            except Exception as e:
                job_run = JobRun.query.filter_by(run_id=run_id).first()
                job_run.status = "failed"
                job_run.error = str(e)[:500]
                job_run.completed_at = datetime.now(timezone.utc)
                db.session.commit()
```

### Pattern 2: HTMX Progress Polling

**What:** Server returns different HTML fragments based on job state; HTMX auto-polls until complete then swaps to results.
**When to use:** Long-running operations where user needs visual feedback.

```html
<!-- Source: HTMX 1.9 docs + project pattern -->
<!-- _compliance_progress.html (returned while job is running) -->
<div id="compliance-progress"
     hx-get="/api/admin/jobs/compliance_check/status/{{ run_id }}"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
  <div class="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
    <div class="bg-blue-600 rounded-full h-2 transition-all duration-300"
         style="width: {{ percent }}%"></div>
  </div>
  <div class="flex justify-between items-center mt-2 text-sm text-gray-600">
    <span>{{ checked_count }}/{{ total_employees }} employees checked</span>
    <span>{{ percent }}% complete</span>
  </div>
</div>
```

When job completes, the status endpoint returns the results table instead (with `hx-swap="outerHTML"` replacing the progress div with the full violations table).

### Pattern 3: Portal M2M Token Authentication

**What:** SandCastle portal authenticates with Keycloak M2M token (`azp=sandcastle-scheduler`). Job endpoints accept both admin session cookies AND portal bearer tokens.
**When to use:** Any endpoint the portal scheduler needs to trigger.

```python
# Source: Queue-Tip/src/auth/keycloak_deps.py (adapted for Flask)
from functools import wraps
from flask import request, g
import jwt as pyjwt

PORTAL_SERVICE_ACCOUNT = "sandcastle-scheduler"

def admin_or_portal_required(f):
    """Allow either admin session OR portal M2M bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if admin session exists (standard @auth_required path)
        if g.get("user") and g.get("role") == "admin":
            return f(*args, **kwargs)

        # Check for Bearer token (portal M2M)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            claims = validate_portal_token(token)
            if claims and claims.get("azp") == PORTAL_SERVICE_ACCOUNT:
                g.user = "sandcastle-scheduler"
                return f(*args, **kwargs)

        abort(403)
    return decorated
```

### Pattern 4: Categorized Error Mapping (D-09)

**What:** Map pyodbc error codes/exception types to human-readable categories.
**When to use:** Any warehouse operation that can fail with opaque ODBC errors.

```python
# Error categorization map for pyodbc exceptions
WAREHOUSE_ERROR_CATEGORIES = {
    "08001": ("connection_timeout", "Connection timeout - warehouse unreachable"),
    "08S01": ("connection_timeout", "Connection timeout - warehouse unreachable"),
    "28000": ("auth_failed", "Authentication failed - check service principal credentials"),
    "HYT00": ("query_timeout", "Query timeout - warehouse may be under load"),
    "HYT01": ("query_timeout", "Query timeout - warehouse may be under load"),
}

def categorize_pyodbc_error(error: Exception) -> tuple:
    """Return (category, message) for a pyodbc error."""
    if hasattr(error, "args") and error.args:
        error_str = str(error.args[0]) if error.args else ""
        for code, (category, message) in WAREHOUSE_ERROR_CATEGORIES.items():
            if code in error_str:
                return category, message
    return "unknown", "Sync failed - an unexpected error occurred"
```

### Anti-Patterns to Avoid
- **Running compliance check synchronously in request thread:** The existing `api_run_compliance_check()` does this -- must be refactored to use job manager
- **Storing job state in memory only:** CrystalBall uses in-memory composite state which is lost on restart. WhoDis should store all state in PostgreSQL for durability across gunicorn worker restarts
- **Polling without a termination condition:** HTMX `hx-trigger="every 2s"` must stop when job completes. Use conditional `hx-trigger` or swap the element entirely (outerHTML swap to results table)
- **Thread without Flask app context:** Background threads cannot access `current_app` or `db.session` without explicit `app.app_context()` -- use `copy_current_request_context` or pass `app` reference

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background job management | Custom daemon threads | ThreadPoolExecutor + PostgreSQL state table | Proper lifecycle, state persistence, mutex coordination |
| CSV generation | Manual string concatenation | Python stdlib `csv` module + `io.StringIO` | Handles quoting, escaping, Unicode properly |
| Progress bar UI | Custom polling JavaScript | HTMX `hx-trigger="every 2s"` + server-side state | Zero JS needed for polling; project standard |
| Token validation | Manual JWT decode | authlib/PyJWT with JWKS endpoint | Key rotation, signature verification, expiry checks |
| Error categorization | Generic try/except | Categorized error map keyed by ODBC error codes | Consistent user-facing messages, auditable |

**Key insight:** This phase's complexity is in the orchestration (job lifecycle, progress updates, HTMX swapping), not in any single technical challenge. The CrystalBall reference implementation provides a proven pattern -- adaptation to Flask/PostgreSQL is straightforward.

## Common Pitfalls

### Pitfall 1: Flask App Context in Background Threads
**What goes wrong:** `RuntimeError: Working outside of application context` when background thread tries to access `current_app` or `db.session`.
**Why it happens:** ThreadPoolExecutor runs functions in a separate thread without Flask context.
**How to avoid:** Pass `app = current_app._get_current_object()` before submitting to executor, then wrap the job body in `with app.app_context():`.
**Warning signs:** Any `db.session` call in the job runner function.

### Pitfall 2: HTMX Polling Doesn't Stop
**What goes wrong:** Browser keeps polling the status endpoint forever even after job completes.
**Why it happens:** The progress partial keeps the `hx-trigger="every 2s"` attribute even after completion.
**How to avoid:** When job completes, return a different HTML fragment (the results table) that does NOT have `hx-trigger`. The `hx-swap="outerHTML"` replaces the polling element entirely.
**Warning signs:** Network tab shows continuous 2s requests after completion.

### Pitfall 3: Concurrent Compliance Check Runs
**What goes wrong:** Two admins click "Run Compliance Check" simultaneously, creating duplicate/conflicting data.
**Why it happens:** Without mutex, both requests pass the "is running?" check before either starts.
**How to avoid:** Use threading.Lock in the job manager (following CrystalBall pattern). Also check DB state within the lock. Return HTTP 409 Conflict if already running.
**Warning signs:** Multiple `ComplianceCheckRun` records with overlapping `started_at` timestamps.

### Pitfall 4: Memory Exhaustion on Large CSV Export
**What goes wrong:** Loading all compliance checks into memory for a large run (thousands of rows).
**Why it happens:** `ComplianceCheck.query.filter_by(check_run_id=run_id).all()` loads everything.
**How to avoid:** Use SQLAlchemy `yield_per()` or stream the response with Flask's `stream_with_context`.
**Warning signs:** High memory usage on export of runs with 5000+ checks.

### Pitfall 5: pyodbc Error Codes Are Driver-Specific
**What goes wrong:** Error categorization fails because ODBC driver returns different error codes than expected.
**Why it happens:** Error codes vary by ODBC driver version and SQL Server version.
**How to avoid:** Match on substring patterns in the error message, not just the SQLSTATE code. Include a fallback "unknown" category. Log the raw error for debugging.
**Warning signs:** All warehouse errors show "unexpected error" generic message.

## Code Examples

### CSV Export Endpoint

```python
# Source: Python stdlib csv module + Flask streaming pattern
import csv
import io
from flask import Response, g
from datetime import datetime, timezone

@require_role("admin")
def api_compliance_export(run_id):
    """Export compliance results as CSV with metadata headers."""
    check_run = ComplianceCheckRun.query.filter_by(run_id=run_id).first()
    if not check_run:
        return jsonify({"error": "Run not found"}), 404

    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata header rows (D-13)
    writer.writerow([f"Run ID: {check_run.run_id}"])
    writer.writerow([f"Date/Time (UTC): {check_run.started_at.strftime('%Y-%m-%d %H:%M:%S')}"])
    writer.writerow([f"Scope: {check_run.scope or 'All employees'}"])
    writer.writerow([f"Triggered By: {check_run.started_by}"])
    writer.writerow([])  # Blank separator

    # Column headers (D-14)
    writer.writerow([
        "Employee (UPN)", "Job Code", "System", "Expected Role",
        "Actual Assignment", "Violation Type", "Severity", "Remediation Action"
    ])

    # Data rows - stream from DB
    checks = ComplianceCheck.query.filter_by(check_run_id=run_id).yield_per(100)
    for check in checks:
        writer.writerow([
            check.employee_upn,
            check.job_code,
            check.system_name,
            check.role_name,
            str(check.actual_assignment).lower(),
            check.compliance_status,
            check.violation_severity,
            check.remediation_action or "",
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=compliance_run_{run_id}.csv"}
    )
    return response
```

### Client-Side Table Sort (D-05, D-06)

```javascript
// Source: Vanilla JS sort pattern for static HTML tables
const SEVERITY_RANK = { critical: 4, high: 3, medium: 2, low: 1 };

function sortTable(table, columnIndex, direction, sortType) {
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));

    rows.sort((a, b) => {
        let aVal = a.cells[columnIndex].textContent.trim().toLowerCase();
        let bVal = b.cells[columnIndex].textContent.trim().toLowerCase();

        if (sortType === "severity") {
            aVal = SEVERITY_RANK[aVal] || 0;
            bVal = SEVERITY_RANK[bVal] || 0;
        } else if (sortType === "date") {
            aVal = new Date(aVal).getTime() || 0;
            bVal = new Date(bVal).getTime() || 0;
        }

        if (aVal < bVal) return direction === "asc" ? -1 : 1;
        if (aVal > bVal) return direction === "asc" ? 1 : -1;
        return 0;
    });

    rows.forEach(row => tbody.appendChild(row));
}
```

### SandCastle Job Manifest

```python
# Source: ProjectCrystalBall/src/api/v2/routers/jobs.py JOB_REGISTRY pattern
JOB_REGISTRY = [
    {
        "name": "compliance_check",
        "display_name": "Compliance Check",
        "description": "Run bulk job role compliance check across all employees",
        "endpoint": "/api/admin/jobs/compliance_check",
        "default_cron": "0 6 * * 1",  # Weekly Monday 6am
        "timeout_seconds": 600,
        "method": "POST",
        "dependencies": ["warehouse_sync"],
    },
    {
        "name": "warehouse_sync",
        "display_name": "Warehouse Sync",
        "description": "Sync job codes, roles, and assignments from data warehouse",
        "endpoint": "/api/admin/jobs/warehouse_sync",
        "default_cron": "0 5 * * *",  # Daily 5am
        "timeout_seconds": 300,
        "method": "POST",
        "dependencies": [],
    },
]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Synchronous compliance check in request thread | Background ThreadPoolExecutor with progress callback | This phase | Unblocks UI, enables progress tracking |
| Raw pyodbc exception bubbling to UI | Categorized error mapping | This phase | Users see actionable messages |
| No warehouse sync visibility | sync_metadata table + status card | This phase | Admins know data freshness |
| Server-side pagination only for violations | Client-side sort + server pagination | This phase | Faster sort without round-trip |

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (installed Phase 2) |
| Config file | `pytest.ini` or `pyproject.toml` |
| Quick run command | `pytest tests/ -x -q --timeout=30` |
| Full suite command | `pytest tests/ -v --cov=app` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMP-01 | Job manager starts compliance check, updates progress, returns status | unit | `pytest tests/test_job_manager.py -x` | Wave 0 |
| COMP-02 | Violations sort correctly by severity rank | unit (JS) | Manual browser test (client-side JS) | manual-only |
| COMP-03 | CSV export contains metadata headers + correct columns | unit | `pytest tests/test_compliance_export.py -x` | Wave 0 |
| COMP-04 | Warehouse sync errors categorized correctly | unit | `pytest tests/test_warehouse_errors.py -x` | Wave 0 |
| COMP-05 | Sync metadata updates on success/failure | unit | `pytest tests/test_sync_metadata.py -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q --timeout=30`
- **Per wave merge:** `pytest tests/ -v --cov=app`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_job_manager.py` -- covers COMP-01 (job lifecycle, mutex, progress updates)
- [ ] `tests/test_compliance_export.py` -- covers COMP-03 (CSV format, metadata, columns)
- [ ] `tests/test_warehouse_errors.py` -- covers COMP-04 (pyodbc error categorization)
- [ ] `tests/test_sync_metadata.py` -- covers COMP-05 (sync timestamp tracking)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | Keycloak OIDC session + M2M portal token (existing authlib) |
| V3 Session Management | no | No session changes this phase |
| V4 Access Control | yes | `@require_role("admin")` on all new endpoints + portal bypass |
| V5 Input Validation | yes | run_id path param validated as existing DB record; no user-supplied SQL |
| V6 Cryptography | no | No new crypto operations |

### Known Threat Patterns for Flask + HTMX + Background Jobs

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Unauthorized job triggering | Elevation of Privilege | `@require_role("admin")` + portal M2M token check |
| IDOR on run_id (view other org data) | Information Disclosure | Single-tenant app; run_id is UUID (unguessable) |
| CSV injection via employee names | Tampering | Prefix cells starting with `=`, `+`, `-`, `@` with apostrophe |
| HTMX response injection | Spoofing | Server-rendered HTML only; no user content in progress partial |
| Job manager denial of service | Denial of Service | Mutex + 409 Conflict; max one concurrent job per type |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HTMX 1.9.10 supports `hx-trigger="every 2s"` with conditional stop via outerHTML swap | Architecture Patterns | Polling would not stop; would need JS fallback |
| A2 | pyodbc error codes `08001`, `28000`, `HYT00` cover the common Azure SQL failure modes | Common Pitfalls | Some errors would show generic message; add codes as discovered |
| A3 | Single gunicorn worker sufficient for job state consistency (per WD-CONT-02 context) | Architecture | Multi-worker would need Redis for lock coordination |

## Open Questions

1. **Portal M2M token validation path**
   - What we know: Queue-Tip uses `PyJWKClient` to fetch JWKS from Keycloak and validates RS256 tokens. WhoDis already has authlib OIDC for user sessions.
   - What's unclear: Does `authlib` provide a utility for validating raw bearer tokens (not session-based), or should we use `PyJWT` directly for portal tokens?
   - Recommendation: Use `PyJWT` + `PyJWKClient` directly for M2M tokens (matches Queue-Tip pattern); keep authlib for user OIDC sessions. Both are already available.

2. **Alembic migration for new columns/tables**
   - What we know: Alembic is set up (`alembic.ini` exists). Need `checked_count` on `compliance_check_runs`, new `sync_metadata` table, new `job_runs` table.
   - What's unclear: Whether to use a single migration or multiple.
   - Recommendation: Single migration file for all schema changes in this phase (they're logically coupled).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PostgreSQL | All job state, sync metadata | Assumed available (project requirement) | 12+ | -- |
| pyodbc + ODBC Driver 18 | Warehouse sync | Assumed available (existing feature) | 5.3.0 | -- |
| Keycloak | Portal M2M auth | Required for portal integration | -- | Admin UI works without portal |

**Missing dependencies with no fallback:** None (all existing)
**Missing dependencies with fallback:** None

## Sources

### Primary (HIGH confidence)
- ProjectCrystalBall `src/api/v2/job_manager.py` -- Thread-pool executor pattern, mutex, progress_callback, state persistence
- ProjectCrystalBall `src/api/v2/routers/jobs.py` -- JobManifestEntry schema, JOB_REGISTRY, trigger/status endpoints
- Queue-Tip `src/auth/keycloak_deps.py` -- Portal M2M token validation pattern (azp=sandcastle-scheduler)
- WhoDis `app/services/compliance_checking_service.py` -- Existing batch-of-50 loop, ComplianceCheckRun lifecycle
- WhoDis `app/models/job_role_compliance.py` -- ComplianceCheckRun model schema
- WhoDis `app/auth/oidc.py` -- Existing Keycloak OIDC setup with authlib

### Secondary (MEDIUM confidence)
- HTMX 1.9.10 polling pattern (`hx-trigger="every Ns"`) -- well-documented, used elsewhere in project
- Python stdlib `csv` module -- standard approach for CSV generation

### Tertiary (LOW confidence)
- pyodbc SQLSTATE error codes for Azure SQL -- A2 assumption above

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all existing dependencies, no new packages
- Architecture: HIGH - direct adaptation of proven CrystalBall pattern with reference code available
- Pitfalls: HIGH - based on direct analysis of existing code + known Flask threading issues

**Research date:** 2026-05-16
**Valid until:** 2026-06-16 (stable domain, no fast-moving dependencies)
