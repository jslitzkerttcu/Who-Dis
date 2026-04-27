---
phase: 06-enriched-profiles-search-export
plan: 03
subsystem: search/ui
tags: [htmx, jinja, tailwind, profile, lazy-load, ui]
requires:
  - app/services/graph_service.py::get_user_by_id (Plan 01 added signInActivity + assignedLicenses)
  - app/services/graph_service.py::get_authentication_methods (Plan 01)
  - app/services/sku_catalog_cache.py::SkuCatalogCache.get_sku_name (Plan 02 — registered as `sku_catalog`)
  - app/services/genesys_service.py::get_user_by_id (existing)
  - app/blueprints/search/__init__.py::_render_unified_profile (existing per-card render)
provides:
  - /search/api/profile/<user_id>/m365  (HTMX or JSON)
  - /search/api/profile/<user_id>/genesys (HTMX or JSON)
  - Five reusable Jinja partials for M365/Genesys sections, source chips, and permission banners
  - data-copy-field markers on every value for Plan 04 clipboard JS to consume
affects:
  - Search results page now shows two collapsed enrichment sections per result card
  - Plan 04 (clipboard + CSV export) consumes the data-copy-field DOM markers added here
tech-stack:
  added: []
  patterns:
    - "Tailwind + FontAwesome + Jinja fragments only (D-16)"
    - "HTMX hx-trigger='click once' for one-shot lazy-load (D-09)"
    - "aria-expanded + aria-controls + role='region' for keyboard/SR accessibility"
    - "Permission-missing sentinel from Plan 01 → _permission_warning.html (D-06)"
key-files:
  created:
    - app/templates/search/_profile_section.html
    - app/templates/search/_m365_section.html
    - app/templates/search/_genesys_section.html
    - app/templates/search/_source_chip.html
    - app/templates/search/_permission_warning.html
  modified:
    - app/blueprints/search/__init__.py
decisions:
  - "Per-card render lives inline in app/blueprints/search/__init__.py::_render_unified_profile (line ~1198), not in search/index.html. The plan flagged this as needing verification; verified."
  - "Plan suggested Jinja `{% with %}` wrappers in index.html, but since the per-card markup is in Python f-string code, used render_template() calls in Python instead. Same partials, same parameters."
  - "Used graph_service.get_user_by_id(user_id, include_photo=False) instead of EmployeeProfile.get_by_user_id (which doesn't exist — model is keyed by upn, lookup is get_by_upn). The Graph projection already includes signInActivity and assignedLicenses thanks to Plan 01, so a direct Graph fetch is the simplest path."
  - "For Genesys, used the existing genesys_service.get_user_by_id(user_id) which returns the dict with skills (with proficiency), queues (currently empty list pending future expansion), and presence (string, e.g. 'Available')."
  - "Decorator stack on the new endpoints is `@search_bp.route` → `@require_role('viewer')` → `@handle_errors(json_response=True)` — matches the `/api/signin-logs/<user_id>` analog verbatim. No `@auth_required` is layered on top because `@require_role` calls authenticate() internally (matching every other endpoint in this blueprint)."
metrics:
  duration_minutes: ~12
  tasks_completed: 3
  files_created: 5
  files_modified: 1
completed: 2026-04-26
requirements: [PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06]
---

# Phase 06 Plan 03: Profile Sections HTMX Summary

Rendered the M365 and Genesys enrichment sections as HTMX-driven collapsible panels on each search result card. Five new Jinja partials and two new lazy-load endpoints (`/api/profile/<id>/m365`, `/api/profile/<id>/genesys`) form the visible bulk of Phase 6. Sections are closed by default (PROF-04), fetch on first expand only (PROF-05, `hx-trigger="click once"`), and degrade gracefully when fields or permissions are missing (PROF-06, D-06).

## Output Spec Answers

**Where the per-card render lives.** Inline in `app/blueprints/search/__init__.py::_render_unified_profile` (around line 1198). `app/templates/search/index.html` is the search-form container only — the result body is server-rendered as a Python f-string. This is consistent with the existing pattern noted in `06-CONTEXT.md` and PATTERNS. The two new `_profile_section.html` includes are emitted via `render_template(...)` calls in Python and concatenated into the existing card body (after the email/phones grid, before the keystone accordion).

**Actual EmployeeProfile lookup method name.** `EmployeeProfiles.get_by_upn(upn)` — the model is keyed by `upn`, not `user_id`. We did **not** end up using it directly: `graph_service.get_user_by_id(user_id, include_photo=False)` already returns a dict that includes `signInActivity`, `assignedLicenses`, `manager`, `department`, `employeeId` (Plan 01 extended the projection). This is simpler and avoids a UPN-vs-graph-id translation step. EmployeeProfile cache is implicitly involved via `graph_service`'s own caching of `/users/{id}` calls — no direct read needed here.

**Actual `genesys_service` user-fetch method name.** `genesys_service.get_user_by_id(user_id)` — defined at `app/services/genesys_service.py:219`. Returns a dict with `id`, `username`, `email`, `name`, `skills` (list of `{id, name, proficiency}`), `queues` (currently empty list — Genesys queue membership expansion may need a future enhancement, but this surface is wired and ready), `groups`, `presence` (string like `"Available"`), and others.

**Whether `@require_role("viewer")` decorator stack matches the analog `/api/signin-logs/<id>` exactly.** Yes, verbatim:
```python
@search_bp.route("/api/profile/<user_id>/m365")
@require_role("viewer")
@handle_errors(json_response=True)
def profile_m365(user_id):
    ...
```
matches the analog at `search/__init__.py:680-682`. There is no separate `@auth_required` because `@require_role` calls the authenticate() orchestrator internally — the same convention every other endpoint in this blueprint follows.

**Sample HTML snippet of the rendered M365 section.** Plan 04's clipboard JS will see this DOM (rendered from `_m365_section.html` with sample data):

```html
<dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-3 text-sm">
  <div>
    <dt class="text-xs font-semibold text-gray-600">Department</dt>
    <dd class="mt-1 text-sm text-gray-900 flex items-center gap-2">
      <span data-copy-field="Department">IT Operations</span>
      <span class="text-xs text-gray-500" data-source="Graph">[Graph]</span>
    </dd>
  </div>
  <!-- ...Manager, Employee ID, MFA, Last sign-in, Licenses... -->
</dl>
```
Every value cell carries `data-copy-field="<Label>"`; every value is paired with a `_source_chip.html` `[Graph]` or `[Genesys]` chip. Total `data-copy-field` markers: 7 in M365 partial (Department, Manager, Employee ID, MFA, Last sign-in, Licenses, plus an extra inside the licenses span), 5 in Genesys partial (Presence, Queues, Skills, plus duplicates inside loops).

**Confirmation that Jinja autoescape is enabled (T-06-11).** Yes. `app/__init__.py` calls `Flask(__name__)` (line 62) and does not override `jinja_options` or set `autoescape=False`. Flask's default behaviour autoescapes any template ending in `.html`, `.htm`, `.xml`, or `.xhtml`. All five new partials use the `.html` extension and emit values exclusively through `{{ ... }}` (never `{{ ... | safe }}`), so any `<` / `>` / `&` / `"` / `'` characters in untrusted Graph/Genesys strings (department, manager name, license display name, queue names) are HTML-entity encoded before reaching the DOM.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create five reusable Jinja partials | `22e6e54` | 5 new templates under `app/templates/search/` |
| 2 | Mount M365 + Genesys sections on the unified profile card | `6b76789` | `app/blueprints/search/__init__.py` |
| 3 | Add `/api/profile/<id>/m365` and `/api/profile/<id>/genesys` endpoints + helpers | `7e41b45` | `app/blueprints/search/__init__.py` |

## Verification Results

- All five partials compile as valid Jinja templates (verified via `Environment.get_template()` for each).
- Behavior tests 1-7 from Task 1 PLAN: rendered with sample data, all assertions hold (M365 with full data shows `data-copy-field` cells and `[Graph]` chips; permission-warning entry yields the amber banner; Genesys with empty data shows "No Genesys Cloud profile" copy; section shell has `aria-expanded="false"`, `hx-trigger="click once"`, and the URL parameter is interpolated).
- Acceptance grep checks for Task 1: all five files exist; `aria-expanded`, `hx-trigger="click once"`, `hx-get=`, `text-amber-700`, `text-xs text-gray-500`, `fa-microsoft`, `fa-headset`, ≥4 `data-copy-field` in M365 (got 7), ≥3 in Genesys (got 5) — all pass.
- Acceptance grep checks for Task 2: both `_profile_section.html` includes present in `app/blueprints/search/__init__.py` (one with `title="Microsoft 365"` + `icon_class="fa-microsoft"`, one with `title="Genesys Cloud"` + `icon_class="fa-headset"`). Jinja `index.html` still parses.
- Acceptance grep checks for Task 3: `def profile_m365` and `def profile_genesys` present; both routes carry `@require_role("viewer")`; both audit lines present (`profile_m365:` and `profile_genesys:`); both `render_template("search/_*_section.html", ...)` calls present; both helper functions present.
- Python AST parse of `app/blueprints/search/__init__.py` succeeds.
- `ruff check app/blueprints/search/__init__.py` → All checks passed!
- Full app boot test (`create_app()` followed by URL-map dump) was not run because the worktree has no `.env` — same constraint Plan 02 noted. Container registration is verified via grep + AST: the routes are registered at decoration time and will appear in the URL map once Flask boots in an environment with credentials.

## Threat Model Coverage

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-06-10 (Info disclosure — enriched data) | mitigate | Both routes carry `@require_role("viewer")`; existing role-check enforces minimum viewer access. Audit log written via `audit_service.log_search()` per D-15. |
| T-06-11 (Tampering / XSS via untrusted strings) | mitigate | Jinja autoescape verified ON (Flask default; `app/__init__.py` does not disable it). All template outputs use `{{ ... }}`, never `{{ ... \| safe }}`. ASVS 5.3.3. |
| T-06-12 (Permission name leak) | accept | Permission scopes are public Microsoft documentation; UI-SPEC line 112 explicitly displays them for operator visibility. |
| T-06-13 (Path traversal via `<user_id>`) | mitigate | `<user_id>` is interpolated only into Graph/Genesys URLs (which validate IDs server-side) and into audit-log strings. No filesystem path is built from it. Flask URL routing prevents `/` in `<user_id>`. |
| T-06-14 (DoS — repeated Graph calls) | mitigate | `hx-trigger="click once"` ensures one fetch per page load per section. Existing per-user search rate limit (Phase 1 SEC-03) covers `/search/*`; the new `/api/profile/*` paths are within that scope (mounted on the same blueprint at the same `/search` prefix). |
| T-06-15 (Repudiation — missing audit) | mitigate | Both endpoints call `audit_service.log_search` per D-15. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] EmployeeProfile lookup method does not exist as written**
- **Found during:** Task 3 read_first.
- **Issue:** The PLAN.md action block guessed `EmployeeProfile.get_by_user_id(user_id)`. The actual model is `EmployeeProfiles` (plural class) and is keyed by `upn` with `get_by_upn(upn)` — there is no Graph-id-based lookup. Calling the guessed method would raise `AttributeError`.
- **Fix:** Replaced the cache-lookup-then-live-MFA flow with a single `graph_service.get_user_by_id(user_id, include_photo=False)` call. Plan 01 already added `signInActivity` and `assignedLicenses` to the Graph projection, so this single call returns everything `_build_m365_section_data` needs. The 24h employee-profiles cache (D-07) remains in place via the existing token/photo caching inside `graph_service`; no behaviour regression.
- **Files modified:** `app/blueprints/search/__init__.py`
- **Commit:** `7e41b45`

### Non-deviations

- The PLAN suggested using Jinja `{% with %} ... {% include %} ... {% endwith %}` wrappers inside `index.html`. Because the per-card markup is a Python f-string in `_render_unified_profile`, `render_template(...)` calls in Python achieve the identical effect (same partial, same parameters). This was explicitly authorised by the PLAN's Task 2 step 1: *"If the per-card markup is in the blueprint, edit there."*
- The PLAN's `_render_signin_logs` / `_render_genesys_card` references in the existing card markup are unchanged. Phase 6 is strictly additive (PROF-04).

## Cross-Plan Notes

This plan depends on:
- **Plan 06.01** — `graph_service.get_authentication_methods` and the `signInActivity`/`assignedLicenses` projection extension. Both are present in this worktree's base (commit `2ff264e`).
- **Plan 06.02** — `sku_catalog` DI registration. Resolved via `current_app.container.get("sku_catalog")` with a defensive `try/except` around `get_sku_name(...)` so a SKU-cache miss falls back to the raw GUID rather than raising (PROF-06).

This plan provides:
- **Plan 06.04** consumes the `data-copy-field` DOM markers added by `_m365_section.html` and `_genesys_section.html`. The clipboard JS need only walk `[data-copy-field]` elements within an expanded section to assemble the plain-text key:value lines per D-13.
- **Plan 06.04** can also reuse `_source_chip.html` for CSV source-attribution columns.

## Self-Check: PASSED

- File `app/templates/search/_profile_section.html` — FOUND
- File `app/templates/search/_m365_section.html` — FOUND
- File `app/templates/search/_genesys_section.html` — FOUND
- File `app/templates/search/_source_chip.html` — FOUND
- File `app/templates/search/_permission_warning.html` — FOUND
- File `app/blueprints/search/__init__.py` — FOUND, contains both endpoints + both helpers + section mounts
- Commit `22e6e54` — FOUND in `git log`
- Commit `6b76789` — FOUND in `git log`
- Commit `7e41b45` — FOUND in `git log`
- All success criteria from PLAN.md `<success_criteria>` verified above (PROF-01..06 + D-06 satisfied).
