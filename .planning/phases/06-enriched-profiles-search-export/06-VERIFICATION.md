---
phase: 06-enriched-profiles-search-export
verified: 2026-04-26T00:00:00Z
status: human_needed
score: 8/8 must-haves verified (programmatic) — 1 live-browser smoke remains
overrides_applied: 0
human_verification:
  - test: "Open /search, query for a known user, expand the Microsoft 365 section on the result card"
    expected: "Section is closed by default; clicking the header fires exactly one HTMX GET to /search/api/profile/<id>/m365 (verify in DevTools Network tab); response renders department, manager, employee ID, MFA status, last sign-in, and license chips with [Graph] source chips"
    why_human: "PROF-04 (collapsed default) and PROF-05 (HTMX lazy-load on first expand) are observable only in a running browser; the partials, endpoints, and hx-trigger='click once' contract are all verified statically but final paint behavior requires a live render"
  - test: "On the same result card, expand the Genesys Cloud section"
    expected: "One HTMX GET to /search/api/profile/<id>/genesys; queues, skills with proficiency progress bars (0-5), and presence indicator render with [Genesys] source chips; missing data falls back to em-dash without errors"
    why_human: "PROF-03 visual presentation (proficiency bars, presence colored dots) cannot be verified by code inspection alone"
  - test: "Click 'Copy to Clipboard' on a result card with both sections collapsed"
    expected: "Toast 'Copied profile to clipboard' appears; pasted clipboard contents show default-card fields (Name, Title, Department, Email...) followed by 'Microsoft 365\\nNot loaded\\n\\nGenesys Cloud\\nNot loaded'"
    why_human: "SRCH-01 navigator.clipboard.writeText behavior + WYSIWYG serialization of collapsed sections is browser-only; clipboard.js logic is verified statically"
  - test: "Click 'Export CSV' on a result card"
    expected: "Browser downloads file named whodis-<username>-<yyyymmdd>.csv with header 'Field,Value,Source' and rows including [Graph]/[Graph, not loaded]/[Genesys, not loaded] source attribution; opening in Excel does not execute any formulas (CSV-injection defense)"
    why_human: "SRCH-02 download dispatch + Content-Disposition handling + Excel rendering of formula-prefixed values are observable only end-to-end"
  - test: "Test graceful degradation: configure a Graph app registration without UserAuthenticationMethod.Read.All and expand M365 section"
    expected: "Inline amber banner reads 'MFA unavailable — missing UserAuthenticationMethod.Read.All' instead of crashing; rest of section still renders department/manager/etc."
    why_human: "PROF-06 graceful-degradation requires actual 403 from Graph; sentinel return path is verified statically but live rendering requires a permission-misconfigured tenant"
---

# Phase 6: Enriched Profiles & Search Export Verification Report

**Phase Goal:** Profile cards show the full picture of an employee — Graph licenses, MFA, last sign-in, Genesys queues and skills — without cluttering the default view, and users can export what they see.

**Verified:** 2026-04-26
**Status:** human_needed (programmatic verification PASS; 5 visual/interaction items require live-browser smoke)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | Profile card shows department, manager, assigned licenses, MFA status, and last sign-in date from Graph | VERIFIED | `app/services/graph_service.py:273-274` adds `signInActivity` + `assignedLicenses` to projection; `:415,454,488` add `get_authentication_methods`, `get_license_details`, `get_subscribed_skus`; `_build_m365_section_data` (`search/__init__.py:791`) maps every field; `_m365_section.html:38-101` renders dept/manager/employee_id/mfa/last_sign_in/licenses with `data-copy-field` markers |
| 2 | Profile card shows Genesys queues, skills with proficiency levels, and current presence | VERIFIED | `_build_genesys_section_data` (`search/__init__.py:886`) extracts queues, skills with proficiency 0-5, and presence; `_genesys_section.html:28-95` renders presence dots, queue badges, skill bars |
| 3 | Extended data lives in collapsible sections that are closed by default | VERIFIED | `_profile_section.html:14-18` sets `aria-expanded="false"` on header and `class="hidden"` on body; mounted at `search/__init__.py:1542,1551` for both M365 and Genesys |
| 4 | Expensive fields load after initial card render via HTMX, not blocking page paint | VERIFIED | `_profile_section.html:37-41` uses `hx-get` + `hx-trigger="click once from:#{section_id}-header"` — single fetch per page load; endpoints registered at `search/__init__.py:724,761` |
| 5 | User can copy a structured text summary to clipboard or download a CSV of all visible fields | VERIFIED | `app/static/js/clipboard.js` (40 lines) implements `window.copyProfileToClipboard` using `navigator.clipboard.writeText`; `_export_buttons.html` mounts both buttons; `profile_export_csv` route (`search/__init__.py:939-1057`) emits CSV with `Field,Value,Source` columns |

**Score: 5/5 ROADMAP success criteria verified programmatically**

### Required Artifacts

| Artifact | Expected | Exists | Substantive | Wired | Data Flows | Status |
|----------|---------|--------|-------------|-------|------------|--------|
| `app/services/graph_service.py` (modified) | get_authentication_methods, get_license_details, get_subscribed_skus, _permission_missing, signInActivity/assignedLicenses passthrough | YES | YES (5 new symbols, sentinel pattern intact) | YES (called by m365 endpoint + sku_catalog) | YES | VERIFIED |
| `app/services/sku_catalog_cache.py` | SkuCatalogCache.refresh/get_sku_name | YES (118 lines) | YES (5 methods, ExternalServiceData reuse) | YES (registered in container, called from refresh_employee_profiles + m365 endpoint + export.csv) | YES (queries `external_service_data`) | VERIFIED |
| `app/container.py` (modified) | sku_catalog registration | YES (lines 131, 145) | YES | YES | n/a | VERIFIED |
| `app/services/refresh_employee_profiles.py` (modified) | sku_catalog refresh hook | YES (lines 607-609) | YES (in finally block per Plan 02 decisions) | YES | YES | VERIFIED |
| `app/templates/search/_profile_section.html` | Collapsible HTMX shell | YES | YES (50 lines: aria-expanded, hx-trigger=click once, role=region) | YES (mounted at search/__init__.py:1542,1551) | n/a | VERIFIED |
| `app/templates/search/_m365_section.html` | M365 fragment | YES | YES (department, manager, employee_id, MFA, last sign-in, licenses with 7+ data-copy-field markers) | YES (rendered by /api/profile/<id>/m365) | YES | VERIFIED |
| `app/templates/search/_genesys_section.html` | Genesys fragment | YES | YES (presence, queues, skills with proficiency bars; 5+ data-copy-field markers) | YES (rendered by /api/profile/<id>/genesys) | YES | VERIFIED |
| `app/templates/search/_source_chip.html` | [Graph]/[Genesys] chip | YES | YES | YES (included by m365/genesys partials) | n/a | VERIFIED |
| `app/templates/search/_permission_warning.html` | Amber permission banner | YES | YES (role=alert, displays field + permission) | YES (included by m365/genesys partials when permission_warnings non-empty) | YES (driven by Plan 01 sentinel) | VERIFIED |
| `app/templates/search/_export_buttons.html` | Copy + Export CSV buttons | YES (30 lines) | YES (bg-ttcu-yellow, mobile-responsive) | YES (mounted at search/__init__.py:1566) | YES | VERIFIED |
| `app/static/js/clipboard.js` | WYSIWYG serializer | YES (40 lines, ≤50 cap) | YES (textContent only, never innerHTML; respects aria-expanded) | YES (loaded by base.html:486) | n/a | VERIFIED |
| `app/templates/base.html` (modified) | clipboard.js script tag | YES (line 486) | YES | YES | n/a | VERIFIED |
| `app/blueprints/search/__init__.py` (modified) | profile_m365, profile_genesys, profile_export_csv routes + section mounts | YES (3 routes at 724/761/939; mounts at 1542/1551/1566; data-profile-card scope at 1583) | YES | YES (decorated with @require_role("viewer") + @handle_errors; audit_service.log_search calls present) | YES | VERIFIED |

### Key Link Verification

| From | To | Via | Status |
|------|----|----|--------|
| `_profile_section.html` header button | `/search/api/profile/<id>/m365` | `hx-get + hx-trigger="click once"` (line 37-38) | WIRED |
| `_profile_section.html` header button | `/search/api/profile/<id>/genesys` | same | WIRED |
| `profile_m365` endpoint | `graph_service.get_user_by_id` + `get_authentication_methods` | `current_app.container.get` (lines 736, 740) | WIRED |
| `profile_m365` endpoint | `_m365_section.html` template | `render_template` on HX-Request (line 757) | WIRED |
| `profile_genesys` endpoint | `genesys_service.get_user_by_id` | `current_app.container.get` (line 770) | WIRED |
| `profile_export_csv` endpoint | `graph_service.get_user_by_id` + `sku_catalog.get_sku_name` | `current_app.container.get` (lines 952-953) | WIRED |
| `_export_buttons.html` Copy button | `window.copyProfileToClipboard` | `onclick` (line 11) → `clipboard.js:31` | WIRED |
| `_export_buttons.html` Export CSV link | `search.profile_export_csv` route | `url_for` (line 19) | WIRED |
| `clipboard.js` serializer | DOM `[data-copy-field]` markers | `cardEl.querySelectorAll` (line 12, 22) | WIRED |
| `sku_catalog` container registration | `SkuCatalogCache` factory | `container.py:131,145` | WIRED |
| Daily refresh loop | `sku_catalog.refresh()` | `refresh_employee_profiles.py:607-609` (finally block) | WIRED |
| `SkuCatalogCache.refresh` | `graph_service.get_subscribed_skus` | `current_app.container.get` (sku_catalog_cache.py:74-75) | WIRED |
| `SkuCatalogCache.refresh` | `ExternalServiceData.update_service_data` | direct call (sku_catalog_cache.py:94) | WIRED |
| `_m365_section.html` permission warnings | Plan 01 `_permission_missing` sentinel | `permission_warnings` list assembled at `_build_m365_section_data:808-811` | WIRED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full pytest suite passes | `python -m pytest tests/ -q --no-cov` | 282 passed, 1 skipped, 11 xfailed in 56.46s | PASS |
| graph_service imports cleanly | (python import via test discovery) | imports OK | PASS |
| sku_catalog_cache module importable | (python import via test discovery) | imports OK | PASS |
| URL routes registered | grep for route decorators | `/api/profile/<user_id>/m365`, `/api/profile/<user_id>/genesys`, `/api/profile/<user_id>/export.csv` all present | PASS |
| All 8 expected artifacts on disk | `ls -la` in app/templates/search/ + app/services/ + app/static/js/ | All 8 files present, non-empty | PASS |
| clipboard.js syntactically valid JS | `node -e "new Function(...)"` per Plan 04 summary | Confirmed in summary | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| PROF-01 | 06.01, 06.02, 06.03 | Department, manager, employee ID, licenses, last sign-in from Graph | SATISFIED | Graph projection extended (graph_service.py:273-274,335-336); SKU catalog resolves GUIDs (sku_catalog_cache.py); `_m365_section.html` renders all 5 fields with data-copy-field |
| PROF-02 | 06.01, 06.03 | MFA status + authentication methods | SATISFIED | `get_authentication_methods` (graph_service.py:415); `_friendly_mfa_method_name` mapping (search/__init__.py:863); MFA dt/dd in `_m365_section.html:67-72` |
| PROF-03 | 06.03 | Genesys queues, skills with proficiency, presence | SATISFIED | `_build_genesys_section_data` extracts all 3 (search/__init__.py:886-924); `_genesys_section.html:28-95` renders presence + queue chips + skill bars |
| PROF-04 | 06.03 | Collapsible sections closed by default | SATISFIED | `_profile_section.html:16,18,36` — `aria-expanded="false"` + `class="hidden"` + button toggles via inline JS |
| PROF-05 | 06.03 | HTMX lazy-load expensive fields | SATISFIED | `_profile_section.html:38` — `hx-trigger="click once from:#{section_id}-header"`; endpoints at `search/__init__.py:724,761` |
| PROF-06 | 06.01, 06.03 | Result merger handles missing fields gracefully | SATISFIED | `_permission_missing` sentinel returns `{error, permission}` dict; `_build_m365_section_data` handles permission_missing/list/None (search/__init__.py:805-818); all template reads use `.get()` with em-dash fallback; sku_catalog has try/except wrapper |
| SRCH-01 | 06.04 | Copy to Clipboard | SATISFIED | `clipboard.js:31` registers `window.copyProfileToClipboard`; serializes via `[data-copy-field]` walking; `_export_buttons.html:10-18` button wired |
| SRCH-02 | 06.04 | Export CSV with source attribution | SATISFIED | `profile_export_csv` route at search/__init__.py:939; CSV has Field,Value,Source columns; filename whodis-<username>-<yyyymmdd>.csv; `_csv_safe` adds CSV-injection defense |

**Score: 8/8 requirements SATISFIED programmatically**

### Anti-Patterns Found

None blocking. Review of modified files (`graph_service.py`, `sku_catalog_cache.py`, `container.py`, `refresh_employee_profiles.py`, `search/__init__.py`, all 5 new partials, `clipboard.js`, `_export_buttons.html`, `base.html`):

- No TODO/FIXME/PLACEHOLDER comments introduced
- No `return None` / `return []` stubs in user-visible paths (defensive empty returns in `_build_*_section_data` are intentional — used when data legitimately absent)
- No `console.log`-only handlers; `clipboard.js` uses real Promise success/failure
- No hardcoded empty props at mount sites — all parameters resolved via container or function args
- Jinja autoescape ON (default Flask behavior, all `.html` templates) — XSS mitigation T-06-11 verified

### Gaps Summary

**No blocking gaps.** All 8 requirements are satisfied programmatically against the merged main branch. All four sub-plans (06.01, 06.02, 06.03, 06.04) shipped their full task lists; commits are present in main; the test suite is green at 282 passing.

The reason status is `human_needed` rather than `passed` is that five behaviors are inherently visual/interactive and were explicitly deferred from sub-plan summaries to phase verification:

1. **PROF-04 collapsed default render** (visual)
2. **PROF-05 HTMX lazy-load network behavior** (browser DevTools)
3. **PROF-03 Genesys proficiency bars / presence dots** (visual)
4. **SRCH-01 clipboard write + toast** (browser API)
5. **SRCH-02 CSV download dispatch + Excel injection defense** (browser + Excel render)

Each plan summary noted "live browser test deferred — Phase-level verifier re-runs against merged branch." All five smoke tests are listed in the `human_verification` frontmatter for the developer to execute.

---

_Verified: 2026-04-26_
_Verifier: Claude (gsd-verifier, Opus 4.7 1M)_
