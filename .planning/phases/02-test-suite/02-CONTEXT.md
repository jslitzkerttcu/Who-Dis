# Phase 2: Test Suite - Context

**Gathered:** 2026-04-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Bootstrap pytest infrastructure (framework, fixtures, model factories, container-level fakes for external APIs, coverage gate, pre-push enforcement) sufficient to gate the Phase 3-5 refactors. Delivers TEST-01..04.

In scope: pytest config, test DB harness, fake LDAP/Graph/Genesys services, factory_boy model factories, integration tests for auth pipeline + search flow, targeted tests for the 3 hottest service files, 60% coverage gate on `app/services/` + `app/middleware/`, pre-push hook.

Out of scope: exhaustive blueprint testing (search/__init__.py 2720L and admin/database.py 2532L are too large for this phase — defer to a follow-up "blueprint hardening" phase). E2E browser testing. Performance / load testing. CI pipeline (no CI exists yet — pre-push hook is the gate).

</domain>

<decisions>
## Implementation Decisions

### Test Database (TEST-01, TEST-03)
- **D-01:** **Ephemeral PostgreSQL via testcontainers-python.** Session-scoped fixture spins one Postgres container, schema persists for the run. Matches prod schema exactly (JSONB columns in `Configuration`, `EmployeeProfile`, `GenesysGroup`; memoryview/BYTEA in encryption paths). Adds `testcontainers[postgres]` to dev requirements; requires Docker on dev machines. Aligns with Phase 3 containerization direction.
- **D-02:** **Schema loaded by executing `database/create_tables.sql` at session setup**, not `db.create_all()`. The SQL file is the canonical schema (indexes, defaults, `ANALYZE` calls); SQLAlchemy `create_all()` diverges. When Phase 5 introduces Alembic, swap this fixture body to `alembic upgrade head` — the rest of the test harness is unaffected.
- **D-03:** **Per-test isolation via nested SAVEPOINT rollback.** SQLAlchemy event listener pattern — each test wraps its work in a SAVEPOINT and rolls back at teardown. Zero data leak between tests, zero TRUNCATE cost. Standard pytest-flask-sqlalchemy pattern.

### Mocking Strategy (TEST-02)
- **D-04:** **Container-level fake services.** `tests/fakes/` contains `FakeLDAPService`, `FakeGraphService`, `FakeGenesysService` — each implements the same interface as the real service (`ISearchService`, `ITokenService`). Test fixture overrides container entries: `app.container.register("ldap_service", lambda c: FakeLDAPService(users=test_users))`. Real `SearchOrchestrator`, real `ResultMerger`, real auth middleware run against the fakes. Mirrors prod wiring.
- **D-05:** **Configurable in-memory fakes.** Each fake takes constructor arguments for the dataset it should return: `FakeLDAPService(users=[{"sAMAccountName": "jdoe", ...}])`. Tests instantiate with exactly what they need. No global JSON fixture file. Fakes return real-shaped dicts (matching the real services' return contracts).
- **D-06:** **Background threads disabled via `app.config['TESTING']` flag.** `create_app()` checks `app.config.get('TESTING')` and skips `.start()` calls on `token_refresh_service`, `employee_profiles_refresh_service`, and `cache_cleanup_service`. Small, surgical edit to existing init code. Tests can still drive these services manually by calling their public methods directly.

### Fixtures & Factories
- **D-07:** **factory_boy** for model factories. Add `factory-boy` to dev requirements. Factories live in `tests/factories/` — one module per model (`user.py`, `api_token.py`, `job_code.py`, `system_role.py`, etc.). SQLAlchemySession integration so factories `.create()` against the test DB session managed by the SAVEPOINT fixture.
- **D-08:** **Conftest organization:** root `tests/conftest.py` holds the session-scoped Postgres + app fixtures and the SAVEPOINT pattern. `tests/unit/conftest.py` and `tests/integration/conftest.py` add scope-specific fixtures (e.g., authenticated test client). Fakes registered as fixtures so tests can request them by name.

### Merge Gate (TEST-04, criterion 4)
- **D-09:** **Pre-push git hook running `pytest -x --cov-fail-under=60`.** Installed via the existing pre-commit framework if present, otherwise plain bash hook in `.githooks/pre-push` with a one-liner installer in the README. Pre-push (not pre-commit) so iterative commits stay fast; the gate fires before code leaves the dev machine. `--no-verify` remains an explicit emergency escape.
- **D-10:** **Makefile target `make test`** for ad-hoc invocation. Wraps the same `pytest` command. Lets devs run the suite without a git operation. Single source of truth — the hook calls the make target.

### Coverage Scope (TEST-04)
- **D-11:** **Coverage gate measured on `app/services/` + `app/middleware/` only.** Matches TEST-04 literally. `pytest-cov` config (in `pyproject.toml`) sets `--cov=app.services --cov=app.middleware --cov-fail-under=60`. Other packages (`app/blueprints/`, `app/models/`, `app/utils/`) still appear in the HTML report for visibility but don't gate the build.
- **D-12:** **Targeted seed tests for the 3 hottest service files:** `search_orchestrator.py`, `ldap_service.py` (652L), `genesys_service.py` (668L). These are the auth/search hot paths Phases 3-5 will refactor. Search blueprint (2720L) and admin/database blueprint (2532L) are deferred to a future "blueprint hardening" phase — explicitly out of scope for Phase 2.

### Integration Tests (TEST-03)
- **D-13:** **Auth pipeline coverage:** valid Azure-AD-style header → user auto-provisioned with `viewer` role + `g.user`/`g.role` populated; missing header → 401; valid header but role insufficient → 403; existing user → role retained. Covers `authentication_handler` → `user_provisioner` → `role_resolver` → `@require_role` chain. NOTE: Phase 4 will replace Azure AD headers with Keycloak OIDC — these tests will need to be rewritten then. Acceptable: Phase 2 ships the harness, Phase 4 rewrites the auth tests against the new pipeline.
- **D-14:** **Search flow e2e:** `GET /search?term=jdoe` with FakeLDAP returning a record, FakeGraph returning licenses, FakeGenesys returning queue membership → orchestrator merges → HTMX fragment renders with all three sources. Verifies the entire request → orchestrator → fakes → merger → template path. ~6-8 integration tests total.

### Claude's Discretion
The following are tactical enough for the planner to decide:
- **pytest config location** — `pyproject.toml` (matches modern Python convention, ruff/mypy already use config files)
- **Test directory layout** — `tests/{unit,integration,fakes,factories,fixtures}/` per the recommended structure in `.planning/codebase/TESTING.md`
- **pytest-mock vs unittest.mock** — pytest-mock (cleaner fixture-based API)
- **HTMX response assertions** — assert on rendered HTML fragments using BeautifulSoup or simple `in response.data` substring checks; pick whichever reads cleaner per test
- **Test app factory** — reuse production `create_app()` with `TESTING=True` config override; do not introduce a separate `create_test_app()`
- **`conftest.py` path-juggling** — none expected; standard pytest discovery from repo root

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Planning
- `.planning/ROADMAP.md` §"Phase 2: Test Suite" — 4 success criteria
- `.planning/REQUIREMENTS.md` §"Testing" — TEST-01..04 acceptance criteria
- `.planning/STATE.md` — Phase 1 completion notes, accumulated decisions
- `.planning/phases/01-foundation/01-CONTEXT.md` — D-05/06 (request-ID + JSON logging — tests must capture these cleanly), D-08 (Flask-Limiter — disable in tests or assert 429)

### Codebase Maps
- `.planning/codebase/TESTING.md` — Existing testing analysis, recommended directory structure, mocking patterns
- `.planning/codebase/STACK.md` — Python 3.8+, Flask 3.1, SQLAlchemy 2.0, ldap3, msal, requests
- `.planning/codebase/ARCHITECTURE.md` — DI container, blueprint structure, service patterns
- `.planning/codebase/CONVENTIONS.md` — snake_case, type hints, decorator stacks
- `.planning/codebase/STRUCTURE.md` — Package layout for coverage scope decisions

### Existing Code (must read before changing)
- `app/__init__.py` — `create_app()` factory; D-06 edit goes here (TESTING flag gates thread starts)
- `app/container.py` — Service registration; tests override entries here
- `app/services/base.py` — `BaseSearchService`, `BaseAPIService`, `BaseTokenService` — fakes implement these contracts
- `app/services/ldap_service.py` (652L) — Targeted test seed (D-12)
- `app/services/genesys_service.py` (668L) — Targeted test seed (D-12)
- `app/services/search_orchestrator.py` — Targeted test seed (D-12)
- `app/services/result_merger.py` — Exercised end-to-end via search integration test
- `app/services/token_refresh_service.py`, `app/services/employee_profiles_refresh_service.py`, `app/services/cache_cleanup_service.py` — Background threads disabled by D-06
- `app/middleware/authentication_handler.py` — Header parsing for D-13
- `app/middleware/user_provisioner.py` — Auto-provision path for D-13
- `app/middleware/role_resolver.py` — Role lookup for D-13
- `app/middleware/auth.py` — `@auth_required` / `@require_role` decorators tested in D-13
- `app/middleware/csrf.py`, `app/middleware/security_headers.py`, `app/middleware/audit_logger.py` — Counted toward coverage gate
- `app/interfaces/search_service.py`, `app/interfaces/token_service.py` — Contracts the fakes must satisfy
- `database/create_tables.sql` — Schema source for D-02
- `requirements.txt` — Add `pytest`, `pytest-cov`, `pytest-mock`, `factory-boy`, `testcontainers[postgres]` to a new `requirements-dev.txt` (or split section)

### Project Conventions
- `CLAUDE.md` §"Critical Implementation Patterns" — DI container, decorators, model patterns; tests must respect these
- `CLAUDE.md` §"Important Database Notes" — Memoryview handling, ANALYZE, encryption key bootstrap (matters for fake configuration service if needed)
- `mypy.ini` — Type-checking config; tests should pass mypy (or be explicitly excluded)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **DI container** (`app/container.py`) — Already supports `register()` overrides; tests use this for D-04 fake injection without touching production code paths
- **Service interfaces** (`app/interfaces/`) — `ISearchService`, `ITokenService`, `ICacheRepository` already define the contracts fakes must implement; no new abstractions needed
- **Service base classes** (`app/services/base.py`) — Real services inherit `BaseSearchService` / `BaseAPIService`; fakes can implement the interface directly without inheriting the base (avoids dragging real HTTP/timeout logic into tests)
- **Background-service skeleton** (token_refresh, employee_profiles_refresh, cache_cleanup) — All three follow the same `start()` pattern. D-06 gate is one `if not testing` check at each `.start()` call site
- **`ANALYZE` post-creation** — `database/analyze_tables.sql` exists; the test session fixture should run it after `create_tables.sql` so query plans match prod

### Established Patterns
- **`@handle_service_errors` decorator** — Service tests need to verify that this decorator catches and logs without raising (or re-raises when configured); test the decorator behavior alongside service logic
- **`logger = logging.getLogger(__name__)` per module** — Tests can use `caplog` to assert on log output; no special instrumentation needed
- **`config_get("category.key", default)`** — Tests that need configuration should override via `app.config` or by writing rows to the test DB's `Configuration` table; do not patch `config_get` directly (defeats the encryption layer)
- **`copy_current_request_context`** — Used in `SearchOrchestrator` for thread-pool calls. Tests of orchestrator must establish a request context (Flask test client does this automatically; direct unit tests need `app.test_request_context()`)
- **Memoryview/BYTEA** — Encryption service paths need `bytes(memoryview)` conversion. Tests touching encrypted config must round-trip through this conversion

### Integration Points
- **Pre-push hook** (D-09) — Either extends an existing `.pre-commit-config.yaml` (none currently in repo) or adds a `.githooks/` directory with a one-line `git config core.hooksPath .githooks` installer in the README
- **`requirements.txt` split** — Phase 2 introduces the dev/prod requirements split (production must not pull in `pytest`, `testcontainers`, `factory-boy`); this aligns with WD-CONT-03 ("no dev tools in image") for Phase 3
- **Coverage HTML output** — `htmlcov/` should be added to `.gitignore` (not `.coverage` — that's already typically gitignored)

</code_context>

<specifics>
## Specific Ideas

- Fakes should mimic real services' "multiple_results" wrapper pattern (`{"multiple_results": True, "results": [...]}` for >1 match, single dict for 1 match, `None` for 0 matches) — see `BaseSearchService` contract
- Test data realism: fake LDAP records must include `sAMAccountName`, `mail`, `displayName`, `memberOf` at minimum (the orchestrator reads these); fake Graph records must include `userPrincipalName`, `assignedLicenses`, `signInActivity`; fake Genesys records must include `id`, `email`, `routingStatus`
- The Phase 4 Keycloak migration will rewrite the auth tests (D-13 caveat) — call this out in PLAN.md so it's not a surprise

</specifics>

<deferred>
## Deferred Ideas

- **Blueprint hardening phase** — Targeted tests for `app/blueprints/search/__init__.py` (2720 lines) and `app/blueprints/admin/database.py` (2532 lines). Both are too large to cover meaningfully in Phase 2. Candidate for a post-integration follow-up phase or roadmap backlog item.
- **CI pipeline** — Phase 2 ships pre-push enforcement only. A real CI pipeline (GitHub Actions / SandCastle webhook trigger) belongs with Phase 3 (containerization + portal registration) where the deployment infra exists.
- **E2E browser tests** (Playwright/Selenium) — HTMX fragments are testable via response.data substring assertions; full browser e2e is overkill for this team size. Revisit if/when the UI grows.
- **Performance / load tests** — Out of scope. Could pair with Phase 8 (reporting) if cache hit rates need verification.
- **Mutation testing** (mutmut, cosmic-ray) — Quality multiplier, not a phase requirement. Backlog candidate.

</deferred>

---

*Phase: 02-test-suite*
*Context gathered: 2026-04-25*
</content>
</invoke>