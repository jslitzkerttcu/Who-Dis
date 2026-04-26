# Phase 6: Enriched Profiles & Search Export - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Profile cards display the full picture of an employee — Microsoft 365 (assigned licenses, MFA status, last sign-in date) and Genesys Cloud (queues, skills with proficiency, current presence) — surfaced in two collapsible sections that lazy-load on expand. Per-profile **Copy to Clipboard** (plain text) and **Export CSV** buttons let IT staff move that data into tickets, Teams, or audits.

Read-only: Phase 6 displays and exports. Write actions on M365 licenses (assign / remove SKU) belong to Phase 9.

Delivers PROF-01..06 + SRCH-01..02 (8 requirements).

</domain>

<decisions>
## Implementation Decisions

### Data sources (Graph)
- **D-01:** Last sign-in date (PROF-01) sourced from `user.signInActivity.lastSignInDateTime`. Single Graph field, cheap, returns the timestamp directly. **Requires `AuditLog.Read.All` AND Azure AD Premium P1 license on the tenant.**
- **D-02:** MFA status + auth methods (PROF-02) sourced from `GET /users/{id}/authentication/methods`. Per-user call on section expand (lazy). **Requires `UserAuthenticationMethod.Read.All`.**
- **D-03:** Existing `/api/signin-logs/<id>` endpoint (already wired, uses `AuditLog.Read.All`) is retained for the expanded sign-in history list. Already in production.

### License display (PROF-01)
- **D-04:** SKU GUID → friendly name resolution via cached `/subscribedSkus` from Graph. Background job refreshes once per day (mirror of `genesys_cache_db` pattern). **Requires `Organization.Read.All`** (verify whether already granted on existing app reg).
- **D-05:** License section shows SKU friendly name + `assignedDateTime` from `/users/{id}/licenseDetails`. No per-service-plan breakdown in v1 (defer to a future phase if asked).

### Permission degradation
- **D-06:** When a Graph permission is missing or returns 403, the section still renders but shows `"<field> unavailable — missing <permission>"`. The service logs an ERROR once per startup naming the missing permission. Operators get a clear signal; users aren't blocked. No hard-fail / startup gate.

### Caching
- **D-07:** New enriched fields (signInActivity, MFA methods, M365 licenses + license details) cache in the existing **EmployeeProfile 24-hour TTL**. Reuses Phase 1 force-refresh button. No separate short-TTL layer.

### Section layout (PROF-04, PROF-05)
- **D-08:** Two collapsible sections below the default card:
  1. **Microsoft 365** — licenses, MFA, last sign-in timestamp, sign-in log (existing endpoint reused for the log table)
  2. **Genesys Cloud** — queues, skills with proficiency, current presence
  Default card stays unchanged (name, title, department, manager, contact).
- **D-09:** Strict lazy-load (PROF-05): sections render empty until the user clicks expand. First expand triggers HTMX `GET /search/api/profile/<id>/m365` (and `/genesys`) endpoints that follow the existing `/api/signin-logs/<id>` shape verbatim — `@auth_required` + `@require_role("viewer")` + audit log + Jinja fragment response.
- **D-10:** No per-result eager summary line. No hover/intersection-observer auto-load. Click to expand only.

### Export & copy (SRCH-01, SRCH-02)
- **D-11:** Per-profile scope only. Each result card carries its own **Copy** and **Export CSV** buttons. No bulk "export all results" button (defer; multi-result CSV is its own phase if requested).
- **D-12:** WYSIWYG export — copy / CSV reflects what's currently displayed. Sections that haven't been expanded export with `"Not loaded"` markers. CSV includes a **source-attribution column** per field (e.g., `[Graph]`, `[Genesys]`, `[Genesys, not loaded]`). No auto-fetch on export click.
- **D-13:** Clipboard format is **plain text key:value lines** (e.g. `Name: Jane Doe\nDept: IT\nMFA: registered (Authenticator, SMS)\n...`). Pastes cleanly into Teams, ServiceNow, email. No markdown variant in v1.

### Carrying forward (locked from prior phases)
- **D-14:** Reuse HTMX lazy-load pattern from `app/blueprints/search/__init__.py:680` (`/api/signin-logs/<id>`) and `:706` (`/api/genesys-licenses/<id>`). New `/api/profile/<id>/<section>` endpoints follow this shape.
- **D-15:** All endpoints `@auth_required` + `@require_role("viewer")` + `audit_service.log_search()` per project conventions. No new auth or DB topology — Phase 6 ships against final Keycloak + Alembic stack (Phases 4 + 5).
- **D-16:** Tailwind + FontAwesome + Jinja fragments only. No new frontend frameworks (architecture constraint from STATE.md).

### Open for the planner
- New Graph permissions (`AuditLog.Read.All`, `UserAuthenticationMethod.Read.All`, `Organization.Read.All`) and Azure AD Premium P1 — coordinate with the Azure AD app registration owner; planner should call this out as an external dependency.
- Whether `/subscribedSkus` cache lives in a new model + service or reuses an existing pattern (genesys_cache_db is the closest analog).
- CSV/clipboard generation location: per-profile route or a dedicated export module.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 6: Enriched Profiles & Search Export" — 5 success criteria
- `.planning/REQUIREMENTS.md` §"Profile Cards" + §"Search & Export" — PROF-01..06, SRCH-01..02
- `.planning/STATE.md` §"Key Decisions Locked In" — pagination pattern, audit/role conventions inherited from Phase 1

### Codebase Maps
- `.planning/codebase/STRUCTURE.md` — directory layout, blueprint/service/model locations
- `.planning/codebase/INTEGRATIONS.md` — Graph + Genesys integration shape
- `.planning/codebase/CONVENTIONS.md` — service patterns, decorator usage

### Existing Code (reuse, do NOT redesign)
- `app/blueprints/search/__init__.py:680-718` — HTMX lazy-load pattern (`/api/signin-logs/<id>`, `/api/genesys-licenses/<id>`); copy verbatim for new `/api/profile/<id>/<section>` endpoints
- `app/services/graph_service.py:245-267` — `_get_select_fields()` (extend to include `signInActivity` and `assignedLicenses`)
- `app/services/graph_service.py:269-349` — `get_user_by_id()` + `_process_user_data()` (extend with new fields)
- `app/services/graph_service.py:391-` — `get_sign_in_logs()` (already used; keep as-is)
- `app/services/genesys_service.py:240-374` — queues/skills/presence already returned by `_process_user_data`-equivalent; PROF-03 likely needs only template work
- `app/services/genesys_cache_db.py` — daily-refresh background-cache pattern; mirror this for `subscribedSkus` (D-04)
- `app/models/employee_profiles.py` — 24h TTL profile cache (extension target for D-07)
- `app/services/result_merger.py` — graceful missing-field handling (PROF-06 likely partially complete)
- `app/templates/search/index.html` — search results template (currently 118 lines; expanded section UI added here or in a new partial)
- `app/utils/error_handler.py` — `@handle_service_errors` decorator pattern for the new endpoints

### Permission References (verify with Azure AD app reg owner)
- New Graph perms: `AuditLog.Read.All` (D-01, may already exist), `UserAuthenticationMethod.Read.All` (D-02 — new), `Organization.Read.All` (D-04 — verify)
- Tenant prerequisite: **Azure AD Premium P1** for `signInActivity` to populate (D-01)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **HTMX lazy endpoint pattern** (`/api/signin-logs/<id>`, `/api/genesys-licenses/<id>` in `app/blueprints/search/__init__.py`): `@auth_required` + role check + audit log + Jinja fragment. New `/api/profile/<id>/m365` and `/api/profile/<id>/genesys` follow this shape.
- **EmployeeProfile 24h cache** (`app/models/employee_profiles.py`): existing TTL/force-refresh button reused for new enriched fields (D-07).
- **genesys_cache_db daily refresh**: closest analog for the new `/subscribedSkus` SKU-name cache (D-04).
- **Graph service** already returns department, manager, jobTitle, employeeId, hire date, password change, account state (`_process_user_data`) — most of PROF-01's "non-license, non-sign-in" half is already done.
- **Genesys service** already returns queues, skills with proficiency, presence — PROF-03 may be largely template work.
- **result_merger** already handles missing fields → PROF-06 likely partially or fully done; verify in research.

### Established Patterns
- Server-renders Jinja fragments for HTMX endpoints (no JSON APIs for UI consumption).
- Inline HTML in `app/blueprints/search/__init__.py:1584+` — Phase 6 may want to extract a partial template to keep the new sections maintainable; planner's call.
- `g.user` for current user, `format_ip_info()` for audit IP, `audit_service.log_search()` per blueprint convention.

### Integration Points
- New endpoints: `/search/api/profile/<id>/m365`, `/search/api/profile/<id>/genesys`, `/search/api/profile/<id>/copy`, `/search/api/profile/<id>/export.csv`.
- Service additions: `graph_service.get_authentication_methods(user_id)`, `graph_service.get_license_details(user_id)`, plus `signInActivity` + `assignedLicenses` added to `_get_select_fields`.
- New model/service for SKU catalog (mirror `genesys_cache_db`).

</code_context>

<specifics>
## Specific Ideas

- Permission-degradation message format: `"Last sign-in unavailable — missing AuditLog.Read.All"` (or similar). Inline in the section, not a toast or modal.
- Source-attribution column in CSV: `department [Graph]`, `queues [Genesys, not loaded]`. Makes WYSIWYG export self-documenting.
- Clipboard format: plain text key:value lines, exemplar:
  ```
  Name: Jane Doe
  Title: Senior Analyst
  Dept: IT
  MFA: registered (Authenticator, SMS)
  Last sign-in: 2026-04-23
  ```

</specifics>

<deferred>
## Deferred Ideas

- **Multi-result / bulk CSV export** — single "Export all results" button at the top of the result list. Defer; per-profile covers the dominant workflow. Revisit if a use case emerges.
- **Markdown copy variant** — second "Copy as markdown" button. Defer until someone actually asks; plain text covers Teams + ServiceNow + email.
- **Per-service-plan license breakdown** — drill-down inside each SKU showing Exchange/Teams/SharePoint individually. Niche; defer to a future license-troubleshooting phase or fold into Phase 8 (Reporting).
- **License assignment / removal from the profile view** — write operation; belongs in Phase 9 (Write Operations).
- **Auto-fetch all sections on export click** — would give "complete" exports but adds Graph hits and surprise behavior. Reconsider only if WYSIWYG turns out to be confusing in practice.
- **Hover / intersection-observer auto-expand** — snappier UX but burns Graph calls and needs a JS layer outside the HTMX-only constraint.

</deferred>

---

*Phase: 06-enriched-profiles-search-export*
*Context gathered: 2026-04-26*
