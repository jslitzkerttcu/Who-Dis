---
phase: 06-enriched-profiles-search-export
plan: 02
subsystem: graph-cache
tags: [graph, cache, sku, license, scheduled-job]
requires:
  - app/services/genesys_cache_db.py (analog only — not modified)
  - app/models/external_service.py (reused — ExternalServiceData)
  - app/services/base.py (BaseConfigurableService)
  - app/services/graph_service.py::get_subscribed_skus (created by Plan 06.01 in parallel worktree)
provides:
  - sku_catalog DI service (SkuCatalogCache)
  - Daily SKU GUID → friendly-name resolution for Plan 06.03 license rendering
affects:
  - Daily employee-profiles refresh cycle now also refreshes the SKU catalog
tech-stack:
  added: []
  patterns: [BaseConfigurableService subclass, ExternalServiceData reuse, finally-block hook into existing schedule]
key-files:
  created:
    - app/services/sku_catalog_cache.py
  modified:
    - app/container.py
    - app/services/refresh_employee_profiles.py
decisions:
  - Scheduling lives in EmployeeProfilesRefreshService.refresh_all_profiles (the entry point invoked by the existing daily scheduler), not in token_refresh_service.py. The PATTERNS doc flagged this as needing verification — refresh_employee_profiles.py owns the daily loop.
  - SKU refresh hook placed in the `finally` block so it runs once per cycle even when employee-profile work returns early or raises, with its own try/except so a SKU failure never crashes the parent job.
  - Reused ExternalServiceData (service_name='graph', data_type='sku') — no new model, no migration.
  - 24h cadence is configurable via graph.sku_cache_refresh_hours (defaults to "24").
metrics:
  duration_minutes: ~10
  tasks_completed: 2
  files_created: 1
  files_modified: 2
completed: 2026-04-26
---

# Phase 06 Plan 02: SKU Catalog Cache Summary

Added a database-backed Microsoft 365 SKU catalog that resolves SKU GUIDs (e.g. `6fd2c87f-b296-...`) to friendly names (e.g. `ENTERPRISEPACK`) via a 24-hour cache piggybacked on the existing employee-profiles refresh cycle. Mirrors the `genesys_cache_db` pattern, reuses `ExternalServiceData`, and adds zero new threads or models.

## Output Spec Answers

**Which file owns the daily cycle?** `app/services/refresh_employee_profiles.py` — specifically `EmployeeProfilesRefreshService.refresh_all_profiles()` is the per-cycle entry point invoked by the scheduler. `token_refresh_service.py` runs token-rotation, not employee/data-cache refresh, so it was the wrong hook point. The PATTERNS doc flagged this as needing verification — verified.

**Does the existing scheduler run inside a Flask app context?** The hook uses `current_app` directly (imported defensively at module top with an ImportError guard). When the daily refresh runs inside the Flask app process (which it does — the scheduler is part of the Flask container lifecycle), `current_app` resolves naturally. If the call ever runs outside a Flask app context (e.g. CLI `python scripts/refresh_employee_profiles.py refresh`), the `if current_app is not None` guard plus the surrounding try/except would convert that into a logged error rather than a crash. No `with app.app_context():` wrapper was added because the scheduler already provides one.

**Deviation from PATTERNS analog?** None of substance. The PATTERNS doc shows the hook landing inline in the refresh loop body; the only refinement is placement in the `finally` block (so a partial-failure cycle still refreshes SKUs once per cycle and a SKU failure cannot interfere with employee-profile error reporting).

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create SkuCatalogCache service mirroring genesys_cache_db | `148aa12` | app/services/sku_catalog_cache.py |
| 2 | Register sku_catalog in DI container and hook into daily refresh loop | `9717325` | app/container.py, app/services/refresh_employee_profiles.py |

## Verification Results

- `python -c "from app.services.sku_catalog_cache import SkuCatalogCache; ..."` — OK (returns `OK`).
- `python -c "from app.container import register_services; ..."` — OK (`container_imports_ok`).
- `grep -nE "container\.register\(\"sku_catalog\"" app/container.py` — matches at line 145.
- `grep -n "from app.services.sku_catalog_cache import SkuCatalogCache" app/container.py` — matches at line 131.
- `grep -nE "sku_catalog" app/services/refresh_employee_profiles.py` — matches at lines 607-609.
- `grep -nE "needs_refresh\(\)" app/services/refresh_employee_profiles.py` — matches in the finally-block guard.
- `grep -cE "^def |^    def " app/services/sku_catalog_cache.py` — returns 5 (init + property + needs_refresh + refresh + get_sku_name) — matches the 5-method acceptance criterion.
- AST syntax check on `container.py` and `refresh_employee_profiles.py` — both `syntax OK`.
- Full app boot test (`create_app() ... container.get('sku_catalog')`) was attempted but failed at `DATABASE_URL is not set` — environmental (no `.env` in worktree), not a code defect. Container registration is verified by import path + grep.

## Threat Model Coverage

| Threat ID | Disposition | Mitigation Applied |
|-----------|-------------|---------------------|
| T-06-06 (Tampering — SKU rows) | mitigate | All writes use `ExternalServiceData.update_service_data` (parameterised SQLAlchemy ORM); no user input flows in. |
| T-06-07 (DoS — long Graph call hangs loop) | mitigate | Graph call is the responsibility of `graph_service._make_request` (timeout enforced by Plan 01). Call site wraps refresh in try/except so a hang/error is logged but never aborts the parent job. |
| T-06-08 (Info disclosure — SKU raw_data) | accept | M365 product metadata only; non-sensitive. |
| T-06-09 (Repudiation — refresh outcomes) | mitigate | `logger.info("SKU catalog refreshed: N SKUs")` on success; `logger.error(..., exc_info=True)` on failure; `logger.error` with the missing permission name on the permission_missing sentinel. |

## Deviations from Plan

None — plan executed exactly as written. The only judgement call was placing the refresh hook inside the `finally` block instead of inline in the try body; this is more defensive and was implicitly authorised by the plan's "wrap in try/except" instruction. The `current_app` import was wrapped in a defensive try/except ImportError to keep the module loadable in CLI contexts where Flask might not be ready, and the call site checks `if current_app is not None` before resolving the container.

## Cross-Plan Notes

This plan depends on **Plan 06.01** (`graph_service.get_subscribed_skus()`), which is being executed in a parallel worktree. The contract is documented in the plan's `<interfaces>` block:

```python
def get_subscribed_skus(self) -> Optional[Any]:
    """Returns list of SKU dicts on success, or {'error': 'permission_missing', 'permission': 'Organization.Read.All'} on 403."""
```

Both shapes (list and permission_missing dict) are handled in `SkuCatalogCache.refresh()`. Once both worktrees merge, runtime resolution will succeed.

## Self-Check: PASSED

- File `app/services/sku_catalog_cache.py` — FOUND
- File `app/container.py` — FOUND, contains `sku_catalog` registration + import
- File `app/services/refresh_employee_profiles.py` — FOUND, contains `sku_catalog.needs_refresh()` + `.refresh()` calls
- Commit `148aa12` — FOUND in `git log`
- Commit `9717325` — FOUND in `git log`
