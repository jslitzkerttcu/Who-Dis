"""Integration-test fixtures: authenticated client driving the full middleware chain.

# PHASE 4 NOTE (D-13): When Keycloak OIDC ships, replace header injection with a
# mocked OIDC callback that mints a fake ID token. The fixture's public API
# (authenticated_client / admin_client) stays the same — only the internals change.
"""
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
