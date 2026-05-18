"""Unit tests for AD write operation endpoints (Phase 9, Plan 02).

Tests cover:
- Reason validation (400 on empty/short reasons)
- Successful unlock/enable/disable (200 + HX-Trigger showToast)
- Reset-password returns HTML fragment with password
- Service failure propagation (500)
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client(app):
    """Flask test client with CSRF disabled."""
    app.config["WTF_CSRF_ENABLED"] = False
    return app.test_client()


@pytest.fixture
def mock_write_ops():
    """Mock WriteOperationsService injected into container."""
    mock = MagicMock()
    return mock


@pytest.fixture(autouse=True)
def patch_auth_and_service(app, mock_write_ops):
    """Bypass auth decorators and inject mock write_operations service."""
    # Register mock in container
    app.container.register("write_operations", lambda c: mock_write_ops)

    # Patch require_role to be a no-op for testing
    with patch("app.blueprints.search.write_routes.require_role", lambda role: lambda f: f):
        # Patch csrf_double_submit.protect to be a no-op
        with patch(
            "app.blueprints.search.write_routes.csrf_double_submit"
        ) as mock_csrf:
            mock_csrf.protect = lambda f: f
            yield


@pytest.fixture(autouse=True)
def fake_user(app):
    """Set g.user and g.role for all requests in this module."""
    @app.before_request
    def _set_fake_user():
        from flask import g
        g.user = "admin@test.com"
        g.role = "admin"

    yield

    # Remove the before_request handler after tests
    app.before_request_funcs.setdefault(None, [])
    if _set_fake_user in app.before_request_funcs.get(None, []):
        app.before_request_funcs[None].remove(_set_fake_user)


class TestReasonValidation:
    """Reason must be >= 3 chars (stripped) for all write endpoints."""

    @pytest.mark.parametrize("endpoint", [
        "/search/api/write/unlock",
        "/search/api/write/reset-password",
        "/search/api/write/enable",
        "/search/api/write/disable",
    ])
    def test_empty_reason_returns_400(self, client, endpoint):
        resp = client.post(endpoint, data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "",
        })
        assert resp.status_code == 400
        assert b"Reason must be at least 3 characters" in resp.data

    @pytest.mark.parametrize("endpoint", [
        "/search/api/write/unlock",
        "/search/api/write/reset-password",
        "/search/api/write/enable",
        "/search/api/write/disable",
    ])
    def test_short_reason_returns_400(self, client, endpoint):
        resp = client.post(endpoint, data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "ab",
        })
        assert resp.status_code == 400

    @pytest.mark.parametrize("endpoint", [
        "/search/api/write/unlock",
        "/search/api/write/reset-password",
        "/search/api/write/enable",
        "/search/api/write/disable",
    ])
    def test_whitespace_only_reason_returns_400(self, client, endpoint):
        resp = client.post(endpoint, data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "   ",
        })
        assert resp.status_code == 400


class TestUnlockEndpoint:
    """POST /search/api/write/unlock."""

    def test_successful_unlock(self, client, mock_write_ops):
        mock_write_ops.unlock_account.return_value = {
            "success": True,
            "message": "Account unlocked",
        }

        resp = client.post("/search/api/write/unlock", data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "User called, needs access",
        })

        assert resp.status_code == 200
        assert resp.data == b""
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "Account unlocked successfully"
        assert trigger["showToast"]["type"] == "success"

    def test_failed_unlock(self, client, mock_write_ops):
        mock_write_ops.unlock_account.return_value = {
            "success": False,
            "error": "LDAP connection failed",
        }

        resp = client.post("/search/api/write/unlock", data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "User locked out",
        })

        assert resp.status_code == 500
        assert b"LDAP connection failed" in resp.data


class TestResetPasswordEndpoint:
    """POST /search/api/write/reset-password."""

    def test_successful_reset_returns_html_with_password(self, client, mock_write_ops):
        mock_write_ops.reset_password.return_value = {
            "success": True,
            "data": {"password": "Sunset42!"},
        }

        resp = client.post("/search/api/write/reset-password", data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "Forgot their password",
        })

        assert resp.status_code == 200
        # Response body is the password banner HTML
        assert b"Sunset42!" in resp.data
        assert b"password-banner" in resp.data
        assert b"font-mono" in resp.data
        # HX-Trigger header also present
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "Password reset successfully"


class TestEnableDisableEndpoints:
    """POST /search/api/write/enable and /disable."""

    def test_successful_enable(self, client, mock_write_ops):
        mock_write_ops.set_account_enabled.return_value = {
            "success": True,
            "message": "Account enabled",
        }

        resp = client.post("/search/api/write/enable", data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "New hire onboarding",
        })

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "Account enabled successfully"

    def test_successful_disable(self, client, mock_write_ops):
        mock_write_ops.set_account_enabled.return_value = {
            "success": True,
            "message": "Account disabled",
        }

        resp = client.post("/search/api/write/disable", data={
            "user_dn": "CN=Test,DC=example,DC=com",
            "display_name": "Test User",
            "reason": "Termination per HR",
        })

        assert resp.status_code == 200
        trigger = json.loads(resp.headers["HX-Trigger"])
        assert trigger["showToast"]["message"] == "Account disabled successfully"
