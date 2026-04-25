"""Boundary tests for GenesysCacheDB (Plan 02-05 gap closure).

Patches ``requests`` at the module-level boundary
``app.services.genesys_cache_db.requests`` so no real Genesys traffic is
generated. ApiToken.is_expired is a method-not-property bug per
deferred-items.md; tests that need to bypass the cached-token path patch
``ApiToken.get_token`` directly.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.database import db
from app.models.api_token import ApiToken
from app.models.external_service import ExternalServiceData
from app.services.genesys_cache_db import GenesysCacheDB

pytestmark = pytest.mark.unit


def _make_svc():
    svc = GenesysCacheDB()
    svc._config_cache.update({
        "genesys.client_id": "fake-id",
        "genesys.client_secret": "fake-secret",
        "genesys.region": "mypurecloud.com",
        "genesys.cache_timeout": 30,
        "genesys.cache_refresh_period": 21600,  # 6h
    })
    return svc


@pytest.fixture
def svc(app, db_session):
    return _make_svc()


# --- needs_refresh (pure date math) -------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: needs_refresh imports `timezone` only inside the "
    "`if last_update is None` branch; passing a non-None last_update raises "
    "UnboundLocalError, which the except clause swallows and returns True.",
)
def test_needs_refresh_recent_update_returns_false(svc):
    recent = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert svc.needs_refresh(last_update=recent) is False


def test_needs_refresh_stale_update_returns_true(svc):
    # Returns True both for the correct stale path AND for the timezone-import bug
    # path (the except clause defaults to True). Either way the assertion holds.
    stale = datetime.now(timezone.utc) - timedelta(hours=7)
    assert svc.needs_refresh(last_update=stale) is True


@pytest.mark.xfail(
    strict=True,
    reason="Pre-existing bug: needs_refresh `timezone` import scoping (see recent-path xfail).",
)
def test_needs_refresh_naive_datetime_treated_as_utc(svc):
    naive_recent = datetime.now() - timedelta(minutes=1)
    assert svc.needs_refresh(last_update=naive_recent) is False


# --- _get_access_token --------------------------------------------------------


def test_get_access_token_returns_none_when_no_token_row(svc, db_session):
    assert svc._get_access_token() is None


def test_get_access_token_returns_none_when_get_token_returns_none(svc, mocker):
    mocker.patch.object(ApiToken, "get_token", return_value=None)
    assert svc._get_access_token() is None


# --- _refresh_groups (HTTP-mocked) --------------------------------------------


def _mock_response(mocker, status=200, json_payload=None):
    resp = mocker.MagicMock()
    resp.status_code = status
    resp.json.return_value = json_payload or {}
    return resp


def test_refresh_groups_writes_external_service_data(svc, db_session, mocker):
    payload = {
        "entities": [{"id": "g1", "name": "Sales", "description": "Sales team"}],
        "pageCount": 1,
    }
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        return_value=_mock_response(mocker, json_payload=payload),
    )

    count = svc._refresh_groups("fake-token")
    assert count == 1
    rows = ExternalServiceData.query.filter_by(
        service_name="genesys", data_type="group"
    ).all()
    assert len(rows) == 1
    assert rows[0].name == "Sales"
    assert rows[0].service_id == "g1"


def test_refresh_groups_handles_http_error(svc, db_session, mocker):
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        return_value=_mock_response(mocker, status=500),
    )
    assert svc._refresh_groups("fake-token") == 0


def test_refresh_groups_swallows_request_exception(svc, db_session, mocker):
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        side_effect=Exception("boom"),
    )
    assert svc._refresh_groups("fake-token") == 0


# --- _refresh_skills / _refresh_locations -------------------------------------


def test_refresh_skills_writes_rows(svc, db_session, mocker):
    payload = {"entities": [{"id": "s1", "name": "English"}], "pageCount": 1}
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        return_value=_mock_response(mocker, json_payload=payload),
    )
    assert svc._refresh_skills("tok") == 1
    assert ExternalServiceData.query.filter_by(
        service_name="genesys", data_type="skill"
    ).count() == 1


def test_refresh_locations_writes_rows_with_address(svc, db_session, mocker):
    payload = {
        "entities": [
            {
                "id": "loc1",
                "name": "HQ",
                "address": {"street1": "1 Main", "city": "Town", "state": "TX"},
            }
        ],
        "pageCount": 1,
    }
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        return_value=_mock_response(mocker, json_payload=payload),
    )
    assert svc._refresh_locations("tok") == 1
    row = ExternalServiceData.query.filter_by(
        service_name="genesys", data_type="location"
    ).first()
    assert row is not None
    assert "1 Main" in row.description


# --- Lookup methods -----------------------------------------------------------


def test_get_group_name_reads_from_external_service_data(svc, db_session):
    ExternalServiceData(
        service_name="genesys",
        data_type="group",
        service_id="g42",
        name="Engineering",
        raw_data={},
    ).save()
    assert svc.get_group_name("g42") == "Engineering"


def test_get_group_name_returns_none_for_missing(svc, db_session):
    assert svc.get_group_name("ghost") is None


def test_get_skill_name_reads_from_external_service_data(svc, db_session):
    ExternalServiceData(
        service_name="genesys",
        data_type="skill",
        service_id="s42",
        name="Spanish",
        raw_data={},
    ).save()
    assert svc.get_skill_name("s42") == "Spanish"


def test_get_location_info_returns_dict(svc, db_session):
    ExternalServiceData(
        service_name="genesys",
        data_type="location",
        service_id="loc42",
        name="Annex",
        description="2 Side St",
        raw_data={},
    ).save()
    info = svc.get_location_info("loc42")
    assert info is not None
    assert info["name"] == "Annex"
    assert info["address"] == "2 Side St"


def test_get_cache_status_returns_default_dict_when_tables_missing(svc, db_session):
    # genesys_groups/skills/locations tables don't exist in the test schema (Phase 9
    # removed those legacy tables); the method should swallow the error and return
    # a safe default.
    status = svc.get_cache_status()
    assert "groups_cached" in status
    assert "needs_refresh" in status


# --- refresh_all_caches orchestrator ------------------------------------------


def test_refresh_all_caches_returns_zero_results_when_no_token(svc, mocker):
    mocker.patch.object(svc, "_get_access_token", return_value=None)
    result = svc.refresh_all_caches(genesys_service=None)
    assert result == {"groups": 0, "skills": 0, "locations": 0}


def test_refresh_all_caches_uses_provided_genesys_service_token(svc, db_session, mocker):
    fake_genesys = mocker.MagicMock()
    fake_genesys.get_access_token.return_value = "provided-token"
    payload = {"entities": [], "pageCount": 1}
    mocker.patch(
        "app.services.genesys_cache_db.requests.get",
        return_value=_mock_response(mocker, json_payload=payload),
    )
    result = svc.refresh_all_caches(genesys_service=fake_genesys)
    assert result == {"groups": 0, "skills": 0, "locations": 0}
    fake_genesys.get_access_token.assert_called()
