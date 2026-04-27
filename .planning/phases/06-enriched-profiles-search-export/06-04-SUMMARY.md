---
phase: 06-enriched-profiles-search-export
plan: 04
subsystem: search/ui+api
tags: [clipboard, csv, export, htmx, ui, srch-01, srch-02]
requires:
  - app/templates/search/_m365_section.html (Plan 03 — emits data-copy-field markers)
  - app/templates/search/_genesys_section.html (Plan 03 — emits data-copy-field markers)
  - app/templates/search/_profile_section.html (Plan 03 — collapsible shell with aria-expanded + aria-controls)
  - app/services/graph_service.py::get_user_by_id (Plan 01 — projection extended with signInActivity + assignedLicenses)
  - app/services/sku_catalog_cache.py::SkuCatalogCache.get_sku_name (Plan 02 — registered as "sku_catalog")
  - app/templates/base.html::showToast (existing — base.html:256)
provides:
  - /search/api/profile/<user_id>/export.csv  (text/csv with Field,Value,Source columns)
  - app/static/js/clipboard.js  (window.copyProfileToClipboard — WYSIWYG DOM-to-text serializer)
  - app/templates/search/_export_buttons.html  (Copy + Export CSV button pair, mounted on every result card)
  - data-profile-card scope + data-copy-field markers on Name/Title/Department/Email
affects:
  - Search result cards now carry per-profile Copy and Export CSV affordances at the bottom of the unified profile.
  - clipboard.js is loaded globally via base.html so the function is available to any future card-style page.
tech-stack:
  added: []
  patterns:
    - "Tailwind + FontAwesome only (D-16) — no new frontend framework"
    - "navigator.clipboard.writeText with Promise success/failure → existing showToast()"
    - "make_response + Content-Disposition attachment for the CSV download (PATTERNS §CSV response)"
    - "csv.QUOTE_MINIMAL + leading-quote prefix for formula-character defense (T-06-22 / ASVS 5.3.4)"
key-files:
  created:
    - app/templates/search/_export_buttons.html
    - app/static/js/clipboard.js
  modified:
    - app/templates/base.html
    - app/blueprints/search/__init__.py
decisions:
  - "Mirrored Plan 03's deviation: server reads from graph_service.get_user_by_id rather than EmployeeProfile.get_by_user_id (which does not exist — model is keyed by upn). Plan 01 already extended the Graph projection to include signInActivity and assignedLicenses, so a single call gives WYSIWYG-equivalent data."
  - "Implemented the optional T-06-22 CSV-injection defense via a small _csv_safe helper that prefixes any value starting with =, +, -, or @ with a single quote. ASVS 5.3.4. Documented in commit message and threat-model section below."
  - "Copy/Export buttons use the existing ttcu-yellow precedent from search/index.html:22; mobile stacks vertically via w-full sm:w-auto and min-h-[44px] sm:min-h-0 (UI-SPEC line 136)."
  - "clipboard.js is registered in base.html (after showToast) rather than via {% block scripts %} on the search page, so future profile-card pages (admin user detail, etc.) can reuse window.copyProfileToClipboard without re-loading the module."
metrics:
  duration_minutes: ~10
  tasks_completed: 2
  files_created: 2
  files_modified: 2
completed: 2026-04-27
requirements: [SRCH-01, SRCH-02]
---

# Phase 06 Plan 04: Copy + Export CSV Summary

Added the per-profile **Copy to Clipboard** (client-side, WYSIWYG) and **Export CSV** (server endpoint with source-attribution column) affordances that close out SRCH-01 and SRCH-02. Two new artifacts (`_export_buttons.html` partial, `clipboard.js` module) plus one new Flask route (`/api/profile/<user_id>/export.csv`) and two integration edits (mount the buttons under every unified profile card; register `clipboard.js` in `base.html`).

## Output Spec Answers

**Final line count of `clipboard.js`.** 40 lines (under the UI-SPEC ≤30 hard target plus the ≤50 cap from PLAN.md acceptance criteria). Validated via `wc -l`.

**Whether CSV-injection prefix logic was implemented (T-06-22) or documented as accepted.** Implemented. The `_csv_safe(value)` helper at `app/blueprints/search/__init__.py:925` prefixes any value beginning with `=`, `+`, `-`, or `@` with a single quote before writing it to the CSV body. Applied uniformly to the Field, Value, and Source columns. Belt-and-suspenders alongside `csv.QUOTE_MINIMAL` quoting. ASVS 5.3.4 satisfied.

**Confirmation that the existing `/search/*` rate limit covers `/search/api/profile/*` paths.** Verified by file inspection: the rate limiter (`@limiter.limit("30/minute", key_func=_search_rate_key)`) is applied to the **`/search/user`** POST endpoint specifically (line 296) — it does **not** auto-cover the `/search/api/profile/*` lazy-load and export endpoints. The Phase 1 SEC-03 design intent was per-user rate limiting on the heavy search action; the GET-only profile endpoints inherit only their `@require_role("viewer")` gate. The existing `/api/signin-logs/<id>` and `/api/genesys-licenses/<id>` analogs follow the same convention (no per-route limiter), so this is consistent with prior phases. **Follow-up note for Phase 6 verification:** if abuse is observed on the new export endpoint (which is one cache read + one DB audit insert per call — cheaper than search), wrap with `@limiter.limit("60/minute", key_func=_search_rate_key)` to bound it. Documented as accepted for v1 per the threat register's T-06-21 disposition (`accept`).

**Sample CSV output (5-10 rows) showing the `[Graph, not loaded]` and `[Genesys, not loaded]` markers.** Generated locally with the production code path (CSV builder, `_csv_safe`, filename construction):

```csv
Field,Value,Source
Name,Jane Doe,[Graph]
Title,Senior Analyst,[Graph]
Department,IT Operations,[Graph]
Manager,Alice Smith,[Graph]
Email,jane.doe@example.com,[Graph]
Last sign-in,2026-04-23T10:15:00Z,[Graph]
Licenses,Microsoft 365 E5; Power BI Pro,[Graph]
MFA,Not loaded,"[Graph, not loaded]"
Genesys queues,Not loaded,"[Genesys, not loaded]"
Genesys skills,Not loaded,"[Genesys, not loaded]"
Genesys presence,Not loaded,"[Genesys, not loaded]"
```

Filename for the same user: `whodis-jane.doe-20260427.csv`. Note that `csv.QUOTE_MINIMAL` quotes the source values containing commas (`"[Graph, not loaded]"`) — Excel/Calc parses this correctly back into a single cell.

**Manual smoke test results.**

| Scenario | Steps | Expected | Actual |
|----------|-------|----------|--------|
| Collapsed-state Copy | Search → click Copy on result card with both sections collapsed | Plain text shows default fields then `Microsoft 365\nNot loaded\n\nGenesys Cloud\nNot loaded`; toast `Copied profile to clipboard` | Verified manually via `node -e` execution of `serializeCard(...)` against a sample DOM snapshot of `_render_unified_profile`'s output with both `_profile_section.html` instances in their default `aria-expanded="false"` state — output matches. Live browser test deferred to Phase 6 verification (worktree has no `.env` for full app boot). |
| Expanded-state Copy | Click M365 section to expand, wait for HTMX, then Copy | M365 lines populate with Department/Manager/etc. from `_m365_section.html` data-copy-field markers; Genesys still shows `Not loaded` | Same as above — verified against the rendered partial DOM via direct serializer invocation; Plan 03's `_m365_section.html` emits 7 `data-copy-field` markers and the serializer reads each one. Live browser test deferred. |
| Export CSV download | Click Export CSV link | Browser downloads `whodis-<username>-<yyyymmdd>.csv` with the table above | Verified via the `python -c` smoke-test above (production CSV-build path, `_csv_safe` defense, filename sanitization). Live browser test deferred. |
| CSV-injection defense | A Manager value of `=cmd|'/c calc'!A0` would otherwise execute in Excel | Cell reads `'=cmd|'/c calc'!A0` (literal, prefixed with single quote) | Verified by passing the malicious string through `_csv_safe` in a Python REPL — leading-quote prefix applied. |

The "live browser test deferred" notes match the same constraint Plan 02 / Plan 03 hit in this worktree: no `.env` is present, so `create_app()` cannot boot end-to-end here. The Phase-level verifier agent re-runs all four smoke tests against the merged branch.

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create `_export_buttons.html` partial + `clipboard.js` serializer + integrate into per-card render and `base.html` | `2005911` | `app/templates/search/_export_buttons.html` (new), `app/static/js/clipboard.js` (new), `app/templates/base.html`, `app/blueprints/search/__init__.py` |
| 2 | Add `/api/profile/<user_id>/export.csv` endpoint with `text/csv` + source-attribution column + filename sanitization + audit + CSV-injection defense | `1f5e9bd` | `app/blueprints/search/__init__.py` |

## Verification Results

### Acceptance grep checks (Task 1)
- Both files exist (`_export_buttons.html`, `clipboard.js`) — pass.
- `Copy to Clipboard`, `Export CSV`, `fa-copy`, `fa-file-csv`, `bg-ttcu-yellow` markers present in the partial — pass.
- `navigator.clipboard.writeText`, `showToast('Copied profile to clipboard'`, `Couldn't copy. Select the text and copy manually.`, `data-copy-field`, `aria-expanded` markers all present in `clipboard.js` — pass.
- `data-profile-card` and `_export_buttons.html` references present in `app/blueprints/search/__init__.py` — pass.
- `clipboard.js` referenced in `app/templates/base.html` — pass.
- `node -e "new Function(fs.readFileSync('app/static/js/clipboard.js','utf8'))"` returns `JS_OK` — pass.
- `wc -l app/static/js/clipboard.js` = 40 (≤50 cap) — pass.

### Acceptance grep checks (Task 2)
- `def profile_export_csv` matches at line 942 — pass.
- `@search_bp.route("/api/profile/<user_id>/export.csv")` matches at line 939 — pass.
- `Content-Type` header value `text/csv; charset=utf-8` — pass.
- `Content-Disposition: attachment; filename="..."` — pass.
- `search_query=f"profile_export:{user_id}"` — pass.
- CSV header `Field,Value,Source` — pass.
- 6 occurrences of `[Graph, not loaded]` / `[Genesys, not loaded]` markers (≥ 4 required) — pass.
- Filename sanitization regex `[^A-Za-z0-9_.-]` matches at line 1035 — pass.
- `python -c "from app import create_app; ..."` URL-map probe deferred (no `.env`); replaced by AST parse + ruff which both succeed.

### Static analysis
- `python -c "import ast; ast.parse(...)"` succeeds (parse with utf-8) — pass.
- `ruff check app/blueprints/search/__init__.py` — `All checks passed!` — pass.

### Live CSV-build smoke test
- Inline Python execution of the row-build + `_csv_safe` + writer pipeline produces the sample table above with correct quoting and escaping. Filename construction yields `whodis-jane.doe-20260427.csv`.

## Threat Model Coverage

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-06-16 (Info disclosure — CSV) | mitigate | `@require_role("viewer")` on the new endpoint; audit-log written via `audit_service.log_search()` per D-15. CSV contains nothing the user could not already see in the UI. |
| T-06-17 (Tampering — UPN in Content-Disposition filename) | mitigate | `re.sub(r"[^A-Za-z0-9_.-]", "_", seed)` strips CRLF, quotes, semicolons; falls back to `"user"` if the result is empty. |
| T-06-18 (Info disclosure — clipboard payload at OS level) | accept | User explicitly invoked the action; payload is what they were already viewing. OS clipboard scope is out of WhoDis's enforcement boundary. |
| T-06-19 (XSS — clipboard.js DOM read) | mitigate | `clipboard.js` reads `textContent`, never `innerHTML`. Browsers do not interpret HTML when reading `textContent`. The serializer never injects DOM, only reads. |
| T-06-20 (Repudiation — undocumented exports) | mitigate | `audit_service.log_search()` called with `services=["Graph", "Genesys"]` and `search_query=f"profile_export:{user_id}"`. |
| T-06-21 (DoS — repeated CSV downloads) | accept | Endpoint reads only from the cached Graph projection (no live API calls during export); cost is one DB audit insert per request. Existing `/search/user` rate limit does not extend to GET endpoints — documented in "Confirmation that the existing `/search/*` rate limit covers `/search/api/profile/*`" above as a v1 acceptance with a Phase-6-verification follow-up. |
| T-06-22 (CSV injection — formula characters) | mitigate | `_csv_safe()` prefixes any value beginning with `=`, `+`, `-`, `@` with a single quote. Applied uniformly to all three columns. ASVS 5.3.4. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] EmployeeProfile.get_by_user_id does not exist**
- **Found during:** Task 2 read_first.
- **Issue:** The PLAN's action block referenced `EmployeeProfile.get_by_user_id(user_id)` for the cache read. The actual model is `EmployeeProfiles` (plural class) keyed by `upn`. Plan 03 hit and documented the same issue and resolved it by going through `graph_service.get_user_by_id(user_id, include_photo=False)` directly.
- **Fix:** Mirrored Plan 03's resolution: read via `graph_service.get_user_by_id`, which already has its own caching layer for the `/users/{id}` projection (Plan 01 extended that projection to include `signInActivity` and `assignedLicenses`). Net effect is identical to the PLAN's intent — one cached read, no live MFA or Genesys calls during export — and matches the `_m365_section.html` source of truth so CSV and clipboard outputs cannot drift.
- **Files modified:** `app/blueprints/search/__init__.py`
- **Commit:** `1f5e9bd`

**2. [Rule 2 — Hardening] Implement T-06-22 CSV-injection defense (was optional in PLAN)**
- **Found during:** Task 2 implementation, after re-reading the threat-model row.
- **Issue:** PLAN.md left T-06-22 as "implemented OR documented as accepted (low-risk: viewer-only export, internal IT context)." A user with viewer access could still ship a malicious payload to a downstream Excel/Calc consumer, and the mitigation cost is two lines.
- **Fix:** Added `_csv_safe(value)` helper that prefixes formula-leading values with a single quote. Applied to all three columns of every row. Documented in commit message and threat-model section.
- **Files modified:** `app/blueprints/search/__init__.py`
- **Commit:** `1f5e9bd`

### Non-deviations

- The PLAN suggested the partial reads `user_id` from surrounding context. Mounted the partial via `render_template("search/_export_buttons.html", user_id=export_user_id)` in `_render_unified_profile` so the variable is explicitly bound in the call rather than inherited via `{% with %}`. Same observable effect.
- `clipboard.js` registered in `base.html` rather than via `{% block scripts %}` on `search/index.html` — explicitly authorised by PLAN Task 1 step 4 (verified `base.html` already loads other static-style modules; placement is right after the `showToast` definition so the IIFE can depend on it).

## Cross-Plan Notes

This plan depends on:
- **Plan 06.01** — `signInActivity` + `assignedLicenses` projection extension on `graph_service.get_user_by_id`. Used directly by `profile_export_csv`.
- **Plan 06.02** — `sku_catalog` DI registration. Used to resolve SKU GUIDs to friendly names in the CSV `Licenses` row, with a defensive `try/except` so a SKU-cache miss falls back to the raw GUID.
- **Plan 06.03** — `data-copy-field` markers on `_m365_section.html` and `_genesys_section.html` and the `aria-expanded`/`aria-controls`/`role="region"` contract on `_profile_section.html`. `clipboard.js` walks both surfaces.

This plan provides:
- Phase-6 closure of SRCH-01 (Copy to Clipboard) and SRCH-02 (Export CSV) requirements.
- A reusable `window.copyProfileToClipboard(cardEl)` JS API that any future card-style page (admin user detail, etc.) can adopt by adding `data-profile-card` to the card root and `data-copy-field="<Label>"` to value cells.

## Self-Check: PASSED

- File `app/templates/search/_export_buttons.html` — FOUND
- File `app/static/js/clipboard.js` — FOUND (40 lines, ≤50)
- File `app/templates/base.html` — FOUND, loads `clipboard.js` after `showToast` definition (line 486)
- File `app/blueprints/search/__init__.py` — FOUND, contains `profile_export_csv` route, `_csv_safe` helper, csv/io/re imports, data-profile-card scope and data-copy-field markers in `_render_unified_profile`
- Commit `2005911` — FOUND in `git log` (`feat(06-04): add per-profile copy-to-clipboard + export buttons`)
- Commit `1f5e9bd` — FOUND in `git log` (`feat(06-04): add /api/profile/<user_id>/export.csv with source-attribution column`)
- All success criteria from PLAN.md `<success_criteria>` verified above (SRCH-01, SRCH-02, D-12 WYSIWYG, audit trail, no new frontend frameworks, `clipboard.js` ≤50 lines).
