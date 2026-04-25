---
phase: 01-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - app/__init__.py
  - app/app_factory.py
  - app/container.py
  - app/services/data_warehouse_service.py
autonomous: true
requirements: [DEBT-01, DEBT-02, DEBT-04]
must_haves:
  truths:
    - "Application starts using only app/__init__.py:create_app() — app_factory.py does not exist"
    - "DataWarehouseService is removed and no caller imports it"
    - "Asyncio code uses get_running_loop()/asyncio.run() — no get_event_loop() calls remain"
  artifacts:
    - path: "app/__init__.py"
      provides: "Single canonical app factory with logging-quieting calls migrated from app_factory.py"
      contains: "logging.getLogger(\"urllib3\").setLevel"
    - path: "app/services/refresh_employee_profiles.py"
      provides: "Authoritative employee profile refresh (replaces DataWarehouseService callers)"
  key_links:
    - from: "app/container.py"
      to: "app/services/refresh_employee_profiles.py"
      via: "container.register"
      pattern: "register.*refresh"
    - from: "(removed)"
      to: "app/services/data_warehouse_service.py"
      via: "deleted file + no imports"
      pattern: "data_warehouse_service"
---

<objective>
Consolidate the application initialization path, delete the deprecated DataWarehouseService, and modernize asyncio usage. This plan satisfies DEBT-01, DEBT-02, DEBT-04 and clears the slate before subsequent Phase 1 plans add new wiring to `app/__init__.py`.

Purpose: Phase 1 foundation — single clean init path, no deprecated code paths, Python 3.10+ asyncio compatibility.
Output: app_factory.py deleted, DataWarehouseService deleted, asyncio patterns updated, app/__init__.py absorbs the unique logging-quieting logic from app_factory.py.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/01-foundation/01-CONTEXT.md
@.planning/phases/01-foundation/01-PATTERNS.md
@CLAUDE.md
@app/__init__.py
@app/app_factory.py
@app/container.py
@app/services/data_warehouse_service.py
@app/services/refresh_employee_profiles.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Consolidate app factory (DEBT-01) — delete app_factory.py, migrate logging-quieting</name>
  <read_first>
    - app/__init__.py (target — confirm current create_app signature)
    - app/app_factory.py (source of unique logic to migrate, then delete)
    - app/container.py (verify it calls create_app from __init__.py, not app_factory)
    - run.py (entry point — confirm it imports from app, not app.app_factory)
  </read_first>
  <action>
    Per D-01 / DEBT-01 Claude's Discretion:

    1. Read `app/app_factory.py:configure_logging()` (lines 12–22 per PATTERNS.md). Identify any logic NOT already present in `app/__init__.py`. Specifically migrate:
       - `logging.getLogger("urllib3").setLevel(logging.WARNING)` and any other third-party logger quieting calls
       - Any unique format strings or handler attachments
    2. Add the migrated quieting calls inside `app/__init__.py:create_app()` immediately after the existing `logging.basicConfig(...)` call (currently around lines 17–20 per PATTERNS.md).
    3. Run repo-wide grep for `app_factory` references (e.g. `from app.app_factory`, `import app_factory`). Update any callers to import from `app` package directly. Expected callers per CONTEXT: none in production code (container + scripts already use `app.__init__.create_app`).
    4. Delete `app/app_factory.py`.
    5. Verify `python -c "from app import create_app; create_app()"` still succeeds (smoke test).
  </action>
  <verify>
    <automated>test ! -f app/app_factory.py &amp;&amp; grep -q 'urllib3' app/__init__.py &amp;&amp; ! grep -rn 'app_factory' app/ scripts/ run.py 2&gt;/dev/null</automated>
  </verify>
  <acceptance_criteria>
    - `app/app_factory.py` does NOT exist (`test ! -f app/app_factory.py`)
    - `grep -rn "app_factory" app/ scripts/ run.py` returns NO matches
    - `grep -n "urllib3" app/__init__.py` returns at least one match (quieting logic migrated)
    - `python -c "from app import create_app; app = create_app()"` exits 0
  </acceptance_criteria>
  <done>app_factory.py deleted, all unique logic preserved in __init__.py, no broken imports.</done>
</task>

<task type="auto">
  <name>Task 2: Remove DataWarehouseService (DEBT-02)</name>
  <read_first>
    - app/services/data_warehouse_service.py (file to delete — confirm public API surface)
    - app/services/refresh_employee_profiles.py (replacement service)
    - app/container.py (find and remove `data_warehouse_service` registration)
  </read_first>
  <action>
    Per DEBT-02 Claude's Discretion:

    1. `grep -rn "data_warehouse_service\\|DataWarehouseService" app/ scripts/` to enumerate all references.
    2. For each caller (expected in container, possibly admin blueprints or scripts/refresh_employee_profiles.py):
       - If the call maps to functionality already in `EmployeeProfilesRefreshService`, replace `current_app.container.get("data_warehouse_service")` with `current_app.container.get("employee_profiles_refresh")` (or the actual key — verify by reading container.py).
       - If a caller relies on a method NOT present in EmployeeProfilesRefreshService, add the method to EmployeeProfilesRefreshService (preserve behavior) before deleting.
    3. Remove the `container.register("data_warehouse_service", ...)` line from `app/container.py:register_services()`.
    4. Delete `app/services/data_warehouse_service.py`.
    5. Smoke test: `python -c "from app import create_app; create_app()"` must succeed without import errors.
  </action>
  <verify>
    <automated>test ! -f app/services/data_warehouse_service.py &amp;&amp; ! grep -rn 'DataWarehouseService\|data_warehouse_service' app/ scripts/ 2&gt;/dev/null</automated>
  </verify>
  <acceptance_criteria>
    - `test ! -f app/services/data_warehouse_service.py`
    - `grep -rn "DataWarehouseService\|data_warehouse_service" app/ scripts/` returns NO matches
    - `grep -n "data_warehouse" app/container.py` returns NO matches
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>DataWarehouseService file deleted, container registration removed, all callers migrated to EmployeeProfilesRefreshService.</done>
</task>

<task type="auto">
  <name>Task 3: Modernize asyncio patterns (DEBT-04)</name>
  <read_first>
    - All files matching `grep -rn "asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop" app/ scripts/`
    - Python 3.10+ asyncio docs reference (use `asyncio.run()` and `asyncio.get_running_loop()`)
  </read_first>
  <action>
    Per DEBT-04 Claude's Discretion:

    1. Run `grep -rn "asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop" app/ scripts/` to locate all occurrences.
    2. For each occurrence, apply the appropriate transformation:
       - Inside an async function (already running loop): replace `asyncio.get_event_loop()` with `asyncio.get_running_loop()`.
       - At top-level synchronous entry points calling async code: replace the manual `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(coro)` pattern with `asyncio.run(coro)`.
       - Inside Flask request handlers spawning async work: keep the single-call `asyncio.run(coro)` form (Flask is sync; each call gets a fresh loop).
    3. Do NOT introduce a new event-loop-policy. Do NOT add `nest_asyncio`. The Python 3.10+ stdlib API is the target.
    4. Smoke test affected modules can still be imported.
  </action>
  <verify>
    <automated>! grep -rn 'asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop' app/ scripts/ 2&gt;/dev/null</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "asyncio.get_event_loop\|asyncio.new_event_loop\|asyncio.set_event_loop" app/ scripts/` returns NO matches
    - At least one of `asyncio.run\|asyncio.get_running_loop` appears in the modified files (verifies replacement happened, not just deletion)
    - App boots: `python -c "from app import create_app; create_app()"` exits 0
  </acceptance_criteria>
  <done>All deprecated asyncio APIs replaced with Python 3.10+ idioms.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| process startup → import graph | Removing files must not leave dangling imports that crash boot |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-01-01-01 | Tampering | app_factory.py removal | mitigate | Verify no live caller imports app_factory before deletion via repo-wide grep; smoke-test create_app() boots after change |
| T-01-01-02 | Denial of Service | asyncio refactor | mitigate | Targeted replacement only inside the matched grep set; smoke-test app boot after edits |
| T-01-01-03 | Information Disclosure | logging-quieting migration | accept | urllib3 is quieted to WARNING — same behavior as before; no new log content exposed |
</threat_model>

<verification>
- `python -c "from app import create_app; create_app()"` exits 0
- `python run.py` starts the dev server without ImportError
- No grep matches for `app_factory`, `DataWarehouseService`, `data_warehouse_service`, `asyncio.get_event_loop`, `asyncio.new_event_loop`, `asyncio.set_event_loop` across `app/`, `scripts/`, `run.py`
</verification>

<success_criteria>
DEBT-01, DEBT-02, DEBT-04 acceptance criteria from REQUIREMENTS.md are satisfied. Application starts via a single canonical factory; deprecated service is gone; asyncio idioms are Python 3.10+.
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-01-SUMMARY.md`.
</output>
