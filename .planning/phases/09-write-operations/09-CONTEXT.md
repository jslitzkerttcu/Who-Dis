# Phase 9: Write Operations - Context

**Gathered:** 2026-05-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Admins can take action on search results — unlocking AD accounts, resetting passwords, enabling/disabling accounts, and managing M365 licenses (assign, remove, swap) — with every action confirmed via modal, audited with full context, and handled safely on partial failure.

Write operations are admin-only (editor role collapsed to viewer in Phase 4). Actions surface inside the existing expanded profile sections (Phase 6 collapsible areas). Delivers WRIT-01..08.

</domain>

<decisions>
## Implementation Decisions

### Confirmation UX
- **D-01:** Confirmation modal shows the target user's name/email prominently and requires a freeform reason textarea before Confirm button enables. No re-typing of the target name required — just visual echo for awareness.
- **D-02:** After action completes, user sees an inline toast notification (success/error) at the top of the page plus the action button briefly changes to a checkmark or error icon. Non-blocking — user can continue working immediately.
- **D-03:** Reason text is freeform only — plain textarea, no preset dropdowns. Admin types whatever context is relevant.

### AD Action Scope
- **D-04:** All four AD operations ship together in v1: unlock, reset password, enable, disable. Full WRIT-01/02/03 coverage.
- **D-05:** Temporary password displayed in a dismissible banner with show/hide toggle and copy button. Stays visible until manually dismissed so admin can reference it while on a call. Never stored server-side after generation.
- **D-06:** Generated passwords follow a readable pattern (Word+Digits+Symbol, e.g., "Sunset42!") — easy to communicate verbally to employees. Must meet typical AD complexity requirements (uppercase, lowercase, digit, symbol, 8+ chars).
- **D-07:** AD write operations use the same LDAP bind credentials already configured. No separate write service account — assumes existing bind DN has unlock/reset/enable/disable permissions in AD.

### License Atomicity
- **D-08:** License swap uses two sequential Graph API calls (remove old SKU, then assign new SKU). If the assign fails after remove succeeds, attempt rollback by re-adding the removed license.
- **D-09:** If rollback also fails — Claude's discretion on failure UX (planner determines operationally safest approach for a ~4-5 person IT team).
- **D-10:** Graph API permissions for license write operations are unknown — planner must flag this as an external dependency and document exactly which permissions are needed (likely `User.ReadWrite.All` or `Directory.ReadWrite.All`).

### Action Placement
- **D-11:** Write action buttons appear inside the expanded profile sections (Phase 6 collapsible areas). AD actions (unlock, reset, enable/disable) in the AD/identity section. License actions (assign, remove, swap) in the M365 section. Contextual and grouped with the data they affect.
- **D-12:** Visibility of action buttons for non-admins — Claude's discretion based on the small team size (~4-5 users) and existing role-visibility patterns.
- **D-13:** License management UI placement (inline vs. sub-panel) — Claude's discretion based on complexity and existing patterns.

### Claude's Discretion
- **D-09:** Failure UX for double-failure in license swap (remove succeeded, assign failed, rollback failed). Pick the operationally safest approach.
- **D-12:** Whether action buttons are hidden for non-admins or visible-but-disabled. Consider the 4-5 person team context.
- **D-13:** Whether license actions are inline next to each license row or in a dedicated "Manage Licenses" sub-panel.
- **D-14:** Risk tiering for confirmation modals — whether high-risk actions (disable, license remove) get an extra warning banner vs. same flow for all actions. Determine based on AD/Graph reversibility.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 9: Write Operations" — 5 success criteria, depends on Phases 2/4/5/6
- `.planning/REQUIREMENTS.md` §"Write Operations" — WRIT-01..08
- `.planning/STATE.md` §"Key Decisions Locked In" — pagination pattern, audit/role conventions

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` — directory layout, blueprint/service/model locations
- `.planning/codebase/INTEGRATIONS.md` — Graph + LDAP integration shape, existing API patterns
- `.planning/codebase/CONVENTIONS.md` — service patterns, decorator usage, error handling

### Prior Phase Context
- `.planning/phases/06-enriched-profiles-search-export/06-CONTEXT.md` — D-08/D-09 (collapsible sections, lazy-load pattern), D-14 (HTMX endpoint shape)
- `.planning/phases/07-compliance-polish/07-CONTEXT.md` — SandCastle job pattern, HTMX polling
- `.planning/phases/08-reporting/08-CONTEXT.md` — Report UI patterns, KPI cards

### Existing Code (reuse, do NOT redesign)
- `app/services/ldap_service.py` — read-only LDAP service; write methods (unlock, reset, enable, disable) must be ADDED here following existing patterns
- `app/services/graph_service.py:455-484` — `get_license_details()` read method; license write methods must be ADDED here
- `app/services/audit_service_postgres.py:71` — `log_admin_action()` already exists for audit trail
- `app/middleware/auth.py:131` — `require_role()` decorator for admin-gating
- `app/models/user.py:134-150` — `has_permission()` with editor collapsed to viewer (Phase 4 D-05)
- `app/templates/admin/compliance_violations.html:185-225` — existing modal pattern for reference
- `app/blueprints/search/__init__.py` — search result view where expanded profiles live

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `audit_service.log_admin_action()`: already supports who/what/target/IP/reason logging — extend for write ops
- Confirmation modal pattern in `admin/compliance_violations.html`: existing modal with JS confirm flow
- HTMX fragment pattern from Phase 6 expanded sections: action buttons render inside these fragments
- `@auth_required` + `@require_role("admin")` decorator stack: ready to gate write endpoints

### Established Patterns
- Services extend `BaseSearchService` or `BaseAPIService` with `@handle_service_errors` decorator
- New endpoints follow `@auth_required` → `@require_role()` → audit log → HTMX fragment response
- Toast/notification pattern needs to be established (no existing toast component found)
- LDAP operations use `ldap3` library: `Connection.modify()` for attribute changes, `Connection.extend.microsoft.unlock_account()` for unlock

### Integration Points
- New LDAP write methods added to existing `LDAPService` class
- New Graph write methods added to existing `GraphService` class
- New blueprint routes in `app/blueprints/search/` (or a new `write_operations` sub-module)
- Confirmation modal as a shared Jinja partial (reusable across all write actions)
- Toast notification component (new, shared across the app)

</code_context>

<specifics>
## Specific Ideas

- Password generation: readable pattern like "Sunset42!" — word from a curated list + 2 digits + symbol. Must meet AD complexity (upper, lower, digit, symbol, 8+ chars minimum).
- Dismissible password banner persists on screen until manually closed — designed for admin on a phone call reading the password to a user.
- All actions surface contextually in expanded profile sections — no separate "actions page" or top-level action bar.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 9-Write Operations*
*Context gathered: 2026-05-17*
