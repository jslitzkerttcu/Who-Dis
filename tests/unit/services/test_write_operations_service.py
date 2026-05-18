"""Unit tests for WriteOperationsService coordinator.

Verifies that each method calls the correct underlying service and always
logs via audit_logger.log_admin_action with expected action/details.
"""

import pytest
from unittest.mock import MagicMock

import flask
from flask import g

from app.services.write_operations import WriteOperationsService

pytestmark = pytest.mark.unit


@pytest.fixture
def _minimal_app():
    """Minimal Flask app for request context (no DB needed)."""
    app = flask.Flask(__name__)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def write_ops(_minimal_app):
    """Provide a WriteOperationsService with mocked dependencies."""
    with _minimal_app.test_request_context(
        headers={"X-Forwarded-For": "10.0.0.1", "User-Agent": "TestAgent"}
    ):
        g.user = "admin@test.com"
        g.role = "admin"
        svc = WriteOperationsService()
        svc._ldap_service = MagicMock()
        svc._graph_service = MagicMock()
        svc._audit_logger = MagicMock()
        yield svc


class TestUnlockAccount:
    def test_calls_ldap_and_audits(self, write_ops):
        write_ops._ldap_service.unlock_account.return_value = True

        result = write_ops.unlock_account("CN=User,DC=x", "Test User", "Ticket #123")

        assert result["success"] is True
        write_ops._ldap_service.unlock_account.assert_called_once_with("CN=User,DC=x")
        write_ops._audit_logger.log_admin_action.assert_called_once()
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "unlock_account"
        assert call_kwargs["target"] == "CN=User,DC=x"
        assert call_kwargs["details"]["reason"] == "Ticket #123"
        assert call_kwargs["details"]["success"] is True

    def test_failure_still_audits(self, write_ops):
        write_ops._ldap_service.unlock_account.return_value = False

        result = write_ops.unlock_account("CN=User,DC=x", "Test User", "Ticket #123")

        assert result["success"] is False
        write_ops._audit_logger.log_admin_action.assert_called_once()


class TestResetPassword:
    def test_success_returns_password_in_data(self, write_ops):
        write_ops._ldap_service.reset_password.return_value = True

        result = write_ops.reset_password("CN=User,DC=x", "Test User", "Ticket #456")

        assert result["success"] is True
        assert "password" in result["data"]
        # Password should be non-empty
        assert len(result["data"]["password"]) >= 8

    def test_password_never_in_audit_details(self, write_ops):
        write_ops._ldap_service.reset_password.return_value = True

        write_ops.reset_password("CN=User,DC=x", "Test User", "Ticket #456")

        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        details = call_kwargs["details"]
        # T-09-01: password MUST NOT appear in audit details
        assert "password" not in details
        assert "new_password" not in details

    def test_failure_returns_error(self, write_ops):
        write_ops._ldap_service.reset_password.return_value = False

        result = write_ops.reset_password("CN=User,DC=x", "Test User", "Ticket #456")

        assert result["success"] is False
        assert "error" in result


class TestSetAccountEnabled:
    def test_enable_uses_correct_action(self, write_ops):
        write_ops._ldap_service.set_account_enabled.return_value = True

        result = write_ops.set_account_enabled(
            "CN=User,DC=x", "Test User", enabled=True, reason="Rehired"
        )

        assert result["success"] is True
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "enable_account"

    def test_disable_uses_correct_action(self, write_ops):
        write_ops._ldap_service.set_account_enabled.return_value = True

        result = write_ops.set_account_enabled(
            "CN=User,DC=x", "Test User", enabled=False, reason="Terminated"
        )

        assert result["success"] is True
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "disable_account"


class TestAssignLicense:
    def test_calls_graph_and_audits(self, write_ops):
        write_ops._graph_service.assign_license.return_value = {"success": True}

        result = write_ops.assign_license(
            "user-123", "user@test.com", "sku-abc", "Office 365 E3", "New hire"
        )

        assert result["success"] is True
        write_ops._graph_service.assign_license.assert_called_once_with("user-123", "sku-abc")
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "assign_license"
        assert call_kwargs["target"] == "user@test.com"
        assert call_kwargs["details"]["sku_id"] == "sku-abc"
        assert call_kwargs["details"]["sku_name"] == "Office 365 E3"


class TestRemoveLicense:
    def test_calls_graph_and_audits(self, write_ops):
        write_ops._graph_service.remove_license.return_value = {"success": True}

        result = write_ops.remove_license(
            "user-123", "user@test.com", "sku-abc", "Office 365 E3", "Offboarding"
        )

        assert result["success"] is True
        write_ops._graph_service.remove_license.assert_called_once_with("user-123", "sku-abc")
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "remove_license"


class TestSwapLicense:
    def test_calls_graph_and_audits(self, write_ops):
        write_ops._graph_service.swap_license.return_value = {
            "success": True,
            "rollback_needed": False,
            "rollback_success": None,
        }

        result = write_ops.swap_license(
            "user-123", "user@test.com",
            "old-sku", "E3", "new-sku", "E5", "Upgrade"
        )

        assert result["success"] is True
        write_ops._graph_service.swap_license.assert_called_once_with(
            "user-123", "old-sku", "new-sku"
        )
        call_kwargs = write_ops._audit_logger.log_admin_action.call_args[1]
        assert call_kwargs["action"] == "swap_license"
        assert call_kwargs["details"]["old_sku_id"] == "old-sku"
        assert call_kwargs["details"]["new_sku_id"] == "new-sku"

    def test_double_failure_logs_manual_intervention(self, write_ops, caplog):
        import logging

        write_ops._graph_service.swap_license.return_value = {
            "success": False,
            "rollback_needed": True,
            "rollback_success": False,
            "error": "assign failed",
        }

        with caplog.at_level(logging.ERROR):
            result = write_ops.swap_license(
                "user-123", "user@test.com",
                "old-sku", "E3", "new-sku", "E5", "Upgrade"
            )

        assert result["success"] is False
        assert result["rollback_needed"] is True
        assert result["rollback_success"] is False
        assert "MANUAL_INTERVENTION_REQUIRED" in caplog.text
