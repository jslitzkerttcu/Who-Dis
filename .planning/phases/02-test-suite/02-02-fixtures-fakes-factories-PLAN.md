---
phase: 02-test-suite
plan: 02
type: execute
wave: 2
depends_on: [02-01-test-infra-scaffolding]
files_modified:
  - app/__init__.py
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
autonomous: true
requirements: [TEST-01, TEST-02]
tags: [testing, pytest, fixtures, fakes, factories, di-container]

must_haves:
  truths:
    - "`app.config['TESTING']` is True when conftest creates the app, and no background threads (`token_refresh`, `cache_cleanup`, employee_profiles refresh) start under that flag"
    - "Test session boots a single ephemeral PostgreSQL container, applies `database/create_tables.sql` + `database/analyze_tables.sql`, and tears it down on session end"
    - "Each test runs inside a SAVEPOINT that rolls back at teardown — no cross-test data leak"
    - "`FakeLDAPService`, `FakeGraphService`, `FakeGenesysService` each implement the same interface as the real service (ISearchService and, for Graph/Genesys, ITokenService) and return real-shaped dicts driven by constructor data"
    - "Container override fixture replaces real services with fakes via `app.container.register('ldap_service', lambda c: FakeLDAPService(...))`"
    - "factory_boy factories for User, ApiToken, JobCode, SystemRole create rows against the SAVEPOINT-scoped session"
  artifacts:
    - path: "tests/conftest.py"
      provides: "Session-scoped Postgres + Flask app fixtures + per-test SAVEPOINT pattern + container-override helper"
      contains: "TESTING"
    - path: "tests/fakes/fake_ldap_service.py"
      provides: "FakeLDAPService implementing ISearchService"
      contains: "class FakeLDAPService"
    - path: "tests/fakes/fake_graph_service.py"
      provides: "FakeGraphService implementing ISearchService + ITokenService"
      contains: "class FakeGraphService"
    - path: "tests/fakes/fake_genesys_service.py"
      provides: "FakeGenesysService implementing ISearchService + ITokenService with too_many_results support"
      contains: "class FakeGenesysService"
    - path: "tests/factories/user.py"
      provides: "UserFactory using SQLAlchemyModelFactory"
      contains: "class UserFactory"
    - path: "app/__init__.py"
      provides: "TESTING gate skipping background-thread starts"
      contains: "app.config.get(\"TESTING\")"
  key_links:
    - from: "tests/conftest.py"
      to: "app.container"
      via: "container.register override"
      pattern: "container.register"
    - from: "tests/conftest.py"
      to: "database/create_tables.sql"
      via: "psycopg2 cursor.execute on testcontainers DSN"
      pattern: "create_tables.sql"
    - from: "app/__init__.py"
      to: "tests/conftest.py"
      via: "TESTING flag set in app.config before create_app() is invoked"
      pattern: "TESTING"
---

<objective>
Establish the runtime test harness: surgical edit to `app/__init__.py` to gate background-thread starts on `TESTING`, ephemeral Postgres + SAVEPOINT-rollback fixtures in `tests/conftest.py`, container-override fixture for fake injection (D-04), the three fake services (D-05), and factory_boy factories (D-07) for the four core models tests will need.

Purpose: After this plan, a developer can write `def test_x(client, fake_ldap, user_factory): ...` and have the full Flask app, an ephemeral DB, fake external APIs, and seed-data helpers ready — without touching any production wiring.
Output: 1 modified production file (`app/__init__.py`), 12 new test-harness files, full conftest tree, three interface-compliant fakes, four factory_boy factories.

**Phase 4 caveat (carry-over from D-13 in CONTEXT):** The auth-pipeline tests in Plan 03 will be rewritten when Phase 4 swaps Azure AD headers for Keycloak OIDC. The harness here (fakes, factories, container override, SAVEPOINT) is auth-agnostic and will be reused unchanged.
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
@.planning/phases/02-test-suite/02-PATTERNS.md
@.planning/phases/02-test-suite/02-01-SUMMARY.md
@app/__init__.py
@app/container.py
@app/database.py
@app/services/base.py
@app/interfaces/search_service.py
@app/interfaces/token_service.py
@app/models/user.py
@app/models/base.py
@app/models/api_token.py
@database/create_tables.sql

<interfaces>
<!-- The exact contracts fakes MUST satisfy. Extracted from app/interfaces/. Do NOT explore — implement against these. -->

# app/interfaces/search_service.py — ISearchService
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

class ISearchService(ABC):
    @abstractmethod
    def search_user(self, search_term: str) -> Optional[Dict[str, Any]]: ...
    @abstractmethod
    def test_connection(self) -> bool: ...
    @property
    @abstractmethod
    def service_name(self) -> str: ...

# app/interfaces/token_service.py — ITokenService
class ITokenService(ABC):
    @abstractmethod
    def get_access_token(self) -> Optional[str]: ...
    @abstractmethod
    def refresh_token_if_needed(self) -> bool: ...
    @property
    @abstractmethod
    def token_service_name(self) -> str: ...

# app/services/base.py — multiple-results wrapper contract (lines 377-394)
{"multiple_results": True, "results": results, "total": total or len(results)}

# Orchestrator extra method calls fakes must support (search_orchestrator.py):
#   - LDAP: get_user_by_dn(dn)                  (line 141-143)
#   - Genesys: get_user_by_id(genesys_user_id)  (line 155)
#   - Graph: get_user_by_id(id, include_photo=False)  (line 174-183)
#   - Graph: search_user(term, include_photo=False)

# Genesys "too_many_results" error shape (search_orchestrator.py:238-242):
{"error": "too_many_results", "message": "...", "total": N}

# app/container.py — registration / reset surface
container.register(name: str, factory: Callable[[ServiceContainer], Any]) -> None
container.reset() -> None
container.get(name: str) -> Any

# app/models/user.py — User model field surface
class User(BaseModel, TimestampMixin):
    __tablename__ = "users"
    ROLE_VIEWER = "viewer"; ROLE_EDITOR = "editor"; ROLE_ADMIN = "admin"
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    role = db.Column(db.String(50), nullable=False, default="viewer", index=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    # Email lookup (User.get_by_email) does .lower().strip() — factories must emit lowercase emails
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Surgical TESTING-flag gate in app/__init__.py (D-06)</name>
  <files>app/__init__.py, tests/__init__.py, tests/conftest.py</files>
  <read_first>
    - app/__init__.py (full file — lines 143-200 contain the three .start() call sites)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"app/__init__.py (MODIFIED — D-06 TESTING gate)" — exact line numbers and pattern)
    - app/services/token_refresh_service.py (verify .start() signature does what's claimed — daemon thread; no side effects on import)
    - app/services/cache_cleanup_service.py (same)
    - app/container.py (employee_profiles_refresh_service is registered — confirm whether it auto-starts elsewhere)
  </read_first>
  <behavior>
    - Test 1: `create_app()` invoked with `TESTING=True` env override → no thread named `TokenRefreshThread` (or equivalent) appears in `threading.enumerate()`
    - Test 2: `create_app()` invoked normally (TESTING unset) → existing behavior preserved (background services start under the existing `WERKZEUG_RUN_MAIN`/`not app.debug` gate)
    - Test 3: When TESTING=True, `audit_service.init_app(app)` STILL runs (audit logging is required by integration tests; only the background-loop `.start()` calls are skipped)
  </behavior>
  <action>
    Edit `app/__init__.py` with surgical changes ONLY at the three documented sites. Do NOT refactor surrounding code, do NOT change logging, do NOT touch the `WERKZEUG_RUN_MAIN`/`app.debug` gate condition itself.

    **Edit 1** — line ~143 block. Current code:
    ```python
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        from app.services.audit_service_postgres import audit_service
        audit_service.init_app(app)
    ```
    Leave the `audit_service.init_app(app)` line UNTOUCHED — audit logging must work in tests (integration tests in Plan 03 assert on audit rows).

    **Edit 2** — line ~173-177 (token_refresh.start()). Wrap in TESTING guard:
    ```python
    # D-06: skip background thread under TESTING; tests drive these services synchronously.
    if not app.config.get("TESTING"):
        token_refresh = app.container.get("token_refresh")
        token_refresh.app = app
        token_refresh.container = app.container
        token_refresh.start()
        app.logger.info("Token refresh background service started")
    ```

    **Edit 3** — line ~180-183 (cache_cleanup.start()). Wrap in TESTING guard:
    ```python
    # D-06: skip background thread under TESTING.
    if not app.config.get("TESTING"):
        cache_cleanup = app.container.get("cache_cleanup")
        cache_cleanup.app = app
        cache_cleanup.start()
        app.logger.info("Cache cleanup background service started")
    ```

    **Edit 4** — Same outer block contains a `genesys_cache_db.refresh_all_caches(genesys_service)` call (around line 194). Wrap that in the same TESTING guard so tests don't trigger external Genesys HTTP calls during `create_app()`:
    ```python
    if genesys_service and not app.config.get("TESTING"):
        try:
            from app.services.genesys_cache_db import genesys_cache_db
            if genesys_cache_db.needs_refresh():
                ...
    ```

    **Edit 5** — Also wrap the startup token-refresh loop (`for service in token_services: ... service.refresh_token_if_needed()`, around lines 156-170) in `if not app.config.get("TESTING"):`. Reasoning: under TESTING the token services are FAKES (registered by conftest BEFORE `create_app()` finishes? No — `create_app()` runs first then conftest swaps. So during create_app() the REAL services would be present and would attempt real HTTP token fetches. Skip under TESTING.) The container override happens AFTER `create_app()` returns; the startup loop must not fire when TESTING is set.

    **Verify:** check `app/services/employee_profiles_refresh_service.py` and grep for `.start()` calls of it across the codebase. PATTERNS.md notes it's registered in container but says "isn't started in __init__.py — verify in the plan whether it auto-starts elsewhere." Run:
    ```
    grep -rn "employee_profiles_refresh.*start\|employee_profiles.*\.start(" app/ scripts/
    ```
    If a `.start()` call exists, gate it under TESTING the same way. If no call exists (registered-but-not-started), no edit needed — note in summary.

    Then create `tests/__init__.py` (empty file) and `tests/conftest.py` with the bare TESTING-gate test fixture (full conftest body comes in Task 2):

    ```python
    # tests/conftest.py — Task 1 stub (Task 2 expands this with DB + container fixtures)
    import os
    import pytest
    from app import create_app

    @pytest.fixture(scope="session")
    def app():
        """Session-scoped Flask app with TESTING=True so D-06 gates background threads."""
        os.environ["TESTING"] = "1"  # belt-and-suspenders; conftest sets app.config too
        flask_app = create_app()
        flask_app.config["TESTING"] = True
        flask_app.config["RATELIMIT_ENABLED"] = False  # Phase 1 D-08 — disable Flask-Limiter in tests per CONTEXT canonical_refs
        yield flask_app

    @pytest.fixture
    def client(app):
        return app.test_client()
    ```

    **CRITICAL:** Per Discretion ("reuse production `create_app()` with `TESTING=True` config override; do not introduce a separate `create_test_app()`"), do NOT create a `create_test_app()` function. The TESTING flag is the only switch.
  </action>
  <verify>
    <automated>test "$(grep -c 'if not app.config.get("TESTING"):' app/__init__.py)" -ge 3</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "if not app.config.get(\"TESTING\"):" app/__init__.py` returns at least 3 (token_refresh, cache_cleanup, genesys_cache_db.refresh_all_caches block, and the startup token-refresh loop — at minimum 3 distinct guards).
    - `audit_service.init_app(app)` line is NOT wrapped in a TESTING guard (still runs under TESTING).
    - The original `if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:` line is unchanged in form.
    - `tests/__init__.py` exists (empty file is fine).
    - `tests/conftest.py` exists with `app` and `client` fixtures and sets `RATELIMIT_ENABLED=False` and `TESTING=True`.
    - `python -c "from app import create_app; a = create_app(); a.config['TESTING']=True; print('OK')"` does NOT print "Token refresh background service started" or "Cache cleanup background service started" when TESTING is pre-set in env (since the gates fire on the config flag set inside create_app once the conftest fixture runs — for this test, set `app.config['TESTING']=True` BEFORE the gated block executes; if create_app reads config before the override is possible, document the call order in the SUMMARY and adjust by checking `os.environ.get("TESTING")` instead).
    - mypy passes: `mypy app/__init__.py` clean (no new errors introduced).
    - ruff passes: `ruff check app/__init__.py` clean.
    - No production behavior change when TESTING is unset: `grep -A1 "if not app.config.get(\"TESTING\"):" app/__init__.py | grep -c "container.get"` returns ≥2 (proving the gates wrap the existing container.get() lines, not replace them).
  </acceptance_criteria>
  <done>Production code paths preserved exactly; TESTING-gated branches skip background threads, startup token refresh, and Genesys cache warmup; tests/conftest.py stub yields a TESTING+RATELIMIT_ENABLED=False app fixture.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Ephemeral Postgres + SAVEPOINT conftest + container-override fixture</name>
  <files>tests/conftest.py, tests/unit/__init__.py, tests/unit/conftest.py, tests/integration/__init__.py, tests/integration/conftest.py</files>
  <read_first>
    - tests/conftest.py (the stub from Task 1 — expand it, do not rewrite from scratch)
    - app/__init__.py (lines 71-90 — init_db pattern; understand how SQLALCHEMY_DATABASE_URI is read)
    - app/database.py (db.session lifecycle, init_db signature)
    - database/create_tables.sql (the schema source per D-02 — verify it exists and is complete)
    - database/analyze_tables.sql (companion file per code_context "ANALYZE post-creation")
    - scripts/verify_encrypted_config.py (lines 7-15 — psycopg2.connect + raw-SQL execution pattern)
    - app/container.py (lines 27-37 register(), lines 88-92 reset())
    - app/middleware/authentication_handler.py (lines 35-47 — header name comes from `auth.principal_header` config; default `X-MS-CLIENT-PRINCIPAL-NAME`)
    - app/middleware/auth.py (lines 59-87 — `authenticate()` orchestrator; integration conftest uses it via real header injection)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"tests/conftest.py", §"tests/unit/conftest.py", §"tests/integration/conftest.py" — pattern bodies)
  </read_first>
  <behavior>
    - Test 1: `pytest --collect-only` succeeds (fixtures parse cleanly, no import errors)
    - Test 2: A trivial `def test_db(db_session, user_factory): user_factory.create()` runs, persists, and the row is gone after teardown (SAVEPOINT rollback proven)
    - Test 3: `def test_override(app, fake_ldap_factory): app.container.register('ldap_service', lambda c: fake_ldap_factory(users=[...])); assert app.container.get('ldap_service').search_user('x') == ...` works; the next test gets the real (or default-fake) ldap service back via container.reset() in fixture teardown
    - Test 4: `def test_authenticated(authenticated_client): r = authenticated_client.get('/'); assert r.status_code == 200` works — header is set, user auto-provisioned
  </behavior>
  <action>
    **Expand `tests/conftest.py`** to the full session+function harness. The stub from Task 1 only had `app` and `client`; replace with this complete version (preserve the TESTING+RATELIMIT_ENABLED config from Task 1):

    ```python
    """Root conftest: session-scoped ephemeral Postgres + Flask app, per-test SAVEPOINT, container-override helpers."""
    import os
    import pytest
    from pathlib import Path
    from sqlalchemy import event
    from testcontainers.postgres import PostgresContainer

    REPO_ROOT = Path(__file__).resolve().parent.parent
    SCHEMA_SQL = REPO_ROOT / "database" / "create_tables.sql"
    ANALYZE_SQL = REPO_ROOT / "database" / "analyze_tables.sql"


    @pytest.fixture(scope="session")
    def postgres_container():
        """One ephemeral Postgres for the whole test run. Schema persists; SAVEPOINT isolates per-test."""
        with PostgresContainer("postgres:15-alpine") as pg:
            yield pg


    @pytest.fixture(scope="session")
    def database_url(postgres_container):
        return postgres_container.get_connection_url()


    @pytest.fixture(scope="session", autouse=True)
    def _set_testing_env():
        """Set TESTING + DB env vars BEFORE create_app() runs so the D-06 gates fire."""
        os.environ["TESTING"] = "1"
        # WHODIS_ENCRYPTION_KEY required by encryption service bootstrap; generate per session.
        from cryptography.fernet import Fernet
        os.environ.setdefault("WHODIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
        yield


    @pytest.fixture(scope="session")
    def app(database_url, _set_testing_env):
        """Session-scoped Flask app pointed at the testcontainers DB."""
        # Apply schema BEFORE create_app() so init_db succeeds.
        import psycopg2
        with psycopg2.connect(database_url) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(SCHEMA_SQL.read_text())
                if ANALYZE_SQL.exists():
                    cur.execute(ANALYZE_SQL.read_text())

        os.environ["SQLALCHEMY_DATABASE_URI"] = database_url
        # Or whichever env var app/database.py reads — verify in app/database.py during impl.

        from app import create_app
        flask_app = create_app()
        flask_app.config["TESTING"] = True
        flask_app.config["RATELIMIT_ENABLED"] = False  # Phase 1 D-08
        flask_app.config["WTF_CSRF_ENABLED"] = False    # Avoid CSRF noise in test client POSTs

        with flask_app.app_context():
            yield flask_app


    @pytest.fixture
    def db_session(app):
        """SAVEPOINT-per-test (D-03). Standard SQLAlchemy 2.0 nested-transaction pattern.

        Uses the public sessionmaker + scoped_session API per the SQLAlchemy 2.0 docs:
        https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites
        Avoids the private `db._make_scoped_session` helper, whose signature varies across
        SQLAlchemy 2.0.x patch releases.
        """
        from sqlalchemy.orm import scoped_session, sessionmaker
        from app.database import db

        connection = db.engine.connect()
        transaction = connection.begin()

        # Public API: bind a fresh sessionmaker to the open connection, wrap as scoped_session
        # so Flask-SQLAlchemy's `db.session` proxy keeps working for the duration of the test.
        SessionFactory = sessionmaker(bind=connection)
        session = scoped_session(SessionFactory)
        original_session = db.session
        db.session = session

        nested = connection.begin_nested()

        @event.listens_for(session, "after_transaction_end")
        def restart_savepoint(sess, trans):
            nonlocal nested
            if trans.nested and not trans._parent.nested:
                nested = connection.begin_nested()

        try:
            yield session
        finally:
            session.remove()
            transaction.rollback()
            connection.close()
            db.session = original_session


    @pytest.fixture
    def client(app, db_session):
        """Test client bound to the SAVEPOINT-scoped session."""
        return app.test_client()


    @pytest.fixture
    def container_reset(app):
        """Snapshot container state, restore after test (so fakes from one test don't leak into next)."""
        snapshot = dict(app.container._factories)  # shallow copy of the factory map
        yield app.container
        app.container._factories = snapshot
        app.container.reset()  # drop singletons cached during the test


    # --- Fake-service convenience fixtures ---
    @pytest.fixture
    def fake_ldap(container_reset):
        from tests.fakes.fake_ldap_service import FakeLDAPService
        instance = FakeLDAPService()
        container_reset.register("ldap_service", lambda c: instance)
        container_reset.reset()
        return instance


    @pytest.fixture
    def fake_graph(container_reset):
        from tests.fakes.fake_graph_service import FakeGraphService
        instance = FakeGraphService()
        container_reset.register("graph_service", lambda c: instance)
        container_reset.reset()
        return instance


    @pytest.fixture
    def fake_genesys(container_reset):
        from tests.fakes.fake_genesys_service import FakeGenesysService
        instance = FakeGenesysService()
        container_reset.register("genesys_service", lambda c: instance)
        container_reset.reset()
        return instance
    ```

    **NOTE on env-var name for the DB URL:** `app/__init__.py` line 77 references `SQLALCHEMY_DATABASE_URI` from app.config. Inspect `app/database.py` to find the actual env-var-to-config mapping (likely `POSTGRES_HOST`/`POSTGRES_USER`/etc. composed in `init_db`). Adjust the conftest to set whatever env vars `init_db` actually reads — DO NOT bypass `init_db`, override its inputs. Document the exact env-var names you set in the SUMMARY.

    **Create `tests/unit/__init__.py`** (empty) and `tests/unit/conftest.py`:

    ```python
    """Unit-test fixtures: lightweight request-context for orchestrator tests that use copy_current_request_context."""
    import pytest
    from flask import g

    @pytest.fixture
    def request_context(app):
        """Yield inside an app.test_request_context() with g.user populated."""
        with app.test_request_context():
            g.user = "test@example.com"
            g.role = "admin"
            yield
    ```

    **Create `tests/integration/__init__.py`** (empty) and `tests/integration/conftest.py`:

    ```python
    """Integration-test fixtures: authenticated client driving the full middleware chain."""
    import pytest


    @pytest.fixture
    def authenticated_client(client, db_session):
        """Test client preconfigured with the principal header so @auth_required succeeds.

        Uses the configured `auth.principal_header` config (default X-MS-CLIENT-PRINCIPAL-NAME).
        Auto-provisioner creates the user with role=viewer on first request (per D-13).
        """
        from app.services.configuration_service import config_get
        header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
        client.environ_base[f"HTTP_{header_name.upper().replace('-', '_')}"] = "test-viewer@example.com"
        return client


    @pytest.fixture
    def admin_client(client, db_session):
        """Same as authenticated_client but pre-seeds an admin user so @require_role('admin') passes."""
        from app.services.configuration_service import config_get
        from tests.factories.user import UserFactory
        UserFactory(email="test-admin@example.com", role="admin")
        header_name = config_get("auth.principal_header", "X-MS-CLIENT-PRINCIPAL-NAME")
        client.environ_base[f"HTTP_{header_name.upper().replace('-', '_')}"] = "test-admin@example.com"
        return client
    ```

    **Phase 4 marker comment** at top of `tests/integration/conftest.py`:
    ```python
    # PHASE 4 NOTE (D-13): When Keycloak OIDC ships, replace header injection with a
    # mocked OIDC callback that mints a fake ID token. The fixture's public API
    # (authenticated_client / admin_client) stays the same — only the internals change.
    ```
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -c "import ast; ast.parse(open('tests/conftest.py').read()); ast.parse(open('tests/unit/conftest.py').read()); ast.parse(open('tests/integration/conftest.py').read()); print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - All five files exist: `tests/conftest.py`, `tests/unit/__init__.py`, `tests/unit/conftest.py`, `tests/integration/__init__.py`, `tests/integration/conftest.py`.
    - `grep -c "PostgresContainer" tests/conftest.py` returns 1.
    - `grep -c "create_tables.sql" tests/conftest.py` returns 1.
    - `grep -c "begin_nested" tests/conftest.py` returns 1 (SAVEPOINT pattern); `grep -c "_make_scoped_session" tests/conftest.py` returns 0 (uses public sessionmaker API per SQLAlchemy 2.0 docs); `grep -c "from sqlalchemy.orm import scoped_session, sessionmaker" tests/conftest.py` returns 1.
    - `grep -c "RATELIMIT_ENABLED" tests/conftest.py` returns 1 (Phase 1 D-08 guarded).
    - `grep -c "container.register" tests/conftest.py` returns ≥3 (one per fake convenience fixture).
    - `grep -c "PHASE 4 NOTE" tests/integration/conftest.py` returns 1.
    - `grep -c "X-MS-CLIENT-PRINCIPAL-NAME\|principal_header" tests/integration/conftest.py` returns ≥1.
    - `python -c "import ast; ast.parse(open('tests/conftest.py').read())"` succeeds (valid Python).
    - `pytest --collect-only` runs without ImportError or fixture-resolution errors (zero tests collected is acceptable until Plan 03 adds tests).
  </acceptance_criteria>
  <done>conftest tree fully wired: ephemeral Postgres boots once, SAVEPOINT isolates each test, container-override fixtures inject fakes, authenticated client drives the real middleware chain.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Three fake services + four factory_boy factories</name>
  <files>tests/fakes/__init__.py, tests/fakes/fake_ldap_service.py, tests/fakes/fake_graph_service.py, tests/fakes/fake_genesys_service.py, tests/factories/__init__.py, tests/factories/user.py, tests/factories/api_token.py, tests/factories/job_code.py, tests/factories/system_role.py</files>
  <read_first>
    - app/interfaces/search_service.py (full file — ISearchService contract)
    - app/interfaces/token_service.py (full file — ITokenService contract)
    - app/services/ldap_service.py (lines 18-80 — class signature + service_name property + test_connection)
    - app/services/graph_service.py (class signature + search_user signature with include_photo + get_user_by_id)
    - app/services/genesys_service.py (lines 13-15 inheritance, refresh_token_if_needed)
    - app/services/search_orchestrator.py (lines 141-183, 198-203, 238-242 — orchestrator's call shapes + multiple_results switch + too_many_results)
    - app/services/base.py (lines 377-394 — multiple-results wrapper exact dict shape)
    - app/models/user.py (full file — User model + ROLE_* constants + email lookup behavior)
    - app/models/api_token.py (full file — ApiToken fields, expires_at semantics)
    - app/models/job_code.py (full file — JobCode field surface)
    - app/models/system_role.py (full file — SystemRole field surface)
    - app/models/base.py (lines 15-29 — TimestampMixin defaults; factories should NOT set created_at/updated_at)
    - .planning/phases/02-test-suite/02-PATTERNS.md (§"tests/fakes/*", §"tests/factories/*" — pattern bodies)
    - .planning/phases/02-test-suite/02-CONTEXT.md (D-04, D-05, D-07; "Specific Ideas" §1-§2 for required fake fields)
  </read_first>
  <behavior>
    - Fake LDAP: constructed with `users=[{"sAMAccountName":"jdoe","mail":"jdoe@x.com","displayName":"J Doe","memberOf":[]}]` → `search_user("jdoe")` returns that single dict; `search_user("zz")` returns None; `search_user("user")` (matches multiple) returns `{"multiple_results": True, "results": [...], "total": N}`
    - Fake Graph: `search_user("jdoe")` returns dict with `userPrincipalName`, `assignedLicenses`, `signInActivity`; `get_user_by_id(id, include_photo=False)` returns same shape; `get_access_token()` returns `"fake-graph-token"`; `refresh_token_if_needed()` returns True
    - Fake Genesys: `search_user("jdoe")` returns dict with `id`, `email`, `routingStatus`; `get_user_by_id(id)` returns same; `refresh_token_if_needed()` returns True; constructed with `too_many=True` → returns `{"error": "too_many_results", "message": "...", "total": 999}`
    - UserFactory: `UserFactory()` creates a row with email like `user1@test.local` (lowercase, sequence-driven), role=viewer, is_active=True; `UserFactory(role="admin")` overrides role
    - ApiTokenFactory: default `expires_at = now + 1 hour`; `ApiTokenFactory(expiring=True)` sets `expires_at = now + 5 minutes` (within token-refresh service's 10-minute threshold)
  </behavior>
  <action>
    Create `tests/fakes/__init__.py` (empty) and the three fake modules.

    **`tests/fakes/fake_ldap_service.py`:**
    ```python
    """In-memory ISearchService implementation for tests (D-04, D-05).

    Implements ISearchService directly — does NOT inherit BaseSearchService (per code_context:
    avoids dragging real HTTP/timeout logic into tests).
    """
    from typing import Any, Dict, List, Optional
    from app.interfaces.search_service import ISearchService


    class FakeLDAPService(ISearchService):
        def __init__(self, users: Optional[List[Dict[str, Any]]] = None) -> None:
            self._users: List[Dict[str, Any]] = list(users or [])

        @property
        def service_name(self) -> str:
            return "ldap"

        def test_connection(self) -> bool:
            return True

        def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
            term = (search_term or "").lower()
            matches = [
                u for u in self._users
                if term in u.get("sAMAccountName", "").lower()
                or term in u.get("mail", "").lower()
                or term in u.get("displayName", "").lower()
            ]
            if not matches:
                return None
            if len(matches) == 1:
                return matches[0]
            # Multiple-results wrapper per app/services/base.py:377-394
            return {"multiple_results": True, "results": matches, "total": len(matches)}

        def get_user_by_dn(self, dn: str) -> Optional[Dict[str, Any]]:
            """Orchestrator second-pass lookup (search_orchestrator.py:141-143)."""
            for u in self._users:
                if u.get("distinguishedName") == dn or u.get("dn") == dn:
                    return u
            return None

        # --- Test helpers ---
        def add_user(self, user: Dict[str, Any]) -> None:
            self._users.append(user)
    ```

    **`tests/fakes/fake_graph_service.py`:**
    ```python
    """Fake Graph service implementing ISearchService + ITokenService."""
    from typing import Any, Dict, List, Optional
    from app.interfaces.search_service import ISearchService
    from app.interfaces.token_service import ITokenService


    class FakeGraphService(ISearchService, ITokenService):
        def __init__(self, users: Optional[List[Dict[str, Any]]] = None) -> None:
            self._users: List[Dict[str, Any]] = list(users or [])

        @property
        def service_name(self) -> str:
            return "graph"

        @property
        def token_service_name(self) -> str:
            return "graph"

        def test_connection(self) -> bool:
            return True

        def get_access_token(self) -> Optional[str]:
            return "fake-graph-token"

        def refresh_token_if_needed(self) -> bool:
            return True

        def search_user(self, search_term: str, include_photo: bool = False) -> Optional[Dict[str, Any]]:
            term = (search_term or "").lower()
            matches = [
                u for u in self._users
                if term in u.get("userPrincipalName", "").lower()
                or term in u.get("displayName", "").lower()
                or term in u.get("mail", "").lower()
            ]
            if not matches:
                return None
            if len(matches) == 1:
                return matches[0]
            return {"multiple_results": True, "results": matches, "total": len(matches)}

        def get_user_by_id(self, user_id: str, include_photo: bool = False) -> Optional[Dict[str, Any]]:
            for u in self._users:
                if u.get("id") == user_id or u.get("userPrincipalName") == user_id:
                    return u
            return None

        def add_user(self, user: Dict[str, Any]) -> None:
            self._users.append(user)
    ```

    **`tests/fakes/fake_genesys_service.py`:**
    ```python
    """Fake Genesys service. Supports the orchestrator's too_many_results degraded path."""
    from typing import Any, Dict, List, Optional
    from app.interfaces.search_service import ISearchService
    from app.interfaces.token_service import ITokenService


    class FakeGenesysService(ISearchService, ITokenService):
        def __init__(
            self,
            users: Optional[List[Dict[str, Any]]] = None,
            too_many: bool = False,
            too_many_total: int = 999,
        ) -> None:
            self._users: List[Dict[str, Any]] = list(users or [])
            self._too_many = too_many
            self._too_many_total = too_many_total

        @property
        def service_name(self) -> str:
            return "genesys"

        @property
        def token_service_name(self) -> str:
            return "genesys"

        def test_connection(self) -> bool:
            return True

        def get_access_token(self) -> Optional[str]:
            return "fake-genesys-token"

        def refresh_token_if_needed(self) -> bool:
            return True

        def search_user(self, search_term: str) -> Optional[Dict[str, Any]]:
            if self._too_many:
                # Exact shape from search_orchestrator.py:238-242
                return {
                    "error": "too_many_results",
                    "message": f"Search returned {self._too_many_total} results; refine the term.",
                    "total": self._too_many_total,
                }
            term = (search_term or "").lower()
            matches = [
                u for u in self._users
                if term in u.get("email", "").lower() or term in u.get("name", "").lower()
            ]
            if not matches:
                return None
            if len(matches) == 1:
                return matches[0]
            return {"multiple_results": True, "results": matches, "total": len(matches)}

        def get_user_by_id(self, genesys_user_id: str) -> Optional[Dict[str, Any]]:
            for u in self._users:
                if u.get("id") == genesys_user_id:
                    return u
            return None

        def add_user(self, user: Dict[str, Any]) -> None:
            self._users.append(user)
    ```

    Then create `tests/factories/__init__.py` (empty) and the four factory modules.

    **`tests/factories/user.py`:**
    ```python
    """factory_boy factory for User model (D-07). Emails are lowercase to satisfy User.get_by_email() contract."""
    import factory
    from factory.alchemy import SQLAlchemyModelFactory
    from app.database import db
    from app.models.user import User


    class UserFactory(SQLAlchemyModelFactory):
        class Meta:
            model = User
            sqlalchemy_session = db.session
            sqlalchemy_session_persistence = "flush"

        email = factory.Sequence(lambda n: f"user{n}@test.local")
        role = User.ROLE_VIEWER
        is_active = True
    ```

    **`tests/factories/api_token.py`:**
    ```python
    """factory_boy factory for ApiToken. Default expires_at = now+1h; expiring variant within refresh threshold."""
    from datetime import datetime, timedelta, timezone
    import factory
    from factory.alchemy import SQLAlchemyModelFactory
    from app.database import db
    from app.models.api_token import ApiToken


    class ApiTokenFactory(SQLAlchemyModelFactory):
        class Meta:
            model = ApiToken
            sqlalchemy_session = db.session
            sqlalchemy_session_persistence = "flush"

        service_name = "graph"
        access_token = factory.Sequence(lambda n: f"fake-token-{n}")
        expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(hours=1))

        class Params:
            # Trait: token within the 10-minute refresh threshold (token_refresh_service.py:92-102)
            expiring = factory.Trait(
                expires_at=factory.LazyFunction(
                    lambda: datetime.now(timezone.utc) + timedelta(minutes=5)
                )
            )
    ```

    **`tests/factories/job_code.py`** — same pattern, fields per `app/models/job_code.py`. Generate `code` via `factory.Sequence(lambda n: f"JC{n:04d}")`. Verify model fields by reading the model file first; only set REQUIRED columns.

    **`tests/factories/system_role.py`** — same pattern, fields per `app/models/system_role.py`. Generate `name` via `factory.Sequence(lambda n: f"role-{n}")`. Verify model fields by reading the model file first; only set REQUIRED columns.

    **DO NOT** set `created_at` or `updated_at` in any factory — TimestampMixin handles those (per PATTERNS.md).
  </action>
  <verify>
    <automated>cd C:/repos/Who-Dis &amp;&amp; python -c "import ast; [ast.parse(open(f).read()) for f in ['tests/fakes/fake_ldap_service.py','tests/fakes/fake_graph_service.py','tests/fakes/fake_genesys_service.py','tests/factories/user.py','tests/factories/api_token.py','tests/factories/job_code.py','tests/factories/system_role.py']]; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - All 9 files exist (3 fake modules + `__init__.py`, 4 factory modules + `__init__.py`).
    - `grep -c "class FakeLDAPService(ISearchService)" tests/fakes/fake_ldap_service.py` returns 1.
    - `grep -c "class FakeGraphService(ISearchService, ITokenService)" tests/fakes/fake_graph_service.py` returns 1.
    - `grep -c "class FakeGenesysService(ISearchService, ITokenService)" tests/fakes/fake_genesys_service.py` returns 1.
    - `grep -rc "BaseSearchService\|BaseAPIService" tests/fakes/ | awk -F: '{sum+=$2} END {print sum}'` returns 0 (fakes do NOT inherit base service classes — per code_context).
    - `grep -c "multiple_results" tests/fakes/fake_ldap_service.py` returns 1; same for fake_graph and fake_genesys.
    - `grep -c "too_many_results" tests/fakes/fake_genesys_service.py` returns 1.
    - `grep -c "get_user_by_dn" tests/fakes/fake_ldap_service.py` returns 1.
    - `grep -c "get_user_by_id" tests/fakes/fake_graph_service.py` returns 1; same for fake_genesys.
    - `grep -c "include_photo" tests/fakes/fake_graph_service.py` returns ≥2 (search_user signature + get_user_by_id signature).
    - `grep -c "class UserFactory(SQLAlchemyModelFactory)" tests/factories/user.py` returns 1.
    - `grep -c "factory.Sequence" tests/factories/user.py` returns ≥1 (email sequence for unique constraint).
    - `grep -c "User.ROLE_VIEWER" tests/factories/user.py` returns 1.
    - `grep -c "expiring = factory.Trait" tests/factories/api_token.py` returns 1.
    - `grep -rc "created_at\|updated_at" tests/factories/ | awk -F: '{sum+=$2} END {print sum}'` returns 0 (factories defer to TimestampMixin).
    - All 7 Python files parse cleanly (`python -c "import ast; ast.parse(...)"`).
    - `pytest --collect-only` runs without ImportError on these modules.
  </acceptance_criteria>
  <done>Three fakes implement the exact interfaces, return realistic dict shapes, and support the orchestrator's degraded paths. Four factories generate valid model rows against the SAVEPOINT-scoped session.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| test process → ephemeral DB | testcontainers Postgres only reachable from local Docker; no exposure to host network beyond pytest process |
| test fakes → app container | Fakes implement same interface as real services; cannot escape container scope; reset between tests prevents leak |
| app/__init__.py TESTING gate | Production behavior preserved when TESTING is unset; gate is one-line `if not app.config.get("TESTING")` per call site |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04 | T (Tampering) | TESTING flag accidentally left on in production | mitigate | TESTING is read from `app.config`, only set by `tests/conftest.py`; production `create_app()` never sets it. Acceptance criteria assert audit_service.init_app() still runs under TESTING (so prod paths exercise). |
| T-02-05 | I (Information Disclosure) | testcontainers Postgres exposes random port to host | accept | Random port, ephemeral lifetime (test session only), no real data; localhost-only by Docker default. |
| T-02-06 | D (Denial of Service) | SAVEPOINT pattern leaks connections under test failure | mitigate | conftest fixture uses try/yield/finally implicit teardown; `connection.close()` runs on test failure too (pytest fixture semantics). Verified by Plan 04 full-suite run with no `connection pool exhausted` warnings. |
| T-02-07 | S (Spoofing) | Header injection in integration tests bypasses real Azure AD | accept | Tests intentionally inject the header to drive the real middleware chain. Phase 4 will rewrite when Keycloak ships (D-13 caveat). Production header trust comes from Azure App Service infrastructure, not the app — tests can inject freely. |
</threat_model>

<verification>
- `tests/conftest.py` parses (Python AST valid)
- `pytest --collect-only` returns success (zero tests collected is acceptable)
- `python -c "from app import create_app; a = create_app(); a.config['TESTING']=True"` — no exceptions, no background-thread log lines
- `mypy app/__init__.py` clean (no new errors introduced by the surgical edits)
- `ruff check app/__init__.py tests/` clean
</verification>

<success_criteria>
- All Task 1-3 acceptance criteria pass
- TESTING flag wired through 3+ background-thread sites in `app/__init__.py`
- Ephemeral Postgres + SAVEPOINT-rollback pattern in conftest
- Container-override fixtures expose `fake_ldap`, `fake_graph`, `fake_genesys` by name
- Authenticated client fixture drives the real middleware chain via header injection
- All 3 fakes implement the canonical interfaces (no base-class inheritance)
- All 4 factories use SQLAlchemyModelFactory bound to db.session
- Phase 4 caveat documented at top of `tests/integration/conftest.py`
</success_criteria>

<output>
After completion, create `.planning/phases/02-test-suite/02-02-SUMMARY.md` documenting:
- Exact line numbers in `app/__init__.py` where the TESTING gates were added
- Whether `employee_profiles_refresh_service.start()` exists anywhere (and was gated) or doesn't exist
- The exact env-var name(s) used to point `init_db` at the testcontainers DSN
- Confirmation that `audit_service.init_app(app)` is NOT gated (still runs under TESTING)
- Fake-class inheritance proof (just `(ISearchService)` or `(ISearchService, ITokenService)`, no Base*)
- Factory list with the model each binds to
</output>
