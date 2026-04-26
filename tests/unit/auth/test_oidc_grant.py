"""Unit tests for the auto-grant helper in app.auth.oidc.

The helper decides whether to grant a default who-dis client role to a
freshly-federated user and returns the role that was newly granted (or None).
KeycloakAdminClient is mocked — we don't talk to Keycloak.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.auth.oidc import _grant_default_role_if_missing


@pytest.fixture(autouse=True)
def _kc_env(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "who-dis")
    monkeypatch.delenv("WHODIS_LEGACY_ADMINS", raising=False)
    monkeypatch.delenv("WHODIS_AUTOGRANT_DISABLED", raising=False)


def test_skips_when_admin_already_in_claims():
    fake_admin = MagicMock()
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("a@b.test", ["admin"])
    assert result is None
    fake_admin.find_user_id_by_email.assert_not_called()


def test_skips_when_viewer_already_in_claims():
    fake_admin = MagicMock()
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("a@b.test", ["viewer"])
    assert result is None
    fake_admin.find_user_id_by_email.assert_not_called()


def test_skips_when_disabled_via_env(monkeypatch):
    monkeypatch.setenv("WHODIS_AUTOGRANT_DISABLED", "1")
    fake_admin = MagicMock()
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("a@b.test", [])
    assert result is None
    fake_admin.find_user_id_by_email.assert_not_called()


def test_grants_viewer_for_unknown_email():
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = "uid-1"
    fake_admin.assign_client_role.return_value = True
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("newhire@b.test", [])
    assert result == "viewer"
    fake_admin.assign_client_role.assert_called_once_with(
        user_id="uid-1", client_id="who-dis", role_name="viewer"
    )


def test_grants_admin_for_legacy_email(monkeypatch):
    monkeypatch.setenv(
        "WHODIS_LEGACY_ADMINS", "dbarron@ttcu.com,dlight@ttcu.com,jbotts@ttcu.com"
    )
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = "uid-2"
    fake_admin.assign_client_role.return_value = True
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("dlight@ttcu.com", [])
    assert result == "admin"
    fake_admin.assign_client_role.assert_called_once_with(
        user_id="uid-2", client_id="who-dis", role_name="admin"
    )


def test_legacy_email_lookup_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("WHODIS_LEGACY_ADMINS", "  DBarron@TTCU.COM  ,  ")
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = "uid-3"
    fake_admin.assign_client_role.return_value = True
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        # email arrives lowercased per oidc.py:authorize() (.strip().lower())
        result = _grant_default_role_if_missing("dbarron@ttcu.com", [])
    assert result == "admin"


def test_returns_none_when_user_not_in_keycloak():
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = None
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("ghost@b.test", [])
    assert result is None
    fake_admin.assign_client_role.assert_not_called()


def test_returns_role_even_when_already_assigned():
    """If KC reports the role already exists for the user, still return it
    so the in-flight session gets the role injected."""
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = "uid-4"
    fake_admin.assign_client_role.return_value = False  # already had it
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("tpeterson@ttcu.com", [])
    assert result == "viewer"


def test_swallows_keycloak_failure(caplog):
    """A Keycloak error must not block login — return None and log."""
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.side_effect = RuntimeError("kc down")
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        with caplog.at_level("ERROR"):
            result = _grant_default_role_if_missing("a@b.test", [])
    assert result is None
    assert any("auto-grant: failed" in rec.message for rec in caplog.records)


def test_unknown_role_in_claims_still_triggers_grant():
    """A claim like ['some-unrelated-role'] does not match {admin,viewer},
    so we still grant a default — otherwise the user is locked out."""
    fake_admin = MagicMock()
    fake_admin.find_user_id_by_email.return_value = "uid-5"
    fake_admin.assign_client_role.return_value = True
    with patch(
        "app.services.keycloak_admin.KeycloakAdminClient", return_value=fake_admin
    ):
        result = _grant_default_role_if_missing("a@b.test", ["uma_authorization"])
    assert result == "viewer"
