"""Root conftest: session-scoped ephemeral Postgres + Flask app, per-test SAVEPOINT, container-override helpers.

D-01: testcontainers-python boots one Postgres for the whole session.
D-02: schema loaded by executing database/create_tables.sql (canonical schema), not db.create_all().
D-03: per-test isolation via nested SAVEPOINT rollback (SQLAlchemy 2.0 public API).
D-04: container-level fake services injected via app.container.register() override.
D-06: app.config['TESTING'] is set BEFORE create_app() finishes its background-thread blocks.
"""
import os
import pytest
from pathlib import Path
from urllib.parse import urlparse
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

    # Apply schema BEFORE create_app() so init_db's db.create_all() is a no-op
    # against the canonical schema from database/create_tables.sql (D-02).
    import psycopg2
    conn = psycopg2.connect(database_url)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL.read_text())
            if ANALYZE_SQL.exists():
                cur.execute(ANALYZE_SQL.read_text())
    finally:
        conn.close()

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
    Avoids private Flask-SQLAlchemy session-helper APIs whose signatures vary across
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
