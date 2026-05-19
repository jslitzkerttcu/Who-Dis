# Phase 11: Workflow Automation - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can generate onboarding and offboarding checklists from job role compliance mappings, track each item's completion with full audit trail, and monitor active workflows on a dashboard with progress and overdue indicators. Delivers WKFL-01, WKFL-02, WKFL-03, WKFL-04.

</domain>

<decisions>
## Implementation Decisions

### Checklist Generation
- **D-01:** Checklist generation approach is **Claude's discretion** — choose between manual trigger (admin selects job code + employee, clicks Generate) or template-first (admin customizes templates per job code, then instantiates). Consider the 4-5 person team size and existing `JobRoleMapping` data model.
- **D-02:** Checklist item scope is **Claude's discretion** — decide whether items come exclusively from `JobRoleMapping` entries or whether admin can add freeform custom items (equipment, orientation, etc.). Consider WKFL-01 wording ("from job role mappings") and practical IT operations needs.
- **D-03:** Two paths for identifying the target employee: (1) search-first for existing employees (reuse `SearchOrchestrator`), clicking "Start Onboarding" from profile; (2) form entry for net-new hires not yet in any system. Both paths must be supported.
- **D-04:** Whether checklist items linked to Phase 9 write operations (AD enable, license assign) have an "Execute" button or remain manual checkboxes is **Claude's discretion**. Consider that AUTO-01 (auto-execute) is deferred to v2 requirements — decide how close to that line v1 should go.

### Completion Tracking
- **D-05:** How admins mark items complete (individual checkboxes vs. individual + bulk) is **Claude's discretion**. Consider typical checklist size per job code and the 4-5 person team workflow.
- **D-06:** Items CAN be marked "Skipped" or "N/A" with a required note explaining why. The skipped status and reason are recorded in the audit trail. Items are not silently removable.
- **D-07:** Each checklist item can have an optional due date. Overdue items are highlighted on the dashboard (supports WKFL-04 "highlights overdue items" requirement).
- **D-08:** No formal workflow assignment — any admin can complete any item on any workflow. The audit trail records who completed each item. Practical for a 4-5 person team without formal task routing.

### Offboarding Reversal
- **D-09:** Offboarding checklists are generated directly from the job code's `JobRoleMapping` entries (same source as onboarding). Each "required" role becomes a "remove" item. No dependency on whether the employee was previously onboarded through WhoDis — works for all existing employees.
- **D-10:** Offboarding includes role removals from mappings PLUS a configurable set of standard offboarding items (e.g., disable AD account, forward email, collect equipment) that apply to everyone regardless of job code.
- **D-11:** Standard offboarding items are managed through the admin UI — admins can add, remove, and reorder items at any time without a code deploy.

### Dashboard Design
- **D-12:** Dashboard navigation placement is **Claude's discretion** — choose between admin sub-section (`/admin/workflows`) or top-level nav item based on existing nav structure and admin-only access.
- **D-13:** Dashboard at-a-glance content is **Claude's discretion** — choose between a simple active workflows list or KPI cards + list (matching Phase 8 reporting pattern).
- **D-14:** Whether completed workflows appear on the dashboard (tabbed Active/Completed) or in a separate history view is **Claude's discretion** — optimize for dashboard clarity.

### Claude's Discretion
- **D-01:** Checklist generation approach (manual trigger vs. template-first)
- **D-02:** Item scope (roles-only vs. roles + custom freeform items)
- **D-04:** Actionable execute buttons vs. manual checkboxes for write-operation items
- **D-05:** Individual vs. individual + bulk completion
- **D-12:** Dashboard nav placement (admin sub-section vs. top-level)
- **D-13:** Dashboard layout (list-only vs. KPI cards + list)
- **D-14:** Completed workflow visibility (tabbed vs. separate archive)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 11: Workflow Automation" — 4 success criteria, depends on Phases 7 and 9
- `.planning/REQUIREMENTS.md` §"Workflow" — WKFL-01..04
- `.planning/REQUIREMENTS.md` §"Advanced Automation" — AUTO-01/02 are v2 (deferred); do NOT implement auto-execution of checklist items
- `.planning/STATE.md` §"Key Decisions Locked In" — pagination pattern, audit/role conventions

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` — directory layout, blueprint/service/model locations
- `.planning/codebase/ARCHITECTURE.md` — DI container, service patterns, entry points
- `.planning/codebase/CONVENTIONS.md` — naming, decorator usage, error handling patterns

### Existing Code (extend, do NOT redesign)
- `app/models/job_role_compliance.py` — `JobCode`, `SystemRole`, `JobRoleMapping` models with `mapping_type` (required/optional/prohibited), priorities, effective dates. **This is the data source for checklist generation.**
- `app/models/job_role_compliance.py:198` — `JobRoleMapping.get_active_mappings_for_job_code()` — retrieves current mappings for a job code (the core query for checklist generation)
- `app/models/job_role_compliance.py:46` — `JobCode.get_active_job_codes()` — lists job codes for the generation form dropdown
- `app/services/job_role_mapping_service.py` — existing service for managing job role mappings
- `app/services/compliance_checking_service.py` — compliance check patterns (progress tracking, bulk operations)
- `app/services/audit_service_postgres.py:71` — `log_admin_action()` for audit trail on checklist actions
- `app/middleware/auth.py:131` — `require_role()` decorator for admin-gating workflow endpoints
- `app/blueprints/admin/` — admin blueprint where workflow management lives
- `app/blueprints/search/__init__.py` — search result view where "Start Onboarding" button would surface

### Prior Phase Context
- `.planning/phases/09-write-operations/09-CONTEXT.md` — confirmation UX patterns (D-01..03), AD/license write services, audit conventions
- `.planning/phases/08-reporting/08-CONTEXT.md` — KPI card + data table dashboard pattern (D-02), CSV export, paginated tables
- `.planning/phases/07-compliance-polish/07-CONTEXT.md` — SandCastle job pattern, HTMX progress polling, compliance check flow

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `JobRoleMapping.get_active_mappings_for_job_code()`: core query for generating onboarding items from compliance mappings
- `JobCode.get_active_job_codes()`: populates job code dropdown in generation form
- `SearchOrchestrator`: employee lookup for search-first onboarding path
- `audit_service.log_admin_action()`: audit trail for workflow creation, item completion, skip/N/A
- Phase 1 `paginate()` helper: paginate workflow history and large checklists
- Phase 7 CSV export pattern: export completed workflow history
- Phase 8 KPI cards pattern: dashboard summary statistics
- Phase 9 write operations services: AD actions and license management (if actionable items are implemented)
- `@auth_required` + `@require_role("admin")`: gate all workflow endpoints

### Established Patterns
- Blueprint-based routing: new routes in `app/blueprints/admin/` (or new workflows sub-module)
- Service registration in `app/container.py`: register workflow service
- `@handle_service_errors` decorator: consistent error handling
- HTMX fragment responses for partial updates (checklist item completion without page reload)
- Model mixins: `TimestampMixin` + `UserTrackingMixin` for workflow and item models
- `BaseModel.save(commit=True/False)` for atomic operations

### Integration Points
- New models: Workflow, WorkflowItem, StandardOffboardingItem (or similar)
- New service: WorkflowService for checklist generation, completion tracking, dashboard queries
- New admin routes: `/admin/workflows/` (dashboard), `/admin/workflows/create` (generation), `/admin/workflows/<id>` (detail/completion)
- New templates: workflow dashboard, checklist detail view, generation form
- Search integration: "Start Onboarding" button on profile cards (search blueprint)
- Alembic migration for new tables

</code_context>

<specifics>
## Specific Ideas

- Search-first path: "Start Onboarding" button appears on expanded profile cards in search results, pre-populating employee data and detecting their job code from `EmployeeProfiles.ukg_job_code`
- Form entry path: simple form with name, email, job code dropdown for employees not yet in any system
- Offboarding standard items managed via admin UI (add/remove/reorder), stored in database, included in every offboarding checklist regardless of job code
- Skipped items show as a distinct visual state (not hidden) with the reason visible on hover or expansion

</specifics>

<deferred>
## Deferred Ideas

- **AUTO-01: Auto-execute checklist items** — v2 requirement. Checklist items that correspond to write operations auto-execute AD actions and license assignments. Not in Phase 11 scope.
- **AUTO-02: Self-service portal** — v2 requirement. Common IT requests handled through self-service. Not in Phase 11 scope.

</deferred>

---

*Phase: 11-Workflow Automation*
*Context gathered: 2026-05-17*
