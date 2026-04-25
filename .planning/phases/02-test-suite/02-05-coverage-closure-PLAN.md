---
phase: 02-test-suite
plan: 05
type: execute
wave: 5
depends_on: [02-04-coverage-gate-and-docs]
gap_closure: true
files_modified:
  - tests/factories/__init__.py
  - tests/factories/job_role_mapping.py
  - tests/unit/services/test_compliance_checking_service.py
  - tests/unit/services/test_job_role_mapping_service.py
  - tests/unit/services/test_job_role_warehouse_service.py
  - tests/unit/services/test_genesys_cache_db.py
  - tests/unit/services/test_refresh_employee_profiles.py
autonomous: true
requirements: [TEST-04]
tags: [testing, coverage, gap-closure]

must_haves:
  truths:
    - "Combined statement+branch coverage on `app/services/` + `app/middleware/` is ≥60% (the `--cov-fail-under=60` gate in pyproject.toml passes)"
    - "`pytest tests/` exits 0 with the existing pyproject.toml addopts (no `--no-cov`, no `--cov-fail-under` override on the CLI)"
    - "Pre-push hook (`.githooks/pre-push` → `make test`) unblocks ordinary pushes from a clean clone — running `make test` from a fresh checkout exits 0"
    - "Each of the 5 previously zero/low-coverage service files has at least one passing pytest module under `tests/unit/services/` that exercises happy-path + at-least-one error path"
    - "No production code in `app/services/` is modified by this plan (coverage rises purely from new tests, not by deleting branches)"
    - "pyproject.toml `[tool.pytest.ini_options]` `--cov-fail-under=60` value is unchanged (gate scope per D-11 preserved)"
  artifacts:
    - path: "tests/unit/services/test_compliance_checking_service.py"
      provides: "Boundary tests for ComplianceCheckingService (closes ~50% of 202 missed stmts)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/unit/services/test_job_role_mapping_service.py"
      provides: "Boundary tests for JobRoleMappingService (closes ~50% of 137 missed stmts)"
      contains: "def test_"
      min_lines: 80
    - path: "tests/unit/services/test_job_role_warehouse_service.py"
      provides: "Boundary tests for JobRoleWarehouseService (closes ~50% of 193 missed stmts)"
      contains: "def test_"
      min_lines: 60
    - path: "tests/unit/services/test_genesys_cache_db.py"
      provides: "Boundary tests for GenesysCacheDB (closes ~50% of 225 missed stmts)"
      contains: "def test_"
      min_lines: 60
    - path: "tests/unit/services/test_refresh_employee_profiles.py"
      provides: "Boundary tests for EmployeeProfilesRefreshService (closes ~50% of 292 missed stmts)"
      contains: "def test_"
      min_lines: 60
    - path: "tests/factories/job_role_mapping.py"
      provides: "factory_boy factory for JobRoleMapping (needed by mapping/compliance tests)"
      contains: "JobRoleMappingFactory"
      min_lines: 15
  key_links:
    - from: "tests/unit/services/test_*_service.py (new)"
      to: "app/services/*.py (under test)"
      via: "Direct service instantiation + container.get OR class-direct with fakes"
      pattern: "from app.services"
    - from: "tests/unit/services/test_job_role_mapping_service.py"
      to: "tests/factories/job_role_mapping.py + tests/factories/{job_code,system_role}.py"
      via: "factory_boy fixtures driving real DB rows"
      pattern: "JobCodeFactory|SystemRoleFactory|JobRoleMappingFactory"
    - from: "tests/unit/services/test_genesys_cache_db.py"
      to: "app.services.genesys_cache_db.requests"
      via: "mocker.patch on module-imported requests symbol"
      pattern: "patch\\(.app\\.services\\.genesys_cache_db\\.requests"
    - from: "tests/unit/services/test_refresh_employee_profiles.py"
      to: "app.services.refresh_employee_profiles.pyodbc + httpx"
      via: "mocker.patch on module-imported symbols"
      pattern: "patch\\(.app\\.services\\.refresh_employee_profiles"
---

<objective>
**Gap closure for Phase 2 VERIFICATION.md.** Combined services+middleware coverage is **32.0%** today; the `--cov-fail-under=60` gate (D-11) FAILS on every `pytest tests/` and every `git push`. Five service files (~1049 missed statements) have effectively zero coverage. This plan adds boundary-style unit tests for each, lifting combined coverage above 60% so the gate flips to pass and ordinary pushes are unblocked.

Per VERIFICATION.md path (1) — preserves the 60% gate scope (D-11) without amending REQUIREMENTS.md or carving cold-path files out.

**Boundary-style means:** for each file, write ~6-10 tests covering: (a) instantiation + 1 happy path, (b) 1-2 key error / fallback paths, (c) any auth/header/config edge that's cheap to exercise. Do NOT chase per-file 100% — the gate is package-level. Closing roughly half of each file's missed statements yields combined coverage ~46%; the remaining lift comes from the side-effect coverage of modules already at 50-70% (base.py, simple_config.py, audit_service_postgres.py) which these tests will incidentally exercise via `_get_config`, `_make_request`, and similar BaseService plumbing.

Purpose: Close the single Phase 2 gap so the suite can ship without `git push --no-verify` workarounds. Without this plan, every push from main blocks on the coverage gate and the merge-protection contract from D-09 / SC #4 silently degrades to "developers always bypass."
Output: 1 new factory + 5 new test modules; combined coverage ≥60%; `pytest tests/` exits 0.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-test-suite/02-CONTEXT.md
@.planning/phases/02-test-suite/02-VERIFICATION.md
@.planning/phases/02-test-suite/02-PATTERNS.md
@.planning/phases/02-test-suite/deferred-items.md
@.planning/phases/02-test-suite/02-03-SUMMARY.md
@.planning/phases/02-test-suite/02-04-SUMMARY.md
@app/services/compliance_checking_service.py
@app/services/job_role_mapping_service.py
@app/services/job_role_warehouse_service.py
@app/services/genesys_cache_db.py
@app/services/refresh_employee_profiles.py
@app/services/base.py
@app/models/job_role_compliance.py
@tests/conftest.py
@tests/unit/conftest.py
@tests/factories/user.py
@tests/factories/job_code.py
@tests/factories/system_role.py
@tests/factories/api_token.py
@tests/unit/services/test_search_orchestrator.py
@tests/unit/services/test_ldap_service.py
@tests/unit/services/test_genesys_service.py

<interfaces>
<!-- Public methods to target on each file under test. Verify exact signatures
     by reading the source — these are extracted for orienting the executor,
     not as authoritative call signatures. -->

# app/services/compliance_checking_service.py — class ComplianceCheckingService(BaseConfigurableService)
#   _determine_violation_severity(mapping_type, compliance_status, priority=1) -> str  [pure, line ~34]
#   _determine_remediation_action(compliance_status, mapping_type=None) -> str          [pure, line ~69]
#   check_employee_compliance(employee_upn, ...)                                        [DB-driven, line ~97]
#   run_compliance_check(scope, scope_filter, started_by, ...)                          [DB-driven, line ~216]
#   get_compliance_summary(run_id=None) -> Dict                                         [DB-driven, line ~354]
#   get_employee_compliance_report(employee_upn) -> Dict                                [DB-driven, line ~451]
#   cleanup_old_compliance_data(days_to_keep=90) -> Dict[str, int]                      [DB-driven, line ~565]

# app/services/job_role_mapping_service.py — class JobRoleMappingService(BaseConfigurableService)
#   create_mapping(job_code, role_name, system_name, mapping_type="required", priority=1, ...) -> JobRoleMapping
#   update_mapping(mapping_id, ...)
#   delete_mapping(mapping_id, ...)
#   get_mappings_for_job_code(job_code, system_name=None) -> List[Dict]
#   get_mappings_for_role(role_name, system_name) -> List[Dict]
#   get_mapping_matrix(system_name=None) -> Dict
#   bulk_create_mappings(mappings, created_by) -> Dict
#   export_mappings_csv(...) -> str
#   import_mappings_csv(csv_text, ...) -> Dict
#   get_statistics() -> Dict

# app/services/job_role_warehouse_service.py — class JobRoleWarehouseService(BaseAPIService)
#   pyodbc may be None; service must degrade gracefully.
#   _get_connection_string() -> str          [string composition, no IO]
#   test_connection() -> bool                [opens pyodbc connection — mock pyodbc.connect]
#   sync_job_codes() -> Dict[str, int]       [warehouse query → JobCode upsert]
#   sync_keystone_roles() -> Dict[str, int]
#   sync_employee_keystone_assignments() -> Dict[str, int]
#   get_expected_roles_mapping() -> Dict[str, List[str]]
#   sync_all_compliance_data() -> Dict[str, Any]

# app/services/genesys_cache_db.py — class GenesysCacheDB(BaseCacheService)
#   uses module-level `import requests`. Patch `app.services.genesys_cache_db.requests`.
#   _get_access_token() -> Optional[str]                        [DB lookup via ApiToken.get_token]
#   needs_refresh(last_update=None) -> bool                     [pure date math]
#   refresh_all_caches(genesys_service=None) -> Dict[str, int]  [orchestrates _refresh_groups/_skills/_locations]
#   _refresh_groups(token) -> int                               [HTTP GET via requests + DB upsert into ExternalServiceData]
#   _refresh_skills(token) -> int                               [same shape]
#   _refresh_locations(token) -> int                            [same shape]
#   get_group_name(group_id) -> Optional[str]                   [DB read]
#   get_skill_name(skill_id) -> Optional[str]                   [DB read]
#   get_location_info(location_id) -> Optional[Dict]            [DB read]
#   get_cache_status() -> Dict                                  [DB aggregate]

# app/services/refresh_employee_profiles.py — class EmployeeProfilesRefreshService(BaseConfigurableService)
#   pyodbc and httpx may be None — degrade gracefully.
#   _get_connection_string() -> str
#   test_connection() -> bool
#   execute_keystone_query() -> List[Dict]
#   load_keystone_employee_data() -> List[Dict]                  [calls execute_keystone_query, returns _get_fallback_mock_data on error]
#   _get_fallback_mock_data() -> List[Dict]                      [pure, returns canned data]
#   _get_user_photo_sync(upn) -> Optional[bytes]                 [httpx call — mock or assert None when httpx is None]
#   _mock_photo_bytes() -> bytes                                 [pure]
#   refresh_all_profiles() -> Dict[str, Any]                     [orchestrator — heavy, mock everything]
#   get_employee_profile(upn) -> Optional[Dict]                  [DB read on EmployeeProfiles]
#   get_cache_stats() -> Dict
#   test_data_warehouse_connection() -> Dict
#   get_cache_status() -> Dict

# Required factory shape (new) — tests/factories/job_role_mapping.py
#   class JobRoleMappingFactory(SQLAlchemyModelFactory):
#       Meta.model = JobRoleMapping
#       job_code_id = factory.SubFactory(JobCodeFactory)  -> .id
#       system_role_id = factory.SubFactory(SystemRoleFactory)  -> .id
#       mapping_type = "required"
#       priority = 1
#       created_by = "test-suite"
#   (effective_date defaults to date.today via model default; expiration_date default None)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: JobRoleMapping factory + JobRoleMappingService boundary tests</name>
  <files>tests/factories/__init__.py, tests/factories/job_role_mapping.py, tests/unit/services/test_job_role_mapping_service.py</files>
  <read_first>
    - app/services/job_role_mapping_service.py (full file — confirm exact signatures of create_mapping, update_mapping, delete_mapping, get_mapping_matrix, bulk_create_mappings, get_statistics)
    - app/models/job_role_compliance.py (lines 149-260 — JobRoleMapping schema; lines 244-260 JobRoleMappingHistory; verify required NOT-NULL columns: job_code_id, system_role_id, mapping_type, created_by)
    - tests/factories/user.py (factory_boy SQLAlchemyModelFactory pattern)
    - tests/factories/job_code.py (subfactory pattern + sequence)
    - tests/factories/system_role.py (unique-tuple pattern)
    - tests/unit/services/test_ldap_service.py (analog test layout — pytestmark, fixtures, marker usage)
    - tests/conftest.py (db_session, container_reset fixtures)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"tests/factories/*", §"Configuration Access", §"Container Override")
  </read_first>
  <behavior>
    **`tests/factories/job_role_mapping.py` (new):**
    - `JobRoleMappingFactory` extends `SQLAlchemyModelFactory` with `Meta.model = JobRoleMapping`, `sqlalchemy_session = db.session`, `sqlalchemy_session_persistence = "flush"`
    - `job_code_id` via `factory.SubFactory(JobCodeFactory)` chained through `.id` post-flush — use `factory.LazyAttribute` if SubFactory chaining is awkward; alternatively write a `@factory.post_generation` to set the FK. Confirm with executor's read of factory_boy docs / existing patterns.
    - `system_role_id` similarly via `SystemRoleFactory`
    - `mapping_type` default `"required"` (model accepts "required"/"optional"/"prohibited" per line 163)
    - `priority` default `1`
    - `created_by` default `"test-suite"` (NOT NULL per line 170)

    **`tests/factories/__init__.py` (new, empty)** — present so the directory is an importable package; existing factories already work without it but the new file should ship one for consistency.

    **`test_job_role_mapping_service.py` cases (target 8-10 tests):**
    - `test_create_mapping_happy_path` — Pre-create a JobCode + SystemRole via factories; call `service.create_mapping(job_code=jc.job_code, role_name=sr.role_name, system_name=sr.system_name)`; assert returned object is JobRoleMapping with `mapping_type="required"`, `priority=1`, FK ids match, history row exists
    - `test_create_mapping_with_explicit_overrides` — pass `mapping_type="prohibited"`, `priority=5`, `notes="x"`; assert all values reflected
    - `test_create_mapping_unknown_job_code_raises` — call with job_code that doesn't exist; assert ValueError or similar (verify exact behavior by reading source)
    - `test_update_mapping_changes_fields_and_writes_history` — create via factory, call `update_mapping(mapping.id, mapping_type="optional", changed_by="x")`; assert mapping mutated AND a JobRoleMappingHistory row appears with `change_type="updated"` (or whatever the source emits)
    - `test_delete_mapping_writes_history` — create via factory, call `delete_mapping(mapping.id, deleted_by="x")`; assert mapping no longer queryable + history row with `change_type="deleted"`
    - `test_get_mappings_for_job_code` — seed 3 mappings on same job_code; call `get_mappings_for_job_code(jc.job_code)`; assert returns 3, all priority-sorted (or whatever the source promises)
    - `test_get_mapping_matrix_filters_by_system` — seed mappings across 2 system_names; call `get_mapping_matrix(system_name="ad_groups")`; assert only ad_groups mappings returned
    - `test_bulk_create_mappings_partial_failure` — pass list of 3 dicts where 1 references unknown job_code; assert returned dict has `created` count + `errors` list
    - `test_get_statistics_counts_by_mapping_type` — seed mappings, assert `get_statistics()` returns dict with totals broken down

    Skip CSV import/export tests (export_mappings_csv / import_mappings_csv) for this plan unless the executor finds the implementation is already 50%+ covered by other tests — if so, add 1 happy-path round-trip.
  </behavior>
  <action>
    1. Create `tests/factories/__init__.py` as an empty file (`""` content).

    2. Create `tests/factories/job_role_mapping.py`:
       ```python
       """factory_boy factory for JobRoleMapping.

       Uses SubFactory to auto-create JobCode + SystemRole rows. Tests that need
       to control those parents should pass `job_code_id=...` / `system_role_id=...`
       explicitly to bypass the SubFactory.
       """
       import factory
       from factory.alchemy import SQLAlchemyModelFactory
       from app.database import db
       from app.models.job_role_compliance import JobRoleMapping
       from tests.factories.job_code import JobCodeFactory
       from tests.factories.system_role import SystemRoleFactory


       class JobRoleMappingFactory(SQLAlchemyModelFactory):
           class Meta:
               model = JobRoleMapping
               sqlalchemy_session = db.session
               sqlalchemy_session_persistence = "flush"

           job_code = factory.SubFactory(JobCodeFactory)
           system_role = factory.SubFactory(SystemRoleFactory)
           mapping_type = "required"
           priority = 1
           created_by = "test-suite"
       ```

       NOTE: If `JobRoleMapping` exposes ORM relationships `job_code` / `system_role` that auto-resolve to FK ids on flush, the relationship-style fields shown above are simpler than `job_code_id`/`system_role_id` LazyAttributes. Confirm by reading `app/models/job_role_compliance.py:149-180` for `db.relationship(...)` declarations. If only `*_id` columns exist (no relationship), switch to:
       ```python
       job_code_id = factory.LazyAttribute(lambda o: JobCodeFactory().id)
       system_role_id = factory.LazyAttribute(lambda o: SystemRoleFactory().id)
       ```

    3. Create `tests/unit/services/test_job_role_mapping_service.py`:
       - Top of file: `import pytest`; `pytestmark = pytest.mark.unit` (module-level marker).
       - Use the existing `db_session`, `container_reset`, and `app` fixtures from `tests/conftest.py`.
       - Instantiate the service via `JobRoleMappingService()` directly (no container registration needed — service is config-driven and reads from DB).
       - For each test, build prerequisites with the new factory + existing JobCodeFactory/SystemRoleFactory.
       - Use `pytest-mock` for any patches (do NOT use `unittest.mock` directly — see Plan 02-03 acceptance criteria § "from unittest").
       - Assert on persisted state (`db.session.query(JobRoleMapping).filter_by(...).first()`) AND on returned values — both directions.
       - For history-row assertions, query `JobRoleMappingHistory` (model in `app/models/job_role_compliance.py:244+`).

    Conform to Plan 02-03's style: `@pytest.mark.unit` per test (or module-level via `pytestmark`); no `mocker.patch("app.services.configuration_service.config_get")`; no `unittest.mock`.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_job_role_mapping_service.py -v --no-cov 2>&amp;1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - `tests/factories/__init__.py`, `tests/factories/job_role_mapping.py`, `tests/unit/services/test_job_role_mapping_service.py` all exist.
    - `pytest tests/unit/services/test_job_role_mapping_service.py -v --no-cov` reports ≥8 tests collected, all PASS.
    - `grep -c "JobRoleMappingFactory" tests/factories/job_role_mapping.py` returns ≥1.
    - `grep -c "pytestmark = pytest.mark.unit" tests/unit/services/test_job_role_mapping_service.py` returns 1 OR `grep -c "@pytest.mark.unit" tests/unit/services/test_job_role_mapping_service.py` returns ≥8.
    - `grep -rE "from unittest" tests/unit/services/test_job_role_mapping_service.py` returns 0.
    - `grep -rE "patch\(.*config_get" tests/unit/services/test_job_role_mapping_service.py` returns 0.
    - Per-file coverage check: `pytest tests/unit/services/test_job_role_mapping_service.py --cov=app.services.job_role_mapping_service --cov-report=term --no-cov-on-fail 2>&1 | grep -E "^app[/\\\\]services[/\\\\]job_role_mapping_service.py"` shows coverage ≥50% (was 13.3%).
    - `ruff check tests/unit/services/test_job_role_mapping_service.py tests/factories/job_role_mapping.py` clean.
  </acceptance_criteria>
  <done>JobRoleMappingFactory shipped + 8+ unit tests passing against real DB; per-file coverage on job_role_mapping_service.py ≥50%.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: ComplianceCheckingService boundary tests (highest-leverage file — 202 missed stmts)</name>
  <files>tests/unit/services/test_compliance_checking_service.py</files>
  <read_first>
    - app/services/compliance_checking_service.py (full file 565L — focus on _determine_violation_severity / _determine_remediation_action [pure helpers], check_employee_compliance, run_compliance_check, get_compliance_summary, cleanup_old_compliance_data)
    - app/models/job_role_compliance.py (lines 305-456 ComplianceCheckRun + ComplianceCheck schemas; lines 457+ EmployeeRoleAssignment)
    - app/models/employee_profiles.py (EmployeeProfiles columns — needed for _get_employees_for_scope)
    - tests/factories/job_code.py, tests/factories/system_role.py
    - tests/factories/job_role_mapping.py (created in Task 1)
    - tests/unit/services/test_search_orchestrator.py (analog — orchestrator-style boundary tests)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"Configuration Access" — write Configuration rows, do NOT patch config_get)
  </read_first>
  <behavior>
    **Target ~10 tests covering the 202 missed statements. Prioritize PURE helpers first (cheap coverage), then DB-driven methods (slower but high impact):**

    **Pure helpers (no DB, fast):**
    - `test_determine_violation_severity_compliant_returns_low` — call with `compliance_status="compliant"`, any priority; assert `"low"`
    - `test_determine_violation_severity_prohibited_priority_3_returns_critical` — `("required", "has_prohibited", priority=3)` → `"critical"`
    - `test_determine_violation_severity_prohibited_priority_1_returns_high` — `("required", "has_prohibited", priority=1)` → `"high"`
    - `test_determine_violation_severity_missing_required_priority_5` → `"critical"`
    - `test_determine_violation_severity_unexpected_role_low_priority` → `"low"`
    - `test_determine_violation_severity_default_branch` — pass an unrecognized status → `"medium"`
    - `test_determine_remediation_action_returns_string` — happy path coverage of the helper at line ~69

    **DB-driven (factories + db_session fixture):**
    - `test_check_employee_compliance_no_assignments_returns_no_violations` — seed an EmployeeProfiles row + JobCode but no JobRoleMapping; call `check_employee_compliance(employee_upn)`; assert returned dict has `compliant=True` (or whatever the source emits) — verify exact return shape by reading source
    - `test_check_employee_compliance_missing_required_role_creates_violation` — seed JobCode + SystemRole + JobRoleMapping(required) + EmployeeRoleAssignment with the role MISSING; call check; assert returned dict reports a `missing_required` violation
    - `test_run_compliance_check_creates_run_row` — call `run_compliance_check(scope="all", started_by="test")`; assert a `ComplianceCheckRun` row exists with the returned `run_id`, status reflects completion
    - `test_get_compliance_summary_with_run_id` — pre-seed a `ComplianceCheckRun` + 2 `ComplianceCheck` rows (1 compliant, 1 violation) via direct ORM; call `get_compliance_summary(run_id)`; assert dict counts match
    - `test_cleanup_old_compliance_data_deletes_old_rows` — pre-seed an old `ComplianceCheckRun` (created_at = now - 100 days) + recent run; call `cleanup_old_compliance_data(days_to_keep=90)`; assert old run deleted, recent retained, returned dict has `deleted_count >= 1`

    **Skip** `get_employee_compliance_report` and `schedule_compliance_check` for this plan unless reading the source reveals they're trivial — they're listed as deferrable in the source-audit footnote.
  </behavior>
  <action>
    Create `tests/unit/services/test_compliance_checking_service.py`. Top of file:
    ```python
    """Boundary tests for ComplianceCheckingService (Plan 02-05 gap closure for VERIFICATION.md).

    202 missed statements at start; this module targets ~50% coverage via 7 pure-helper tests
    + 5 DB-driven tests. Pure helpers are the cheap wins; the run/check methods exercise the
    full ORM round-trip without HTTP mocks.
    """
    import pytest
    from datetime import datetime, timezone, timedelta

    from app.services.compliance_checking_service import ComplianceCheckingService
    from app.models.job_role_compliance import (
        JobCode, SystemRole, JobRoleMapping, ComplianceCheck, ComplianceCheckRun,
        EmployeeRoleAssignment,
    )
    from app.models.employee_profiles import EmployeeProfiles
    from tests.factories.job_code import JobCodeFactory
    from tests.factories.system_role import SystemRoleFactory
    from tests.factories.job_role_mapping import JobRoleMappingFactory

    pytestmark = pytest.mark.unit
    ```

    For pure helpers, instantiate the service once at module scope or in a fixture:
    ```python
    @pytest.fixture
    def svc(app, db_session):
        return ComplianceCheckingService()
    ```
    (Pulling in `app` + `db_session` ensures Flask context is established for any internal `current_app` access in BaseConfigurableService.)

    For pure-helper tests, DO NOT touch the DB:
    ```python
    def test_determine_violation_severity_compliant_returns_low(svc):
        assert svc._determine_violation_severity("required", "compliant", priority=5) == "low"
    ```

    For DB-driven tests, build the prerequisite chain via factories:
    ```python
    def test_check_employee_compliance_missing_required_role_creates_violation(svc, db_session):
        jc = JobCodeFactory(job_code="ENG-1", job_title="Engineer")
        sr = SystemRoleFactory(role_name="admin", system_name="ad_groups", role_type="security_group")
        JobRoleMappingFactory(job_code=jc, system_role=sr, mapping_type="required", priority=3)
        # Seed EmployeeProfiles with this job code, NO assignment row.
        emp = EmployeeProfiles(upn="alice@example.com", job_code="ENG-1", ...)  # verify required NOT-NULL columns
        db_session.add(emp)
        db_session.commit()

        result = svc.check_employee_compliance("alice@example.com")
        # assert based on actual return shape — read the source method
        assert result is not None
    ```

    **CRITICAL — verify return shape against source:** the executor MUST read `compliance_checking_service.py` lines 97-215 (check_employee_compliance) and 216-317 (run_compliance_check) before writing the assertions. Test names + intent above are durable; the exact `result["..."]` field accesses depend on the source.

    **For `cleanup_old_compliance_data`** — `created_at` is a TimestampMixin column with `default=lambda: datetime.now(timezone.utc)`. Override post-creation with explicit `created_at=datetime.now(timezone.utc) - timedelta(days=100)` to simulate old rows; then commit, then call cleanup.

    **DO NOT** patch `app.services.configuration_service.config_get`. If a test needs config (`job_role_compliance.*` keys), write rows to the `Configuration` table directly via the encryption service or use `service._config_cache["job_role_compliance.<key>"] = value` for the specific test (the latter is the documented workaround in `deferred-items.md` for the simple_config bug — same precedent).

    **Pre-existing production bugs** — if any test surfaces the `simple_config` table mismatch or other documented bugs from `deferred-items.md`, mark with `@pytest.mark.xfail(strict=True, reason="...")` matching the pattern in `tests/integration/test_search_flow.py`.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_compliance_checking_service.py -v --no-cov 2>&amp;1 | tail -30</automated>
  </verify>
  <acceptance_criteria>
    - File `tests/unit/services/test_compliance_checking_service.py` exists.
    - `pytest tests/unit/services/test_compliance_checking_service.py -v --no-cov` reports ≥10 tests collected, all PASS or xfail-strict.
    - `grep -c "def test_" tests/unit/services/test_compliance_checking_service.py` returns ≥10.
    - `grep -c "_determine_violation_severity" tests/unit/services/test_compliance_checking_service.py` returns ≥6 (pure-helper tests present).
    - `grep -rE "patch\(.*config_get" tests/unit/services/test_compliance_checking_service.py` returns 0.
    - `grep -rE "from unittest" tests/unit/services/test_compliance_checking_service.py` returns 0.
    - Per-file coverage check: `pytest tests/unit/services/test_compliance_checking_service.py --cov=app.services.compliance_checking_service --cov-report=term --no-cov-on-fail 2>&1 | grep -E "compliance_checking_service.py"` shows coverage ≥50% (was 0.0%).
    - `ruff check tests/unit/services/test_compliance_checking_service.py` clean.
  </acceptance_criteria>
  <done>10+ unit tests covering both pure helpers and DB-driven methods; per-file coverage on compliance_checking_service.py ≥50% (was 0%).</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: GenesysCacheDB + EmployeeProfilesRefreshService boundary tests (HTTP/pyodbc-mocked)</name>
  <files>tests/unit/services/test_genesys_cache_db.py, tests/unit/services/test_refresh_employee_profiles.py</files>
  <read_first>
    - app/services/genesys_cache_db.py (full file — confirm `import requests` is at module top; confirm method signatures for needs_refresh, refresh_all_caches, _refresh_groups, _refresh_skills, _refresh_locations, get_group_name, get_skill_name, get_location_info, get_cache_status; verify ExternalServiceData usage)
    - app/services/refresh_employee_profiles.py (full file — confirm pyodbc/httpx try-except imports; confirm signatures for test_connection, execute_keystone_query, _get_fallback_mock_data, _mock_photo_bytes, get_employee_profile, get_cache_stats, test_data_warehouse_connection)
    - app/models/external_service.py (ExternalServiceData schema — for genesys_cache_db assertions)
    - app/models/employee_profiles.py (EmployeeProfiles required columns — for refresh_employee_profiles tests)
    - app/models/api_token.py (ApiToken.get_token / is_expired — needed for genesys_cache_db._get_access_token tests; NOTE per deferred-items.md: ApiToken.is_expired is a method-not-property bug — tests must `mocker.patch.object(ApiToken, "get_token", ...)` rather than rely on `is_expired` evaluation)
    - tests/unit/services/test_genesys_service.py (analog — uses `mocker.patch("app.services.base.requests.request", ...)`; this task patches at a different module path)
    - tests/unit/services/test_ldap_service.py (analog for boundary mocking style)
  </read_first>
  <behavior>
    **`test_genesys_cache_db.py` (target 7-9 tests; closes ~50% of 225 missed stmts):**
    - `test_needs_refresh_first_time_returns_true` — pass `last_update=None`; assert True
    - `test_needs_refresh_recent_update_returns_false` — pass `last_update=datetime.now(timezone.utc)`; assert False
    - `test_needs_refresh_stale_update_returns_true` — pass `last_update = now - 7 hours` (default refresh period is 6h); assert True
    - `test_get_access_token_returns_none_when_no_token_row` — empty `api_tokens` table; assert `_get_access_token() is None`
    - `test_get_access_token_returns_none_when_expired` — pre-seed an expired `ApiToken` (use ApiTokenFactory with `expires_at=now - 1 hour`); patch `ApiToken.get_token` to return the row directly OR rely on the model getter — verify which is reachable; assert `_get_access_token()` returns None for expired (workaround per deferred-items.md if needed)
    - `test_refresh_groups_writes_external_service_data` — `mocker.patch("app.services.genesys_cache_db.requests")` to return a mock with `.get(...).json()` returning `{"entities": [{"id": "g1", "name": "Sales"}], "pageCount": 1}` (verify Genesys pagination shape from `_refresh_groups` source); call `service._refresh_groups("fake-token")`; assert ≥1 ExternalServiceData row exists with the group; assert returned int ≥1
    - `test_refresh_groups_handles_http_error` — mock requests to raise or return status 500; assert method returns 0 and does NOT raise
    - `test_get_group_name_reads_from_external_service_data` — pre-seed an ExternalServiceData row for service="genesys", entity_type="group", external_id="g1", data={"name": "Sales"}; assert `get_group_name("g1") == "Sales"`
    - `test_get_cache_status_aggregates_counts` — pre-seed mixed groups/skills/locations rows; assert returned dict has counts per type

    **`test_refresh_employee_profiles.py` (target 6-8 tests; closes ~50% of 292 missed stmts):**
    - `test_mock_photo_bytes_returns_bytes` — pure helper, assert `isinstance(result, bytes)` and length > 0
    - `test_get_fallback_mock_data_returns_list` — pure helper, assert returned list non-empty + dicts contain expected keys (verify by reading source)
    - `test_get_connection_string_when_pyodbc_present` — patch `app.services.refresh_employee_profiles.pyodbc` to a non-None object; instantiate service; assert `_get_connection_string()` returns a non-empty string with server/database substrings
    - `test_test_connection_returns_false_when_pyodbc_none` — `mocker.patch("app.services.refresh_employee_profiles.pyodbc", None)`; assert `service.test_connection() is False`
    - `test_test_connection_happy_path_with_mocked_connect` — pyodbc not None; `mocker.patch("app.services.refresh_employee_profiles.pyodbc.connect")` returns mock cursor; assert `test_connection() is True`
    - `test_load_keystone_employee_data_falls_back_on_error` — patch `service.execute_keystone_query` to raise; assert `load_keystone_employee_data()` returns `_get_fallback_mock_data()` result (non-empty list, no exception escapes)
    - `test_get_employee_profile_returns_none_for_missing_upn` — empty EmployeeProfiles table; assert `get_employee_profile("nobody@example.com") is None`
    - `test_get_employee_profile_returns_dict_for_existing_upn` — seed EmployeeProfiles row directly via ORM; assert returned dict contains `upn` field
    - `test_get_cache_stats_returns_dict_with_count` — seed 2 EmployeeProfiles rows; assert `get_cache_stats()` returns dict with `total >= 2` (verify exact key by reading source)
  </behavior>
  <action>
    Create both test modules. Top of each:
    ```python
    """Boundary tests for <Service> (Plan 02-05 gap closure)."""
    import pytest
    pytestmark = pytest.mark.unit
    ```

    **For `test_genesys_cache_db.py`:**
    - Patch `requests` at `app.services.genesys_cache_db.requests` (the module-level import, NOT `app.services.base.requests` — this service uses its own `import requests` per source line 3).
    - For ExternalServiceData seeding, use direct ORM (no factory exists for it; one would be a new artifact for a future plan):
      ```python
      from app.models.external_service import ExternalServiceData
      esd = ExternalServiceData(service="genesys", entity_type="group",
                                  external_id="g1", data={"name": "Sales"})
      db_session.add(esd)
      db_session.commit()
      ```
      Verify exact column names by reading `app/models/external_service.py` BEFORE writing the test.
    - For ApiToken expired-token test: per `deferred-items.md` ApiToken.is_expired is a method, not a property — if the assertion relies on the broken behavior, mark `@pytest.mark.xfail(strict=True, reason="ApiToken.is_expired bug — see deferred-items.md")`. Otherwise patch `mocker.patch.object(ApiToken, "get_token", return_value=None)` to bypass.
    - The `_refresh_groups` HTTP shape MUST be verified against the source — Genesys uses cursor-paginated responses; the mock has to satisfy whatever `pageCount` / `nextUri` logic the method uses, OR the test should set up the mock to return only one page (`pageCount=1`).

    **For `test_refresh_employee_profiles.py`:**
    - Patch `pyodbc` and `httpx` at `app.services.refresh_employee_profiles.<module-symbol>`. Both are imported via try/except and may already be None in the test env — check with `print(refresh_employee_profiles.pyodbc)` once at the top of investigation.
    - For pyodbc.connect mocking, follow this pattern:
      ```python
      mock_cursor = mocker.MagicMock()
      mock_cursor.fetchall.return_value = []
      mock_conn = mocker.MagicMock()
      mock_conn.cursor.return_value = mock_cursor
      mocker.patch("app.services.refresh_employee_profiles.pyodbc.connect", return_value=mock_conn)
      ```
    - DO NOT mock the entire async `refresh_all_profiles` orchestrator in this plan — it's heavyweight (asyncio.gather + httpx.AsyncClient + concurrent semaphore) and exercising it requires too much setup for the coverage gain. Stick to the synchronous methods.
    - DO NOT call any method that hits real Azure SQL or real Graph — every external IO must be mocked.

    Use `db_session` and `app` fixtures from `tests/conftest.py` for tests that touch the DB. Use `mocker` from `pytest-mock` for all patches. NO `unittest.mock` imports.
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_genesys_cache_db.py tests/unit/services/test_refresh_employee_profiles.py -v --no-cov 2>&amp;1 | tail -40</automated>
  </verify>
  <acceptance_criteria>
    - Both files exist.
    - `pytest tests/unit/services/test_genesys_cache_db.py -v --no-cov` reports ≥7 tests, all PASS or xfail-strict.
    - `pytest tests/unit/services/test_refresh_employee_profiles.py -v --no-cov` reports ≥7 tests, all PASS.
    - `grep -c "patch\(.app\.services\.genesys_cache_db\.requests" tests/unit/services/test_genesys_cache_db.py` returns ≥1 (correct module-path patching).
    - `grep -c "patch\(.app\.services\.refresh_employee_profiles" tests/unit/services/test_refresh_employee_profiles.py` returns ≥2 (pyodbc + httpx or pyodbc + pyodbc.connect).
    - `grep -rE "from unittest" tests/unit/services/test_genesys_cache_db.py tests/unit/services/test_refresh_employee_profiles.py` returns 0.
    - Per-file coverage: `pytest tests/unit/services/test_genesys_cache_db.py --cov=app.services.genesys_cache_db --cov-report=term --no-cov-on-fail` shows coverage ≥45% (was 11.9%).
    - Per-file coverage: `pytest tests/unit/services/test_refresh_employee_profiles.py --cov=app.services.refresh_employee_profiles --cov-report=term --no-cov-on-fail` shows coverage ≥40% (was 16.4%).
    - `ruff check tests/unit/services/test_genesys_cache_db.py tests/unit/services/test_refresh_employee_profiles.py` clean.
    - No real network calls — verifiable by running with `pytest tests/unit/services/test_genesys_cache_db.py -v --no-cov` while offline; should pass.
  </acceptance_criteria>
  <done>14+ tests across both files passing, all external IO (HTTP/pyodbc/httpx) mocked at module-import boundary; per-file coverage on each ≥40%.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 4: JobRoleWarehouseService boundary tests (pyodbc-mocked)</name>
  <files>tests/unit/services/test_job_role_warehouse_service.py</files>
  <read_first>
    - app/services/job_role_warehouse_service.py (full file — confirm pyodbc import (line ~10), method signatures for test_connection, sync_job_codes, sync_keystone_roles, sync_employee_keystone_assignments, get_expected_roles_mapping, sync_all_compliance_data; identify what each method writes to DB)
    - app/models/job_role_compliance.py (JobCode, SystemRole, EmployeeRoleAssignment schemas — what does sync_* upsert?)
    - tests/unit/services/test_refresh_employee_profiles.py (created in Task 3 — analog for pyodbc patching pattern; copy that pattern)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"Configuration Access" — pre-populate _config_cache for warehouse keys per simple_config bug)
  </read_first>
  <behavior>
    Target 6-8 tests covering ~50% of 193 missed stmts:
    - `test_pyodbc_unavailable_logs_warning` — `mocker.patch("app.services.job_role_warehouse_service.pyodbc", None)`; instantiate service; assert log warning emitted (use caplog)
    - `test_get_connection_string_includes_server_and_database` — pre-populate `service._config_cache` with `data_warehouse.server`, `data_warehouse.database`, `data_warehouse.client_id`, `data_warehouse.client_secret`; call `_get_connection_string()`; assert returned string contains expected substrings
    - `test_test_connection_returns_false_when_pyodbc_none` — same as analog in Task 3
    - `test_test_connection_happy_path_with_mocked_connect` — mock pyodbc.connect, assert returns True
    - `test_test_connection_returns_false_on_pyodbc_exception` — mock pyodbc.connect to raise; assert returns False; assert log error
    - `test_sync_job_codes_upserts_rows` — mock pyodbc cursor to `fetchall()` returning 2 rows of (job_code, job_title, ...); call `sync_job_codes()`; assert 2 JobCode rows in DB; assert returned dict has `synced=2` (verify shape)
    - `test_sync_job_codes_updates_existing_row` — pre-seed JobCode("JC1", "Old Title"); mock cursor to return [("JC1", "New Title")]; assert title was updated, not duplicated
    - `test_sync_keystone_roles_upserts_system_roles` — mock cursor with role rows; assert SystemRole rows created
    - `test_sync_all_compliance_data_orchestrates_subcalls` — mock all 3 sync_* methods on service via `mocker.patch.object(service, "sync_job_codes", ...)`; call `sync_all_compliance_data()`; assert each was called once

    Skip `sync_employee_keystone_assignments` and `get_expected_roles_mapping` unless trivial — both are downstream of sync_job_codes/sync_keystone_roles and may not be reachable without significant fixture setup.
  </behavior>
  <action>
    Create `tests/unit/services/test_job_role_warehouse_service.py`. Top:
    ```python
    """Boundary tests for JobRoleWarehouseService (Plan 02-05 gap closure).

    Mock pyodbc at `app.services.job_role_warehouse_service.pyodbc` (module-level
    try/except import). Use _config_cache override for warehouse credentials per
    the simple_config table-mismatch bug documented in deferred-items.md.
    """
    import pytest
    pytestmark = pytest.mark.unit
    ```

    For configuration setup in each test that hits a config-reading method:
    ```python
    @pytest.fixture
    def configured_svc(app, db_session):
        from app.services.job_role_warehouse_service import JobRoleWarehouseService
        svc = JobRoleWarehouseService()
        svc._config_cache.update({
            "data_warehouse.server": "test-sql.example.com",
            "data_warehouse.database": "TestDB",
            "data_warehouse.client_id": "fake-client",
            "data_warehouse.client_secret": "fake-secret",
            "data_warehouse.connection_timeout": 30,
            "data_warehouse.query_timeout": 60,
        })
        return svc
    ```

    For pyodbc cursor mocking (reuse pattern from Task 3):
    ```python
    def _mock_pyodbc_cursor(mocker, fetchall_return):
        cursor = mocker.MagicMock()
        cursor.fetchall.return_value = fetchall_return
        cursor.__enter__ = mocker.MagicMock(return_value=cursor)
        cursor.__exit__ = mocker.MagicMock(return_value=False)
        conn = mocker.MagicMock()
        conn.cursor.return_value = cursor
        conn.__enter__ = mocker.MagicMock(return_value=conn)
        conn.__exit__ = mocker.MagicMock(return_value=False)
        mocker.patch("app.services.job_role_warehouse_service.pyodbc.connect", return_value=conn)
        return cursor, conn
    ```

    Verify the exact return-row shape by reading `sync_job_codes` source — column ordering matters for the unpacking inside the method.

    Use `mocker.patch.object` for orchestrator-style sync_all_compliance_data test:
    ```python
    def test_sync_all_compliance_data_orchestrates_subcalls(configured_svc, mocker):
        m1 = mocker.patch.object(configured_svc, "sync_job_codes", return_value={"synced": 0})
        m2 = mocker.patch.object(configured_svc, "sync_keystone_roles", return_value={"synced": 0})
        m3 = mocker.patch.object(configured_svc, "sync_employee_keystone_assignments", return_value={"synced": 0})

        result = configured_svc.sync_all_compliance_data()
        m1.assert_called_once()
        m2.assert_called_once()
        m3.assert_called_once()
        assert isinstance(result, dict)
    ```
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -m pytest tests/unit/services/test_job_role_warehouse_service.py -v --no-cov 2>&amp;1 | tail -25</automated>
  </verify>
  <acceptance_criteria>
    - File exists.
    - `pytest tests/unit/services/test_job_role_warehouse_service.py -v --no-cov` reports ≥7 tests, all PASS.
    - `grep -c "patch\(.app\.services\.job_role_warehouse_service" tests/unit/services/test_job_role_warehouse_service.py` returns ≥3.
    - `grep -rE "from unittest" tests/unit/services/test_job_role_warehouse_service.py` returns 0.
    - Per-file coverage: `pytest tests/unit/services/test_job_role_warehouse_service.py --cov=app.services.job_role_warehouse_service --cov-report=term --no-cov-on-fail` shows coverage ≥45% (was 14.7%).
    - `ruff check tests/unit/services/test_job_role_warehouse_service.py` clean.
  </acceptance_criteria>
  <done>7+ unit tests passing; per-file coverage on job_role_warehouse_service.py ≥45% (was 14.7%).</done>
</task>

<task type="auto">
  <name>Task 5: Run full suite + verify 60% coverage gate passes (gap closed)</name>
  <files>.planning/phases/02-test-suite/02-VERIFICATION.md (append; do NOT overwrite the canonical report)</files>
  <read_first>
    - .planning/phases/02-test-suite/02-VERIFICATION.md (read full file — append a "Gap Closure (Plan 02-05)" section at the end; preserve all existing canonical content)
    - pyproject.toml (confirm `--cov-fail-under=60` is unchanged from its current value)
    - Makefile (confirm `make test` invocation unchanged)
  </read_first>
  <action>
    1. **Run the full suite with the configured gate:**
       ```bash
       cd C:/repos/Who-Dis
       pytest tests/ 2>&1 | tee /tmp/phase02-gap-closure-run.log
       ```
       Capture exit code, total test count, pass/fail/xfail counts, and the final coverage line (e.g., `Required test coverage of 60% reached. Total coverage: XX.XX%`).

    2. **Verify exit code is 0:** `echo "exit=$?"` after the run; if non-zero, do NOT proceed — return to whichever per-file coverage didn't lift enough and add 2-3 more tests in the corresponding test_*.py until the gate passes. Per-task acceptance criteria specify the per-file targets; if the aggregate still doesn't reach 60%, the bottleneck is most likely audit_service_postgres.py (19.4%, 149 missed) or graph_service.py (10.2%, 191 missed) — these are NOT scoped to this plan; if needed, add a small `tests/unit/services/test_audit_service_postgres.py` with 3-4 boundary tests as scope creep, with a comment block explaining why.

    3. **Verify pyproject.toml gate value unchanged:**
       ```bash
       grep "cov-fail-under" pyproject.toml
       ```
       MUST still show `--cov-fail-under=60`. If it's been lowered, REVERT — that's a contract violation per VERIFICATION.md path (1).

    4. **Verify pre-push hook unblocks ordinary pushes:**
       ```bash
       bash .githooks/pre-push 2>&1
       echo "hook_exit=$?"
       ```
       Must exit 0. (No need to actually `git push --dry-run` — that requires a remote; running the hook script directly is sufficient because the hook IS just `make test`.)

    5. **Append a "Gap Closure (Plan 02-05)" section to `.planning/phases/02-test-suite/02-VERIFICATION.md`** at the BOTTOM of the file (do not modify the canonical content above). Format:

       ```markdown
       ---

       ## Gap Closure (Plan 02-05) — appended <YYYY-MM-DD>

       **Plan:** `02-05-coverage-closure-PLAN.md`
       **Closes gap:** ROADMAP SC #2 / TEST-04 — services + middleware coverage ≥60%

       ### Coverage Delta

       | Package | Before (Wave-4) | After (Plan 02-05) | Delta |
       |---------|----------------:|-------------------:|------:|
       | app/services | 33.0% line | <X.X%> line | +<X.X>pp |
       | app/middleware | 56.2% line | <X.X%> line | +<X.X>pp |
       | **Combined gate (line+branch)** | **32.0%** | **<X.X%>** | **+<X.X>pp** |

       ### Per-File Coverage Lift (Plan 02-05 targets)

       | File | Before | After | Delta |
       |------|-------:|------:|------:|
       | compliance_checking_service.py | 0.0% | <X%> | +<X>pp |
       | genesys_cache_db.py | 11.9% | <X%> | +<X>pp |
       | job_role_mapping_service.py | 13.3% | <X%> | +<X>pp |
       | job_role_warehouse_service.py | 14.7% | <X%> | +<X>pp |
       | refresh_employee_profiles.py | 16.4% | <X%> | +<X>pp |

       ### Gate Status

       - `pytest tests/` exit code: **0**
       - `--cov-fail-under=60` in pyproject.toml: **PASS** (combined coverage <X.X%> ≥ 60%)
       - `bash .githooks/pre-push` exit code: **0** (hook unblocks ordinary pushes)
       - pyproject.toml `--cov-fail-under` value: **60** (unchanged from Plan 02-04 — D-11 contract preserved)

       ### Tests Added

       | File | Tests | Passing | xfail-strict |
       |------|------:|--------:|-------------:|
       | test_compliance_checking_service.py | <N> | <N> | <N> |
       | test_genesys_cache_db.py | <N> | <N> | <N> |
       | test_job_role_mapping_service.py | <N> | <N> | <N> |
       | test_job_role_warehouse_service.py | <N> | <N> | <N> |
       | test_refresh_employee_profiles.py | <N> | <N> | <N> |
       | **Total** | **<N>** | **<N>** | **<N>** |

       ### Verification Status (re-run)

       | ROADMAP SC | Wave-4 Status | Plan-02-05 Status |
       |------------|---------------|-------------------|
       | #2 services + middleware ≥60% | FAIL (32.0%) | **PASS** (<X.X%>) |

       Phase 2 verification status updated from `gaps_found` to `verified` upon orchestrator re-verification.
       ```

       Replace every `<...>` placeholder with real numbers from the run log.

    6. **Sanity-check that no production code was modified.** Run:
       ```bash
       git diff --stat app/ requirements.txt pyproject.toml Makefile .githooks/
       ```
       Expected output: empty (Plan 02-05 only touches `tests/` and `.planning/`).
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; pytest tests/ 2>&amp;1 | tail -5 &amp;&amp; echo "===" &amp;&amp; grep "cov-fail-under" pyproject.toml &amp;&amp; echo "===" &amp;&amp; bash .githooks/pre-push &amp;&amp; echo "hook=PASS" &amp;&amp; echo "===" &amp;&amp; grep -c "Gap Closure (Plan 02-05)" .planning/phases/02-test-suite/02-VERIFICATION.md</automated>
  </verify>
  <acceptance_criteria>
    - `pytest tests/` (no `--no-cov`, no CLI override of `--cov-fail-under`) exits 0.
    - Run output contains a line matching `Required test coverage of 60% reached. Total coverage: \d+\.\d+%` (the pytest-cov success message).
    - `grep -c "cov-fail-under=60" pyproject.toml` returns ≥1 (gate value unchanged).
    - `grep -c "cov-fail-under=" pyproject.toml | sort -u` shows ONLY `60` (no values <60).
    - `bash .githooks/pre-push` exits 0 (hook unblocks ordinary pushes from a clean tree).
    - `git diff --stat app/ requirements.txt pyproject.toml Makefile .githooks/ | wc -l` returns 0 (no production changes).
    - `.planning/phases/02-test-suite/02-VERIFICATION.md` contains a `## Gap Closure (Plan 02-05)` H2 section.
    - All `<...>` placeholders in the appended VERIFICATION section are replaced with real numbers (no leftover angle-bracketed placeholders inside that section — verifiable by `grep -c "<X" .planning/phases/02-test-suite/02-VERIFICATION.md` returning 0 within the new section, scoped via `awk '/Gap Closure/,/^$/'`).
    - The canonical content of VERIFICATION.md ABOVE the new section is byte-identical to its pre-Plan-02-05 state (verifiable via `git diff` showing only appended lines).
    - Full suite test count is ≥36 (Plans 02-01..04 baseline) + new tests from Tasks 1-4 (≥40 added) = ≥76 total tests collected.
  </acceptance_criteria>
  <done>Phase 2 gap closed: `pytest tests/` exits 0, coverage gate passes at ≥60%, pre-push hook unblocks ordinary pushes, VERIFICATION.md records the delta with real numbers; pyproject.toml gate value preserved per D-11.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test process → mocked external services | Tests patch `requests`, `pyodbc`, `httpx` at module-import boundaries; no real network or DB-warehouse calls. Unchanged from Plan 02-03. |
| test DB → application code | Tests drive real SQLAlchemy operations against the testcontainers Postgres instance — same trust boundary as Plan 02-03's integration tests. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-13 | T (Tampering) | A test could pass while production code path is broken if mocks return overly-permissive shapes | mitigate | Mock at the import boundary (`app.services.<module>.requests`, `pyodbc`), assert on persisted DB state where possible (factories + queries), and exercise pure helpers without mocks. Per-file coverage thresholds in acceptance criteria force assertions on real branches, not just mock side-effects. |
| T-02-14 | I (Information Disclosure) | Cleanup-old-data tests delete real-looking PII from test DB | accept | Test DB is ephemeral testcontainer; data is synthetic via factories (`@test.local` emails, fake job codes). |
| T-02-15 | D (Denial of Service) | Coverage push to 60% may add slow tests that bloat pre-push hook runtime | mitigate | Each task targets ≤10 tests; total new tests ≤40. Pyodbc/httpx tests are mock-only (no IO). Genesys cache HTTP tests use `requests` mocks. Wall-time addition expected ≤3s on top of existing 18.71s — acceptable for a pre-push gate. |
</threat_model>

<verification>
- All four implementation tasks (1-4) pass acceptance criteria; per-file coverage on each of the 5 targeted services is ≥40-50% (up from 0-16%).
- Task 5 confirms aggregate coverage ≥60% by running `pytest tests/` with the existing pyproject.toml gate and getting exit 0.
- pyproject.toml `--cov-fail-under=60` value verified unchanged (D-11 preserved).
- No production code modifications in `app/`, `requirements*.txt`, `Makefile`, `.githooks/`.
- VERIFICATION.md retains its canonical Wave-4-supersede content + an appended "Gap Closure (Plan 02-05)" section with real numbers.
- Pre-push hook (`bash .githooks/pre-push`) exits 0 from a clean tree, demonstrating that ordinary pushes are no longer blocked by the coverage gate.
</verification>

<success_criteria>
- All Task 1-5 acceptance criteria pass.
- Combined services+middleware coverage ≥60% (the contract from D-11 / TEST-04 / ROADMAP SC #2).
- `pytest tests/` exits 0 from a clean clone with no `--no-verify` workaround needed.
- `.planning/phases/02-test-suite/02-VERIFICATION.md` updated with a "Gap Closure (Plan 02-05)" section containing real coverage numbers and confirming gate PASS.
- Phase 2 verification status flips from `gaps_found` to `verified` on orchestrator re-verification.
- No new pre-existing-bug discoveries beyond what's documented in `deferred-items.md` (any new ones surfaced via xfail-strict markers, not silent skips).
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-05-SUMMARY.md` documenting:
- Final combined coverage percentage (services + middleware, line+branch as the gate measures)
- Per-file coverage delta for the 5 targeted services (before vs after)
- Total tests added (count per file + grand total)
- Any new xfail-strict markers added (mapped to deferred-items.md entries)
- Confirmation that pyproject.toml `--cov-fail-under=60` value is unchanged
- One-paragraph note suitable for the milestone retrospective: "Phase 2 gap closed — what changed for the developer" (e.g., `git push` no longer requires `--no-verify`, the 5 cold-path services now have boundary regression protection ahead of Phase 3 containerization)
</output>
