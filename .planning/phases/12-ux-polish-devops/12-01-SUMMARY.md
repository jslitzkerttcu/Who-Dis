---
phase: 12-ux-polish-devops
plan: 01
subsystem: search-ui
tags: [tooltip, sku, service-plans, ux]
dependency_graph:
  requires: []
  provides: [service-plan-tooltip, get_service_plans-method]
  affects: [search-profile-cards, sku-catalog-cache]
tech_stack:
  added: []
  patterns: [tailwind-group-hover-namespace, css-only-tooltip]
key_files:
  created: []
  modified:
    - app/services/sku_catalog_cache.py
    - app/blueprints/search/__init__.py
    - app/templates/search/_m365_section.html
decisions:
  - Used group/badge Tailwind namespace to isolate tooltip hover from admin remove button hover
  - 73 friendly name mappings (exceeds 30 minimum) covering E3/E5/F1/Business plans
  - CSS-only tooltip (no JavaScript) using group-hover with opacity/visibility transition
  - Skipped service_plans injection in CSV export (line 1147) since it builds flat text, not template dicts
metrics:
  duration: 3m 27s
  completed: 2026-05-19T03:56:30Z
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
---

# Phase 12 Plan 01: SKU License Service Plan Tooltip Summary

Service plan extraction from cached Graph SKU JSONB with 73-entry friendly name mapping, priority-sorted tooltip display (top 5 plans), and Tailwind CSS-only tooltip on license badges with graceful degradation.

## Tasks Completed

| Task | Name | Commit | Key Changes |
|------|------|--------|-------------|
| 1 | Add service plan extraction and humanization to SkuCatalogCache | d4e8d03 | SERVICE_PLAN_FRIENDLY_NAMES dict, _humanize_service_plan(), get_service_plans() method |
| 2 | Wire service plans into license dicts and render tooltip | 2598f60 | service_plans in license dict, Tailwind tooltip with group/badge namespace |

## Deviations from Plan

### Scope Adjustment

**1. [Rule 3 - Scope] Skipped service_plans injection in CSV export location**
- **Found during:** Task 2
- **Issue:** Plan mentioned "Find the second location where licenses are built (around line 1157 in the compare view)" but this location is the CSV export function, which builds flat text strings (e.g., "License1; License2"), not template-renderable license dicts. Service plan tooltips have no meaning in CSV output.
- **Decision:** Skipped this injection point. Only the template-rendered license dict loop (line 886-908) receives service_plans data.
- **Impact:** None -- CSV export is not affected by tooltip feature.

## Decisions Made

1. **73 friendly name mappings** -- exceeded the 30 minimum by covering the full range of E3/E5/F1/Business/Security/Compliance/Power Platform plans
2. **CSS-only tooltip** -- used Tailwind `group/badge` hover namespace with opacity/visibility transitions; no JavaScript needed for basic show/hide
3. **Priority sorting** -- 14 high-priority plans (Exchange, Teams, SharePoint, Office, Security) sort first in tooltip display
4. **Fallback humanization** -- unknown plan names get underscores replaced and trailing version suffixes (_P1, _E3, etc.) stripped before title-casing

## Verification Results

| Check | Result |
|-------|--------|
| ruff check (both Python files) | PASS |
| mypy (no new errors introduced) | PASS (pre-existing errors only) |
| role="tooltip" in template | 1 occurrence |
| group/badge in template | 1 occurrence |
| Old title attribute removed | 0 occurrences (removed) |
| aria-describedby in template | 1 occurrence |
| SERVICE_PLAN_FRIENDLY_NAMES >= 30 | 73 entries |
| _humanize_service_plan("EXCHANGE_S_ENTERPRISE") | "Exchange Online (Plan 2)" |
| _humanize_service_plan("UNKNOWN_PLAN_X") | "Unknown Plan" (humanized, not raw) |

## Self-Check: PASSED

All 3 modified files exist. Both task commits (d4e8d03, 2598f60) verified in git log.
