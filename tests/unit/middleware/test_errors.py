"""Boundary tests for handle_errors decorator (Plan 02-06 gap closure round 2)."""
import pytest
from flask import Flask

from app.middleware.errors import handle_errors

pytestmark = pytest.mark.unit


def _fresh_app(debug: bool = False) -> Flask:
    a = Flask(__name__)
    a.config["SECRET_KEY"] = "test-secret-key"
    a.config["TESTING"] = True
    a.debug = debug
    return a


def test_handle_errors_passthrough_on_success():
    app = _fresh_app()

    @app.route("/_ok")
    @handle_errors()
    def _ok():
        return "ok"

    client = app.test_client()
    resp = client.get("/_ok")
    assert resp.status_code == 200
    assert resp.data == b"ok"


def test_handle_errors_returns_500_html_on_exception():
    app = _fresh_app(debug=False)

    @app.route("/_boom")
    @handle_errors()
    def _boom():
        raise RuntimeError("expected")

    client = app.test_client()
    resp = client.get("/_boom")
    assert resp.status_code == 500
    assert b"internal error" in resp.data.lower()
    # debug=False should mask the message
    assert b"expected" not in resp.data


def test_handle_errors_returns_500_html_with_message_in_debug():
    app = _fresh_app(debug=True)

    @app.route("/_boom_dbg")
    @handle_errors()
    def _boom():
        raise RuntimeError("debug-mode message")

    client = app.test_client()
    resp = client.get("/_boom_dbg")
    assert resp.status_code == 500
    assert b"debug-mode message" in resp.data


def test_handle_errors_returns_json_when_flag_true():
    app = _fresh_app()

    @app.route("/_boom_json")
    @handle_errors(json_response=True)
    def _boom():
        raise ValueError("json please")

    client = app.test_client()
    resp = client.get("/_boom_json")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False
    assert "error" in body


def test_handle_errors_returns_json_for_api_path():
    """Path starting with /api/ auto-switches to JSON response."""
    app = _fresh_app()

    @app.route("/api/_thing")
    @handle_errors()
    def _boom():
        raise RuntimeError("api boom")

    client = app.test_client()
    resp = client.get("/api/_thing")
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False


def test_handle_errors_returns_json_for_json_request():
    """request.is_json triggers JSON response even on non-/api/ path."""
    app = _fresh_app()

    @app.route("/_thing", methods=["POST"])
    @handle_errors()
    def _boom():
        raise RuntimeError("json boom")

    client = app.test_client()
    resp = client.post("/_thing", json={"a": 1})
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["success"] is False


def test_handle_errors_continues_when_audit_log_raises(mocker):
    """If the audit-log call itself fails, the request still returns 500
    cleanly — the audit failure must not mask the original error."""
    app = _fresh_app()

    # Patch the audit service to raise during error logging
    import app.middleware.errors as errors_mod
    fake_audit = mocker.MagicMock()
    fake_audit.log_error.side_effect = RuntimeError("audit dead")
    mocker.patch(
        "app.services.audit_service_postgres.audit_service",
        fake_audit,
    )

    @app.route("/_boom_audit")
    @handle_errors()
    def _boom():
        raise RuntimeError("real bug")

    client = app.test_client()
    resp = client.get("/_boom_audit")
    assert resp.status_code == 500
