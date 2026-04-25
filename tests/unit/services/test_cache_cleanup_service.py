"""Boundary tests for CacheCleanupService (Plan 02-06 gap closure round 2)."""
from datetime import datetime, timedelta

import pytest

from app.services.cache_cleanup_service import CacheCleanupService

pytestmark = pytest.mark.unit


def test_constructor_defaults():
    svc = CacheCleanupService()
    assert svc.is_running is False
    assert svc.thread is None
    assert svc.check_interval == 3600


def test_init_app_attaches_flask_app(app):
    svc = CacheCleanupService()
    svc.init_app(app)
    assert svc.app is app


def test_start_then_stop_state_machine(mocker):
    svc = CacheCleanupService()
    mocker.patch.object(svc, "_run", lambda: None)
    svc.start()
    assert svc.is_running is True
    assert svc.thread is not None
    svc.stop()
    assert svc.is_running is False


def test_start_idempotent_logs_warning(mocker, caplog):
    svc = CacheCleanupService()
    mocker.patch.object(svc, "_run", lambda: None)
    svc.start()
    try:
        with caplog.at_level("WARNING"):
            svc.start()
        assert any("already running" in r.message for r in caplog.records)
    finally:
        svc.stop()


def test_stop_when_not_started_is_idempotent():
    svc = CacheCleanupService()
    svc.stop()  # No exception
    assert svc.is_running is False


def test_cleanup_deletes_only_expired_rows(app, db_session):
    """_cleanup() removes SearchCache rows where expires_at < now, leaves
    fresh rows alone, returns (deleted_count, duration_ms)."""
    from app.database import db
    from app.models.cache import SearchCache

    now = datetime.utcnow()
    expired = SearchCache(
        search_query="expired-query",
        search_type="ldap",
        result_data={"a": 1},
        expires_at=now - timedelta(hours=1),
    )
    fresh = SearchCache(
        search_query="fresh-query",
        search_type="ldap",
        result_data={"b": 2},
        expires_at=now + timedelta(hours=1),
    )
    db.session.add_all([expired, fresh])
    db.session.commit()

    svc = CacheCleanupService(app=app)
    deleted, duration_ms = svc._cleanup()
    assert deleted >= 1
    assert duration_ms >= 0
    # Fresh row survives
    assert SearchCache.query.filter_by(search_query="fresh-query").first() is not None
    assert SearchCache.query.filter_by(search_query="expired-query").first() is None


def test_run_now_calls_cleanup(app, db_session, mocker):
    svc = CacheCleanupService(app=app)
    cleanup_spy = mocker.patch.object(svc, "_cleanup", return_value=(3, 12.5))
    result = svc.run_now()
    cleanup_spy.assert_called_once()
    assert result == (3, 12.5)


def test_cleanup_returns_zero_when_no_expired_rows(app, db_session):
    """Empty cache table -> _cleanup returns (0, duration)."""
    svc = CacheCleanupService(app=app)
    deleted, duration_ms = svc._cleanup()
    assert deleted == 0
    assert duration_ms >= 0
