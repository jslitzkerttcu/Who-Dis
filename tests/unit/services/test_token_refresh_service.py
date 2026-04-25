"""Boundary tests for TokenRefreshService (Plan 02-06 gap closure round 2).

The service has a background-thread runner; the TESTING gate in app/__init__.py
prevents auto-start during tests. These tests call the public sync methods
directly — never invoke ``_run`` (the thread loop) which would block on
``time.sleep(self.check_interval)``.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.interfaces.token_service import ITokenService
from app.services.token_refresh_service import TokenRefreshService

pytestmark = pytest.mark.unit


class _FakeTokenService(ITokenService):
    """Minimal ITokenService that satisfies the interface and records calls."""

    def __init__(self, name: str, refresh_returns: bool = True, refresh_raises: bool = False):
        self._name = name
        self._refresh_returns = refresh_returns
        self._refresh_raises = refresh_raises
        self.refresh_calls = 0

    @property
    def token_service_name(self) -> str:
        return self._name

    def refresh_token_if_needed(self) -> bool:
        self.refresh_calls += 1
        if self._refresh_raises:
            raise RuntimeError(f"{self._name} blew up")
        return self._refresh_returns

    def get_access_token(self):
        return "fake-token"


# ----------------- construction / lifecycle (no thread) ----------------------


def test_constructor_defaults():
    svc = TokenRefreshService()
    assert svc.is_running is False
    assert svc.thread is None
    assert svc.check_interval == 300


def test_init_app_attaches_flask_app(app):
    svc = TokenRefreshService()
    svc.init_app(app)
    assert svc.app is app


def test_stop_when_not_running_is_idempotent():
    svc = TokenRefreshService()
    svc.stop()  # No thread, no exception
    assert svc.is_running is False


def test_start_sets_is_running_then_stop_resets(mocker):
    """Smoke-test start/stop without letting the loop run.

    Patch ``_run`` so the daemon thread exits immediately, then assert the
    state machine. We never let the production loop iterate."""
    svc = TokenRefreshService()
    mocker.patch.object(svc, "_run", lambda: None)
    svc.start()
    assert svc.is_running is True
    assert svc.thread is not None
    svc.stop()
    assert svc.is_running is False


def test_start_when_already_running_logs_warning_and_skips(mocker, caplog):
    svc = TokenRefreshService()
    mocker.patch.object(svc, "_run", lambda: None)
    svc.start()
    try:
        with caplog.at_level("WARNING"):
            svc.start()  # Second call: warns + skips
        assert any("already running" in r.message for r in caplog.records)
    finally:
        svc.stop()


# ----------------- _check_and_refresh_tokens ---------------------------------


def test_check_and_refresh_returns_early_when_no_app(caplog):
    svc = TokenRefreshService()  # no app set
    with caplog.at_level("WARNING"):
        svc._check_and_refresh_tokens()
    assert any("No Flask app" in r.message for r in caplog.records)


def test_check_and_refresh_uses_container_when_present(app, mocker):
    svc = TokenRefreshService(app=app)
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = []
    svc.container = container
    svc._check_and_refresh_tokens()
    container.get_all_by_interface.assert_called_once_with(ITokenService)


# ----------------- _refresh_using_container ----------------------------------


def test_refresh_using_container_no_token_entry_skips(app, mocker, db_session):
    """When ApiToken.get_token returns None, no refresh is attempted."""
    svc = TokenRefreshService(app=app)
    fake = _FakeTokenService("genesys")
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = [fake]
    svc.container = container
    mocker.patch("app.models.api_token.ApiToken.get_token", return_value=None)
    with app.app_context():
        svc._refresh_using_container()
    assert fake.refresh_calls == 0


def test_refresh_using_container_refreshes_when_expiring_soon(app, mocker, db_session):
    """Token expiring within 10 minutes triggers refresh_token_if_needed."""
    svc = TokenRefreshService(app=app)
    fake = _FakeTokenService("genesys", refresh_returns=True)
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = [fake]
    svc.container = container

    expiring_soon = mocker.MagicMock()
    expiring_soon.expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
    mocker.patch("app.models.api_token.ApiToken.get_token", return_value=expiring_soon)

    with app.app_context():
        svc._refresh_using_container()
    assert fake.refresh_calls == 1


def test_refresh_using_container_skips_when_token_still_fresh(app, mocker, db_session):
    """Token with >10 minutes remaining is left alone."""
    svc = TokenRefreshService(app=app)
    fake = _FakeTokenService("genesys")
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = [fake]
    svc.container = container

    fresh = mocker.MagicMock()
    fresh.expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
    mocker.patch("app.models.api_token.ApiToken.get_token", return_value=fresh)

    with app.app_context():
        svc._refresh_using_container()
    assert fake.refresh_calls == 0


def test_refresh_using_container_one_service_failure_does_not_stop_others(app, mocker, db_session):
    """If one service raises during refresh, the orchestrator catches and
    continues with the next service."""
    svc = TokenRefreshService(app=app)
    bad = _FakeTokenService("graph", refresh_raises=True)
    good = _FakeTokenService("genesys", refresh_returns=True)
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = [bad, good]
    svc.container = container

    expiring = mocker.MagicMock()
    expiring.expires_at = datetime.now(timezone.utc) + timedelta(minutes=1)
    mocker.patch("app.models.api_token.ApiToken.get_token", return_value=expiring)

    with app.app_context():
        svc._refresh_using_container()
    # Bad service raised, but good service still refreshed
    assert good.refresh_calls == 1


def test_refresh_using_container_naive_datetime_normalized(app, mocker, db_session):
    """Naive (tz-less) expires_at timestamps are coerced to UTC, not crashed on."""
    svc = TokenRefreshService(app=app)
    fake = _FakeTokenService("genesys", refresh_returns=True)
    container = mocker.MagicMock()
    container.get_all_by_interface.return_value = [fake]
    svc.container = container

    naive = mocker.MagicMock()
    naive.expires_at = datetime.utcnow() + timedelta(minutes=2)  # naive  # noqa: DTZ003
    mocker.patch("app.models.api_token.ApiToken.get_token", return_value=naive)

    with app.app_context():
        svc._refresh_using_container()
    assert fake.refresh_calls == 1
