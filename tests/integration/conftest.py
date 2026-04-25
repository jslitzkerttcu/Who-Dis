"""Integration-test fixtures: authenticated client driving the full middleware chain.

Phase 9 (WD-AUTH-01): identity now comes from the Flask session populated by the
Authlib OIDC callback (app/auth/oidc.py). Header-based auth has been deleted.
These fixtures populate the session directly via `client.session_transaction()`
to simulate a completed OIDC callback — the public fixture API is unchanged.
"""
import pytest


def _login(client, email: str, roles: list[str]) -> None:
    """Populate the Flask session with the minimal claims set written by the
    OIDC callback in app/auth/oidc.py:authorize."""
    with client.session_transaction() as sess:
        sess["user"] = {
            "email": email,
            "sub": f"test-sub-{email}",
            "name": email.split("@")[0],
            "roles": roles,
        }


@pytest.fixture
def authenticated_client(client, db_session):
    """Client whose session looks like a successful OIDC callback for an unknown
    user. role_resolver will find no DB row and authenticate() will return False —
    that's what the insufficient-role test asserts on."""
    _login(client, "test-viewer@example.com", roles=["viewer"])
    return client


@pytest.fixture
def admin_client(client, db_session):
    """Same as authenticated_client but pre-seeds an admin user so @require_role('admin') passes."""
    from tests.factories.user import UserFactory
    UserFactory(email="test-admin@example.com", role="admin")
    _login(client, "test-admin@example.com", roles=["admin"])
    return client
