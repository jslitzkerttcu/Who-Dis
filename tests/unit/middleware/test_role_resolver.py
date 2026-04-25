"""Boundary tests for RoleResolver (Plan 02-06 gap closure round 2)."""
import pytest
from flask import Flask

from app.middleware.role_resolver import RoleResolver

pytestmark = pytest.mark.unit


def _ctx(roles=None):
    """Create a Flask test request context with a populated session."""
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    ctx = app.test_request_context()
    ctx.push()
    from flask import session
    if roles is not None:
        session["user"] = {"email": "x@x.com", "roles": roles}
    return ctx


def test_get_user_role_admin_when_admin_in_claims():
    ctx = _ctx(["admin"])
    try:
        assert RoleResolver().get_user_role("x@x.com") == "admin"
    finally:
        ctx.pop()


def test_get_user_role_viewer_when_only_viewer_in_claims():
    ctx = _ctx(["viewer"])
    try:
        assert RoleResolver().get_user_role("x@x.com") == "viewer"
    finally:
        ctx.pop()


def test_get_user_role_admin_takes_precedence_over_viewer():
    ctx = _ctx(["viewer", "admin"])
    try:
        assert RoleResolver().get_user_role("x@x.com") == "admin"
    finally:
        ctx.pop()


def test_get_user_role_returns_none_when_no_known_role():
    ctx = _ctx(["randomrole"])
    try:
        assert RoleResolver().get_user_role("x@x.com") is None
    finally:
        ctx.pop()


def test_get_user_role_returns_none_when_no_session_user():
    ctx = _ctx(roles=None)
    try:
        assert RoleResolver().get_user_role("x@x.com") is None
    finally:
        ctx.pop()


def test_has_minimum_role_admin_satisfies_admin():
    assert RoleResolver().has_minimum_role("admin", "admin") is True


def test_has_minimum_role_admin_satisfies_viewer():
    assert RoleResolver().has_minimum_role("admin", "viewer") is True


def test_has_minimum_role_viewer_does_not_satisfy_admin():
    assert RoleResolver().has_minimum_role("viewer", "admin") is False


def test_has_minimum_role_legacy_editor_treated_as_admin():
    """D-05 collapsed the hierarchy; legacy 'editor' minimum maps to admin."""
    rr = RoleResolver()
    assert rr.has_minimum_role("admin", "editor") is True
    assert rr.has_minimum_role("viewer", "editor") is False


def test_has_minimum_role_invalid_user_role_returns_false():
    assert RoleResolver().has_minimum_role("garbage", "viewer") is False


def test_has_minimum_role_invalid_minimum_role_returns_false():
    assert RoleResolver().has_minimum_role("admin", "garbage") is False


def test_is_valid_role():
    rr = RoleResolver()
    assert rr.is_valid_role("admin") is True
    assert rr.is_valid_role("viewer") is True
    assert rr.is_valid_role("editor") is False  # D-05 removed
    assert rr.is_valid_role("garbage") is False


def test_load_role_lists_returns_empty_tuple():
    """Deprecated method — kept for backwards compatibility, returns empty lists."""
    a, b, c = RoleResolver()._load_role_lists()
    assert a == []
    assert b == []
    assert c == []
