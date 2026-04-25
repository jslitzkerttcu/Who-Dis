---
phase: 01-foundation
plan: 01
subsystem: foundation
tags: [tech-debt, refactor, asyncio, app-factory, di-container]
one_liner: "Single canonical app factory, DataWarehouseService removed, asyncio modernized"
requires: []
provides:
  - "app/__init__.py:create_app — sole canonical Flask factory"
  - "EmployeeProfilesRefreshService — owns Azure SQL Keystone query + cache wrappers"
  - "container key: employee_profiles_refresh"
affects:
  - app/__init__.py
  - app/container.py
  - app/blueprints/admin/cache.py
  - app/services/refresh_employee_profiles.py
tech-stack:
  added: []
  patterns:
    - "asyncio.get_running_loop() detection + asyncio.run() fallback"
key-files:
  created: []
  modified:
    - app/__init__.py
    - app/container.py
    - app/blueprints/admin/cache.py
    - app/services/refresh_employee_profiles.py
    - scripts/archive/migrate_configuration.py
  deleted:
    - app/app_factory.py
    - app/services/data_warehouse_service.py
decisions:
  - "Consolidated Keystone query + Azure SQL connection helpers directly into EmployeeProfilesRefreshService rather than introducing a new shared base — avoids leaving the deprecated module under a different name"
  - "Added get_cache_status / refresh_cache wrapper methods on EmployeeProfilesRefreshService to preserve the dict shapes consumed by app/blueprints/admin/cache.py admin UI routes"
  - "Bundled the single DEBT-04 asyncio.get_event_loop() fix into the Task 2 commit because it lives in the same file (refresh_employee_profiles.py) being heavily restructured — separating it would have created merge friction without value"
metrics:
  duration_seconds: 374
  tasks_completed: 3
  files_modified: 5
  files_deleted: 2
  completed_date: "2026-04-25"
requirements_satisfied: [DEBT-01, DEBT-02, DEBT-04]
---

# Phase 1 Plan 1: Debt Cleanup Summary

**One-liner:** Consolidated the duplicated `app_factory.py` into `app/__init__.py`, deleted the deprecated `DataWarehouseService` and migrated all callers to `EmployeeProfilesRefreshService`, and replaced the Python <3.10 `asyncio.get_event_loop()` idiom with `asyncio.get_running_loop()` + `asyncio.run()`.

## What Shipped

### Task 1 — DEBT-01: App factory consolidation (commit `7773991`)

- Migrated the third-party logger quieting calls (`urllib3`, `msal`, `app.services.simple_config`) from `app/app_factory.py:configure_logging()` into `app/__init__.py:create_app()` immediately after the existing `logging.basicConfig(...)`.
- Repo-wide grep for `app_factory` references found one remaining caller in `scripts/archive/migrate_configuration.py` (an archived migration script). Updated it to `from app import create_app`.
- Deleted `app/app_factory.py`.
- Smoke test: `python -c "from app import create_app; create_app()"` exits 0.

### Task 2 — DEBT-02: DataWarehouseService removal (commit `5b394ca`)

- Moved the Azure SQL configuration properties (`server`, `database`, `client_id`, `client_secret`, `connection_timeout`, `query_timeout`, `cache_refresh_hours`), `_get_connection_string()`, `test_connection()`, and `execute_keystone_query()` from `DataWarehouseService` into `EmployeeProfilesRefreshService`. The `pyodbc` import + missing-driver guard moved with them.
- Updated `load_keystone_employee_data()` to call `self.execute_keystone_query()` directly instead of importing the legacy module.
- Updated `test_data_warehouse_connection()` to call `self.test_connection()` directly.
- Added two compatibility wrapper methods on `EmployeeProfilesRefreshService`:
  - `get_cache_status()` — returns `{total_records, record_count, last_updated, refresh_status}` (the shape that `admin/cache.py::data_warehouse_cache_status` jsonifies).
  - `refresh_cache()` — runs the Keystone query, calls `refresh_all_profiles()`, and returns `{total_records, cached_records}` (the shape `admin/cache.py::refresh_data_warehouse_cache` audit-logs).
- Registered the service in the DI container under the key `employee_profiles_refresh` (factory: `lambda c: EmployeeProfilesRefreshService()`).
- Updated `app/blueprints/admin/cache.py` callers to fetch `current_app.container.get("employee_profiles_refresh")` instead of `"data_warehouse_service"`.
- Deleted `app/services/data_warehouse_service.py`.
- Smoke test: factory still creates, the new service imports cleanly.

### Task 3 — DEBT-04: Asyncio modernization

- The repo-wide grep for `asyncio.get_event_loop|asyncio.new_event_loop|asyncio.set_event_loop` returned exactly **one** match: `app/services/refresh_employee_profiles.py` line 365 (in `refresh_all_profiles`).
- Replaced the `loop = asyncio.get_event_loop(); loop.is_running()` pattern with the Python 3.10+ idiom: try `asyncio.get_running_loop()` to detect an existing loop (and fall back to sync processing if found), otherwise call `asyncio.run(coro)` directly.
- Verified post-fix: `grep -rn 'asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop' app/ scripts/` returns no matches; `asyncio.run` and `asyncio.get_running_loop` both appear in the modified file.
- Because the only occurrence sat inside the file already being heavily restructured for Task 2, the asyncio fix was bundled into the Task 2 commit (`5b394ca`). Documented as a deviation under **Deviations from Plan** below.

## Verification

Plan-level success criteria from `01-01-debt-cleanup-PLAN.md`:

| Criterion | Result |
|-----------|--------|
| `test ! -f app/app_factory.py` | PASS |
| `test ! -f app/services/data_warehouse_service.py` | PASS |
| `grep -rn "app_factory" app/ scripts/ run.py` returns no matches | PASS |
| `grep -rn "DataWarehouseService\|data_warehouse_service" app/ scripts/` returns no matches | PASS |
| `grep -n "data_warehouse" app/container.py` returns no matches | PASS |
| `grep -n "urllib3" app/__init__.py` returns at least one match | PASS |
| `grep -rn "asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop" app/ scripts/` returns no matches | PASS |
| `asyncio.run` or `asyncio.get_running_loop` appears in modified files | PASS (`refresh_employee_profiles.py`) |
| `python -c "from app import create_app; app = create_app()"` exits 0 | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] Asyncio fix bundled into Task 2 commit**

- **Found during:** Task 2.
- **Issue:** The single `asyncio.get_event_loop()` occurrence (DEBT-04 / Task 3) lives inside `refresh_employee_profiles.py`, the same file being heavily restructured for the DataWarehouseService consolidation in Task 2. Splitting it into a separate commit would have produced a hand-edited intermediate file with both the old asyncio idiom and the new dependency surface, increasing the chance of a broken intermediate revision.
- **Fix:** Applied the asyncio replacement (try `asyncio.get_running_loop()` → fall back to sync; else `asyncio.run(coro)`) inside the Task 2 commit. Plan acceptance for Task 3 was already met when the commit landed.
- **Files modified:** `app/services/refresh_employee_profiles.py`
- **Commit:** `5b394ca`

**2. [Rule 3 — Blocking] Caller in `scripts/archive/` updated**

- **Found during:** Task 1.
- **Issue:** The plan's grep target (`app/`, `scripts/`, `run.py`) included `scripts/archive/migrate_configuration.py`, which still imported `from app.app_factory import create_app`. Without this fix the acceptance grep would not return zero matches.
- **Fix:** Updated the import to `from app import create_app`. The archived script remains otherwise untouched.
- **Files modified:** `scripts/archive/migrate_configuration.py`
- **Commit:** `7773991`

## Auth Gates

None encountered.

## Threat Flags

None — no new network surfaces, auth paths, or trust boundaries introduced. Removed surface (deprecated `DataWarehouseService` module) reduces import-graph attack surface. Per the plan's threat register, `T-01-01-01` (tampering via dangling import) and `T-01-01-02` (DoS via asyncio) were mitigated by the smoke-test gate after every change.

## Known Stubs

None — no UI placeholders introduced. All wired data sources continue to flow.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | `7773991` | refactor(01-01): consolidate app factory into app/__init__.py |
| 2+3 | `5b394ca` | refactor(01-01): remove deprecated DataWarehouseService (includes DEBT-04 asyncio fix) |

## Self-Check: PASSED

- `app/app_factory.py` — confirmed deleted (`test ! -f` passes)
- `app/services/data_warehouse_service.py` — confirmed deleted
- `app/__init__.py` contains `urllib3` quieting line — confirmed
- `app/container.py` registers `employee_profiles_refresh` — confirmed
- Commit `7773991` exists in git log — confirmed
- Commit `5b394ca` exists in git log — confirmed
- `python -c "from app import create_app; create_app()"` exits 0 — confirmed
