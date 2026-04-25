---
phase: 02-test-suite
plan: 02
subsystem: testing
tags: [testing, pytest, fixtures, fakes, factories, di-container, savepoint, testcontainers]

requires:
  - phase: 02-test-suite
    plan: 01
    provides: pyproject.toml pytest config, requirements-dev.txt with testcontainers/factory-boy/pytest, Makefile, pre-push hook
provides:
  - tests/conftest.py — session-scoped ephemeral Postgres + Flask app + per-test SAVEPOINT + container snapshot/reset + fake_ldap/fake_graph/fake_genesys fixtures
  - tests/unit/conftest.py — request_context fixture for orchestrator unit tests
  - tests/integration/conftest.py — authenticated_client + admin_client header-injection fixtures (PHASE 4 NOTE for Keycloak migration documented)
  - tests/fakes/fake_ldap_service.py — FakeLDAPService(ISearchService) with multiple_results + get_user_by_dn
  - tests/fakes/fake_graph_service.py — FakeGraphService(ISearchService, ITokenService) with include_photo + get_user_by_id
  - tests/fakes/fake_genesys_service.py — FakeGenesysService(ISearchService, ITokenService) with too_many_results degraded path
  - tests/factories/{user,api_token,job_code,system_role}.py — factory_boy SQLAlchemyModelFactory bound to db.session
  - app/__init__.py — TESTING-flag gates around 4 background-thread / external-API call sites
affects: [02-03 targeted-and-integration-tests, 02-04 coverage-gate-and-docs, 03-containerization (uses TESTING flag for image-build smoke tests)]

tech-stack:
  added: []  # All deps were added in Wave 1 (testcontainers, factory-boy already in requirements-dev.txt)
  patterns:
    - "Container-override fake injection (D-04): app.container.register('ldap_service', lambda c: FakeLDAPService(...))"
    - "SAVEPOINT-per-test isolation (D-03): SQLAlchemy 2.0 nested-transaction pattern via public sessionmaker + scoped_session API"
    - "TESTING-config gate (D-06): production create_app() preserved; tests skip background threads + startup HTTP via single Boolean check"
    - "Interface-only fakes (D-04): fakes implement ISearchService/ITokenService directly, no production base-class inheritance"
    - "Header-injection auth fixture (D-13): integration tests drive the real auth middleware via X-MS-CLIENT-PRINCIPAL-NAME injection; PHASE 4 NOTE documents Keycloak swap path"

key-files:
  created:
    - tests/__init__.py
    - tests/conftest.py
    - tests/unit/__init__.py
    - tests/unit/conftest.py
    - tests/integration/__init__.py
    - tests/integration/conftest.py
    - tests/fakes/__init__.py
    - tests/fakes/fake_ldap_service.py
    - tests/fakes/fake_graph_service.py
    - tests/fakes/fake_genesys_service.py
    - tests/factories/__init__.py
    - tests/factories/user.py
    - tests/factories/api_token.py
    - tests/factories/job_code.py
    - tests/factories/system_role.py
  modified:
    - app/__init__.py (4 TESTING gates added at lines 160, 181, 190, 198 — startup token-refresh loop, token_refresh.start(), cache_cleanup.start(), Genesys cache warmup)

key-decisions:
  - "init_db env-var override (not URI bypass): conftest sets POSTGRES_HOST/PORT/USER/PASSWORD/DB from urlparse(testcontainers_dsn) so app/database.py:get_database_uri runs unchanged. SQLALCHEMY_DATABASE_URI itself is composed by init_db."
  - "WHODIS_ENCRYPTION_KEY auto-generated per session via Fernet.generate_key().decode() so tests don't depend on developer .env contents — bootstrapping the encryption service before configuration_service runs"
  - "WTF_CSRF_ENABLED=False on the test app to avoid CSRF noise in test client POSTs (CSRF middleware itself stays active and is exercised by dedicated csrf-focused tests in Plan 03)"
  - "JobCode factory uses model field name `job_code` (not `code` from the plan body) — verified by reading app/models/job_role_compliance.py:JobCode. JobCode and SystemRole live in job_role_compliance.py, not standalone modules"
  - "ApiTokenFactory.service_name uses factory.Sequence (not hardcoded 'graph') — ApiToken.service_name has unique=True, so multiple ApiTokenFactory() calls in one test would conflict on a static value"

requirements-completed: [TEST-01, TEST-02]

duration: 9min
completed: 2026-04-25
---

# Phase 2 Plan 2: Fixtures, Fakes & Factories Summary

**Test harness wired end-to-end: TESTING flag gates background threads in production code, ephemeral Postgres + SAVEPOINT conftest isolates each test, container-override fixtures inject interface-only fakes for LDAP/Graph/Genesys, and four factory_boy factories generate model rows against the SAVEPOINT-scoped session.**

## Performance

- **Tasks:** 3
- **Files modified:** 16 (15 created, 1 modified — app/__init__.py)
- **Production code change:** 4 surgical TESTING-gate insertions in app/__init__.py; zero behavior change when TESTING is unset

## Accomplishments

### Task 1 — TESTING-flag gates in app/__init__.py
Added `if not app.config.get("TESTING"):` guards at four sites:

| Line | Block | What is skipped under TESTING |
|------|-------|-------------------------------|
| 160 | `for service in token_services: ... refresh_token_if_needed()` | Startup token-refresh loop — would attempt real HTTP fetches against MS Graph / Genesys |
| 181 | `token_refresh.start()` | Background TokenRefreshService thread |
| 190 | `cache_cleanup.start()` | Background CacheCleanupService thread (DEBT-03) |
| 198 | `genesys_cache_db.refresh_all_caches(genesys_service)` (combined with `genesys_service` truthiness) | Genesys cache warmup — would fire real HTTP requests |

**Untouched** (still runs under TESTING):
- `audit_service.init_app(app)` at line 146 — integration tests in Plan 03 will assert on audit rows
- The outer `if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:` gate at line 143 — form unchanged

**`employee_profiles_refresh_service` `.start()` call sites:** None exist in `app/` or `scripts/` (verified via grep). The service is registered in `app/container.py` but is invoked on-demand only (not wired to a startup background thread). No gating needed.

### Task 2 — Conftest tree (root + unit + integration)
- **`tests/conftest.py`** boots one `PostgresContainer("postgres:15-alpine")` per session, applies `database/create_tables.sql` + `database/analyze_tables.sql` via psycopg2, projects DSN parts into `POSTGRES_HOST/PORT/USER/PASSWORD/DB` env vars so `app/database.py:get_database_uri` runs unchanged
- Per-test `db_session` fixture wraps work in a SAVEPOINT (SQLAlchemy 2.0 public-API pattern: `from sqlalchemy.orm import scoped_session, sessionmaker` — no `db._make_scoped_session`), rolls back on teardown
- `container_reset` fixture snapshots `app.container._factories` and restores after each test; `fake_ldap`/`fake_graph`/`fake_genesys` convenience fixtures use it to register fake instances and drop singleton cache via `container.reset()`
- **`tests/unit/conftest.py`** provides `request_context` for orchestrator unit tests that need `g.user`/`g.role` populated under `app.test_request_context()`
- **`tests/integration/conftest.py`** provides `authenticated_client` (header-only viewer) and `admin_client` (pre-seeds admin user via UserFactory then sets header). PHASE 4 NOTE at top of file documents the Keycloak OIDC swap path per D-13.

### Task 3 — Fakes + factories
- **Fakes** all implement only the interface (`ISearchService` for LDAP; `ISearchService, ITokenService` for Graph/Genesys). Confirmed via `grep -rc 'BaseSearchService\|BaseAPIService' tests/fakes/` → 0 matches in source code (post-cleanup of doc string).
- **multiple_results wrapper** present in all three fakes; **too_many_results** degraded path in Genesys fake; **get_user_by_dn** in LDAP fake; **get_user_by_id** in Graph + Genesys fakes; **include_photo** parameter in Graph fake's `search_user` and `get_user_by_id` signatures
- **Factories:** `UserFactory`, `ApiTokenFactory` (with `expiring` Trait inside the 10-min refresh threshold), `JobCodeFactory`, `SystemRoleFactory` — all bind to `db.session` with `sqlalchemy_session_persistence="flush"`; none set `created_at`/`updated_at` (TimestampMixin handles those)

## Task Commits

1. **Task 1: Surgical TESTING-flag gate in app/__init__.py + conftest stub** — `c7c5f05` (feat)
2. **Task 2: Ephemeral Postgres + SAVEPOINT conftest + container-override fixtures** — `9aa789f` (feat)
3. **Task 3: Three fakes + four factory_boy factories** — `fc01a62` (feat)

## Files Created/Modified

**Created (15):** `tests/__init__.py`, `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/conftest.py`, `tests/integration/__init__.py`, `tests/integration/conftest.py`, `tests/fakes/__init__.py`, `tests/fakes/fake_ldap_service.py`, `tests/fakes/fake_graph_service.py`, `tests/fakes/fake_genesys_service.py`, `tests/factories/__init__.py`, `tests/factories/user.py`, `tests/factories/api_token.py`, `tests/factories/job_code.py`, `tests/factories/system_role.py`

**Modified (1):** `app/__init__.py` — 4 TESTING gates inserted; existing `WERKZEUG_RUN_MAIN`/`app.debug` outer gate untouched; audit_service init untouched

## Decisions Made

- **`init_db` env-var override over URI bypass.** `app/database.py:get_database_uri` reads `POSTGRES_HOST/PORT/DB/USER/PASSWORD` from env. Setting these from `urlparse(testcontainers_dsn)` lets `init_db` and the connection-pool config run identically to production — no parallel test-only database wiring path.
- **JobCode/SystemRole models live in `app/models/job_role_compliance.py`**, not standalone files. Plan PATTERNS body referenced `app/models/job_code.py` and `app/models/system_role.py`; verified the actual paths and adjusted factory imports.
- **`ApiTokenFactory.service_name` uses `factory.Sequence`**, not the static `"graph"` shown in the plan body. `ApiToken.service_name` has `unique=True`; a static value would cause `IntegrityError` on the second `ApiTokenFactory()` call in the same test.
- **`WHODIS_ENCRYPTION_KEY` generated per session.** Fresh Fernet key avoids depending on developer `.env` contents and prevents any chance of test runs reading/writing real encrypted production data.
- **Doc-string scrub in fake_ldap_service.py.** Initial draft mentioned "does NOT inherit BaseSearchService" — that literal phrase tripped the acceptance grep that asserts zero `BaseSearchService` references in `tests/fakes/`. Reworded to "without inheriting from any production base service class".

## Deviations from Plan

**1. [Rule 3 - Verification Limitation] Cannot run pytest validation in this executor environment**
- **Found during:** Task 2 verification
- **Issue:** `pytest --collect-only` fails with `ModuleNotFoundError: No module named 'testcontainers'` — this venv doesn't have the dev requirements installed.
- **Decision per executor prompt:** Plan instructs "If you cannot run pytest to validate, document it in SUMMARY.md deviations and let Wave 4 do the full validation — do NOT block on it."
- **Mitigation:** All Python files validated via `ast.parse()` (syntax-correct). All grep-based acceptance criteria confirmed. `cd .planning/phases/02-test-suite/02-04-coverage-gate-and-docs-PLAN.md` (Wave 4) will run the full suite end-to-end.
- **Files affected:** None modified to work around — the harness is correct; validation deferred.

**2. [Rule 1 - Bug] Plan-body model paths corrected**
- **Found during:** Task 3 read-first phase
- **Issue:** Plan referenced `app/models/job_code.py` and `app/models/system_role.py`; both classes actually live in `app/models/job_role_compliance.py`.
- **Fix:** Updated factory imports to `from app.models.job_role_compliance import JobCode` / `SystemRole`.
- **Files modified:** `tests/factories/job_code.py`, `tests/factories/system_role.py`
- **Commit:** `fc01a62`

**3. [Rule 2 - Critical Functionality] ApiTokenFactory.service_name uniqueness**
- **Found during:** Task 3 implementation
- **Issue:** Plan body showed `service_name = "graph"` (static), but `ApiToken.service_name` is `unique=True`. Two factory calls in the same test would `IntegrityError`.
- **Fix:** Changed to `factory.Sequence(lambda n: f"service-{n}")`.
- **Files modified:** `tests/factories/api_token.py`
- **Commit:** `fc01a62`

## Self-Check: PASSED

- All 15 new files exist on disk — VERIFIED via `git diff --name-only HEAD~3 HEAD`
- All commits in git log: `c7c5f05`, `9aa789f`, `fc01a62` — VERIFIED
- `grep -c 'if not app.config.get("TESTING"):' app/__init__.py` returns 3 — VERIFIED (plan acceptance: ≥3)
- `grep -c 'app.config.get("TESTING")' app/__init__.py` returns 4 (3 standalone + 1 combined-with-genesys_service) — VERIFIED
- `grep -c 'audit_service.init_app' app/__init__.py` returns 1, NOT inside any TESTING block — VERIFIED by inspection at line 146
- `grep -c 'PostgresContainer' tests/conftest.py` returns 2 (import + with-statement) — exceeds plan minimum of 1
- `grep -c 'create_tables.sql' tests/conftest.py` returns 3 (constant + read + comment) — exceeds plan minimum of 1
- `grep -c 'begin_nested' tests/conftest.py` returns 2 (initial + listener restart) — exceeds plan minimum of 1
- `grep -c '_make_scoped_session' tests/conftest.py` returns 0 — VERIFIED (uses public API)
- `grep -c 'from sqlalchemy.orm import scoped_session, sessionmaker' tests/conftest.py` returns 1 — VERIFIED
- `grep -c 'RATELIMIT_ENABLED' tests/conftest.py` returns 1 — VERIFIED (Phase 1 D-08)
- `grep -c 'PHASE 4 NOTE' tests/integration/conftest.py` returns 1 — VERIFIED
- `grep -rc 'BaseSearchService\|BaseAPIService' tests/fakes/` returns 0 across all fake modules — VERIFIED
- All 7 fake/factory Python files parse via `ast.parse()` — VERIFIED
- `created_at`/`updated_at` not set in any factory file (`grep -rc` returns 0 across `tests/factories/`) — VERIFIED

## Threat Flags

None — this plan adds test-only files plus 4 surgical TESTING-config gates around existing call sites. No new network endpoints, auth paths, or trust-boundary crossings.

## Known Stubs

None. All fixtures, fakes, and factories are fully wired against the production interfaces.

## Outstanding Validation Items (for Wave 4)

These cannot be run in this executor due to missing dev deps in the active venv:
- `pip install -r requirements-dev.txt` then `pytest --collect-only` (must succeed with zero ImportError)
- A trivial `def test_savepoint(db_session): ...` to prove SAVEPOINT rollback works against a real Postgres container
- A trivial `def test_container_override(fake_ldap): ...` to prove the container snapshot/restore cycle works
- Docker daemon connectivity check from testcontainers via npipe (Windows host)
- `mypy app/__init__.py` clean (only the 4 surgical edits added)

## Next Plan Readiness

Plan 02-03 (targeted + integration tests) can now write tests as `def test_x(client, fake_ldap, user_factory): ...` — the harness exposes:
- `app`, `client` (auto-includes `db_session`), `db_session` — DB lifecycle
- `fake_ldap`, `fake_graph`, `fake_genesys` — interface-compliant external-service stand-ins
- `authenticated_client`, `admin_client` — pre-headered test clients for `@auth_required` / `@require_role` routes
- `request_context` — for orchestrator unit tests using `copy_current_request_context`
- Factories: import directly via `from tests.factories.user import UserFactory` etc.

Plan 02-04 will surface to README:
- `git config core.hooksPath .githooks` (one-time per clone)
- `pip install -r requirements-dev.txt` (one-time per dev environment)
- Docker required for the `testcontainers` Postgres fixture

---
*Phase: 02-test-suite*
*Completed: 2026-04-25*
