"""Root conftest: session-scoped ephemeral Postgres + Flask app, per-test SAVEPOINT, container-override helpers.

D-01: testcontainers-python boots one Postgres for the whole session.
D-02 (updated Phase 9 / Plan 04): schema loaded via `alembic upgrade head` against the test DB,
      replacing the former database/create_tables.sql approach (retired per WD-DB-05, Plan 04).
      The Phase 9 baseline migration (001_baseline_from_live_schema.py) is a no-op scaffold until
      the operator populates it during Plan 06 cutover. Until then, tests that require schema use
      db.create_all() as a fallback (see _apply_schema below).
D-03: per-test isolation via nested SAVEPOINT rollback (SQLAlchemy 2.0 public API).
D-04: container-level fake services injected via app.container.register() override.
D-06: app.config['TESTING'] is set BEFORE create_app() finishes its background-thread blocks.
"""
import os
import subprocess
import pytest
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import event
from testcontainers.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def postgres_container():
    """One ephemeral Postgres for the whole test run. Schema persists; SAVEPOINT isolates per-test."""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg


@pytest.fixture(scope="session")
def database_url(postgres_container):
    """Return the DSN for the testcontainers Postgres instance."""
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def _set_testing_env():
    """Set TESTING + WHODIS_ENCRYPTION_KEY BEFORE create_app() runs so the D-06 gates fire.

    Configuration service requires a valid Fernet key for the encryption layer to bootstrap;
    we generate a fresh per-session key so tests don't depend on developer .env contents.
    """
    os.environ["TESTING"] = "1"
    from cryptography.fernet import Fernet
    os.environ.setdefault("WHODIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    # Phase 9 OIDC (app/auth/oidc.py:init_oauth) reads these at app boot. Real values
    # are unnecessary under TESTING — Authlib only resolves the discovery URL on first
    # /auth/login, which tests don't hit. Provide stable dummies so create_app() boots.
    os.environ.setdefault("KEYCLOAK_ISSUER", "https://keycloak.test.local/realms/test")
    os.environ.setdefault("KEYCLOAK_CLIENT_ID", "whodis-test")
    os.environ.setdefault("KEYCLOAK_CLIENT_SECRET", "test-secret")
    yield


@pytest.fixture(scope="session")
def app(database_url, _set_testing_env):
    """Session-scoped Flask app pointed at the testcontainers DB.

    init_db (app/database.py) composes the URI from POSTGRES_HOST/PORT/DB/USER/PASSWORD
    env vars — we override those with the testcontainers DSN parts rather than bypass init_db.
    """
    # Parse the testcontainers DSN and project its parts into the env vars init_db reads.
    parsed = urlparse(database_url)
    os.environ["POSTGRES_HOST"] = parsed.hostname or "localhost"
    os.environ["POSTGRES_PORT"] = str(parsed.port or 5432)
    os.environ["POSTGRES_USER"] = parsed.username or "postgres"
    os.environ["POSTGRES_PASSWORD"] = parsed.password or ""
    os.environ["POSTGRES_DB"] = (parsed.path or "/postgres").lstrip("/")

    # Apply schema BEFORE create_app() so init_db's db.create_all() is a no-op.
    # Phase 9 Plan 04: database/create_tables.sql retired (WD-DB-05); schema is now
    # applied via `alembic upgrade head`. The baseline migration (001_baseline_from_live_schema.py)
    # is a no-op scaffold until Plan 06 cutover — in that case db.create_all() below catches
    # any tables Alembic doesn't create, ensuring tests remain green pre-cutover.
    #
    # Strip the SQLAlchemy driver prefix so Alembic's psycopg2 URL parser is happy.
    plain_dsn = database_url.replace("postgresql+psycopg2://", "postgresql://")
    alembic_result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "DATABASE_URL": plain_dsn},
        capture_output=True,
        text=True,
    )
    if alembic_result.returncode != 0:
        # Log but do not abort — db.create_all() below will create missing tables.
        print(f"[conftest] alembic upgrade head stderr: {alembic_result.stderr}")

    from app import create_app
    flask_app = create_app()
    flask_app.config["TESTING"] = True
    flask_app.config["RATELIMIT_ENABLED"] = False  # Phase 1 D-08
    flask_app.config["WTF_CSRF_ENABLED"] = False    # Avoid CSRF noise in test client POSTs

    with flask_app.app_context():
        yield flask_app


@pytest.fixture
def db_session(app):
    """Per-test isolation via TRUNCATE-on-teardown (D-03 simplified).

    The original SAVEPOINT-rollback approach (commits within tests stayed in
    a nested transaction, rolled back at teardown) hit two issues with
    Flask-SQLAlchemy 3.x + SQLAlchemy 2.0 in the integration-test context:
      1. Flask request handlers issue commits that escape begin_nested when
         multiple requests fire in sequence (audit_logger.commit, user.save).
      2. Replacing db.session with a per-test scoped_session leaves the next
         test's "original_session" pointing at a closed Connection.

    Trade-off: we lose strict per-test isolation INSIDE a single test (a
    request that commits halfway can be observed by the rest of the test —
    that's actually what integration tests want), but TRUNCATE on teardown
    keeps cross-test isolation intact. Performance cost: one TRUNCATE per
    test (~5ms on a small Postgres)."""
    from app.database import db

    yield db.session
    db.session.rollback()
    # TRUNCATE all user tables (preserve schema); keep internal pg_* alone.
    with db.engine.begin() as conn:
        from sqlalchemy import text
        conn.execute(text("""
            DO $$
            DECLARE r RECORD;
            BEGIN
              FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'TRUNCATE TABLE public.' || quote_ident(r.tablename) || ' RESTART IDENTITY CASCADE';
              END LOOP;
            END $$;
        """))
    # Drop identity-map references to TRUNCATEd rows. Without this, factory_boy
    # SubFactory calls in subsequent tests crash inside SA's instance_dict() lookup
    # when they encounter stale objects. close() also releases the connection so
    # the next test's first DB call gets a fresh transaction.
    db.session.close()
    db.session.remove()


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
