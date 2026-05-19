# Phase 11: Workflow Automation - Research

**Researched:** 2026-05-17
**Domain:** Workflow checklists (onboarding/offboarding) built on existing Flask/PostgreSQL/HTMX stack
**Confidence:** HIGH

## Summary

Phase 11 adds onboarding and offboarding workflow checklists to WhoDis. The feature generates checklists from the existing `JobRoleMapping` compliance data model, tracks per-item completion with audit trails, and provides a dashboard for monitoring active workflows. This is a pure application-layer feature -- no new external libraries or services are required. All patterns (models, services, admin blueprint, HTMX interactions, Alembic migrations) are well-established in the codebase from Phases 7-10.

The primary complexity is in the data model design: three new tables (`workflows`, `workflow_items`, `standard_offboarding_items`) plus an Alembic migration (005). The service layer is a single `WorkflowService` registered in the DI container. The admin blueprint gets a new `workflows.py` module with routes wired in `__init__.py` following the exact pattern used for reports, compliance, and API tokens. Templates follow the Phase 8 KPI-cards + tabbed-table pattern established in `reports.html`.

**Primary recommendation:** Implement as a standard admin feature module (model + service + blueprint routes + templates) following the Phase 8/10 patterns exactly. No new dependencies needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-03:** Two paths for employee identification: search-first (reuse SearchOrchestrator) and form entry for net-new hires
- **D-06:** Items CAN be marked "Skipped" or "N/A" with required note. Recorded in audit trail.
- **D-07:** Each checklist item can have an optional due date. Overdue items highlighted on dashboard.
- **D-08:** No formal workflow assignment -- any admin can complete any item. Audit trail records who.
- **D-09:** Offboarding checklists generated from JobRoleMapping entries (same source as onboarding). Works for all employees.
- **D-10:** Offboarding includes role removals PLUS configurable standard offboarding items.
- **D-11:** Standard offboarding items managed through admin UI without code deploy.
- **AUTO-01/AUTO-02:** Explicitly deferred to v2. Do NOT implement auto-execution of checklist items.

### Claude's Discretion
- **D-01:** Checklist generation approach (manual trigger vs. template-first)
- **D-02:** Item scope (roles-only vs. roles + custom freeform items)
- **D-04:** Actionable execute buttons vs. manual checkboxes for write-operation items
- **D-05:** Individual vs. individual + bulk completion
- **D-12:** Dashboard nav placement (admin sub-section vs. top-level)
- **D-13:** Dashboard layout (list-only vs. KPI cards + list)
- **D-14:** Completed workflow visibility (tabbed vs. separate archive)

### Deferred Ideas (OUT OF SCOPE)
- **AUTO-01:** Auto-execute checklist items (v2)
- **AUTO-02:** Self-service portal (v2)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| WKFL-01 | Admin can generate onboarding checklist from job role mappings for a given job code | `JobRoleMapping.get_active_mappings_for_job_code()` provides the data source. New `WorkflowService.generate_onboarding()` method creates workflow + items from mappings. |
| WKFL-02 | Admin can generate offboarding checklist that reverses all provisions | Same data source as WKFL-01, mapping type "required" becomes "remove" action. Standard offboarding items appended from `standard_offboarding_items` table. |
| WKFL-03 | Each checklist item tracks completion status (who completed, when) | `workflow_items` table has `completed_by`, `completed_at`, `status` columns. Audit trail via `audit_service.log_admin_action()`. |
| WKFL-04 | Dashboard shows active workflows with progress and overdue items | Dashboard route at `/admin/workflows` with KPI cards + tabbed Active/Completed tables. Progress = completed_count/total_count. Overdue = items past due_date with pending status. |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Checklist generation from job code | API / Backend (WorkflowService) | -- | Business logic: query mappings, create workflow records |
| Completion tracking | API / Backend (WorkflowService + audit) | Frontend (HTMX checkbox POST) | State change is a DB write; HTMX provides the interaction |
| Overdue detection | API / Backend (SQL query) | Frontend (Jinja2 conditional rendering) | Date comparison in SQL; visual treatment in template |
| Dashboard KPI calculation | API / Backend (aggregate queries) | Frontend (KPI card templates) | Counts computed server-side; rendered as HTML |
| Employee search for workflow creation | API / Backend (SearchOrchestrator) | Frontend (HTMX typeahead) | Reuses existing search infrastructure |
| Standard offboarding items management | API / Backend (CRUD service) | Frontend (admin list UI) | Simple CRUD, stored in DB |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | Web framework | Already in use [VERIFIED: requirements.txt] |
| SQLAlchemy | 2.0.45 | ORM for new models | Already in use [VERIFIED: requirements.txt] |
| Alembic | 1.18.4 | Database migrations | Already in use [VERIFIED: requirements.txt] |
| Jinja2 | (bundled with Flask) | Template rendering | Already in use [VERIFIED: codebase] |
| HTMX | CDN | Dynamic interactions | Already in use [VERIFIED: codebase templates] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| psycopg2-binary | 2.9.11 | PostgreSQL adapter | Already installed, no change [VERIFIED: requirements.txt] |

**No new packages required for this phase.** All functionality builds on the existing stack.

## Package Legitimacy Audit

No new packages are introduced in this phase. All libraries are already in `requirements.txt` and verified from prior phases.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| (none) | -- | -- | -- | -- | -- | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Admin clicks "Generate Checklist"
        |
        v
[Create Workflow Form]  <-- employee search (HTMX typeahead -> SearchOrchestrator)
   |            |               OR manual entry with job code dropdown
   v            v
[WorkflowService.generate_onboarding/offboarding()]
   |
   |-- Query JobRoleMapping.get_active_mappings_for_job_code(job_code)
   |-- (offboarding only) Query StandardOffboardingItem.get_all_active()
   |-- Create Workflow record (type, employee_name, employee_email, job_code)
   |-- Create WorkflowItem records (one per mapping + standard items)
   |-- audit_service.log_admin_action("workflow_created", ...)
   |
   v
[Workflow Dashboard]  <-- HTMX tab switching (Active / Completed)
   |
   |-- KPI queries: active count, overdue count, completed this month, avg days
   |-- Active table: workflows WHERE status='active' with progress calculation
   |-- Completed table: workflows WHERE status='completed' (paginated)
   |
   v
[Workflow Detail View]  <-- individual workflow with all items
   |
   |-- Item completion: HTMX POST -> WorkflowService.complete_item(item_id, user)
   |-- Item skip: HTMX POST -> WorkflowService.skip_item(item_id, user, reason)
   |-- Auto-complete workflow when all items done/skipped
   |-- audit_service.log_admin_action() on every state change
```

### Recommended Project Structure

```
app/
├── models/
│   └── workflow.py              # Workflow, WorkflowItem, StandardOffboardingItem
├── services/
│   └── workflow_service.py      # WorkflowService (generation, completion, dashboard queries)
├── blueprints/
│   └── admin/
│       └── workflows.py         # Route handlers (dashboard, create, detail, offboarding items)
├── templates/
│   └── admin/
│       ├── workflows.html                    # Dashboard page (KPI cards + tabs)
│       ├── workflow_create.html              # Create workflow form
│       ├── workflow_detail.html              # Workflow detail with checklist
│       ├── workflow_offboarding_items.html   # Standard offboarding items admin
│       └── partials/
│           ├── _workflow_active_table.html   # Active workflows HTMX partial
│           ├── _workflow_completed_table.html # Completed workflows HTMX partial
│           ├── _workflow_item.html           # Single checklist item row partial
│           └── _workflow_kpi.html            # KPI cards partial
alembic/
└── versions/
    └── 005_workflow_tables.py   # Migration: workflows, workflow_items, standard_offboarding_items
```

### Pattern 1: Admin Blueprint Module Registration
**What:** New route module follows exact pattern of `reports.py` and `api_tokens.py`
**When to use:** All workflow routes
**Example:**
```python
# Source: app/blueprints/admin/__init__.py (existing pattern)
# In workflows.py - define route handlers with @require_role("admin")
# In __init__.py - wire routes:
from . import workflows
admin_bp.route("/workflows", endpoint="workflows_dashboard")(workflows.workflows_dashboard)
admin_bp.route("/workflows/create", methods=["GET", "POST"])(workflows.create_workflow)
admin_bp.route("/workflows/<int:workflow_id>")(workflows.workflow_detail)
# ... etc
```

### Pattern 2: Model with Mixins
**What:** New models extend BaseModel + TimestampMixin following established conventions
**When to use:** Workflow and WorkflowItem models
**Example:**
```python
# Source: app/models/base.py (existing pattern)
class Workflow(BaseModel, TimestampMixin):
    __tablename__ = "workflows"

    workflow_type = db.Column(db.String(20), nullable=False)  # 'onboarding' / 'offboarding'
    status = db.Column(db.String(20), nullable=False, default="active")
    employee_name = db.Column(db.String(255), nullable=False)
    employee_email = db.Column(db.String(255))
    job_code = db.Column(db.String(50), nullable=False)
    job_title = db.Column(db.String(255))
    created_by = db.Column(db.String(255), nullable=False)
    completed_at = db.Column(db.DateTime(timezone=True))
```

### Pattern 3: HTMX Fragment Responses
**What:** Routes return full page for initial load, HTML fragments for HTMX requests
**When to use:** Tab switching, item completion, skip forms
**Example:**
```python
# Source: app/blueprints/admin/reports.py (existing pattern)
@require_role("admin")
def workflows_dashboard():
    tab = request.args.get("tab", "active")
    if request.headers.get("HX-Request"):
        return _render_tab(tab)  # Fragment only
    tab_content = _render_tab(tab)
    return render_template("admin/workflows.html", active_tab=tab, tab_content=tab_content)
```

### Pattern 4: Service Registration in DI Container
**What:** WorkflowService registered as singleton factory in container.py
**When to use:** Service initialization
**Example:**
```python
# Source: app/container.py (existing pattern)
from app.services.workflow_service import WorkflowService
container.register("workflow_service", lambda c: WorkflowService())
```

### Pattern 5: Alembic Migration
**What:** New migration 005 creates three tables following exact pattern from 004
**When to use:** Database schema changes
**Example:**
```python
# Source: alembic/versions/004_external_api_tokens.py (existing pattern)
revision: str = "005_workflow_tables"
down_revision: Union[str, None] = "004_external_api_tokens"
```

### Anti-Patterns to Avoid
- **Auto-executing checklist items:** AUTO-01 is explicitly deferred to v2. Do not add "Execute" buttons that call Phase 9 write operations.
- **Freeform per-workflow items:** Per UI-SPEC D-02 decision, items come from role mappings + standard offboarding items only. No freeform text input per workflow.
- **Complex assignment/routing:** D-08 locks this -- any admin can complete any item. No user assignment, no task routing.
- **Separate blueprint:** Workflows are admin-only. Add to existing admin blueprint, not a new top-level blueprint.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pagination | Custom offset/limit logic | `paginate()` helper from Phase 1 | Already tested, includes HTMX `hx-push-url` |
| Audit logging | Custom logging table/logic | `audit_service.log_admin_action()` | Standard audit trail pattern across all admin features |
| Auth enforcement | Custom role checks | `@auth_required` + `@require_role("admin")` | Middleware-level enforcement, tested in Phase 2 |
| Error handling | Try/except in every route | `@handle_service_errors` decorator | Consistent error handling with logging |
| Date/time handling | Naive datetime operations | `datetime.now(timezone.utc)` | UTC-aware timestamps matching all existing models |
| CSV export | Manual string building | `csv.DictWriter` pattern from reports.py | Safe CSV generation with injection prevention |

**Key insight:** This phase introduces zero new technical concepts. Every pattern (models, services, admin routes, HTMX fragments, Alembic migrations, audit logging, pagination) has a direct precedent in the codebase from Phases 7-10. The risk is not technical complexity but scope creep toward AUTO-01 territory.

## Common Pitfalls

### Pitfall 1: Forgetting to Auto-Complete Workflows
**What goes wrong:** All items marked complete/skipped but workflow stays "active" forever
**Why it happens:** Missing the check after each item status change
**How to avoid:** In `WorkflowService.complete_item()` and `skip_item()`, always call `_check_workflow_completion()` which sets workflow status to "completed" and `completed_at` when no items remain pending.
**Warning signs:** Active workflow count grows but items are all done

### Pitfall 2: N+1 Queries on Dashboard
**What goes wrong:** Dashboard loads slowly because each workflow row triggers separate queries for item counts
**Why it happens:** Lazy-loading relationships without joinedload or subquery aggregation
**How to avoid:** Use `db.session.query()` with `func.count()` aggregation for progress/overdue counts. Dashboard queries should be 2-3 SQL statements max, not N+1.
**Warning signs:** Dashboard load time scales linearly with workflow count

### Pitfall 3: Race Condition on Concurrent Item Completion
**What goes wrong:** Two admins mark the same item complete simultaneously, or auto-complete check fires incorrectly
**Why it happens:** No optimistic locking or status precondition check
**How to avoid:** Check item status before updating (`if item.status != 'pending': return error`). SQLAlchemy's session scoping handles the DB-level concurrency for a 4-5 user team.
**Warning signs:** Duplicate completion entries in audit log

### Pitfall 4: Orphaned Standard Offboarding Items
**What goes wrong:** Deleting a standard offboarding item breaks existing workflows that reference it
**Why it happens:** Direct FK relationship with cascade delete
**How to avoid:** WorkflowItem stores the item text directly (denormalized copy), not an FK to StandardOffboardingItem. Deleting a standard item only affects future checklists.
**Warning signs:** IntegrityError when deleting standard items

### Pitfall 5: Missing CSRF on State-Changing HTMX Requests
**What goes wrong:** Item completion/skip POSTs fail with 403
**Why it happens:** HTMX requests don't automatically include CSRF token
**How to avoid:** Include `hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'` on HTMX forms/buttons, or use the existing `@ensure_csrf_cookie` pattern. The existing HTMX setup likely already handles this via a global header configuration.
**Warning signs:** 403 errors on POST requests

## Code Examples

### Data Model Design

```python
# Source: Derived from existing patterns in app/models/base.py and app/models/job_role_compliance.py

class Workflow(BaseModel, TimestampMixin):
    """Onboarding or offboarding workflow for an employee."""
    __tablename__ = "workflows"

    workflow_type = db.Column(db.String(20), nullable=False, index=True)  # 'onboarding'/'offboarding'
    status = db.Column(db.String(20), nullable=False, default="active", index=True)  # 'active'/'completed'/'cancelled'
    employee_name = db.Column(db.String(255), nullable=False)
    employee_email = db.Column(db.String(255), index=True)
    job_code = db.Column(db.String(50), nullable=False, index=True)
    job_title = db.Column(db.String(255))
    created_by = db.Column(db.String(255), nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True))

    items = db.relationship("WorkflowItem", back_populates="workflow", cascade="all, delete-orphan",
                           order_by="WorkflowItem.sort_order")


class WorkflowItem(BaseModel, TimestampMixin):
    """Single checklist item within a workflow."""
    __tablename__ = "workflow_items"

    workflow_id = db.Column(db.Integer, db.ForeignKey("workflows.id"), nullable=False, index=True)
    item_text = db.Column(db.String(500), nullable=False)  # Denormalized: copied from mapping/standard item
    item_source = db.Column(db.String(50), nullable=False)  # 'role_mapping' / 'standard_offboarding'
    source_detail = db.Column(db.String(255))  # e.g., "keystone.TellerRole (required)" or "Collect equipment"
    action_type = db.Column(db.String(20), nullable=False)  # 'add'/'remove' for roles
    system_name = db.Column(db.String(100))  # From SystemRole.system_name
    role_name = db.Column(db.String(255))  # From SystemRole.role_name
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)  # 'pending'/'completed'/'skipped'
    completed_by = db.Column(db.String(255))
    completed_at = db.Column(db.DateTime(timezone=True))
    skip_reason = db.Column(db.Text)
    due_date = db.Column(db.Date)

    workflow = db.relationship("Workflow", back_populates="items")


class StandardOffboardingItem(BaseModel, TimestampMixin):
    """Configurable standard offboarding checklist items that apply to all employees."""
    __tablename__ = "standard_offboarding_items"

    item_text = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_by = db.Column(db.String(255), nullable=False)
```

### Checklist Generation Logic

```python
# Source: Derived from JobRoleMapping.get_active_mappings_for_job_code() pattern

def generate_onboarding(self, employee_name, employee_email, job_code, created_by):
    """Generate onboarding workflow from job role mappings."""
    mappings = JobRoleMapping.get_active_mappings_for_job_code(job_code)
    if not mappings:
        raise ValueError(f"No active role mappings found for job code {job_code}")

    job_code_obj = JobCode.get_by_job_code(job_code)
    workflow = Workflow(
        workflow_type="onboarding",
        employee_name=employee_name,
        employee_email=employee_email,
        job_code=job_code,
        job_title=job_code_obj.job_title if job_code_obj else None,
        created_by=created_by,
    )
    workflow.save(commit=False)

    for i, mapping in enumerate(mappings):
        if mapping.mapping_type == "prohibited":
            continue  # Skip prohibited mappings for onboarding
        item = WorkflowItem(
            workflow_id=workflow.id,
            item_text=f"{'Assign' if mapping.mapping_type == 'required' else 'Consider assigning'}: "
                      f"{mapping.system_role.role_name} ({mapping.system_role.system_name})",
            item_source="role_mapping",
            source_detail=f"{mapping.system_role.system_name}.{mapping.system_role.role_name} ({mapping.mapping_type})",
            action_type="add",
            system_name=mapping.system_role.system_name,
            role_name=mapping.system_role.role_name,
            sort_order=i,
        )
        item.save(commit=False)

    db.session.commit()
    return workflow
```

### Dashboard Aggregate Query

```python
# Source: Derived from ComplianceCheckingService.get_compliance_summary() pattern

def get_dashboard_stats(self):
    """Get KPI stats for the workflow dashboard."""
    from sqlalchemy import func, case
    active_count = Workflow.query.filter_by(status="active").count()

    overdue_count = db.session.query(func.count(WorkflowItem.id)).filter(
        WorkflowItem.status == "pending",
        WorkflowItem.due_date < date.today(),
    ).join(Workflow).filter(Workflow.status == "active").scalar() or 0

    # ... completed_this_month, avg_completion_days similarly
    return {"active": active_count, "overdue": overdue_count, ...}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| SQL files for schema | Alembic migrations | Phase 9 (WD-DB-02) | New tables use Alembic, not create_tables.sql |
| config_get() for settings | os.environ | Phase 9 (D-11) | No encrypted-config dependency for new services |
| Separate blueprint per feature | Admin sub-modules | Phase 7+ | workflows.py is an admin module, not a separate blueprint |

**Deprecated/outdated:**
- `database/create_tables.sql`: No longer the primary schema tool. Use Alembic migrations for new tables. [VERIFIED: alembic/ directory exists with 4 migrations]
- `EncryptionService` / `config_get()` for secrets: Removed in Phase 9. New services use `os.environ` directly. [VERIFIED: container.py comments]

## Assumptions Log

> List all claims tagged `[ASSUMED]` in this research.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | WorkflowItem should denormalize item_text rather than FK to StandardOffboardingItem | Code Examples | If FK is used instead, deleting standard items cascades to existing workflows. Denormalization is the safer design. |
| A2 | Prohibited mappings should be excluded from onboarding checklists | Code Examples | If users want to see prohibited items as "do NOT assign" reminders, the generation logic needs adjustment. Low risk -- easily added later. |
| A3 | Default due dates are not auto-set during generation | Architecture | If users expect auto-generated due dates (e.g., "3 days from creation"), the generation logic needs a configurable default. Can be added without schema change (due_date column exists). |

**All other claims are verified against the codebase directly.**

## Open Questions

1. **Due date default behavior**
   - What we know: D-07 says items CAN have optional due dates, overdue items are highlighted
   - What's unclear: Should generation auto-set due dates (e.g., 3 business days from creation) or leave them blank for manual entry?
   - Recommendation: Leave blank by default. Admin can set per-item. Simpler first version, aligns with "manual trigger" approach.

2. **Workflow deletion vs. cancellation**
   - What we know: UI-SPEC has a "Delete Workflow" button with destructive confirmation
   - What's unclear: Should this be a hard delete or soft cancel (status = "cancelled")?
   - Recommendation: Soft cancel (status = "cancelled") to preserve audit trail. The word "Delete" in the UI can map to cancel + hide from active view.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.4.2 |
| Config file | `tests/conftest.py` (session-scoped ephemeral Postgres via testcontainers) |
| Quick run command | `pytest tests/unit/services/test_workflow_service.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| WKFL-01 | Generate onboarding checklist from job code mappings | unit | `pytest tests/unit/services/test_workflow_service.py::test_generate_onboarding -x` | Wave 0 |
| WKFL-01 | Error when job code has no mappings | unit | `pytest tests/unit/services/test_workflow_service.py::test_generate_onboarding_no_mappings -x` | Wave 0 |
| WKFL-02 | Generate offboarding with reversed provisions + standard items | unit | `pytest tests/unit/services/test_workflow_service.py::test_generate_offboarding -x` | Wave 0 |
| WKFL-03 | Complete item records who and when | unit | `pytest tests/unit/services/test_workflow_service.py::test_complete_item -x` | Wave 0 |
| WKFL-03 | Skip item requires reason | unit | `pytest tests/unit/services/test_workflow_service.py::test_skip_item_requires_reason -x` | Wave 0 |
| WKFL-04 | Dashboard stats return correct counts | unit | `pytest tests/unit/services/test_workflow_service.py::test_dashboard_stats -x` | Wave 0 |
| WKFL-04 | Overdue items detected correctly | unit | `pytest tests/unit/services/test_workflow_service.py::test_overdue_detection -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/unit/services/test_workflow_service.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/services/test_workflow_service.py` -- covers WKFL-01, WKFL-02, WKFL-03, WKFL-04
- [ ] Test fixtures for Workflow, WorkflowItem, StandardOffboardingItem factories in `tests/factories/`

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `@auth_required` decorator on all routes |
| V3 Session Management | no (handled at middleware level) | Existing session management |
| V4 Access Control | yes | `@require_role("admin")` on all workflow routes |
| V5 Input Validation | yes | Validate employee_name, email, job_code, skip_reason inputs |
| V6 Cryptography | no | No secrets stored in workflow tables |

### Known Threat Patterns for This Phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| CSRF on state-changing HTMX requests | Tampering | Double-submit CSRF token via `@ensure_csrf_cookie` + `hx-headers` |
| Unauthorized workflow manipulation | Elevation of Privilege | `@require_role("admin")` on all endpoints |
| XSS in employee_name or skip_reason | Tampering | Jinja2 auto-escaping (default) + `escape()` for any raw rendering |
| SQL injection in search/filter params | Tampering | SQLAlchemy parameterized queries (ORM-level protection) |
| Audit trail tampering | Repudiation | Audit log via separate service; admin cannot edit audit records |

## Project Constraints (from CLAUDE.md)

- **Tech stack:** Flask/PostgreSQL/HTMX -- extend existing patterns, no new frameworks
- **Auth:** Azure AD SSO / Keycloak OIDC -- all new endpoints use `@auth_required` + `@require_role`
- **Security:** All write operations require audit trail and appropriate role checks
- **DI Container:** New services registered in `app/container.py`
- **Error handling:** Use `@handle_service_errors` decorator on service methods
- **Naming:** snake_case modules, PascalCase classes, module-level loggers
- **Models:** Extend BaseModel + appropriate mixins (TimestampMixin at minimum)
- **Linting:** `ruff check --fix` before commit
- **Type checking:** `mypy app/` before commit

## Sources

### Primary (HIGH confidence)
- `app/models/job_role_compliance.py` -- JobCode, SystemRole, JobRoleMapping models with `get_active_mappings_for_job_code()` [VERIFIED: codebase]
- `app/models/base.py` -- BaseModel, TimestampMixin, UserTrackingMixin patterns [VERIFIED: codebase]
- `app/services/compliance_checking_service.py` -- Service pattern with `@handle_service_errors`, batch processing, progress tracking [VERIFIED: codebase]
- `app/services/job_role_mapping_service.py` -- CRUD service pattern, history logging [VERIFIED: codebase]
- `app/container.py` -- DI registration pattern [VERIFIED: codebase]
- `app/blueprints/admin/__init__.py` -- Route wiring pattern for admin modules [VERIFIED: codebase]
- `app/blueprints/admin/reports.py` -- KPI cards + tabbed dashboard pattern [VERIFIED: codebase]
- `alembic/versions/004_external_api_tokens.py` -- Migration pattern [VERIFIED: codebase]
- `tests/conftest.py` -- Test infrastructure (testcontainers Postgres, session fixtures) [VERIFIED: codebase]
- `.planning/phases/11-workflow-automation/11-UI-SPEC.md` -- UI design contract [VERIFIED: codebase]
- `.planning/phases/11-workflow-automation/11-CONTEXT.md` -- User decisions [VERIFIED: codebase]

### Secondary (MEDIUM confidence)
- None needed -- all patterns verified directly in codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new packages, all patterns verified in codebase
- Architecture: HIGH -- follows established admin module pattern (Phase 8/10 precedent)
- Pitfalls: HIGH -- derived from known SQLAlchemy/Flask patterns and codebase conventions

**Research date:** 2026-05-17
**Valid until:** 2026-06-17 (stable -- no external dependency changes expected)
