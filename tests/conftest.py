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
    flask_app.config["RATELIMIT_ENABLED"] = False  # Phase 1 D-08 — disable Flask-Limiter in tests
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()
