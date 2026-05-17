# Phase 8: Reporting - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/blueprints/admin/reports.py` | controller | request-response | `app/blueprints/admin/job_role_compliance.py` | exact |
| `app/blueprints/admin/__init__.py` | route-config | request-response | `app/blueprints/admin/__init__.py` (self) | exact |
| `app/blueprints/admin/jobs.py` | controller | request-response | `app/blueprints/admin/jobs.py` (self) | exact |
| `app/models/report_cache.py` | model | CRUD | `app/models/sync_metadata.py` + `app/models/external_service.py` | role-match |
| `app/services/report_sync_service.py` | service | batch | `app/services/compliance_checking_service.py` | exact |
| `app/services/graph_service.py` | service | request-response | `app/services/graph_service.py` (self) | exact |
| `app/services/genesys_service.py` | service | request-response | `app/services/genesys_service.py` (self) | exact |
| `app/container.py` | config | CRUD | `app/container.py` (self) | exact |
| `app/templates/admin/reports.html` | template | request-response | `app/templates/admin/compliance_dashboard.html` | exact |
| `app/templates/admin/partials/_report_licenses.html` | template | request-response | `app/templates/admin/partials/_compliance_overview.html` | exact |
| `app/templates/admin/partials/_report_security.html` | template | request-response | `app/templates/admin/partials/_compliance_overview.html` | role-match |
| `app/templates/admin/partials/_report_genesys.html` | template | request-response | `app/templates/admin/partials/_compliance_overview.html` | role-match |
| `app/templates/admin/partials/_report_history.html` | template | request-response | `app/templates/admin/partials/_compliance_violations_table.html` | role-match |

## Pattern Assignments

### `app/blueprints/admin/reports.py` (controller, request-response)

**Analog:** `app/blueprints/admin/job_role_compliance.py`

**Imports pattern** (lines 1-27):
```python
"""
Report Dashboard Admin Module

This module provides admin interface for viewing license utilization,
security posture, contact center status, and run history reports.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from flask import request, jsonify, render_template, g, Response, abort

from app.middleware.auth import require_role
from app.database import db

logger = logging.getLogger(__name__)
```

**Auth pattern** (line 30-31 from analog):
```python
@require_role("admin")
def reports():
    """Main reports page with tab navigation."""
```

**Core tab-routing pattern** (derived from analog HTMX detection at `__init__.py` line 205):
```python
@require_role("admin")
def reports():
    """Main reports page with tab navigation."""
    tab = request.args.get("tab", "licenses")
    if request.headers.get("HX-Request"):
        # HTMX partial request -- return tab content only
        return _render_tab(tab)
    # Full page request
    return render_template("admin/reports.html", active_tab=tab)
```

**CSV export pattern** (lines 639-710 from `job_role_compliance.py`):
```python
def _csv_safe(value: str) -> str:
    """Prevent CSV injection by prefixing dangerous characters with apostrophe."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


@require_role("admin")
def export_license_csv():
    """Export license utilization as CSV."""
    # ... query ReportCache ...
    output = io.StringIO()
    writer = csv.writer(output)

    # Metadata rows (Phase 7 pattern)
    writer.writerow([f"Report: License Utilization"])
    writer.writerow([f"Generated: {cache.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')}"])
    writer.writerow([])

    # Header row
    writer.writerow(["SKU Name", "Assigned", "Available", "Consumed", "Utilization %", "Unused (30d)"])

    # Data rows
    for sku in cache.data:
        writer.writerow([
            _csv_safe(sku["name"]),
            sku["assigned"],
            # ...
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=license_utilization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        },
    )
```

---

### `app/blueprints/admin/__init__.py` (route-config, MODIFY)

**Analog:** Self -- follow existing route registration pattern.

**Import pattern** (lines 10-17):
```python
from . import (
    users,
    database,
    cache,
    audit,
    admin_employee_profiles,
    job_role_compliance,
    reports,  # NEW
)
```

**Route registration pattern** (lines 393-420 for compliance -- copy structure):
```python
# Report routes
admin_bp.route("/reports")(reports.reports)
admin_bp.route("/api/reports/licenses")(reports.api_licenses_tab)
admin_bp.route("/api/reports/security")(reports.api_security_tab)
admin_bp.route("/api/reports/genesys")(reports.api_genesys_tab)
admin_bp.route("/api/reports/history")(reports.api_history_tab)
admin_bp.route("/api/reports/export/licenses")(reports.export_license_csv)
admin_bp.route("/api/reports/export/security")(reports.export_security_csv)
admin_bp.route("/api/reports/export/genesys")(reports.export_genesys_csv)
```

---

### `app/blueprints/admin/jobs.py` (controller, MODIFY)

**Analog:** Self -- extend JOB_REGISTRY and _JOB_RUNNERS.

**Job registry pattern** (lines 22-43):
```python
JOB_REGISTRY = [
    # ... existing jobs ...
    {
        "name": "report_license_sync",
        "display_name": "License Report Sync",
        "description": "Sync license utilization data from Graph API",
        "endpoint": "/api/v2/admin/jobs/report_license_sync",
        "default_cron": "0 4 * * *",
        "timeout_seconds": 600,
        "method": "POST",
        "dependencies": [],
    },
    {
        "name": "report_security_sync",
        "display_name": "Security Report Sync",
        "description": "Sync MFA and sign-in failure data from Graph API",
        "endpoint": "/api/v2/admin/jobs/report_security_sync",
        "default_cron": "0 * * * *",
        "timeout_seconds": 300,
        "method": "POST",
        "dependencies": [],
    },
]
```

**Runner function pattern** (lines 50-69):
```python
def _run_report_license_sync(run_id: str) -> None:
    """Runner function for license report sync job."""
    service = current_app.container.get("report_sync_service")
    service.sync_license_data()


def _run_report_security_sync(run_id: str) -> None:
    """Runner function for security report sync job."""
    service = current_app.container.get("report_sync_service")
    service.sync_security_data()
```

---

### `app/models/report_cache.py` (model, CRUD)

**Analog:** `app/models/sync_metadata.py` (lines 1-25) for structure + `app/models/external_service.py` for domain methods.

**Model structure pattern** (from `sync_metadata.py`):
```python
"""
Report Cache Model

Stores pre-aggregated report data with tiered TTL support.
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

from app.database import db
from app.models.base import BaseModel, TimestampMixin


class ReportCache(BaseModel, TimestampMixin):
    """Model for cached report data with tiered TTL."""

    __tablename__ = "report_cache"

    report_type = db.Column(db.String(50), nullable=False, index=True)
    cache_key = db.Column(db.String(100), nullable=False, index=True)
    data = db.Column(db.JSON, nullable=False)
    generated_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ttl_hours = db.Column(db.Integer, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("report_type", "cache_key", name="uq_report_cache"),
    )

    @property
    def is_stale(self) -> bool:
        if not self.generated_at:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.ttl_hours)
        return self.generated_at < cutoff

    def __repr__(self):
        return f"<ReportCache {self.report_type}/{self.cache_key}>"
```

**UniqueConstraint pattern** (from `external_service.py` lines 28-33):
```python
__table_args__ = (
    db.UniqueConstraint(
        "service_name", "data_type", "service_id", name="uq_service_type_id"
    ),
)
```

---

### `app/services/report_sync_service.py` (service, batch)

**Analog:** `app/services/compliance_checking_service.py` (lines 1-33 for structure) + `app/services/sku_catalog_cache.py` (lines 1-30 for base class pattern).

**Service class pattern** (from `compliance_checking_service.py`):
```python
"""
Report Sync Service

Aggregates license, MFA, and sign-in data from Graph API into
the report_cache table for dashboard display.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from app.database import db
from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors

logger = logging.getLogger(__name__)


class ReportSyncService(BaseConfigurableService):
    """Service for syncing report data from Graph API into report cache."""

    def __init__(self):
        super().__init__(config_prefix="reports")
```

**Container-based service access pattern** (from `compliance_checking_service.py` line 52):
```python
service = current_app.container.get("compliance_checking_service")
```

**Error handling decorator** (from `app/services/base.py`):
```python
@handle_service_errors(raise_errors=False)
def sync_license_data(self):
    """Sync license utilization from Graph API."""
    # ...
```

---

### `app/services/graph_service.py` (service, MODIFY)

**Analog:** Self -- add new bulk methods following existing method pattern.

**Existing per-user method pattern** (lines 489-521 for `get_subscribed_skus()`):
```python
def get_subscribed_skus(self) -> Optional[Any]:
    """Get the tenant SKU catalog from Graph."""
    token = self.get_access_token()
    if not token:
        logger.error("Failed to get Graph API access token for subscribed SKUs")
        return None

    try:
        url = f"{self.graph_base_url}/subscribedSkus"
        response = self._make_request("GET", url, token)
        data = self._handle_response(response)
        if not data or "value" not in data:
            return []
        return data["value"]
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            return self._permission_missing("Organization.Read.All")
        logger.error(f"HTTP error fetching subscribed SKUs: {str(e)}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Error fetching subscribed SKUs: {str(e)}", exc_info=True)
        return None
```

**New paginated method pattern** (extend with `@odata.nextLink` loop):
```python
def get_all_users_with_licenses(self) -> List[Dict[str, Any]]:
    """Paginate through all users with license+signIn data."""
    token = self.get_access_token()
    if not token:
        return []

    all_users = []
    url = (
        f"{self.graph_base_url}/users"
        "?$select=displayName,userPrincipalName,assignedLicenses,signInActivity"
        "&$top=500"
    )
    headers = self._get_headers(token)
    headers["ConsistencyLevel"] = "eventual"

    while url:
        response = self._make_request("GET", url, token, headers=headers)
        data = self._handle_response(response)
        if not data:
            break
        all_users.extend(data.get("value", []))
        url = data.get("@odata.nextLink")

    return all_users
```

**Permission-missing sentinel pattern** (lines 440-441):
```python
if e.response is not None and e.response.status_code == 403:
    return self._permission_missing("UserAuthenticationMethod.Read.All")
```

---

### `app/container.py` (config, MODIFY)

**Analog:** Self -- follow existing service registration pattern.

**Registration pattern** (lines 170-180):
```python
# Report sync service (Phase 8: license + security data aggregation)
from app.services.report_sync_service import ReportSyncService

container.register(
    "report_sync_service", lambda c: ReportSyncService()
)
```

---

### `app/templates/admin/reports.html` (template, shell page)

**Analog:** `app/templates/admin/compliance_dashboard.html` (lines 1-55)

**Page shell pattern**:
```html
{% extends "base.html" %}

{% block title %}Reports - Admin{% endblock %}

{% block content %}
<div class="container mx-auto px-4 py-6 max-w-7xl">
    <div class="mb-6">
        <h1 class="text-2xl font-bold text-gray-900 mb-2">Reports</h1>
        <p class="text-gray-600">License utilization, security posture, and contact center status.</p>
    </div>

    <!-- Tab navigation -->
    <!-- Tab content area with HTMX loading -->
</div>
{% endblock %}
```

---

### `app/templates/admin/partials/_report_licenses.html` (template, KPI + table)

**Analog:** `app/templates/admin/partials/_compliance_overview.html` (lines 1-63)

**KPI card pattern** (lines 1-38):
```html
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
    <div class="flex items-center">
        <div class="flex-shrink-0">
            <div class="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
                <i class="fas fa-shield-alt text-green-600"></i>
            </div>
        </div>
        <div class="ml-5 w-0 flex-1">
            <dl>
                <dt class="text-sm font-medium text-gray-500 truncate">
                    Overall Compliance
                </dt>
                <dd class="flex items-baseline">
                    <div class="text-2xl font-semibold text-gray-900">
                        {{ "%.1f"|format(data.compliance_percentage) }}%
                    </div>
                </dd>
            </dl>
        </div>
    </div>
</div>
```

**Grid layout for KPI cards** (line 48 from `compliance_dashboard.html`):
```html
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
    <!-- KPI card 1: Total SKUs -->
    <!-- KPI card 2: Total Assigned -->
    <!-- KPI card 3: Unused (30d) -->
    <!-- KPI card 4: Utilization % -->
</div>
```

---

### `app/templates/admin/partials/_report_history.html` (template, table)

**Analog:** `app/templates/admin/partials/_compliance_violations_table.html`

**Table pattern**: Standard Tailwind table with `<thead>` / `<tbody>`, reading from `job_runs` query data. Follow the compliance violations table structure.

---

## Shared Patterns

### Authentication & Authorization
**Source:** `app/middleware/auth.py`
**Apply to:** All report routes (reports.py)
```python
@require_role("admin")
def my_report_route():
    # ...
```

### SandCastle Portal Auth
**Source:** `app/auth/portal_auth.py`
**Apply to:** Job trigger and status endpoints (jobs.py)
```python
@admin_or_portal_required
def trigger_job(name: str):
    # ...
```

### Error Handling (Services)
**Source:** `app/utils/error_handler.py`
**Apply to:** `report_sync_service.py` methods
```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=False)
def sync_license_data(self):
    # ...
```

### CSV Injection Prevention
**Source:** `app/blueprints/admin/job_role_compliance.py` lines 639-643
**Apply to:** All CSV export routes in `reports.py`
```python
def _csv_safe(value: str) -> str:
    """Prevent CSV injection by prefixing dangerous characters with apostrophe."""
    if value and value[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value
```

### HTMX Partial Detection
**Source:** `app/blueprints/admin/__init__.py` line 205
**Apply to:** All tab-content routes in `reports.py`
```python
if request.headers.get("HX-Request"):
    # Return partial HTML fragment
    return render_template("admin/partials/_report_licenses.html", data=data)
# Full page request
return render_template("admin/reports.html", active_tab="licenses")
```

### DI Container Access
**Source:** `app/blueprints/admin/jobs.py` line 52
**Apply to:** `reports.py` (accessing report_sync_service), `jobs.py` runners
```python
service = current_app.container.get("report_sync_service")
```

### Base Configurable Service
**Source:** `app/services/base.py` lines 22-60
**Apply to:** `report_sync_service.py`
```python
class ReportSyncService(BaseConfigurableService):
    def __init__(self):
        super().__init__(config_prefix="reports")
```

### Model Base Pattern
**Source:** `app/models/base.py` lines 169-174 + `app/models/sync_metadata.py` lines 11-25
**Apply to:** `report_cache.py`
```python
class ReportCache(BaseModel, TimestampMixin):
    __tablename__ = "report_cache"
    # ...
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have analogs in the existing codebase |

Every new file maps to an existing pattern. This phase is primarily data aggregation + display on top of proven infrastructure (jobs, caching, HTMX tabs, CSV export).

## Metadata

**Analog search scope:** `app/blueprints/admin/`, `app/models/`, `app/services/`, `app/templates/admin/`
**Files scanned:** 42
**Pattern extraction date:** 2026-05-17
