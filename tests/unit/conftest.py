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
