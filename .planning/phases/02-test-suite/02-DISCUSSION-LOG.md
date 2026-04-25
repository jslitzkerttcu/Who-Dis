# Phase 2: Test Suite - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-25
**Phase:** 02-test-suite
**Areas discussed:** Test DB strategy, Mocking + container fakes, Merge gate enforcement, Coverage scope + fragile-file priorities

---

## Test DB Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Ephemeral Postgres (testcontainers) | Real Postgres container per session via testcontainers-python; matches prod schema exactly. Adds ~3-5s session startup; requires Docker. | ✓ |
| pytest-postgresql plugin | Local Postgres binary launched per session by plugin. No Docker, but every dev needs Postgres installed. | |
| Transactional rollback on dev DB | Each test runs in a SAVEPOINT against existing whodis_db. Zero infra; risks pollution and parallel-run conflicts. | |
| SQLite in-memory | Fastest, zero infra. JSONB and PG-specific patterns will silently diverge. | |

**User's choice:** Ephemeral Postgres (testcontainers) — recommended option.

### Per-test isolation

| Option | Description | Selected |
|--------|-------------|----------|
| Nested transaction rollback | SAVEPOINT per test, fast, standard SQLAlchemy event listener pattern. | ✓ |
| Truncate all tables between tests | Simpler model, slower. | |
| Drop + recreate schema per test | Slowest, fully isolated. | |

**User's choice:** Nested transaction rollback — recommended.

### Schema source

| Option | Description | Selected |
|--------|-------------|----------|
| Run database/create_tables.sql at session setup | Canonical SQL file, zero divergence from prod. Swap to `alembic upgrade head` in Phase 5. | ✓ |
| SQLAlchemy db.create_all() | Faster but diverges from create_tables.sql. | |

**User's choice:** Run database/create_tables.sql — recommended.

---

## Mocking + Container Fakes

| Option | Description | Selected |
|--------|-------------|----------|
| Container override with fake services | Fixture replaces ldap_service/graph_service/genesys_service in DI container with Fake* classes implementing the interfaces. Real orchestrator + real auth + fake providers. | ✓ |
| HTTP-level mocking (responses + ldap3-mock) | Mock at network boundary. Catches real request shapes; more setup per test. | |
| unittest.mock.patch per test | Familiar but scattered; doesn't match "container level" literally. | |

**User's choice:** Container override with fake services — recommended.

### Background threads

| Option | Description | Selected |
|--------|-------------|----------|
| TESTING flag gates thread startup | create_app() checks `app.config['TESTING']` and skips `.start()` calls. | ✓ |
| Test-only create_app variant | Duplicates wiring. | |
| Mock the thread classes themselves | Leaks test-awareness everywhere. | |

**User's choice:** TESTING flag gates thread startup — recommended.

### Fake data source

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable in-memory fakes | FakeLDAPService(users=[...]) per test. Easy to assert on. | ✓ |
| Static JSON fixture files | Centralized; every test must share global dataset. | |
| Recorded cassettes (vcrpy-style) | Catches schema drift but couples to recording moment. | |

**User's choice:** Configurable in-memory fakes — recommended.

### Model factories

| Option | Description | Selected |
|--------|-------------|----------|
| factory_boy | Standard, SQLAlchemy integration, SubFactory for relationships. | ✓ |
| Hand-rolled conftest fixtures | Fewer deps, more boilerplate. | |
| polyfactory | Type-hint-driven; less mature SQLAlchemy support. | |

**User's choice:** factory_boy — recommended.

---

## Merge Gate Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Pre-push hook running pytest -x | Fires before push, not every commit. `--no-verify` remains explicit escape. | ✓ |
| Pre-commit hook on staged files | Slower friction per commit; devs likely to skip. | |
| Makefile target + documented gate | Honor system; weakest enforcement. | |
| Both: Makefile + pre-push hook | Slight duplication but covers both flows. | |

**User's choice:** Pre-push hook running pytest -x — recommended. (Makefile target retained anyway as the single source of truth invoked by the hook — captured in D-10.)

---

## Coverage Scope + Fragile-File Priorities

| Option | Description | Selected |
|--------|-------------|----------|
| services + middleware only | Matches TEST-04 literally. Other packages still measured for visibility but don't gate. | ✓ |
| services + middleware + models | Adds models; coverage comes "free" from ORM declarations. | |
| Whole app/ package | Strictest; blueprints make 60% global a multi-phase effort. | |

**User's choice:** services + middleware only — recommended.

### Fragile-file targeted seeds

| Option | Description | Selected |
|--------|-------------|----------|
| Orchestrator + LDAP + Genesys only | Auth/search hot paths Phases 3-5 will refactor. Big blueprints deferred. | ✓ |
| All five files | Phase 2 scope blowup risk. | |
| Coverage gate only — no targeted seeds | Pure metric-driven; fragile logic might not get covered. | |

**User's choice:** Orchestrator + LDAP + Genesys only — recommended.

---

## Integration Test Depth

| Option | Description | Selected |
|--------|-------------|----------|
| Auth happy + denial + search e2e | ~6-8 tests covering auth pipeline (provision, 401, 403) + search merge happy path. | ✓ |
| Plus Phase 1 hardening checks | Adds rate-limit 429, /health, request-ID echo, config validator failures. ~12-15 tests. | |
| Minimal smoke only | One auth test, one search test. Misses denial paths. | |

**User's choice:** Auth happy + denial + search e2e — recommended.

---

## Claude's Discretion

Items deferred to the planner:
- pytest config location (`pyproject.toml`)
- Test directory layout (`tests/{unit,integration,fakes,factories,fixtures}/`)
- pytest-mock vs unittest.mock (pytest-mock)
- HTMX response assertion style (BeautifulSoup or substring)
- Test app factory approach (reuse `create_app()` with `TESTING=True`)

## Deferred Ideas

- Blueprint hardening phase (search/__init__.py 2720L, admin/database.py 2532L)
- Real CI pipeline (belongs with Phase 3 portal/webhook work)
- E2E browser tests (Playwright/Selenium) — overkill for current team size
- Performance / load tests
- Mutation testing
</content>
</invoke>