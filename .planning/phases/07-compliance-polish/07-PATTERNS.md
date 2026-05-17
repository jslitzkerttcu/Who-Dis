# Phase 7: Compliance Polish - Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 11 (new/modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/blueprints/admin/jobs.py` | controller | request-response | `ProjectCrystalBall/src/api/v2/routers/jobs.py` | exact |
| `app/services/job_manager_service.py` | service | event-driven | `ProjectCrystalBall/src/api/v2/job_manager.py` | exact |
| `app/models/sync_metadata.py` | model | CRUD | `app/models/job_role_compliance.py` (ComplianceCheckRun) | role-match |
| `app/services/compliance_checking_service.py` | service | batch | (self - existing file) | exact |
| `app/services/job_role_warehouse_service.py` | service | batch | (self - existing file) | exact |
| `app/models/job_role_compliance.py` | model | CRUD | (self - add `checked_count` column) | exact |
| `app/blueprints/admin/job_role_compliance.py` | controller | request-response | (self - add CSV export route) | exact |
| `app/templates/admin/partials/_compliance_progress.html` | component | request-response | `app/templates/admin/partials/_compliance_overview.html` | role-match |
| `app/templates/admin/partials/_warehouse_sync_status.html` | component | request-response | `app/templates/admin/partials/_compliance_overview.html` | role-match |
| `app/templates/admin/partials/_compliance_violations_table.html` | component | request-response | (self - add sort headers + CSV button) | exact |
| `app/static/js/compliance-sort.js` | utility | transform | `app/static/js/blocked-numbers.js` | partial |
| `alembic/versions/002_compliance_polish.py` | migration | CRUD | `alembic/versions/001_baseline_from_live_schema.py` | exact |

## Pattern Assignments

### `app/blueprints/admin/jobs.py` (controller, request-response)

**Analog:** `ProjectCrystalBall/src/api/v2/routers/jobs.py` (adapted from FastAPI to Flask)

**Imports pattern** (from WhoDis `app/blueprints/admin/job_role_compliance.py` lines 1-24):
```python
import logging
from flask import request, jsonify, g, Blueprint

from app.middleware.auth import require_role
from app.database import db

logger = logging.getLogger(__name__)
```

**Job manifest pattern** (from CrystalBall `routers/jobs.py` lines 98-177):
```python
_ENDPOINT_PREFIX = "/api/admin/jobs"

JOB_REGISTRY = [
    {
        "name": "compliance_check",
        "display_name": "Compliance Check",
        "description": "Run bulk job role compliance check across all employees",
        "endpoint": f"{_ENDPOINT_PREFIX}/compliance_check",
        "default_cron": "0 6 * * 1",
        "timeout_seconds": 600,
        "method": "POST",
        "dependencies": ["warehouse_sync"],
    },
    {
        "name": "warehouse_sync",
        "display_name": "Warehouse Sync",
        "description": "Sync job codes, roles, and assignments from data warehouse",
        "endpoint": f"{_ENDPOINT_PREFIX}/warehouse_sync",
        "default_cron": "0 5 * * *",
        "timeout_seconds": 300,
        "method": "POST",
        "dependencies": [],
    },
]
```

**Trigger endpoint pattern** (from CrystalBall `routers/jobs.py` lines 364-385, adapted to Flask):
```python
@require_role("admin")
def trigger_job(name):
    """POST /api/admin/jobs/{name} - Trigger a background job."""
    if name not in _JOBS_BY_NAME:
        return jsonify({"error": f"Job '{name}' not found"}), 404

    job_manager = current_app.container.get("job_manager")
    try:
        run_id = job_manager.start_job(name, _JOB_RUNNERS[name])
        return jsonify({"status": "started", "run_id": run_id}), 202
    except ConflictError as e:
        return jsonify({"error": str(e), "run_id": e.run_id}), 409
```

**Status polling endpoint pattern** (from CrystalBall `routers/jobs.py` lines 388-417, adapted to Flask + HTMX):
```python
@require_role("admin")
def job_status(name, run_id):
    """GET /api/admin/jobs/{name}/status/{run_id} - Poll progress."""
    job_manager = current_app.container.get("job_manager")
    state = job_manager.get_status(run_id)
    if state is None:
        return jsonify({"error": "Run not found"}), 404

    # Return HTMX partial for browser, JSON for portal
    if request.headers.get("HX-Request"):
        if state["status"] == "completed":
            # Swap progress bar with results table
            return render_template("admin/partials/_compliance_violations_table.html", data=...)
        return render_template("admin/partials/_compliance_progress.html", **state)

    return jsonify(state)
```

**Portal M2M auth pattern** (from Queue-Tip `src/auth/keycloak_deps.py` lines 55-80, adapted to Flask decorator):
```python
import jwt as pyjwt
from jwt import PyJWKClient

PORTAL_SERVICE_ACCOUNT = "sandcastle-scheduler"

def admin_or_portal_required(f):
    """Allow either admin session OR portal M2M bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if g.get("user") and g.get("role") == "admin":
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Peek at azp before full verification
            unverified = pyjwt.decode(token, options={"verify_signature": False})
            if unverified.get("azp") != PORTAL_SERVICE_ACCOUNT:
                abort(403)
            # Full RS256 verification
            client = get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            claims = pyjwt.decode(token, signing_key.key, algorithms=["RS256"],
                                  issuer=KEYCLOAK_ISSUER, options={"verify_aud": False})
            g.user = "sandcastle-scheduler"
            return f(*args, **kwargs)

        abort(403)
    return decorated
```

---

### `app/services/job_manager_service.py` (service, event-driven)

**Analog:** `ProjectCrystalBall/src/api/v2/job_manager.py`

**Imports pattern** (from CrystalBall `job_manager.py` lines 19-28 + WhoDis service pattern):
```python
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Dict, Optional, Any

from flask import current_app
from app.database import db

logger = logging.getLogger(__name__)
```

**Core service class pattern** (adapted from CrystalBall `job_manager.py` lines 36-39, using WhoDis DI):
```python
class JobManagerService:
    """Flask-native job manager with PostgreSQL state.

    Adapted from CrystalBall's job_manager.py (SQLite) for WhoDis (PostgreSQL).
    Single worker thread pool; mutex prevents concurrent runs of same job type.
    """

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._lock = threading.Lock()
```

**ConflictError pattern** (from CrystalBall `job_manager.py` lines 109-115):
```python
class ConflictError(Exception):
    """Raised when a job of the same type is already running."""
    def __init__(self, message: str, run_id: str):
        super().__init__(message)
        self.run_id = run_id
```

**Start job with mutex pattern** (from CrystalBall `job_manager.py` lines 150-159 adapted):
```python
def start_job(self, job_name: str, runner_fn: Callable, app=None) -> str:
    """Start a background job. Returns run_id. Raises ConflictError if already running."""
    with self._lock:
        # Check for active run in PostgreSQL
        from app.models.job_run import JobRun
        active = JobRun.query.filter_by(job_name=job_name, status="running").first()
        if active:
            raise ConflictError(f"{job_name} already running", active.run_id)

        run_id = str(uuid.uuid4())
        job_run = JobRun(run_id=run_id, job_name=job_name, status="running",
                         started_at=datetime.now(timezone.utc))
        db.session.add(job_run)
        db.session.commit()

    # Submit to thread pool with Flask app context
    app = app or current_app._get_current_object()
    self._executor.submit(self._run_with_context, app, run_id, runner_fn)
    return run_id
```

**Flask app context in worker thread** (from WhoDis `app/container.py` background thread pattern):
```python
def _run_with_context(self, app, run_id: str, fn: Callable):
    """Execute job within Flask app context."""
    with app.app_context():
        try:
            fn(run_id=run_id)
            job_run = JobRun.query.filter_by(run_id=run_id).first()
            job_run.status = "completed"
            job_run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
        except Exception as e:
            logger.error(f"Job {run_id} failed: {e}", exc_info=True)
            job_run = JobRun.query.filter_by(run_id=run_id).first()
            job_run.status = "failed"
            job_run.error = str(e)[:500]
            job_run.completed_at = datetime.now(timezone.utc)
            db.session.commit()
```

---

### `app/models/sync_metadata.py` (model, CRUD)

**Analog:** `app/models/job_role_compliance.py` (`ComplianceCheckRun` at lines 304-362)

**Model pattern** (from `job_role_compliance.py` lines 304-310 + base model conventions):
```python
from datetime import datetime, timezone
from app.database import db
from app.models.base import BaseModel, TimestampMixin

class SyncMetadata(BaseModel, TimestampMixin):
    """Tracks warehouse sync status for admin visibility."""

    __tablename__ = "sync_metadata"

    sync_type = db.Column(db.String(50), unique=True, nullable=False, index=True)
    last_success_at = db.Column(db.DateTime(timezone=True))
    last_error_at = db.Column(db.DateTime(timezone=True))
    last_error_message = db.Column(db.Text)
    last_error_category = db.Column(db.String(100))
    total_records_synced = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer)
```

---

### `app/services/compliance_checking_service.py` MODIFICATION (service, batch)

**Existing file -- add progress_callback to batch loop**

**Current batch pattern** (lines 265-292):
```python
for i in range(0, len(employees_to_check), batch_size):
    batch = employees_to_check[i : i + batch_size]
    try:
        for employee_data in batch:
            # ... check logic ...
            total_checks += len(checks)
        db.session.commit()
        logger.debug(f"Processed batch {i // batch_size + 1}, total checks: {total_checks}")
    except Exception as e:
        # ...
```

**Pattern to add** (progress_callback per batch, modeled after CrystalBall `_run_data_refresh` lines 256-267):
```python
def run_compliance_check(self, ..., progress_callback=None) -> ComplianceCheckRun:
    # ... existing setup ...
    for i in range(0, len(employees_to_check), batch_size):
        batch = employees_to_check[i : i + batch_size]
        # ... process batch ...
        db.session.commit()
        # NEW: update checked_count and invoke progress callback
        checked_so_far = min(i + batch_size, len(employees_to_check))
        check_run.checked_count = checked_so_far
        check_run.save()
        if progress_callback:
            progress_callback(checked_so_far, len(employees_to_check))
```

---

### `app/services/job_role_warehouse_service.py` MODIFICATION (service, batch)

**Existing file -- add categorized error handling**

**Error categorization pattern** (from RESEARCH.md):
```python
WAREHOUSE_ERROR_CATEGORIES = {
    "08001": ("connection_timeout", "Connection timeout - warehouse unreachable"),
    "08S01": ("connection_timeout", "Connection timeout - warehouse unreachable"),
    "28000": ("auth_failed", "Authentication failed - check service principal credentials"),
    "HYT00": ("query_timeout", "Query timeout - warehouse may be under load"),
    "HYT01": ("query_timeout", "Query timeout - warehouse may be under load"),
}

def _categorize_pyodbc_error(self, error: Exception) -> tuple:
    """Return (category, message) for a pyodbc error."""
    error_str = str(error.args[0]) if error.args else ""
    for code, (category, message) in WAREHOUSE_ERROR_CATEGORIES.items():
        if code in error_str:
            return category, message
    return "unknown", "Sync failed - an unexpected error occurred"
```

**Sync metadata update pattern** (follows existing `mark_completed`/`mark_failed` from ComplianceCheckRun lines 343-362):
```python
def _update_sync_metadata(self, sync_type: str, success: bool, error: Exception = None):
    from app.models.sync_metadata import SyncMetadata
    meta = SyncMetadata.query.filter_by(sync_type=sync_type).first()
    if not meta:
        meta = SyncMetadata(sync_type=sync_type)
    if success:
        meta.last_success_at = datetime.now(timezone.utc)
    else:
        meta.last_error_at = datetime.now(timezone.utc)
        category, message = self._categorize_pyodbc_error(error)
        meta.last_error_category = category
        meta.last_error_message = message
    meta.save()
```

---

### `app/blueprints/admin/job_role_compliance.py` MODIFICATION - CSV Export Route

**Analog:** Existing HTMX response pattern from same file (lines 104-108)

**CSV export pattern** (uses Flask Response + csv stdlib):
```python
import csv
import io
from flask import Response

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
    writer.writerow([])

    # Column headers (D-14)
    writer.writerow(["Employee (UPN)", "Job Code", "System", "Expected Role",
                     "Actual Assignment", "Violation Type", "Severity", "Remediation Action"])

    # Data rows with yield_per for memory efficiency
    checks = ComplianceCheck.query.filter_by(check_run_id=run_id).yield_per(100)
    for check in checks:
        writer.writerow([...])

    response = Response(output.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=compliance_run_{run_id}.csv"})
    return response
```

---

### `app/templates/admin/partials/_compliance_progress.html` (component, request-response)

**Analog:** `app/templates/admin/partials/_compliance_overview.html` + HTMX polling pattern

**HTMX polling partial pattern** (adapted from existing dashboard HTMX style):
```html
<!-- Returns different content based on job state; hx-trigger stops via outerHTML swap -->
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

---

### `app/static/js/compliance-sort.js` (utility, transform)

**Analog:** `app/static/js/blocked-numbers.js` (class-based JS pattern)

**JS class pattern** (from `blocked-numbers.js` lines 1-15):
```javascript
/**
 * Compliance Violations Table Sorting
 * Client-side sort with severity rank map (D-05, D-06)
 */

class ComplianceSortManager {
    constructor() {
        this.currentSort = { column: null, direction: "asc" };
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        document.querySelectorAll("[data-sort-column]").forEach(header => {
            header.addEventListener("click", (e) => this.handleSort(e));
        });
    }
}
```

---

### `alembic/versions/002_compliance_polish.py` (migration, CRUD)

**Analog:** `alembic/versions/001_baseline_from_live_schema.py`

**Migration structure pattern** (from `001_baseline_from_live_schema.py` lines 1-40):
```python
"""compliance_polish_schema_additions

Revision ID: 002_compliance_polish
Revises: 001_baseline_from_live_schema
Create Date: 2026-05-16

Adds:
- checked_count column to compliance_check_runs (COMP-01 progress tracking)
- sync_metadata table (COMP-04, COMP-05 warehouse sync visibility)
- job_runs table (job manager state persistence)
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_compliance_polish"
down_revision: Union[str, None] = "001_baseline_from_live_schema"

def upgrade() -> None:
    # Add checked_count to compliance_check_runs
    op.add_column("compliance_check_runs",
                  sa.Column("checked_count", sa.Integer(), default=0))

    # Create sync_metadata table
    op.create_table("sync_metadata", ...)

    # Create job_runs table
    op.create_table("job_runs", ...)

def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("sync_metadata")
    op.drop_column("compliance_check_runs", "checked_count")
```

---

## Shared Patterns

### Authentication (Admin + Portal Dual-Auth)
**Source:** `app/middleware/auth.py` (`@require_role`) + `Queue-Tip/src/auth/keycloak_deps.py` (M2M validation)
**Apply to:** All routes in `app/blueprints/admin/jobs.py`

The jobs blueprint needs a new decorator `@admin_or_portal_required` that accepts either:
1. Standard admin session (existing `@require_role("admin")` path)
2. Portal M2M bearer token with `azp=sandcastle-scheduler` (RS256 via PyJWKClient)

### Error Handling
**Source:** `app/utils/error_handler.py` (`@handle_service_errors`)
**Apply to:** `job_manager_service.py`, warehouse service modifications

```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=True)
def start_job(self, job_name: str, runner_fn: Callable, app=None) -> str:
    ...
```

### HTMX Fragment Response
**Source:** `app/blueprints/admin/job_role_compliance.py` lines 104-108
**Apply to:** All new endpoints that serve browser requests

```python
# Return HTML for HTMX requests, JSON for API/portal
if request.headers.get("HX-Request"):
    return render_template("admin/partials/_partial.html", data=result)
return jsonify(result)
```

### DI Container Registration
**Source:** `app/container.py` `register_services()` function (lines 115-140)
**Apply to:** `job_manager_service.py`

```python
# In register_services():
from app.services.job_manager_service import JobManagerService
container.register("job_manager", lambda c: JobManagerService())
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have strong analogs either in WhoDis codebase or CrystalBall/Queue-Tip references |

## Metadata

**Analog search scope:** `app/`, `ProjectCrystalBall/src/api/v2/`, `Queue-Tip/src/auth/`
**Files scanned:** ~25
**Pattern extraction date:** 2026-05-16
