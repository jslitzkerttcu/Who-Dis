"""Boundary tests for DoubleSubmitCSRF (Plan 02-06 gap closure round 2).

Pure unit tests against generate_token / validate_token / get_*_token /
protect / exempt. Uses Flask's test client to exercise the protect()
decorator end-to-end.

Each test that registers a route uses a *fresh* Flask app to avoid
view-name collisions with the session-scoped ``app`` fixture from
tests/conftest.py.
"""
import time

import pytest
from flask import Flask, jsonify

from app.middleware.csrf import DoubleSubmitCSRF, ensure_csrf_cookie

pytestmark = pytest.mark.unit


def _fresh_app() -> Flask:
    """Build a minimal Flask app with the env vars CSRF expects.

    Avoids importing the full app factory (which boots OIDC, DB, etc.)
    and keeps each test's route registry isolated.
    """
    a = Flask(__name__)
    a.config["SECRET_KEY"] = "test-secret-key"
    a.config["TESTING"] = True
    return a


# ----------------- token generate / validate ---------------------------------


def test_generate_token_format():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        token = csrf.generate_token()
    parts = token.split(":")
    assert len(parts) == 3
    timestamp, random_data, signature = parts
    assert timestamp.isdigit()
    assert len(random_data) > 0
    assert len(signature) == 64  # sha256 hex


def test_validate_token_round_trip():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        token = csrf.generate_token()
        assert csrf.validate_token(token) is True


def test_validate_token_empty_returns_false():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        assert csrf.validate_token("") is False
        assert csrf.validate_token(None) is False


def test_validate_token_wrong_part_count_returns_false():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        assert csrf.validate_token("only-one-part") is False
        assert csrf.validate_token("a:b") is False
        assert csrf.validate_token("a:b:c:d") is False


def test_validate_token_non_numeric_timestamp_returns_false():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        assert csrf.validate_token("notanumber:random:signature") is False


def test_validate_token_expired_returns_false():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        old_timestamp = str(int(time.time()) - 10000)  # 10000s ago
        # Use a real signature so signature check passes; expiration check fails first
        import hashlib
        import hmac
        secret = app.config["SECRET_KEY"].encode()
        message = f"{old_timestamp}:random".encode()
        sig = hmac.new(secret, message, hashlib.sha256).hexdigest()
        token = f"{old_timestamp}:random:{sig}"
        assert csrf.validate_token(token) is False


def test_validate_token_bad_signature_returns_false():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    with app.app_context():
        good = csrf.generate_token()
        ts, rnd, _sig = good.split(":")
        bad = f"{ts}:{rnd}:" + "0" * 64
        assert csrf.validate_token(bad) is False


# ----------------- get_cookie_token / get_header_token -----------------------


def test_get_cookie_and_header_tokens():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]
    header_name = app.config["CSRF_HEADER_NAME"]

    @app.route("/_csrf_probe")
    def _probe():
        return jsonify(
            cookie=csrf.get_cookie_token(),
            header=csrf.get_header_token(),
        )

    client = app.test_client()
    client.set_cookie(cookie_name, "cook-token")
    resp = client.get("/_csrf_probe", headers={header_name: "hdr-token"})
    assert resp.json == {"cookie": "cook-token", "header": "hdr-token"}


# ----------------- protect() decorator end-to-end ----------------------------


def test_protect_get_skips_csrf_check():
    """GET requests bypass CSRF — required for normal page loads."""
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)

    @app.route("/_csrf_get")
    @csrf.protect
    def _get():
        return "ok"

    client = app.test_client()
    assert client.get("/_csrf_get").data == b"ok"


def test_protect_post_missing_tokens_returns_403():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)

    @app.route("/_csrf_post1", methods=["POST"])
    @csrf.protect
    def _p():
        return "ok"

    client = app.test_client()
    resp = client.post("/_csrf_post1")
    assert resp.status_code == 403


def test_protect_post_mismatched_tokens_returns_403():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]
    header_name = app.config["CSRF_HEADER_NAME"]

    @app.route("/_csrf_post2", methods=["POST"])
    @csrf.protect
    def _p():
        return "ok"

    client = app.test_client()
    client.set_cookie(cookie_name, "abc")
    resp = client.post("/_csrf_post2", headers={header_name: "xyz"})
    assert resp.status_code == 403


def test_protect_post_invalid_token_returns_403():
    """Cookie==Header but token signature invalid -> 403."""
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]
    header_name = app.config["CSRF_HEADER_NAME"]

    @app.route("/_csrf_post3", methods=["POST"])
    @csrf.protect
    def _p():
        return "ok"

    bogus = "1:2:3"
    client = app.test_client()
    client.set_cookie(cookie_name, bogus)
    resp = client.post("/_csrf_post3", headers={header_name: bogus})
    assert resp.status_code == 403


def test_protect_post_valid_token_allows_request():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]
    header_name = app.config["CSRF_HEADER_NAME"]

    @app.route("/_csrf_post4", methods=["POST"])
    @csrf.protect
    def _p():
        return "ok"

    with app.app_context():
        token = csrf.generate_token()
    client = app.test_client()
    client.set_cookie(cookie_name, token)
    resp = client.post("/_csrf_post4", headers={header_name: token})
    assert resp.status_code == 200
    assert resp.data == b"ok"


# ----------------- exempt() ---------------------------------------------------


def test_exempt_marks_function():
    csrf = DoubleSubmitCSRF()

    def view():
        return "ok"

    exempted = csrf.exempt(view)
    assert getattr(exempted, "_csrf_exempt", False) is True


# ----------------- ensure_csrf_cookie decorator -------------------------------


def test_ensure_csrf_cookie_sets_cookie_when_missing():
    app = _fresh_app()
    DoubleSubmitCSRF().init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]

    @app.route("/_csrf_ensure1")
    @ensure_csrf_cookie
    def _v():
        return "page"

    client = app.test_client()
    resp = client.get("/_csrf_ensure1")
    cookies = resp.headers.getlist("Set-Cookie")
    assert any(cookie_name in c for c in cookies)


def test_ensure_csrf_cookie_keeps_existing_valid_token():
    app = _fresh_app()
    csrf = DoubleSubmitCSRF()
    csrf.init_app(app)
    cookie_name = app.config["CSRF_COOKIE_NAME"]

    @app.route("/_csrf_ensure2")
    @ensure_csrf_cookie
    def _v():
        return "page"

    with app.app_context():
        token = csrf.generate_token()
    client = app.test_client()
    client.set_cookie(cookie_name, token)
    resp = client.get("/_csrf_ensure2")
    cookies = resp.headers.getlist("Set-Cookie")
    assert not any(cookie_name in c for c in cookies)
