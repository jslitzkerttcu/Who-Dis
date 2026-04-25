"""Boundary tests for init_security_headers (Plan 02-06 gap closure round 2)."""
import pytest
from flask import Flask

from app.middleware.security_headers import init_security_headers

pytestmark = pytest.mark.unit


def _app_with_headers() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    init_security_headers(app)

    @app.route("/_probe")
    def _probe():
        return "ok"

    return app


def test_csp_header_set_with_expected_directives():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    csp = resp.headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "form-action 'self'" in csp


def test_xframe_options_is_deny():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    assert resp.headers["X-Frame-Options"] == "DENY"


def test_xcontent_type_options_is_nosniff():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_xss_protection_header_set():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    assert resp.headers["X-XSS-Protection"] == "1; mode=block"


def test_referrer_policy_strict_origin_when_cross_origin():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_permissions_policy_disables_sensors():
    client = _app_with_headers().test_client()
    resp = client.get("/_probe")
    pp = resp.headers["Permissions-Policy"]
    assert "geolocation=()" in pp
    assert "camera=()" in pp
    assert "microphone=()" in pp


def test_security_headers_apply_to_every_response():
    """All routes get the headers — they're an after_request hook."""
    app = _app_with_headers()

    @app.route("/_other")
    def _other():
        return "other-ok"

    client = app.test_client()
    resp = client.get("/_other")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in resp.headers
