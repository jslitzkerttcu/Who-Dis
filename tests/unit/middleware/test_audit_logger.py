"""Boundary tests for AuditLogger middleware (Plan 02-06 gap closure round 2)."""
import pytest
from flask import Flask

from app.middleware.audit_logger import AuditLogger

pytestmark = pytest.mark.unit


def _ctx(headers=None, path="/test"):
    a = Flask(__name__)
    a.config["SECRET_KEY"] = "test-secret"
    return a.test_request_context(path=path, headers=headers or {})


def test_log_access_denied_writes_audit_row(mocker):
    fake_audit = mocker.MagicMock()
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )
    with _ctx({"X-Forwarded-For": "1.2.3.4", "User-Agent": "ua"}, path="/admin"):
        AuditLogger().log_access_denied(user_email="u@x.com", user_role="viewer")
    fake_audit.log_access.assert_called_once()
    kwargs = fake_audit.log_access.call_args.kwargs
    assert kwargs["user_email"] == "u@x.com"
    assert kwargs["action"] == "access_denied"
    assert kwargs["target_resource"] == "/admin"
    assert kwargs["success"] is False


def test_log_access_denied_uses_unauthenticated_when_email_missing(mocker):
    fake_audit = mocker.MagicMock()
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )
    with _ctx():
        AuditLogger().log_access_denied()
    kwargs = fake_audit.log_access.call_args.kwargs
    assert kwargs["user_email"] == "unauthenticated"
    assert kwargs["user_role"] == "unknown"


def test_log_access_denied_swallows_audit_failure(mocker):
    """Audit failures must not propagate — they cannot break the auth flow."""
    fake_audit = mocker.MagicMock()
    fake_audit.log_access.side_effect = RuntimeError("audit dead")
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )
    with _ctx():
        AuditLogger().log_access_denied(user_email="u@x.com")  # No exception


def test_log_authentication_success_writes_audit_row(mocker):
    fake_audit = mocker.MagicMock()
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )
    with _ctx({"X-Forwarded-For": "5.6.7.8"}, path="/dashboard"):
        AuditLogger().log_authentication_success("u@x.com", "admin")
    kwargs = fake_audit.log_access.call_args.kwargs
    assert kwargs["user_email"] == "u@x.com"
    assert kwargs["action"] == "authentication"
    assert kwargs["user_role"] == "admin"
    assert kwargs["target_resource"] == "/dashboard"
    assert kwargs["success"] is True


def test_log_authentication_success_swallows_audit_failure(mocker):
    fake_audit = mocker.MagicMock()
    fake_audit.log_access.side_effect = RuntimeError("audit dead")
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )
    with _ctx():
        AuditLogger().log_authentication_success("u@x.com", "admin")  # No exception
