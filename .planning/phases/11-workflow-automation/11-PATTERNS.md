# Phase 11: Workflow Automation - Pattern Map

**Mapped:** 2026-05-17
**Files analyzed:** 12 new/modified files
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/models/workflow.py` | model | CRUD | `app/models/job_role_compliance.py` | exact |
| `app/services/workflow_service.py` | service | CRUD | `app/services/compliance_checking_service.py` | exact |
| `app/blueprints/admin/workflows.py` | controller | request-response | `app/blueprints/admin/reports.py` | exact |
| `app/blueprints/admin/__init__.py` | route-config | request-response | `app/blueprints/admin/__init__.py` (self) | exact |
| `app/container.py` | config | N/A | `app/container.py` (self) | exact |
| `alembic/versions/005_workflow_tables.py` | migration | batch | `alembic/versions/004_external_api_tokens.py` | exact |
| `app/templates/admin/workflows.html` | template | request-response | `app/templates/admin/reports.html` | exact |
| `app/templates/admin/workflow_create.html` | template | request-response | `app/templates/admin/_external_api_tokens.html` | role-match |
| `app/templates/admin/workflow_detail.html` | template | request-response | `app/templates/admin/compliance_violations.html` | role-match |
| `app/templates/admin/workflow_offboarding_items.html` | template | CRUD | `app/templates/admin/_external_api_tokens.html` | role-match |
| `app/templates/admin/partials/` (4 files) | template | request-response | `app/templates/admin/partials/_report_*.html` | exact |
| `tests/unit/services/test_workflow_service.py` | test | N/A | `tests/unit/services/test_compliance_checking_service.py` | exact |
| `tests/factories/workflow.py` | test-factory | N/A | `tests/factories/job_code.py` | exact |

## Pattern Assignments

### `app/models/workflow.py` (model, CRUD)

**Analog:** `app/models/job_role_compliance.py`

**Imports pattern** (lines 1-14):
```python
"""
Job Role Compliance Matrix Models

This module contains SQLAlchemy models for managing job role compliance
across multiple systems (Keystone, AD, Genesys, etc.).
"""

from datetime import datetime, timezone, date
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from app.database import db
from app.models.base import BaseModel, TimestampMixin, JSONDataMixin
```

**Model definition pattern** (lines 16-67 -- JobCode as structural template):
```python
class JobCode(BaseModel, TimestampMixin, JSONDataMixin):
    """Model for job codes from UKG/data warehouse."""

    __tablename__ = "job_codes"

    job_code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    job_title = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(255), index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)

    # Relationships
    role_mappings = db.relationship(
        "JobRoleMapping", back_populates="job_code", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<JobCode {self.job_code}: {self.job_title}>"

    @classmethod
    def get_active_job_codes(cls) -> List["JobCode"]:
        """Get all active job codes."""
        return cls.query.filter_by(is_active=True).order_by(cls.job_code).all()
```

**Relationship + back_populates pattern** (lines 149-174 -- JobRoleMapping):
```python
class JobRoleMapping(BaseModel, TimestampMixin, JSONDataMixin):
    __tablename__ = "job_role_mappings"

    job_code_id = db.Column(
        db.Integer, db.ForeignKey("job_codes.id"), nullable=False, index=True
    )
    # ...
    created_by = db.Column(db.String(255), nullable=False, index=True)

    # Relationships
    job_code = db.relationship("JobCode", back_populates="role_mappings")
    system_role = db.relationship("SystemRole", back_populates="role_mappings")
```

**Status tracking pattern** (lines 304-363 -- ComplianceCheckRun):
```python
class ComplianceCheckRun(BaseModel, TimestampMixin, JSONDataMixin):
    __tablename__ = "compliance_check_runs"

    status = db.Column(
        db.String(50), default="running", index=True
    )  # 'running', 'completed', 'failed', 'cancelled'
    started_by = db.Column(db.String(255), nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True))

    def mark_completed(self, commit=True):
        """Mark the run as completed."""
        self.status = "completed"
        self.completed_at = datetime.now(timezone.utc)
        return self.save(commit=commit)
```

---

### `app/services/workflow_service.py` (service, CRUD)

**Analog:** `app/services/compliance_checking_service.py`

**Imports pattern** (lines 1-25):
```python
"""
Compliance Checking Service

This service performs compliance checks by comparing expected role mappings
against actual role assignments across all systems.
"""

import logging
from typing import Callable, Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
import uuid

from app.database import db
from app.services.base import BaseConfigurableService
from app.utils.error_handler import handle_service_errors
from app.models.job_role_compliance import (
    JobCode,
    JobRoleMapping,
    ComplianceCheck,
    ComplianceCheckRun,
    EmployeeRoleAssignment,
)

logger = logging.getLogger(__name__)
```

**Service class declaration** (lines 28-31):
```python
class ComplianceCheckingService(BaseConfigurableService):
    """Service for performing job role compliance checks."""

    def __init__(self):
        super().__init__(config_prefix="job_role_compliance")
```

**Core business logic with `@handle_service_errors` and batch DB operations** (lines 96-213):
```python
@handle_service_errors(raise_errors=True)
def check_employee_compliance(
    self, employee_upn: str, job_code: str, run_id: str, commit: bool = True
) -> List[ComplianceCheck]:
    """..."""
    compliance_checks: List[ComplianceCheck] = []

    expected_mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
    if not expected_mappings:
        logger.debug(f"No role mappings found for job code {job_code}")
        return compliance_checks

    # ... process mappings ...
    for mapping in expected_mappings:
        check = ComplianceCheck(
            # ... fields ...
        )
        check.save(commit=False)
        compliance_checks.append(check)

    if commit:
        db.session.commit()

    return compliance_checks
```

**Aggregate query pattern for dashboard stats** (lines 363-458 -- get_compliance_summary):
```python
def get_compliance_summary(self, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Get compliance summary statistics."""
    # ... get the run ...
    checks = ComplianceCheck.query.filter_by(check_run_id=check_run.run_id).all()

    total_checks = len(checks)
    compliant_checks = sum(1 for c in checks if c.compliance_status == "compliant")

    # Group violations by type
    job_code_violations = (
        db.session.query(
            ComplianceCheck.job_code, db.func.count(ComplianceCheck.id)
        )
        .filter(...)
        .group_by(ComplianceCheck.job_code)
        .order_by(db.func.count(ComplianceCheck.id).desc())
        .limit(10)
        .all()
    )

    return {
        "summary": {
            "total_checks": total_checks,
            "compliant_checks": compliant_checks,
            # ...
        },
    }
```

---

### `app/blueprints/admin/workflows.py` (controller, request-response)

**Analog:** `app/blueprints/admin/reports.py` (primary) + `app/blueprints/admin/api_tokens.py` (for CRUD operations)

**Imports pattern** (reports.py lines 1-25):
```python
"""
Reports Admin Module

Provides admin interface for viewing organization-wide reports including
license utilization, security posture (MFA + failed sign-ins), with
tabbed navigation, KPI cards, data tables, and CSV export.
"""

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from flask import (
    abort,
    current_app,
    render_template,
    request,
    Response,
)

from app.middleware.auth import require_role
from app.models.report_cache import ReportCache

logger = logging.getLogger(__name__)
```

**Tabbed dashboard with HTMX fragment pattern** (reports.py lines 55-95):
```python
@require_role("admin")
def reports():
    """Main reports page with tabbed interface."""
    tab = request.args.get("tab", "licenses")
    if request.headers.get("HX-Request"):
        return _render_tab(tab)
    tab_content = _render_tab(tab)
    return render_template("admin/reports.html", active_tab=tab, tab_content=tab_content)


def _render_tab(tab: str) -> str:
    """Dispatch tab rendering to the appropriate handler."""
    tab_handlers = {
        "licenses": _render_licenses_tab,
        "security": _render_security_tab,
        "genesys": _render_genesys_tab,
        "history": _render_history_tab,
    }
    handler = tab_handlers.get(tab)
    if handler is None:
        abort(404)
    return handler()
```

**CRUD with CSRF, audit, and HTMX trigger pattern** (api_tokens.py lines 23-76):
```python
@require_role("admin")
@csrf_double_submit.protect
def create_api_token():
    """Create a new external API token."""
    token_service = current_app.container.get("external_api_token_service")
    name = request.form.get("name", "").strip()

    # Validate name
    if not name or len(name) < 2:
        return jsonify({
            "success": False,
            "error": "Token name must be at least 2 characters."
        }), 400

    try:
        model, raw_token = token_service.create_token(
            name=name, created_by=g.user
        )

        # Audit log
        admin_role = getattr(request, "user_role", None)
        user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

        current_app.container.get("audit_logger").log_admin_action(
            user_email=g.user,
            action="api_token_created",
            target=name,
            details={
                "token_id": model.id,
                "token_prefix": model.token_prefix,
            },
            user_role=admin_role,
            ip_address=user_ip,
            user_agent=request.headers.get("User-Agent"),
        )

        response = jsonify({"success": True, ...})
        response.headers["HX-Trigger"] = "tokenCreated"
        return response

    except Exception as e:
        logger.error(f"Token creation failed: {str(e)}", exc_info=True)
        return jsonify({
            "success": False,
            "error": "Token creation failed. Please try again."
        }), 500
```

---

### `app/blueprints/admin/__init__.py` (route wiring)

**Analog:** `app/blueprints/admin/__init__.py` (self -- lines 1-21 for imports, lines 32-67 for route wiring)

**Module import pattern** (lines 10-20):
```python
from . import (
    users,
    database,
    cache,
    audit,
    admin_employee_profiles,
    job_role_compliance,
    reports,
    api_tokens,
)
```

**Route wiring pattern** (lines 62-67 as example -- api_tokens):
```python
# External API token management routes
admin_bp.route("/api-tokens", endpoint="api_tokens")(api_tokens.manage_api_tokens)
admin_bp.route("/api-tokens/create", methods=["POST"])(api_tokens.create_api_token)
admin_bp.route("/api-tokens/<int:token_id>/revoke", methods=["POST"])(
    api_tokens.revoke_api_token
)
admin_bp.route("/api-tokens/list")(api_tokens.api_token_list)
```

---

### `app/container.py` (service registration)

**Analog:** `app/container.py` (self -- lines 175-196 for recent service registration)

**Service registration pattern** (lines 175-196):
```python
# Compliance checking service (bulk job-role compliance checks)
from app.services.compliance_checking_service import ComplianceCheckingService

container.register(
    "compliance_checking_service", lambda c: ComplianceCheckingService()
)

# External API token service (Phase 10: REST API bearer token management)
from app.services.external_api_token_service import ExternalApiTokenService

container.register(
    "external_api_token_service", lambda c: ExternalApiTokenService()
)
```

---

### `alembic/versions/005_workflow_tables.py` (migration, batch)

**Analog:** `alembic/versions/004_external_api_tokens.py`

**Full migration pattern** (lines 1-64):
```python
"""external_api_tokens

Revision ID: 004_external_api_tokens
Revises: 003_report_cache
Create Date: 2026-05-18

Phase 10 -- REST API: Adds external_api_tokens table for bearer
token authentication against the public API.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_external_api_tokens"
down_revision: Union[str, None] = "003_report_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        # ... columns ...
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_external_api_tokens_token_hash",
        "external_api_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_external_api_tokens_token_hash",
        table_name="external_api_tokens",
    )
    op.drop_table("external_api_tokens")
```

---

### `tests/unit/services/test_workflow_service.py` (test)

**Analog:** `tests/unit/services/test_compliance_checking_service.py`

**Test file structure** (lines 1-30):
```python
"""Boundary tests for ComplianceCheckingService (Plan 02-05 gap closure)."""

from datetime import datetime, timezone, timedelta

import pytest

from app.database import db
from app.models.employee_profiles import EmployeeProfiles
from app.models.job_role_compliance import (
    ComplianceCheck,
    ComplianceCheckRun,
    EmployeeRoleAssignment,
)
from app.services.compliance_checking_service import ComplianceCheckingService
from tests.factories.job_code import JobCodeFactory
from tests.factories.system_role import SystemRoleFactory
from tests.factories.job_role_mapping import JobRoleMappingFactory

pytestmark = pytest.mark.unit


@pytest.fixture
def svc(app, db_session):
    return ComplianceCheckingService()
```

---

### `tests/factories/workflow.py` (test factory)

**Analog:** `tests/factories/job_code.py`

**Factory pattern** (full file):
```python
"""factory_boy factory for JobCode (app/models/job_role_compliance.py:JobCode)."""

import factory
from factory.alchemy import SQLAlchemyModelFactory
from app.database import db
from app.models.job_role_compliance import JobCode


class JobCodeFactory(SQLAlchemyModelFactory):
    class Meta:
        model = JobCode
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"

    job_code = factory.Sequence(lambda n: f"JC{n:04d}")
    job_title = factory.Sequence(lambda n: f"Test Role {n}")
    is_active = True
```

---

## Shared Patterns

### Authentication & Authorization
**Source:** `app/blueprints/admin/api_tokens.py` lines 15, 24, 86
**Apply to:** All workflow route handlers in `workflows.py`
```python
from app.middleware.auth import require_role
from app.middleware.csrf import csrf_double_submit

@require_role("admin")
def workflow_dashboard():
    # ...

@require_role("admin")
@csrf_double_submit.protect
def create_workflow():
    # state-changing POST handler
```

### Audit Logging
**Source:** `app/blueprints/admin/api_tokens.py` lines 54-68
**Apply to:** All state-changing workflow operations (create, complete item, skip item, cancel)
```python
admin_role = getattr(request, "user_role", None)
user_ip = request.headers.get("X-Forwarded-For", request.remote_addr)

current_app.container.get("audit_logger").log_admin_action(
    user_email=g.user,
    action="workflow_created",
    target=f"{workflow.employee_name} ({workflow.workflow_type})",
    details={
        "workflow_id": workflow.id,
        "job_code": workflow.job_code,
        "item_count": len(workflow.items),
    },
    user_role=admin_role,
    ip_address=user_ip,
    user_agent=request.headers.get("User-Agent"),
)
```

### Error Handling (Service Layer)
**Source:** `app/services/compliance_checking_service.py` lines 96, 215-216
**Apply to:** All `WorkflowService` methods
```python
from app.utils.error_handler import handle_service_errors

@handle_service_errors(raise_errors=True)
def generate_onboarding(self, employee_name, employee_email, job_code, created_by):
    # ...
```

### HTMX Fragment Response
**Source:** `app/blueprints/admin/reports.py` lines 55-62
**Apply to:** Dashboard tab switching, item completion, skip form
```python
@require_role("admin")
def workflows_dashboard():
    tab = request.args.get("tab", "active")
    if request.headers.get("HX-Request"):
        return _render_tab(tab)
    tab_content = _render_tab(tab)
    return render_template("admin/workflows.html", active_tab=tab, tab_content=tab_content)
```

### DI Container Access
**Source:** `app/blueprints/admin/api_tokens.py` line 18, `app/blueprints/admin/reports.py` line 133
**Apply to:** All route handlers needing `workflow_service`
```python
workflow_service = current_app.container.get("workflow_service")
```

### Batch save with deferred commit
**Source:** `app/services/compliance_checking_service.py` lines 170-213
**Apply to:** `WorkflowService.generate_onboarding()` and `generate_offboarding()` -- create workflow + items in one transaction
```python
workflow = Workflow(...)
workflow.save(commit=False)

for i, mapping in enumerate(mappings):
    item = WorkflowItem(workflow_id=workflow.id, ...)
    item.save(commit=False)

db.session.commit()
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | -- | -- | All files have strong analogs in the existing codebase |

## Metadata

**Analog search scope:** `app/models/`, `app/services/`, `app/blueprints/admin/`, `alembic/versions/`, `tests/`
**Files scanned:** 18
**Pattern extraction date:** 2026-05-17
